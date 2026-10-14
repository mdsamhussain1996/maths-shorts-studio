"""Thin wrapper around the Gemini API (google-genai SDK)."""
from __future__ import annotations

import time

from google import genai
from google.genai import types


class GeminiError(RuntimeError):
    pass


class Gemini:
    def __init__(self, api_key: str, model: str = "gemini-3.5-flash", code_model: str | None = None):
        if not api_key:
            raise GeminiError("No Gemini API key. Get a free one at https://aistudio.google.com/apikey")
        self.client = genai.Client(api_key=api_key)
        self.model = model
        self.code_model = code_model or model

    # -- low level -------------------------------------------------------
    def _call(self, model: str, contents: str, config: types.GenerateContentConfig, tries: int = 4):
        delay = 4.0
        last = None
        for attempt in range(tries):
            try:
                return self.client.models.generate_content(model=model, contents=contents, config=config)
            except Exception as exc:  # network, quota, overload
                last = exc
                msg = str(exc)
                retryable = any(k in msg for k in ("429", "500", "503", "RESOURCE_EXHAUSTED", "UNAVAILABLE", "overloaded", "deadline"))
                if not retryable or attempt == tries - 1:
                    break
                time.sleep(delay)
                delay *= 2
        raise GeminiError(f"Gemini call failed: {last}")

    # -- public ----------------------------------------------------------
    def research(self, prompt: str) -> tuple[str, list[dict]]:
        """Answer with Google Search grounding. Returns (text, [{title, url}])."""
        cfg = types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())], temperature=0.4)
        try:
            resp = self._call(self.model, prompt, cfg)
        except GeminiError:
            # Some models / keys don't allow search grounding: fall back to plain generation.
            resp = self._call(self.model, prompt, types.GenerateContentConfig(temperature=0.4))
        sources: list[dict] = []
        seen = set()
        try:
            meta = resp.candidates[0].grounding_metadata
            for chunk in (meta.grounding_chunks or []) if meta else []:
                web = getattr(chunk, "web", None)
                if web and web.uri and web.uri not in seen:
                    seen.add(web.uri)
                    sources.append({"title": web.title or web.uri, "url": web.uri})
        except (AttributeError, IndexError, TypeError):
            pass
        return (resp.text or "").strip(), sources

    def structured(self, prompt: str, schema, temperature: float = 0.7):
        cfg = types.GenerateContentConfig(
            response_mime_type="application/json", response_schema=schema, temperature=temperature
        )
        resp = self._call(self.model, prompt, cfg)
        parsed = getattr(resp, "parsed", None)
        if isinstance(parsed, schema):
            return parsed
        try:
            return schema.model_validate_json(resp.text)
        except Exception as exc:
            raise GeminiError(f"Gemini returned JSON that didn't match the script format: {exc}") from exc

    def code(self, prompt: str, system: str) -> str:
        cfg = types.GenerateContentConfig(system_instruction=system, temperature=0.5)
        resp = self._call(self.code_model, prompt, cfg)
        return resp.text or ""
