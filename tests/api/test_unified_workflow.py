"""Workflow/source/template binding on new disposable local fixtures only."""
from datetime import datetime, timedelta, timezone
import json
import sqlite3

from fastapi.testclient import TestClient
import pytest

from campus247.bootstrap.unified_demo import create_unified_demo_app
from campus247.application.knowledge.operations import digest
from tests.api.test_service_stage6 import login, draft, sent, candidate, kp, kc, read, act, APPEAL, SUPPORT

PATH = "/v1/assistant/workflows/resolve"


@pytest.fixture
def runtime(tmp_path):
    database = tmp_path / "workflow.sqlite3"
    app = create_unified_demo_app(database)
    with TestClient(app) as client:
        yield app, client, database


def resolve(client, headers, record, **extra):
    return client.post(PATH, headers=headers, json={"resource": {
        "kind": "service_request", "id": record["id"], "expected_version": record["version"]}, **extra})


def table_digest(database):
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as connection:
        return {table: digest(list(connection.execute('SELECT * FROM "' + table + '" ORDER BY rowid')))
                for table in ("service_request", "service_request_audit", "service_operations_record", "certificate_replay")}


@pytest.mark.parametrize("form,officer", [(APPEAL, "OF002"), (SUPPORT, "OF001")])
def test_shared_binding_is_read_only_and_never_completes_reviews(runtime, form, officer):
    _, client, database = runtime
    headers, record, _ = sent(client, form)
    before = table_digest(database)
    student = resolve(client, headers, record)
    staff = resolve(client, login(client, officer), record)
    assert student.status_code == staff.status_code == 200
    assert student.headers["cache-control"] == "no-store"
    left, right = student.json(), staff.json()
    assert left["resource"]["view"] == "student" and right["resource"]["view"] == "staff"
    assert left["binding"] == right["binding"] and left["template"] == right["template"]
    binding = dict(left["binding"])
    checksum = binding.pop("sha256")
    assert checksum == digest(binding)
    assert binding["as_of"] == record["submitted_at"]
    assert left["binding_status"] == "bound" and left["readiness"] == "requires_officer_review"
    assert all(c["required"] and c["status"] == "required" for c in left["mandatory_reviews"])
    assert left["action_authority"] == "none" and left["classification"] == "synthetic"
    assert table_digest(database) == before
    assert not {"payload", "profile", "preview", "token", "messages", "internal_notes"} & left.keys()


@pytest.mark.parametrize("account", ["SV024", "OF001"])
def test_wrong_student_or_queue_is_concealed(runtime, account):
    _, client, _ = runtime
    _, record, _ = sent(client)
    assert resolve(client, login(client, account), record).status_code == 404


def test_staff_cannot_read_private_draft_and_stale_or_unauthenticated_requests_fail(runtime):
    app, client, _ = runtime
    headers = login(client)
    record = draft(client, headers)
    assert resolve(client, login(client, "OF002"), record).status_code == 404
    with TestClient(app) as anonymous:
        assert resolve(anonymous, {}, record).status_code == 401
    assert resolve(client, login(client, "KA001"), record).status_code == 403
    assert resolve(client, headers, {**record, "version": record["version"] + 1}).status_code == 409


@pytest.mark.parametrize("extra", [{"confirmed": True}, {"readiness": "ready"}, {"model_confidence": 1},
    {"source": {"verified": True}}, {"mandatory_reviews": []}, {"actor_id": "OF002"}])
def test_browser_cannot_supply_policy_source_review_or_authority(runtime, extra):
    _, client, _ = runtime
    headers = login(client)
    record = draft(client, headers)
    assert resolve(client, headers, record, **extra).status_code == 422


def test_superseded_snapshot_is_selected_without_switching_to_newest(runtime):
    _, client, _ = runtime
    headers, record, _ = sent(client)
    old = resolve(client, headers, record).json()["binding"]
    editor, reviewer = login(client, "KA001"), login(client, "KA002")
    _, version = candidate(client, editor, reviewer)
    assert kc(client, reviewer, version, kp(client, reviewer, version)).status_code == 200
    package = resolve(client, headers, record).json()
    assert package["binding"] == old
    assert package["current_source_differs"] and package["readiness"] == "requires_officer_review"
    assert package["binding"]["source"]["version_id"] != version["id"]


