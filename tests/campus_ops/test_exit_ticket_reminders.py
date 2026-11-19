"""Reminders for exit tickets (phiếu ra lớp) that are open, close soon and have not been answered by that student."""
from datetime import UTC, datetime, timedelta

import pytest

from campus247.application.campus_ops.reminders import deliver, exit_ticket_candidates
from campus247.application.learning.exit_reminders import open_exit_ticket_deadlines
from campus247.infrastructure.repositories.sqlite_campus_ops import CampusOpsStore

NOW = datetime(2026, 11, 20, 3, 0, tzinfo=UTC)
OFFERING = "off-1"


def stamp(moment):
    return moment.isoformat().replace("+00:00", "Z")


def ticket(identifier="t1", *, opens=-2, closes=20, status="PUBLISHED", published=1, offering=OFFERING, question="Nêu một ý chính của bài hôm nay"):
    return {"id": identifier, "session_id": "s1", "offering_id": offering, "status": status, "published_question_revision": published,
            "opens": {"utc": stamp(NOW + timedelta(hours=opens))}, "closes": {"utc": stamp(NOW + timedelta(hours=closes))}, "question": question}


def member(subject, *, role="STUDENT", status="ACTIVE", offering=OFFERING):
    return {"actor_subject_id": subject, "role": role, "status": status, "offering_id": offering}


def state(tickets, members, submissions=()):
    return {"exit_tickets": {t["id"]: t for t in tickets},
            "members": {f"m{i}": m for i, m in enumerate(members)},
            "exit_submissions": {f"{t}:{s}": {"ticket_id": t, "student_id": s} for t, s in submissions},
            "sessions": {"s1": {"id": "s1", "offering_id": OFFERING, "title": "Buổi 3"}}}


def find(s, **kw):
    return open_exit_ticket_deadlines(s, offerings={OFFERING}, now=NOW, **kw)


def test_students_who_have_not_answered_are_listed_for_a_ticket_closing_soon():
    rows = find(state([ticket()], [member("a"), member("b"), member("teacher", role="INSTRUCTOR"), member("gone", status="REMOVED")], [("t1", "b")]))
    assert len(rows) == 1
    assert rows[0]["ticket_id"] == "t1" and rows[0]["students"] == ["a"]
    assert rows[0]["closes"] == NOW + timedelta(hours=20)


@pytest.mark.parametrize("changes", [
    {"closes": 30},                      # beyond the 26-hour window
    {"closes": -1},                      # already closed
    {"opens": 1},                        # not open yet
    {"status": "DRAFT"},
    {"published": None},                 # question never published to students
    {"offering": "other"},               # the class does not have exit tickets switched on
])
def test_tickets_that_are_not_open_soon_or_not_enabled_produce_nothing(changes):
    assert find(state([ticket(**changes)], [member("a"), member("a", offering="other")])) == []


def test_candidates_carry_the_deadline_the_link_and_the_preference_kind():
    rows = find(state([ticket(question="x" * 400)], [member("a")]))
    [candidate] = exit_ticket_candidates(rows)
    assert candidate.recipient == "a" and candidate.item_key == "exit_ticket:t1" and candidate.pref_kind == "exit_tickets"
    assert candidate.deadline == NOW + timedelta(hours=20) and candidate.link == "/learning"
    title, body = candidate.describe(timedelta(hours=20))
    assert "Buổi 3" in title and "khoảng 20 giờ" in body and len(body) < 300


@pytest.fixture
def store(tmp_path):
    return CampusOpsStore(tmp_path / "ops.sqlite3")


def inbox(store, who):
    return [row["title"] for row in store.query("SELECT title FROM ops_notifications WHERE recipient_subject_id=?", (who,))]


def test_two_reminders_once_each_and_none_after_the_student_answers(store):
    s = state([ticket(closes=20)], [member("a"), member("b")])
    # 20 h left: the 24 h reminder is due for both
    assert deliver(store, exit_ticket_candidates(find(s)), now=NOW) == 2
    assert deliver(store, exit_ticket_candidates(find(s)), now=NOW + timedelta(minutes=5)) == 0
    # b answers; 1.5 h before closing only a is reminded
    s["exit_submissions"]["t1:b"] = {"ticket_id": "t1", "student_id": "b"}
    later = NOW + timedelta(hours=18, minutes=30)
    assert deliver(store, exit_ticket_candidates(open_exit_ticket_deadlines(s, offerings={OFFERING}, now=later)), now=later) == 1
    assert len(inbox(store, "a")) == 2 and len(inbox(store, "b")) == 1


def test_a_student_who_switched_the_reminder_off_gets_nothing(store):
    with store.tx() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS ops_reminder_prefs(subject_id TEXT NOT NULL, kind TEXT NOT NULL, enabled INTEGER NOT NULL,
                     updated_at TEXT NOT NULL, PRIMARY KEY(subject_id, kind))""")
        c.execute("INSERT INTO ops_reminder_prefs VALUES ('a','exit_tickets',0,'x')")
    s = state([ticket()], [member("a"), member("b")])
    assert deliver(store, exit_ticket_candidates(find(s)), now=NOW) == 1
    assert inbox(store, "a") == [] and len(inbox(store, "b")) == 1
