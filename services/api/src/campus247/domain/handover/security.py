"""Instruction overrides are refused; genuine crises retain their priority."""
from __future__ import annotations


def requires_security_refusal(*, reason: str | None, is_crisis: bool) -> bool:
    return reason == "prompt_injection_signal" and not is_crisis
