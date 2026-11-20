import os
import re
import json
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional
import yt_dlp
try:
    import imageio_ffmpeg
except ImportError:
    imageio_ffmpeg = None
from config import DOWNLOADS_DIR, TEMP_DIR

def get_ffmpeg_bin() -> str:
    """Return path to modern FFmpeg executable."""
    if imageio_ffmpeg is not None:
        try:
            return imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            pass
    return "ffmpeg"

def extract_video_id(url: str) -> Optional[str]:
    """Extract 11-character YouTube video ID from various URL formats."""
    patterns = [
        r'(?:v=|\/live\/|\/shorts\/|\/embed\/|youtu\.be\/|\/v\/)([0-9A-Za-z_-]{11})',
        r'(?:v=)([0-9A-Za-z_-]{11})',
        r'([0-9A-Za-z_-]{11})'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def normalize_youtube_url(url: str) -> str:
    """Normalize any YouTube link format (live, shorts, mobile, missing https) to standard watch URL."""
    url = url.strip()
    vid = extract_video_id(url)
    if vid:
        return f"https://www.youtube.com/watch?v={vid}"
    if not url.startswith("http://") and not url.startswith("https://"):
        return f"https://{url}"
    return url

def get_video_info(url: str, proxy: Optional[str] = None) -> Dict[str, Any]:
    """Fetch video metadata without downloading the full video."""
    canonical_url = normalize_youtube_url(url)
    ffmpeg_exe = get_ffmpeg_bin()
    ydl_opts = {
        'skip_download': True,
        'quiet': True,
        'no_warnings': True,
        'socket_timeout': 20,
        'source_address': '0.0.0.0',
        'ffmpeg_location': ffmpeg_exe,
        'js_runtimes': {'node': {}},
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'ios', 'web', 'mweb'],
            }
        },
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        },
        'geo_bypass': True,
    }
    if proxy:
        ydl_opts['proxy'] = proxy

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(canonical_url, download=False)
        return {
            'id': info.get('id', ''),
            'title': info.get('title', 'Unknown Title'),
            'duration': info.get('duration', 0),
            'thumbnail': info.get('thumbnail', ''),
            'channel': info.get('uploader', 'Unknown Creator'),
            'description': info.get('description', '')[:500],
            'url': canonical_url
        }

def download_audio_only(url: str, output_path: Optional[Path] = None, proxy: Optional[str] = None) -> Path:
    """Download audio only (converted to mp3 or m4a) for Whisper transcription."""
    canonical_url = normalize_youtube_url(url)
    ffmpeg_exe = get_ffmpeg_bin()
    if output_path is None:
        video_id = extract_video_id(canonical_url) or "temp_audio"
        output_path = TEMP_DIR / f"{video_id}.mp3"

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': str(output_path.with_suffix('')),
        'ffmpeg_location': ffmpeg_exe,
        'source_address': '0.0.0.0',
        'js_runtimes': {'node': {}},
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'ios', 'web', 'mweb'],
            }
        },
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        },
        'geo_bypass': True,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '128',
        }],
        'quiet': True,
        'no_warnings': True,
        'overwrites': True,
        'socket_timeout': 20,
    }
    if proxy:
        ydl_opts['proxy'] = proxy

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([canonical_url])

    final_path = output_path.with_suffix('.mp3')
    return final_path

def download_video_section(url: str, start_time: float, end_time: float, output_path: Path, proxy: Optional[str] = None) -> Path:
    """
    Download only a specific section of the video using yt-dlp.
    Super fast since it doesn't need to download the full video.
    """
    canonical_url = normalize_youtube_url(url)
    ffmpeg_exe = get_ffmpeg_bin()
    start_sec = max(0, start_time)
    end_sec = max(start_sec + 1, end_time)

    ydl_opts = {
        'format': 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best',
        'outtmpl': str(output_path),
        'ffmpeg_location': ffmpeg_exe,
        'source_address': '0.0.0.0',
        'js_runtimes': {'node': {}},
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'ios', 'web', 'mweb'],
            }
        },
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        },
        'geo_bypass': True,
        'download_ranges': yt_dlp.utils.download_range_func(None, [(start_sec, end_sec)]),
        'force_keyframes_at_cuts': True,
        'overwrites': True,
        'quiet': True,
        'no_warnings': True,
        'socket_timeout': 20,
    }
    if proxy:
        ydl_opts['proxy'] = proxy

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([canonical_url])

    return output_path

def extract_audio_from_file(video_path: Path, output_audio: Optional[Path] = None) -> Path:
    """Extract audio from local video file for Groq Whisper transcription."""
    ffmpeg_exe = get_ffmpeg_bin()
    if output_audio is None:
        output_audio = TEMP_DIR / f"{video_path.stem}_audio.mp3"
    cmd = [
        ffmpeg_exe, "-y", "-i", str(video_path),
        "-vn", "-acodec", "libmp3lame", "-ar", "16000", "-ac", "1",
        "-b:a", "128k", str(output_audio)
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    return output_audio
