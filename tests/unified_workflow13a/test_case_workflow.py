"""Fresh local cases only; no provider, UI, retained writer or runtime reload."""
import pytest
from campus247.domain.shared.values import generate_uuid7
from tests.integration.test_unified_staff12 import runtime, target, dossier, review_body
from tests.api.test_service_stage6 import read, act

def post(client, headers, path, body):
    return client.post("/v1/assistant/cases" + path, headers=headers, json=body)

def ready(client, staff, record):
    value = dossier(client, staff, record)
    for finding in value["findings"]:
        if finding["layer"] == "officer_review":
            result = client.post("/v1/assistant/staff-workspace/review", headers=staff,
                json=review_body(record, value, finding["id"]))
            assert result.status_code == 200, result.text
    return dossier(client, staff, record)

def draft_body(client, staff, record, *, reviewed=True, **updates):
    value = ready(client, staff, record) if reviewed else dossier(client, staff, record)
    return {"resource": target(record), "client_id": generate_uuid7(), "expected_draft_version": 0,
        "student_id": record["student_user_id"], "recipient_id": record["student_user_id"],
        "operation": "resolve", "outcome": "UNCHANGED", "fact_source_ids": ["payload:reason"],
        "public_reasons": ["Đã đối chiếu bằng chứng mô phỏng"], "internal_note": "PRIVATE SENTINEL",
        "workflow_version": value["workflow_version"], "template_version": "service-outcome-demo-v1",
        "binding_hash": value["binding_hash"], "supplement_items": [], "handover": None, **updates}

def prepare(client, staff, body):
    response = post(client, staff, "/draft:prepare", body)
    assert response.status_code == 200, response.text
    return response.json()

def preview(client, staff, body, version=1):
    response = post(client, staff, "/draft:preview", {"resource": body["resource"], "draft_version": version, "client_id": generate_uuid7()})
    assert response.status_code == 200, response.text
    return response.json()

def confirmation(value):
    return {k: value[k] for k in ["preview_id", "confirmation_token", "client_id"]} | {"confirmed": True}

def test_prepare_preview_no_business_effect_and_confirm_atomic_receipt(runtime):
    app, client, student, staff, record, path = runtime
    body = draft_body(client, staff, record)
    draft = prepare(client, staff, body)
    assert draft["version"] == 1 and draft["action_authority"] == "none"
    p = preview(client, staff, body)
    assert p["internal"]["note"] == "PRIVATE SENTINEL"
    assert "PRIVATE" not in str(p["public"])
    assert read(client, student, record["id"])["version"] == record["version"]
    response = post(client, staff, ":confirm", confirmation(p))
    assert response.status_code == 200, response.text
    receipt = response.json()
    assert receipt["state"] == "committed" and receipt["status"] == "READY"
    assert post(client, staff, ":confirm", confirmation(p)).json()["is_replay"]
    public = read(client, student, record["id"])
    assert public["version"] == record["version"] + 1 and "PRIVATE" not in str(public)
    assert post(client, staff, "/receipt:read", {"client_id": p["client_id"]}).json()["receipt"]["receipt_id"] == receipt["receipt_id"]

@pytest.mark.parametrize("drift", ["recipient", "source", "template", "case", "student", "operation"])
def test_exact_prepare_bindings(runtime, drift):
    _, client, _, staff, record, _ = runtime
    body = draft_body(client, staff, record)
    if drift == "recipient": body["recipient_id"] = generate_uuid7()
    if drift == "source": body["fact_source_ids"] = ["invented-source"]
    if drift == "template": body["template_version"] = "official-fabricated-v1"
    if drift == "case": body["resource"]["id"] = generate_uuid7()
    if drift == "student": body["student_id"] = generate_uuid7()
    if drift == "operation": body["operation"] = "reject"
    assert post(client, staff, "/draft:prepare", body).status_code in {404, 409, 422}

def test_officer_review_required_and_draft_cas_preserved(runtime):
    _, client, _, staff, record, _ = runtime
    body = draft_body(client, staff, record, reviewed=False)
    prepare(client, staff, body)
    assert post(client, staff, "/draft:preview", {"resource": target(record), "draft_version": 1, "client_id": generate_uuid7()}).status_code == 409
    changed = {**body, "client_id": generate_uuid7(), "internal_note": "new"}
    assert post(client, staff, "/draft:prepare", changed).status_code == 409
    assert post(client, staff, "/draft:read", {"resource": target(record)}).json()["draft"]["body"] == body

@pytest.mark.parametrize("drift", ["profile", "source", "review", "record", "draft", "assignment"])
def test_confirm_revalidates_all_dependencies_and_preserves_draft(runtime, drift):
    app, client, student, staff, record, _ = runtime
    body = draft_body(client, staff, record)
    prepare(client, staff, body); p = preview(client, staff, body)
    if drift == "profile":
        old = app.state.service_requests.profile_reader
        app.state.service_requests.profile_reader = lambda owner: {**old(owner), "display_name": "fixture drift"}
    elif drift == "source":
        with app.state.service_requests.repository.transaction() as tx:
            source = tx.item("knowledge_version", record["snapshot"]["guidance"]["version_id"])
            source["text"] += "fixture drift"; tx.update("knowledge_version", source)
    elif drift == "review":
        value = dossier(client, staff, record)
        response = client.post("/v1/assistant/staff-workspace/review", headers=staff, json=review_body(record, value, note="Changed review"))
        assert response.status_code == 200
    elif drift == "record":
        assert act(client, staff, record, "respond").status_code == 200
    elif drift == "draft":
        prepare(client, staff, {**body, "client_id": generate_uuid7(), "expected_draft_version": 1})
    elif drift == "assignment":
        with app.state.service_requests.repository.transaction() as tx:
            r = tx.get(record["id"]); r["assigned_user_id"] = generate_uuid7(); tx.save(r)
    response = post(client, staff, ":confirm", confirmation(p))
    assert response.status_code in {404, 409}, response.text
    with app.state.service_requests.repository.transaction() as tx:
        assert app.state.case_workflow.repository.records(tx, "draft")
        assert not app.state.case_workflow.repository.records(tx, "receipt")

def test_session_revoke_and_new_key_cannot_replay_consumed_preview(runtime):
    app, client, _, staff, record, _ = runtime
    body = draft_body(client, staff, record); prepare(client, staff, body); p = preview(client, staff, body)
    first = post(client, staff, ":confirm", confirmation(p)); assert first.status_code == 200, first.text
    assert post(client, staff, ":confirm", {**confirmation(p), "client_id": generate_uuid7()}).status_code == 409
    app.state.service_requests.repository.revoke(app.state.current_session_service.hash_token(staff["Authorization"].split(" ")[1]))
    assert post(client, staff, "/receipt:read", {"client_id": p["client_id"]}).status_code == 401

@pytest.mark.parametrize("value", [1, 1.0, False, "true", None])
def test_only_exact_json_boolean_true_confirms(runtime, value):
    _, client, student, staff, record, _ = runtime
    body = draft_body(client, staff, record); prepare(client, staff, body); p = preview(client, staff, body)
    assert post(client, staff, ":confirm", {**confirmation(p), "confirmed": value}).status_code == 422
    assert read(client, student, record["id"])["version"] == record["version"]
    assert post(client, staff, "/batch:confirm", {"batch_id": generate_uuid7(), "target_hash": "0"*64, "confirmed": value}).status_code == 422
