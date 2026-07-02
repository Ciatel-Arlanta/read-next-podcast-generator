FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    build-essential \
    curl \
    wget \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set up user for Hugging Face Spaces compatibility
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1

WORKDIR $HOME/app

# Copy requirements and install
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Pre-download the Kokoro-82M ONNX model and voices file to avoid runtime download delay
RUN mkdir -p model_cache && \
    wget -q https://huggingface.co/hexgrad/Kokoro-82M/resolve/main/kokoro-v0_19.onnx -O model_cache/kokoro-v0_19.onnx && \
    wget -q https://huggingface.co/hexgrad/Kokoro-82M/resolve/main/voices.bin -O model_cache/voices.bin

# Copy project files
COPY --chown=user . .

# Expose Hugging Face Space default port
EXPOSE 7860

# Run the FastAPI server
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
