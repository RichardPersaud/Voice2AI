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
                FOREIGN KEY (conversation_id) REFERENCES conversations (id)
            )
        """)
        conn.commit()

init_db()


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Serve the main HTML page."""
    return templates.TemplateResponse("index.html", {"request": request, "version": "1.1"})


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
                "SELECT role, content, timestamp FROM messages WHERE conversation_id = ? ORDER BY timestamp ASC",
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
async def transcribe_audio(audio: UploadFile = File(None), text: str = Form(None), model: str = Form(None), conversation_id: str = Form(None)):
    """
    Receive audio file or text prompt, transcribe if audio, and process with LLM.
    The 'model' parameter is optional; if not provided, uses the default from OLLAMA_MODEL env var.
    The 'conversation_id' parameter is optional; if not provided, a new conversation is started.
    """
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

        # Send to Ollama for processing (with conversation history)
        llm_response = await process_with_llm(transcribed_text, selected_model, conversation_id)
        
        # Keep original markdown for frontend rendering
        clean_response = llm_response

        # Save assistant message to DB
        with get_db_connection() as conn:
            conn.execute(
                "INSERT INTO messages (conversation_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
                (conversation_id, "assistant", llm_response, datetime.now().isoformat())
            )
            conn.commit()

        return {
            "success": True,
            "transcription": transcribed_text,
            "llm_response": clean_response,
            "conversation_id": conversation_id,
            "model_used": selected_model
        }

    except Exception as e:
        print(f"Error processing audio: {str(e)}")
        return {
            "success": False,
            "error": f"Failed to process audio: {str(e)}"
        }


async def process_with_llm(text: str, model: str = OLLAMA_MODEL, conversation_id: str = None) -> str:
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)