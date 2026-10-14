"""A ready-made script and scene so the studio can be tried without an API key."""
from __future__ import annotations

from .schema import Beat, Script

DEMO_SCRIPT = Script(
    topic="UPI pay-later: is 3% a month really 36% a year?",
    title="3% a month is NOT 36% a year",
    language="English",
    seconds=60,
    beats=[
        Beat(name="hook",
             narration="Your app says pay later at just three percent a month. Sounds like thirty six percent a year, right? It's actually more.",
             key_text="3% a month = 36% a year?",
             formula="",
             on_screen="Big 36% appears, gets crossed out in red."),
        Beat(name="setup",
             narration="Say you buy a ten thousand rupee phone on pay later and don't pay anything back. Every month, three percent is added to whatever you owe, including last month's interest.",
             key_text="₹10,000 phone, nothing repaid",
             formula="",
             on_screen="A price tag of 10,000 rupees, with a '+3% every month' chip looping back onto it."),
        Beat(name="maths",
             narration="After one month you owe ten thousand three hundred. After two, ten thousand six hundred and nine. Each month multiplies by one point zero three. Twelve months means one point zero three to the power twelve, which is one point four two six. So the yearly rate is forty two point six percent, not thirty six.",
             key_text="Interest on interest",
             formula=r"(1.03)^{12} = 1.426",
             on_screen="Axes over 12 months: a straight 36% line vs a curving compound line; a counter climbs to 14,258."),
        Beat(name="payoff",
             narration="Monthly rates hide compounding. Before you tap pay later, convert to a yearly rate. Three percent a month is really forty two point six percent a year.",
             key_text="3% a month = 42.6% a year",
             formula=r"(1+r)^{12}-1",
             on_screen="Big 42.6% in teal with the general formula under it."),
    ],
    numbers_to_verify=[
        "(1.03)^12 = 1.42576, so the effective annual rate is 42.6% (check: 10,000 × 1.42576 = 14,257.6)",
        "Simple (non-compounded) rate: 3% × 12 = 36%",
    ],
    description="Why 3% a month on pay-later is really 42.6% a year. #MathsInTheWild #UPI #compoundinterest #finance",
    sources=[],
)

