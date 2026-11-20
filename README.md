# 🎬 Free AI YouTube Video Clipper

Turn long YouTube videos, podcasts, and interviews into high-retention, viral short clips (YouTube Shorts, TikTok, Instagram Reels) — **100% Free & Open Source**.

Unlike paid subscription services (Opus Clip, Klap, Munch, Vidyo.ai), this tool runs locally and leverages the high-speed **Groq Cloud API** (Whisper Large v3 + Llama 3.3 70B) and **FFmpeg** to deliver automated viral clipping at **zero recurring cost**.

---

## ✨ Features

- **Paste & Clip**: Simply paste any YouTube video link.
- **Selectable Duration**: Choose target durations (e.g. 15s, 30s, 60s, or custom range).
- **AI Virality Scoring**: Powered by Groq's Llama 3.3 70B model to detect compelling hooks, high-retention moments, and standalone stories.
- **Smart 9:16 Vertical Reframing**:
  - **Blurred Background**: Widescreen video centered with a blurred, zoomed backdrop (no cropping out faces or content).
  - **Center Crop**: Traditional 9:16 vertical crop.
  - **Original 16:9**: Keeps full widescreen.
- **Auto-Generated Captions**: Generates bold, high-contrast subtitle overlays (.ass / .srt) with customizable styling and font size.
- **Direct Stream Slicing**: Uses `yt-dlp` download sections so you don't have to download multi-gigabyte 2-hour videos just to cut a 30-second clip.
- **Interactive Web Dashboard**: Streamlit-based UI with live video playback and one-click MP4 downloads.

---

## 🚀 Quickstart Guide

### 1. Prerequisites
- **Python 3.10+**
- **FFmpeg** installed and accessible in your system PATH.

### 2. Setup Virtual Environment & Dependencies
```bash
python -m venv .venv

# On Windows:
.\.venv\Scripts\activate
pip install -r requirements.txt

# On macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Get Your Free Groq API Key
1. Go to [console.groq.com/keys](https://console.groq.com/keys).
2. Sign in with Google / GitHub and create a free API key.
3. Either create a `.env` file from `.env.example`:
   ```bash
   GROQ_API_KEY=gsk_your_actual_key_here
   ```
   Or simply paste your key into the sidebar in the Web UI!

### 4. Launch the Web App
```bash
.\.venv\Scripts\streamlit run app.py
```
Open [http://localhost:8501](http://localhost:8501) in your browser!

---

## 🛠️ Project Structure
```
f:\Clipper\
├── app.py                 # Streamlit Web UI dashboard
├── config.py              # Configuration & directories
├── core/
│   ├── downloader.py      # yt-dlp section downloader & metadata extractor
│   ├── transcript.py      # youtube-transcript-api + Groq Whisper fallback
│   ├── analyzer.py        # Groq Llama 3.3 clip intelligence & virality scoring
│   ├── video_processor.py # FFmpeg 9:16 framing & cutting engine
│   └── subtitles.py       # Styled ASS subtitle generator
├── requirements.txt       # Python dependencies
├── .env.example           # Example environment file
└── README.md              # Project documentation
```

---

## 💡 How It Works Under The Hood
1. **Extraction**: Attempts to fetch official or auto-generated YouTube subtitles via `youtube-transcript-api` (instant & free). If unavailable, downloads audio and runs Groq's `whisper-large-v3` in under 20 seconds.
2. **Analysis**: Passes the timestamped transcript to `llama-3.3-70b-versatile` with prompt engineering designed for short-form retention (hook strength, narrative arc, punchline, duration boundary).
3. **Rendering**: Downloads only the selected video section using `yt-dlp`'s range streaming, converts to 9:16 vertical aspect ratio with FFmpeg, burns in high-visibility subtitles, and serves the MP4 for download.
