"""The fixed header every generated Manim scene is rendered with.

It sets up the vertical 9:16 frame, the palette, the beat timings measured from the
narration, and a few helpers. Both the LLM-written scene and the template fallback use it.
"""
from __future__ import annotations

import shutil

PALETTE = {
    "BG": "#0E1116",
    "INK": "#F3EFE6",
    "MUTED": "#8B93A1",
    "ACCENT": "#FFB547",   # saffron
    "TEAL": "#3DD6C6",
    "ROSE": "#FF6B6B",
    "BLUE": "#6CA8FF",
    "GREEN": "#7BD88F",
}


def latex_available() -> bool:
    return bool(shutil.which("latex") and shutil.which("dvisvgm"))


def build_preamble(starts: list[float], ends: list[float], has_latex: bool, brand: str = "MATHS IN THE WILD") -> str:
    colours = "\n".join(f'{k} = "{v}"' for k, v in PALETTE.items())
    return f'''# ---- Maths Shorts Studio preamble (auto-generated) -------------------------
from manim import *
import numpy as np
import math
import textwrap

config.frame_width = 9
config.frame_height = 16
config.background_color = "{PALETTE["BG"]}"

BEAT_STARTS = {[round(s, 3) for s in starts]!r}
BEAT_ENDS = {[round(e, 3) for e in ends]!r}
TOTAL = {round(ends[-1], 3)!r}
HAS_LATEX = {has_latex!r}
BRAND = {brand!r}

{colours}
def _pick_font():
    try:
        import manimpango
        installed = set(manimpango.list_fonts())
    except Exception:
        return None
    for name in ("Inter", "Poppins", "Montserrat", "Segoe UI", "Helvetica Neue", "Arial", "DejaVu Sans", "Liberation Sans"):
        if name in installed:
            return name
    return None


FONT = _pick_font()
if FONT:
    Text.set_default(font=FONT)

SAFE_W = 7.8          # keep content inside x in [-3.9, 3.9]
SAFE_TOP = 6.6        # keep content below y = 6.6 (brand line sits above)
SAFE_BOTTOM = -7.0    # keep content above y = -7.0 (progress bar sits below)


def beat_len(i):
    return BEAT_ENDS[i] - BEAT_STARTS[i]


def sync_to(scene, t):
    """Wait until the scene clock reaches t seconds (end of a beat). Keeps picture and voice in step."""
    remaining = t - scene.renderer.time
    if remaining > 1e-3:
        scene.wait(remaining)


def fit(mob, width=SAFE_W, height=None):
    if mob.width > width:
        mob.scale_to_fit_width(width)
    if height is not None and mob.height > height:
        mob.scale_to_fit_height(height)
    return mob


def para(text, size=42, color=INK, width=24, **kwargs):
    """Wrapped multi-line text that always fits the phone width."""
    lines = textwrap.wrap(str(text), width) or [" "]
    return fit(Text("\\n".join(lines), font_size=size, color=color, line_spacing=0.85, **kwargs))


def headline(text, size=62, color=INK):
    return para(text, size=size, color=color, width=16, weight=BOLD)


def formula(tex, size=80, color=INK):
    """MathTex when LaTeX is installed, readable plain text otherwise."""
    if HAS_LATEX:
        try:
            return fit(MathTex(tex, font_size=size, color=color))
        except Exception:
            pass
    plain = tex.replace("\\\\times", "×").replace("\\\\cdot", "·").replace("\\\\%", "%")
    for a in ("\\\\left", "\\\\right", "\\\\frac", "\\\\text", "\\\\mathrm", "\\\\", "{{", "}}"):
        plain = plain.replace(a, "")
    return para(plain, size=size - 10, color=color, width=22)


def chip(label, color=ACCENT):
    t = Text(label, font_size=26, color=BG, weight=BOLD)
    box = RoundedRectangle(corner_radius=0.18, width=t.width + 0.6, height=t.height + 0.32,
                           fill_color=color, fill_opacity=1, stroke_width=0)
    t.move_to(box)
    return VGroup(box, t)


def add_brand(scene):
    tag = Text(BRAND, font_size=22, color=MUTED, weight=BOLD).move_to(UP * 7.35)
    scene.add(tag)
    return tag


def add_progress(scene):
    """Thin progress bar along the bottom that fills over the whole video."""
    track = Rectangle(width=8.2, height=0.08, fill_color=MUTED, fill_opacity=0.25, stroke_width=0).move_to(DOWN * 7.55)
    clock = ValueTracker(0)
    clock.add_updater(lambda v, dt: v.increment_value(dt))
    left = track.get_left()

    def bar():
        w = max(8.2 * min(clock.get_value() / TOTAL, 1.0), 0.01)
        return Rectangle(width=w, height=0.08, fill_color=ACCENT, fill_opacity=1, stroke_width=0).move_to(left + RIGHT * w / 2)

    scene.add(track, clock, always_redraw(bar))
    return track
# ---- end of preamble ---------------------------------------------------------
'''
