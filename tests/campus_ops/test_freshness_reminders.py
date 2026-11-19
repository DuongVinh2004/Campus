"""Reminders to knowledge managers: 30 and 7 days before a source's date, a weekly summary of overdue ones, once each."""
import logging
from datetime import UTC, datetime, timedelta

import pytest

from campus247.application.campus_ops.reminders import deliver
from campus247.application.knowledge.freshness_reminders import run_freshness_reminders, source_candidates
from campus247.infrastructure.repositories.sqlite_campus_ops import CampusOpsStore

NOW = datetime(2026, 11, 17, 3, 0, tzinfo=UTC)  # a Tuesday
D = timedelta(days=1)


def item(version_id, title, state, days_left, reason="EFFECTIVE_UNTIL"):
    due = (NOW + days_left * D).isoformat().replace("+00:00", "Z") if days_left is not None else None
    return {"source_id": "s-" + version_id, "version_id": version_id, "title": title, "state": state, "due_at": due, "reason": reason, "days_left": days_left}


@pytest.fixture
def store(tmp_path):
    return CampusOpsStore(tmp_path / "ops.sqlite3")


def inbox(store, who="manager-1"):
    return store.query("SELECT title, body, link FROM ops_notifications WHERE recipient_subject_id=? ORDER BY title", (who,))


def test_a_source_about_to_expire_gets_a_30_day_and_a_7_day_notice_once_each(store):
    items = [item("v1", "Học phí 2026", "DUE_SOON", 29)]
    assert deliver(store, source_candidates(items, ["manager-1"], now=NOW), now=NOW) == 1
    assert deliver(store, source_candidates(items, ["manager-1"], now=NOW + D), now=NOW + D) == 0
    later = NOW + 23 * D  # six days left
    assert deliver(store, source_candidates([item("v1", "Học phí 2026", "DUE_SOON", 6)], ["manager-1"], now=later), now=later) == 0  # another date is another cycle, and that date is already in the past
    assert deliver(store, source_candidates(items, ["manager-1"], now=later), now=later) == 1  # the original date: seven days left
    (first, second) = inbox(store)
    assert first["title"] == second["title"] == "Nguồn sắp hết hiệu lực: Học phí 2026" and first["link"] == "/knowledge/freshness"
    assert "Sau ngày này nguồn không còn xuất hiện" in first["body"]


def test_a_review_reminder_uses_different_wording_from_an_expiry(store):
    candidates = source_candidates([item("v2", "Quy chế", "DUE_SOON", 20, reason="REVIEW_INTERVAL")], ["manager-1"], now=NOW)
    deliver(store, candidates, now=NOW)
    (message,) = inbox(store)
    assert message["title"] == "Nguồn sắp đến hạn rà soát: Quy chế" and "ghi nhận đã rà soát" in message["body"] and "Còn 20 ngày" in message["body"]


def test_ok_and_expired_sources_get_no_individual_reminder(store):
    items = [item("v1", "A", "OK", 200), item("v2", "B", "EXPIRED", -3), item("v3", "C", "DUE_SOON", None)]
    assert source_candidates(items, ["manager-1"], now=NOW) == []


def test_overdue_sources_make_one_summary_per_week_per_manager(store):
    items = [item("v1", "A", "OVERDUE", -10, "REVIEW_INTERVAL"), item("v2", "B", "OVERDUE", -40, "REVIEW_INTERVAL")]
    managers = ["manager-1", "manager-2"]
    assert deliver(store, source_candidates(items, managers, now=NOW), now=NOW) == 2
    assert deliver(store, source_candidates(items, managers, now=NOW + 2 * D), now=NOW + 2 * D) == 0  # same week
    next_week = NOW + 7 * D
    assert deliver(store, source_candidates(items, managers, now=next_week), now=next_week) == 2
    assert inbox(store, "manager-1")[0]["title"] == "2 nguồn quá hạn rà soát"


def test_no_summary_when_nothing_is_overdue(store):
    assert source_candidates([item("v1", "A", "OK", 100)], ["manager-1"], now=NOW) == []


@pytest.mark.asyncio
async def test_the_loop_reports_sends_and_survives_failures(store, caplog):
    calls = []

    class Service:
        async def report(self, *, now):
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("database unavailable")
            return {"items": [item("v1", "Học phí 2026", "DUE_SOON", 5)]}

    with caplog.at_level(logging.INFO, logger="campus247.freshness"):
        await run_freshness_reminders(Service(), store, lambda: ["manager-1"], every_s=0, clock=lambda: NOW, passes=3)
    assert len(calls) == 3 and len(inbox(store)) == 1
    assert "freshness_reminders_failed kind=RuntimeError" in caplog.text and "database unavailable" not in caplog.text
