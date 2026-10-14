"""Data shapes shared by the pipeline."""
from __future__ import annotations

from pydantic import BaseModel, Field

BEAT_NAMES = ["hook", "setup", "maths", "payoff"]
BEAT_LABELS = {"hook": "HOOK", "setup": "SETUP", "maths": "THE MATHS", "payoff": "PAYOFF"}


class Beat(BaseModel):
    name: str = Field(description="One of: hook, setup, maths, payoff")
    narration: str = Field(description="Exactly what the voice says in this beat")
    key_text: str = Field(description="Big on-screen headline for this beat, at most 8 words, English")
    formula: str = Field(default="", description="One LaTeX formula for this beat, or empty string")
    on_screen: str = Field(description="What the animation should show, concretely (objects, graphs, numbers)")


class ScriptDraft(BaseModel):
    """What the LLM returns. Sources are attached separately from grounding metadata."""
    title: str = Field(description="Catchy title, under 60 characters")
    beats: list[Beat]
    numbers_to_verify: list[str] = Field(
        default_factory=list,
        description="Every factual number or claim in the script that a teacher should double-check, with where it came from",
    )
    description: str = Field(default="", description="2-3 line description for YouTube/Instagram, with hashtags")


class Source(BaseModel):
    title: str = ""
    url: str = ""


class Script(ScriptDraft):
    topic: str
    language: str = "English"
    seconds: int = 60
    sources: list[Source] = Field(default_factory=list)
    research_notes: str = ""
