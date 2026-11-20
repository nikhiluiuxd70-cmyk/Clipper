import json
from typing import List, Dict, Any, Optional
from groq import Groq
from core.transcript import format_transcript_for_llm
from config import GROQ_API_KEY, GROQ_LLM_MODEL

def analyze_transcript_for_clips(
    transcript: List[Dict[str, Any]],
    target_duration: int = 30,
    min_duration: Optional[int] = None,
    max_duration: Optional[int] = None,
    num_clips: int = 3,
    api_key: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Use Groq LLM (Llama 3.3 70B) to analyze video transcript and find the most engaging,
    standalone viral clips matching user duration preferences.
    """
    key = api_key or GROQ_API_KEY
    if not key:
        raise ValueError("Groq API Key is required for clip analysis.")

    client = Groq(api_key=key)

    if min_duration is None:
        min_duration = max(10, int(target_duration * 0.65))
    if max_duration is None:
        max_duration = int(target_duration * 1.35)

    formatted_transcript = format_transcript_for_llm(transcript)

    system_prompt = (
        "You are an expert viral video editor and content strategist specializing in YouTube Shorts, "
        "TikTok, and Instagram Reels. Your mission is to analyze timestamped video transcripts and "
        "identify the absolute most engaging, high-retention segments.\n\n"
        "Criteria for a great clip:\n"
        "1. Hook: Starts with an intriguing question, bold claim, or strong statement.\n"
        "2. Standalone Value: Delivers a complete idea, story, punchline, or insight without needing prior context.\n"
        "3. Duration: Each clip MUST have a duration between the specified MIN and MAX seconds.\n"
        "4. Precise Timestamps: Use exact start_time and end_time (in seconds) matching natural pauses in speech."
    )

    user_prompt = f"""
Here is the timestamped transcript of the video:
---
{formatted_transcript}
---

Requirements:
- Target Duration: ~{target_duration} seconds per clip.
- Strict Duration Limits: Minimum {min_duration} seconds, Maximum {max_duration} seconds.
- Number of top clips to extract: {num_clips}.
- Find the {num_clips} most viral, high-retention segments.

Respond strictly with a JSON object adhering to this schema:
{{
  "clips": [
    {{
      "title": "Engaging Short Title (under 40 chars)",
      "start_time": 12.5,
      "end_time": 42.0,
      "hook": "The opening sentence of the clip",
      "summary": "Why this moment is captivating",
      "virality_score": 9.5,
      "hashtags": ["#tag1", "#tag2"]
    }}
  ]
}}
"""

    candidate_models = [
        GROQ_LLM_MODEL,
        "llama-3.1-8b-instant",
        "llama-3.3-70b-versatile",
        "llama3-70b-8192",
        "llama3-8b-8192",
        "mixtral-8x7b-32768"
    ]
    # Remove duplicates preserving order
    seen = set()
    models_to_try = [m for m in candidate_models if m and not (m in seen or seen.add(m))]

    response = None
    last_err = None
    for model_name in models_to_try:
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.3
            )
            break
        except Exception as err:
            last_err = err
            err_str = str(err).lower()
            if "model" in err_str or "not exist" in err_str or "404" in err_str or "access" in err_str:
                continue
            raise err

    if response is None:
        raise last_err

    response_text = response.choices[0].message.content
    data = json.loads(response_text)
    raw_clips = data.get("clips", [])

    # Validate and clean clips
    validated_clips = []
    for clip in raw_clips:
        start = float(clip.get("start_time", 0.0))
        end = float(clip.get("end_time", 0.0))
        duration = end - start

        if duration < min_duration * 0.7 or duration > max_duration * 1.4:
            # Skip invalid duration if heavily out of bounds
            continue

        clip["start_time"] = round(start, 2)
        clip["end_time"] = round(end, 2)
        clip["duration"] = round(duration, 2)
        clip["virality_score"] = float(clip.get("virality_score", 8.0))
        validated_clips.append(clip)

    # Sort by virality score descending
    validated_clips.sort(key=lambda x: x.get("virality_score", 0), reverse=True)
    return validated_clips[:num_clips]
