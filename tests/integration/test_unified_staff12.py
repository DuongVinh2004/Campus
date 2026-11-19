"""U5 HTTP, exact contracts, source drift and actual cross-process SQLite checks.

All mutations are on new fixtures under this batch; no browser/provider calls.
"""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys
import time

import pytest
from fastapi.testclient import TestClient
from campus247.application.assistance.staff_contracts import StaffRead, StaffReview, StaffSourceRead, StaffDossier
from campus247.application.assistance.state_storage import StorageConflict
from campus247.application.document_request.certificates import CertificateError
from campus247.bootstrap.unified_demo import create_unified_demo_app
from campus247.domain.shared.values import generate_uuid7
from campus247.infrastructure.identity.mock import SyntheticIdentityAdapter
from tests.api.test_service_stage6 import login, sent, act, read
from tests.integration.test_unified_storage_completion import tables, draft_body
from tests.integration.test_unified_storage_completion import main_runtime as native_fixture

ROOT = Path(__file__).resolve().parents[2]
main_runtime = native_fixture


@pytest.fixture
def runtime(tmp_path):
    app = create_unified_demo_app(tmp_path / "business.sqlite3", state_database=tmp_path / "state.sqlite3")
    with TestClient(app) as client:
        student, record, _ = sent(client)
        staff = login(client, "OF002")
        response = act(client, staff, record, "claim")
        assert response.status_code == 200, response.text
        record = response.json()["document_request"]
        yield app, client, student, staff, record, tmp_path


def target(record):
    return {"kind": "service_request", "id": record["id"], "expected_version": record["version"]}


def dossier(client, headers, record):
    response = client.post("/v1/assistant/staff-workspace/read", headers=headers, json={"resource": target(record)})
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    value = response.json()
    assert StaffDossier.model_validate(value).model_dump(mode="json") == value
    assert value["action_authority"] == "none"
    return value


def review_body(record, value, criterion=None, verdict="checked", **changes):
    finding = next(f for f in value["findings"] if f["id"] == criterion) if criterion else next(f for f in value["findings"] if f["layer"] == "officer_review")
    return {"resource": target(record), "binding_hash": value["binding_hash"], "criterion_id": finding["id"],
        "dependency_hash": finding["dependency_hash"], "verdict": verdict, "note": "Cán bộ đã đọc và đối chiếu bản nguồn mô phỏng này",
        "client_id": generate_uuid7(), **changes}


def identity(client):
    token = client.post("/v1/auth/demo-login", json={"account": "OF002"}).json()["token"]
    return SyntheticIdentityAdapter("campus247-demo-secret-key-huce", environment="development", tenant_id="huce-local-public").resolve_token(token)


def test_dossier_sources_all_locators_exact_private_and_no_business_effect(runtime):
    _, client, student, staff, record, path = runtime
    before = tables(path / "business.sqlite3")
    value = dossier(client, staff, record)
    assert value["purpose"] == record["payload"]["reason"] and value["student_id"] == record["student_user_id"]
    assert value["classification"] == "synthetic" and value["readiness"] == "needs_verification"
    assert value["ai_proposals"] == [] and value["ai_state"] == "unavailable"
    assert all(f["state"] == "unchecked" for f in value["findings"] if f["layer"] == "officer_review")
    for ref in value["sources"]:
        response = client.post("/v1/assistant/staff-workspace/source", headers=staff, json={"resource": target(record), "binding_hash": value["binding_hash"], "source_id": ref["id"]})
        assert response.status_code == 200, response.text
        assert response.json()["source"] == ref
    for suffix in ("read", "source"):
        body = {"resource": target(record)}
        if suffix == "source": body.update(binding_hash=value["binding_hash"], source_id="profile")
        assert client.post("/v1/assistant/staff-workspace/" + suffix, headers=student, json=body).status_code == 403
    public = read(client, student, record["id"])
    assert "findings" not in public and "reviews" not in public and "staff_workspace" not in public
    after = tables(path / "business.sqlite3")
    for table in before:
        if table != "service_operations_record": assert after[table] == before[table]


