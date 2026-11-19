from __future__ import annotations

from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parents[3]
API_SRC = ROOT / "services" / "api" / "src"
if str(API_SRC) not in sys.path:
    sys.path.insert(0, str(API_SRC))

from campus247.application.conversation.context import (
    BoundedContextBuilder,
    ContextManifest,
    ConversationSummary,
    TurnItem,
)


def test_bounded_context_builder_truncates_old_turns() -> None:
    builder = BoundedContextBuilder(max_turns=3, max_chars=1000)

    turns = [
        TurnItem(turn_id=f"t_{i}", role="user" if i % 2 == 0 else "assistant", content=f"Tin nhan {i}")
        for i in range(10)
    ]

    manifest = builder.build(conversation_id="conv_001", turns=turns)

    assert isinstance(manifest, ContextManifest)
    assert manifest.conversation_id == "conv_001"
    assert len(manifest.turns) == 3
    # Keeps the latest turns (t_7, t_8, t_9)
    assert manifest.turns[0].turn_id == "t_7"
    assert manifest.turns[2].turn_id == "t_9"
    assert all(t.untrusted is True for t in manifest.turns if t.role == "user")


def test_bounded_context_with_summary() -> None:
    builder = BoundedContextBuilder(max_turns=2, max_chars=1000)
    summary = ConversationSummary(
        conversation_id="conv_002",
        covered_through_turn_id="t_5",
        user_goals=("Hỏi về học phí",),
        open_questions=(),
    )

    turns = [
        TurnItem(turn_id="t_6", role="user", content="Cảm ơn bạn."),
        TurnItem(turn_id="t_7", role="assistant", content="Rất vui được hỗ trợ!"),
    ]

    manifest = builder.build(conversation_id="conv_002", turns=turns, summary=summary)
    assert manifest.summary is not None
    assert manifest.summary.covered_through_turn_id == "t_5"
    assert len(manifest.turns) == 2


def test_bounded_context_empty_turns() -> None:
    builder = BoundedContextBuilder()
    manifest = builder.build(conversation_id="conv_003", turns=[])
    assert manifest.turns == ()
    assert manifest.summary is None
    assert manifest.total_chars == 0


def test_oversized_latest_turn_cannot_exceed_context_budget() -> None:
    turns = [
        TurnItem(turn_id="old", role="user", content="short"),
        TurnItem(turn_id="latest", role="assistant", content="x" * 101),
    ]
    manifest = BoundedContextBuilder(max_chars=100).build("conv_004", turns)
    assert manifest.turns == ()
    assert manifest.total_chars == manifest.item_count == 0
    assert turns[-1].content == "x" * 101  # Stored history is not truncated.


def test_context_budget_keeps_exact_latest_suffix_at_boundary() -> None:
    turns = [TurnItem(str(i), "user", content) for i, content in enumerate(["old", "12345", "67890"])]
    manifest = BoundedContextBuilder(max_chars=10).build("conv_005", turns)
    assert manifest.turns == tuple(turns[1:])
    assert manifest.total_chars == 10
    assert manifest.item_count == 2


@pytest.mark.parametrize("invalid", [0, -1, True, 1.5, "5"])
@pytest.mark.parametrize("name", ["max_turns", "max_chars"])
def test_invalid_context_budget_is_rejected(name, invalid) -> None:
    with pytest.raises(ValueError, match=name):
        BoundedContextBuilder(**{name: invalid})
