"""U4 HTTP consumers on fresh synthetic DBs; no UI or provider dispatch."""
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from campus247.application.document_request.student_preparation import StudentGoal, SavePreparedDraft
from campus247.application.document_request.assistant import understand_student_goal
from campus247.bootstrap.unified_demo import create_unified_demo_app
from campus247.domain.document_request.certificate import CertificateForm
from campus247.domain.service_request import ServiceForm
from campus247.domain.shared.values import generate_uuid7
from tests.integration.test_unified_actor_features import runtime as runtime_fixture
from tests.api.test_service_stage6 import login, draft, preview, confirm, APPEAL

runtime = runtime_fixture


def goal(**changes):
    return {"goal": "Tôi cần giấy xác nhận sinh viên", "workflow": "STUDENT_CERTIFICATE",
        "statements": {"purpose": "Nộp học bổng", "recipient": "Quỹ học bổng mô phỏng"},
        "operation_id": generate_uuid7(), **changes}


def prepare(c, h, request):
    r = c.post("/v1/assistant/student:prepare", headers=h, json=request)
    assert r.status_code == 200, r.text
    assert r.headers["cache-control"] == "no-store"
    assert "confirmation_token" not in r.text
    return r.json()


def save(c, h, request, prepared):
    return c.post("/v1/assistant/student:save-draft", headers=h,
        json={"request": request, "expected_sha256": prepared["sha256"], "reviewed": True})


@pytest.mark.parametrize("text,workflow", [("Xin giấy xác nhận sinh viên", "STUDENT_CERTIFICATE"),
    ("Tôi muốn phúc khảo", "GRADE_APPEAL"), ("Gửi yêu cầu hỗ trợ chung", "GENERAL_SUPPORT"),
    ("Tôi cần một giấy để giải quyết việc", None), ("giấy xác nhận và phúc khảo", None),
    ("muốn gặp cán bộ", None), ("Đặt phòng học", None)])
def test_intent_conservative(text, workflow):
    value = understand_student_goal(text)
    assert value.workflow == workflow
    assert value.status == "needs_clarification" and value.action_authority == "none"


def test_certificate_prepare_save_retry_restart_no_submit(runtime):
    app, c, _, _, _, _, paths = runtime
    h = login(c); request = goal()
    p = prepare(c, h, request)
    assert p["next_action"] == "review_new_draft" and not p["intent"]["missing_fields"]
    assert c.get("/v1/document-requests", headers=h).json()["items"] == []
    result = save(c, h, request, p)
    assert result.status_code == 200, result.text
    first = result.json()
    assert first["document_request"]["status"] == "DRAFT"
    assert first["receipt"]["effect"] == "draft_saved"
    repeated = save(c, h, request, p)
    assert repeated.status_code == 200 and repeated.json()["is_replay"]
    restarted = create_unified_demo_app(paths[0], state_database=paths[1], consent_mode="sqlite", history_database=paths[2])
    with TestClient(restarted) as fresh:
        replay = save(fresh, h, request, p)
        assert replay.status_code == 200 and replay.json()["receipt"] == first["receipt"]
    assert len(c.get("/v1/document-requests", headers=h).json()["items"]) == 1
    with app.state.certificate_service.repository.transaction() as tx:
        record = tx.get(first["document_request"]["id"])
        assert record["preview"] is None
        assert record["student_preparations"][0]["goal"] == request["goal"]


