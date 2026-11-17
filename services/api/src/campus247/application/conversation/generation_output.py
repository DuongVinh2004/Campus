"""Safe output diagnostics; invalid claims never become grounded facts."""
from __future__ import annotations

import json

OUTPUT_FAILURE_CODES = frozenset({"AI_GENERATION_EMPTY_OUTPUT", "AI_GENERATION_EMPTY_CLAIMS",
    "AI_GENERATION_INVALID_SCHEMA", "AI_GENERATION_TIMEOUT"})


def invalid_output_code(text: str) -> str:
    if not text.strip():
        return "AI_GENERATION_EMPTY_OUTPUT"
    try:
        value = json.loads(text)
    except (ValueError, TypeError):
        return "AI_GENERATION_INVALID_SCHEMA"
    return ("AI_GENERATION_EMPTY_CLAIMS" if value == {"claims": []}
            else "AI_GENERATION_INVALID_SCHEMA")
