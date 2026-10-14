"""Step 3: have Gemini write the Manim scene, check it, render it, and repair it on failure."""
from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
from pathlib import Path

from .schema import BEAT_LABELS, Script

ALLOWED_IMPORTS = {"manim", "numpy", "math", "random", "itertools", "functools"}
BANNED_NAMES = {
    "open", "exec", "eval", "compile", "__import__", "input", "globals", "locals", "vars",
    "os", "sys", "subprocess", "shutil", "socket", "requests", "urllib", "pathlib", "importlib",
    "builtins", "setattr", "delattr", "breakpoint", "SVGMobject", "ImageMobject", "Code", "VideoMobject",
}

SYSTEM = """You write Manim Community Edition (v0.19+) Python code for vertical 9:16 maths shorts.

The file you write is appended to a fixed preamble that already provides:
- `from manim import *`, `numpy as np`, `math`, `textwrap`; config with frame 9 units wide x 16 tall (x in [-4.5, 4.5], y in [-8, 8]).
- Colours: BG, INK, MUTED, ACCENT (saffron), TEAL, ROSE, BLUE, GREEN.
- BEAT_STARTS, BEAT_ENDS (seconds, measured from the narration audio), TOTAL, HAS_LATEX.
- beat_len(i); sync_to(self, t) waits until the scene clock reaches t.
- fit(mob, width=SAFE_W) shrinks a mobject to fit the width; para(text, size, color, width) wrapped text;
  headline(text) big bold wrapped text; formula(tex, size, color) MathTex (or plain-text fallback without LaTeX);
  chip(label, color) a small rounded label; add_brand(self); add_progress(self).
- Safe area: content within x in [-3.9, 3.9] and y in [-7.0, 6.6].

Hard rules:
1. Define exactly one scene: `class Short(Scene):` with `def construct(self):`.
2. Start construct with `add_brand(self)` and `add_progress(self)`.
3. There are exactly 4 beats (hook, setup, maths, payoff). Animate beat i, then call `sync_to(self, BEAT_ENDS[i])`.
   The run_times inside beat i must add up to LESS than beat_len(i); compute run_times from beat_len(i), e.g. run_time=0.2*beat_len(1).
4. Between beats, FadeOut only the beat's own VGroup. Never use self.clear(), self.remove(*self.mobjects) or FadeOut(*self.mobjects).
5. Use only manim/numpy/math. No file access, no network, no images, no SVGs, no sounds, no 3D scenes, no `config` changes.
6. Text: use para()/headline()/Text() for words and formula() for maths. Never use Tex()/MathTex() directly unless HAS_LATEX is checked.
   On-screen text is English. Keep every mobject inside the safe area; call fit() on anything wide.
7. Prefer real visuals over text: Axes with plotted graphs, NumberLine, bar charts from Rectangles, DecimalNumber counters driven by
   ValueTracker, arrows, highlights (Indicate, Circumscribe, SurroundingRectangle), TransformMatchingShapes, ReplacementTransform.
   For linear algebra use a NumberPlane (x_range/y_range about [-4, 4], scaled to fit) with Arrow/Vector mobjects and
   ApplyMatrix on a VGroup(plane, vectors); show matrices with Matrix([[...]]) only if HAS_LATEX, else para(). Stay in the
   single Scene class (no LinearTransformationScene, no ThreeDScene).
8. Use current Manim names: Create (not ShowCreation), Text (not TextMobject), MathTex (not TexMobject), Axes(...).plot (not get_graph).
   Axes: pass x_range=[min, max, step], y_range=[...], x_length<=7.6, y_length<=6; axis labels via axes.get_axis_labels or Text.
   DecimalNumber: use num_decimal_places, and update with `.add_updater(lambda m: m.set_value(tracker.get_value()))`.
9. Numbers on screen must match the narration exactly.

Reply with ONE ```python code block containing only the scene code (no preamble), and nothing else."""

EXAMPLE = '''Example of the expected style (one beat only):

```python
class Short(Scene):
    def construct(self):
        add_brand(self)
        add_progress(self)
        # Beat 0: hook
        d = beat_len(0)
        q = headline("Is 3% a month really 36% a year?").move_to(UP * 3)
        big = Text("36%", font_size=140, color=ACCENT, weight=BOLD).move_to(DOWN * 0.5)
        cross = Cross(big, stroke_color=ROSE, stroke_width=10)
        g0 = VGroup(q, big, cross)
        self.play(Write(q), run_time=0.3 * d)
        self.play(FadeIn(big, scale=1.4), run_time=0.2 * d)
        self.play(Create(cross), run_time=0.15 * d)
        sync_to(self, BEAT_ENDS[0] - 0.4)
        self.play(FadeOut(g0), run_time=0.35)
        sync_to(self, BEAT_ENDS[0])
        # Beat 1: setup ... and so on for beats 1, 2 and 3
```'''


