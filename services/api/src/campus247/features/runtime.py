"""Process-wide access to the feature service for code deep in the pipeline (RAG options, agent tools).

Nothing is installed in unit tests, so every helper falls back to the old behaviour: tools allowed, no value override.
"""
from __future__ import annotations

from typing import Any

_service = None


def install(service) -> None:
    global _service
    _service = service


def uninstall() -> None:
    install(None)


def value(key: str, fallback: Any) -> Any:
    """Effective value of a feature for the whole process, or `fallback` when no service is installed or the lookup fails."""
    if _service is None:
        return fallback
    try:
        return _service.value(key)
    except Exception:  # noqa: BLE001 -- a failing flag lookup must never break an answer
        return fallback


def tool_allowed(tool_id: str) -> bool:
    if _service is None:
        return True
    try:
        return _service.tool_enabled(tool_id)
    except Exception:  # noqa: BLE001
        return True
