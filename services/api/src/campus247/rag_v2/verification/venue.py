"""Deterministic place check: a source that regulates one named place does not answer for another."""
from __future__ import annotations

from collections.abc import Iterable

from campus247.rag_v2.types import Unit
from campus247.rag_v2.understanding.normalize import fold

# Canonical place -> folded terms that name it. Only places with their own regulations are listed.
_VENUES = {
    "exam_room": ("phong thi", "dia diem thi", "khu vuc thi", "ban coi thi"),
    "computer_lab": ("phong may", "phong thuc hanh may", "phong may tinh"),
    "dormitory": ("ky tuc xa", "ktx", "noi tru"),
    "library": ("thu vien",),
    "gym": ("nha the thao", "san the thao", "nha tap"),
}


def _venues(text: str) -> set[str]:
    folded = f" {fold(text)} "
    return {name for name, terms in _VENUES.items() if any(f" {term} " in folded or f" {term}," in folded
                                                          or f" {term}." in folded for term in terms)}


def venue_conflict(question: str, cited: Iterable[Unit]) -> bool:
    """True when the question names a place and every cited source is about other places only."""
    wanted = _venues(question)
    if not wanted:
        return False
    cited = list(cited)
    if not cited:
        return False
    for unit in cited:
        found = _venues(f"{unit.path} {unit.text}")
        if not found or found & wanted:
            return False
    return True
