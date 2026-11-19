"""Real SQLite and HTTP tests; fresh retained databases, no destructive fixtures."""
from __future__ import annotations

import concurrent.futures
from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastapi.testclient import TestClient
from identities import generate_identities

from campus247.bootstrap.certificate_demo import create_certificate_demo_app
from campus247.domain.action.confirmation import ConfirmationTokenService
from campus247.infrastructure.identity.mock import SyntheticIdentityAdapter
from campus247.ports.identity import IdentityRole

FORM = {"purpose": "Nộp hồ sơ thực tập demo", "recipient": "Đơn vị demo", "quantity": 1,
        "delivery_method": "DIGITAL", "attachments": []}


@pytest.fixture
def runtime(tmp_path):
    app = create_certificate_demo_app(tmp_path / "requests.sqlite3")
    with TestClient(app) as client:
        yield app, client, tmp_path / "requests.sqlite3"


def login(client, account="SV001"):
    response = client.post("/v1/auth/demo-login", json={"account": account})
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["token"]}


def draft(client, headers, form=FORM):
    response = client.post("/v1/document-requests/drafts", json={"form": form}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def preview(client, headers, record):
    response = client.post(f"/v1/document-requests/{record['id']}/preview",
                           json={"expected_version": record["version"]}, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def confirm(client, headers, p, key="confirmation-key-001", form=FORM):
    return client.post(f"/v1/document-requests/{p['document_request']['id']}/confirm", headers=headers,
        json={"preview_id": p["preview_id"], "confirmation_token": p["confirmation_token"], "idempotency_key": key, "form": form})


def submitted(client):
    student = login(client)
    record = draft(client, student)
    p = preview(client, student, record)
    response = confirm(client, student, p)
    assert response.status_code == 201, response.text
    return student, record["id"]


def action(client, headers, did, name, version, key, note="", form=None):
    base = "/v1/document-requests" if name == "supplement" else "/v1/staff/document-requests"
    return client.post(f"{base}/{did}/{name}", headers=headers,
        json={"expected_version": version, "idempotency_key": key, "note": note, "form": form})


def test_full_approval_and_result_and_audit_restart(runtime):
    app, client, db = runtime
    student, did = submitted(client)
    staff = login(client, "OF001")
    queue = client.get("/v1/staff/document-requests", headers=staff).json()
    assert queue["items"][0]["id"] == did
    r = queue["items"][0]
    accepted = action(client, staff, did, "accept", r["version"], "accept-key-001")
    assert accepted.status_code == 200
    r = accepted.json()["document_request"]
    approved = action(client, staff, did, "approve", r["version"], "approve-key-001", "Đã kiểm tra dữ liệu mô phỏng")
    assert approved.status_code == 200
    assert approved.json()["document_request"]["status"] == "READY"
    result = client.get(f"/v1/document-requests/{did}/result", headers=student)
    assert result.status_code == 200 and "GIẤY XÁC NHẬN SINH VIÊN" in result.text
    assert "MÔ PHỎNG" not in result.text and "DEMO" not in result.text
    restarted = create_certificate_demo_app(db)
    with TestClient(restarted) as other:
        saved = other.get(f"/v1/document-requests/{did}", headers=student).json()
        assert saved["status"] == "READY"
        assert [e["action"] for e in saved["history"]] == ["draft.saved", "confirmation.prepared", "request.submitted", "request.accept", "request.approve"]
    with app.state.certificate_repository.transaction() as tx:
        assert tx.connection.execute("SELECT COUNT(*) FROM certificate_audit WHERE document_id=?", (did,)).fetchone()[0] == 5


def test_supplement_and_rejection(runtime):
    _, client, _ = runtime
    student, did = submitted(client)
    staff = login(client, "OF001")
    r = client.get(f"/v1/staff/document-requests/{did}", headers=staff).json()
    r = action(client, staff, did, "accept", r["version"], "accept-key-002").json()["document_request"]
    response = action(client, staff, did, "request_supplement", r["version"], "request-info-key-001", "Bổ sung nội dung nơi nộp")
    assert response.status_code == 200
    r = response.json()["document_request"]
    assert r["status"] == "WAITING_STUDENT"
    updated = {**FORM, "recipient": "Đơn vị demo đã bổ sung", "attachments": [{"name": "demo.txt", "content": "Bằng chứng giả lập"}]}
    response = action(client, student, did, "supplement", r["version"], "supplement-key-001", "Đã bổ sung", updated)
    assert response.status_code == 200
    r = response.json()["document_request"]
    assert r["status"] == "SUBMITTED" and r["supplements"][0]["payload"] == updated
    r = action(client, staff, did, "accept", r["version"], "accept-key-003").json()["document_request"]
    response = action(client, staff, did, "reject", r["version"], "reject-key-001", "Không phù hợp mục đích demo")
    assert response.status_code == 200
    assert response.json()["document_request"]["status"] == "REJECTED"
    assert client.get(f"/v1/document-requests/{did}/result", headers=student).status_code == 409


def test_pending_preview_resume_and_confirm_replay_after_restart(runtime):
    _, client, db = runtime
    student = login(client)
    r = draft(client, student)
    p = preview(client, student, r)
    with TestClient(create_certificate_demo_app(db)) as second:
        resume = second.get(f"/v1/document-requests/{r['id']}/preview", headers=student)
        assert resume.status_code == 200 and resume.json()["preview_id"] == p["preview_id"]
        first = confirm(second, student, p)
        assert first.status_code == 201
    with TestClient(create_certificate_demo_app(db)) as third:
        replay = confirm(third, student, p)
        assert replay.status_code == 201 and replay.json()["is_replay"]
        assert replay.json()["document_request_id"] == first.json()["document_request_id"]
        assert len(third.get("/v1/document-requests", headers=student).json()["items"]) == 1
        assert confirm(third, student, p, "different-key-001").status_code == 409


def test_ownership_roles_queue_and_actor_spoofing(runtime):
    _, client, _ = runtime
    student, did = submitted(client)
    other = login(client, "SV024")
    assert client.get(f"/v1/document-requests/{did}", headers=other).status_code == 404
    assert client.get(f"/v1/document-requests/{did}/result", headers=other).status_code == 404
    assert client.get("/v1/staff/document-requests", headers=student).status_code == 403
    assert action(client, student, did, "approve", 3, "student-approve-001", "forged").status_code == 403
    assert client.post("/v1/document-requests/drafts", json={"form": FORM, "actor": "OF001"}, headers=student).status_code == 422
    directory = generate_identities()["records"]
    wrong_uid = next(r["user_id"] for r in directory["role_binding"] if r["role"] == "SUPPORT_OFFICER" and r["scope_key"] == "ACADEMIC_SERVICES")
    adapter = SyntheticIdentityAdapter("campus247-demo-secret-key-huce", tenant_id="huce-local-public")
    wrong = {"Authorization": "Bearer " + adapter.mint_token(wrong_uid)}
    assert client.get("/v1/staff/document-requests", headers=wrong).status_code == 403
    client.cookies.clear()
    assert client.get("/v1/document-requests").status_code == 401


def test_token_mismatch_expiry_new_session(runtime):
    app, client, _ = runtime
    student = login(client)
    r = draft(client, student)
    p = preview(client, student, r)
    assert confirm(client, student, p, form={**FORM, "purpose": "Đã đổi"}).status_code == 422
    assert confirm(client, student, {**p, "preview_id": "wrong-preview"}).status_code == 422
    another_session = login(client)
    assert confirm(client, another_session, p).status_code == 422
    assert client.get(f"/v1/document-requests/{r['id']}/preview", headers=another_session).status_code == 409
    with app.state.certificate_repository.transaction() as tx:
        value = tx.get(r["id"])
        old = value["preview"]
        from campus247.application.document_request.certificates import preview_entity, serial
        expired = replace(preview_entity(old), created_at=datetime.now(timezone.utc)-timedelta(minutes=10), expires_at=datetime.now(timezone.utc)-timedelta(minutes=5))
        value["preview"] = serial(asdict(expired))
        tx.save(value)
    expired_token = ConfirmationTokenService("campus247-secret-signing-key").mint_token(expired)
    assert confirm(client, student, {**p, "confirmation_token": expired_token}).status_code == 422


def test_invalid_state_stale_version_missing_reason(runtime):
    _, client, _ = runtime
    student, did = submitted(client)
    staff = login(client, "OF001")
    r = client.get(f"/v1/staff/document-requests/{did}", headers=staff).json()
    assert action(client, staff, did, "approve", r["version"], "early-approve-001", "ok").status_code == 409
    accepted = action(client, staff, did, "accept", r["version"], "accept-stale-001").json()["document_request"]
    assert action(client, staff, did, "reject", r["version"], "stale-reject-001", "ok").status_code == 409
    assert action(client, staff, did, "reject", accepted["version"], "missing-reason-001").status_code == 422
    assert action(client, student, did, "supplement", accepted["version"], "invalid-supplement-001", "ok", FORM).status_code == 409
    assert client.post("/v1/document-requests/drafts", json={"form": FORM, "document_id": did, "expected_version": accepted["version"]}, headers=student).status_code == 409


def test_idempotency_key_conflict_and_staff_retry(runtime):
    _, client, _ = runtime
    student, did = submitted(client)
    second = preview(client, student, draft(client, student))
    assert confirm(client, student, second).status_code == 409
    staff = login(client, "OF001")
    r = client.get(f"/v1/staff/document-requests/{did}", headers=staff).json()
    first = action(client, staff, did, "accept", r["version"], "accept-retry-001")
    retry = action(client, staff, did, "accept", r["version"], "accept-retry-001")
    assert first.status_code == retry.status_code == 200 and retry.json()["is_replay"]
    assert action(client, staff, did, "reject", r["version"], "accept-retry-001", "changed").status_code == 409


def test_concurrent_confirmation_and_compare_and_swap(runtime):
    app, client, db = runtime
    student = login(client)
    p = preview(client, student, draft(client, student))
    def send(_):
        with TestClient(create_certificate_demo_app(db)) as worker:
            return confirm(worker, student, p).json()
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(send, range(2)))
    assert len({r["document_request_id"] for r in responses}) == 1
    assert sorted(r["is_replay"] for r in responses) == [False, True]
    with app.state.certificate_repository.transaction() as tx:
        assert tx.connection.execute("SELECT COUNT(*) FROM certificate_request").fetchone()[0] == 1


def test_logout_revocation_is_durable(runtime):
    _, client, db = runtime
    student = login(client)
    assert client.post("/v1/auth/logout", headers=student).status_code == 200
    with TestClient(create_certificate_demo_app(db)) as other:
        assert other.get("/v1/users/me", headers=student).status_code == 401


def test_form_validation_guidance_hash_and_assistant(runtime):
    _, client, _ = runtime
    student = login(client)
    for form in ({**FORM, "purpose": " "}, {**FORM, "quantity": 0}, {**FORM, "student_user_id": "forged"}):
        assert client.post("/v1/document-requests/drafts", json={"form": form}, headers=student).status_code == 422
    reply = client.post("/v1/document-assistant", json={"message": "toi muon xin giay xac nhan sinh vien"}, headers=student).json()
    assert reply["missing_fields"] == ["purpose", "recipient"] and reply["requires_explicit_confirmation"]
    assert not client.get("/v1/document-requests", headers=student).json()["items"]
    import hashlib
    for source in reply["guidance"]["sources"]:
        opened = client.get("/v1/certificate-guidance/sources/" + source["id"]).json()
        assert hashlib.sha256(opened["content_text"].encode()).hexdigest() == source["content_sha256"]


def test_retrieval_backend_error_is_propagated(tmp_path):
    def failure(request):
        return httpx.Response(503, json={"detail": "retrieval unavailable"})
    app = create_certificate_demo_app(tmp_path / "proxy.sqlite3", rag_transport=httpx.MockTransport(failure))
    with TestClient(app) as client:
        student = login(client)
        response = client.post("/v1/conversations", headers=student, json={})
        assert response.status_code == 503 and "retrieval unavailable" in response.text


def test_concurrent_staff_decisions_only_one_wins(runtime):
    _, client, db = runtime
    _, did = submitted(client)
    staff = login(client, "OF001")
    current = client.get(f"/v1/staff/document-requests/{did}", headers=staff).json()
    current = action(client, staff, did, "accept", current["version"], "concurrent-accept-001").json()["document_request"]
    def decide(name):
        with TestClient(create_certificate_demo_app(db)) as other:
            return action(other, staff, did, name, current["version"], "concurrent-"+name+"-001", "Quyết định mô phỏng").status_code
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        codes = list(pool.map(decide, ["approve", "reject"]))
    assert sorted(codes) == [200, 409]


def test_original_confirmation_replay_after_supplement_does_not_duplicate(runtime):
    _, client, _ = runtime
    student = login(client)
    p = preview(client, student, draft(client, student))
    did = confirm(client, student, p).json()["document_request_id"]
    staff = login(client, "OF001")
    r = client.get(f"/v1/staff/document-requests/{did}", headers=staff).json()
    r = action(client, staff, did, "accept", r["version"], "replay-accept-001").json()["document_request"]
    r = action(client, staff, did, "request_supplement", r["version"], "replay-request-info-001", "Bổ sung nơi nộp").json()["document_request"]
    assert action(client, student, did, "supplement", r["version"], "replay-supplement-001", "Đã bổ sung", {**FORM, "recipient": "Updated demo"}).status_code == 200
    response = confirm(client, student, p)
    assert response.status_code == 201 and response.json()["is_replay"]
    assert len(client.get("/v1/document-requests", headers=student).json()["items"]) == 1
