from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence


@dataclass(frozen=True)
class ConversationSummary:
    conversation_id: str
    covered_through_turn_id: str
    summary_version: str = "1.0"
    user_goals: tuple[str, ...] = ()
    confirmed_facts: tuple[dict[str, Any], ...] = ()
    open_questions: tuple[str, ...] = ()
    pending_action_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class TurnItem:
    turn_id: str
    role: str
    content: str
    untrusted: bool = True


@dataclass(frozen=True)
class ContextManifest:
    conversation_id: str
    turns: tuple[TurnItem, ...]
    summary: ConversationSummary | None = None
    total_chars: int = 0
    item_count: int = 0


class BoundedContextBuilder:
    """Constructs bounded conversation context window with summary and untrusted labeling."""

    def __init__(self, max_turns: int = 5, max_chars: int = 4000) -> None:
        for name, value in (("max_turns", max_turns), ("max_chars", max_chars)):
            if type(value) is not int or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        self._max_turns = max_turns
        self._max_chars = max_chars

    def build(
        self,
        conversation_id: str,
        turns: Sequence[TurnItem],
        summary: ConversationSummary | None = None,
    ) -> ContextManifest:
        if not turns:
            return ContextManifest(
                conversation_id=conversation_id,
                turns=(),
                summary=summary,
                total_chars=0,
                item_count=0,
            )

        # Slice latest turns up to max_turns
        recent_turns = list(turns[-self._max_turns :])

        # Enforce character budget by dropping oldest if necessary
        while recent_turns:
            total_chars = sum(len(t.content) for t in recent_turns)
            if total_chars <= self._max_chars:
                break
            recent_turns.pop(0)

        total_chars = sum(len(t.content) for t in recent_turns)
        return ContextManifest(
            conversation_id=conversation_id,
            turns=tuple(recent_turns),
            summary=summary,
            total_chars=total_chars,
            item_count=len(recent_turns),
        )
