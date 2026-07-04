# Agent Notes

ReadNext is a FastAPI app with a static frontend. `main.py` accepts article URLs or pasted text, `generator.py` turns article text into a two-speaker script, and `tts_engine.py` synthesizes and stitches audio with Kokoro and pydub.

## Verify

Use the fast regression suite for ordinary changes:

```bash
python3 -m pytest
```

Install dev dependencies first with:

```bash
python3 -m pip install -r requirements-dev.txt
```

## Boundaries

- Do not call real Hugging Face, Kokoro, or article URLs in tests. Mock network, model, and TTS calls.
- Preserve the public route contract used by `frontend/script.js`: `POST /api/generate-podcast`, `GET /api/audio/{session_id}/podcast.mp3`, and `GET /api/health`.
- Keep generated audio under `AUDIO_CACHE_DIR`; do not broaden audio serving without an explicit filename allowlist.
- Keep static frontend files dependency-free unless a larger frontend build system is intentionally introduced.

## Deployment

The Dockerfile targets Hugging Face Spaces on port `7860` and pre-downloads Kokoro model files into `model_cache`. The GitHub Actions workflow syncs `main` or `master` to the Space using `HF_TOKEN` and `HF_SPACE` secrets.