@pytest.mark.parametrize("change,reason", [("withdrawn", "SOURCE_NOT_APPLICABLE_AT_MILESTONE"),
    ("future", "SOURCE_NOT_APPLICABLE_AT_MILESTONE"), ("review", "SOURCE_REVIEW_UNVERIFIED"),
    ("author_review", "SOURCE_REVIEW_UNVERIFIED"), ("scope", "SOURCE_SCOPE_MISMATCH"),
    ("build", "SOURCE_BUILD_UNVERIFIED"), ("snapshot", "SOURCE_SNAPSHOT_MISMATCH"),
    ("missing", "SOURCE_SNAPSHOT_MISSING")])
def test_missing_invalid_source_or_review_never_produces_template_or_readiness(runtime, change, reason):
    app, client, _ = runtime
    headers, record, _ = sent(client)
    with app.state.service_requests.repository.transaction() as tx:
        raw = tx.get(record["id"])
        source = tx.item("knowledge_version", raw["snapshot"]["guidance"]["version_id"])
        if change == "withdrawn": source["state"] = "WITHDRAWN"
        if change == "future": source["effective_from"] = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        if change == "review": source["reviews"][-1]["verdict"] = "rejected"
        if change == "author_review": source["reviews"][-1]["reviewer"] = source["created_by"]
        if change == "scope": source["campus"] = "OTHER"
        if change == "build": source["build"]["checksum"] = "0" * 64
        if change == "snapshot": raw["snapshot"]["guidance"]["source_sha256"] = "0" * 64
        if change == "missing": raw["snapshot"]["guidance"] = {"unverified": "MISSING_SOURCE"}
        raw["internal_notes"] = "PRIVATE-SENTINEL"
        tx.save(raw)
        tx.update("knowledge_version", source)
    response = resolve(client, headers, record)
    assert response.status_code == 200
    package = response.json()
    assert reason in package["reasons"]
    assert package["binding_status"] == "unresolved" and package["readiness"] == "undetermined"
    assert package["binding"] is None and package["template"] is None
    assert "PRIVATE-SENTINEL" not in response.text


def test_source_hash_failure_remains_an_error_and_unknown_workflow_milestone_stops(runtime):
    app, client, _ = runtime
    headers, record, _ = sent(client)
    with app.state.service_requests.repository.transaction() as tx:
        raw = tx.get(record["id"])
        raw["submitted_at"] = "2020-01-01T00:00:00+00:00"
        tx.save(raw)
    assert resolve(client, headers, record).json()["code"] == "WORKFLOW_VERSION_UNRESOLVED"
    with app.state.service_requests.repository.transaction() as tx:
        raw["submitted_at"] = record["submitted_at"]
        tx.save(raw)
        source = tx.item("knowledge_version", raw["snapshot"]["guidance"]["version_id"])
        source["rendition_sha256"] = "0" * 64
        tx.update("knowledge_version", source)
    response = resolve(client, headers, record)
    assert response.status_code == 409 and response.json()["code"] == "RENDITION_HASH_MISMATCH"


def test_outcome_renderer_uses_bound_template_and_rejects_unknown_outcome_atomically(runtime):
    _, client, database = runtime
    _, record, _ = sent(client, SUPPORT)
    officer = login(client, "OF001")
    response = act(client, officer, record, "claim")
    assert response.status_code == 200
    record = response.json()["document_request"]
    before = table_digest(database)
    response = act(client, officer, record, "resolve", outcome="INVENTED-OFFICIAL-DECISION")
    assert response.status_code == 422 and table_digest(database) == before
    response = act(client, officer, record, "resolve")
    assert response.status_code == 200
    record = response.json()["document_request"]
    package = resolve(client, officer, record).json()
    assert record["result"]["template_version"] == package["template"]["version"]
    assert record["result"]["title"] == package["template"]["title"]
    assert package["readiness"] == "requires_officer_review"
