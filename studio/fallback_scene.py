"""A deterministic template scene used when the LLM-written scene can't be rendered."""
from __future__ import annotations

import json

from .schema import BEAT_LABELS, Script

TEMPLATE = '''

BEATS = json.loads({beats_json!r})
LABEL_COLOURS = [ROSE, BLUE, ACCENT, TEAL]


class Short(Scene):
    def construct(self):
        add_brand(self)
        add_progress(self)
        last = len(BEATS) - 1
        for i, b in enumerate(BEATS):
            dur = beat_len(i)
            label = chip(b["label"], LABEL_COLOURS[i % 4]).move_to(UP * 4.6)
            head = headline(b["key_text"], size=70).next_to(label, DOWN, buff=0.7)
            group = VGroup(label, head)
            self.play(FadeIn(label, shift=DOWN * 0.3), run_time=min(0.5, dur * 0.1))
            self.play(Write(head), run_time=min(1.4, dur * 0.22))
            if b["formula"].strip():
                eq = formula(b["formula"], size=100 if i == 2 else 84, color=ACCENT if i == 2 else INK)
                eq.move_to(DOWN * 1.2)
                box = SurroundingRectangle(eq, color=ACCENT, buff=0.35, corner_radius=0.15, stroke_width=3)
                group.add(eq, box)
                self.play(Write(eq), run_time=min(2.2, dur * 0.3))
                self.play(Create(box), run_time=min(0.8, dur * 0.1))
            else:
                line = Line(LEFT * 2.5, RIGHT * 2.5, color=ACCENT, stroke_width=6).next_to(head, DOWN, buff=0.5)
                group.add(line)
                self.play(GrowFromCenter(line), run_time=min(0.6, dur * 0.1))
            if i < last:
                sync_to(self, BEAT_ENDS[i] - 0.45)
                self.play(FadeOut(group, shift=UP * 0.4), run_time=0.4)
            sync_to(self, BEAT_ENDS[i])
'''


def fallback_code(script: Script) -> str:
    beats = [
        {"label": BEAT_LABELS.get(b.name, b.name.upper()), "key_text": b.key_text, "formula": b.formula}
        for b in script.beats
    ]
    return "import json" + TEMPLATE.format(beats_json=json.dumps(beats))
