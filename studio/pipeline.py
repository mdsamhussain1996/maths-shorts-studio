"""Glue: script -> narration -> scene -> render (with repairs) -> final MP4."""
from __future__ import annotations

import json
import os
import re
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import assemble, scene_gen, tts
from .fallback_scene import fallback_code
from .llm import Gemini
from .preamble import build_preamble, latex_available
from .schema import Script

ROOT = Path(__file__).resolve().parent.parent
OUTPUTS = ROOT / "outputs"


@dataclass
class Settings:
    voice: str = "en-IN-NeerjaNeural"
    rate_pct: int = 0
    quality: str = "draft"          # draft (540x960) or final (1080x1920)
    max_attempts: int = 3           # LLM scene attempts before the template fallback
    use_llm_scene: bool = True
    brand: str = "MATHS IN THE WILD"
    tts_engine: str = field(default_factory=lambda: os.environ.get("STUDIO_TTS_ENGINE", "edge"))  # "espeak" = offline test voice


@dataclass
class Result:
    job_dir: Path
    video: Path
    srt: Path
    scene_file: Path
    used_fallback: bool
    duration: float
    overrun: float                  # seconds the animation ran past the narration
    log: list[str] = field(default_factory=list)


def slugify(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return s[:40] or "short"


def new_job_dir(script: Script) -> Path:
    d = OUTPUTS / f"{time.strftime('%Y%m%d-%H%M%S')}-{slugify(script.title or script.topic)}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def make_video(script: Script, settings: Settings, gemini: Gemini | None = None, log=print) -> Result:
    messages: list[str] = []

    def say(msg: str):
        messages.append(msg)
        log(msg)

    job = new_job_dir(script)
    (job / "script.json").write_text(script.model_dump_json(indent=2), encoding="utf-8")

    # 1. Narration, one clip per beat, so we know exactly when each beat starts and ends.
    say(f"Recording narration ({settings.voice})…")
    audio_dir = job / "audio"
    audio_dir.mkdir(exist_ok=True)
    wavs, starts, ends, speech = [], [], [], []
    t = 0.0
    for i, beat in enumerate(script.beats):
        raw = tts.synthesize(beat.narration, settings.voice, audio_dir / f"beat{i}.mp3",
                             settings.rate_pct, settings.tts_engine)
        lead = assemble.LEAD_IN if i == 0 else 0.0
        wav = audio_dir / f"beat{i}.wav"
        d = assemble.to_wav(raw, wav, assemble.TAIL_PAUSE, pad_before=lead)
        wavs.append(wav)
        starts.append(t)
        speech.append(d - assemble.TAIL_PAUSE - lead)
        t += d
        ends.append(t)
        say(f"  beat {i + 1} ({beat.name}): {d:.1f} s")
    narration = job / "narration.wav"
    assemble.concat_wavs(wavs, narration)
    say(f"Narration: {t:.1f} s in total.")

    srt = job / "captions.srt"
    assemble.write_srt([b.narration for b in script.beats],
                       [s + (assemble.LEAD_IN if i == 0 else 0) for i, s in enumerate(starts)], speech, srt)

    # 2. Scene code: Gemini first, template as a safety net.
    has_latex = latex_available()
    preamble = build_preamble(starts, ends, has_latex, settings.brand)
    attempts_dir = job / "attempts"
    attempts_dir.mkdir(exist_ok=True)
    media = job / "media"
    video, used_fallback, final_scene = None, False, None

    if settings.use_llm_scene and gemini is not None:
        prompt = scene_gen.scene_prompt(script, starts, ends, has_latex)
        code = ""
        for attempt in range(1, settings.max_attempts + 1):
            try:
                say(f"Gemini is writing the animation (attempt {attempt}/{settings.max_attempts})…")
                code = scene_gen.extract_code(gemini.code(prompt, scene_gen.SYSTEM))
            except Exception as exc:
                say(f"  Gemini error: {exc}")
                break
            scene_file = attempts_dir / f"scene_attempt{attempt}.py"
            scene_file.write_text(preamble + "\n\n" + code, encoding="utf-8")
            problem = scene_gen.check_code(code)
            if problem:
                say(f"  Rejected before rendering: {problem}")
                prompt = scene_gen.repair_prompt(code, problem)
                continue
            say(f"  Rendering ({settings.quality})…")
            ok, out, msg = scene_gen.render(scene_file, media, settings.quality)
            if ok:
                video, final_scene = out, scene_file
                say("  Rendered.")
                break
            say(f"  Render failed: {scene_gen.headline_error(msg)[:160]}")
            (attempts_dir / f"error_attempt{attempt}.txt").write_text(msg, encoding="utf-8")
            prompt = scene_gen.repair_prompt(code, msg)

    if video is None:
        used_fallback = True
        say("Using the template animation (headline + formula per beat)…")
        scene_file = attempts_dir / "scene_template.py"
        scene_file.write_text(preamble + "\n\n" + fallback_code(script), encoding="utf-8")
        ok, out, msg = scene_gen.render(scene_file, media, settings.quality)
        if not ok:
            raise RuntimeError(f"Even the template scene failed to render:\n{msg}")
        video, final_scene = out, scene_file

    shutil.copy(final_scene, job / "scene.py")

    # 3. Put picture and voice together.
    say("Mixing video and narration…")
    final = job / "final.mp4"
    v_len = assemble.media_duration(video)
    duration = assemble.mux(video, narration, final)
    overrun = max(0.0, v_len - t)
    if overrun > 1.0:
        say(f"Note: the animation runs {overrun:.1f} s longer than the narration; the end is silent.")
    meta = {"title": script.title, "topic": script.topic, "language": script.language,
            "duration": round(duration, 2), "used_fallback": used_fallback, "quality": settings.quality,
            "voice": settings.voice, "created": time.strftime("%Y-%m-%d %H:%M")}
    (job / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    (job / "log.txt").write_text("\n".join(messages), encoding="utf-8")
    say(f"Done: {final}")
    return Result(job, final, srt, job / "scene.py", used_fallback, duration, overrun, messages)


def list_jobs() -> list[dict]:
    jobs = []
    if not OUTPUTS.exists():
        return jobs
    for d in sorted(OUTPUTS.iterdir(), reverse=True):
        meta_f, vid = d / "meta.json", d / "final.mp4"
        if meta_f.exists() and vid.exists():
            meta = json.loads(meta_f.read_text(encoding="utf-8"))
            meta["dir"] = d
            jobs.append(meta)
    return jobs
