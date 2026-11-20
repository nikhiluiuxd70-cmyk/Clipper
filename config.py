import os
from pathlib import Path

# Load .env if present (optional for local development)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_DIR = Path(__file__).resolve().parent
TEMP_DIR = BASE_DIR / "temp"
DOWNLOADS_DIR = BASE_DIR / "downloads"
OUTPUT_DIR = BASE_DIR / "output"

# Ensure directories exist
TEMP_DIR.mkdir(parents=True, exist_ok=True)
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Default Groq Models
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
try:
    import streamlit as st
    if hasattr(st, "secrets") and "GROQ_API_KEY" in st.secrets:
        GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
except Exception:
    pass

GROQ_LLM_MODEL = os.getenv("GROQ_LLM_MODEL", "llama-3.3-70b-versatile")
GROQ_WHISPER_MODEL = os.getenv("GROQ_WHISPER_MODEL", "whisper-large-v3")

# Video Framing presets
FRAMING_BLURRED_BG = "blurred_background"
FRAMING_CENTER_CROP = "center_crop"
FRAMING_ORIGINAL = "original"
