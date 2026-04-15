#!/usr/bin/env python3
"""Kokoro TTS module for Voice2AI"""
import os
import uuid
import soundfile as sf
from kokoro import KPipeline

# Initialize Kokoro pipeline (American English)
print("Loading Kokoro TTS pipeline...")
pipeline = KPipeline(lang_code='a')
print("Kokoro TTS loaded!")

# Available voices (American English female voices are typically best for assistants)
DEFAULT_VOICE = 'af_heart'  # American female, warm tone
VOICES = {
    'af_heart': 'American Female - Warm',
    'af_bella': 'American Female - Bella',
    'af_sarah': 'American Female - Sarah',
    'am_adam': 'American Male - Adam',
    'am_michael': 'American Male - Michael',
}

def generate_speech(text: str, voice: str = DEFAULT_VOICE, speed: float = 1.0) -> str:
    """
    Generate speech from text using Kokoro TTS.
    
    Args:
        text: Text to convert to speech
        voice: Voice to use (see VOICES dict)
        speed: Speech speed (0.5 to 2.0)
    
    Returns:
        Path to the generated audio file
    """
    # Create output directory if needed (use relative path for Docker compatibility)
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'tts_cache')
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate unique filename
    filename = f"tts_{uuid.uuid4().hex}.wav"
    output_path = os.path.join(output_dir, filename)
    
    # Validate voice
    if voice not in VOICES:
        voice = DEFAULT_VOICE
    
    # Generate speech
    generator = pipeline(text, voice=voice, speed=speed)
    
    # Kokoro returns generator with (graphemes, phonemes, audio) tuples
    audio_segments = []
    for gs, ps, audio in generator:
        audio_segments.append(audio)
    
    # Concatenate all segments
    if audio_segments:
        import numpy as np
        full_audio = np.concatenate(audio_segments)
        sf.write(output_path, full_audio, 24000)
    else:
        raise Exception("No audio generated")
    
    # Return the relative URL path
    return f"/static/tts_cache/{filename}"

def get_voice_options():
    """Return available voice options"""
    return VOICES

if __name__ == "__main__":
    # Test
    test_text = "Hello! This is a test of Kokoro text to speech. It sounds natural and fast!"
    result = generate_speech(test_text)
    print(f"Generated: {result}")
