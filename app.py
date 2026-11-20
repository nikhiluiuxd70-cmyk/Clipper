from core.dns_patch import apply_secure_dns
apply_secure_dns()

import os
import re
import time
import shutil
from pathlib import Path
import streamlit as st

from config import (
    TEMP_DIR,
    DOWNLOADS_DIR,
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
    download_full_video,
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
    page_title="AI YouTube Downloader & Viral Clipper",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for modern styling
st.markdown("""
<style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 800;
        background: linear-gradient(90deg, #FF4B4B, #FF8F00);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0px;
    }
    .sub-title {
        color: #888888;
        font-size: 1.05rem;
        margin-bottom: 25px;
    }
    .step-card {
        background-color: #1a1c24;
        border-radius: 12px;
        padding: 20px;
        border: 1px solid #2d313e;
        margin-bottom: 20px;
    }
    .stButton>button {
        border-radius: 8px;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# --- Sidebar Configuration ---
with st.sidebar:
    st.header("⚙️ Settings")

    user_groq_key = st.text_input(
        "Groq API Key",
        value=GROQ_API_KEY,
        type="password",
        help="Free key from console.groq.com. Needed for Whisper audio transcription & Llama viral clipping."
    )

    if not user_groq_key:
        st.warning("⚠️ Enter your free Groq API key to enable AI transcription and viral analysis.")
        st.markdown("[Get Free Groq API Key](https://console.groq.com/keys)")

    proxy_val = st.text_input(
        "Network Proxy (Optional)",
        value="",
        placeholder="e.g. http://proxy.host:port",
        help="Leave blank unless your network strictly requires an outbound HTTP proxy."
    )
    if not proxy_val:
        proxy_val = None

    st.markdown("---")
    st.subheader("✂️ Viral Clip Preferences")
    target_duration = st.slider(
        "Target Duration (seconds)",
        min_value=15,
        max_value=60,
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
    st.caption("Powered by Groq Whisper, Llama 3.3 & FFmpeg. 100% Free & Open Source.")

# --- Main Title ---
st.markdown('<div class="main-title">🎬 AI YouTube Downloader & Viral Clipper</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Part 1: Download any YouTube video to your device. Part 2: Turn any video into viral 9:16 Shorts & Reels with Groq AI!</div>', unsafe_allow_html=True)

# --- Two-Part Workflow Tabs ---
tab_part1, tab_part2 = st.tabs([
    "📥 Part 1: Download YouTube Video",
    "🎬 Part 2: AI Viral Clip Generator"
])

# ==========================================
# PART 1: YOUTUBE DOWNLOADER
# ==========================================
with tab_part1:
    st.markdown("### 📥 Part 1: Download Full YouTube Video to Device")
    st.write("Paste any YouTube link, choose your video quality, download it to your device (it will prompt you for the save location), or send it straight to the AI Clipper.")

    def on_sample_p1_change():
        chosen = st.session_state.get("p1_sample_selector")
        if chosen == "TED Talk: How to Speak so People Want to Listen":
            st.session_state["p1_yt_link"] = "https://www.youtube.com/watch?v=eIho2S0ZahI"
        elif chosen == "Sample Music & Speech: Rick Astley":
            st.session_state["p1_yt_link"] = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        elif chosen == "Custom link (paste below)":
            st.session_state["p1_yt_link"] = ""

    if "p1_yt_link" not in st.session_state:
        st.session_state["p1_yt_link"] = ""

    p1_sample_choice = st.selectbox(
        "💡 Quick Test (Or select a working sample video):",
        options=[
            "Custom link (paste below)",
            "TED Talk: How to Speak so People Want to Listen",
            "Sample Music & Speech: Rick Astley"
        ],
        key="p1_sample_selector",
        on_change=on_sample_p1_change
    )

    p1_youtube_url = st.text_input(
        "Paste YouTube Video Link:",
        key="p1_yt_link",
        placeholder="https://www.youtube.com/watch?v=..."
    )

    if p1_youtube_url:
        active_vid_id = extract_video_id(p1_youtube_url)
        if active_vid_id:
            st.markdown(
                """
                <div style="background-color: #1e2230; padding: 14px; border-radius: 10px; border-left: 4px solid #00d26a; margin: 10px 0;">
                    <b style="color: #00d26a; font-size: 1.05rem;">📲 Fast 1-Tap Mobile Download:</b><br/>
                    <span style="font-size: 0.9rem; color: #ccc;">
                        Because YouTube blocks cloud hosting servers (AWS), use these links to download straight onto your phone's 5G network with <b>0 blocks</b>:
                    </span>
                </div>
                """,
                unsafe_allow_html=True
            )
            col_m1, col_m2 = st.columns(2)
            with col_m1:
                st.link_button(
                    "⬇️ Download via SaveFrom (Instant MP4)",
                    f"https://www.ssyoutube.com/watch?v={active_vid_id}",
                    type="primary",
                    use_container_width=True
                )
            with col_m2:
                st.link_button(
                    "⬇️ Download via 10Downloader (HD)",
                    f"https://10downloader.com/download?v={active_vid_id}",
                    use_container_width=True
                )
            st.caption("⚡ **Speed Tip:** On SaveFrom / 10Downloader, select **720p or 480p** (around 15MB–25MB). It downloads in 3 seconds to your phone and uploads in just **5 seconds** in Part 2!")
            st.markdown("---")

    col_q1, col_btn1 = st.columns([1, 2])
    with col_q1:
        video_quality = st.selectbox(
            "Video Quality:",
            options=["720p HD (Recommended)", "1080p Full HD", "480p SD"]
        )
        quality_val = "720p"
        if "1080p" in video_quality:
            quality_val = "1080p"
        elif "480p" in video_quality:
            quality_val = "480p"

    with col_btn1:
        st.write("")
        st.write("")
        download_yt_btn = st.button("☁️ Or Download on Cloud Server", use_container_width=True)

    if download_yt_btn:
        if not p1_youtube_url:
            st.error("Please enter a YouTube video URL.")
            st.stop()

        canonical_url = normalize_youtube_url(p1_youtube_url)
        vid_id = extract_video_id(canonical_url)
        if not vid_id:
            st.error("Invalid YouTube URL. Please check the link and try again.")
            st.stop()

        p1_status = st.status("📥 Downloading YouTube Video...", expanded=True)

        try:
            # Pre-flight check
            p1_status.write("🔍 Verifying video availability on YouTube...")
            vid_check = check_video_status(canonical_url)
            if not vid_check.get("available", True):
                p1_status.update(label="❌ Video Unavailable", state="error")
                st.error(
                    f"⚠️ **{vid_check.get('reason')}**\n\n"
                    "**How to solve:**\n"
                    "- Please ensure the YouTube video is public and can be played in an Incognito browser window.\n"
                    "- If the video was an ended live stream, the creator has not published the recording."
                )
                st.stop()

            # Metadata
            p1_status.write("📋 Fetching video details...")
            info = get_video_info(canonical_url, proxy=proxy_val)
            p1_status.write(f"🎬 Video: **{info['title']}** ({format_timestamp(info['duration'])})")

            # Download full video
            p1_status.write(f"⬇️ Downloading full {quality_val} video with FFmpeg...")
            safe_name = re.sub(r'[^a-zA-Z0-9_\- ]+', '', info['title'])[:40].strip() or vid_id
            target_path = DOWNLOADS_DIR / f"{safe_name}_{vid_id}.mp4"

            downloaded_file = download_full_video(
                url=canonical_url,
                output_path=target_path,
                quality=quality_val,
                proxy=proxy_val
            )

            p1_status.update(label="🎉 Download complete!", state="complete", expanded=False)

            st.session_state["downloaded_video"] = {
                "path": str(downloaded_file),
                "title": info["title"],
                "filename": f"{safe_name}.mp4",
                "thumbnail": info.get("thumbnail", "")
            }

        except Exception as e:
            p1_status.update(label="❌ Download failed", state="error")
            err_str = str(e)
            if "403" in err_str or "forbidden" in err_str.lower():
                st.error(
                    "⚠️ **YouTube Cloud Access Blocked (HTTP 403 Forbidden)**:\n\n"
                    "YouTube has blocked Streamlit Cloud's AWS server from downloading this video directly.\n\n"
                    "**How to download right now on your phone:**\n"
                    "1. Tap the green **'⬇️ Download via SaveFrom'** or **'10Downloader'** button above to download directly onto your phone's 5G connection with 0 blocks!\n"
                    "2. Then switch to **'🎬 Part 2: AI Viral Clip Generator'** above and upload your video to create viral clips!"
                )
            elif "unavailable" in err_str.lower():
                st.error("⚠️ **Video Unavailable**: YouTube reports this video does not exist or has ended.")
            else:
                st.error(f"Download Error: {err_str}")

    # Display downloaded video action cards
    if "downloaded_video" in st.session_state and os.path.exists(st.session_state["downloaded_video"]["path"]):
        dl_info = st.session_state["downloaded_video"]
        file_path = dl_info["path"]
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)

        st.markdown("---")
        st.success(f"✅ **Ready:** {dl_info['title']} ({file_size_mb:.1f} MB)")

        col_v1, col_v2 = st.columns([1, 1])
        with col_v1:
            st.video(file_path)

        with col_v2:
            st.markdown("#### 💾 Save to Device or Clip with AI")
            st.write("Click below to save this video directly to your phone/PC. Your browser will prompt you for the location to save it.")

            with open(file_path, "rb") as f:
                st.download_button(
                    label=f"💾 Save '{dl_info['filename']}' to Device",
                    data=f,
                    file_name=dl_info["filename"],
                    mime="video/mp4",
                    type="primary",
                    use_container_width=True
                )

            st.write("")
            send_to_part2 = st.button("✨ Use this Video in Part 2 (AI Clipper Directly)", use_container_width=True)
            if send_to_part2:
                st.session_state["chosen_clip_video"] = file_path
                st.session_state["chosen_clip_title"] = dl_info["title"]
                st.success("✅ Video loaded into Part 2! Click the **'Part 2: AI Viral Clip Generator'** tab above to generate clips!")

# ==========================================
# PART 2: AI VIRAL CLIP GENERATOR
# ==========================================
with tab_part2:
    st.markdown("### 🎬 Part 2: AI Viral Clip Generator")
    st.write("Upload any video file from your phone/PC (or use the video downloaded from Part 1). Groq AI will transcribe speech, detect viral moments, and FFmpeg will cut 9:16 vertical clips with animated captions!")

    # Video Source Selection
    has_dl_video = "downloaded_video" in st.session_state and os.path.exists(st.session_state["downloaded_video"]["path"])
    video_to_process = None
    video_source_title = ""

    source_options = ["📁 Upload Video File from Phone / PC"]
    if has_dl_video:
        source_options.insert(0, f"📥 Use Downloaded Video: {st.session_state['downloaded_video']['title'][:40]}...")

    source_choice = st.radio(
        "Select Video Input:",
        options=source_options,
        horizontal=True
    )

    if has_dl_video and source_choice.startswith("📥 Use Downloaded Video"):
        video_to_process = Path(st.session_state["downloaded_video"]["path"])
        video_source_title = st.session_state["downloaded_video"]["title"]
        st.info(f"🎬 Active video: **{video_source_title}**")
        st.video(str(video_to_process))
    else:
        st.markdown(
            """
            <div style="background-color: #1e2230; padding: 12px; border-radius: 8px; border-left: 4px solid #3b82f6; margin-bottom: 12px;">
                <b style="color: #60a5fa;">⚡ Pro-Tips for Fast Uploads on Mobile:</b><br/>
                <span style="font-size: 0.88rem; color: #ccc;">
                    • <b>Use 720p or 480p videos (15MB–30MB):</b> They upload in <b>5–8 seconds</b>!<br/>
                    • Large 1080p/4K files (150MB+) take 1–2 minutes over cellular data.<br/>
                    • <b>Wait for 100%:</b> Make sure the blue upload bar reaches 100% and turns into a green checkmark before clicking 'Generate Clips'. Keep your phone screen awake so mobile does not pause the upload!
                </span>
            </div>
            """,
            unsafe_allow_html=True
        )
        uploaded_file = st.file_uploader(
            "Choose a video or audio file from your phone or PC",
            type=["mp4", "mov", "mkv", "webm", "avi", "mp3", "m4a", "wav"],
            help="Videos are trimmed and reframed into 9:16 Shorts with subtitles. Audio files are analyzed for viral moments."
        )
        if uploaded_file:
            saved_local_path = TEMP_DIR / uploaded_file.name
            with open(saved_local_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            video_to_process = saved_local_path
            video_source_title = uploaded_file.name
            file_size_mb = len(uploaded_file.getbuffer()) / (1024 * 1024)
            st.success(f"✅ Uploaded & Ready: **{uploaded_file.name}** ({file_size_mb:.1f} MB)")

    col_clip_btn, _ = st.columns([1, 3])
    with col_clip_btn:
        generate_clips_btn = st.button("🚀 Generate Viral Clips with Groq AI", type="primary", use_container_width=True)

    if generate_clips_btn:
        if not video_to_process or not video_to_process.exists():
            st.error("Please upload or select a video file first.")
            st.stop()

        if not user_groq_key:
            st.error("Please enter your Groq API key in the sidebar.")
            st.stop()

        clip_status = st.status("🎬 Processing Video with AI...", expanded=True)

        try:
            # Step 1: Extract Audio
            clip_status.write("🎙️ Extracting audio track with FFmpeg...")
            audio_path = extract_audio_from_file(video_to_process)

            # Step 2: Transcribe via Groq Whisper
            clip_status.write("⚡ Transcribing audio with Groq Whisper Large v3...")
            transcript = get_transcript_from_groq(audio_path, api_key=user_groq_key)

            if not transcript or len(transcript) == 0:
                clip_status.update(label="❌ Failed to extract speech", state="error")
                st.error("Could not detect any speech in this video. Please make sure the video has clear spoken audio.")
                st.stop()

            clip_status.write(f"✅ Transcribed **{len(transcript)}** spoken segments.")

            # Step 3: Groq LLM Viral Moment Detection
            clip_status.write("🧠 Groq AI is analyzing transcript for high-retention viral moments...")
            clips_data = analyze_transcript_for_clips(
                transcript=transcript,
                target_duration=target_duration,
                num_clips=num_clips,
                api_key=user_groq_key
            )

            if not clips_data:
                clip_status.update(label="❌ No viral moments found", state="error")
                st.warning("Could not find suitable clips matching your duration criteria.")
                st.stop()

            clip_status.write(f"🔥 Detected **{len(clips_data)}** viral clip candidates!")

            # Step 4: Render Vertical Clips
            clip_status.write("✂️ Rendering 9:16 vertical clips with animated captions...")
            rendered_clips = []

            for idx, clip in enumerate(clips_data, 1):
                clip_status.write(f"Rendering Clip {idx}/{len(clips_data)}: *{clip['title']}* ({clip['start_time']}s - {clip['end_time']}s)...")
                final_clip_path = OUTPUT_DIR / f"clip_{idx}_{int(time.time())}.mp4"

                # Subtitles
                sub_path = None
                if enable_subtitles:
                    clip_sub_segments = extract_clip_transcript(
                        full_transcript=transcript,
                        clip_start=clip["start_time"],
                        clip_end=clip["end_time"]
                    )
                    if clip_sub_segments:
                        ass_file = TEMP_DIR / f"clip_sub_{idx}.ass"
                        sub_path = generate_ass_subtitles(
                            segments=clip_sub_segments,
                            output_path=ass_file,
                            font_size=font_size
                        )

                # Process with modern FFmpeg
                process_video_clip(
                    input_video=video_to_process,
                    output_path=final_clip_path,
                    start_time=clip["start_time"],
                    duration=clip["duration"],
                    framing_mode=framing_option,
                    subtitle_path=sub_path
                )

                clip["file_path"] = str(final_clip_path)
                rendered_clips.append(clip)

            clip_status.update(label="🎉 All viral clips successfully created!", state="complete", expanded=False)
            st.session_state["clips"] = rendered_clips

        except Exception as e:
            err_msg = str(e)
            clip_status.update(label="❌ Error occurred", state="error")
            if "blocked at the project level" in err_msg or "model_permission_blocked_project" in err_msg or ("403" in err_msg and "whisper" in err_msg.lower()):
                st.error(
                    "⚠️ **Groq Whisper Audio Model Blocked in Your Groq Project**:\n\n"
                    "Your Groq API key is valid, but your Groq Project currently has audio models (`whisper`) disabled in project limits.\n\n"
                    "### 🛠️ How to Enable it in 15 Seconds (100% Free):\n"
                    "1. Click to open your Groq console: [console.groq.com/settings/project/limits](https://console.groq.com/settings/project/limits)\n"
                    "2. Scroll down to the **Model Permissions** section.\n"
                    "3. Select **Allow All Models** (or toggle on `whisper-large-v3` and `whisper-large-v3-turbo`).\n"
                    "4. Click **Save** at the bottom.\n"
                    "5. Come back here and tap **🚀 Generate Viral Clips with Groq AI** again!"
                )
            elif "429" in err_msg or "rate limit" in err_msg.lower():
                st.error("⚠️ **Groq Rate Limit Reached**: Free accounts have a per-minute token limit. Please wait 30–60 seconds and try again!")
            elif "401" in err_msg or "invalid_api_key" in err_msg.lower():
                st.error("⚠️ **Invalid Groq API Key**: Please check your API key in the sidebar.")
            else:
                st.error(f"Error processing video: {err_msg}")

# ==========================================
# DISPLAY GENERATED CLIPS (RESULTS GALLERY)
# ==========================================
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
