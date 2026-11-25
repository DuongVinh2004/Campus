"""F6: real providers over the ops tables, the HTTP routes, and the hand-over from the old exam reminder."""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "announcements"))
from ann_helpers import NOW, demo_accounts, draft, make_service, person, sid  # noqa: E402

from campus247.application.features.service import FeatureService  # noqa: E402
from campus247.application.proactive.engine import ProactiveEngine  # noqa: E402
from campus247.application.proactive.providers import AnnouncementProvider, TicketProvider  # noqa: E402
from campus247.ports.identity import IdentityRole  # noqa: E402
from campus247.presentation.campus_ops import register_ops_errors  # noqa: E402
from campus247.presentation.nudges import create_nudges_router  # noqa: E402

OFFICER = person(sid(1000), IdentityRole.SUPPORT_OFFICER)


def setup(tmp_path):
    svc, store, clock = make_service(tmp_path)
    created = svc.create_draft(OFFICER, draft(requires_ack=True, ack_deadline=(NOW + timedelta(days=2)).isoformat(), priority="URGENT"))
    pv = svc.publish_preview(OFFICER, created["id"])
    svc.publish_confirm(OFFICER, pv["preview_id"], pv["confirmation_token"], "k")
    engine = ProactiveEngine(store, [AnnouncementProvider(store), TicketProvider(store)], clock=clock, subjects=lambda: [sid(n) for n in range(1, 41)])
    return svc, store, clock, engine, created["id"]


def test_announcement_signals_show_up_and_disappear_when_handled(tmp_path):
    svc, store, clock, engine, ann = setup(tmp_path)
    kinds = {i["kind"] for i in engine.today(sid(1))}
    assert kinds == {"ANNOUNCEMENT_ACK"}  # urgent-unread only counts after two hours
    clock.now = NOW + timedelta(hours=3)
    assert {i["kind"] for i in engine.today(sid(1))} == {"ANNOUNCEMENT_ACK", "ANNOUNCEMENT_URGENT_UNREAD"}
    svc.get(person(sid(1), IdentityRole.STUDENT), ann)
    svc.ack(person(sid(1), IdentityRole.STUDENT), ann)
    assert engine.today(sid(1)) == []  # read and acknowledged at the source: no longer a task
    assert engine.today(sid(2)) != []
    assert engine.run_once()["sent"] >= 1


def test_ticket_needing_information_becomes_a_task(tmp_path):
    svc, store, clock, engine, _ = setup(tmp_path)
    with store.tx() as c:
        c.execute("INSERT INTO ops_tickets(id,code,owner_subject_id,owner_display,owner_code,service_kind,title,summary,fields,status,created_at,updated_at,idempotency_key) "
                  "VALUES('t1','TK-1',?,'x','S1','GENERAL_SUPPORT','Xin giấy xác nhận','s','{}','NEED_INFO',?,?,'k')", (sid(3), NOW.isoformat(), NOW.isoformat()))
    assert any(i["kind"] == "TICKET_NEED_INFO" and i["key"] == "ticket:t1" for i in engine.today(sid(3)))
    assert not any(i["key"] == "ticket:t1" for i in engine.today(sid(4)))


def build_client(engine):
    app = FastAPI()
    register_ops_errors(app)
    app.include_router(create_nudges_router(engine))

    @app.middleware("http")
    async def who(request, call_next):
        name = request.headers.get("x-user")
        if name:
            request.state.identity = person(name, IdentityRole.STUDENT)
        return await call_next(request)

    return TestClient(app)


def test_routes_done_snooze_restore_preferences_and_ownership(tmp_path):
    _, _, _, engine, ann = setup(tmp_path)
    c, h = build_client(engine), {"x-user": sid(1)}
    key = c.get("/v1/nudges/today", headers=h).json()["items"][0]["key"]
    assert c.post(f"/v1/nudges/{key}/snooze", json={"hours": 5}, headers=h).status_code == 422
    assert c.post(f"/v1/nudges/{key}/snooze", json={"hours": 3}, headers=h).status_code == 200
    assert c.get("/v1/nudges/today", headers=h).json()["items"] == []
    assert c.post(f"/v1/nudges/{key}/restore", headers=h).status_code == 200
    assert c.post(f"/v1/nudges/{key}/done", headers=h).status_code == 200
    assert c.get("/v1/nudges/today", headers=h).json()["items"] == []
    assert c.post(f"/v1/nudges/{key}/done", headers={"x-user": sid(99)}).status_code == 404  # not their task
    assert c.put("/v1/nudges/preferences", json={"preferences": {"DIGEST": True, "PRACTICE_DUE": True}}, headers=h).json()["preferences"]["DIGEST"] is True
    assert c.put("/v1/nudges/preferences", json={"preferences": {"NOPE": True}}, headers=h).status_code == 422
    assert c.get("/v1/nudges/today").status_code == 401


def test_old_exam_reminder_stops_when_nudges_turn_on():
    off = FeatureService()
    assert off.job_enabled("exam_reminders")
    on = FeatureService(profile_values={"announcements.publish": False, "proactive.nudges": True})
    assert not on.job_enabled("exam_reminders") and on.job_enabled("proactive_nudges") is True
