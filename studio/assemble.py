"""Audio timing, captions and final muxing with ffmpeg."""
from __future__ import annotations

import re
import subprocess
import textwrap
import wave
from pathlib import Path

import imageio_ffmpeg

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
TAIL_PAUSE = 0.35  # seconds of silence after each beat
LEAD_IN = 0.25     # silence before the first word


def _run(args: list[str]):
    proc = subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", *args],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {proc.stderr[-1500:]}")


def to_wav(src: Path, dst: Path, pad_after: float, pad_before: float = 0.0) -> float:
    """Convert to 48 kHz mono WAV with silence padding. Returns duration in seconds."""
    filters = []
    if pad_before > 0:
        filters.append(f"adelay={int(pad_before * 1000)}:all=1")
    filters.append(f"apad=pad_dur={pad_after}")
    _run(["-i", str(src), "-af", ",".join(filters), "-ar", "48000", "-ac", "1", str(dst)])
    return wav_duration(dst)


def wav_duration(path: Path) -> float:
    with wave.open(str(path)) as w:
        return w.getnframes() / float(w.getframerate())


def concat_wavs(parts: list[Path], dst: Path):
    inputs = []
    for p in parts:
        inputs += ["-i", str(p)]
    n = len(parts)
    _run([*inputs, "-filter_complex", "".join(f"[{i}:a]" for i in range(n)) + f"concat=n={n}:v=0:a=1[a]",
          "-map", "[a]", "-ar", "48000", "-ac", "1", str(dst)])


def media_duration(path: Path) -> float:
    proc = subprocess.run([FFMPEG, "-hide_banner", "-i", str(path)], capture_output=True, text=True)
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", proc.stderr)
    if not m:
        raise RuntimeError(f"Could not read duration of {path}")
    h, mnt, s = m.groups()
    return int(h) * 3600 + int(mnt) * 60 + float(s)


def mux(video: Path, audio: Path, dst: Path) -> float:
    """Combine video and narration; whichever is shorter is padded (last frame held / silence)."""
    v, a = media_duration(video), media_duration(audio)
    total = max(v, a) + 0.4
    vpad = max(0.0, total - v)
    _run([
        "-i", str(video), "-i", str(audio),
        "-filter_complex", f"[0:v]tpad=stop_mode=clone:stop_duration={vpad:.3f},format=yuv420p[v];"
                           f"[1:a]apad=whole_dur={total:.3f}[a]",
        "-map", "[v]", "-map", "[a]", "-t", f"{total:.3f}",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-c:a", "aac", "-b:a", "160k",
        "-movflags", "+faststart", str(dst),
    ])
    return total


# -- captions -------------------------------------------------------------
def _ts(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_srt(beats_text: list[str], starts: list[float], speech_lens: list[float], dst: Path):
    """Split each beat's narration into short caption lines, timed in proportion to their length."""
    out, idx = [], 1
    for text, start, length in zip(beats_text, starts, speech_lens):
        chunks = textwrap.wrap(" ".join(text.split()), 42) or [""]
        total_chars = sum(len(c) for c in chunks) or 1
        t = start
        for c in chunks:
            d = length * len(c) / total_chars
            out.append(f"{idx}\n{_ts(t)} --> {_ts(t + d)}\n{c}\n")
            idx += 1
            t += d
    dst.write_text("\n".join(out), encoding="utf-8")
