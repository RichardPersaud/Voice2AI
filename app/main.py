import os
import tempfile
import uuid
from pathlib import Path
from datetime import datetime
import sqlite3
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from starlette.requests import Request
import whisper
import requests
import json
from dotenv import load_dotenv
from ddgs import DDGS
import sys
# Add current directory to path for kokoro_tts import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kokoro_tts import generate_speech, get_voice_options

load_dotenv()

app = FastAPI(title="Voice Command App", version="1.0.0")

# CORS middleware for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files and templates
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# Load Whisper model (will download on first run if not cached)
print("Loading Whisper model...")
whisper_model = whisper.load_model("base")
print("Whisper model loaded successfully!")

# Configuration
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://192.168.50.209:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:latest")
MAX_UPLOAD_SIZE = int(os.getenv("MAX_UPLOAD_SIZE", "10485760"))
DB_PATH = "conversations.db"


async def search_web(query: str, max_results: int = 3) -> tuple:
    """Search DuckDuckGo and return formatted results for LLM context."""
    try:
        results = []
        with DDGS() as ddgs:
            search_results = ddgs.text(query, max_results=max_results)
            if search_results:
                for r in search_results:
                    results.append({
                        'title': r.get('title', ''),
                        'body': r.get('body', ''),
                        'href': r.get('href', '')
                    })

        if not results:
            return "", []

        formatted = "Here are relevant web search results:\n\n"
        for i, r in enumerate(results, 1):
            formatted += f"{i}. [{r['title']}]({r['href']})\n"
            formatted += f"   {r['body']}\n\n"

        return formatted, results
    except Exception as e:
        print(f"Web search error: {str(e)}")
        return "", []


async def search_images(query: str, max_results: int = 5) -> tuple:
    """Search DuckDuckGo for images and return formatted results."""
    try:
        results = []
        with DDGS() as ddgs:
            search_results = ddgs.images(query, max_results=max_results, safesearch="moderate")
            if search_results:
                for r in search_results:
                    results.append({
                        'title': r.get('title', ''),
                        'image': r.get('image', ''),
                        'thumbnail': r.get('thumbnail', ''),
                        'url': r.get('url', ''),
                        'source': r.get('source', '')
                    })

        if not results:
            return "", []

        # Format for LLM context - provide image URLs
        formatted = "Here are image search results:\n\n"
        for i, r in enumerate(results, 1):
            formatted += f"{i}. {r['title']}\n"
            formatted += f"   Image URL: {r['image']}\n"
            formatted += f"   Source: {r['url']}\n\n"

        return formatted, results
    except Exception as e:
        print(f"Image search error: {str(e)}")
        return "", []


def is_image_request(text: str) -> bool:
    """Detect if user is asking for an image."""
    text_lower = text.lower()
    image_patterns = [
        "show me an image of", "show me a picture of", "show me a photo of",
        "show me another image of", "show me another picture of", "show me another photo of",
        "show me images of", "show me pictures of", "show me photos of",
        "show an image of", "show a picture of", "show a photo of",
        "show another image of", "show another picture of", "show another photo of",
        "display an image of", "display a picture of", "display a photo of",
        "i want to see an image of", "i want to see a picture of",
        "find an image of", "find a picture of", "find me an image of",
        "give me an image of", "give me a picture of", "give me a photo of"
    ]
    return any(pattern in text_lower for pattern in image_patterns)


def extract_search_term(text: str) -> str:
    """Extract the search term from an image request."""
    import re
    text_lower = text.lower()
    # Remove common prefixes (including "another")
    patterns = [
        r"show me (an?|another) (image|picture|photo)s? of (a|an|the|another)? ?",
        r"show (me )?(an?|another)? ?(image|picture|photo)s? of (a|an|the|another)? ?",
        r"(display|find|get|give) (me )?(an?|another)? ?(image|picture|photo)s? of (a|an|the|another)? ?",
    ]
    for pattern in patterns:
        text_lower = re.sub(pattern, "", text_lower, count=1)

    # Clean up extra phrases after the subject
    cleanup_patterns = [
        r" that (looks|is|appears) .*$",
        r" (that|which|with) .*$",
        r" (exactly|similar|like) .*$",
    ]
    for pattern in cleanup_patterns:
        text_lower = re.sub(pattern, "", text_lower, count=1)

    return text_lower.strip()


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

import re

