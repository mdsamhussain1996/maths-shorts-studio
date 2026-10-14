"""Command-line version of the studio.

  python make_short.py "FASTag: how toll is calculated" --lang English --seconds 60
  python make_short.py --demo                       # no API key needed
  python make_short.py --rerender outputs/<job>     # after editing <job>/scene.py by hand
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from studio import assemble, scene_gen
from studio.config import load_env_key
from studio.demo import DEMO_SCRIPT, DemoGemini
from studio.llm import Gemini
from studio.pipeline import Settings, make_video
from studio.research import fact_check, make_script
from studio.tts import VOICES


def rerender(job: Path, quality: str):
    scene = job / "scene.py"
    if not scene.exists():
        sys.exit(f"No scene.py in {job}")
    print("Rendering", scene)
    ok, video, msg = scene_gen.render(scene, job / "media", quality)
    if not ok:
        sys.exit(msg)
    out = job / "final.mp4"
    assemble.mux(video, job / "narration.wav", out)
    print("Done:", out)


def main():
    ap = argparse.ArgumentParser(description="Make a narrated maths short from a topic.")
    ap.add_argument("topic", nargs="?")
    ap.add_argument("--lang", default="English", choices=list(VOICES))
    ap.add_argument("--voice", help="edge-tts voice id, e.g. en-IN-PrabhatNeural")
    ap.add_argument("--seconds", type=int, default=60)
    ap.add_argument("--level", default="college students")
    ap.add_argument("--quality", default="draft", choices=["draft", "final"])
    ap.add_argument("--model", default="gemini-3.5-flash")
    ap.add_argument("--code-model")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--rerender", type=Path, metavar="JOB_DIR")
    a = ap.parse_args()

    if a.rerender:
        return rerender(a.rerender, a.quality)
    voice = a.voice or next(iter(VOICES[a.lang].values()))
    settings = Settings(voice=voice, quality=a.quality)
    if a.demo:
        return make_video(DEMO_SCRIPT, settings, DemoGemini())
    if not a.topic:
        ap.error("give a topic, or use --demo")
    g = Gemini(load_env_key(), a.model, a.code_model)
    script = make_script(g, a.topic, a.lang, a.seconds, a.level)
    script, _ = fact_check(g, script)
    print("\nNumbers to verify:\n" + "\n".join(f"  - {n}" for n in script.numbers_to_verify))
    make_video(script, settings, g)


if __name__ == "__main__":
    main()
