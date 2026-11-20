from core.dns_patch import apply_secure_dns
apply_secure_dns()

import os
import time
import shutil
from pathlib import Path
import streamlit as st

from config import (
    TEMP_DIR,
    OUTPUT_DIR,
    GROQ_API_KEY,
    FRAMING_BLURRED_BG,
    FRAMING_CENTER_CROP,
    FRAMING_ORIGINAL,
)
from core.downloader import (
    extract_video_id,
    normalize_youtube_url,
    get_video_info,
    download_video_section,
    extract_audio_from_file,
    check_video_status,
)
from core.transcript import (
    get_video_transcript,
    get_transcript_from_groq,
    format_timestamp,
)
from core.analyzer import analyze_transcript_for_clips
from core.subtitles import (
    extract_clip_transcript,
    generate_ass_subtitles,
)
from core.video_processor import process_video_clip

st.set_page_config(
    page_title="AI Video Clipper - Free Viral Shorts Generator",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .main-title {
        font-size: 2.4rem;
        font-weight: 800;
        background: -webkit-linear-gradient(45deg, #FF4B4B, #FF8F00);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0px;
    }
    .sub-title {
        color: #888888;
        font-size: 1.1rem;
        margin-bottom: 1.5rem;
    }
    .tip-box {
        background-color: #1a1a24;
        border-left: 4px solid #FF8F00;
        padding: 12px;
        border-radius: 6px;
        margin-bottom: 15px;
    }
</style>
""", unsafe_allow_html=True)

# --- Sidebar Configuration ---
with st.sidebar:
    st.header("⚙️ Configuration")
    
    user_groq_key = st.text_input(
        "Groq API Key (Free)",
        value=GROQ_API_KEY,
        type="password",
        help="Get a 100% free key with high limits at https://console.groq.com/keys"
    )
    if not user_groq_key:
        st.warning("⚠️ Enter your Groq API key to enable AI clip detection.")
    else:
        st.success("✅ Groq API key connected!")

    with st.expander("🌐 Proxy / VPN Settings (Optional)"):
        st.caption("If your local network/firewall restricts YouTube, enter a proxy below (e.g. `http://127.0.0.1:7890` or `socks5://127.0.0.1:10808`).")
        user_proxy = st.text_input("Proxy URL", value="", placeholder="http://127.0.0.1:7890")
        proxy_val = user_proxy.strip() if user_proxy.strip() else None

    st.markdown("---")
    st.subheader("✂️ Clip Settings")

    target_duration = st.slider(
        "Target Duration (seconds)",
        min_value=15,
        max_value=90,
        value=30,
        step=5,
        help="Average duration for each generated clip."
    )

    num_clips = st.slider(
        "Number of Clips",
        min_value=1,
        max_value=5,
        value=3,
        help="How many top viral moments to generate."
    )

    framing_option = st.selectbox(
        "Framing / Aspect Ratio",
        options=[
            ("Blurred Background (9:16 Vertical)", FRAMING_BLURRED_BG),
            ("Center Crop (9:16 Vertical)", FRAMING_CENTER_CROP),
            ("Original Widescreen (16:9)", FRAMING_ORIGINAL)
        ],
        format_func=lambda x: x[0]
    )[1]

    st.markdown("---")
    st.subheader("💬 Subtitles / Captions")
    enable_subtitles = st.checkbox("Burn Animated Subtitles", value=True)
    font_size = st.slider("Caption Font Size", min_value=18, max_value=32, value=24)

    st.markdown("---")
    st.caption("Built with Groq Llama 3.3, Whisper & FFmpeg. 100% Free & Open Source.")

# --- Main Layout ---
st.markdown('<div class="main-title">🎬 Free AI YouTube Video Clipper</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Turn long videos into viral Shorts, Reels & TikToks in seconds without paying for OpusClip or Klap.</div>', unsafe_allow_html=True)

tab_yt, tab_local = st.tabs(["🔗 YouTube Link", "📁 Upload Local Video File"])

# ==========================================
# TAB 1: YOUTUBE VIDEO
# ==========================================
with tab_yt:
    def on_sample_video_change():
        chosen = st.session_state.get("sample_video_choice")
        if chosen == "TED Talk: How to Speak so People Want to Listen":
            st.session_state["yt_link_input"] = "https://www.youtube.com/watch?v=eIho2S0ZahI"
        elif chosen == "Sample Music & Speech: Rick Astley":
            st.session_state["yt_link_input"] = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        elif chosen == "Custom link (paste below)":
            st.session_state["yt_link_input"] = ""

    if "yt_link_input" not in st.session_state:
        st.session_state["yt_link_input"] = ""

    sample_choice = st.selectbox(
        "💡 Quick Test (Or select a working sample video):",
        options=[
            "Custom link (paste below)",
            "TED Talk: How to Speak so People Want to Listen",
            "Sample Music & Speech: Rick Astley"
        ],
        key="sample_video_choice",
        on_change=on_sample_video_change
    )

    youtube_url = st.text_input(
        "Paste YouTube Video Link:",
        key="yt_link_input",
        placeholder="https://www.youtube.com/watch?v=..."
    )

    col_btn, _ = st.columns([1, 4])
    with col_btn:
        generate_yt_btn = st.button("🚀 Generate Clips from YouTube", type="primary", use_container_width=True)

    if generate_yt_btn:
        if not youtube_url:
            st.error("Please enter a valid YouTube URL.")
            st.stop()

        youtube_url = normalize_youtube_url(youtube_url)

        if not user_groq_key:
            st.error("Please provide your Groq API key in the sidebar.")
            st.stop()

        video_id = extract_video_id(youtube_url)
        if not video_id:
            st.error("Invalid YouTube URL. Please check the link and try again.")
            st.stop()

        status_box = st.status("🎬 Processing YouTube Video...", expanded=True)

        try:
            # Step 0: Availability Pre-flight check
            status_box.write("🔍 Verifying video availability on YouTube...")
            vid_status = check_video_status(youtube_url)
            if not vid_status.get("available", True):
                status_box.update(label="❌ Video Unavailable on YouTube", state="error")
                st.error(
                    f"⚠️ **{vid_status.get('reason')}**\n\n"
                    "### 💡 How to solve this:\n"
                    "1. **Check the Video**: Open this link in an Incognito browser window. If it shows *'Video unavailable'* or *'This live stream recording is not available'*, YouTube has deleted or hidden it, so no downloader can access it.\n"
                    "2. **Use a Working Sample**: Select **'TED Talk'** or **'Rick Astley'** from the dropdown above to test the AI clipper on a guaranteed public video.\n"
                    "3. **Switch to 'Upload Local Video File' tab**: If you have the video file saved on your phone/computer, click the **'📁 Upload Local Video File'** tab above to clip it directly without needing YouTube!"
                )
                st.stop()

            # Step 1: Video Info
            status_box.write("📥 Fetching video details...")
            info = get_video_info(youtube_url, proxy=proxy_val)

            st.sidebar.image(info["thumbnail"], caption=info["title"], use_container_width=True)
            status_box.write(f"✅ Video: **{info['title']}** ({format_timestamp(info['duration'])})")

            # Step 2: Transcripts
            status_box.write("🎙️ Extracting transcript (YouTube captions / Groq Whisper)...")
            transcript = get_video_transcript(youtube_url, api_key=user_groq_key, proxy=proxy_val)

            if not transcript or len(transcript) == 0:
                status_box.update(label="❌ Failed to retrieve transcript", state="error")
                st.error("Could not obtain any transcript for this video.")
                st.stop()

            status_box.write(f"✅ Extracted {len(transcript)} transcript segments.")

            # Step 3: Groq LLM Viral Analysis
            status_box.write("🧠 Groq AI (Llama 3.3) is finding high-retention moments...")
            clips_data = analyze_transcript_for_clips(
                transcript=transcript,
                target_duration=target_duration,
                num_clips=num_clips,
                api_key=user_groq_key
            )

            if not clips_data:
                status_box.update(label="❌ No suitable clips found", state="error")
                st.warning("Could not find suitable clips matching your duration criteria.")
                st.stop()

            status_box.write(f"🔥 Found **{len(clips_data)}** viral clip candidates!")

            # Step 4: Video Cutting & Rendering
            status_box.write("✂️ Downloading and rendering 9:16 clips with FFmpeg...")
            generated_clips = []

            for idx, clip in enumerate(clips_data, 1):
                status_box.write(f"Rendering Clip {idx}/{len(clips_data)}: *{clip['title']}* ({clip['start_time']}s - {clip['end_time']}s)...")

                clip_video_raw = TEMP_DIR / f"{video_id}_raw_{idx}.mp4"
                final_clip_path = OUTPUT_DIR / f"clip_{video_id}_{idx}_{int(time.time())}.mp4"

                # Download section directly
                download_video_section(
                    url=youtube_url,
                    start_time=clip["start_time"],
                    end_time=clip["end_time"],
                    output_path=clip_video_raw,
                    proxy=proxy_val
                )

                # Subtitles
                sub_path = None
                if enable_subtitles:
                    clip_sub_segments = extract_clip_transcript(
                        full_transcript=transcript,
                        clip_start=clip["start_time"],
                        clip_end=clip["end_time"]
                    )
                    if clip_sub_segments:
                        ass_file = TEMP_DIR / f"{video_id}_sub_{idx}.ass"
                        sub_path = generate_ass_subtitles(
                            segments=clip_sub_segments,
                            output_path=ass_file,
                            font_size=font_size
                        )

                # Process with FFmpeg
                process_video_clip(
                    input_video=clip_video_raw,
                    output_path=final_clip_path,
                    framing_mode=framing_option,
                    subtitle_path=sub_path
                )

                if clip_video_raw.exists():
                    try:
                        clip_video_raw.unlink()
                    except Exception:
                        pass

                clip["file_path"] = str(final_clip_path)
                generated_clips.append(clip)

            status_box.update(label="🎉 All clips successfully generated!", state="complete", expanded=False)
            st.session_state["clips"] = generated_clips

        except Exception as e:
            err_msg = str(e)
            status_box.update(label="❌ Error occurred", state="error")
            if "429" in err_msg or "rate limit" in err_msg.lower():
                st.error("⚠️ **Groq Rate Limit Reached**: Free accounts have a per-minute token limit. Please wait 30–60 seconds and try again!")
            elif "401" in err_msg or "invalid_api_key" in err_msg.lower():
                st.error("⚠️ **Invalid Groq API Key**: Please check your API key in the sidebar.")
            elif "403" in err_msg or "forbidden" in err_msg.lower():
                st.error(
                    "⚠️ **Access Denied (HTTP 403 Forbidden)**:\n\n"
                    "YouTube blocked cloud access to this specific video. This happens when:\n"
                    "- The link is an expired live stream, private, or age-restricted.\n"
                    "- YouTube datacenter bot detection is blocking Streamlit Cloud's IP.\n\n"
                    "**Solutions:**\n"
                    "1. Try selecting a sample video above (e.g. TED Talk or Rick Astley).\n"
                    "2. Switch to the **'📁 Upload Local Video File'** tab to upload and clip any video directly from your phone!\n"
                    "3. Run the mobile tunnel from your PC (`run_mobile.bat`) to use your home IP instead of AWS cloud."
                )
            elif "unavailable" in err_msg.lower():
                st.error("⚠️ **Video Unavailable**: YouTube reports this video does not exist, has ended, or is set to private. Please test with another public video link!")
            elif "timed out" in err_msg.lower() or "unable to download" in err_msg.lower():
                st.error(f"Network Connection Issue: {err_msg}")
            else:
                st.error(f"Error processing video: {err_msg}")

# ==========================================
# TAB 2: LOCAL VIDEO FILE UPLOAD
# ==========================================
with tab_local:
    st.info("💡 Upload any video from your phone or PC (saved videos, screen recordings, podcasts, TikToks). Works 100% reliably and completely bypasses YouTube network restrictions!")
    uploaded_file = st.file_uploader("Choose a video file", type=["mp4", "mov", "mkv", "webm", "avi"])

    col_local_btn, _ = st.columns([1, 4])
    with col_local_btn:
        generate_local_btn = st.button("🚀 Generate Clips from File", type="primary", use_container_width=True)

    if generate_local_btn:
        if not uploaded_file:
            st.error("Please upload a video file first.")
            st.stop()

        if not user_groq_key:
            st.error("Please provide your Groq API key in the sidebar.")
            st.stop()

        status_box = st.status("🎬 Processing Local Video...", expanded=True)

        try:
            # Save uploaded file
            status_box.write("💾 Saving video file...")
            local_video_path = TEMP_DIR / uploaded_file.name
            with open(local_video_path, "wb") as f:
                f.write(uploaded_file.getbuffer())

            # Step 1: Extract Audio
            status_box.write("🎙️ Extracting audio for Groq Whisper...")
            audio_path = extract_audio_from_file(local_video_path)

            # Step 2: Transcribe via Groq Whisper
            status_box.write("⚡ Transcribing audio with Groq Whisper Large v3...")
            transcript = get_transcript_from_groq(audio_path, api_key=user_groq_key)

            if not transcript:
                status_box.update(label="❌ Failed to transcribe audio", state="error")
                st.error("Could not obtain any speech from the video.")
                st.stop()

            status_box.write(f"✅ Transcribed {len(transcript)} spoken segments.")

            # Step 3: Groq LLM Viral Analysis
            status_box.write("🧠 Groq AI (Llama 3.3) is finding high-retention moments...")
            clips_data = analyze_transcript_for_clips(
                transcript=transcript,
                target_duration=target_duration,
                num_clips=num_clips,
                api_key=user_groq_key
            )

            if not clips_data:
                status_box.update(label="❌ No suitable clips found", state="error")
                st.warning("Could not find suitable clips matching your duration criteria.")
                st.stop()

            status_box.write(f"🔥 Found **{len(clips_data)}** viral clip candidates!")

            # Step 4: Render Clips
            status_box.write("✂️ Cutting and rendering 9:16 vertical clips with FFmpeg...")
            generated_clips = []

            for idx, clip in enumerate(clips_data, 1):
                status_box.write(f"Rendering Clip {idx}/{len(clips_data)}: *{clip['title']}* ({clip['start_time']}s - {clip['end_time']}s)...")

                final_clip_path = OUTPUT_DIR / f"clip_local_{idx}_{int(time.time())}.mp4"

                # Subtitles
                sub_path = None
                if enable_subtitles:
                    clip_sub_segments = extract_clip_transcript(
                        full_transcript=transcript,
                        clip_start=clip["start_time"],
                        clip_end=clip["end_time"]
                    )
                    if clip_sub_segments:
                        ass_file = TEMP_DIR / f"local_sub_{idx}.ass"
                        sub_path = generate_ass_subtitles(
                            segments=clip_sub_segments,
                            output_path=ass_file,
                            font_size=font_size
                        )

                # Process with FFmpeg directly from source video
                process_video_clip(
                    input_video=local_video_path,
                    output_path=final_clip_path,
                    start_time=clip["start_time"],
                    duration=clip["duration"],
                    framing_mode=framing_option,
                    subtitle_path=sub_path
                )

                clip["file_path"] = str(final_clip_path)
                generated_clips.append(clip)

            status_box.update(label="🎉 All clips successfully generated!", state="complete", expanded=False)
            st.session_state["clips"] = generated_clips

        except Exception as e:
            err_msg = str(e)
            status_box.update(label="❌ Error occurred", state="error")
            if "429" in err_msg or "rate limit" in err_msg.lower():
                st.error("⚠️ **Groq Rate Limit Reached**: Free accounts have a per-minute token limit. Please wait 30–60 seconds and try again!")
            elif "401" in err_msg or "invalid_api_key" in err_msg.lower():
                st.error("⚠️ **Invalid Groq API Key**: Please check your API key in the sidebar.")
            else:
                st.error(f"Error processing video: {err_msg}")

# --- Display Generated Clips ---
if "clips" in st.session_state and st.session_state["clips"]:
    st.markdown("---")
    st.subheader(f"✨ Generated Viral Clips ({len(st.session_state['clips'])})")

    cols = st.columns(min(len(st.session_state["clips"]), 3))

    for idx, clip in enumerate(st.session_state["clips"]):
        col = cols[idx % len(cols)]
        with col:
            st.markdown(f"### #{idx+1} {clip['title']}")
            st.caption(f"⏱️ **{format_timestamp(clip['start_time'])} - {format_timestamp(clip['end_time'])}** ({clip['duration']}s)")
            st.markdown(f"🔥 **Virality Score:** `{clip['virality_score']}/10`")
            st.markdown(f"💡 *\"{clip.get('hook', '')}\"*")

            if os.path.exists(clip["file_path"]):
                st.video(clip["file_path"])
                with open(clip["file_path"], "rb") as f:
                    st.download_button(
                        label=f"⬇️ Download Clip #{idx+1}",
                        data=f,
                        file_name=Path(clip["file_path"]).name,
                        mime="video/mp4",
                        use_container_width=True
                    )