def test_explicit_reviews_required_readiness_receipt_and_restart(runtime):
    _, client, _, staff, record, path = runtime
    value = dossier(client, staff, record)
    for finding in value["findings"]:
        if finding["layer"] != "officer_review": continue
        body = review_body(record, value, finding["id"])
        first = client.post("/v1/assistant/staff-workspace/review", headers=staff, json=body)
        assert first.status_code == 200 and first.json()["saved"]
        assert client.post("/v1/assistant/staff-workspace/review", headers=staff, json=body).json()["is_replay"]
        assert client.post("/v1/assistant/staff-workspace/review", headers=staff, json={**body, "note": "Different intent"}).status_code == 409
    value = dossier(client, staff, record)
    assert value["readiness"] == "ready" and not value["reasons"]
    assert all(f["reviewed_by"] == record["assigned_user_id"] for f in value["findings"] if f["layer"] == "officer_review")
    with TestClient(create_unified_demo_app(path / "business.sqlite3", state_database=path / "state.sqlite3")) as restarted:
        restored = dossier(restarted, staff, record)
        assert restored["findings"] == value["findings"] and restored["readiness"] == "ready"
    assert read(client, staff, record["id"], staff=True)["status"] == "VALIDATING"


@pytest.mark.parametrize("verdict,readiness", [("missing_source", "missing"), ("conflicting", "blocked")])
def test_officer_records_uncertainty_without_synthetic_pass_or_rejection(runtime, verdict, readiness):
    _, client, _, staff, record, _ = runtime
    value = dossier(client, staff, record)
    response = client.post("/v1/assistant/staff-workspace/review", headers=staff, json=review_body(record, value, verdict=verdict))
    assert response.status_code == 200
    assert dossier(client, staff, record)["readiness"] == readiness
    assert read(client, staff, record["id"], staff=True)["status"] == "VALIDATING"