# What a good Gemini-written scene for the demo looks like. Used by demo mode to exercise
# the same check -> render path as a real run.
DEMO_SCENE = r'''```python
class Short(Scene):
    def construct(self):
        add_brand(self)
        add_progress(self)

        # Beat 0: hook
        d = beat_len(0)
        q = headline("3% a month = 36% a year?").move_to(UP * 3.6)
        big = Text("36%", font_size=150, color=ACCENT, weight=BOLD).move_to(DOWN * 0.3)
        cross = Cross(big, stroke_color=ROSE, stroke_width=12)
        g0 = VGroup(q, big, cross)
        self.play(Write(q), run_time=0.22 * d)
        self.play(FadeIn(big, scale=1.5), run_time=0.15 * d)
        sync_to(self, BEAT_ENDS[0] - 0.25 * d)
        self.play(Create(cross), run_time=0.12 * d)
        sync_to(self, BEAT_ENDS[0] - 0.4)
        self.play(FadeOut(g0), run_time=0.35)
        sync_to(self, BEAT_ENDS[0])

        # Beat 1: setup
        d = beat_len(1)
        label = chip("SETUP", BLUE).move_to(UP * 5.7)
        tag = RoundedRectangle(corner_radius=0.3, width=6.2, height=2.4, stroke_color=INK, stroke_width=4)
        price = fit(Text("₹10,000", font_size=96, color=INK, weight=BOLD), width=5.4).move_to(tag)
        tagg = VGroup(tag, price).move_to(UP * 1.8)
        note = para("Phone on pay-later. Nothing repaid.", size=38, color=MUTED, width=22).next_to(tagg, DOWN, buff=0.5)
        plus = chip("+3% every month", ACCENT).move_to(DOWN * 3.2)
        loop = CurvedArrow(plus.get_right() + RIGHT * 0.2, tagg.get_right() + DOWN * 0.3, angle=TAU / 4, color=ACCENT)
        g1 = VGroup(label, tagg, note, plus, loop)
        self.play(FadeIn(label, shift=DOWN * 0.3), run_time=0.06 * d)
        self.play(Create(tag), Write(price), run_time=0.18 * d)
        self.play(FadeIn(note), run_time=0.1 * d)
        self.play(FadeIn(plus, shift=UP * 0.3), run_time=0.1 * d)
        self.play(Create(loop), run_time=0.15 * d)
        self.play(Indicate(price, color=ACCENT), run_time=0.12 * d)
        sync_to(self, BEAT_ENDS[1] - 0.4)
        self.play(FadeOut(g1), run_time=0.35)
        sync_to(self, BEAT_ENDS[1])

        # Beat 2: the maths
        d = beat_len(2)
        label = chip("THE MATHS", ACCENT).move_to(UP * 5.7)
        axes = Axes(x_range=[0, 12, 3], y_range=[10000, 15000, 1000], x_length=7.0, y_length=5.2,
                    axis_config={"color": MUTED, "include_numbers": False}, tips=False).move_to(UP * 1.6)
        xl = Text("months", font_size=24, color=MUTED).next_to(axes.x_axis, DOWN, buff=0.25)
        simple = axes.plot(lambda m: 10000 * (1 + 0.03 * m), x_range=[0, 12], color=BLUE, stroke_width=5)
        comp = axes.plot(lambda m: 10000 * 1.03 ** m, x_range=[0, 12], color=ACCENT, stroke_width=6)
        s_lab = Text("36% simple", font_size=26, color=BLUE).next_to(axes.c2p(12, 13600), DOWN + LEFT * 0.2, buff=0.15)
        c_lab = Text("compound", font_size=26, color=ACCENT).next_to(axes.c2p(12, 14258), UP + LEFT * 0.2, buff=0.15)
        months = ValueTracker(0)
        owed = DecimalNumber(10000, num_decimal_places=0, group_with_commas=True, font_size=72, color=INK)
        owed.add_updater(lambda m: m.set_value(10000 * 1.03 ** months.get_value()))
        rs = Text("₹", font_size=64, color=INK)
        counter = VGroup(rs, owed).arrange(RIGHT, buff=0.15).move_to(DOWN * 2.2)
        rs.add_updater(lambda m: m.next_to(owed, LEFT, buff=0.15))
        eq = formula(r"(1.03)^{12} = 1.426", size=76, color=ACCENT).move_to(DOWN * 4.3)
        rate = Text("→ 42.6% a year", font_size=48, color=TEAL, weight=BOLD).next_to(eq, DOWN, buff=0.45)
        g2 = VGroup(label, axes, xl, simple, comp, s_lab, c_lab, counter, eq, rate)
        self.play(FadeIn(label, shift=DOWN * 0.3), Create(axes), FadeIn(xl), run_time=0.08 * d)
        self.add(counter)
        self.play(Create(simple), FadeIn(s_lab), run_time=0.1 * d)
        self.play(Create(comp), months.animate.set_value(12), run_time=0.32 * d, rate_func=linear)
        self.play(FadeIn(c_lab), run_time=0.04 * d)
        self.play(Write(eq), run_time=0.14 * d)
        self.play(FadeIn(rate, shift=UP * 0.2), Circumscribe(eq, color=TEAL), run_time=0.12 * d)
        sync_to(self, BEAT_ENDS[2] - 0.4)
        owed.clear_updaters()
        rs.clear_updaters()
        self.play(FadeOut(g2), run_time=0.35)
        sync_to(self, BEAT_ENDS[2])

        # Beat 3: payoff
        d = beat_len(3)
        label = chip("PAYOFF", TEAL).move_to(UP * 5.7)
        top = headline("3% a month is really").move_to(UP * 3.2)
        big = Text("42.6%", font_size=150, color=TEAL, weight=BOLD).move_to(UP * 0.6)
        yr = Text("a year", font_size=56, color=INK).next_to(big, DOWN, buff=0.3)
        gen = formula(r"(1+r)^{12}-1", size=72, color=ACCENT).move_to(DOWN * 3.2)
        tip = para("Convert monthly rates to yearly before you tap pay-later.", size=34, color=MUTED, width=26).move_to(DOWN * 5.2)
        self.play(FadeIn(label, shift=DOWN * 0.3), Write(top), run_time=0.15 * d)
        self.play(GrowFromCenter(big), FadeIn(yr), run_time=0.15 * d)
        self.play(Write(gen), run_time=0.15 * d)
        self.play(FadeIn(tip), run_time=0.1 * d)
        sync_to(self, BEAT_ENDS[3])
```'''


class DemoGemini:
    """Stands in for Gemini in demo mode: returns the ready-made scene."""
    code_model = model = "demo"

    def code(self, prompt: str, system: str) -> str:
        return DEMO_SCENE
