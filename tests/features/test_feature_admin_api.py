"""F0.6: the admin API — preview, confirm with an idempotency key, audit, and who may call it."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from campus247.application.features.service import FeatureService
from campus247.infrastructure.repositories.sqlite_feature_flags import FeatureStore
from campus247.ports.identity import IdentityContext, IdentityRole
from campus247.presentation.campus_ops import register_ops_errors
from campus247.presentation.features import FeatureGateMiddleware, create_features_router

NOW = datetime.now(timezone.utc)
SUBJECTS = {"admin": ("01900000-0000-7000-8000-00000000000a", IdentityRole.KNOWLEDGE_ADMIN),
            "student": ("01900000-0000-7000-8000-00000000000b", IdentityRole.STUDENT),
            "contrib": ("01900000-0000-7000-8000-00000000000c", IdentityRole.KNOWLEDGE_CONTRIBUTOR)}


def build(tmp_path):
    # A clock that always moves past the 2 s cache window: each request sees the newest overrides.
    ticks = iter(range(0, 10**9, 10))
    svc = FeatureService(store=FeatureStore(tmp_path / "ff.sqlite3"), monotonic=lambda: float(next(ticks)))
    app = FastAPI()
    register_ops_errors(app)
    app.include_router(create_features_router(svc))
    app.add_middleware(FeatureGateMiddleware, service=svc)

    @app.middleware("http")
    async def who(request, call_next):
        name = request.headers.get("x-user")
        if name:
            sid, role = SUBJECTS[name]
            kw = {"student_code": "S1"} if role == IdentityRole.STUDENT else {}
            request.state.identity = IdentityContext(subject_id=sid, external_subject="x", issuer="l", roles=(role,), display_name="x",
                                                     auth_time=NOW, expires_at=NOW + timedelta(hours=1), **kw)
        return await call_next(request)

    @app.get("/v1/rooms/x")
    def rooms():
        return {"rooms": True}

    @app.get("/v1/users/me")
    def me():
        return {"me": True}

    return TestClient(app), svc


def test_admin_flow_changes_the_gate_and_is_audited(tmp_path):
    c, svc = build(tmp_path)
    assert c.get("/v1/rooms/x").status_code == 200
    body = {"value": False, "reason": "Bảo trì phòng tầng 3", "expected_version": 0}
    pv = c.post("/v1/admin/features/rooms.booking/preview", json=body, headers={"x-user": "admin"})
    assert pv.status_code == 200 and pv.json()["impact"]["data_kept"] is True and pv.headers["cache-control"] == "no-store"
    ok = c.post("/v1/admin/features/confirm", json={"preview_id": pv.json()["preview_id"], "confirmation_token": pv.json()["confirmation_token"]},
                headers={"x-user": "admin", "Idempotency-Key": "k-1"})
    assert ok.status_code == 200 and ok.json()["version"] == 1 and ok.json()["value"] is False
    closed = c.get("/v1/rooms/x")
    assert closed.status_code == 404 and closed.json()["code"] == "FEATURE_DISABLED"
    assert c.get("/v1/users/me").status_code == 200
    mine = c.get("/v1/features").json()
    assert mine["features"]["rooms.booking"] is False and mine["version"] == 1 and "chat.answer_cache" not in mine["features"]
    etag = c.get("/v1/features").headers["etag"]
    assert c.get("/v1/features", headers={"If-None-Match": etag}).status_code == 304
    audit = c.get("/v1/admin/features/audit?key=rooms.booking", headers={"x-user": "admin"}).json()["items"]
    assert len(audit) == 1 and str(audit[0]["after"]["value"]).lower() == "false" and audit[0]["by"] == SUBJECTS["admin"][0]
    listing = c.get("/v1/admin/features", headers={"x-user": "admin"}).json()
    item = next(i for i in listing["items"] if i["key"] == "rooms.booking")
    assert item["effective_for_all"] is False and item["off_reasons"] == ["CONFIGURED_OFF"] and item["configured"]["source"] == "override"


@pytest.mark.parametrize("who", ["student", "contrib"])
def test_only_admins_can_use_the_admin_api(tmp_path, who):
    c, _ = build(tmp_path)
    h = {"x-user": who}
    assert c.get("/v1/admin/features", headers=h).status_code == 403
    assert c.post("/v1/admin/features/rooms.booking/preview", json={"value": False, "reason": "x" * 12, "expected_version": 0}, headers=h).status_code == 403
    assert c.get("/v1/admin/features/audit", headers=h).status_code == 403
    assert c.post("/v1/admin/features/confirm", json={"preview_id": "x"}, headers={**h, "Idempotency-Key": "k"}).status_code == 403


def test_error_codes(tmp_path):
    c, _ = build(tmp_path)
    h = {"x-user": "admin"}
    p = lambda key, **b: c.post(f"/v1/admin/features/{key}/preview", json={"reason": "Lý do đủ dài", "expected_version": 0, **b}, headers=h)  # noqa: E731
    assert p("nope.x", value=False).json()["code"] == "FEATURE_UNKNOWN" and p("nope.x", value=False).status_code == 404
    assert p("core.auth", value=False).status_code == 422 and p("core.auth", value=False).json()["code"] == "FEATURE_LOCKED"
    assert p("policy.simulator", value=True).json()["code"] == "FEATURE_DEPENDENCY_OFF"
    assert p("rooms.booking", value="maybe").json()["code"] == "FEATURE_VALUE_INVALID"
    pv = p("rooms.booking", value=False).json()
    no_key = c.post("/v1/admin/features/confirm", json={"preview_id": pv["preview_id"], "confirmation_token": pv["confirmation_token"]}, headers=h)
    assert no_key.status_code == 422
    bad = c.post("/v1/admin/features/confirm", json={"preview_id": pv["preview_id"], "confirmation_token": "bad"}, headers={**h, "Idempotency-Key": "z"})
    assert bad.status_code == 428 and bad.json()["code"] == "CONFIRMATION_REQUIRED"
    assert c.post("/v1/admin/features/confirm", json={"preview_id": "missing", "confirmation_token": "t"}, headers={**h, "Idempotency-Key": "y"}).status_code == 410
    c.post("/v1/admin/features/confirm", json={"preview_id": pv["preview_id"], "confirmation_token": pv["confirmation_token"]}, headers={**h, "Idempotency-Key": "ok"})
    stale = p("rooms.booking", value=True)
    assert stale.status_code == 409 and stale.json()["code"] == "FEATURE_VERSION_CONFLICT"


def test_guests_get_a_public_snapshot_but_no_admin(tmp_path):
    c, _ = build(tmp_path)
    assert c.get("/v1/features").status_code == 200
    assert c.get("/v1/admin/features").status_code == 401
