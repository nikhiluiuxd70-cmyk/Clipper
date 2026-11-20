import os
from pathlib import Path
from typing import List, Dict, Any, Optional

def seconds_to_ass_time(seconds: float) -> str:
    """Format seconds into ASS timestamp format: H:MM:SS.cs"""
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centis = int(round((seconds - int(seconds)) * 100))
    if centis >= 100:
        centis = 99
    return f"{hrs}:{mins:02d}:{secs:02d}.{centis:02d}"

def seconds_to_srt_time(seconds: float) -> str:
    """Format seconds into SRT timestamp format: HH:MM:SS,mmm"""
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    if millis >= 1000:
        millis = 999
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{millis:03d}"

def extract_clip_transcript(
    full_transcript: List[Dict[str, Any]],
    clip_start: float,
    clip_end: float
) -> List[Dict[str, Any]]:
    """
    Extract transcript segments that fall inside the clip boundaries,
    and shift their timestamps so they start at 0.0 relative to the clip.
    """
    clip_segments = []
    for item in full_transcript:
        item_start = float(item['start'])
        item_end = float(item.get('end', item_start + item.get('duration', 0.0)))

        # Check if the segment overlaps with the clip
        if item_end > clip_start and item_start < clip_end:
            rel_start = max(0.0, item_start - clip_start)
            rel_end = min(clip_end - clip_start, item_end - clip_start)
            clip_segments.append({
                'text': item['text'].strip(),
                'start': rel_start,
                'end': rel_end,
                'duration': rel_end - rel_start
            })
    return clip_segments

def generate_ass_subtitles(
    segments: List[Dict[str, Any]],
    output_path: Path,
    highlight_color: str = "&H0000FFFF",  # Yellow in BGR hex format
    primary_color: str = "&H00FFFFFF",    # White
    font_name: str = "Arial",
    font_size: int = 24
) -> Path:
    """
    Generate modern styled ASS subtitle file for 9:16 vertical video.
    High-visibility font with strong black outline, centered in lower third.
    """
    ass_header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{font_size},{primary_color},&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,1,0,1,4,2,2,40,40,260,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [ass_header]
    for seg in segments:
        text = seg['text'].upper()
        if not text:
            continue
        start_t = seconds_to_ass_time(seg['start'])
        end_t = seconds_to_ass_time(seg['end'])
        # Add slight styling / bold punch
        lines.append(f"Dialogue: 0,{start_t},{end_t},Default,,0,0,0,,{text}\n")

    output_path.write_text("".join(lines), encoding="utf-8")
    return output_path

def generate_srt_subtitles(segments: List[Dict[str, Any]], output_path: Path) -> Path:
    """Generate standard .srt subtitle file."""
    lines = []
    for idx, seg in enumerate(segments, 1):
        text = seg['text'].strip()
        if not text:
            continue
        start_t = seconds_to_srt_time(seg['start'])
        end_t = seconds_to_srt_time(seg['end'])
        lines.append(f"{idx}\n{start_t} --> {end_t}\n{text}\n\n")

    output_path.write_text("".join(lines), encoding="utf-8")
    return output_path
