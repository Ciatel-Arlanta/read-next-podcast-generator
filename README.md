---
title: ReadNext Podcast Generator
emoji: 🎙️
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
---

# ReadNext Podcast Generator

ReadNext is an AI-powered podcast generator that converts articles, markdown text, or web URLs into engaging, natural-sounding two-person podcasts. 

It is designed to run entirely on open-source, local-friendly models:
* **Script Writer:** Gemma-2-2b-it (local GGUF or free HF Serverless API)
* **Dialogue Text-to-Speech:** Kokoro-82M ONNX model (highly optimized CPU inference)
* **Audio Stitching:** Pydub/FFmpeg

---

## How to Run Locally

### Prerequisites
* Python 3.10+
* `ffmpeg` installed on your machine and added to your system PATH.

### Installation
1. Clone this repository.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set your Hugging Face and/or Gemini keys (optional fallback):
   ```bash
   export HF_TOKEN="your_hugging_face_token"
   ```

### Execution
Start the FastAPI server:
```bash
uvicorn main:app --reload --port 7860
```
Then open `http://localhost:7860` in your browser.

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