def strip_markdown(text: str) -> str:
    """Remove markdown syntax from text for cleaner display."""
    # Remove code blocks
    text = re.sub(r'`{3}[\w]*\n?', '', text)
    text = re.sub(r'`{3}', '', text)
    # Remove headers
    text = re.sub(r'#{1,6}\s', '', text)
    # Remove bold/italic markers
    text = re.sub(r'\*\*?|__?', '', text)
    # Remove inline code backticks but keep content
    text = re.sub(r'`([^`]+)`', r'\1', text)
    return text.strip()

def init_db():
    with get_db_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                title TEXT,
                created_at TIMESTAMP,
                model_used TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT,
                role TEXT,
                content TEXT,
                timestamp TIMESTAMP,
                web_search_used INTEGER DEFAULT 0,
                FOREIGN KEY (conversation_id) REFERENCES conversations (id)
            )
        """)
        # Migration: Add web_search_used column if it doesn't exist
        try:
            conn.execute("ALTER TABLE messages ADD COLUMN web_search_used INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # Column already exists
        # Migration: Add tts_audio_url column if it doesn't exist
        try:
            conn.execute("ALTER TABLE messages ADD COLUMN tts_audio_url TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists
        conn.commit()

init_db()


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Serve the main HTML page."""
    return templates.TemplateResponse("index.html", {"request": request, "version": "1.1"})


@app.get("/api/link-preview")
async def get_link_preview(url: str = ""):
    """Fetch Open Graph metadata for a URL to show link previews."""
    if not url:
        return {"error": "URL is required"}

    try:
        import httpx
        from bs4 import BeautifulSoup

        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            # Try Open Graph tags first
            title = None
            desc = None
            image = None

            og_title = soup.find('meta', property='og:title')
            if og_title:
                title = og_title.get('content')

            og_desc = soup.find('meta', property='og:description')
            if og_desc:
                desc = og_desc.get('content')

            og_image = soup.find('meta', property='og:image')
            if og_image:
                image = og_image.get('content')

            # Fallback to regular meta tags
            if not title:
                title_tag = soup.find('title')
                title = title_tag.text.strip()[:100] if title_tag else url[:50]

            if not desc:
                meta_desc = soup.find('meta', attrs={'name': 'description'})
                desc = meta_desc.get('content', '')[:200] if meta_desc else ''

            # Get favicon
            favicon = soup.find('link', rel='icon') or soup.find('link', rel='shortcut icon')
            icon = favicon.get('href') if favicon else None

            # Make image URL absolute
            if image and not image.startswith('http'):
                from urllib.parse import urljoin
                image = urljoin(url, image)

            return {
                "title": title or "",
                "description": desc or "",
                "image": image,
                "icon": icon,
                "url": url
            }

    except Exception as e:
        print(f"Link preview error: {str(e)}")
        return {"title": url[:50], "description": "", "image": None, "url": url}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "whisper": "loaded", "ollama_host": OLLAMA_HOST}


@app.get("/api/models")
async def get_models():
    """Fetch available models from Ollama."""
    try:
        response = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            return {"models": []}
    except Exception as e:
        print(f"Error fetching models: {str(e)}")
        return {"models": []}


@app.post("/api/models/test")
async def test_ollama_connection(host: str = Form(...)):
    """Test connection to a custom Ollama host and return available models."""
    try:
        # Validate URL
        if not host.startswith(('http://', 'https://')):
            raise HTTPException(status_code=400, detail="Invalid URL. Must start with http:// or https://")

        response = requests.get(f"{host}/api/tags", timeout=10)
        if response.status_code == 200:
            data = response.json()
            return {"success": True, "models": data.get("models", [])}
        else:
            return {"success": False, "error": f"HTTP {response.status_code}", "models": []}
    except requests.exceptions.ConnectionError:
        return {"success": False, "error": "Could not connect to Ollama server", "models": []}
    except requests.exceptions.Timeout:
        return {"success": False, "error": "Connection timed out", "models": []}
    except Exception as e:
        print(f"Error testing connection: {str(e)}")
        return {"success": False, "error": str(e), "models": []}


@app.get("/api/conversations")
async def get_conversations():
    """List all past conversations."""
    try:
        with get_db_connection() as conn:
            cursor = conn.execute("SELECT * FROM conversations ORDER BY created_at DESC")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        print(f"Error fetching conversations: {str(e)}")
        return {"error": "Could not retrieve conversations"}

