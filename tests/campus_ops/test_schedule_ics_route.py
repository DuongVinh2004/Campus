"""GET /v1/students/me/schedule.ics: the caller's own timetable as a calendar file, with the same access rules as the JSON route."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from campus247.application.campus_ops.service import CampusOpsService
from campus247.domain.shared.values import generate_uuid7
from campus247.infrastructure.repositories.sqlite_campus_ops import CampusOpsStore
from campus247.ports.identity import IdentityContext, IdentityRole
from campus247.presentation.campus_ops import create_campus_ops_router, register_ops_errors
from campus247.presentation.identity import IdentityMiddleware

H = timedelta(hours=1)


class Adapter:
    def __init__(self):
        self.contexts = {}

    def resolve_token(self, token):
        if token in self.contexts:
            return self.contexts[token]
        raise ValueError("bad token")


def add(adapter, token, role, code=None):
    now = datetime.now(timezone.utc)
    adapter.contexts[token] = IdentityContext(generate_uuid7(), "ext:" + token, "test", (role,), token, now, now + H,
                                              student_code=code, tenant_id="t", session_id=generate_uuid7())


@pytest.fixture
def env(tmp_path):
    store = CampusOpsStore(tmp_path / "ops.sqlite3")
    adapter = Adapter()
    add(adapter, "student", IdentityRole.STUDENT, "LOCAL-STUDENT-001")
    add(adapter, "other", IdentityRole.STUDENT, "SV-OTHER")
    add(adapter, "officer", IdentityRole.SUPPORT_OFFICER)
    app = FastAPI()
    app.add_middleware(IdentityMiddleware, adapter=adapter)
    app.include_router(create_campus_ops_router(CampusOpsService(store)))
    register_ops_errors(app)  # turns OpsError into the problem response the real runtime returns
    with TestClient(app) as client:
        yield client, store


def rows(store, owner):
    return store.query("SELECT id, kind, course_name, starts_at FROM ops_schedule WHERE owner_key=? AND deleted_at IS NULL ORDER BY starts_at", (owner,))


def around(rows_):
    first = datetime.fromisoformat(rows_[0]["starts_at"].replace("Z", "+00:00"))
    last = datetime.fromisoformat(rows_[-1]["starts_at"].replace("Z", "+00:00"))
    return (first - timedelta(days=1)).isoformat(), (last + timedelta(days=1)).isoformat()


def test_a_student_downloads_their_own_timetable_as_a_valid_calendar(env):
    client, store = env
    mine = rows(store, "LOCAL-STUDENT-001")
    start, end = around(mine)
    reply = client.get("/v1/students/me/schedule.ics", params={"from": start, "to": end}, headers={"Authorization": "Bearer student"})
    assert reply.status_code == 200
    assert reply.headers["content-type"].startswith("text/calendar") and reply.headers["cache-control"] == "no-store"
    assert 'attachment; filename="lich-hoc-campus247.ics"' == reply.headers["content-disposition"]
    text = reply.text
    assert text.startswith("BEGIN:VCALENDAR\r\n") and text.endswith("END:VCALENDAR\r\n")
    assert text.count("BEGIN:VEVENT") == len(mine) == text.count("END:VEVENT") == text.count("DTSTART:") == text.count("UID:")
    assert all(f"UID:{row['id']}@campus247.local" in text for row in mine)


def test_exams_are_marked_and_nobody_else_s_events_leak(env):
    client, store = env
    mine = rows(store, "LOCAL-STUDENT-001")
    exams = [r for r in mine if r["kind"] == "EXAM"]
    start, end = around(mine)
    text = client.get("/v1/students/me/schedule.ics", params={"from": start, "to": end}, headers={"Authorization": "Bearer student"}).text
    assert text.count("SUMMARY:[Thi] ") == len(exams)
    other = client.get("/v1/students/me/schedule.ics", params={"from": start, "to": end}, headers={"Authorization": "Bearer other"}).text
    assert "BEGIN:VEVENT" not in other  # a different student code has no timetable here
    theirs = {r["id"] for r in rows(store, "LOCAL-STUDENT-001")}
    assert not any(f"UID:{identifier}@" in other for identifier in theirs)


def test_a_range_without_events_is_an_empty_but_valid_calendar(env):
    client, _ = env
    text = client.get("/v1/students/me/schedule.ics", params={"from": "2001-01-01T00:00:00Z", "to": "2001-02-01T00:00:00Z"},
                      headers={"Authorization": "Bearer student"}).text
    assert text.startswith("BEGIN:VCALENDAR") and "BEGIN:VEVENT" not in text


@pytest.mark.parametrize(("token", "expected"), [("officer", 403), (None, 401)])
def test_only_students_with_a_session_may_download(env, token, expected):
    client, _ = env
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    reply = client.get("/v1/students/me/schedule.ics", params={"from": "2026-11-01T00:00:00Z", "to": "2026-12-01T00:00:00Z"}, headers=headers)
    assert reply.status_code == expected and "BEGIN:VCALENDAR" not in reply.text


def test_the_range_is_limited_like_the_json_route(env):
    client, _ = env
    reply = client.get("/v1/students/me/schedule.ics", params={"from": "2026-01-01T00:00:00Z", "to": "2028-01-01T00:00:00Z"},
                       headers={"Authorization": "Bearer student"})
    assert reply.status_code == 422 and "BEGIN:VCALENDAR" not in reply.text
