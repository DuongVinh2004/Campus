from dataclasses import replace
import pytest
from fastapi.testclient import TestClient
from campus247.bootstrap.unified_demo import create_unified_demo_app
from campus247.domain.shared.values import generate_uuid7
from tests.integration.test_unified_staff12 import runtime, target, dossier
from tests.api.test_service_stage6 import read, act, sent, login
from tests.unified_workflow13a.test_case_workflow import post, ready, draft_body, prepare, preview, confirmation

def request_supplement(client, staff, record):
    body = draft_body(client, staff, record, operation="request_supplement", outcome="SUPPLEMENT_REQUIRED",
        supplement_items=[{"id": "reason-detail", "criterion_id": "evidence_review", "source_ids": ["payload:reason"],
            "field": "reason", "public_reason": "Bổ sung chi tiết để cán bộ đối chiếu", "accepted_format": "text"}])
    prepare(client, staff, body); p = preview(client, staff, body)
    response = post(client, staff, ":confirm", confirmation(p))
    assert response.status_code == 200, response.text
    return response.json()

def test_structured_supplement_full_roundtrip_delta_and_restart(runtime):
    app, client, student, staff, record, path = runtime
    request_supplement(client, staff, record)
    waiting = read(client, student, record["id"])
    checklist = post(client, student, "/supplement:read", {"resource": target(waiting)}).json()
    request = checklist["current_request"]
    assert "PRIVATE SENTINEL" not in str(checklist)
    assert request["items"][0]["criterion_id"] == "evidence_review"
    response = {"resource": target(waiting), "request_id": request["id"], "request_version": request["version"],
        "client_id": generate_uuid7(), "responses": [{"item_id": "reason-detail", "field": "reason", "value": "Chi tiết mới do sinh viên khai báo"}], "note": "Bổ sung theo đúng item"}
    p = post(client, student, "/supplement:preview", response)
    assert p.status_code == 200, p.text
    assert read(client, student, record["id"])["version"] == waiting["version"]
    c = post(client, student, "/supplement:confirm", confirmation(p.json()))
    assert c.status_code == 200, c.text
    assert post(client, student, "/supplement:confirm", confirmation(p.json())).json()["is_replay"]
    changed = read(client, student, record["id"])
    assert changed["status"] == "VALIDATING"
    d = dossier(client, staff, changed)
    assert "reason" in [v["field"] for v in d["delta"]["changes"]]
    assert "field_reason" in d["delta"]["rechecked"] and "source_binding" in d["delta"]["reused"]
    with TestClient(create_unified_demo_app(path / "business.sqlite3", state_database=path / "state.sqlite3")) as restarted:
        value = post(restarted, student, "/supplement:read", {"resource": target(changed)})
        assert value.status_code == 200, value.text
        assert value.json()["responses"][0]["responses"] == response["responses"]

@pytest.mark.parametrize("drift", ["item", "field", "recipient", "request", "version", "source"])
def test_supplement_boundaries(runtime, drift):
    app, client, student, staff, record, _ = runtime
    request_supplement(client, staff, record)
    waiting = read(client, student, record["id"])
    request = post(client, student, "/supplement:read", {"resource": target(waiting)}).json()["current_request"]
    body = {"resource": target(waiting), "request_id": request["id"], "request_version": request["version"], "client_id": generate_uuid7(),
        "responses": [{"item_id": "reason-detail", "field": "reason", "value": "Chi tiết"}], "note": "Tự khai báo"}
    headers = student
    if drift == "item": body["responses"][0]["item_id"] = "invented"
    if drift == "field": body["responses"][0]["field"] = "recipient"
    if drift == "recipient": headers = login(client, "SV024")
    if drift == "request": body["request_id"] = generate_uuid7()
    if drift == "version": body["request_version"] += 1
    if drift == "source":
        with app.state.service_requests.repository.transaction() as tx:
            value = tx.item("knowledge_version", record["snapshot"]["guidance"]["version_id"])
            value["text"] += "drift"; tx.update("knowledge_version", value)
    r = post(client, headers, "/supplement:preview", body)
    assert r.status_code in {404, 409, 422}, r.text
    assert read(client, student, record["id"])["status"] == "WAITING_STUDENT"

def test_transfer_internal_summary_receipt_projection_and_reauthorization(runtime):
    app, client, student, staff, record, path = runtime
    directory = client.get("/v1/service-staff-directory", headers=staff).json()["items"]
    target_staff = next(v for v in directory if "HUCE_GENERAL" in v["queues"])
    body = draft_body(client, staff, record, operation="transfer", outcome="TRANSFERRED", handover={"done": ["Đã đọc nguồn"],
        "open": ["Cần đối chiếu tiếp"], "evidence_ids": ["payload:reason"], "next_action": "Đối chiếu bằng chứng theo quyền mới",
        "visibility": "internal", "target_queue": "HUCE_GENERAL", "target_actor": target_staff["user_id"]})
    prepare(client, staff, body); p = preview(client, staff, body)
    assert p["public"]["handover"] is None and p["internal"]["handover"]
    r = post(client, staff, ":confirm", confirmation(p)); assert r.status_code == 200, r.text
    assert r.json()["queue"] == "HUCE_GENERAL"
    changed = read(client, student, record["id"])
    public = post(client, student, "/projection:read", {"resource": target(changed)})
    assert public.status_code == 200 and public.json()["handovers"] == []
    assert post(client, staff, "/projection:read", {"resource": target(changed)}).status_code == 404
    with TestClient(create_unified_demo_app(path / "business.sqlite3", state_database=path / "state.sqlite3")) as restarted:
        assert post(restarted, staff, "/receipt:read", {"client_id": p["client_id"]}).json()["receipt"]["queue"] == "HUCE_GENERAL"
        recipient = login(restarted, "OF001")
        value = post(restarted, recipient, "/projection:read", {"resource": target(changed)})
        assert value.status_code == 200, value.text
        assert value.json()["handovers"][0]["summary"]["open"] == ["Cần đối chiếu tiếp"]

