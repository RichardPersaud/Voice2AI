# 🎤 Voice Command App

A modern web application that captures voice commands, transcribes them using OpenAI Whisper, and processes them through an LLM (Ollama). Features web search augmentation, image search, link previews, conversation history, configurable settings, and a beautiful dark-themed UI. Designed for easy deployment on CasaOS.

<img width="1453" height="755" alt="image" src="https://github.com/user-attachments/assets/8cff2b1f-01aa-413c-98eb-b2eabf4d1c34" />

## ✨ Features

### Voice & Audio
- **Voice Recording**: Simple, intuitive UI with real-time audio visualization
- **Recording Timer**: Configurable max recording duration (1-5 minutes) with visual countdown
- **Speech-to-Text**: Powered by OpenAI Whisper (runs locally)
- **Multiple Audio Formats**: WebM, MP4, WAV, OGG, MP3 support

### Web Search & Images (v2.2)
- **Web Search**: Toggle web search to augment LLM responses with real-time DuckDuckGo results
  <img width="50%" alt="image" src="https://github.com/user-attachments/assets/0e523c9d-f1fe-4d01-b56b-c1f9c748745b" />

- **Image Search**: Ask for images naturally ("show me a picture of...") and get visual results inline
  <img width="50%" alt="image" src="https://github.com/user-attachments/assets/1490c14b-e503-4e4d-bd5b-b7747a2ac462" />

- **Link Previews**: Hover over any link in AI responses to see Open Graph previews with thumbnails
  <img width="50%" alt="image" src="https://github.com/user-attachments/assets/015006d3-341c-4df6-adca-e4aff6443d46" />

- **Source Citations**: AI cites sources with markdown links when using web search results

### AI & LLM Integration
- **AI Processing**: Integrates with Ollama LLM for intelligent command interpretation
- **Model Selection**: Choose from available Ollama models via Settings
- **Connection Testing**: Test Ollama connection and fetch models from custom hosts
- **Conversation Context**: Maintains conversation history for contextual responses

### Conversation Management
- **Persistent History**: SQLite database stores all conversations and messages
- **Browse Conversations**: View list of past conversations with timestamps
- **Resume Conversations**: Continue previous conversations seamlessly
- **Delete Conversations**: Remove entire conversations or individual message pairs
- **Text Input Fallback**: Rerun voice commands with text input for corrections

### UI/UX
- **Modern Glassmorphism Design**: Beautiful dark theme with Tailwind CSS
- **Typing Animation**: AI responses type out character by character with markdown rendering
- **Markdown Support**: AI responses render markdown formatting (code blocks, headers, etc.)
- **Mobile Responsive**: Fully functional on mobile devices
- **PWA Ready**: Service worker and manifest for installable web app

### Configuration
- **Settings Modal**: Configure Ollama host, default model, and recording timer
- **Model Persistence**: Default model selection saved to localStorage
- **Web Search Toggle**: Enable/disable web search per query
- **Live Reload**: Docker volume mount for development changes

## 🚀 Quick Start (CasaOS)

1. **Clone or copy the app directory** to your CasaOS host
2. **Update the Ollama IP** in `docker-compose.yml` to match your setup
3. **Deploy via CasaOS**:
   ```bash
   cd voice-command-app
   docker-compose up -d
   ```
4. **Access the app** at `http://your-server-ip:8080`

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
   curl http://localhost:8080/health
   ```

## ⚙️ Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_HOST` | `http://192.168.50.209:11434` | Ollama API endpoint |
| `OLLAMA_MODEL` | `llama3.2:latest` | Default model for processing |
| `MAX_UPLOAD_SIZE` | `10485760` (10MB) | Max audio file size in bytes |

> **Note**: Web search uses DuckDuckGo directly — no API key required.

### Application Settings

Access settings via the **gear icon** in the profile menu:

- **Ollama Configuration**: Set custom Ollama host and test connection
- **Default Model**: Select from available models on your Ollama server
- **Recording Timer**: Set maximum recording duration (1-5 minutes)

### Changing Ollama Model

Via Settings modal (recommended):
1. Click profile menu (top-right) → Settings
2. Under "Model Selection", choose from available models
3. Click Save

Or via `docker-compose.yml`:
```yaml
environment:
  - OLLAMA_MODEL=llama3.1:latest  # Or any installed model
```

## 📝 Usage

1. **Open the app** in your browser
2. **Configure Settings** (first time):
   - Set your Ollama host if different from default
   - Select your preferred model
   - Adjust recording timer if needed
3. **Click the microphone button** to start recording
4. **Speak your command or question**
5. **Click again** or wait for timer to stop recording
6. **View the results** - transcription and AI response
7. **Access history** via the sidebar to resume past conversations

### Using Web Search

- **Toggle web search** before submitting a query to get real-time results
- The AI will cite sources with clickable links when using search results
- Hover over any link in the response to see a preview card with thumbnail and description

### Using Image Search

Ask for images using natural language:
- "Show me a picture of a sunset"
- "Find me an image of a mountain landscape"
- "Display a photo of a cat"
- "Show me another picture of the ocean"

The AI detects image requests automatically and returns results with inline images and source links.

### Managing Conversations

