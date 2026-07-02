"""
main.py — FastAPI Orchestrator for ReadNext Podcast Generator

Serves the frontend, handles article scraping, coordinates the
script writer (generator.py) and TTS engine (tts_engine.py),
and streams the final podcast audio back to the client.
"""

import os
import re
import uuid
import logging
import asyncio
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from generator import generate_script
from tts_engine import generate_podcast_audio, AUDIO_CACHE_DIR

# ---------------------------------------------------------------------------
# Logging Setup
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="ReadNext Podcast Generator",
    description="Convert any article into an AI-generated two-person podcast.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------

class PodcastRequest(BaseModel):
    source: str                    # URL or raw text
    input_type: str = "auto"       # "url", "text", or "auto"


class PodcastResponse(BaseModel):
    title: str
    dialogue: list[dict]
    timing: list[dict]
    audio_url: str


# ---------------------------------------------------------------------------
# URL Scraping
# ---------------------------------------------------------------------------

def _scrape_url(url: str) -> str:
    """Extract the main text content from a URL."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch URL: {e}")

    soup = BeautifulSoup(resp.text, "html.parser")

    # Remove noise elements
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form", "iframe"]):
        tag.decompose()

    # Try to find the main article content
    article = soup.find("article") or soup.find("main") or soup.find("body")
    if not article:
        raise HTTPException(status_code=400, detail="Could not extract text from URL.")

    # Extract paragraphs
    paragraphs = article.find_all("p")
    text = "\n\n".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))

    if len(text) < 100:
        # Fallback: grab all visible text
        text = article.get_text(separator="\n", strip=True)

    if len(text) < 50:
        raise HTTPException(status_code=400, detail="Extracted text is too short to generate a podcast.")

    logger.info("Scraped %d characters from %s", len(text), url)
    return text


def _detect_input_type(source: str) -> str:
    """Detect whether the source is a URL or raw text."""
    url_pattern = re.compile(
        r"^https?://"
        r"(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+"
        r"[a-zA-Z]{2,}"
    )
    if url_pattern.match(source.strip()):
        return "url"
    return "text"


# ---------------------------------------------------------------------------
# Main Endpoint
# ---------------------------------------------------------------------------

@app.post("/api/generate-podcast", response_model=PodcastResponse)
async def generate_podcast(req: PodcastRequest):
    """
    Generate a podcast from an article URL or raw text.

    Steps:
    1. Parse input (scrape URL if needed).
    2. Generate podcast script via Gemma-2-2b-it.
    3. Synthesize speech via Kokoro-82M ONNX.
    4. Return audio URL + script + timing metadata.
    """
    session_id = uuid.uuid4().hex[:12]
    logger.info("=== New podcast request [%s] ===", session_id)

    # Step 1: Get the article text
    input_type = req.input_type
    if input_type == "auto":
        input_type = _detect_input_type(req.source)

    if input_type == "url":
        logger.info("Scraping URL: %s", req.source)
        article_text = _scrape_url(req.source.strip())
    else:
        article_text = req.source.strip()
        if len(article_text) < 50:
            raise HTTPException(status_code=400, detail="Text is too short. Please provide more content.")

    # Step 2: Generate the podcast script
    logger.info("Generating podcast script...")
    try:
        script = generate_script(article_text)
    except Exception as e:
        logger.error("Script generation failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Script generation failed: {e}")

    logger.info("Script ready: '%s' with %d lines", script.title, len(script.dialogue))

    # Step 3: Generate audio
    logger.info("Generating audio with Kokoro TTS...")
    try:
        dialogue_dicts = [{"speaker": line.speaker, "text": line.text} for line in script.dialogue]
        audio_path, timing = await generate_podcast_audio(dialogue_dicts, session_id=session_id)
    except Exception as e:
        logger.error("Audio generation failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Audio generation failed: {e}")

    logger.info("Podcast generation complete! Audio at: %s", audio_path)

    return PodcastResponse(
        title=script.title,
        dialogue=dialogue_dicts,
        timing=timing,
        audio_url=f"/api/audio/{session_id}/podcast.mp3",
    )


# ---------------------------------------------------------------------------
# Audio Serving
# ---------------------------------------------------------------------------

@app.get("/api/audio/{session_id}/{filename}")
async def serve_audio(session_id: str, filename: str):
    """Serve a generated audio file."""
    file_path = AUDIO_CACHE_DIR / session_id / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found.")
    return FileResponse(
        str(file_path),
        media_type="audio/mpeg",
        filename=filename,
    )


# ---------------------------------------------------------------------------
# Health Check
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "ReadNext Podcast Generator"}


# ---------------------------------------------------------------------------
# Static Frontend (must be mounted LAST so API routes take priority)
# ---------------------------------------------------------------------------

frontend_dir = Path(__file__).parent / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
