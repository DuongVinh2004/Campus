"""F1.4: routes translate service results and errors; flags close the right routes and keep sent notices readable."""
from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent))
from ann_helpers import NOW, demo_accounts, draft, make_service, person, sid  # noqa: E402

from campus247.application.features.service import FeatureService  # noqa: E402
from campus247.ports.identity import IdentityRole  # noqa: E402
from campus247.presentation.announcements import create_announcements_router, register_announcement_errors  # noqa: E402
from campus247.presentation.features import FeatureGateMiddleware  # noqa: E402

PEOPLE = {"officer": person(sid(1000), IdentityRole.SUPPORT_OFFICER), "student": person(sid(1), IdentityRole.STUDENT), "other": person(sid(30), IdentityRole.STUDENT)}


def build(tmp_path, features=None):
    svc, store, clock = make_service(tmp_path)
    app = FastAPI()
    register_announcement_errors(app)
    app.include_router(create_announcements_router(svc))
    if features is not None:
        app.add_middleware(FeatureGateMiddleware, service=features)

    @app.middleware("http")
    async def who(request, call_next):
        name = request.headers.get("x-user")
        if name:
            request.state.identity = PEOPLE[name]
        return await call_next(request)

    return TestClient(app), svc


def body(**over):
    return {k: v for k, v in draft(**over).items()}


def test_end_to_end_over_http(tmp_path):
    c, _ = build(tmp_path)
    officer, student, other = {"x-user": "officer"}, {"x-user": "student"}, {"x-user": "other"}
    created = c.post("/v1/announcements/drafts", json=body(audience={"groups": [{"class_codes": ["66IT1"]}]}), headers=officer)
    assert created.status_code == 201 and created.headers["cache-control"] == "no-store"
    ann = created.json()["id"]
    assert c.post(f"/v1/announcements/{ann}:audience-preview", headers=officer).json()["total"] == 5
    pv = c.post(f"/v1/announcements/{ann}:publish-preview", headers=officer).json()
    assert pv["summary"]["total"] == 5
    ok = c.post("/v1/announcements:publish-confirm", json={"preview_id": pv["preview_id"], "confirmation_token": pv["confirmation_token"]},
                headers={**officer, "Idempotency-Key": "abc"})
    assert ok.status_code == 200 and ok.json()["status"] == "PUBLISHED"
    inbox = c.get("/v1/announcements/mine", headers=student).json()["items"]
    assert [i["id"] for i in inbox] == [ann] and inbox[0]["read"] is False
    assert c.get(f"/v1/announcements/{ann}", headers=student).json()["body"].startswith("Sinh viên nộp")
    assert c.get(f"/v1/announcements/{ann}", headers=other).status_code == 404
    assert c.get(f"/v1/announcements/{ann}", headers=other).json()["code"] == "ANNOUNCEMENT_NOT_FOUND"
    assert c.get("/v1/announcements/mine", headers=other).json()["items"] == []
    assert c.get(f"/v1/announcements/{ann}/stats", headers=officer).json()["delivered"] == 5
    assert c.get(f"/v1/announcements/{ann}/stats", headers=student).status_code == 404
    assert c.get("/v1/announcements/authored", headers=officer).json()["items"][0]["id"] == ann
    assert c.get("/v1/announcements/authored", headers=student).status_code == 403


def test_validation_error_payload_lists_fields_and_codes(tmp_path):
    c, _ = build(tmp_path)
    r = c.post("/v1/announcements/drafts", json=body(title="ab", links=[{"label": "x", "url": "ftp://x"}]), headers={"x-user": "officer"})
    assert r.status_code == 422 and r.json()["code"] == "ANNOUNCEMENT_INVALID"
    assert {"field": "title", "code": "TITLE_LENGTH"} in r.json()["errors"] and {"field": "links[0]", "code": "LINK_SCHEME"} in r.json()["errors"]


def test_draft_edit_conflict_and_delete(tmp_path):
    c, _ = build(tmp_path)
    h = {"x-user": "officer"}
    created = c.post("/v1/announcements/drafts", json=body(), headers=h).json()
    new = body(title="Tiêu đề đã được sửa lại")
    assert c.put(f"/v1/announcements/{created['id']}/draft", json={**new, "row_version": created["row_version"]}, headers=h).json()["row_version"] == 2
    stale = c.put(f"/v1/announcements/{created['id']}/draft", json={**new, "row_version": 1}, headers=h)
    assert stale.status_code == 409 and stale.json()["code"] == "ANNOUNCEMENT_CONFLICT"
    assert c.delete(f"/v1/announcements/{created['id']}/draft", headers=h).status_code == 200
    assert c.get("/v1/announcements/authored", headers=h).json()["items"] == []


def test_public_list_needs_no_login_and_unauthenticated_inbox_is_401(tmp_path):
    c, svc = build(tmp_path)
    assert c.get("/v1/announcements/public").json() == {"items": [], "next_offset": None}
    assert c.get("/v1/announcements/mine").status_code == 401


def test_flags_close_publishing_routes_but_not_the_inbox(tmp_path):
    flags = FeatureService(env={"CAMPUS247_FEATURES_OFF": ""}, profile_values={"announcements.publish": True, "announcements.inbox": True})
    c, svc = build(tmp_path, flags)
    h = {"x-user": "officer"}
    ann = c.post("/v1/announcements/drafts", json=body(), headers=h).json()["id"]
    pv = c.post(f"/v1/announcements/{ann}:publish-preview", headers=h).json()
    c.post("/v1/announcements:publish-confirm", json={"preview_id": pv["preview_id"], "confirmation_token": pv["confirmation_token"]}, headers={**h, "Idempotency-Key": "z"})
    off = FeatureService(env={"CAMPUS247_FEATURES_OFF": "announcements.publish"}, profile_values={"announcements.inbox": True, "announcements.publish": True})
    c2 = TestClient(_rebuild(svc, off))
    assert c2.post("/v1/announcements/drafts", json=body(), headers=h).json()["code"] == "FEATURE_DISABLED"
    assert c2.get("/v1/announcements/mine", headers={"x-user": "student"}).status_code == 200
    assert c2.get(f"/v1/announcements/{ann}", headers={"x-user": "student"}).status_code == 200
    # inbox off, publish on: the inbox routes close, authoring stays
    only_publish = FeatureService(profile_values={"announcements.publish": True, "announcements.inbox": False})
    c3 = TestClient(_rebuild(svc, only_publish))
    assert c3.get("/v1/announcements/mine", headers={"x-user": "student"}).json()["code"] == "FEATURE_DISABLED"
    assert c3.get("/v1/announcements/authored", headers=h).status_code == 200


def _rebuild(svc, features):
    app = FastAPI()
    register_announcement_errors(app)
    app.include_router(create_announcements_router(svc))
    app.add_middleware(FeatureGateMiddleware, service=features)

    @app.middleware("http")
    async def who(request, call_next):
        name = request.headers.get("x-user")
        if name:
            request.state.identity = PEOPLE[name]
        return await call_next(request)

    return app
