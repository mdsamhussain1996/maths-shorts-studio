"""Maths Shorts Studio — type a topic, get a narrated vertical maths short.

Run with:  streamlit run app.py
"""
from __future__ import annotations

from pathlib import Path

import streamlit as st

from studio.config import load_env_key
from studio.demo import DEMO_SCRIPT, DemoGemini
from studio.llm import Gemini
from studio.pipeline import Settings, list_jobs, make_video
from studio.preamble import latex_available
from studio.research import WORDS_PER_SEC, make_script
from studio.schema import BEAT_LABELS, Beat, Script
from studio.tts import VOICES

ROOT = Path(__file__).resolve().parent
TOPIC_IDEAS = [
    "FASTag: how toll is calculated per km",
    "SIP: why ₹5,000 a month becomes crores",
    "DLS method: how a rain-hit target is set",
    "No-cost EMI: where the interest hides",
    "Tatkal fares and dynamic pricing",
    "Electricity bill slabs: why the 201st unit costs more",
]



st.set_page_config(page_title="Maths Shorts Studio", page_icon="🎬", layout="wide")
st.markdown("""
<style>
.block-container {padding-top: 2rem; max-width: 1200px;}
.beat-tag {display:inline-block; padding:2px 10px; border-radius:6px; font-weight:700; font-size:0.8rem;
           background:#FFB547; color:#0E1116; margin-bottom:6px;}
.small-muted {color:#8B93A1; font-size:0.85rem;}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.header("Settings")
    demo_mode = st.toggle("Demo mode (no API key)", value=False,
                          help="Uses a ready-made UPI pay-later script and scene so you can test voice, rendering and mixing.")
    api_key = st.text_input("Gemini API key", value=load_env_key(), type="password",
                            help="Free key from aistudio.google.com/apikey. Or put GEMINI_API_KEY=... in a .env file next to app.py.",
                            disabled=demo_mode)
    model = st.text_input("Model for research & script", value="gemini-3.5-flash", disabled=demo_mode)
    code_model = st.text_input("Model for animation code", value="gemini-3.5-flash", disabled=demo_mode,
                               help="A Pro model writes more reliable Manim code but uses more of your quota.")
    st.divider()
    quality = st.radio("Video quality", ["draft", "final"],
                       format_func=lambda q: {"draft": "Draft · 540×960 (fast)", "final": "Final · 1080×1920"}[q])
    max_attempts = st.slider("Animation attempts before template", 1, 5, 3,
                             help="If Gemini's scene fails to render, the error is sent back for a fix this many times; then a simple template is used.")
    rate = st.slider("Speech speed", -20, 20, 0, step=5, format="%d%%")
    brand = st.text_input("Brand line at top", value="MATHS IN THE WILD")
    st.divider()
    st.markdown(
        f"<span class='small-muted'>LaTeX for formulas: {'✅ found' if latex_available() else '⚠️ not found — formulas show as plain text (see README)'}</span>",
        unsafe_allow_html=True)

st.title("🎬 Maths Shorts Studio")
st.caption("Type a topic → Gemini researches it and writes a 60-second script → you check the maths → "
           "voice + Manim animation → a vertical MP4 ready for Shorts and Reels.")

tab_make, tab_library = st.tabs(["Create a short", "Library"])

# ---------------------------------------------------------------- create
with tab_make:
    c1, c2, c3, c4 = st.columns([4, 1.3, 1.1, 1.6])
    topic = c1.text_input("Topic", placeholder="e.g. FASTag: how toll is calculated per km",
                          value=st.session_state.get("topic_pick", ""))
    language = c2.selectbox("Language", ["English", "Hinglish", "Hindi"])
    seconds = c3.selectbox("Length", [45, 60, 75, 90], index=1, format_func=lambda s: f"{s} s")
    level = c4.selectbox("Audience", ["college students", "school students (class 8–12)", "general public"])

    with st.expander("Need an idea?"):
        cols = st.columns(3)
        for i, idea in enumerate(TOPIC_IDEAS):
            if cols[i % 3].button(idea, key=f"idea{i}", use_container_width=True):
                st.session_state.topic_pick = idea
                st.rerun()

    voice_names = VOICES[language]
    voice_label = st.selectbox("Voice", list(voice_names.keys()))
    voice = voice_names[voice_label]

    # Step 1 -----------------------------------------------------------
    st.subheader("1 · Research and script")
    if st.button("🔎 Research & write script", type="primary", disabled=not (topic or demo_mode)):
        if demo_mode:
            st.session_state.script = DEMO_SCRIPT.model_dump()
        else:
            try:
                g = Gemini(api_key, model, code_model)
                with st.status("Working on the script…", expanded=True) as status:
                    script = make_script(g, topic, language, seconds, level, log=status.write)
                    status.update(label="Script ready — check it below", state="complete")
                st.session_state.script = script.model_dump()
            except Exception as exc:
                st.error(str(exc))
        st.session_state.pop("result", None)
        st.session_state.script_version = st.session_state.get("script_version", 0) + 1

    script_data = st.session_state.get("script")
    if script_data:
        v = st.session_state.get("script_version", 0)
        sd = script_data
        title = st.text_input("Title", value=sd["title"], key=f"title{v}")

        left, right = st.columns([3, 2])
        with right:
            if sd.get("numbers_to_verify"):
                st.warning("**Check these before rendering** — AI can get numbers wrong:\n\n" +
                           "\n".join(f"- {n}" for n in sd["numbers_to_verify"]))
            if sd.get("sources"):
                with st.expander(f"Web sources ({len(sd['sources'])})"):
                    for s in sd["sources"]:
                        st.markdown(f"- [{s['title']}]({s['url']})")
            if sd.get("research_notes"):
                with st.expander("Research notes"):
                    st.markdown(sd["research_notes"])
            desc = st.text_area("Video description", value=sd.get("description", ""), key=f"desc{v}", height=110)

        edited = []
        with left:
            wps = WORDS_PER_SEC.get(sd.get("language", language), 2.5)
            for i, b in enumerate(sd["beats"]):
                st.markdown(f"<span class='beat-tag'>{BEAT_LABELS.get(b['name'], b['name'])}</span>",
                            unsafe_allow_html=True)
                narr = st.text_area("Narration", value=b["narration"], key=f"n{v}_{i}", height=100,
                                    label_visibility="collapsed")
                st.markdown(f"<span class='small-muted'>≈ {len(narr.split()) / wps:.0f} s spoken</span>",
                            unsafe_allow_html=True)
                k1, k2 = st.columns(2)
                key_text = k1.text_input("On-screen headline", value=b["key_text"], key=f"k{v}_{i}")
                formula = k2.text_input("Formula (LaTeX)", value=b["formula"], key=f"f{v}_{i}")
                if formula.strip():
                    try:
                        st.latex(formula)
                    except Exception:
                        pass
                on_screen = st.text_input("Animation idea", value=b["on_screen"], key=f"o{v}_{i}")
                edited.append(Beat(name=b["name"], narration=narr, key_text=key_text, formula=formula, on_screen=on_screen))
                st.write("")

        total_words = sum(len(b.narration.split()) for b in edited)
        st.caption(f"Estimated length: about {total_words / wps:.0f} s")

        # Step 2 -------------------------------------------------------
        st.subheader("2 · Make the video")
        use_llm_scene = st.checkbox("Let Gemini design the animation (otherwise use the simple template)", value=True)
        if st.button("🎬 Make video", type="primary"):
            script = Script(**{**sd, "title": title, "description": desc, "beats": edited})
            settings = Settings(voice=voice if not demo_mode else "en-IN-NeerjaNeural", rate_pct=rate,
                                quality=quality, max_attempts=max_attempts, use_llm_scene=use_llm_scene, brand=brand)
            try:
                gem = DemoGemini() if demo_mode else Gemini(api_key, model, code_model)
                with st.status("Making your short…", expanded=True) as status:
                    result = make_video(script, settings, gem, log=status.write)
                    status.update(label="Video ready", state="complete", expanded=False)
                st.session_state.result = {
                    "video": str(result.video), "srt": str(result.srt), "scene": str(result.scene_file),
                    "job": str(result.job_dir), "fallback": result.used_fallback, "duration": result.duration,
                    "overrun": result.overrun,
                }
            except Exception as exc:
                st.error(f"Could not make the video: {exc}")

        res = st.session_state.get("result")
        if res:
            vc, ic = st.columns([1, 1.4])
            with vc:
                st.video(res["video"])
            with ic:
                st.success(f"{res['duration']:.0f}-second short saved to `{res['job']}`")
                if res["fallback"]:
                    st.info("Gemini's animation didn't render, so the template was used. "
                            "Try again, switch the code model to a Pro model, or simplify the animation ideas.")
                if res["overrun"] > 1:
                    st.info(f"The animation runs {res['overrun']:.1f} s past the narration.")
                st.download_button("⬇️ Video (MP4)", Path(res["video"]).read_bytes(), file_name="short.mp4",
                                   mime="video/mp4", use_container_width=True)
                st.download_button("⬇️ Captions (SRT)", Path(res["srt"]).read_bytes(), file_name="captions.srt",
                                   use_container_width=True)
                st.download_button("⬇️ Manim scene (.py)", Path(res["scene"]).read_bytes(), file_name="scene.py",
                                   use_container_width=True)
                st.caption("To change the animation by hand: edit scene.py, then run "
                           "`python make_short.py --rerender <job folder>`.")

# ---------------------------------------------------------------- library
with tab_library:
    jobs = list_jobs()
    if not jobs:
        st.info("Your finished shorts will appear here.")
    cols = st.columns(3)
    for i, j in enumerate(jobs):
        with cols[i % 3]:
            st.video(str(j["dir"] / "final.mp4"))
            st.markdown(f"**{j['title']}**  \n<span class='small-muted'>{j['language']} · {j['duration']:.0f} s · "
                        f"{j['quality']} · {j['created']}</span>", unsafe_allow_html=True)
            st.download_button("Download", (j["dir"] / "final.mp4").read_bytes(), file_name=f"{j['dir'].name}.mp4",
                               key=f"dl{i}", use_container_width=True)
