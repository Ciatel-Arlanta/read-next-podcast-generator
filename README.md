---
title: ReadNext Podcast Generator
emoji: 🎙️
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 7860
pinned: true
---

# ReadNext Podcast Generator

ReadNext is an AI-powered podcast generator that converts articles, markdown text, or web URLs into engaging, natural-sounding two-person podcasts. 

It is designed to run entirely on open-source, local-friendly models:
* **Script Writer:** Hugging Face Inference Providers chat model or local GGUF
* **Dialogue Text-to-Speech:** Kokoro-82M ONNX model (highly optimized CPU inference)
* **Audio Stitching:** Pydub/FFmpeg

---

## How to Run Locally

### Prerequisites
* Python 3.10+
* `ffmpeg` installed on your machine and added to your system PATH.

### Installation
1. Clone this repository.
2. Create and activate a virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
3. Install runtime dependencies:
   ```bash
   python3 -m pip install -r requirements.txt
   ```
4. Install test/development dependencies:
   ```bash
   python3 -m pip install -r requirements-dev.txt
   ```
5. Configure a generation backend. Use either Hugging Face Serverless Inference:
   ```bash
   export HF_TOKEN="your_hugging_face_token"
   export HF_MODEL_ID="openai/gpt-oss-120b:fastest"
   ```
   or a local GGUF model:
   ```bash
   export LOCAL_MODEL_PATH="/absolute/path/to/model.gguf"
   ```

### Environment Variables

| Variable | Required | Purpose |
| --- | --- | --- |
| `HF_TOKEN` | One backend required | Hugging Face token used for hosted script generation. |
| `HF_MODEL_ID` | No | Hosted Hugging Face model ID. Defaults to `openai/gpt-oss-120b:fastest`. |
| `LOCAL_MODEL_PATH` | One backend required | Path to a local GGUF model for `llama-cpp-python` generation. |
| `AUDIO_CACHE_DIR` | No | Directory for generated MP3 files. Defaults to `/tmp/podcast_audio`. |
| `KOKORO_MODEL_DIR` | No | Directory containing `kokoro-v0_19.onnx` and `voices.json`. Defaults to `model_cache`; missing files are downloaded at first TTS use. |

Copy `.env.example` for a local reference. The app reads environment variables from the process environment; it does not automatically load `.env` files.

### Tests

Run the fast regression suite:
```bash
python3 -m pytest
```

### Execution
Start the FastAPI server:
```bash
python3 -m uvicorn main:app --reload --port 7860
```
Then open `http://localhost:7860` in your browser.

### Troubleshooting

* If MP3 export fails, confirm `ffmpeg` is installed and available on `PATH`.
* If script generation fails with "No generation backend available", set either `HF_TOKEN` or `LOCAL_MODEL_PATH`.
* If Kokoro model download fails at runtime, set `KOKORO_MODEL_DIR` to a directory containing `kokoro-v0_19.onnx` and `voices.json`, or let Docker pre-download them into `model_cache`.
* Generated MP3 files are stored in `AUDIO_CACHE_DIR`, which defaults to `/tmp/podcast_audio`. Clear that directory if local test runs leave old generated files behind.

---

## Deploying to Hugging Face Spaces

This repository is pre-configured to run as a Docker Space on Hugging Face.

### Option 1: Direct Push
Add Hugging Face as a Git remote and push directly:
```bash
git remote add hf https://huggingface.co/spaces/YOUR_USERNAME/YOUR_SPACE_NAME
git push hf main
```

### Option 2: Automatic GitHub Actions Sync
To automatically push changes to Hugging Face whenever you push to GitHub:
1. Create a **Space** on Hugging Face with the **Docker SDK**.
2. Go to your GitHub Repository -> Settings -> Secrets and variables -> Actions.
3. Add a secret named `HF_TOKEN` containing your Hugging Face write token.
4. Add a secret named `HF_SPACE` containing your Hugging Face space path (e.g., `username/space-name`).
5. Pushing to GitHub will trigger the workflow in `.github/workflows/deploy.yml` which deploys the app to Hugging Face.