def test_existing_manual_fields_diff_cas_and_no_repeat_questions(runtime):
    app, c, _, _, _, _, _ = runtime
    h = login(c); r = draft(c, h)
    target = {"kind": "service_request", "id": r["id"], "expected_version": r["version"]}
    request = goal(goal="Tôi muốn phúc khảo", workflow="GRADE_APPEAL", resource=target, statements={"reason": "Lý do mới do tôi khai"})
    p = prepare(c, h, request)
    assert p["intent"]["missing_fields"] == []
    assert p["form"]["course_record_id"] == r["payload"]["course_record_id"]
    assert p["provenance"]["course_record_id"]["origin"] == "saved_resource"
    assert p["diff"] == [{"field": "reason", "before": r["payload"]["reason"], "candidate": "Lý do mới do tôi khai", "origin": "user_statement", "evidence": None}]
    assert p["proposal"]["proposal"]["target"] == target
    followup = prepare(c, h, {**request, "workflow": None, "goal": "Sửa lý do của hồ sơ này"})
    assert followup["intent"]["workflow"] == "GRADE_APPEAL" and not followup["intent"]["missing_fields"]
    assert c.get(f"/v1/service-requests/{r['id']}", headers=h).json()["payload"] == r["payload"]
    manual = c.post("/v1/service-requests/drafts", headers=h, json={"form": {**r["payload"], "reason": "Manual work must survive"}, "document_id": r["id"], "expected_version": r["version"]})
    assert manual.status_code == 201
    assert save(c, h, request, p).status_code == 409
    assert c.get(f"/v1/service-requests/{r['id']}", headers=h).json()["payload"]["reason"] == "Manual work must survive"


def test_goal_change_preserves_original_and_multiple_drafts_require_selection(runtime):
    _, c, _, _, _, _, _ = runtime
    h = login(c); a = draft(c, h); b = draft(c, h)
    request = goal(goal="Phúc khảo", workflow="GRADE_APPEAL", statements={"reason": "Xem lại điểm", "course_record_id": APPEAL["course_record_id"]})
    p = prepare(c, h, request)
    assert p["next_action"] == "choose_draft" and {x["id"] for x in p["candidates"]} == {a["id"], b["id"]}
    assert not p.get("sha256")
    changed = prepare(c, h, goal(resource={"kind": "service_request", "id": a["id"], "expected_version": a["version"]}))
    assert changed["next_action"] == "choose_workflow" and changed["field_errors"][0]["code"] == "GOAL_CHANGED"


@pytest.mark.parametrize("account", ["SV024", "OF001", "KA001"])
def test_own_resource_not_reused_by_other_actor_or_role(runtime, account):
    _, c, _, _, _, _, _ = runtime
    r = draft(c, login(c))
    request = goal(resource={"kind": "service_request", "id": r["id"], "expected_version": r["version"]})
    assert c.post("/v1/assistant/student:prepare", headers=login(c, account), json=request).status_code in {403, 404}


@pytest.mark.parametrize("change", [{"statements": {"quantity": True}}, {"statements": {"recipient": {"value": "forged"}}},
    {"statements": {"academic_status": "ACTIVE"}}, {"authority": "submit"}, {"constraints": [""]}, {"goal": " "}])
def test_strict_input_does_not_accept_authority_or_unproven_facts(runtime, change):
    _, c, _, _, _, _, _ = runtime
    assert c.post("/v1/assistant/student:prepare", headers=login(c), json=goal(**change)).status_code == 422


def test_missing_group_validation_and_ocr_unavailable(runtime):
    _, c, _, _, _, _, _ = runtime
    h = login(c)
    p = prepare(c, h, goal(statements={}))
    assert p["intent"]["missing_fields"] == ["purpose", "recipient"] and not p.get("sha256")
    p = prepare(c, h, goal(statements={"purpose": "X" * 501, "recipient": "Người nhận"}))
    assert p["field_errors"][0]["field"] == "purpose"
    assert p["field_errors"][0]["source"] == "server_form_schema"
    assert p["ocr"]["available"] is False


@pytest.mark.parametrize("file", [{"name": "x.pdf", "content": "text"}, {"name": "../x.txt", "content": "text"},
    {"name": "x.txt", "content": "ế" * 6000}, {"name": "x.txt", "content": "\x00"}, {"name": "x.txt", "content": "  "}])
def test_server_attachment_contracts(file):
    with pytest.raises(ValueError):
        CertificateForm(purpose="Mục đích", recipient="Nơi nhận", attachments=[file])
    with pytest.raises(ValueError):
        ServiceForm(kind="GENERAL_SUPPORT", reason="Lý do", attachments=[file])