@app.get("/api/conversations/{conversation_id}")
async def get_conversation_history(conversation_id: str):
    """Retrieve all messages for a specific conversation."""
    try:
        with get_db_connection() as conn:
            # Get model info from conversation
            conv_cursor = conn.execute(
                "SELECT model_used FROM conversations WHERE id = ?",
                (conversation_id,)
            )
            conv_row = conv_cursor.fetchone()
            model_used = conv_row['model_used'] if conv_row else 'AI'
            
            cursor = conn.execute(
                "SELECT role, content, timestamp, web_search_used, tts_audio_url FROM messages WHERE conversation_id = ? ORDER BY timestamp ASC",
                (conversation_id,)
            )
            rows = cursor.fetchall()
            messages = [dict(row) for row in rows]
            return {"messages": messages, "model_used": model_used}
    except Exception as e:
        print(f"Error fetching conversation {conversation_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.delete("/api/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete a conversation and its messages."""
    try:
        with get_db_connection() as conn:
            conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
            conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
            conn.commit()
            return {"success": True}
    except Exception as e:
        print(f"Error deleting conversation {conversation_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.delete("/api/messages")
async def delete_message_pair(conversation_id: str = Form(None), content: str = Form(None)):
    """
    Delete a user message and the subsequent AI response.
    Matches by conversation_id and the content of the user message.
    """
    if not conversation_id or not content:
        raise HTTPException(status_code=400, detail="conversation_id and content are required")

    try:
        with get_db_connection() as conn:
            # Find the most recent user message matching this content
            cursor = conn.execute(
                "SELECT id FROM messages WHERE conversation_id = ? AND role = 'user' AND content = ? ORDER BY id DESC LIMIT 1",
                (conversation_id, content)
            )
            user_msg = cursor.fetchone()

            if not user_msg:
                return {"success": False, "error": "User message not found"}

            user_id = user_msg['id']

            # Find the assistant message that follows this user message
            cursor = conn.execute(
                "SELECT id FROM messages WHERE conversation_id = ? AND id > ? AND role = 'assistant' ORDER BY id ASC LIMIT 1",
                (conversation_id, user_id)
            )
            ai_msg = cursor.fetchone()

            # Delete both
            conn.execute("DELETE FROM messages WHERE id = ?", (user_id,))
            if ai_msg:
                conn.execute("DELETE FROM messages WHERE id = ?", (ai_msg['id'],))

            conn.commit()
            return {"success": True}
    except Exception as e:
        print(f"Error deleting message pair: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/api/transcribe")
async def transcribe_audio(
    audio: UploadFile = File(None),
    text: str = Form(None),
    model: str = Form(None),
    conversation_id: str = Form(None),
    web_search: bool = Form(False)
):
    """
    Receive audio file or text prompt, transcribe if audio, and process with LLM.
    The 'model' parameter is optional; if not provided, uses the default from OLLAMA_MODEL env var.
    The 'conversation_id' parameter is optional; if not provided, a new conversation is started.
    The 'web_search' parameter enables web search to augment LLM responses.
    """
    # LOG REQUEST
    with open("/app/debug.log", "a") as f:
        f.write(f"[TRANSCRIBE REQUEST] {datetime.now().isoformat()} - text={text is not None}, audio={audio is not None}, model={model}, conv={conversation_id}\n")
    
    # Use provided model or fall back to environment variable default
    selected_model = model if model else OLLAMA_MODEL
    try:
        transcribed_text = ""

        # Case 1: Text prompt provided (e.g., for Rerun)
        if text:
            transcribed_text = text.strip()

        # Case 2: Audio file provided
        elif audio:
            # Validate file
            if audio.content_type not in ["audio/wav", "audio/webm", "audio/ogg", "audio/mpeg", "audio/mp4", "audio/webm;codecs=opus"]:
                return {
                    "success": False,
                    "error": f"Unsupported audio format: {audio.content_type}. Please use WAV, WebM, OGG, MP3, or MP4."
                }

            # Create temporary file with appropriate extension
            file_ext = audio.filename.split('.')[-1] if '.' in audio.filename else 'webm'
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=f'.{file_ext}')

            try:
                # Save uploaded file
                content = await audio.read()
                if len(content) > MAX_UPLOAD_SIZE:
                    return {
                        "success": False,
                        "error": f"File too large. Max size is {MAX_UPLOAD_SIZE / 1024 / 1024:.1f}MB"
                    }

                temp_file.write(content)
                temp_file.close()

                # Transcribe with Whisper
                print(f"Transcribing audio file: {temp_file.name}")
                result = whisper_model.transcribe(temp_file.name)
                transcribed_text = result["text"].strip()
                print(f"Transcription: {transcribed_text}")

            finally:
                # Clean up temp file
                if os.path.exists(temp_file.name):
                    os.unlink(temp_file.name)
        else:
            return {
                "success": False,
                "error": "No audio or text prompt provided."
            }

        if not transcribed_text:
            return {
                "success": False,
                "transcription": "",
                "llm_response": "I couldn't understand what you said. Please try again.",
                "error": "Empty transcription"
            }

        # Manage Conversation ID and Persistence
        if not conversation_id:
            conversation_id = str(uuid.uuid4())
            title = transcribed_text[:50] + "..." if len(transcribed_text) > 50 else transcribed_text
            with get_db_connection() as conn:
                conn.execute(
                    "INSERT INTO conversations (id, title, created_at, model_used) VALUES (?, ?, ?, ?)",
                    (conversation_id, title, datetime.now().isoformat(), selected_model)
                )
                conn.commit()

        # Save user message to DB
        with get_db_connection() as conn:
            conn.execute(
                "INSERT INTO messages (conversation_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
                (conversation_id, "user", transcribed_text, datetime.now().isoformat())
            )
            conn.commit()

        # Perform web search if enabled
        search_results = []
        search_context = ""
        image_results = []
        is_image_search = False

        if web_search and transcribed_text:
            # Check if user is asking for an image
            if is_image_request(transcribed_text):
                search_term = extract_search_term(transcribed_text)
                search_context, image_results = await search_images(search_term)
                is_image_search = True
            else:
                search_context, search_results = await search_web(transcribed_text)

        # Send to Ollama for processing (with conversation history and optional search context)
        llm_response = await process_with_llm(transcribed_text, selected_model, conversation_id, search_context, is_image_search)

        # Keep original markdown for frontend rendering
        clean_response = llm_response

        # Determine if web search was used
        used_web_search = web_search and (len(search_results) > 0 or len(image_results) > 0)

        # Save assistant message to DB (without TTS - generated on demand)
        with get_db_connection() as conn:
            conn.execute(
                "INSERT INTO messages (conversation_id, role, content, timestamp, web_search_used, tts_audio_url) VALUES (?, ?, ?, ?, ?, ?)",
                (conversation_id, "assistant", llm_response, datetime.now().isoformat(), 1 if used_web_search else 0, None)
            )
            conn.commit()

        return {
            "success": True,
            "transcription": transcribed_text,
            "llm_response": clean_response,
            "conversation_id": conversation_id,
            "model_used": selected_model,
            "web_search_used": web_search and (len(search_results) > 0 or len(image_results) > 0),
            "tts_audio_url": None
        }

    except Exception as e:
        print(f"Error processing audio: {str(e)}")
        return {
            "success": False,
            "error": f"Failed to process audio: {str(e)}"
        }


async def process_with_llm(text: str, model: str = OLLAMA_MODEL, conversation_id: str = None, search_context: str = "", is_image_search: bool = False) -> str:
    """Send transcribed text to Ollama LLM and return response, including conversation history if provided."""
    try:
        history_context = ""
        if conversation_id:
            with get_db_connection() as conn:
                # Fetch last 10 messages to maintain context
                cursor = conn.execute(
                    "SELECT role, content FROM messages WHERE conversation_id = ? ORDER BY timestamp ASC LIMIT 10",
                    (conversation_id,)
                )
                messages = cursor.fetchall()
                if messages:
                    history_context = "\n".join([f"{m['role'].capitalize()}: {m['content']}" for m in messages])

        prompt = "You are a helpful voice assistant.\n\n"
        if history_context:
            prompt += f"Here is the recent conversation history:\n{history_context}\n\n"
        else:
            prompt += "This is a new conversation.\n\n"

        # Add search results if available
        if search_context:
            if is_image_search:
                prompt += "=== IMAGE SEARCH RESULTS ===\n"
                prompt += search_context
                prompt += "=== END SEARCH RESULTS ===\n\n"
                prompt += "IMPORTANT: You MUST display an image from the results above using markdown syntax.\n"
                prompt += "Use this EXACT format: ![Description](image_url)\n\n"
                prompt += "Example: ![A beautiful duck swimming](https://example.com/duck.jpg)\n\n"
                prompt += "ALWAYS include the source link after the image using markdown link syntax:\n"
                prompt += "Format: Image source: [Website Name](source_url)\n\n"
                prompt += "Always include at least one image in your response with its source link.\n\n"
            else:
                prompt += "=== WEB SEARCH RESULTS ===\n"
                prompt += search_context
                prompt += "=== END SEARCH RESULTS ===\n\n"
                prompt += "Use the above web search results to answer the user's question. When citing sources, use markdown link format like [Source Title](URL). Always include the source link at the end of relevant information.\n\n"

        prompt += f"The user has just spoken the following:\n\"{text}\"\n\nPlease provide a helpful, concise response. If this is a command, acknowledge it and provide any relevant feedback or suggestions."

        response = requests.post(
            f"{OLLAMA_HOST}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False
            },
            timeout=120
        )

        if response.status_code == 200:
            result = response.json()
            return result.get("response", "Sorry, I couldn't process that.")
        else:
            return f"Ollama error: {response.status_code} - {response.text}"

    except requests.exceptions.ConnectionError:
        return f"Could not connect to Ollama at {OLLAMA_HOST}. Please ensure Ollama is running."
    except requests.exceptions.Timeout:
        return "The LLM took too long to respond. Please try again."
    except Exception as e:
        return f"Error processing with LLM: {str(e)}"

@app.post("/api/generate-tts")
async def generate_tts_endpoint(text: str = Form(...)):
    """Generate TTS audio for given text on demand."""
    try:
        # Clean text for TTS - remove markdown and URLs
        import re
        cleaned_text = text
        
        # Remove markdown bold/italic asterisks
        cleaned_text = re.sub(r'\*\*\*?(.+?)\*\*\*?', r'\1', cleaned_text)
        
        # Remove markdown links [text](url) -> just keep text
        cleaned_text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', cleaned_text)
        
        # Remove bare URLs (http/https links)
        cleaned_text = re.sub(r'https?://[^\s]+', '', cleaned_text)
        
        # Remove www. links
        cleaned_text = re.sub(r'www\.[^\s]+', '', cleaned_text)
        
        # Remove markdown code blocks
        cleaned_text = re.sub(r'```[\s\S]*?```', ' code snippet ', cleaned_text)
        cleaned_text = re.sub(r'`([^`]+)`', r'\1', cleaned_text)
        
        # Remove markdown headers (# ## ###)
        cleaned_text = re.sub(r'^#+\s*', '', cleaned_text, flags=re.MULTILINE)
        
        # Remove markdown list markers
        cleaned_text = re.sub(r'^[-*+]\s+', '', cleaned_text, flags=re.MULTILINE)
        
        # Clean up extra whitespace
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
        
        # Log to file
        with open("/app/debug.log", "a") as f:
            f.write(f"[TTS REQUEST] {datetime.now().isoformat()} - Text: {cleaned_text[:50]}...\n")
        
        print(f"Generating on-demand TTS for: {cleaned_text[:50]}...")
        audio_url = generate_speech(cleaned_text[:1000])  # Limit to 1000 chars
        
        # Log success
        with open("/app/debug.log", "a") as f:
            f.write(f"[TTS SUCCESS] {datetime.now().isoformat()} - URL: {audio_url}\n")
        
        print(f"TTS generated: {audio_url}")
        return {"success": True, "audio_url": audio_url}
    except Exception as e:
        error_msg = str(e)
        with open("/app/debug.log", "a") as f:
            f.write(f"[TTS ERROR] {datetime.now().isoformat()} - {error_msg}\n")
        print(f"TTS generation error: {error_msg}")
        return {"success": False, "error": error_msg}


@app.get("/api/debug-log")
async def get_debug_log():
    """Get the debug log contents."""
    try:
        with open("/app/debug.log", "r") as f:
            content = f.read()
        return {"success": True, "log": content}
    except FileNotFoundError:
        return {"success": True, "log": "No debug log yet"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/api/clear-debug-log")
async def clear_debug_log():
    """Clear the debug log."""
    try:
        with open("/app/debug.log", "w") as f:
            f.write("")
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)