@pytest.mark.parametrize("boundary", ["tenant", "queue", "role", "expired", "session", "inactive", "student", "case", "version"])
def test_server_scope_boundaries_fail_closed(runtime, boundary):
    app, client, _, _, record, path = runtime
    actor = identity(client); request = StaffRead(resource=target(record))
    if boundary == "tenant": actor = replace(actor, tenant_id="other-tenant")
    elif boundary == "queue": actor = replace(actor, unit_ids=("HUCE_GENERAL",))
    elif boundary == "role": actor = replace(actor, roles=())
    elif boundary == "expired": actor = replace(actor, auth_time=datetime.now(timezone.utc) - timedelta(days=1), expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
    elif boundary == "session": actor = replace(actor, session_id="")
    elif boundary == "inactive":
        from campus247.ports.identity import AccountState
        actor = replace(actor, account_state=AccountState.SUSPENDED)
    elif boundary == "case": request = StaffRead(resource={**target(record), "id": generate_uuid7()})
    elif boundary == "version": request = StaffRead(resource={**target(record), "expected_version": record["version"] + 1})
    elif boundary == "student":
        actor = replace(actor, subject_id=record["student_user_id"])
    before = tables(path / "business.sqlite3")
    with pytest.raises(CertificateError): app.state.staff_workspace.prepare(actor, request)
    assert tables(path / "business.sqlite3") == before


@pytest.mark.parametrize("operation", ["source", "review"])
def test_stale_binding_cannot_open_source_or_record_review(runtime, operation):
    _, client, _, staff, record, _ = runtime
    value = dossier(client, staff, record)
    if operation == "source": body = {"resource": target(record), "source_id": "profile", "binding_hash": "0" * 64}
    else: body = review_body(record, value, binding_hash="0" * 64)
    assert client.post("/v1/assistant/staff-workspace/" + operation, headers=staff, json=body).status_code == 409


def test_source_and_profile_drift_invalidate_cached_findings_and_draft(runtime):
    app, client, _, staff, record, _ = runtime
    value = dossier(client, staff, record)
    body = review_body(record, value)
    assert client.post("/v1/assistant/staff-workspace/review", headers=staff, json=body).status_code == 200
    assert client.post("/v1/assistant/staff-drafts/save", headers=staff, json=draft_body(record)).status_code == 201
    old_reader = app.state.service_requests.profile_reader
    app.state.service_requests.profile_reader = lambda owner: {**old_reader(owner), "display_name": "Changed fixture profile"}
    changed = dossier(client, staff, record)
    assert changed["readiness"] == "blocked"
    assert next(f for f in changed["findings"] if f["id"] == "profile_snapshot")["state"] == "conflicting"
    assert any(f["state"] == "unchecked" for f in changed["findings"] if f["layer"] == "officer_review")
    saved = client.post("/v1/assistant/staff-drafts/read", headers=staff, json={"resource": target(record)}).json()
    assert saved["binding_stale"] and saved["text"]
    with app.state.service_requests.repository.transaction() as tx:
        version = tx.item("knowledge_version", record["snapshot"]["guidance"]["version_id"])
        version["text"] += " drift"; tx.update("knowledge_version", version)
    drift = dossier(client, staff, record)
    assert drift["binding_hash"] != changed["binding_hash"] and drift["readiness"] in {"missing", "blocked"}
    assert not any(s["kind"] == "workflow" for s in drift["sources"])
    assert read(client, staff, record["id"], staff=True)["status"] == "VALIDATING"


def test_supplement_delta_rechecks_only_impacted_rules_and_keeps_diff(runtime):
    _, client, student, staff, record, _ = runtime
    initial = dossier(client, staff, record)
    assert client.post("/v1/assistant/staff-workspace/review", headers=staff, json=review_body(record, initial)).status_code == 200
    waiting = act(client, staff, record, "request_information").json()["document_request"]
    assert dossier(client, staff, waiting)["readiness"] == "waiting"
    form = {**waiting["payload"], "reason": "Bổ sung lý do mới từ sinh viên"}
    preview = client.post(f"/v1/service-requests/{record['id']}/preview", headers=student, json={"expected_version": waiting["version"], "form": form, "note": "Bổ sung"})
    assert preview.status_code == 200, preview.text
    p = preview.json()
    confirmed = client.post(f"/v1/service-requests/{record['id']}/confirm", headers=student,
        json={"preview_id": p["preview_id"], "confirmation_token": p["confirmation_token"], "idempotency_key": "supplement:" + p["preview_id"], "form": p["form"]})
    assert confirmed.status_code == 201, confirmed.text
    supplemented = read(client, staff, record["id"], staff=True)
    value = dossier(client, staff, supplemented)
    assert "field_reason" in value["delta"]["rechecked"]
    assert "field_course_record_id" in value["delta"]["reused"] and "source_binding" in value["delta"]["reused"]
    assert value["delta"]["changes"] == [{"field": "reason", "before": waiting["payload"]["reason"], "after": form["reason"]}]
    assert all(f["state"] == "unchecked" for f in value["findings"] if f["layer"] == "officer_review")
    assert dossier(client, staff, supplemented)["delta"]["changes"] == value["delta"]["changes"]
    assert client.post("/v1/assistant/staff-workspace/review", headers=staff, json=review_body(record, initial)).status_code == 409


def test_transfer_and_revoke_invalidate_pending_review_draft_response_and_replay(runtime):
    _, client, _, staff, record, path = runtime
    value = dossier(client, staff, record); pending = review_body(record, value)
    draft = draft_body(record)
    assert client.post("/v1/assistant/staff-drafts/save", headers=staff, json=draft).status_code == 201
    before = tables(path / "state.sqlite3")
    target_user = next(r for r in client.get("/v1/service-staff-directory", headers=staff).json()["items"] if "HUCE_GENERAL" in r["queues"])
    moved = act(client, staff, record, "transfer", target_user_id=target_user["user_id"], target_queue="HUCE_GENERAL")
    assert moved.status_code == 200
    for suffix, body in [("staff-workspace/review", pending), ("staff-drafts/save", draft)]:
        assert client.post("/v1/assistant/" + suffix, headers=staff, json=body).status_code == 404
    assert act(client, staff, record, "respond").status_code == 404
    assert tables(path / "state.sqlite3") == before
    incoming = login(client, "OF001"); latest = moved.json()["document_request"]
    assert client.post("/v1/auth/logout", headers=incoming).status_code == 200
    assert client.post("/v1/assistant/staff-workspace/read", headers=incoming, json={"resource": target(latest)}).status_code == 401
    assert act(client, incoming, latest, "respond").status_code == 401


def test_revalidation_runs_after_waiting_for_business_lock(runtime):
    app, client, _, _, record, _ = runtime
    actor = identity(client)
    def revoked(_): raise CertificateError(401, "SESSION_REVOKED", "Revoked while waiting")
    with pytest.raises(CertificateError, match="Revoked"):
        app.state.staff_drafts.save(actor, target(record), "Keep unsaved text", 0, generate_uuid7(), revalidate=revoked)
    with pytest.raises(CertificateError, match="Revoked"):
        app.state.service_requests.act(actor, record["id"], "respond", record["version"], "late-session", "Not sent", revalidate=revoked)


def test_concurrent_review_idempotency_and_draft_cas_restart_readback(runtime):
    app, client, _, staff, record, path = runtime
    actor = identity(client); value = dossier(client, staff, record)
    body = StaffReview.model_validate(review_body(record, value))
    with ThreadPoolExecutor(max_workers=2) as pool:
        receipts = list(pool.map(lambda _: app.state.staff_workspace.review(actor, body), range(2)))
    assert sorted(r["is_replay"] for r in receipts) == [False, True]
    def save(text):
        try: return app.state.staff_drafts.save(actor, target(record), text, 0, generate_uuid7())
        except StorageConflict: return "conflict"
    with ThreadPoolExecutor(max_workers=2) as pool: outcomes = list(pool.map(save, ["Tab A retained", "Tab B retained"]))
    assert sum(o == "conflict" for o in outcomes) == 1
    restarted = create_unified_demo_app(path / "business.sqlite3", state_database=path / "state.sqlite3")
    saved = restarted.state.staff_drafts.read(actor, target(record))
    assert saved["saved"] and saved["text"] in {"Tab A retained", "Tab B retained"}
    assert len(tables(path / "state.sqlite3")["unified_state_receipt"]) == 1


def test_legacy_staff_draft_payload_remains_readable_without_rewrite(runtime):
    from campus247.application.assistance.state_storage import StateScope, StaffDraftSnapshot
    from campus247.application.assistance.workflow import WorkflowResolveRequest
    app, client, _, _, record, path = runtime
    actor = identity(client)
    snapshot = StaffDraftSnapshot(resource=app.state.staff_drafts.workflow.resolve(actor, WorkflowResolveRequest(resource=target(record))),
        assigned_actor=actor.subject_id, queue=record["queue"], text="Legacy private draft")
    payload = snapshot.model_dump(mode="json")
    assert "input_sha256" not in payload
    app.state.actor_state_store.commit(StateScope("huce-local-public", actor.subject_id), "staff_draft", record["id"], 0, payload, generate_uuid7())
    before = tables(path / "state.sqlite3")
    value = app.state.staff_drafts.read(actor, target(record))
    assert value["saved"] and value["binding_stale"] and value["text"] == "Legacy private draft"
    assert tables(path / "state.sqlite3") == before


def test_corrupt_cache_fails_closed_without_repair_or_business_transition(runtime):
    app, client, _, staff, record, path = runtime
    dossier(client, staff, record)
    with app.state.service_requests.repository.transaction() as tx:
        row = tx.items("staff_workspace")[0]; row["findings"][0]["state"] = "checked"; row["binding_hash"] = "0" * 64
        tx.update("staff_workspace", row)
    before = tables(path / "business.sqlite3")
    response = client.post("/v1/assistant/staff-workspace/read", headers=staff, json={"resource": target(record)})
    assert response.status_code == 503 and response.json()["code"] == "STAFF_CACHE_CORRUPT"
    assert tables(path / "business.sqlite3") == before


def test_review_receipt_preserves_provenance_and_corruption_is_not_replayed(runtime):
    app, client, _, staff, record, path = runtime
    value = dossier(client, staff, record); body = review_body(record, value)
    response = client.post("/v1/assistant/staff-workspace/review", headers=staff, json=body)
    assert response.status_code == 200
    assert response.json()["review"]["actor"] == record["assigned_user_id"]
    assert response.json()["review"]["note"] == body["note"]
    with app.state.service_requests.repository.transaction() as tx:
        receipt = tx.items("staff_review_receipt")[0]; receipt["saved"] = False; tx.update("staff_review_receipt", receipt)
    before = tables(path / "business.sqlite3")
    repeated = client.post("/v1/assistant/staff-workspace/review", headers=staff, json=body)
    assert repeated.status_code == 503 and repeated.json()["code"] == "STAFF_RECEIPT_CORRUPT"
    assert tables(path / "business.sqlite3") == before


def test_missing_source_keeps_private_draft_readable_and_stale(runtime):
    app, client, _, staff, record, _ = runtime
    assert client.post("/v1/assistant/staff-drafts/save", headers=staff, json=draft_body(record)).status_code == 201
    with app.state.service_requests.repository.transaction() as tx:
        source = tx.item("knowledge_version", record["snapshot"]["guidance"]["version_id"])
        source["rendition_sha256"] = "0" * 64; tx.update("knowledge_version", source)
    saved = client.post("/v1/assistant/staff-drafts/read", headers=staff, json={"resource": target(record)})
    assert saved.status_code == 200 and saved.json()["text"] and saved.json()["binding_stale"]
    assert saved.json()["action_authority"] == "none"


def test_course_snapshot_drift_invalidates_review_and_private_draft(runtime):
    app, client, _, staff, record, _ = runtime
    value = dossier(client, staff, record)
    assert client.post("/v1/assistant/staff-drafts/save", headers=staff, json=draft_body(record)).status_code == 201
    assert client.post("/v1/assistant/staff-workspace/review", headers=staff, json=review_body(record, value, "course_eligibility")).status_code == 200
    with app.state.service_requests.repository.transaction() as tx:
        changed = tx.get(record["id"]); changed["snapshot"]["course"]["score"] = "Changed synthetic snapshot"; tx.save(changed)
    fresh = dossier(client, staff, record)
    assert fresh["binding_hash"] != value["binding_hash"]
    assert next(f for f in fresh["findings"] if f["id"] == "course_eligibility")["state"] == "unchecked"
    assert "field_reason" in fresh["delta"]["reused"]
    saved = client.post("/v1/assistant/staff-drafts/read", headers=staff, json={"resource": target(record)})
    assert saved.status_code == 200 and saved.json()["binding_stale"] and saved.json()["text"]


def test_certificate_sources_review_and_reader_failure_are_typed(runtime):
    from tests.api.test_certificate_stage1 import submitted, action
    app, client, _, _, _, _ = runtime
    _, identifier = submitted(client); headers = login(client, "OF001")
    current = client.get(f"/v1/staff/document-requests/{identifier}", headers=headers).json()
    accepted = action(client, headers, identifier, "accept", current["version"], "staff12-accept")
    assert accepted.status_code == 200, accepted.text
    record = accepted.json()["document_request"]
    resource = {"kind": "certificate_request", "id": identifier, "expected_version": record["version"]}
    response = client.post("/v1/assistant/staff-workspace/read", headers=headers, json={"resource": resource})
    assert response.status_code == 200, response.text
    value = response.json()
    assert value["readiness"] == "needs_verification" and value["purpose"] == record["payload"]["purpose"]
    for source in value["sources"]:
        result = client.post("/v1/assistant/staff-workspace/source", headers=headers, json={"resource": resource,
            "binding_hash": value["binding_hash"], "source_id": source["id"]})
        assert result.status_code == 200 and result.json()["source"] == source
    def unavailable(): raise OSError("fixture source read failure")
    app.state.certificate_service.guidance_reader = unavailable
    result = client.post("/v1/assistant/staff-workspace/read", headers=headers, json={"resource": resource})
    assert result.status_code == 200, result.text
    assert next(f for f in result.json()["findings"] if f["id"] == "source_binding")["state"] == "error"
    assert result.json()["readiness"] == "blocked"
    assert client.get(f"/v1/staff/document-requests/{identifier}", headers=headers).json()["status"] == "VALIDATING"


def test_timeout_and_input_limits_leave_no_prepared_cache(runtime, monkeypatch):
    import campus247.application.assistance.staff_workspace as module
    app, client, _, staff, record, path = runtime
    before = tables(path / "business.sqlite3"); ticks = iter([0, 3])
    monkeypatch.setattr(module, "monotonic", lambda: next(ticks))
    response = client.post("/v1/assistant/staff-workspace/read", headers=staff, json={"resource": target(record)})
    assert response.status_code == 503 and response.json()["code"] == "STAFF_PREPARATION_TIMEOUT"
    assert tables(path / "business.sqlite3") == before
    monkeypatch.undo()
    with app.state.service_requests.repository.transaction() as tx:
        changed = tx.get(record["id"]); changed["history"] = changed["history"] * 70; tx.save(changed)
    response = client.post("/v1/assistant/staff-workspace/read", headers=staff, json={"resource": target(record)})
    assert response.status_code == 413 and response.json()["code"] == "STAFF_PROVENANCE_LIMIT"


def test_native_missing_consumer_is_explicitly_unavailable(main_runtime):
    _, client, headers, _, _, _, _ = main_runtime
    response = client.post("/v1/assistant/staff-workspace/read", headers=headers,
        json={"resource": {"kind": "service_request", "id": generate_uuid7(), "expected_version": 1}})
    assert response.status_code == 503 and response.json()["code"] == "STAFF_WORKSPACE_UNAVAILABLE"
    capability = client.get("/v1/assistant/consumer-capabilities", headers=headers).json()
    assert capability["staff_workspace"] is False and capability["staff_ocr"] is False


@pytest.mark.parametrize("injection", [{"actor_id": "spoof"}, {"tenant": "other"}, {"findings": []}, {"readiness": "ready"}])
def test_staff_authority_is_not_accepted_from_client(runtime, injection):
    _, client, _, staff, record, _ = runtime
    response = client.post("/v1/assistant/staff-workspace/read", headers=staff, json={"resource": target(record), **injection})
    assert response.status_code == 422


@pytest.mark.parametrize("kind", ["draft", "claim"])
def test_actual_two_process_staff_cas(runtime, kind):
    app, client, _, _, record, path = runtime
    if kind == "claim":
        _, record, _ = sent(client)
    actor = identity(client)
    processes = []
    for index in range(2):
        command = [sys.executable, "-B", str(ROOT / "scripts/probe_unified_staff_process12.py"),
            "--fixture", str(path), "--ready", f"{kind}-ready-{index}.json", "--gate", f"{kind}-gate.json",
            "--output", f"{kind}-result-{index}.json", "--owner", actor.subject_id, "--case", record["id"],
            "--client", generate_uuid7(), "--kind", kind, "--version", str(record["version"])]
        with (path / f"{kind}-worker-{index}.log").open("xb") as log:
            processes.append(subprocess.Popen(command, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, creationflags=0x08000000))
    deadline = time.monotonic() + 20
    while not all((path / f"{kind}-ready-{i}.json").exists() for i in range(2)):
        assert time.monotonic() < deadline, [p.poll() for p in processes]
        time.sleep(.03)
    with (path / f"{kind}-gate.json").open("x", encoding="utf-8") as stream: json.dump({"go": True}, stream)
    for process in processes: assert process.wait(timeout=20) == 0
    results = [json.loads((path / f"{kind}-result-{i}.json").read_text()) for i in range(2)]
    assert sorted(r["state"] for r in results) == ["committed", "conflict"]
    if kind == "draft": assert app.state.staff_drafts.read(actor, target(record))["draft_version"] == 1
    else: assert read(client, login(client, "OF002"), record["id"], staff=True)["version"] == record["version"] + 1


@pytest.mark.parametrize("model", [StaffRead, StaffReview, StaffSourceRead, StaffDossier])
def test_exact_contract_exports(model):
    path = ROOT / "contracts/json-schema/assistance/staff-v1-01" / (model.__name__ + ".json")
    assert json.loads(path.read_text(encoding="utf-8")) == model.model_json_schema()
