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

import requests
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
KOKORO_MODEL_FILENAME = "kokoro-v0_19.onnx"
KOKORO_VOICES_FILENAME = "voices.json"
KOKORO_MODEL_URL = (
    "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/"
    f"{KOKORO_MODEL_FILENAME}"
)
KOKORO_VOICES_URL = (
    "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/"
    f"{KOKORO_VOICES_FILENAME}"
)


# ---------------------------------------------------------------------------
# Kokoro Model Singleton
# ---------------------------------------------------------------------------

_kokoro_instance = None


def _patch_phonemizer_espeak_data_path():
    """Use the espeak data files bundled with espeakng-loader."""
    try:
        import espeakng_loader
        from phonemizer.backend.espeak import api as espeak_api
        from phonemizer.backend.espeak.api import EspeakAPI
        from phonemizer.backend.espeak.wrapper import EspeakWrapper
    except ImportError:
        return

    def set_data_path(cls, data_path):
        cls._ESPEAK_DATA_PATH = data_path

    if not hasattr(EspeakWrapper, "set_data_path"):
        EspeakWrapper.set_data_path = classmethod(set_data_path)

    if getattr(EspeakAPI, "_readnext_data_path_patch", False):
        return

    def init_with_data_path(self, library):
        self._library = None

        try:
            espeak = espeak_api.ctypes.cdll.LoadLibrary(str(library))
            library_path = self._shared_library_path(espeak)
            del espeak
        except OSError as error:
            raise RuntimeError(
                f"failed to load espeak library: {str(error)}"
            ) from None

        self._tempdir = espeak_api.tempfile.mkdtemp()
        if espeak_api.sys.platform == "win32":
            espeak_api.atexit.register(self._delete_win32)
        else:
            espeak_api.weakref.finalize(self, self._delete, self._library, self._tempdir)

        espeak_copy = espeak_api.pathlib.Path(self._tempdir) / library_path.name
        espeak_api.shutil.copy(library_path, espeak_copy, follow_symlinks=False)

        self._library = espeak_api.ctypes.cdll.LoadLibrary(str(espeak_copy))
        data_path = getattr(EspeakWrapper, "_ESPEAK_DATA_PATH", None) or espeakng_loader.get_data_path()
        data_path_bytes = str(data_path).encode("utf-8")

        try:
            if self._library.espeak_Initialize(0x02, 0, data_path_bytes, 0) <= 0:
                raise RuntimeError("failed to initialize espeak shared library")
        except AttributeError:
            raise RuntimeError("failed to load espeak library") from None

        self._library_path = library_path

    EspeakAPI.__init__ = init_with_data_path
    EspeakAPI._readnext_data_path_patch = True


def _download_file(url: str, destination: Path):
    """Download a required model asset atomically."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path = destination.with_suffix(destination.suffix + ".tmp")

    with requests.get(url, stream=True, timeout=(10, 120)) as response:
        response.raise_for_status()
        with temp_path.open("wb") as file:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    file.write(chunk)

    temp_path.replace(destination)


def _ensure_kokoro_model_files() -> tuple[Path, Path]:
    """Return Kokoro model files, downloading them if they are missing."""
    model_path = MODEL_DIR / KOKORO_MODEL_FILENAME
    voices_path = MODEL_DIR / KOKORO_VOICES_FILENAME

    if not model_path.exists():
        logger.info("Downloading Kokoro model to %s", model_path)
        _download_file(KOKORO_MODEL_URL, model_path)

    if not voices_path.exists():
        logger.info("Downloading Kokoro voices to %s", voices_path)
        _download_file(KOKORO_VOICES_URL, voices_path)

    return model_path, voices_path


def _get_kokoro():
    """Lazy-load the Kokoro ONNX model (singleton)."""
    global _kokoro_instance
    if _kokoro_instance is not None:
        return _kokoro_instance

    try:
        _patch_phonemizer_espeak_data_path()
        import kokoro_onnx
    except ImportError:
        raise ImportError(
            "kokoro-onnx is not installed. Run: pip install kokoro-onnx"
        )

    model_path, voices_path = _ensure_kokoro_model_files()
    logger.info("Loading Kokoro from files: %s", model_path)
    _kokoro_instance = kokoro_onnx.Kokoro(str(model_path), str(voices_path))

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
