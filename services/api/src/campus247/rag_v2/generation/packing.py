"""Evidence packing by real payload bytes, with an honest signal when context was left out."""
from __future__ import annotations

import json
from collections.abc import Callable, Iterable

from campus247.rag_v2.types import Unit

MAX_SOURCES = 8   # the semantic verifier refuses more than eight sources


def payload_bytes(unit: Unit) -> int:
    return len(json.dumps(unit.text, ensure_ascii=False).encode())


def pack_context(units: Iterable[Unit], chunk_unit: Callable[[str], Unit | None] | None, *,
                 budget: int, max_parents: int = 6) -> tuple[dict[str, Unit], bool]:
    """Rank-ordered evidence that fits ``budget`` bytes; the flag is True when something was left out.

    The parent row is preferred because conditions, footnotes and sibling rows sit there. When the
    parent alone does not fit, the fine unit is used instead (never silently dropped, never over
    budget) and the result is flagged, since the conditions around it were not available.
    """
    selected: dict[str, Unit] = {}
    parents_seen: set[str] = set()
    used, truncated = 0, False
    for unit in units:
        if len(selected) >= MAX_SOURCES:
            truncated = True
            break
        chunk_id = unit.chunk_ids[0] if unit.chunk_ids else None
        parent = chunk_unit(chunk_id) if chunk_unit is not None and chunk_id else None
        if parent is not None and chunk_id in parents_seen:
            continue
        if parent is not None and len(parents_seen) < max_parents and used + payload_bytes(parent) <= budget:
            parents_seen.add(chunk_id)
            selected[parent.unit_id] = parent
            used += payload_bytes(parent)
            continue
        # Parent unavailable or too large: fall back to the fine unit if it fits.
        if unit.unit_id not in selected and used + payload_bytes(unit) <= budget:
            selected[unit.unit_id] = unit
            used += payload_bytes(unit)
            truncated = truncated or parent is not None
        else:
            truncated = True
    return selected, truncated
