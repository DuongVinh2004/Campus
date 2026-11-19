from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from campus247.bootstrap.unified_demo import create_unified_demo_app
from campus247.domain.shared.values import generate_uuid7
from tests.api.test_certificate_stage1 import submitted, login, action
from tests.unified_workflow13a.test_case_workflow import post, prepare, preview, confirmation

@pytest.fixture
def certificate(tmp_path):
    app = create_unified_demo_app(tmp_path / "business.sqlite3", state_database=tmp_path / "state.sqlite3")
    with TestClient(app) as client:
        student, identifier = submitted(client)
        staff = login(client, "OF001")
        record = client.get(f"/v1/staff/document-requests/{identifier}", headers=staff).json()
        result = action(client, staff, identifier, "accept", record["version"], "fixture-accept")
        assert result.status_code == 200, result.text
        yield app, client, student, staff, result.json()["document_request"]

def body(client, staff, record, **updates):
    target = {"kind": "certificate_request", "id": record["id"], "expected_version": record["version"]}
    response = client.post("/v1/assistant/staff-workspace/read", headers=staff, json={"resource": target})
    assert response.status_code == 200, response.text
    d = response.json()
    for finding in d["findings"]:
        if finding["layer"] == "officer_review":
            r = client.post("/v1/assistant/staff-workspace/review", headers=staff, json={"resource": target,
                "binding_hash": d["binding_hash"], "criterion_id": finding["id"], "dependency_hash": finding["dependency_hash"],
                "verdict": "checked", "note": "Đã đối chiếu fixture local; không xác nhận quy định trường", "client_id": generate_uuid7()})
            assert r.status_code == 200, r.text
    return {"resource": target, "client_id": generate_uuid7(), "expected_draft_version": 0,
        "student_id": record["student_user_id"], "recipient_id": record["student_user_id"], "operation": "approve", "outcome": "APPROVED",
        "fact_source_ids": ["payload:purpose", "payload:recipient"], "public_reasons": ["Đối chiếu local/synthetic"], "internal_note": "CERT PRIVATE",
        "workflow_version": d["workflow_version"], "template_version": "certificate-outcome-demo-v1", "binding_hash": d["binding_hash"], **updates}

def test_certificate_structured_draft_approval_result_and_staff_notification_route(certificate):
    app, client, student, staff, record = certificate
    b = body(client, staff, record); prepare(client, staff, b); p = preview(client, staff, b)
    r = post(client, staff, ":confirm", confirmation(p)); assert r.status_code == 200, r.text
    latest = client.get(f"/v1/document-requests/{record['id']}", headers=student).json()
    assert latest["status"] == "READY" and latest["result"]["institutional_rules_verified"] is False
    assert "CERT PRIVATE" not in str(latest)
    with app.state.service_requests.repository.transaction() as tx:
        events = app.state.case_workflow.repository.records(tx, "tracking_event")
        event = next(v for v in reversed(events) if v["audience"] == "staff" and v["resource"]["expected_version"] == latest["version"])
    r = post(client, staff, "/notification:open", {"event_id": event["event_id"]})
    assert r.status_code == 200, r.text
    assert r.json()["open_path"] == "/staff?request=" + record["id"]

def test_certificate_supplement_integer_wrong_type_returns422_without_business_effect(certificate):
    _, client, student, staff, record = certificate
    b = body(client, staff, record, operation="request_supplement", outcome="SUPPLEMENT_REQUIRED", supplement_items=[{
        "id": "quantity", "criterion_id": "evidence_review", "source_ids": ["payload:quantity"], "field": "quantity",
        "public_reason": "Xác nhận lại số bản cần dùng", "accepted_format": "integer"}])
    prepare(client, staff, b); p = preview(client, staff, b)
    r = post(client, staff, ":confirm", confirmation(p)); assert r.status_code == 200, r.text
    latest = client.get(f"/v1/document-requests/{record['id']}", headers=student).json()
    target = {**b["resource"], "expected_version": latest["version"]}
    request = post(client, student, "/supplement:read", {"resource": target}).json()["current_request"]
    response = {"resource": target, "request_id": request["id"], "request_version": request["version"], "client_id": generate_uuid7(),
        "responses": [{"item_id": "quantity", "field": "quantity", "value": "wrong type"}], "note": "Xác nhận số bản"}
    r = post(client, student, "/supplement:preview", response)
    assert r.status_code == 422, r.text
    response["responses"][0]["value"] = 2
    r = post(client, student, "/supplement:preview", response); assert r.status_code == 200, r.text
    c = post(client, student, "/supplement:confirm", confirmation(r.json())); assert c.status_code == 200, c.text
    # Certificate supplements return to SUBMITTED by the existing domain
    # contract. A separate explicit officer accept begins validation again.
    assert c.json()["status"] == "SUBMITTED"
    accepted = action(client, staff, record["id"], "accept", c.json()["version"], "fixture-accept-supplement")
    assert accepted.status_code == 200, accepted.text
    latest = client.get(f"/v1/document-requests/{record['id']}", headers=student).json()
    assert latest["status"] == "VALIDATING" and latest["payload"]["quantity"] == 2

def test_certificate_source_drift_after_preview_preserves_supplement(certificate):
    app, client, student, staff, record = certificate
    b = body(client, staff, record, operation="request_supplement", outcome="SUPPLEMENT_REQUIRED", supplement_items=[{
        "id": "purpose", "criterion_id": "purpose_recipient", "source_ids": ["payload:purpose"], "field": "purpose",
        "public_reason": "Đối chiếu mục đích khai báo", "accepted_format": "text"}])
    prepare(client, staff, b); p = preview(client, staff, b); assert post(client, staff, ":confirm", confirmation(p)).status_code == 200
    latest = client.get(f"/v1/document-requests/{record['id']}", headers=student).json()
    target = {**b["resource"], "expected_version": latest["version"]}
    request = post(client, student, "/supplement:read", {"resource": target}).json()["current_request"]
    response = {"resource": target, "request_id": request["id"], "request_version": request["version"], "client_id": generate_uuid7(),
        "responses": [{"item_id": "purpose", "field": "purpose", "value": "Mục đích bổ sung"}], "note": "Xác nhận mục đích"}
    r = post(client, student, "/supplement:preview", response); assert r.status_code == 200, r.text
    original = app.state.certificate_service.guidance_reader
    def drift():
        result = original()
        result["sources"] = [{**source, "version": source["version"] + "-changed"} for source in result["sources"]]
        return result
    app.state.certificate_service.guidance_reader = drift
    c = post(client, student, "/supplement:confirm", confirmation(r.json()))
    assert c.status_code == 409, c.text
    preserved = client.get(f"/v1/document-requests/{record['id']}", headers=student).json()
    assert preserved["status"] == "WAITING_STUDENT" and preserved["version"] == latest["version"]
