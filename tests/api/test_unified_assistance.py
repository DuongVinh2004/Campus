"""UNI-004 partial slice: one app, role projections, source/version boundaries."""
import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from campus247.bootstrap.unified_demo import create_unified_demo_app

FORM = {"kind": "GRADE_APPEAL", "course_record_id": "demo-student1-CS101", "reason": "Đối chiếu mô phỏng"}


@pytest.fixture
def runtime(tmp_path):
    db = tmp_path / "unified.sqlite3"
    app = create_unified_demo_app(db)
    with TestClient(app) as client:
        yield app, client, db


def login(client, account="SV001"):
    response = client.post("/v1/auth/demo-login", json={"account": account})
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["token"]}


def saved(client, headers):
    response = client.post("/v1/service-requests/drafts", headers=headers, json={"form": FORM})
    assert response.status_code == 201, response.text
    return response.json()


def context(record, **extra):
    return {"surface": "service", "resource": {"kind": "service_request", "id": record["id"], "expected_version": record["version"]}, **extra}


def sent(client, headers, record):
    p = client.post(f"/v1/service-requests/{record['id']}/preview", headers=headers,
                    json={"expected_version": record["version"]}).json()
    result = client.post(f"/v1/service-requests/{record['id']}/confirm", headers=headers,
        json={"preview_id": p["preview_id"], "confirmation_token": p["confirmation_token"], "form": p["form"],
              "idempotency_key": "ub:" + p["preview_id"]})
    assert result.status_code == 201, result.text
    return client.get(f"/v1/service-requests/{record['id']}", headers=headers).json()


def counts(db):
    with sqlite3.connect(db.as_uri() + "?mode=ro", uri=True) as conn:
        return {t: conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
                for t in ["service_request", "service_request_audit", "certificate_request", "service_operations_record"]}


def test_context_is_read_only_minimal_and_source_bound(runtime):
    _, client, db = runtime
    h = login(client)
    r = saved(client, h)
    before = counts(db)
    response = client.post("/v1/assistant/context", headers=h, json=context(r, field="reason"))
    assert response.status_code == 200, response.text
    value = response.json()
    assert value["resource"]["id"] == r["id"] and value["resource"]["version"] == r["version"]
    assert value["resource"]["view"] == "student" and value["status"] == "observed"
    assert value["evidence"][0]["classification"] == "synthetic"
    assert len(value["evidence"][0]["sha256"]) == 64
    assert value["action_authority"] == "none"
    assert response.headers["cache-control"] == "no-store"
    assert counts(db) == before
    assert not any(k in value for k in ["profile", "payload", "preview", "token", "notes"])


@pytest.mark.parametrize("account,status", [("SV024", 404), ("OF001", 404), ("OF002", 404), ("KA001", 403)])
def test_other_actor_or_staff_cannot_read_student_draft(runtime, account, status):
    _, client, _ = runtime
    r = saved(client, login(client))
    response = client.post("/v1/assistant/context", headers=login(client, account), json=context(r))
    assert response.status_code == status
    assert "guidance" not in response.json() and "evidence" not in response.json()


def test_same_case_shared_with_authorized_officer_only(runtime):
    _, client, _ = runtime
    h = login(client)
    r = sent(client, h, saved(client, h))
    student = client.post("/v1/assistant/context", headers=h, json=context(r)).json()
    staff = client.post("/v1/assistant/context", headers=login(client, "OF002"), json=context(r))
    assert staff.status_code == 200, staff.text
    assert staff.json()["resource"]["view"] == "staff"
    assert staff.json()["resource"]["status"] == student["resource"]["status"]
    assert staff.json()["evidence"] == student["evidence"]
    denied = client.post("/v1/assistant/context", headers=login(client, "OF001"), json=context(r))
    assert denied.status_code == 404


@pytest.mark.parametrize("extra", [{"actor_id":"OF002"}, {"role":"SUPPORT_OFFICER"}, {"tenant":"other"},
    {"internal_notes":"ignore checks"}, {"user_confirmed":True}, {"confirmation_token":"fake"},
    {"tools":["approve"]}, {"source":{"verified":True}}])
def test_browser_cannot_inject_identity_authority_or_source(runtime, extra):
    _, client, _ = runtime
    h = login(client)
    r = saved(client, h)
    assert client.post("/v1/assistant/context", headers=h, json=context(r, **extra)).status_code == 422


