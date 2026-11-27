"""Evidence packing by real payload bytes, with an honest signal when context was left out."""
from __future__ import annotations

import json
from collections.abc import Callable, Iterable

from campus247.rag_v2.ingest.units import heading_text
from campus247.rag_v2.retrieval.hybrid import label_only_page
from campus247.rag_v2.types import Unit

MAX_SOURCES = 8   # the semantic verifier refuses more than eight sources


def payload_bytes(unit: Unit) -> int:
    return len(json.dumps(unit.text, ensure_ascii=False).encode())


def _keep_heading_row(unit: Unit, parent: Unit, selected: dict[str, Unit], room: int) -> int:
    """A reviewed curriculum row whose headings say what the page does not (its semester, a prerequisite pair "A → B") is kept
    beside its page: the page is a table whose column layout the text lost. Returns the bytes it used (0 when not kept)."""
    if unit.kind != "curriculum_row" or unit.unit_id in selected or len(selected) >= MAX_SOURCES:
        return 0
    heading = heading_text(unit)
    if not heading or heading == heading_text(parent) or heading in parent.text:
        return 0
    size = payload_bytes(unit)
    if size > room:
        return 0
    selected[unit.unit_id] = unit
    return size


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
        if parent is not None and unit.kind == "curriculum_row" and label_only_page(parent):
            parent = None   # the page is only a label ("71CS / Học phần tiên quyết:"); the row with its headings says it all
        if parent is not None and chunk_id in parents_seen:
            used += _keep_heading_row(unit, parent, selected, budget - used)
            continue
        if parent is not None and len(parents_seen) < max_parents and used + payload_bytes(parent) <= budget:
            parents_seen.add(chunk_id)
            selected[parent.unit_id] = parent
            used += payload_bytes(parent)
            used += _keep_heading_row(unit, parent, selected, budget - used)
            continue
        # Parent unavailable or too large: fall back to the fine unit if it fits.
        if unit.unit_id not in selected and used + payload_bytes(unit) <= budget:
            selected[unit.unit_id] = unit
            used += payload_bytes(unit)
            truncated = truncated or parent is not None
        else:
            truncated = True
    return selected, truncated
