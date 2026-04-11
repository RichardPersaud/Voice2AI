# 🎤 Voice Command App

A modern web application that captures voice commands, transcribes them using OpenAI Whisper, and processes them through an LLM (Ollama). Designed for easy deployment on CasaOS.

<img width="1453" height="755" alt="image" src="https://github.com/user-attachments/assets/6f035de8-9545-434a-b532-fc75a20ca2d6" />


## ✨ Features

- **Voice Recording**: Simple, intuitive UI with real-time audio visualization
- **Speech-to-Text**: Powered by OpenAI Whisper (runs locally)
- **AI Processing**: Integrates with Ollama LLM for intelligent command interpretation
- **Modern UI**: Beautiful glassmorphism design with Tailwind CSS
- **CasaOS Ready**: One-click deployment with Docker Compose

## 🚀 Quick Start (CasaOS)

1. **Clone or copy the app directory** to your CasaOS host
2. **Update the Ollama IP** in `docker-compose.yml` to match your setup
3. **Deploy via CasaOS**:
   ```bash
   cd voice-command-app
   docker-compose up -d
   ```
4. **Access the app** at `http://your-server-ip:8000`

## 🏗️ Manual Deployment

### Prerequisites

- Docker & Docker Compose
- Ollama server running and accessible
- ~2GB free space (Whisper model downloads on first run)

### Installation Steps

1. **Clone/download** the application files

2. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env and set your Ollama host
   ```

3. **Build and run**:
   ```bash
   docker-compose up -d
   ```

4. **Verify health check**:
   ```bash
   curl http://localhost:8000/health
   ```

## ⚙️ Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_HOST` | `http://192.168.50.209:11434` | Ollama API endpoint |
| `OLLAMA_MODEL` | `llama3.2:latest` | Model to use for processing |
| `MAX_UPLOAD_SIZE` | `10485760` (10MB) | Max audio file size in bytes |

### Changing Ollama Model

Edit `docker-compose.yml` or set via environment:
```yaml
environment:
  - OLLAMA_MODEL=llama3.1:latest  # Or any installed model
```

## 📝 Usage

1. **Open the app** in your browser
2. **Click the microphone button** to start recording
3. **Speak your command or question**
4. **Click again** to stop recording
5. **View the results** - transcription and AI response

## 🏛️ Architecture

```
┌─────────────┐     ┌─────────────────┐     ┌──────────┐
│   Browser   │────→│  Voice Command  │────→│  Ollama  │
│  (Web UI)   │←────│     Server      │←────│   LLM    │
└─────────────┘     └─────────────────┘     └──────────┘
                            │
                            ↓
                     ┌──────────┐
                     │  Whisper │
                     │   (STT)  │
                     └──────────┘
```

### Tech Stack

- **Backend**: FastAPI (Python 3.10)
- **STT**: OpenAI Whisper (local)
- **LLM**: Ollama API
- **Frontend**: Vanilla JS + Tailwind CSS
- **Container**: Docker

## 🔧 Troubleshooting

### "Could not connect to Ollama"
- Verify Ollama is running: `curl http://your-ollama-ip:11434/api/tags`
- Check the `OLLAMA_HOST` matches your Ollama server IP
- Ensure both containers are on the same network

### "Microphone not working"
- Use HTTPS or localhost for microphone access (browser requirement)
- Check browser permissions for microphone
- Try a different browser

### "Whisper model download slow"
- First run downloads the model (~150MB for base model)
- Mounted volume persists the cache between restarts

### Supported Audio Formats
- WebM (Chrome/Firefox)
- MP4 (Safari)
- WAV, OGG, MP3

## 📁 Project Structure

```
voice-command-app/
├── app/
│   ├── main.py           # FastAPI application
│   ├── __init__.py
│   ├── static/           # Static assets
│   └── templates/        # HTML templates
│       └── index.html    # Main UI
├── uploads/              # Temporary audio storage
├── requirements.txt      # Python dependencies
├── Dockerfile            # Container definition
├── docker-compose.yml    # CasaOS deployment
├── .env.example         # Environment template
└── README.md             # This file
```

## 🐳 Docker Commands

```bash
# Start
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down

# Rebuild after changes
docker-compose up -d --build

# Access container shell
docker exec -it voice-command-app bash
```

## 🔒 Security Notes

- The app accepts audio uploads - ensure it's behind a firewall/VPN
- CORS is set to allow all origins for flexibility
- No authentication included - add your own reverse proxy with auth if needed
- Audio files are stored temporarily and deleted after processing

## 🔄 CasaOS Import (Custom App)

If CasaOS doesn't detect docker-compose.yml:

1. In CasaOS, go to **Apps** → **+** → **Custom Install**
2. Set:
   - Container Image: Build from local Dockerfile
   - Port: 8000 → 8000
   - Volumes: whisper-cache
3. Environment variables as needed
4. Save and deploy

## 📜 License

MIT - Feel free to modify and redistribute!

## 🤝 Credits

- OpenAI Whisper: https://github.com/openai/whisper
- FastAPI: https://fastapi.tiangolo.com/
- Ollama: https://ollama.ai/
