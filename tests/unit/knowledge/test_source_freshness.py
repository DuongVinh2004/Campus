from datetime import UTC, datetime, timedelta, timezone

import pytest
from campus247.application.knowledge.source_freshness import DueReason, Freshness, assess_freshness

NOW = datetime(2026, 11, 17, 3, 0, tzinfo=UTC)


def days(n):
    return timedelta(days=n)


def test_expired_when_effective_until_has_passed():
    result = assess_freshness(now=NOW, effective_until=NOW - days(1), effective_from=NOW - days(400))
    assert result.state is Freshness.EXPIRED and result.reason is DueReason.EFFECTIVE_UNTIL
    assert result.days_left == -1


def test_expired_exactly_at_effective_until():
    assert assess_freshness(now=NOW, effective_until=NOW).state is Freshness.EXPIRED


@pytest.mark.parametrize(
    ("offset_days", "expected"),
    [(31, Freshness.OK), (30, Freshness.DUE_SOON), (1, Freshness.DUE_SOON)],
)
def test_effective_until_ahead_is_due_soon_inside_the_window(offset_days, expected):
    result = assess_freshness(now=NOW, effective_until=NOW + days(offset_days), effective_from=NOW - days(10))
    assert result.state is expected
    assert result.reason is DueReason.EFFECTIVE_UNTIL
    assert result.days_left == offset_days


def test_source_without_end_date_is_reviewed_a_year_after_it_took_effect():
    started = NOW - days(200)
    result = assess_freshness(now=NOW, effective_from=started)
    assert result.state is Freshness.OK
    assert result.due_at == started + days(365) and result.reason is DueReason.REVIEW_INTERVAL
    assert result.days_left == 165


def test_source_without_end_date_becomes_overdue_after_the_interval():
    result = assess_freshness(now=NOW, effective_from=NOW - days(366))
    assert result.state is Freshness.OVERDUE and result.days_left == -1


def test_review_clock_starts_at_the_later_of_effect_and_publication():
    result = assess_freshness(now=NOW, effective_from=NOW - days(500), published_at=NOW - days(100))
    assert result.state is Freshness.OK
    assert result.due_at == NOW - days(100) + days(365)


def test_a_review_restarts_the_clock():
    stale = assess_freshness(now=NOW, effective_from=NOW - days(800))
    assert stale.state is Freshness.OVERDUE
    reviewed = assess_freshness(now=NOW, effective_from=NOW - days(800), last_reviewed_at=NOW - days(5))
    assert reviewed.state is Freshness.OK and reviewed.due_at == NOW - days(5) + days(365)


def test_earlier_of_end_date_and_review_wins():
    result = assess_freshness(now=NOW, effective_from=NOW - days(360), effective_until=NOW + days(200))
    assert result.reason is DueReason.REVIEW_INTERVAL and result.state is Freshness.DUE_SOON
    result = assess_freshness(now=NOW, effective_from=NOW - days(10), effective_until=NOW + days(20))
    assert result.reason is DueReason.EFFECTIVE_UNTIL and result.state is Freshness.DUE_SOON


def test_no_dates_at_all_has_nothing_to_warn_about():
    result = assess_freshness(now=NOW)
    assert (result.state, result.due_at, result.days_left) == (Freshness.OK, None, None)


def test_applicability_unknown_is_carried_through_every_state():
    assert assess_freshness(now=NOW, applicability_unknown=True).applicability_unknown
    assert assess_freshness(now=NOW, effective_until=NOW - days(1), applicability_unknown=True).applicability_unknown


def test_other_time_zones_compare_by_instant():
    plus7 = timezone(timedelta(hours=7))
    until = datetime(2026, 11, 17, 9, 59, tzinfo=plus7)  # 02:59 UTC, one minute before NOW
    assert assess_freshness(now=NOW, effective_until=until).state is Freshness.EXPIRED


def test_hours_past_due_count_as_minus_one_day():
    result = assess_freshness(now=NOW, effective_from=NOW - days(365) - timedelta(hours=3))
    assert result.state is Freshness.OVERDUE and result.days_left == -1


@pytest.mark.parametrize("field", ["now", "effective_from", "effective_until", "published_at", "last_reviewed_at"])
def test_naive_datetimes_are_rejected(field):
    kwargs = {"now": NOW}
    kwargs[field] = datetime(2026, 1, 1)
    with pytest.raises(ValueError, match="timezone-aware"):
        assess_freshness(**kwargs)


def test_invalid_windows_are_rejected():
    with pytest.raises(ValueError):
        assess_freshness(now=NOW, review_interval_days=0)
    with pytest.raises(ValueError):
        assess_freshness(now=NOW, soon_days=-1)
