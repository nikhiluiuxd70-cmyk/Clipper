import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from youtube_transcript_api import YouTubeTranscriptApi
from groq import Groq
from core.downloader import extract_video_id, download_audio_only
from config import GROQ_API_KEY, GROQ_WHISPER_MODEL

def format_timestamp(seconds: float) -> str:
    """Format seconds into HH:MM:SS or MM:SS."""
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hrs > 0:
        return f"{hrs:02d}:{mins:02d}:{secs:02d}"
    return f"{mins:02d}:{secs:02d}"

def get_transcript_from_youtube(video_id: str, proxy: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
    """
    Attempt to fetch official or auto-generated transcript from YouTube.
    Supports both youtube-transcript-api v1.2+ and legacy versions.
    Returns list of dicts: [{'text': str, 'start': float, 'duration': float}, ...]
    """
    # Method 1: New youtube-transcript-api v1.2+ instance fetch
    try:
        api = YouTubeTranscriptApi()
        data = api.fetch(video_id)
        result = []
        for item in data:
            text = getattr(item, 'text', None) if not isinstance(item, dict) else item.get('text', '')
            if text is None:
                text = item.get('text', '') if isinstance(item, dict) else str(item)
            start = float(getattr(item, 'start', 0.0) if not isinstance(item, dict) else item.get('start', 0.0))
            duration = float(getattr(item, 'duration', 0.0) if not isinstance(item, dict) else item.get('duration', 0.0))
            result.append({
                'text': text.replace('\n', ' ').strip(),
                'start': start,
                'duration': duration,
                'end': start + duration
            })
        if result:
            return result
    except Exception:
        pass

    # Method 2: Legacy fallback
    try:
        proxies = {'http': proxy, 'https': proxy} if proxy else None
        if hasattr(YouTubeTranscriptApi, 'list_transcripts'):
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id, proxies=proxies)
            try:
                transcript = transcript_list.find_transcript(['en', 'en-US', 'en-GB'])
            except Exception:
                transcript = transcript_list.find_generated_transcript(['en'])
            data = transcript.fetch()
            return [
                {
                    'text': item['text'].replace('\n', ' ').strip(),
                    'start': float(item['start']),
                    'duration': float(item.get('duration', 0.0)),
                    'end': float(item['start']) + float(item.get('duration', 0.0))
                }
                for item in data
            ]
    except Exception:
        pass

    return None

def get_transcript_from_groq(audio_path: Path, api_key: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Transcribe audio file using Groq Whisper API (whisper-large-v3).
    """
    key = api_key or GROQ_API_KEY
    if not key:
        raise ValueError("Groq API Key is required for Whisper transcription.")

    client = Groq(api_key=key)

    whisper_models = [GROQ_WHISPER_MODEL, "whisper-large-v3-turbo", "whisper-large-v3"]
    seen = set()
    models_to_try = [m for m in whisper_models if m and not (m in seen or seen.add(m))]

    transcription = None
    last_err = None
    with open(audio_path, "rb") as file:
        audio_bytes = file.read()

    for w_model in models_to_try:
        try:
            transcription = client.audio.transcriptions.create(
                file=(audio_path.name, audio_bytes),
                model=w_model,
                response_format="verbose_json",
                temperature=0.0
            )
            break
        except Exception as err:
            last_err = err
            if "model" in str(err).lower() or "404" in str(err):
                continue
            raise err

    if transcription is None:
        raise last_err

    # transcription segments
    segments = []
    # Groq returns segments in verbose_json
    raw_segments = getattr(transcription, "segments", []) or []
    for seg in raw_segments:
        start = float(seg.get("start", 0.0) if isinstance(seg, dict) else getattr(seg, "start", 0.0))
        end = float(seg.get("end", 0.0) if isinstance(seg, dict) else getattr(seg, "end", 0.0))
        text = (seg.get("text", "") if isinstance(seg, dict) else getattr(seg, "text", "")).strip()
        segments.append({
            'text': text,
            'start': start,
            'end': end,
            'duration': max(0.1, end - start)
        })

    return segments

def get_video_transcript(url: str, api_key: Optional[str] = None, proxy: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Primary entrypoint: Try YouTube captions first; if unavailable, download audio and transcribe via Groq.
    """
    video_id = extract_video_id(url)
    if not video_id:
        raise ValueError(f"Invalid YouTube URL: {url}")

    # 1. Try free YouTube transcript API
    transcript = get_transcript_from_youtube(video_id, proxy=proxy)
    if transcript:
        return transcript

    # 2. Fallback to Groq Whisper
    audio_path = download_audio_only(url, proxy=proxy)
    try:
        return get_transcript_from_groq(audio_path, api_key=api_key)
    finally:
        # Clean up temporary audio file
        if audio_path.exists():
            try:
                audio_path.unlink()
            except Exception:
                pass

def format_transcript_for_llm(transcript: List[Dict[str, Any]]) -> str:
    """
    Convert raw transcript list into a clean, timestamped text block for the LLM.
    Merges adjacent fragments into 12-second paragraphs to reduce token count
    and stay well within Groq free-tier rate limits (6000 TPM).
    """
    if not transcript:
        return ""

    merged = []
    current_chunk = []
    chunk_start = transcript[0]['start']
    chunk_duration = 0.0

    for item in transcript:
        text = item['text'].strip()
        if not text:
            continue
        current_chunk.append(text)
        chunk_duration += item.get('duration', 2.0)

        # Group speech into coherent ~12-second thoughts
        if chunk_duration >= 12.0:
            start_str = format_timestamp(chunk_start)
            end_sec = item['start'] + item.get('duration', 0.0)
            end_str = format_timestamp(end_sec)
            merged.append(f"[{start_str} - {end_str}] {' '.join(current_chunk)}")
            current_chunk = []
            chunk_start = end_sec
            chunk_duration = 0.0

    if current_chunk:
        start_str = format_timestamp(chunk_start)
        last_sec = transcript[-1]['start'] + transcript[-1].get('duration', 0.0)
        end_str = format_timestamp(last_sec)
        merged.append(f"[{start_str} - {end_str}] {' '.join(current_chunk)}")

    # If transcript is very long (>3000 words), sample evenly to stay within TPM limits
    total_text = "\n".join(merged)
    words = total_text.split()
    if len(words) > 3000:
        step = max(2, len(merged) // 80)
        return "\n".join(merged[::step])

    return total_text
