import os
import re
from pathlib import Path

# Load model globally so it stays in RAM and runs fast on subsequent requests.
# The 'base.en' model is very lightweight and optimized for CPU (int8).
from faster_whisper import WhisperModel
print("Loading Whisper model (base.en) into CPU memory...")
model = WhisperModel("base.en", device="cpu", compute_type="int8")


def transcribe_audio(audio_path: str) -> str:
    """Transcribes an audio file into text using faster-whisper."""
    segments, info = model.transcribe(audio_path, beam_size=5)
    text = ""
    for segment in segments:
        text += segment.text + " "
    return text.strip()


def clean_for_tts(text: str) -> str:
    """Removes markdown and emojis so the TTS doesn't read them aloud."""
    text = re.sub(r'[*_#`~]', '', text)
    text = text.encode('ascii', 'ignore').decode('ascii')
    return text


def generate_tts(text: str, output_path: str):
    """Converts text into speech and saves it to a file."""
    text = clean_for_tts(text)
    # Ensure the static directory exists
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    
    # Initialize pyttsx3 inside the function to prevent threading issues
    # in the Flask development server on Windows.
    import pyttsx3
    engine = pyttsx3.init()
    
    # Optional: adjust the speaking rate (default is usually ~200)
    engine.setProperty('rate', 165)
    
    engine.save_to_file(text, output_path)
    engine.runAndWait()
