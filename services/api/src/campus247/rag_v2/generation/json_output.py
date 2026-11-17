"""Bounded JSON extraction; malformed output is data, never an instruction."""
from __future__ import annotations

import json

from campus247.ports.llm import LlmResponse, LlmResponseStatus

MAX_RESPONSE_CHARS = 64_000


def response_object(response: LlmResponse) -> dict | None:
    if (not isinstance(response, LlmResponse)
            or response.status != LlmResponseStatus.COMPLETED or response.tool_candidates):
        return None
    if isinstance(response.structured_output, dict):
        return response.structured_output
    text = response.output_text
    if not isinstance(text, str) or len(text) > MAX_RESPONSE_CHARS:
        return None
    decoder = json.JSONDecoder()
    # A fence or a short preamble is tolerated, but a later object must not
    # replace an earlier valid object with an invalid schema.
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text, index)
        except ValueError:
            continue
        if isinstance(value, dict):
            return value
    return None
