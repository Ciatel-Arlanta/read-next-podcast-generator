"""
generator.py — Podcast Script Writer Agent

Uses a Hugging Face Inference Providers chat model
to convert article text into a structured two-person podcast script.
Falls back to a local GGUF model via llama-cpp-python if available.
"""

import json
import os
import re
import logging
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)

DEFAULT_HF_MODEL_ID = "openai/gpt-oss-120b:fastest"

try:
    from huggingface_hub import get_token as _hf_get_token
except ImportError:
    _hf_get_token = None

# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class DialogueLine:
    speaker: str   # "Host" or "Guest"
    text: str

@dataclass
class PodcastScript:
    title: str
    dialogue: list[DialogueLine] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "dialogue": [asdict(line) for line in self.dialogue],
        }


# ---------------------------------------------------------------------------
# Prompt Template
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a professional podcast script writer. Your job is to convert article content into an engaging, natural-sounding two-person podcast conversation.

RULES:
- The podcast has exactly two speakers: "Host" and "Guest".
- The Host drives the conversation with questions and transitions.
- The Guest is the expert who explains the content in depth.
- Make it conversational, not a lecture. Use natural language, occasional humor, and reactions like "That's a great point" or "Exactly!".
- Cover ALL the key points of the article but make them accessible.
- The dialogue should be 12-20 exchanges long (6-10 per speaker).
- Each speaker turn should be 1-3 sentences. Keep it punchy.

OUTPUT FORMAT:
You MUST respond with ONLY valid JSON matching this exact schema, with no other text before or after:
{
  "title": "A catchy podcast episode title",
  "dialogue": [
    {"speaker": "Host", "text": "..."},
    {"speaker": "Guest", "text": "..."},
    ...
  ]
}"""

USER_PROMPT_TEMPLATE = """Convert the following article into a podcast script following the rules above.

ARTICLE:
{article_text}

Remember: respond with ONLY the JSON object, nothing else."""


# ---------------------------------------------------------------------------
# JSON Extraction Helper
# ---------------------------------------------------------------------------

def _extract_json(raw: str) -> dict:
    """Robustly extract JSON from LLM output that may contain markdown fences."""
    # Try direct parse first
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Try extracting from ```json ... ``` blocks
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Try finding the first { ... } block
    brace_start = raw.find("{")
    brace_end = raw.rfind("}")
    if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
        try:
            return json.loads(raw[brace_start : brace_end + 1])
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not extract valid JSON from model output:\n{raw[:500]}")


def _parse_script(data: dict) -> PodcastScript:
    """Parse a raw dict into a validated PodcastScript."""
    title = data.get("title", "Untitled Episode")
    raw_dialogue = data.get("dialogue", [])
    dialogue = []
    for entry in raw_dialogue:
        speaker = entry.get("speaker", "Host")
        text = entry.get("text", "")
        if text.strip():
            dialogue.append(DialogueLine(speaker=speaker, text=text.strip()))
    if not dialogue:
        raise ValueError("Parsed script contains no dialogue lines.")
    return PodcastScript(title=title, dialogue=dialogue)


# ---------------------------------------------------------------------------
# Generator Backends
# ---------------------------------------------------------------------------

def _get_hf_token() -> str | None:
    """Return a Hugging Face token from the environment or CLI login cache."""
    env_token = os.environ.get("HF_TOKEN")
    if env_token:
        return env_token

    if _hf_get_token:
        return _hf_get_token()
    return None


def _get_hf_model_id() -> str:
    """Return the configured Hugging Face Inference Providers model ID."""
    return os.environ.get("HF_MODEL_ID", DEFAULT_HF_MODEL_ID)


def _generate_via_hf_api(article_text: str, model_id: str | None = None) -> str:
    """Call the free Hugging Face Serverless Inference API."""
    from huggingface_hub import InferenceClient

    model_id = model_id or _get_hf_model_id()
    token = _get_hf_token()
    client = InferenceClient(model=model_id, token=token)
    prompt = SYSTEM_PROMPT + "\n\n" + USER_PROMPT_TEMPLATE.format(article_text=article_text)

    if hasattr(client, "chat_completion"):
        messages = [{"role": "user", "content": prompt}]
        response = client.chat_completion(
            messages=messages,
            max_tokens=2048,
            temperature=0.7,
        )
        return response.choices[0].message.content

    return client.text_generation(
        prompt,
        max_new_tokens=2048,
        temperature=0.7,
        return_full_text=False,
    )


def _generate_via_llama_cpp(article_text: str, model_path: str) -> str:
    """Run inference locally using a GGUF model via llama-cpp-python."""
    from llama_cpp import Llama

    llm = Llama(
        model_path=model_path,
        n_ctx=4096,
        n_threads=2,       # Match HF free-tier vCPU count
        verbose=False,
    )

    prompt = (
        f"<start_of_turn>user\n"
        f"{SYSTEM_PROMPT}\n\n"
        f"{USER_PROMPT_TEMPLATE.format(article_text=article_text)}"
        f"<end_of_turn>\n"
        f"<start_of_turn>model\n"
    )

    output = llm(
        prompt,
        max_tokens=2048,
        temperature=0.7,
        stop=["<end_of_turn>"],
    )
    return output["choices"][0]["text"]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_script(article_text: str) -> PodcastScript:
    """
    Generate a podcast script from article text.

    Tries the HF Inference API first (fast, free, no local model needed).
    Falls back to a local GGUF model if no Hugging Face token is available
    and a local model file is available.
    """
    # Truncate very long articles to avoid token limits
    max_chars = 6000
    if len(article_text) > max_chars:
        logger.warning("Article too long (%d chars), truncating to %d", len(article_text), max_chars)
        article_text = article_text[:max_chars] + "\n\n[Article truncated for length...]"

    local_model_path = os.environ.get("LOCAL_MODEL_PATH")

    # Strategy 1: HF Inference API (preferred — fast, free)
    hf_token = _get_hf_token()
    if hf_token:
        logger.info("Using Hugging Face Inference API (%s)", _get_hf_model_id())
        try:
            raw = _generate_via_hf_api(article_text)
            data = _extract_json(raw)
            return _parse_script(data)
        except Exception as e:
            logger.error("HF Inference API failed: %s", e)
            if not local_model_path:
                raise

    # Strategy 2: Local GGUF model
    if local_model_path and os.path.exists(local_model_path):
        logger.info("Using local GGUF model at %s", local_model_path)
        raw = _generate_via_llama_cpp(article_text, local_model_path)
        data = _extract_json(raw)
        return _parse_script(data)

    raise RuntimeError(
        "No generation backend available. "
        "Set HF_TOKEN for the Hugging Face API, or set LOCAL_MODEL_PATH to a .gguf file."
    )
