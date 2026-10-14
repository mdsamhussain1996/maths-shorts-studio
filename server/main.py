"""Maths Shorts Studio website: FastAPI backend around the studio/ pipeline.

Run:  uvicorn server.main:app --port 8000      (or use run_website_*.bat / .sh)
"""
from __future__ import annotations

import asyncio
import json
import re
import threading
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from studio.config import ROOT, load_env_key
from studio.demo import DEMO_SCRIPT, DemoGemini
from studio.llm import Gemini, GeminiError
from studio.pipeline import OUTPUTS, Settings, list_jobs, make_video
from studio.preamble import latex_available
from studio.research import WORDS_PER_SEC, fact_check, make_script
from studio.schema import Script
from studio.tts import VOICES, TTSError

DEFAULT_MODEL = "gemini-3.5-flash"
TOPIC_IDEAS = [
    "Eigenvalues",
    "Derivative",
    "Bayes' theorem",
    "Pythagoras theorem",
    "FASTag: how toll is calculated per km",
    "SIP: why ₹5,000 a month becomes crores",
    "DLS method in cricket",
    "No-cost EMI: where the interest hides",
]
ALLOWED_FILES = {"final.mp4": "video/mp4", "captions.srt": "text/plain", "scene.py": "text/x-python",
                 "script.json": "application/json"}

app = FastAPI(title="Maths Shorts Studio")

# One render at a time (Manim is CPU heavy); script writing runs separately.
render_pool = ThreadPoolExecutor(max_workers=1)
JOBS: dict[str, dict] = {}
QUEUE: list[str] = []
LOCK = threading.Lock()


def friendly(exc: Exception) -> str:
    msg = str(exc)
    if isinstance(exc, (TTSError, GeminiError)):
        if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
            return "Gemini's free quota is used up for now. Wait a minute (or until tomorrow for daily limits) and try again."
        if "API key not valid" in msg or "API_KEY_INVALID" in msg or "PERMISSION_DENIED" in msg:
            return "Gemini rejected the API key. Check it under Settings."
        return msg
    return f"Something went wrong: {msg}"


# ------------------------------------------------------------------ config
@app.get("/api/config")
def config():
    return {
        "languages": list(VOICES),
        "voices": VOICES,
        "words_per_sec": WORDS_PER_SEC,
        "latex": latex_available(),
        "has_key": bool(load_env_key()),
        "default_model": DEFAULT_MODEL,
        "topic_ideas": TOPIC_IDEAS,
    }


class KeyIn(BaseModel):
    key: str


@app.post("/api/key")
def save_key(body: KeyIn):
    """Save the Gemini key to .env on this computer. The key is never sent back to the browser."""
    key = body.key.strip()
    if not re.fullmatch(r"[A-Za-z0-9_\-]{20,100}", key):
        raise HTTPException(400, "That doesn't look like a Gemini API key.")
    env = ROOT / ".env"
    lines = env.read_text(encoding="utf-8").splitlines() if env.exists() else []
    lines = [l for l in lines if not l.strip().startswith("GEMINI_API_KEY")] + [f"GEMINI_API_KEY={key}"]
    env.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"has_key": True}


# ------------------------------------------------------------------ script
class ScriptIn(BaseModel):
    topic: str = ""
    language: str = "English"
    seconds: int = 60
    level: str = "college students"
    model: str = DEFAULT_MODEL
    demo: bool = False


@app.post("/api/script")
async def write_script(body: ScriptIn):
    if body.demo:
        return DEMO_SCRIPT.model_dump()
    if not body.topic.strip():
        raise HTTPException(400, "Please enter a topic.")
    if body.language not in VOICES:
        raise HTTPException(400, "Unknown language.")
    key = load_env_key()
    if not key:
        raise HTTPException(400, "No Gemini API key yet. Add it under Settings, or switch on Demo mode.")
    try:
        g = Gemini(key, body.model or DEFAULT_MODEL)
        script = await run_in_threadpool(make_script, g, body.topic.strip(), body.language,
                                         max(30, min(body.seconds, 120)), body.level, lambda m: None)
    except Exception as exc:
        raise HTTPException(502, friendly(exc))
    return script.model_dump()


# ------------------------------------------------------------------ videos
class VideoIn(BaseModel):
    script: Script
    voice: str = "en-IN-NeerjaNeural"
    rate_pct: int = Field(0, ge=-30, le=30)
    quality: str = "draft"
    max_attempts: int = Field(3, ge=1, le=5)
    use_llm_scene: bool = True
    brand: str = "MATHS IN THE WILD"
    model: str = DEFAULT_MODEL
    code_model: str = DEFAULT_MODEL
    demo: bool = False


class AutoIn(BaseModel):
    """One-click mode: just a topic; research, script, fact-check and video all happen in one job."""
    topic: str = ""
    language: str = "English"
    seconds: int = 60
    level: str = "college students"
    voice: str = "en-IN-NeerjaNeural"
    rate_pct: int = Field(0, ge=-30, le=30)
    quality: str = "draft"
    max_attempts: int = Field(3, ge=1, le=5)
    use_llm_scene: bool = True
    brand: str = "MATHS IN THE WILD"
    model: str = DEFAULT_MODEL
    code_model: str = DEFAULT_MODEL
    demo: bool = False


