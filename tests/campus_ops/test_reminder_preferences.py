"""A person can switch a kind of reminder off and on; the engine respects it without losing the reminder if it is switched back on in time."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from campus247.application.campus_ops.reminders import Candidate, deliver
from campus247.application.campus_ops.service import CampusOpsService
from campus247.domain.shared.values import generate_uuid7
from campus247.infrastructure.repositories.sqlite_campus_ops import CampusOpsStore
from campus247.ports.identity import IdentityContext, IdentityRole
from campus247.presentation.campus_ops import create_campus_ops_router, register_ops_errors
from campus247.presentation.identity import IdentityMiddleware

NOW = datetime(2026, 11, 20, 1, 0, tzinfo=timezone.utc)
H = timedelta(hours=1)


class Adapter:
    def __init__(self):
        self.contexts = {}

    def resolve_token(self, token):
        if token in self.contexts:
            return self.contexts[token]
        raise ValueError("bad token")


@pytest.fixture
def env(tmp_path):
    store = CampusOpsStore(tmp_path / "ops.sqlite3")
    adapter = Adapter()
    now = datetime.now(timezone.utc)
    ids = {}
    for token, code in (("a", "LOCAL-STUDENT-001"), ("b", "SV-B")):
        ids[token] = generate_uuid7()
        adapter.contexts[token] = IdentityContext(ids[token], "ext:" + token, "test", (IdentityRole.STUDENT,), token, now, now + H, student_code=code,
                                                  tenant_id="t", session_id=generate_uuid7())
    app = FastAPI()
    app.add_middleware(IdentityMiddleware, adapter=adapter)
    app.include_router(create_campus_ops_router(CampusOpsService(store)))
    register_ops_errors(app)
    with TestClient(app) as client:
        yield client, store, ids


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def candidate(recipient, kind="exam"):
    return Candidate(item_key="exam:1", recipient=recipient, kind="REMINDER", deadline=NOW, describe=lambda left: ("Sắp thi", "Còn ít giờ"),
                     pref_kind=kind)


def inbox(store, who):
    return store.query("SELECT title FROM ops_notifications WHERE recipient_subject_id=?", (who,))


def test_everything_is_on_by_default(env):
    client, _, _ = env
    assert client.get("/v1/notifications/preferences", headers=auth("a")).json() == {"exam": True, "exit_tickets": True, "sources": True}


def test_switching_off_and_on_is_remembered_per_person(env):
    client, _, _ = env
    assert client.put("/v1/notifications/preferences", headers=auth("a"), json={"exam": False}).json() == {"exam": False, "exit_tickets": True, "sources": True}
    assert client.get("/v1/notifications/preferences", headers=auth("a")).json()["exam"] is False
    assert client.get("/v1/notifications/preferences", headers=auth("b")).json()["exam"] is True  # someone else is unaffected
    assert client.put("/v1/notifications/preferences", headers=auth("a"), json={"exam": True}).json()["exam"] is True


@pytest.mark.parametrize("body", [{}, {"exams": False}, {"exam": "no"}, {"exam": 0}, {"exam": None}, {"exam": True, "other": False}])
def test_bad_bodies_are_refused_and_change_nothing(env, body):
    client, _, _ = env
    reply = client.put("/v1/notifications/preferences", headers=auth("a"), json=body)
    assert reply.status_code in (400, 422)
    assert client.get("/v1/notifications/preferences", headers=auth("a")).json() == {"exam": True, "exit_tickets": True, "sources": True}


def test_it_needs_a_session(env):
    client, _, _ = env
    assert client.get("/v1/notifications/preferences").status_code == 401
    assert client.put("/v1/notifications/preferences", json={"exam": False}).status_code == 401


def test_a_switched_off_kind_sends_nothing_and_can_still_be_sent_after_switching_on(env):
    client, store, ids = env
    client.put("/v1/notifications/preferences", headers=auth("a"), json={"exam": False})
    assert deliver(store, [candidate(ids["a"]), candidate(ids["b"])], now=NOW - 20 * H) == 1  # only b is notified
    assert inbox(store, ids["a"]) == [] and len(inbox(store, ids["b"])) == 1
    client.put("/v1/notifications/preferences", headers=auth("a"), json={"exam": True})
    assert deliver(store, [candidate(ids["a"])], now=NOW - 10 * H) == 1  # not marked as sent while it was off
    assert len(inbox(store, ids["a"])) == 1


def test_switching_off_one_kind_leaves_the_other(env):
    client, store, ids = env
    client.put("/v1/notifications/preferences", headers=auth("a"), json={"sources": False})
    assert deliver(store, [candidate(ids["a"], "exam")], now=NOW - 20 * H) == 1
    assert deliver(store, [candidate(ids["a"], "sources").__class__(item_key="s:1", recipient=ids["a"], kind="REMINDER", deadline=NOW, describe=lambda l: ("x", "y"),
                                                                       pref_kind="sources")], now=NOW - 20 * H) == 0


def test_a_candidate_without_a_kind_cannot_be_switched_off(env):
    client, store, ids = env
    client.put("/v1/notifications/preferences", headers=auth("a"), json={"exam": False, "sources": False})
    plain = Candidate(item_key="x", recipient=ids["a"], kind="REMINDER", deadline=NOW, describe=lambda left: ("t", "b"))
    assert deliver(store, [plain], now=NOW - 20 * H) == 1


def test_the_change_is_audited_without_any_personal_text(env):
    client, store, ids = env
    client.put("/v1/notifications/preferences", headers=auth("a"), json={"exam": False})
    row = store.one("SELECT action, resource, detail FROM ops_audit WHERE action = 'reminders.preferences'")
    assert row["resource"] == ids["a"] and row["detail"] == '{"exam": false}'