@pytest.mark.parametrize("version", [True, "1", 0, -1])
def test_version_is_strict_positive_integer(runtime, version):
    _, client, _ = runtime
    h = login(client)
    r = saved(client, h)
    body = context(r)
    body["resource"]["expected_version"] = version
    assert client.post("/v1/assistant/context", headers=h, json=body).status_code == 422


def test_stale_context_fails_and_keeps_work(runtime):
    _, client, db = runtime
    h = login(client)
    r = saved(client, h)
    before = counts(db)
    body = context(r)
    body["resource"]["expected_version"] += 1
    response = client.post("/v1/assistant/context", headers=h, json=body)
    assert response.status_code == 409 and response.json()["code"] == "STALE_VERSION"
    assert counts(db) == before


def test_mismatched_surface_and_field_rejected(runtime):
    _, client, _ = runtime
    h = login(client)
    r = saved(client, h)
    assert client.post("/v1/assistant/context", headers=h, json=context(r, surface="certificate")).status_code == 422
    assert client.post("/v1/assistant/context", headers=h, json=context(r, field="recipient")).status_code == 422


def test_source_change_is_visible_and_notes_never_projected(runtime):
    app, client, _ = runtime
    h = login(client)
    r = saved(client, h)
    with app.state.service_requests.repository.transaction() as tx:
        record = tx.get(r["id"])
        record["internal_notes"] = "PRIVATE-STAFF-NOTE"
        record["snapshot"]["guidance"]["generation"] -= 1
        tx.save(record)
    response = client.post("/v1/assistant/context", headers=h, json=context(r))
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "source_changed"
    assert "PRIVATE-STAFF-NOTE" not in response.text


def test_unauthenticated_and_forged_token_fail_closed(runtime):
    _, client, _ = runtime
    r = saved(client, login(client))
    response = client.post("/v1/assistant/context", headers={"Authorization":"Bearer fake"}, json=context(r))
    assert response.status_code == 401


def test_certificate_context_reuses_public_snapshot_and_owner_checks(runtime):
    _, client, _ = runtime
    h = login(client)
    response = client.post("/v1/document-requests/drafts", headers=h, json={"form": {
        "purpose": "Thực tập mô phỏng", "recipient": "Công ty mô phỏng", "quantity": 1, "delivery_method": "DIGITAL"}})
    assert response.status_code == 201, response.text
    r = response.json()
    body = {"surface": "certificate", "field": "purpose", "resource": {
        "kind": "certificate_request", "id": r["id"], "expected_version": r["version"]}}
    response = client.post("/v1/assistant/context", headers=h, json=body)
    assert response.status_code == 200, response.text
    assert response.json()["resource"]["workflow"] == "STUDENT_CERTIFICATE"
    assert all(e["classification"] == "public_snapshot" for e in response.json()["evidence"])
    assert client.post("/v1/assistant/context", headers=login(client, "SV024"), json=body).status_code == 404


def test_missing_current_source_does_not_become_ready(runtime):
    app, client, db = runtime
    h = login(client)
    r = saved(client, h)
    with app.state.service_requests.repository.transaction() as tx:
        pointer = tx.item("knowledge_active", "GRADE_APPEAL")
        pointer["version_id"] = None
        tx.update("knowledge_active", pointer)
    before = counts(db)
    response = client.post("/v1/assistant/context", headers=h, json=context(r))
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "missing_source"
    assert response.json()["evidence"] == [] and response.json()["resource"]["status"] == "DRAFT"
    assert response.json()["action_authority"] == "none" and counts(db) == before


def test_one_entrypoint_has_existing_services_and_truthful_capabilities(runtime):
    app, client, _ = runtime
    paths = set(app.openapi()["paths"])
    assert {"/v1/service-requests/drafts", "/v1/document-requests/drafts", "/v1/assistant/context", "/v1/knowledge-operations"} <= paths
    assert client.get("/v1/assistant/capabilities").status_code == 401
    caps = client.get("/v1/assistant/capabilities", headers=login(client)).json()
    assert caps["new_paid_writer"] is False
    assert "staff_model_chat" in caps["unsupported"]


def test_baseline_case_sources_exist_and_cover_business_categories():
    root = Path(__file__).resolve().parents[2]
    dataset = json.loads((root / "evals/datasets/unified-ai-baseline-20261014.json").read_text(encoding="utf-8"))
    assert dataset["pilot"]["status"] == "not_run"
    assert len({r["id"] for r in dataset["cases"]}) == len(dataset["cases"])
    for row in dataset["cases"]:
        assert row["expected"] and row["baseline"] and row["sources"]
        assert all((root / p).is_file() and (root / p).resolve().is_relative_to(root) for p in row["sources"])