def test_projection_event_versions_public_isolation_and_source_refresh(runtime):
    app, client, student, staff, record, _ = runtime
    body = draft_body(client, staff, record, operation="respond", outcome="RESPONDED")
    prepare(client, staff, body); p = preview(client, staff, body)
    r = post(client, staff, ":confirm", confirmation(p)); assert r.status_code == 200
    changed = read(client, student, record["id"])
    a = post(client, student, "/projection:read", {"resource": target(changed)}).json()
    b = post(client, staff, "/projection:read", {"resource": target(changed)}).json()
    assert a["resource"] == b["resource"] and "staff_workspace" not in a
    assert "PRIVATE SENTINEL" not in str(a) and "private_memory" not in str(a)
    events = post(client, student, "/events:read", {"resource": target(changed)}).json()["events"]
    assert events[-1]["version"] == changed["version"] and events[-1]["status"] == changed["status"]
    assert all("note" not in v and "actor_id" not in v for v in events)
    with app.state.service_requests.repository.transaction() as tx:
        source = tx.item("knowledge_version", changed["snapshot"]["guidance"]["version_id"])
        source["text"] += "drift"; tx.update("knowledge_version", source)
    fresh = post(client, student, "/projection:read", {"resource": target(changed)})
    assert fresh.status_code == 200 and fresh.json()["projection_hash"] != a["projection_hash"]
    assert fresh.json()["source_state"] == "unresolved"

def test_staff_intent_exact_action_no_dom_or_multi_case_guess(runtime):
    _, client, student, staff, record, _ = runtime
    for surface, intent in [("queue", "read"), ("detail", "read"), ("checklist", "review"), ("editor", "prepare"), ("error", "retry"), ("handover", "prepare")]:
        r = post(client, staff, "/intent:resolve", {"resources": [target(record)], "surface": surface, "intent": intent})
        assert r.status_code == 200 and r.json()["support"] == "supported"
    r = post(client, staff, "/intent:resolve", {"resources": [], "surface": "editor", "intent": "prepare"})
    assert r.json()["status"] == "needs_clarification"
    r = post(client, staff, "/intent:resolve", {"resources": [target(record)], "surface": "admin", "intent": "publish"})
    assert r.json()["support"] == "unavailable"
    assert post(client, student, "/intent:resolve", {"resources": [target(record)], "surface": "detail", "intent": "read"}).status_code == 403

def test_batch_partial_retry_reads_individual_receipts_and_preserves_scope(runtime):
    app, client, student, staff, first, path = runtime
    _, second, _ = sent(client)
    response = act(client, staff, second, "claim"); assert response.status_code == 200
    second = response.json()["document_request"]
    for record in [first, second]:
        body = draft_body(client, staff, record, operation="respond", outcome="RESPONDED")
        prepare(client, staff, body)
    items = [{"resource": target(r), "draft_version": 1, "client_id": generate_uuid7()} for r in [first, second]]
    batch = post(client, staff, "/batch:prepare", {"client_id": generate_uuid7(), "items": items})
    assert batch.status_code == 200, batch.text
    b = batch.json()
    assert all(v["state"] == "prepared" for v in b["items"])
    assert act(client, staff, second, "respond").status_code == 200
    args = {"batch_id": b["batch_id"], "target_hash": b["target_hash"], "confirmed": True}
    result = post(client, staff, "/batch:confirm", args)
    assert result.status_code == 200, result.text
    assert result.json()["state"] == "partial"
    assert [v["state"] for v in result.json()["results"]] == ["committed", "blocked"]
    version = read(client, student, first["id"])["version"]
    with TestClient(create_unified_demo_app(path / "business.sqlite3", state_database=path / "state.sqlite3")) as restarted:
        retry = post(restarted, staff, "/batch:confirm", args)
        assert retry.json()["results"][0]["is_replay"]
        assert read(restarted, student, first["id"])["version"] == version
    assert post(client, staff, "/batch:confirm", {**args, "target_hash": "0"*64}).status_code == 409

def test_queue_dashboard_scoped_minimized_no_invented_sla_or_active_time(runtime):
    _, client, _, staff, record, _ = runtime
    ready(client, staff, record)
    queue = post(client, staff, "/queue:read", {"kind": "service_request"})
    assert queue.status_code == 200, queue.text
    row = next(v for v in queue.json()["items"] if v["resource"]["id"] == record["id"])
    assert row["group"] == "ready" and row["deadline"] is None
    metrics = post(client, staff, "/dashboard:read", {"kind": "service_request"})
    assert metrics.status_code == 200, metrics.text
    value = metrics.json()
    assert value["groups"]["ready"] == 1 and value["active_work_seconds"] is None and value["system_processing_seconds"] is None
    assert record["student_user_id"] not in str(value) and record["payload"]["reason"] not in str(value)
