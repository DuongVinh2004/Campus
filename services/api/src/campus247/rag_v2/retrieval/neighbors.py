"""Sibling expansion of the top retrieved units.

Units follow the source structure (clause, point, table row), so an answer that sits in a sibling of
the best-matching unit ("Điểm b" next to "Điểm a" of the same Khoản) is not retrieved by similarity
alone. On the dev set the answer facts were present in the top 12 units for 62% of the answerable
cases while the right chunk was present for 91%; the missing text was usually a sibling. Adding the
siblings (same document version, same parent path) of the best candidates closes much of that gap
without a model call.
"""
from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Sequence

from campus247.rag_v2.ports import UnitIndex

_GROUPS: dict[int, tuple[int, dict[tuple[str, str], list[str]]]] = {}
_PAGE = re.compile(r"^tr\.\d+$")


def parent_key(version_id: str, path: str) -> tuple[str, str] | None:
    parts = [p.strip() for p in path.split(">")]
    if parts and _PAGE.match(parts[-1]):
        parts = parts[:-1]
    if len(parts) < 2:  # a top-level unit has no siblings in this sense
        return None
    return version_id, " > ".join(parts[:-1])


def _groups(index: UnitIndex) -> dict[tuple[str, str], list[str]]:
    ids = index.all_ids()
    cached = _GROUPS.get(id(index))
    if cached is None or cached[0] != len(ids):
        groups: dict[tuple[str, str], list[str]] = defaultdict(list)
        for uid in ids:
            unit = index.get(uid)
            if unit is None:
                continue
            key = parent_key(unit.version_id, unit.path)
            if key is not None:
                groups[key].append(uid)
        cached = _GROUPS[id(index)] = (len(ids), dict(groups))
    return cached[1]


def expand_neighbors(unit_ids: Sequence[str], index: UnitIndex, *, seeds: int = 6, per_seed: int = 4,
                     cap: int = 16, allowed: set[str] | None = None) -> list[str]:
    """Return `unit_ids` followed by siblings of the first `seeds` ids, capped at `cap` units."""
    if cap < 1 or seeds < 0 or per_seed < 0:
        raise ValueError("non-negative expansion bounds required")
    ordered = list(dict.fromkeys(unit_ids))[:cap]
    if not ordered or seeds == 0 or per_seed == 0:
        return ordered
    groups = _groups(index)
    seen = set(ordered)
    for uid in list(ordered[:seeds]):
        unit = index.get(uid)
        key = parent_key(unit.version_id, unit.path) if unit is not None else None
        added = 0
        for sibling in groups.get(key, ()) if key is not None else ():
            if len(ordered) >= cap or added >= per_seed:
                break
            if sibling in seen or (allowed is not None and sibling not in allowed):
                continue
            seen.add(sibling)
            ordered.append(sibling)
            added += 1
    return ordered
