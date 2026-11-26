"""F6.2/F6.3: the providers for procedure drafts, exit tickets and practice reviews (synthetic data, fixed clock)."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone

from campus247.application.proactive.providers import (ExitTicketProvider, PracticeDueProvider, ProcedureDraftProvider,
                                                       sqlite_learning_snapshot)

NOW = datetime(2026, 11, 26, 9, 0, tzinfo=timezone.utc)
iso = lambda moment: moment.isoformat().replace("+00:00", "Z")


class Store:
    def __init__(self):
        self.db = sqlite3.connect(":memory:")
        self.db.row_factory = sqlite3.Row

    def query(self, sql, params=()):
        return [dict(r) for r in self.db.execute(sql, tuple(params)).fetchall()]


def test_a_procedure_left_idle_for_three_days_becomes_a_reminder_until_it_expires():
    store = Store()
    store.db.execute("CREATE TABLE proc_runs(id, owner_subject_id, procedure_id, state, updated_at, expires_at)")
    rows = [("r1", "s1", "student-certificate", "COLLECTING", iso(NOW - timedelta(days=4)), iso(NOW + timedelta(days=20))),   # idle: yes
            ("r2", "s1", "student-certificate", "COLLECTING", iso(NOW - timedelta(days=1)), iso(NOW + timedelta(days=20))),   # recent
            ("r3", "s1", "student-certificate", "SUBMITTED", iso(NOW - timedelta(days=9)), iso(NOW + timedelta(days=20))),    # sent
            ("r4", "s1", "student-certificate", "STARTED", iso(NOW - timedelta(days=9)), iso(NOW - timedelta(hours=1))),      # expired
            ("r5", "s2", "student-certificate", "STARTED", iso(NOW - timedelta(days=9)), iso(NOW + timedelta(days=2)))]       # not asked for
    store.db.executemany("INSERT INTO proc_runs VALUES(?,?,?,?,?,?)", rows)
    items = list(ProcedureDraftProvider(store, lambda pid: "Giấy xác nhận sinh viên").items(["s1"], NOW))
    assert [(i.key, i.subject_id, i.kind) for i in items] == [("procedure:r1", "s1", "PROCEDURE_DRAFT")]
    assert items[0].title == "Hồ sơ đang làm dở: Giấy xác nhận sinh viên" and items[0].link == "/services/procedures?run=r1"
    assert items[0].due_at == NOW + timedelta(days=20)


def test_without_the_procedures_table_there_is_nothing_and_no_error():
    assert list(ProcedureDraftProvider(Store(), lambda pid: None).items(["s1"], NOW)) == []


def learning_state():
    return {
        "members": {"m1": {"offering_id": "o1", "actor_subject_id": "s1", "role": "STUDENT", "status": "ACTIVE"},
                    "m2": {"offering_id": "o1", "actor_subject_id": "s2", "role": "STUDENT", "status": "ACTIVE"},
                    "m3": {"offering_id": "o1", "actor_subject_id": "t1", "role": "INSTRUCTOR", "status": "ACTIVE"}},
        "exit_tickets": {
            "e1": {"id": "e1", "offering_id": "o1", "status": "PUBLISHED", "opens": {"utc": iso(NOW - timedelta(hours=1))}, "closes": {"utc": iso(NOW + timedelta(hours=2))}},
            "e2": {"id": "e2", "offering_id": "o1", "status": "PUBLISHED", "opens": {"utc": iso(NOW - timedelta(days=2))}, "closes": {"utc": iso(NOW - timedelta(days=1))}},
            "e3": {"id": "e3", "offering_id": "o1", "status": "DRAFT", "opens": {"utc": iso(NOW - timedelta(hours=1))}, "closes": {"utc": iso(NOW + timedelta(hours=2))}}},
        "exit_submissions": {"e1:s2": {}},
        "practice_sets": {"p1": {"id": "p1", "status": "PUBLISHED", "title": "Ôn chương 1"}, "p2": {"id": "p2", "status": "RETIRED", "title": "Cũ"}},
        "practice_items": {"i1": {"id": "i1", "set_id": "p1"}, "i2": {"id": "i2", "set_id": "p1"}, "i3": {"id": "i3", "set_id": "p2"}},
        "practice_reviews": {"i1:s1": {"due_at": iso(NOW - timedelta(hours=3))}, "i2:s1": {"due_at": iso(NOW - timedelta(days=1))},
                             "i3:s1": {"due_at": iso(NOW - timedelta(days=1))}, "i1:s2": {"due_at": iso(NOW + timedelta(days=3))}},
    }


def test_an_open_exit_ticket_reminds_only_students_who_have_not_answered():
    items = list(ExitTicketProvider(lambda: learning_state()).items(["s1", "s2", "t1"], NOW))
    assert [(i.key, i.subject_id) for i in items] == [("exit:e1", "s1")]          # s2 answered, t1 teaches, e2 closed, e3 draft
    assert items[0].due_at == NOW + timedelta(hours=2) and "chưa trả lời" in items[0].reason


def test_due_practice_questions_give_one_low_reminder_per_set():
    items = list(PracticeDueProvider(lambda: learning_state()).items(["s1", "s2"], NOW))
    assert [(i.subject_id, i.title, i.urgency_hint) for i in items] == [("s1", "2 câu ôn tập đến hạn: Ôn chương 1", "LOW")]
    assert items[0].key == "practice:p1:2026-11-25"                                # keyed by the first due day (Vietnam time)


def test_the_learning_snapshot_reads_the_local_store_read_only(tmp_path):
    database = tmp_path / "learning.sqlite3"
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE learning_state (tenant_id TEXT PRIMARY KEY, revision INTEGER NOT NULL, payload TEXT NOT NULL)")
        db.execute("INSERT INTO learning_state VALUES (?, 1, ?)", ("t", json.dumps(learning_state())))
    snapshot = sqlite_learning_snapshot(database, "t")
    assert snapshot()["practice_sets"]["p1"]["title"] == "Ôn chương 1"
    assert sqlite_learning_snapshot(database, "other")() is None
    assert sqlite_learning_snapshot(tmp_path / "missing.sqlite3", "t")() is None
