"""C fault regressions for typed supplement, handover and shared projections."""
import pytest

from campus247.application.document_request.certificates import CertificateError
from campus247.domain.shared.values import generate_uuid7
from tests.api.test_service_stage6 import login, read
from tests.integration.test_unified_staff12 import target, dossier
from tests.integration.test_unified_storage_completion import tables
from tests.unified_final.test_security_c import runtime as runtime_fixture
from tests.unified_workflow13a.test_case_continuity import request_supplement
from tests.unified_workflow13a.test_case_workflow import post, draft_body, prepare, preview, confirmation

runtime = runtime_fixture


def supplement_preview(client, student, staff, record):
    request_supplement(client, staff, record)
    waiting = read(client, student, record["id"])
    request = post(client, student, "/supplement:read", {"resource": target(waiting)}).json()["current_request"]
    body = {"resource": target(waiting), "request_id": request["id"], "request_version": request["version"],
            "client_id": generate_uuid7(), "responses": [{"item_id": "reason-detail", "field": "reason", "value": "C synthetic correction"}],
            "note": "C response to exact requested item"}
    response = post(client, student, "/supplement:preview", body)
    assert response.status_code == 200, response.text
    return waiting, body, response.json()


@pytest.mark.parametrize("failure_kind", ["response", "student_receipt"])
def test_supplement_commit_rolls_back_business_and_mapping_when_receipt_fails(runtime, monkeypatch, failure_kind):
    app, client, student, staff, record, path = runtime
    waiting, body, candidate = supplement_preview(client, student, staff, record)
    before = tables(path / "business.sqlite3")
    original = app.state.case_workflow.repository.insert
    def failing_insert(tx, kind, value):
        if kind == failure_kind:
            raise CertificateError(503, "C_SUPPLEMENT_COMMIT_FAILURE", "Synthetic write failure")
        return original(tx, kind, value)
    monkeypatch.setattr(app.state.case_workflow.repository, "insert", failing_insert)
    response = post(client, student, "/supplement:confirm", confirmation(candidate))
    assert response.status_code == 503, response.text
    assert tables(path / "business.sqlite3") == before
    assert read(client, student, record["id"]) == waiting
    monkeypatch.setattr(app.state.case_workflow.repository, "insert", original)
    recovered = post(client, student, "/supplement:confirm", confirmation(candidate))
    assert recovered.status_code == 200, recovered.text
    changed = read(client, student, record["id"])
    assert changed["payload"]["reason"] == body["responses"][0]["value"]
    assert changed["status"] == "VALIDATING"
    replay = post(client, student, "/supplement:confirm", confirmation(candidate))
    assert replay.status_code == 200 and replay.json()["receipt_id"] == recovered.json()["receipt_id"]
    assert read(client, student, record["id"]) == changed


@pytest.mark.parametrize("drift", ["source", "session", "other_student"])
def test_supplement_preview_cannot_be_confirmed_after_scope_or_source_drift(runtime, drift):
    app, client, student, staff, record, path = runtime
    waiting, _, candidate = supplement_preview(client, student, staff, record)
    headers = student
    if drift == "source":
        with app.state.service_requests.repository.transaction() as tx:
            source = tx.item("knowledge_version", record["snapshot"]["guidance"]["version_id"])
            source["text"] += " C source drift"
            tx.update("knowledge_version", source)
    elif drift == "session":
        headers = login(client, "SV001")
    else:
        headers = login(client, "SV024")
    before = tables(path / "business.sqlite3")
    result = post(client, headers, "/supplement:confirm", confirmation(candidate))
    assert result.status_code == {"source": 409, "session": 422, "other_student": 404}[drift], result.text
    assert tables(path / "business.sqlite3") == before
    assert read(client, student, record["id"]) == waiting


def test_student_correction_requires_new_officer_review_before_result(runtime):
    _, client, student, staff, record, _ = runtime
    _, _, candidate = supplement_preview(client, student, staff, record)
    confirmed = post(client, student, "/supplement:confirm", confirmation(candidate))
    assert confirmed.status_code == 200
    changed = read(client, student, record["id"])
    value = dossier(client, staff, changed)
    assert any(f["state"] == "unchecked" for f in value["findings"] if f["layer"] == "officer_review")
    prior = post(client, staff, "/draft:read", {"resource": target(changed)})
    assert prior.status_code == 200
    previous_version = prior.json()["draft"]["version"]
    body = draft_body(client, staff, changed, reviewed=False, expected_draft_version=previous_version)
    saved = prepare(client, staff, body)
    denied = post(client, staff, "/draft:preview", {"resource": target(changed), "draft_version": saved["version"], "client_id": generate_uuid7()})
    assert denied.status_code == 409 and denied.json()["code"] == "OFFICER_REVIEW_REQUIRED"
    assert read(client, student, record["id"]).get("result") is None


def test_internal_handover_text_never_enters_student_projection_or_event_feed(runtime):
    _, client, student, staff, record, _ = runtime
    recipient = next(v for v in client.get("/v1/service-staff-directory", headers=staff).json()["items"] if "HUCE_GENERAL" in v["queues"])
    sentinel = "C-INTERNAL-HANDOVER-DO-NOT-PUBLISH"
    body = draft_body(client, staff, record, operation="transfer", outcome="TRANSFERRED", handover={
        "done": [sentinel], "open": ["C private outstanding evidence"], "evidence_ids": ["payload:reason"],
        "next_action": "Review current authorized source", "visibility": "internal", "target_queue": "HUCE_GENERAL",
        "target_actor": recipient["user_id"]})
    prepare(client, staff, body)
    candidate = preview(client, staff, body)
    assert sentinel not in str(candidate["public"])
    assert post(client, staff, ":confirm", confirmation(candidate)).status_code == 200
    changed = read(client, student, record["id"])
    for route in ["/projection:read", "/events:read"]:
        value = post(client, student, route, {"resource": target(changed)})
        assert value.status_code == 200 and sentinel not in value.text
    assert post(client, staff, "/projection:read", {"resource": target(changed)}).status_code == 404
    received = post(client, login(client, "OF001"), "/projection:read", {"resource": target(changed)})
    assert received.status_code == 200 and sentinel in received.text
