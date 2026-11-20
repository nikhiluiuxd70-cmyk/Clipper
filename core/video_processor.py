import os
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any
try:
    import imageio_ffmpeg
except ImportError:
    imageio_ffmpeg = None
from config import FRAMING_BLURRED_BG, FRAMING_CENTER_CROP, FRAMING_ORIGINAL

def get_ffmpeg_bin() -> str:
    """Return path to modern FFmpeg executable."""
    if imageio_ffmpeg is not None:
        try:
            return imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            pass
    return "ffmpeg"

def escape_ffmpeg_path(path: Path) -> str:
    """Format file path for FFmpeg filter arguments on Windows."""
    # Convert to posix style (forward slashes) and escape the drive letter colon
    posix_path = path.as_posix()
    return posix_path.replace(":", r"\:")

def build_filter_graph(
    framing_mode: str = FRAMING_BLURRED_BG,
    subtitle_path: Optional[Path] = None
) -> str:
    """
    Construct the FFmpeg -vf or -filter_complex string based on framing mode and subtitles.
    """
    filters = []

    if framing_mode == FRAMING_BLURRED_BG:
        # Scale & blur for 9:16 background, overlay 16:9 in center
        complex_filter = (
            "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:5[bg];"
            "[0:v]scale=1080:-2[fg];"
            "[bg][fg]overlay=(W-w)/2:(H-h)/2"
        )
        if subtitle_path and subtitle_path.exists():
            sub_escaped = escape_ffmpeg_path(subtitle_path)
            complex_filter += f",subtitles='{sub_escaped}'[outv]"
        else:
            complex_filter += "[outv]"
        return complex_filter

    elif framing_mode == FRAMING_CENTER_CROP:
        # 9:16 Center crop
        crop_filter = "crop=ih*9/16:ih,scale=1080:1920"
        if subtitle_path and subtitle_path.exists():
            sub_escaped = escape_ffmpeg_path(subtitle_path)
            crop_filter += f",subtitles='{sub_escaped}'"
        return crop_filter

    else:
        # Original aspect ratio
        if subtitle_path and subtitle_path.exists():
            sub_escaped = escape_ffmpeg_path(subtitle_path)
            return f"subtitles='{sub_escaped}'"
        return ""

def process_video_clip(
    input_video: Path,
    output_path: Path,
    start_time: Optional[float] = None,
    duration: Optional[float] = None,
    framing_mode: str = FRAMING_BLURRED_BG,
    subtitle_path: Optional[Path] = None
) -> Path:
    """
    Cut video and apply vertical framing and subtitle overlays with FFmpeg.
    """
    cmd = [get_ffmpeg_bin(), "-y"]

    # Fast seeking if start_time is provided
    if start_time is not None:
        cmd.extend(["-ss", str(start_time)])

    cmd.extend(["-i", str(input_video)])

    if duration is not None:
        cmd.extend(["-t", str(duration)])

    filter_str = build_filter_graph(framing_mode, subtitle_path)

    if framing_mode == FRAMING_BLURRED_BG:
        cmd.extend(["-filter_complex", filter_str, "-map", "[outv]", "-map", "0:a?"])
    elif filter_str:
        cmd.extend(["-vf", filter_str, "-map", "0:v?", "-map", "0:a?"])
    else:
        cmd.extend(["-map", "0:v?", "-map", "0:a?"])

    # Encoding options for broad compatibility (H.264 + AAC)
    cmd.extend([
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "22",
        "-c:a", "aac",
        "-b:a", "128k",
        "-pix_fmt", "yuv420p",
        str(output_path)
    ])

    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        # If subtitles filter failed (e.g. font issue), fallback without subtitles
        if subtitle_path and "subtitles" in filter_str:
            return process_video_clip(
                input_video=input_video,
                output_path=output_path,
                start_time=start_time,
                duration=duration,
                framing_mode=framing_mode,
                subtitle_path=None
            )
        raise RuntimeError(f"FFmpeg error: {result.stderr[-500:]}")

    return output_path
