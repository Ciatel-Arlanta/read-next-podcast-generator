"""
tts_engine.py — Multi-Speaker Text-to-Speech Engine

Uses Kokoro-82M ONNX for high-quality, CPU-friendly speech synthesis.
Generates individual audio clips per dialogue line and stitches them
into a single podcast MP3 using pydub.
"""

import os
import logging
import asyncio
import uuid
from pathlib import Path

import soundfile as sf
from pydub import AudioSegment

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Kokoro voice IDs — see https://huggingface.co/hexgrad/Kokoro-82M
VOICE_MAP = {
    "Host": "am_adam",     # American male — warm, clear
    "Guest": "af_bella",   # American female — friendly, expressive
}

SAMPLE_RATE = 24000  # Kokoro outputs 24kHz audio
PAUSE_BETWEEN_SPEAKERS_MS = 600  # 0.6s silence between speaker turns

# Directory for temporary audio files
AUDIO_CACHE_DIR = Path(os.environ.get("AUDIO_CACHE_DIR", "/tmp/podcast_audio"))

# Pre-downloaded model paths (set by Dockerfile)
MODEL_DIR = Path(os.environ.get("KOKORO_MODEL_DIR", "model_cache"))


# ---------------------------------------------------------------------------
# Kokoro Model Singleton
# ---------------------------------------------------------------------------

_kokoro_instance = None


def _get_kokoro():
    """Lazy-load the Kokoro ONNX model (singleton)."""
    global _kokoro_instance
    if _kokoro_instance is not None:
        return _kokoro_instance

    try:
        import kokoro_onnx
    except ImportError:
        raise ImportError(
            "kokoro-onnx is not installed. Run: pip install kokoro-onnx"
        )

    model_path = MODEL_DIR / "kokoro-v0_19.onnx"
    voices_path = MODEL_DIR / "voices.json"

    if model_path.exists() and voices_path.exists():
        logger.info("Loading Kokoro from pre-downloaded files: %s", model_path)
        _kokoro_instance = kokoro_onnx.Kokoro(str(model_path), str(voices_path))
    else:
        # Fallback: let kokoro-onnx download automatically
        logger.info("Kokoro model files not found in %s, downloading...", MODEL_DIR)
        _kokoro_instance = kokoro_onnx.Kokoro.from_pretrained()

    logger.info("Kokoro-82M ONNX model loaded successfully.")
    return _kokoro_instance


# ---------------------------------------------------------------------------
# Single-Line TTS
# ---------------------------------------------------------------------------

async def _synthesize_line(text: str, speaker: str, output_path: Path) -> Path:
    """
    Synthesize a single dialogue line to a WAV file.

    Args:
        text: The text content to speak.
        speaker: "Host" or "Guest" — mapped to a Kokoro voice ID.
        output_path: Where to save the .wav file.

    Returns:
        The output_path on success.
    """
    voice_id = VOICE_MAP.get(speaker, VOICE_MAP["Host"])
    kokoro = _get_kokoro()

    logger.info("Synthesizing [%s] (%s): %.60s...", speaker, voice_id, text)

    # kokoro.create() is synchronous; run in executor to avoid blocking
    loop = asyncio.get_event_loop()
    samples, sample_rate = await loop.run_in_executor(
        None, lambda: kokoro.create(text, voice=voice_id, speed=1.0)
    )

    # Save as WAV
    sf.write(str(output_path), samples, sample_rate)
    logger.info("Saved audio clip: %s (%.1fs)", output_path.name, len(samples) / sample_rate)
    return output_path


# ---------------------------------------------------------------------------
# Full Podcast Generation
# ---------------------------------------------------------------------------

async def generate_podcast_audio(
    dialogue: list[dict],
    session_id: str | None = None,
) -> tuple[str, list[dict]]:
    """
    Generate a complete podcast MP3 from a list of dialogue lines.

    Args:
        dialogue: List of dicts with "speaker" and "text" keys.
        session_id: Optional unique ID for this generation session.

    Returns:
        A tuple of (mp3_file_path, timing_metadata) where timing_metadata
        contains per-line start/end timestamps for transcript sync.
    """
    if not session_id:
        session_id = uuid.uuid4().hex[:12]

    # Create session directory
    session_dir = AUDIO_CACHE_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Synthesize each line individually
    clips = []
    for i, line in enumerate(dialogue):
        speaker = line.get("speaker", "Host")
        text = line.get("text", "")
        if not text.strip():
            continue
        clip_path = session_dir / f"line_{i:03d}_{speaker.lower()}.wav"
        await _synthesize_line(text, speaker, clip_path)
        clips.append({
            "path": clip_path,
            "index": i,
            "speaker": speaker,
            "text": text,
        })

    if not clips:
        raise ValueError("No audio clips were generated.")

    # Step 2: Stitch clips together with pauses
    logger.info("Stitching %d clips into final podcast...", len(clips))
    silence = AudioSegment.silent(duration=PAUSE_BETWEEN_SPEAKERS_MS)
    combined = AudioSegment.empty()
    timing = []
    current_ms = 0

    for clip in clips:
        clip_path = clip["path"]
        segment = AudioSegment.from_wav(str(clip_path))

        # Record timing metadata for this line
        start_ms = current_ms
        end_ms = current_ms + len(segment)
        timing.append({
            "index": clip["index"],
            "speaker": clip["speaker"],
            "text": clip["text"],
            "start_s": round(start_ms / 1000, 2),
            "end_s": round(end_ms / 1000, 2),
        })

        combined += segment + silence
        current_ms = end_ms + PAUSE_BETWEEN_SPEAKERS_MS

    # Step 3: Export as MP3
    output_path = session_dir / "podcast.mp3"
    combined.export(str(output_path), format="mp3", bitrate="128k")
    logger.info("Final podcast saved: %s (%.1fs)", output_path, len(combined) / 1000)

    # Clean up individual WAV clips to save disk
    for clip in clips:
        try:
            clip["path"].unlink()
        except OSError:
            pass

    return str(output_path), timing