def scene_prompt(script: Script, starts: list[float], ends: list[float], has_latex: bool) -> str:
    lines = [f'Title: "{script.title}"', f"Topic: {script.topic}", f"LaTeX installed: {has_latex}", ""]
    for i, b in enumerate(script.beats):
        lines += [
            f"Beat {i} ({BEAT_LABELS.get(b.name, b.name)}): {starts[i]:.2f}s to {ends[i]:.2f}s  (beat_len={ends[i] - starts[i]:.2f}s)",
            f"  Narration (what the viewer hears): {b.narration}",
            f"  Headline: {b.key_text}",
            f"  Formula (LaTeX): {b.formula or '(none)'}",
            f"  Animation to show: {b.on_screen}",
            "",
        ]
    return ("Write the scene for this short. Make each beat visual and in sync with its narration.\n\n"
            + "\n".join(lines) + "\n" + EXAMPLE)


def repair_prompt(code: str, error: str) -> str:
    return (
        "Your Manim scene failed. Fix it and reply with the complete corrected scene code in one ```python block.\n"
        "Keep the same visuals where possible; if a construct keeps failing, replace it with something simpler.\n\n"
        f"Error:\n```\n{error}\n```\n\nCode that failed:\n```python\n{code}\n```"
    )


# -- checking ---------------------------------------------------------------
def extract_code(reply: str) -> str:
    blocks = re.findall(r"```(?:python|py)?\s*\n(.*?)```", reply, flags=re.S)
    code = max(blocks, key=len) if blocks else reply
    # Drop anything that re-declares the preamble.
    code = re.sub(r"^\s*config\.[a-z_]+\s*=.*$", "", code, flags=re.M)
    return code.strip() + "\n"


def check_code(code: str) -> str | None:
    """Return a problem description, or None if the code looks safe and well-formed."""
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return f"SyntaxError: {exc}"
    has_short = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name.split(".")[0] not in ALLOWED_IMPORTS:
                    return f"Import of '{a.name}' is not allowed."
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[0] not in ALLOWED_IMPORTS:
                return f"Import from '{node.module}' is not allowed."
        elif isinstance(node, ast.Name) and node.id in BANNED_NAMES:
            return f"Use of '{node.id}' is not allowed."
        elif isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            return f"Access to '{node.attr}' is not allowed."
        elif isinstance(node, ast.ClassDef) and node.name == "Short":
            has_short = True
    if not has_short:
        return "No `class Short(Scene)` found."
    if "sync_to(" not in code:
        return "The scene never calls sync_to(self, BEAT_ENDS[i]); the picture won't follow the voice."
    return None


# -- rendering ---------------------------------------------------------------
QUALITY = {"draft": ((540, 960), 24), "final": ((1080, 1920), 30)}
_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def clean_log(text: str, lines: int = 45) -> str:
    text = _ANSI.sub("", text)
    text = re.sub(r"[│╭╮╰╯─━┃┏┓┗┛]", "", text)
    rows = [r.rstrip() for r in text.splitlines() if r.strip() and not r.strip().startswith("Manim Community v")]
    return "\n".join(rows[-lines:])


def headline_error(log: str) -> str:
    for row in reversed(log.splitlines()):
        if re.search(r"(Error|Exception|Timeout|took longer)", row):
            return row.strip()
    rows = [r for r in log.splitlines() if r.strip()]
    return rows[-1].strip() if rows else "unknown error"


def render(scene_file: Path, media_dir: Path, quality: str = "draft", timeout: int = 900) -> tuple[bool, Path | None, str]:
    scene_file, media_dir = Path(scene_file).resolve(), Path(media_dir).resolve()
    (w, h), fps = QUALITY[quality]
    cmd = [sys.executable, "-m", "manim", "render", "-r", f"{w},{h}", "--fps", str(fps),
           "--media_dir", str(media_dir), "--disable_caching", "-v", "WARNING", str(scene_file), "Short"]
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "COLUMNS": "100"}
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env,
                              cwd=str(scene_file.parent), encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return False, None, f"Rendering took longer than {timeout} s and was stopped. Simplify the animations."
    videos = sorted(media_dir.rglob("Short.mp4"), key=lambda p: p.stat().st_mtime)
    if proc.returncode == 0 and videos:
        return True, videos[-1], clean_log(proc.stdout + proc.stderr, 15)
    return False, None, clean_log(proc.stdout + "\n" + proc.stderr)
