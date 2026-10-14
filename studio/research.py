"""Step 1: research a topic and write a 4-beat short script."""
from __future__ import annotations

from .llm import Gemini
from .schema import BEAT_NAMES, Script, ScriptDraft

# Rough speaking rates for the neural voices (words per second).
WORDS_PER_SEC = {"English": 2.5, "Hinglish": 2.4, "Hindi": 2.3}

# Share of the video each beat gets.
BEAT_SHARE = {"hook": 0.13, "setup": 0.25, "maths": 0.42, "payoff": 0.20}

LANGUAGE_RULES = {
    "English": "Write the narration in simple, conversational Indian English.",
    "Hinglish": (
        "Write the narration in natural Hinglish as spoken by Indian college students. "
        "Write Hindi words in Devanagari script and keep English technical words (percent, interest, graph, formula, etc.) "
        "in Latin script, e.g. 'सोचो, हर महीने सिर्फ 3 percent interest...'. A Hindi voice will read it aloud."
    ),
    "Hindi": (
        "Write the narration in simple spoken Hindi in Devanagari script (not shuddh/formal Hindi). "
        "Common English words students use (percent, EMI, graph) may stay as they are. A Hindi voice will read it aloud."
    ),
}


def research_prompt(topic: str, level: str) -> str:
    return f"""You are the research assistant for "Maths in the Wild", 60-second vertical maths videos for Indian {level} audiences.

Topic: {topic}

The topic may be an everyday situation (e.g. "UPI pay-later interest") or a pure maths concept (e.g. "eigenvalue",
"derivative", "Bayes' theorem"). Using reliable web sources, collect:
1. The intuition: what the idea really means, in one or two plain sentences a student would remember.
2. The exact mathematics: the definition, the key formula(s), and ONE small fully worked numerical example
   (e.g. a 2×2 matrix, a simple function) with every step computed correctly. Keep numbers small and clean.
3. Where it shows up in real life, preferably something Indian viewers know (cricket, UPI, trains, exams, Google
   search, phone cameras, bridges...). For an everyday topic, give real current figures with date and source;
   prefer official sources (RBI, NPCI, SEBI, government, ICC/BCCI, railway/airline sites).
4. The most common misconception or "surprise" a viewer would not expect.
5. One concrete visual idea for each of: a hook, the setup, the maths, the payoff (for a concept: how to SHOW it
   geometrically, e.g. vectors that only stretch, a tangent line sliding along a curve).

Double-check the arithmetic of the worked example. Be concise and factual; bullet points are fine."""


def script_prompt(topic: str, notes: str, language: str, seconds: int, level: str) -> str:
    wps = WORDS_PER_SEC.get(language, 2.5)
    budgets = "\n".join(
        f"- {name}: about {round(seconds * BEAT_SHARE[name])} s, at most {int(seconds * BEAT_SHARE[name] * wps)} words"
        for name in BEAT_NAMES
    )
    return f"""Write the script for a {seconds}-second vertical maths short (YouTube Shorts / Instagram Reels) for Indian {level} audiences.

Topic: {topic}

Research notes (use only facts that appear here; do not invent figures):
<<<
{notes}
>>>

Structure: exactly four beats, in this order, with these names and word budgets:
{budgets}

- hook: a surprising question or claim that makes people stop scrolling (from everyday Indian life, or a striking fact about the idea).
- setup: the situation (or the intuition, for a pure concept) and the numbers we will work with.
- maths: the actual maths, step by step, with the key formula; the numbers must be computed correctly.
- payoff: the takeaway the viewer can use, ending with a punchy line.

Language: {LANGUAGE_RULES.get(language, LANGUAGE_RULES['English'])}
On-screen text (key_text, formula, on_screen) must always be in English and maths notation.

For each beat:
- narration: exactly what the voice says (no stage directions, no emojis, no markdown).
- key_text: the big on-screen headline, at most 8 words.
- formula: one LaTeX formula shown in this beat (without $ signs), or "" if none. Keep it short enough to fit a phone screen.
- on_screen: a concrete description of the animation: which objects, graphs, number lines, bars, counters, and how they move.

numbers_to_verify: list every factual number or claim (rates, rules, prices, dates) so a teacher can check it.
description: 2-3 lines for the video description, with 3-5 hashtags."""


def make_script(gemini: Gemini, topic: str, language: str = "English", seconds: int = 60,
                level: str = "college students", log=print) -> Script:
    log("Researching the topic with Google Search grounding…")
    notes, sources = gemini.research(research_prompt(topic, level))
    log(f"Research done: {len(sources)} web sources.")
    log("Writing the four-beat script…")
    draft: ScriptDraft = gemini.structured(script_prompt(topic, notes, language, seconds, level), ScriptDraft)
    beats = _normalise_beats(draft.beats)
    return Script(
        **{**draft.model_dump(), "beats": beats},
        topic=topic, language=language, seconds=seconds, sources=sources, research_notes=notes,
    )


def _normalise_beats(beats):
    """Make sure we have exactly hook/setup/maths/payoff in order."""
    by_name = {}
    for b in beats:
        key = b.name.strip().lower().replace("the ", "")
        if key in BEAT_NAMES and key not in by_name:
            by_name[key] = b
    if len(by_name) == 4:
        return [by_name[n] for n in BEAT_NAMES]
    fixed = list(beats)[:4]
    for b, name in zip(fixed, BEAT_NAMES):
        b.name = name
    return fixed


# -- automatic fact-check (used when nobody reviews the script) ----------------
from pydantic import BaseModel, Field  # noqa: E402


class FactCheck(BaseModel):
    issues: list[str] = Field(default_factory=list,
                              description="Each error found and how it was fixed. Empty list if everything was correct.")
    script: ScriptDraft


def fact_check_prompt(script: Script) -> str:
    draft = ScriptDraft(title=script.title, beats=script.beats, numbers_to_verify=script.numbers_to_verify,
                        description=script.description)
    return f"""You are the maths fact-checker for a short educational video. Nobody else will check it before it is published.

1. Recompute every number, formula and worked step in the script from scratch, step by step.
2. Check every factual claim against the research notes. Remove or soften any claim the notes don't support.
3. Check the definition and formula are standard and correct (signs, indices, conditions such as "non-zero vector").
4. Narration and on-screen text (key_text, formula, on_screen) must use the same numbers.
5. Fix errors in place. Keep the same 4 beats in the same order, the same language, similar length, and the same style.
   Change nothing that is already correct.

Return `issues` (what you fixed; empty if nothing) and the full corrected `script`.

Research notes:
<<<
{script.research_notes or '(none)'}
>>>

Script (JSON):
{draft.model_dump_json(indent=1)}"""


def fact_check(gemini: Gemini, script: Script, log=print) -> tuple[Script, list[str]]:
    log("Fact-checking the maths and claims…")
    try:
        res: FactCheck = gemini.structured(fact_check_prompt(script), FactCheck, temperature=0.2)
    except Exception as exc:
        log(f"  Fact-check skipped ({exc}).")
        return script, []
    beats = _normalise_beats(res.script.beats)
    if len(beats) != 4 or any(not b.narration.strip() for b in beats):
        log("  Fact-check returned an incomplete script; keeping the original.")
        return script, []
    fixed = script.model_copy(update={
        "title": res.script.title or script.title,
        "beats": beats,
        "numbers_to_verify": res.script.numbers_to_verify or script.numbers_to_verify,
        "description": res.script.description or script.description,
    })
    log(f"  {len(res.issues)} correction(s) made." if res.issues else "  No errors found.")
    for issue in res.issues:
        log(f"  • {issue}")
    return fixed, res.issues
