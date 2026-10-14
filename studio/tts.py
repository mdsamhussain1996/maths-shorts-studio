"""Step 2: narration with free Microsoft Edge neural voices (edge-tts)."""
from __future__ import annotations

import asyncio
import shutil
import subprocess
from pathlib import Path

import edge_tts

VOICES = {
    "English": {
        "Neerja (Indian English, female)": "en-IN-NeerjaNeural",
        "Prabhat (Indian English, male)": "en-IN-PrabhatNeural",
        "Ava (US English, female)": "en-US-AvaNeural",
        "Ryan (British English, male)": "en-GB-RyanNeural",
    },
    "Hinglish": {
        "Swara (Hindi, female)": "hi-IN-SwaraNeural",
        "Madhur (Hindi, male)": "hi-IN-MadhurNeural",
    },
    "Hindi": {
        "Swara (Hindi, female)": "hi-IN-SwaraNeural",
        "Madhur (Hindi, male)": "hi-IN-MadhurNeural",
    },
}


class TTSError(RuntimeError):
    pass


async def _edge(text: str, voice: str, rate: str, out: Path):
    await edge_tts.Communicate(text, voice, rate=rate).save(str(out))


def synthesize(text: str, voice: str, out_mp3: Path, rate_pct: int = 0, engine: str = "edge") -> Path:
    rate = f"{rate_pct:+d}%"
    out_mp3.parent.mkdir(parents=True, exist_ok=True)
    if engine == "espeak":  # offline, robotic; only used for testing without internet
        if not shutil.which("espeak-ng"):
            raise TTSError("espeak-ng is not installed")
        wav = out_mp3.with_suffix(".espeak.wav")
        subprocess.run(["espeak-ng", "-v", "en-us", "-s", "165", "-w", str(wav), text], check=True)
        return wav
    try:
        asyncio.run(_edge(text, voice, rate, out_mp3))
    except Exception as exc:
        raise TTSError(
            "Couldn't record the voice. The free voices need an internet connection; check it and try again. "
            f"(Details: {exc})"
        ) from exc
    if not out_mp3.exists() or out_mp3.stat().st_size == 0:
        raise TTSError("Voice synthesis produced an empty file. Try again, or pick another voice.")
    return out_mp3