def _run_auto(job_id: str, body: AutoIn):
    job = JOBS[job_id]
    with LOCK:
        if job_id in QUEUE:
            QUEUE.remove(job_id)
    job["status"] = "running"
    log = job["logs"].append
    try:
        if body.demo:
            log("Demo mode: using the ready-made UPI pay-later script.")
            script, issues = DEMO_SCRIPT, []
        else:
            key = load_env_key()
            if not key:
                raise GeminiError("No Gemini API key yet. Add it under Settings, or switch on Demo mode.")
            g = Gemini(key, body.model or DEFAULT_MODEL, body.code_model or DEFAULT_MODEL)
            lang = body.language if body.language in VOICES else "English"
            script = make_script(g, body.topic.strip(), lang, max(30, min(body.seconds, 120)), body.level, log=log)
            log(f"Script ready: \"{script.title}\"")
            script, issues = fact_check(g, script, log=log)
        job["script"] = script.model_dump()
        job["issues"] = issues
        video_body = VideoIn(script=script, **body.model_dump(exclude={"topic", "language", "seconds", "level"}))
        _run_job(job_id, video_body, already_started=True)
    except Exception as exc:
        job["error"] = friendly(exc)
        job["logs"].append(traceback.format_exc(limit=2))
        job["status"] = "error"


@app.post("/api/auto")
def start_auto(body: AutoIn):
    if not body.demo and not body.topic.strip():
        raise HTTPException(400, "Please enter a topic.")
    if not body.demo and not load_env_key():
        raise HTTPException(400, "No Gemini API key yet. Add it under Settings (⚙), or switch on Demo mode.")
    job_id = uuid.uuid4().hex[:12]
    JOBS[job_id] = {"status": "queued", "logs": [], "result": None, "error": None}
    with LOCK:
        QUEUE.append(job_id)
    render_pool.submit(_run_auto, job_id, body)
    return {"job_id": job_id}


def _run_job(job_id: str, body: VideoIn, already_started: bool = False):
    job = JOBS[job_id]
    if not already_started:
        with LOCK:
            if job_id in QUEUE:
                QUEUE.remove(job_id)
        job["status"] = "running"

    def log(msg: str):
        job["logs"].append(msg)

    try:
        all_voices = {v for group in VOICES.values() for v in group.values()}
        voice = body.voice if body.voice in all_voices else "en-IN-NeerjaNeural"
        settings = Settings(voice=voice, rate_pct=body.rate_pct,
                            quality=body.quality if body.quality in ("draft", "final") else "draft",
                            max_attempts=body.max_attempts, use_llm_scene=body.use_llm_scene,
                            brand=body.brand[:40] or "MATHS IN THE WILD")
        if body.demo:
            gem = DemoGemini()
        else:
            key = load_env_key()
            gem = Gemini(key, body.model or DEFAULT_MODEL, body.code_model or DEFAULT_MODEL) if key else None
            if gem is None and body.use_llm_scene:
                log("No Gemini key, so the template animation will be used.")
        res = make_video(body.script, settings, gem, log=log)
        job["result"] = {
            "name": res.job_dir.name, "title": body.script.title, "duration": round(res.duration, 1),
            "used_fallback": res.used_fallback, "overrun": round(res.overrun, 1),
            "description": body.script.description,
            "script": job.get("script") or body.script.model_dump(),
            "issues": job.get("issues", []),
        }
        job["status"] = "done"
    except Exception as exc:
        job["error"] = friendly(exc)
        job["logs"].append(traceback.format_exc(limit=2))
        job["status"] = "error"


@app.post("/api/videos")
def start_video(body: VideoIn):
    if len(body.script.beats) != 4 or any(not b.narration.strip() for b in body.script.beats):
        raise HTTPException(400, "The script needs four beats, each with narration.")
    job_id = uuid.uuid4().hex[:12]
    JOBS[job_id] = {"status": "queued", "logs": [], "result": None, "error": None}
    with LOCK:
        QUEUE.append(job_id)
    render_pool.submit(_run_job, job_id, body)
    return {"job_id": job_id}


@app.get("/api/videos/{job_id}/events")
async def job_events(job_id: str):
    if job_id not in JOBS:
        raise HTTPException(404, "Unknown job.")

    async def stream():
        sent = 0
        last_pos = None
        while True:
            job = JOBS[job_id]
            if job["status"] == "queued":
                pos = QUEUE.index(job_id) if job_id in QUEUE else 0
                if pos != last_pos:
                    last_pos = pos
                    yield f"event: queued\ndata: {json.dumps({'ahead': pos})}\n\n"
            logs = job["logs"]
            while sent < len(logs):
                yield f"event: log\ndata: {json.dumps(logs[sent])}\n\n"
                sent += 1
            if job["status"] == "done":
                yield f"event: done\ndata: {json.dumps(job['result'])}\n\n"
                return
            if job["status"] == "error":
                yield f"event: failed\ndata: {json.dumps(job['error'])}\n\n"
                return
            await asyncio.sleep(0.5)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/videos")
def library():
    return [{**{k: v for k, v in j.items() if k != "dir"}, "name": j["dir"].name} for j in list_jobs()]


@app.get("/api/videos/{name}/files/{filename}")
def get_file(name: str, filename: str, download: bool = False):
    if not re.fullmatch(r"[A-Za-z0-9\-]+", name) or filename not in ALLOWED_FILES:
        raise HTTPException(404, "Not found.")
    path = OUTPUTS / name / filename
    if not path.is_file():
        raise HTTPException(404, "Not found.")
    kwargs = {"filename": f"{name}-{filename}"} if download else {}
    return FileResponse(path, media_type=ALLOWED_FILES[filename], **kwargs)


@app.exception_handler(Exception)
async def unhandled(request, exc):
    return JSONResponse({"detail": friendly(exc)}, status_code=500)


# ------------------------------------------------------------------ site
app.mount("/", StaticFiles(directory=ROOT / "web", html=True), name="web")
