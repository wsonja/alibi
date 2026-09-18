"""Performer selection (docs/INTERFACES.md §0.2, §3).

``get_performer(settings)`` returns the Gemini performer when the resolved mode is ``gemini`` and the scripted one
otherwise.  ``get_scripted_performer()`` is what the Director uses for the per-turn ``provider_fallback`` when a
Gemini call fails after the whole model ladder.
"""

from __future__ import annotations

from typing import Any, Protocol

from .client import resolve_mode
from .scripted import ScriptedPerformer
from .suspect import GeminiPerformer


class Performer(Protocol):
    mode: str

    async def perform(self, ctx: dict) -> dict: ...


_scripted_singleton: ScriptedPerformer | None = None


def get_scripted_performer() -> ScriptedPerformer:
    """The (stateless) scripted performer; shared because it holds nothing per game."""
    global _scripted_singleton
    if _scripted_singleton is None:
        _scripted_singleton = ScriptedPerformer()
    return _scripted_singleton


def get_performer(settings: Any = None) -> Performer:
    """A performer for the resolved LLM mode. ``settings`` may be None (env), a dict, or a settings object."""
    mode = resolve_mode(settings)
    if mode == "gemini":
        return GeminiPerformer()
    return get_scripted_performer()


__all__ = ["Performer", "get_performer", "get_scripted_performer", "resolve_mode"]
