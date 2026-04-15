FROM python:3.11-slim

# Install system dependencies including ffmpeg and build tools for whisper
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    build-essential \
    gcc \
    g++ \
    espeak-ng \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Upgrade pip and install build tools first
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Install openai-whisper separately to isolate build errors
RUN pip install --no-cache-dir openai-whisper

# Install Kokoro TTS and its dependencies
RUN pip install --no-cache-dir kokoro soundfile misaki[en]

# Copy requirements and install the rest
COPY requirements.txt .
# Remove openai-whisper from requirements to avoid re-installing it
RUN sed -i '/openai-whisper/d' requirements.txt && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
