"""How current a knowledge source is, computed from dates alone.

A source can run out in two ways. It may carry an explicit `effective_until`, after which retrieval already ignores it
(`EXPIRED`). Many sources carry none, so nothing ever tells their owner to look at them again; for those a review is
due a fixed interval after the later of the last review and the date the source took effect or was published.

Pure functions: no I/O, no clock reads, no model calls. The caller passes `now`.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

DEFAULT_REVIEW_INTERVAL_DAYS = 365
DEFAULT_SOON_DAYS = 30


class Freshness(StrEnum):
    OK = "OK"
    DUE_SOON = "DUE_SOON"
    OVERDUE = "OVERDUE"
    EXPIRED = "EXPIRED"


class DueReason(StrEnum):
    EFFECTIVE_UNTIL = "EFFECTIVE_UNTIL"
    REVIEW_INTERVAL = "REVIEW_INTERVAL"


@dataclass(frozen=True)
class FreshnessAssessment:
    state: Freshness
    due_at: datetime | None
    reason: DueReason | None
    days_left: int | None  # negative once past due; None when nothing has a date
    applicability_unknown: bool


def _aware(name: str, value: datetime | None) -> datetime | None:
    if value is not None and (value.tzinfo is None or value.utcoffset() is None):
        raise ValueError(f"{name} must be timezone-aware")
    return value


def _days_between(later: datetime, earlier: datetime) -> int:
    """Whole days from `earlier` to `later`, rounded toward negative infinity so a few hours past due is -1."""
    seconds = (later - earlier).total_seconds()
    return int(seconds // 86400)


def assess_freshness(
    *,
    now: datetime,
    effective_from: datetime | None = None,
    effective_until: datetime | None = None,
    published_at: datetime | None = None,
    last_reviewed_at: datetime | None = None,
    review_interval_days: int = DEFAULT_REVIEW_INTERVAL_DAYS,
    soon_days: int = DEFAULT_SOON_DAYS,
    applicability_unknown: bool = False,
) -> FreshnessAssessment:
    if review_interval_days <= 0 or soon_days < 0:
        raise ValueError("review interval must be positive and the warning window not negative")
    now = _aware("now", now)
    effective_from = _aware("effective_from", effective_from)
    effective_until = _aware("effective_until", effective_until)
    published_at = _aware("published_at", published_at)
    last_reviewed_at = _aware("last_reviewed_at", last_reviewed_at)
    assert now is not None

    if effective_until is not None and effective_until <= now:
        return FreshnessAssessment(Freshness.EXPIRED, effective_until, DueReason.EFFECTIVE_UNTIL,
                                   _days_between(effective_until, now), applicability_unknown)

    # The date a review clock starts: the last review if there is one, otherwise the later of effect and publication.
    starts = [d for d in (last_reviewed_at,) if d is not None] or [d for d in (effective_from, published_at) if d is not None]
    review_due = max(starts) + timedelta(days=review_interval_days) if starts else None

    candidates: list[tuple[datetime, DueReason]] = []
    if effective_until is not None:
        candidates.append((effective_until, DueReason.EFFECTIVE_UNTIL))
    if review_due is not None:
        candidates.append((review_due, DueReason.REVIEW_INTERVAL))
    if not candidates:
        return FreshnessAssessment(Freshness.OK, None, None, None, applicability_unknown)

    due_at, reason = min(candidates, key=lambda item: item[0])
    days_left = _days_between(due_at, now)
    if due_at <= now:
        state = Freshness.OVERDUE  # only a review interval can be past due here; a passed effective_until returned above
    elif due_at - now <= timedelta(days=soon_days):
        state = Freshness.DUE_SOON
    else:
        state = Freshness.OK
    return FreshnessAssessment(state, due_at, reason, days_left, applicability_unknown)
