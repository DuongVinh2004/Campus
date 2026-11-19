"""Pure rules for practice questions built from lecture material.

Three things, none of which touch storage, a clock or a model:
  * a question may only quote the page it cites (`verify_citation`), so every answer can be traced to a page;
  * grading is exact: choices by identifier, short answers after a fixed normalization (no model grades anything);
  * spaced repetition, a reduced SM-2: a right answer pushes the next review out, a wrong one brings it back to a day.
"""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

MIN_QUOTE_CHARS = 12
MAX_INTERVAL_DAYS = 365
EASE_START, EASE_MIN, EASE_MAX = 2.5, 1.3, 3.0

_SPACES = re.compile(r"\s+")
_INVISIBLE = dict.fromkeys(map(ord, "​‌‍⁠﻿­"))
_PUNCTUATION = re.compile(r"[^\w\s]", re.UNICODE)


def normalize_text(value: str) -> str:
    """NFC, invisible characters removed, every run of whitespace (including line breaks) becomes one space."""
    return _SPACES.sub(" ", unicodedata.normalize("NFC", value).translate(_INVISIBLE)).strip()


# --------------------------------------------------------------------------------------------------- citations

@dataclass(frozen=True)
class CitationCheck:
    ok: bool
    reason: Literal["OK", "QUOTE_TOO_SHORT", "PAGE_MISSING", "QUOTE_NOT_ON_PAGE"]


def verify_citation(page_text: str | None, quote: str) -> CitationCheck:
    """The quote must appear word for word (after whitespace and Unicode normalization) on the cited page."""
    wanted = normalize_text(quote)
    if len(wanted) < MIN_QUOTE_CHARS:
        return CitationCheck(False, "QUOTE_TOO_SHORT")
    if page_text is None:
        return CitationCheck(False, "PAGE_MISSING")
    return CitationCheck(True, "OK") if wanted in normalize_text(page_text) else CitationCheck(False, "QUOTE_NOT_ON_PAGE")


def verify_item_citations(citations: Sequence[Mapping[str, object]], pages: Mapping[int, str]) -> list[tuple[int, CitationCheck]]:
    """Failed checks as (index in `citations`, result). An item with no citation at all fails with PAGE_MISSING."""
    if not citations:
        return [(0, CitationCheck(False, "PAGE_MISSING"))]
    failures = []
    for index, citation in enumerate(citations):
        page_no = citation.get("page_no")
        text = pages.get(page_no) if isinstance(page_no, int) and not isinstance(page_no, bool) else None
        result = verify_citation(text, str(citation.get("quote", "")))
        if not result.ok:
            failures.append((index, result))
    return failures


# --------------------------------------------------------------------------------------------------- grading

def normalize_answer(value: str) -> str:
    """Case, accents' composition, punctuation and spacing do not decide a short answer; the letters do."""
    return _SPACES.sub(" ", _PUNCTUATION.sub(" ", normalize_text(value).casefold())).strip()


def grade_short_answer(given: str, accepted: Iterable[str]) -> bool:
    answer = normalize_answer(given)
    return bool(answer) and any(answer == normalize_answer(option) for option in accepted)


def grade_choice(chosen: Iterable[str], correct: Iterable[str]) -> bool:
    chosen_set, correct_set = set(chosen), set(correct)
    return bool(correct_set) and chosen_set == correct_set


# --------------------------------------------------------------------------------------------------- spacing

@dataclass(frozen=True)
class ReviewState:
    ease: float = EASE_START
    interval_days: int = 0
    repetitions: int = 0
    due_at: datetime | None = None  # None: never answered


def next_review(state: ReviewState, *, correct: bool, now: datetime) -> ReviewState:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    if correct:
        ease = min(EASE_MAX, state.ease + 0.1)
        interval = min(MAX_INTERVAL_DAYS, max(1, round(state.interval_days * ease)))
        return ReviewState(ease, interval, state.repetitions + 1, now + timedelta(days=interval))
    ease = max(EASE_MIN, state.ease - 0.2)
    return ReviewState(ease, 1, 0, now + timedelta(days=1))


def pick_session(states: Mapping[str, ReviewState], *, now: datetime, size: int = 10) -> list[str]:
    """Item ids for one session: overdue first (longest overdue first), then never-answered, then the soonest due.

    Ties break on the id so the same data always gives the same session.
    """
    if size <= 0:
        return []
    due, new, later = [], [], []
    for item_id, state in states.items():
        if state.due_at is None:
            new.append(item_id)
        elif state.due_at <= now:
            due.append((state.due_at, item_id))
        else:
            later.append((state.due_at, item_id))
    ordered = [i for _, i in sorted(due)] + sorted(new) + [i for _, i in sorted(later)]
    return ordered[:size]
