"""Trailing "next steps" block of an assistant message.

The server writes it from fixed text and values taken from readable sources; the chat UI parses the same marker
back into buttons, and any other reader sees an ordinary bullet list.
"""
from __future__ import annotations

from collections.abc import Sequence

GUIDANCE_MARKER = "Gợi ý hỏi tiếp:"
MAX_ITEMS = 5
# Internal slot names can travel in Outcome.suggestions as a fallback; they are never user-facing text.
_SLOT_KEYS = {"cohort", "academic_year", "program", "training_system", "document", "semester", "audience",
              "cohort|academic_year", "semester|academic_year"}


def render_guidance(suggestions: Sequence[str]) -> str:
    items = []
    for value in suggestions:
        text = " ".join(str(value).split())
        if text and text not in _SLOT_KEYS and text not in items and len(text) <= 160:
            items.append(text)
    if not items:
        return ""
    return "\n\n" + GUIDANCE_MARKER + "\n" + "\n".join("- " + item for item in items[:MAX_ITEMS])
