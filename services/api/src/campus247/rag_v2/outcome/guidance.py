"""Server-built next steps: tappable values for a missing scope and related documents for a dead end.

Everything here is derived from the sources the user is already allowed to read (their scopes and titles) or
from fixed text. Nothing is model-authored, so it can be shown next to any outcome without further checks.
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Sequence

from campus247.rag_v2.types import Unit
from campus247.rag_v2.understanding.analyze import _PROGRAMS
from campus247.rag_v2.understanding.normalize import fold, normalize_query

MAX_CHIPS = 4
_COHORT = re.compile(r"^K(\d{2,3})$", re.IGNORECASE)


def program_label(value: str) -> str | None:
    """Readable programme name for a code ("7480201") or a name already in the sources."""
    for code, names in _PROGRAMS:
        if value == code or fold(value) in names:
            return normalize_query(names[0]).capitalize()
    if value and not value.isdigit() and len(value) <= 60:
        return value[:1].upper() + value[1:]
    return None


def _cohort_key(value: str) -> int:
    match = _COHORT.match(value.strip())
    return int(match[1]) if match else -1


def scope_chips(missing_slots: Iterable[str], units: Iterable[Unit], *, limit: int = MAX_CHIPS) -> tuple[str, ...]:
    """Values the user can tap to narrow an answer, taken from the scopes of the sources that answered."""
    units = list(units)
    chips: list[str] = []
    for slot in missing_slots:
        if slot == "cohort|academic_year":
            cohorts = {c.upper() for u in units for c in u.scope.cohorts if _COHORT.match(c.strip())}
            if not cohorts:
                # Fee and rule tables often name the cohorts only in their text ("K64 trở về trước", "từ K69").
                cohorts = {f"K{m}" for u in units for m in re.findall(r"\bK(\d{2})\b", u.text)}
            if cohorts:
                chips += [c for c in sorted(cohorts, key=_cohort_key, reverse=True)[:limit]]
            else:
                years = sorted({y for u in units for y in u.scope.academic_years}, reverse=True)
                chips += [f"Năm học {y}" for y in years[:2]]
        elif slot == "program":
            labels = []
            for u in units:
                for p in u.scope.programs:
                    label = program_label(p)
                    if label and label not in labels:
                        labels.append(label)
            chips += labels[:limit]
        elif slot == "semester|academic_year":
            years = sorted({y for u in units for y in u.scope.academic_years}, reverse=True)
            chips += [f"Học kỳ 1 năm học {years[0]}", f"Học kỳ 2 năm học {years[0]}"] if years else ["Học kỳ 1", "Học kỳ 2"]
    return tuple(dict.fromkeys(chips))[:limit]


def related_documents(units: Sequence[Unit], *, limit: int = 3) -> tuple[str, ...]:
    """Titles of the documents nearest to a question that could not be answered (a dead end that still helps)."""
    titles: list[str] = []
    for unit in units:
        title = " ".join(unit.doc_title.split())
        if title and title not in titles and len(title) <= 110:
            titles.append(title)
        if len(titles) == limit:
            break
    return tuple(titles)