- **View History**: Click the conversation sidebar (left) to see past chats
- **Resume**: Click any conversation to continue where you left off
- **Delete**: Hover over a conversation and click the trash icon
- **Delete Message**: Hover over any message pair and click the trash icon to remove it

## 🏛️ Architecture

```
┌─────────────┐     ┌─────────────────┐     ┌──────────┐
│   Browser   │────→│  Voice Command  │────→│  Ollama  │
│  (Web UI)   │←────│     Server      │←────│   LLM    │
└─────────────┘     └─────────────────┘     └──────────┘
                            │
                     ┌──────┼──────┐
                     ↓      ↓      ↓
               ┌─────────┐ ┌──────────┐ ┌──────────┐
               │ Whisper  │ │ DuckDuck │ │  SQLite   │
               │  (STT)   │ │  Go API  │ │   (DB)    │
               └─────────┘ └──────────┘ └──────────┘
```

### Tech Stack

- **Backend**: FastAPI (Python 3.10)
- **STT**: OpenAI Whisper (local)
- **LLM**: Ollama API
- **Web Search**: DuckDuckGo Search (ddgs)
- **Link Previews**: httpx + BeautifulSoup4 (Open Graph parsing)
- **Database**: SQLite (persistent conversations)
- **Frontend**: Vanilla JS + Tailwind CSS
- **Container**: Docker

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Serve the main UI |
| `/api/transcribe` | POST | Transcribe audio and process with LLM |
| `/api/conversations` | GET | List all conversations |
| `/api/conversations/{id}` | GET | Get conversation messages |
| `/api/conversations/{id}` | DELETE | Delete a conversation |
| `/api/messages` | DELETE | Delete a message pair |
| `/api/models` | GET | List available Ollama models |
| `/api/link-preview` | GET | Fetch Open Graph metadata for a URL |
| `/api/test-ollama` | POST | Test Ollama connection |
| `/health` | GET | Health check |

## 🔧 Troubleshooting

### "Could not connect to Ollama"
- Verify Ollama is running: `curl http://your-ollama-ip:11434/api/tags`
- Check the `OLLAMA_HOST` matches your Ollama server IP
- Use the Settings modal to test the connection
- Ensure both containers are on the same network

### "Microphone not working"
- Use HTTPS or localhost for microphone access (browser requirement)
- Check browser permissions for microphone
- Try a different browser

### "Whisper model download slow"
- First run downloads the model (~150MB for base model)
- Mounted volume persists the cache between restarts

### "Recording stops automatically"
- Check the Recording Timer setting (default: 1 minute)
- Adjust to 2-5 minutes in Settings if needed

### Supported Audio Formats
- WebM (Chrome/Firefox)
- MP4 (Safari)
- WAV, OGG, MP3

### "Web search not working"
- Ensure `ddgs>=8.0.0` is installed in the container
- Rebuild the container: `docker-compose up -d --build`
- DuckDuckGo search works without an API key
- Check container logs for search errors: `docker-compose logs -f`

## 📁 Project Structure

```
voice-command-app/
├── app/
│   ├── main.py           # FastAPI application
│   ├── __init__.py
│   ├── static/           # Static assets (CSS, JS, manifest)
│   │   ├── manifest.json # PWA manifest
│   │   └── sw.js         # Service worker
│   └── templates/        # HTML templates
│       └── index.html    # Main UI
├── uploads/              # Temporary audio storage
├── conversations.db      # SQLite database (created on first run)
├── requirements.txt      # Python dependencies
├── Dockerfile            # Container definition
├── docker-compose.yml    # CasaOS deployment
├── .env.example         # Environment template
└── README.md             # This file
```

## 🆕 Changelog

### v2.2 - Web Search Update
- DuckDuckGo web search integration with toggle
- Image search with natural language detection ("show me a picture of...")
- Link preview tooltips on hover (Open Graph metadata)
- New `/api/link-preview` endpoint
- `web_search_used` column in messages database
- Added dependencies: ddgs, httpx, beautifulsoup4

### v2.1
- Recording timer with configurable max duration
- Wake/stop word features (moved to BETA)
- UI improvements

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

# Restart container (for code changes with volume mount)
docker restart voice-command-app

# Access container shell
docker exec -it voice-command-app bash
```

## 🔒 Security Notes

- The app accepts audio uploads - ensure it's behind a firewall/VPN
- CORS is set to allow all origins for flexibility
- No authentication included - add your own reverse proxy with auth if needed
- Audio files are stored temporarily and deleted after processing
- Database is stored in a file (`conversations.db`) - back up if needed

## 🔄 CasaOS Import (Custom App)

If CasaOS doesn't detect docker-compose.yml:

1. In CasaOS, go to **Apps** → **+** → **Custom Install**
2. Set:
   - Container Image: Build from local Dockerfile
   - Port: 8000 → 8080 (or your preferred external port)
   - Volumes: whisper-cache, app code, uploads, database
3. Environment variables as needed
4. Save and deploy

## 📜 License

MIT - Feel free to modify and redistribute!

## 🤝 Credits

- OpenAI Whisper: https://github.com/openai/whisper
- FastAPI: https://fastapi.tiangolo.com/
- Ollama: https://ollama.ai/
- DuckDuckGo Search: https://pypi.org/project/ddgs/
- BeautifulSoup4: https://www.crummy.com/software/BeautifulSoup/