def test_prepared_binding_profile_drift_and_explicit_review_required(runtime):
    app, c, _, _, _, _, _ = runtime
    h = login(c); request = goal(); p = prepare(c, h, request)
    denied = c.post("/v1/assistant/student:save-draft", headers=h,
        json={"request": request, "expected_sha256": p["sha256"], "reviewed": False})
    assert denied.status_code == 422
    reader = app.state.certificate_service.profile_reader
    app.state.certificate_service.profile_reader = lambda owner: {**reader(owner), "display_name": "Changed fixture profile"}
    assert save(c, h, request, p).status_code == 409
    assert not c.get("/v1/document-requests", headers=h).json()["items"]


def test_concurrent_save_same_operation_is_atomic(runtime):
    _, c, _, _, _, _, _ = runtime
    h = login(c); request = goal(); p = prepare(c, h, request)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: save(c, h, request, p), range(2)))
    assert all(r.status_code == 200 for r in results), [r.text for r in results]
    assert len({r.json()["document_request"]["id"] for r in results}) == 1
    assert len(c.get("/v1/document-requests", headers=h).json()["items"]) == 1


@pytest.mark.parametrize("kind", ["GRADE_APPEAL", "GENERAL_SUPPORT"])
def test_service_draft_diff_save_then_explicit_business_confirmation(runtime, kind):
    _, c, _, _, _, _, _ = runtime
    h = login(c)
    statements = {"reason": "Căn cứ được người dùng khai"}
    if kind == "GRADE_APPEAL": statements["course_record_id"] = APPEAL["course_record_id"]
    request = goal(goal="Phúc khảo" if kind == "GRADE_APPEAL" else "Hỗ trợ chung", workflow=kind, statements=statements)
    p = prepare(c, h, request)
    saved = save(c, h, request, p)
    assert saved.status_code == 200, saved.text
    r = saved.json()["document_request"]
    assert r["status"] == "DRAFT" and r["snapshot"]["source_effectivity"]["state"] == "PUBLISHED"
    request = {**request, "resource": {"kind": "service_request", "id": r["id"], "expected_version": r["version"]},
        "statements": {"reason": "Tôi bổ sung căn cứ mới"}, "operation_id": generate_uuid7()}
    p = prepare(c, h, request)
    updated = save(c, h, request, p)
    assert updated.status_code == 200, updated.text
    r = updated.json()["document_request"]
    assert r["payload"]["reason"] == "Tôi bổ sung căn cứ mới" and r["status"] == "DRAFT"
    assert save(c, h, request, p).json()["receipt"] == updated.json()["receipt"]
    business = preview(c, h, r)
    receipt = confirm(c, h, business)
    assert receipt.status_code == 201 and receipt.json()["status"] == "SUBMITTED"
    assert confirm(c, h, business).json()["is_replay"] is True
    assert c.get(f"/v1/service-requests/{r['id']}", headers=h).json()["status"] == "SUBMITTED"


def test_source_effectivity_change_blocks_confirm(runtime):
    app, c, _, _, _, _, _ = runtime
    h = login(c); r = draft(c, h); p = preview(c, h, r)
    with app.state.service_requests.repository.transaction() as tx:
        source = tx.item("knowledge_version", r["snapshot"]["guidance"]["version_id"])
        source["effective_from"] = "2026-10-01T00:00:00+00:00"
        tx.update("knowledge_version", source)
    assert confirm(c, h, p).status_code == 409


def test_domain_error_targets_course_and_does_not_create_draft(runtime):
    _, c, _, _, _, _, _ = runtime
    h = login(c)
    p = prepare(c, h, goal(goal="Phúc khảo", workflow="GRADE_APPEAL", statements={"reason": "Xem lại", "course_record_id": "not-owned"}))
    assert p["field_errors"][0]["field"] == "course_record_id" and not p.get("sha256")
    assert not c.get("/v1/service-requests", headers=h).json()["items"]


