"""The reminder loop: it delivers, it survives a failing pass, and it can be cancelled."""
import asyncio
import logging
from datetime import UTC, datetime, timedelta

import pytest

from campus247.application.campus_ops.reminder_job import run_once, run_reminders
from campus247.infrastructure.repositories.sqlite_campus_ops import CampusOpsStore

EXAM = datetime(2026, 11, 20, 1, 0, tzinfo=UTC)


@pytest.fixture
def store(tmp_path):
    store = CampusOpsStore(tmp_path / "ops.sqlite3")
    with store.tx() as c:
        c.execute("""INSERT INTO ops_schedule(id, owner_key, kind, course_code, course_name, starts_at, ends_at, location, instructor, note, source,
                     created_at, updated_at) VALUES ('e1','SV001','EXAM','IT1','Thi cuối kỳ','2026-11-20T01:00:00Z','2026-11-20T02:00:00Z','H1','x','','T','x','x')""")
    return store


def inbox(store):
    return store.query("SELECT title FROM ops_notifications WHERE recipient_subject_id='subject-1'")


def test_run_once_delivers_and_a_second_pass_does_not_repeat(store):
    now = EXAM - timedelta(hours=20)
    resolver = lambda: {"SV001": "subject-1"}.get  # noqa: E731
    assert run_once(store, resolver, now=now) == 1
    assert run_once(store, resolver, now=now + timedelta(minutes=5)) == 0
    assert [n["title"] for n in inbox(store)] == ["Sắp đến giờ thi: Thi cuối kỳ"]


@pytest.mark.asyncio
async def test_the_loop_keeps_going_after_a_failed_pass(store, caplog):
    calls = []

    def resolver():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("directory unreadable")
        return {"SV001": "subject-1"}.get

    with caplog.at_level(logging.WARNING, logger="campus247.reminders"):
        await run_reminders(store, resolver, every_s=0, clock=lambda: EXAM - timedelta(hours=20), passes=3)
    assert len(calls) == 3 and len(inbox(store)) == 1
    assert "reminders_failed kind=RuntimeError" in caplog.text and "directory unreadable" not in caplog.text


@pytest.mark.asyncio
async def test_the_loop_can_be_cancelled_while_it_sleeps(store):
    task = asyncio.create_task(run_reminders(store, lambda: {}.get, every_s=3600, clock=lambda: EXAM - timedelta(hours=20)))
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
