#!/bin/bash
cd /home/retroai/voice-command-app
source venv_kokoro/bin/activate
pkill -f "uvicorn.*voice-command-app" 2>/dev/null
sleep 2
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8080 --app-dir /home/retroai/voice-command-app > app.log 2>&1 &
echo "Voice2AI restarted with Kokoro TTS!"