def test_certificate_confirm_rechecks_profile_and_version(runtime):
    app, c, _, _, _, _, _ = runtime
    h = login(c); request = goal(); p = prepare(c, h, request)
    r = save(c, h, request, p).json()["document_request"]
    previewed = c.post(f"/v1/document-requests/{r['id']}/preview", headers=h, json={"expected_version": r["version"]}).json()
    original = app.state.certificate_service.profile_reader
    app.state.certificate_service.profile_reader = lambda owner: {**original(owner), "academic_status": "INACTIVE"}
    result = c.post(f"/v1/document-requests/{r['id']}/confirm", headers=h, json={"preview_id": previewed["preview_id"],
        "confirmation_token": previewed["confirmation_token"], "idempotency_key": "certificate-submit:" + previewed["preview_id"], "form": r["payload"]})
    assert result.status_code == 409
    assert c.get(f"/v1/document-requests/{r['id']}", headers=h).json()["status"] == "PENDING_CONFIRMATION"


@pytest.mark.parametrize("mutation", ["queue", "version", "payload"])
def test_service_confirmation_revalidates_exact_target_and_version(runtime, mutation):
    app, c, _, _, _, _, _ = runtime
    h = login(c); r = draft(c, h); p = preview(c, h, r)
    with app.state.service_requests.repository.transaction() as tx:
        stored = tx.get(r["id"])
        if mutation == "queue": stored["queue"] = "HUCE_GENERAL"
        elif mutation == "version": stored["version"] += 1
        else: stored["payload"]["reason"] = "Tampered fixture"
        tx.save(stored)
    assert confirm(c, h, p).status_code == 409
    assert c.get(f"/v1/service-requests/{r['id']}", headers=h).json()["status"] == "PENDING_CONFIRMATION"


def test_capability_inventory_no_synthetic_business_success(runtime):
    _, c, _, _, _, _, _ = runtime
    h = login(c)
    caps = c.get("/v1/assistant/consumer-capabilities", headers=h).json()
    assert caps["student_preparation"] and caps["student_draft_writer"] == "business_services"
    assert caps["student_ocr"] is False and caps["coordination"]["profile"] is None
    inventory = c.get("/v1/assistant/student-actions", headers=h).json()
    rows = {r["action"]: r for r in inventory["items"]}
    assert len(rows) == len(inventory["items"])
    for action in ("schedule", "rooms", "ticket.handover", "legacy.forms"):
        assert rows[action]["support"] == "unavailable" and rows[action]["next_step"]
    assert rows["service.submit"]["support"] == "explicit_confirmation"


@pytest.mark.parametrize("model", [StudentGoal, SavePreparedDraft])
def test_exported_u4_contract_exact(model):
    root = Path(__file__).resolve().parents[2]
    actual = json.loads((root / "contracts/json-schema/assistance/student-v1-01" / (model.__name__ + ".json")).read_text(encoding="utf-8"))
    assert actual == model.model_json_schema()


def test_native_without_business_composition_fails_closed(tmp_path):
    from campus247.bootstrap.app import create_app
    from campus247.bootstrap.settings import Settings
    from campus247.infrastructure.repositories.sqlite_actor_state import SQLiteActorStateStore
    from campus247.infrastructure.identity.mock import SyntheticIdentityAdapter
    from tests.integration.test_unified_durable_services import actor
    settings = Settings(_env_file=None, ENVIRONMENT="development", DEMO_MODE=True,
        OPENAI_API_KEY=None, GEMINI_API_KEY=None, DEEPSEEK_API_KEY=None)
    app = create_app(runtime_settings=settings, synthetic_tenant_id="huce-local-public",
        actor_state_store=SQLiteActorStateStore(tmp_path / "native-actor.sqlite3"))
    adapter = SyntheticIdentityAdapter(settings.IDENTITY_SECRET_KEY, environment="development", tenant_id="huce-local-public")
    headers = {"Authorization": "Bearer " + adapter.mint_token(actor().subject_id)}
    with TestClient(app) as client:
        caps = client.get("/v1/assistant/consumer-capabilities", headers=headers)
        assert caps.status_code == 200, caps.text
        assert caps.json()["student_preparation"] is False and caps.json()["student_draft_writer"] is None
        result = client.post("/v1/assistant/student:prepare", headers=headers, json=goal())
        assert result.status_code == 503 and result.json()["code"] == "STUDENT_DRAFT_UNAVAILABLE"
