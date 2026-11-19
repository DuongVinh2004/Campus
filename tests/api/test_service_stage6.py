"""Transactional real SQLite/HTTP development cases; no existing DB fixtures."""
from __future__ import annotations

import base64
import concurrent.futures
import hashlib
from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from campus247.bootstrap.service_demo import create_service_demo_app
from campus247.application.document_request.certificates import preview_entity, serial


APPEAL = {"kind": "GRADE_APPEAL", "course_record_id": "demo-student1-CS101", "reason": "Đề nghị đối chiếu bài thi mô phỏng"}
SUPPORT = {"kind": "GENERAL_SUPPORT", "reason": "Cần cán bộ hỗ trợ", "question": "Chưa rõ thủ tục", "unresolved": "Thiếu dữ liệu hạn thực tế"}


@pytest.fixture
def runtime(tmp_path):
    app = create_service_demo_app(tmp_path / "service.sqlite3")
    with TestClient(app) as client:
        yield app, client, tmp_path / "service.sqlite3"


def login(c, name="SV001"):
    r = c.post("/v1/auth/demo-login", json={"account": name})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["token"]}


def draft(c, h, form=APPEAL):
    r = c.post("/v1/service-requests/drafts", headers=h, json={"form": form})
    assert r.status_code == 201, r.text
    return r.json()


def preview(c, h, r, **extra):
    response = c.post(f"/v1/service-requests/{r['id']}/preview", headers=h, json={"expected_version": r["version"], **extra})
    assert response.status_code == 200, response.text
    return response.json()


def confirm(c, h, p, **extra):
    return c.post(f"/v1/service-requests/{p['document_request']['id']}/confirm", headers=h,
        json={"preview_id": p["preview_id"], "confirmation_token": p["confirmation_token"],
            "idempotency_key": "svc-submit:"+p["preview_id"], "form": p["form"], **extra})


def read(c, h, identifier, staff=False):
    r = c.get(f"/v1/{'staff/' if staff else ''}service-requests/{identifier}", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def act(c, h, r, action, **extra):
    return c.post(f"/v1/staff/service-requests/{r['id']}/{action}", headers=h,
        json={"expected_version": r["version"], "idempotency_key": f"svc:{r['id']}:{r['version']}:{action}",
              "note": "Đã đối chiếu dữ liệu demo", **extra})


def sent(c, form=APPEAL):
    h = login(c)
    r = draft(c, h, form)
    p = preview(c, h, r)
    response = confirm(c, h, p)
    assert response.status_code == 201, response.text
    return h, read(c, h, r["id"]), p


def kstate(c, h):
    return c.get("/v1/knowledge-operations", headers=h).json()


def kp(c, h, v, operation="publish"):
    response = c.post(f"/v1/knowledge-operations/versions/{v['id']}/{operation}/preview", headers=h,
        json={"expected_version": v["revision"]})
    assert response.status_code == 200, response.text
    return response.json()


def kc(c, h, v, p, **extra):
    return c.post(f"/v1/knowledge-operations/versions/{v['id']}/confirm", headers=h,
        json={"preview_id": p["preview_id"], "confirmation_token": p["confirmation_token"],
            "idempotency_key": "kb:" + p["preview_id"], "confirmed": True, **extra})


def candidate(c, a, b, text="MÔ PHỎNG phiên bản nguồn mới với hướng dẫn đối chiếu dữ liệu học phần demo.", mapping="ORIGINAL_TEXT"):
    response = c.post("/v1/knowledge-operations/sources", headers=a, json={
        "title": "Demo source", "filename": "source.txt", "content": text, "locator": "development fixture"})
    assert response.status_code == 201, response.text
    source = response.json()
    response = c.post("/v1/knowledge-operations/versions", headers=a, json={"source_id": source["id"],
        "procedure": "GRADE_APPEAL", "text": text, "mapping": mapping,
        "effective_from": "2026-10-13T00:00:00+00:00", "candidate_text": "NOT SOURCE EVIDENCE"})
    assert response.status_code == 201, response.text
    v = response.json()
    response = c.post(f"/v1/knowledge-operations/versions/{v['id']}/review", headers=b,
        json={"expected_version": v["revision"], "verdict": "approved", "note": "Development source/mapping review"})
    assert response.status_code == 200, response.text
    v = response.json()
    response = c.post(f"/v1/knowledge-operations/versions/{v['id']}/build", headers=b, json={"expected_version": v["revision"]})
    assert response.status_code == 200, response.text
    return source, response.json()


@pytest.mark.parametrize("form,officer", [(APPEAL, "OF002"), (SUPPORT, "OF001")])
def test_end_to_end_restart_result_attachment_and_audit(runtime, form, officer):
    app, c, db = runtime
    form = {**form, "attachments": [{"name": "evidence.txt", "content": "Bằng chứng mô phỏng"}]}
    student, r, p = sent(c, form)
    staff = login(c, officer)
    assert c.get("/v1/staff/service-requests", headers=staff).json()["items"][0]["id"] == r["id"]
    r = act(c, staff, r, "claim").json()["document_request"]
    response = act(c, staff, r, "request_information", note="Bổ sung lý do chi tiết")
    assert response.status_code == 200, response.text
    r = response.json()["document_request"]
    updated = {**r["payload"], "reason": "Lý do bổ sung đã đối chiếu"}
    supplement = preview(c, student, r, form=updated, note="Thông tin bổ sung demo")
    response = confirm(c, student, supplement)
    assert response.status_code == 201, response.text
    assert confirm(c, student, supplement).json()["is_replay"]
    r = read(c, staff, r["id"], True)
    assert r["status"] == "VALIDATING" and r["supplements"][0]["before"]["reason"] == form["reason"]
    r = act(c, staff, r, "respond", note="Đã nhận bổ sung").json()["document_request"]
    response = act(c, staff, r, "resolve", outcome="UNCHANGED" if form["kind"] == "GRADE_APPEAL" else None)
    assert response.status_code == 200, response.text
    r = response.json()["document_request"]
    assert r["status"] == "READY" and r["result"]["template_version"] == "service-outcome-demo-v1"
    html = c.get(f"/v1/service-requests/{r['id']}/result", headers=student)
    assert "MÔ PHỎNG" in html.text and "KHÔNG CÓ GIÁ TRỊ PHÁP LÝ" in html.text
    assert hashlib.sha256(html.content).hexdigest() == html.headers["x-content-sha256"]
    assert c.get(f"/v1/service-requests/{r['id']}/attachments/0", headers=student).text == "Bằng chứng mô phỏng"
    before = r
    with TestClient(create_service_demo_app(db)) as restarted:
        assert read(restarted, student, r["id"]) == before
        assert restarted.get(f"/v1/service-requests/{r['id']}/result", headers=student).content == html.content
    with app.state.service_requests.repository.transaction() as tx:
        assert tx.connection.execute("SELECT COUNT(*) FROM service_request_audit WHERE document_id=?", (r["id"],)).fetchone()[0] == len(r["history"])


def test_confirm_replay_restart_different_key_and_payload(runtime):
    _, c, db = runtime
    h, r, p = sent(c)
    with TestClient(create_service_demo_app(db)) as restarted:
        assert confirm(restarted, h, p).json()["is_replay"]
        assert confirm(restarted, h, p, idempotency_key="another-valid-key").status_code == 409
        assert confirm(restarted, h, p, form={**p["form"], "reason": "changed"}).status_code == 422
        assert len(restarted.get("/v1/service-requests", headers=h).json()["items"]) == 1


@pytest.mark.parametrize("change", ["token", "preview", "session", "payload", "expired"])
def test_invalid_confirmation_has_no_effect(runtime, change):
    app, c, _ = runtime
    h = login(c)
    r = draft(c, h)
    p = preview(c, h, r)
    extras = {}
    if change == "token": extras["confirmation_token"] = "invalid"
    if change == "preview": extras["preview_id"] = "other"
    if change == "session": h = login(c)
    if change == "payload": extras["form"] = {**p["form"], "reason": "changed"}
    if change == "expired":
        with app.state.service_requests.repository.transaction() as tx:
            value = tx.get(r["id"])
            old = preview_entity(value["preview"])
            expired = replace(old, created_at=datetime.now(timezone.utc)-timedelta(minutes=10), expires_at=datetime.now(timezone.utc)-timedelta(minutes=5))
            value["preview"] = serial(asdict(expired))
            tx.save(value)
        extras["confirmation_token"] = app.state.service_requests.tokens.mint_token(expired)
    assert confirm(c, h, p, **extras).status_code == 422
    assert read(c, h, r["id"])["status"] == "PENDING_CONFIRMATION"
    assert c.get("/v1/staff/service-requests", headers=login(c, "OF002")).json()["items"] == []


def test_resume_rechecks_snapshot_and_session(runtime):
    _, c, db = runtime
    h = login(c)
    r = draft(c, h)
    p = preview(c, h, r)
    with TestClient(create_service_demo_app(db)) as restarted:
        assert restarted.get(f"/v1/service-requests/{r['id']}/preview", headers=h).json()["preview_id"] == p["preview_id"]
        assert restarted.get(f"/v1/service-requests/{r['id']}/preview", headers=login(restarted)).status_code == 409


@pytest.mark.parametrize("code,status", [("CS102", 422), ("CS103", 422), ("CS104", 422), ("OTHER", 404)])
def test_ineligible_expired_unknown_course(runtime, code, status):
    _, c, _ = runtime
    h = login(c)
    assert c.post("/v1/service-requests/drafts", headers=h, json={"form": {**APPEAL, "course_record_id": "demo-student1-"+code}}).status_code == status
    rows = c.get("/v1/service-course-records", headers=h).json()["items"]
    assert {r["eligibility"] for r in rows} == {"ELIGIBLE_DEMO", "COURSE_INELIGIBLE", "APPEAL_DEADLINE_PASSED", "ELIGIBILITY_DATA_MISSING"}


@pytest.mark.parametrize("attachment", [
    {"name": "../file.txt", "content": "x"}, {"name": "C:\\file.txt", "content": "x"},
    {"name": "file.html", "content": "x"}, {"name": "file.txt", "content": "界"*6000},
    {"name": "file.txt", "content": "x", "media_type": "text/html"},
])
def test_attachment_validation(runtime, attachment):
    _, c, _ = runtime
    assert c.post("/v1/service-requests/drafts", headers=login(c), json={"form": {**APPEAL, "attachments": [attachment]}}).status_code == 422


def test_role_owner_queue_and_certificate_type_isolation(runtime):
    _, c, _ = runtime
    student, r, _ = sent(c)
    other = login(c, "SV024")
    officer = login(c, "OF001")
    for suffix in ("", "/result", "/attachments/0", "/preview"):
        assert c.get(f"/v1/service-requests/{r['id']}"+suffix, headers=other).status_code == 404
    assert c.get(f"/v1/staff/service-requests/{r['id']}", headers=officer).status_code == 404
    assert c.get("/v1/staff/service-requests", headers=student).status_code == 403
    assert c.get("/v1/knowledge-operations", headers=student).status_code == 403
    assert c.post("/v1/service-requests/drafts", headers=officer, json={"form": APPEAL}).status_code == 403
    assert c.get(f"/v1/document-requests/{r['id']}", headers=student).status_code == 404
    assert c.get("/v1/document-requests", headers=student).json()["items"] == []
    assert c.post("/v1/service-requests/drafts", headers=student, json={"form": APPEAL, "actor_id": "forged"}).status_code == 422
    assert c.post("/v1/service-requests/drafts", headers=other, json={"form": APPEAL}).status_code == 404


def test_concurrent_claim_stale_conflict(runtime):
    _, c, _ = runtime
    _, r, _ = sent(c)
    staff1, staff2 = login(c, "OF002"), login(c, "OF002")
    with concurrent.futures.ThreadPoolExecutor(2) as pool:
        responses = list(pool.map(lambda h: act(c, h, r, "claim", idempotency_key="claim:"+h["Authorization"][-12:]), [staff1, staff2]))
    assert sorted(response.status_code for response in responses) == [200, 409]
    latest = read(c, staff1, r["id"], True)
    assert sum(e["action"] == "request.claim" for e in latest["history"]) == 1
    assert act(c, staff1, latest, "resolve").status_code == 422
    assert act(c, staff1, latest, "respond", note=" ").status_code == 422


def test_assign_transfer_and_visibility_reason_history(runtime):
    _, c, _ = runtime
    student, r, _ = sent(c, SUPPORT)
    a, b = login(c, "OF001"), login(c, "OF002")
    directory = c.get("/v1/service-staff-directory", headers=a).json()["items"]
    target = next(v for v in directory if "ACADEMIC_SERVICES" in v["queues"])["user_id"]
    current = next(v for v in directory if "HUCE_GENERAL" in v["queues"])["user_id"]
    assert act(c, a, r, "assign", target_user_id=target).status_code == 422
    response = act(c, a, r, "assign", target_user_id=current)
    assert response.status_code == 200, response.text
    r = response.json()["document_request"]
    assert act(c, a, r, "transfer", target_user_id="forged", target_queue="ACADEMIC_SERVICES").status_code == 422
    response = act(c, a, r, "transfer", target_user_id=target, target_queue="ACADEMIC_SERVICES", note="Chuyển chuyên viên học vụ demo")
    assert response.status_code == 200, response.text
    r = response.json()["document_request"]
    assert c.get(f"/v1/staff/service-requests/{r['id']}", headers=a).status_code == 404
    assert read(c, b, r["id"], True)["assigned_user_id"] == target
    assert read(c, student, r["id"])["messages"][-1]["before"]["queue"] == "HUCE_GENERAL"
    assert act(c, b, r, "resolve").status_code == 200


def test_publish_withdraw_source_change_and_current_history(runtime):
    _, c, _ = runtime
    h = login(c)
    r = draft(c, h)
    p = preview(c, h, r)
    a, b = login(c, "KA001"), login(c, "KA002")
    before = kstate(c, b)
    old = next(v for v in before["versions"] if v["procedure"] == "GRADE_APPEAL")
    source, v = candidate(c, a, b)
    assert base64.b64decode(source["original_base64"]).decode() == v["text"]
    assert "NOT SOURCE EVIDENCE" not in v["build"]["evidence_text"]
    pp = kp(c, b, v)
    assert kc(c, b, v, pp, confirmed=False).status_code == 422
    response = kc(c, b, v, pp)
    assert response.status_code == 200, response.text
    v = response.json()["version"]
    assert kc(c, b, v, pp).json()["is_replay"]
    assert c.get(f"/v1/service-requests/{r['id']}/preview", headers=h).status_code == 409
    assert confirm(c, h, p).status_code == 409
    assert read(c, h, r["id"])["status"] == "PENDING_CONFIRMATION"
    state = kstate(c, b)
    assert next(item for item in state["versions"] if item["id"] == old["id"])["state"] == "SUPERSEDED"
    pp = kp(c, b, v, "withdraw")
    assert kc(c, b, v, pp).status_code == 200
    assert c.get("/v1/service-guidance/GRADE_APPEAL", headers=h).status_code == 422
    assert c.get(f"/v1/knowledge-operations/sources/{old['source_id']}", headers=b).status_code == 200
    assert c.post("/v1/service-requests/drafts", headers=h, json={"form": APPEAL}).status_code == 422


def test_failed_build_duties_cas_and_active_pointer_preserved(runtime):
    _, c, _ = runtime
    a, b = login(c, "KA001"), login(c, "KA002")
    before = kstate(c, b)["active"]
    _, v = candidate(c, a, b, mapping="unknown mapping")
    assert v["state"] == "BUILD_FAILED" and v["build"]["error"] == "MAPPING_UNVERIFIED"
    assert c.post(f"/v1/knowledge-operations/versions/{v['id']}/publish/preview", headers=b, json={"expected_version": v["revision"]}).status_code == 409
    assert kstate(c, b)["active"] == before
    assert c.post(f"/v1/knowledge-operations/versions/{v['id']}/review", headers=a, json={"expected_version": v["revision"], "verdict": "approved", "note": "self"}).status_code == 403
    assert c.post(f"/v1/knowledge-operations/versions/{v['id']}/build", headers=b, json={"expected_version": 1}).status_code == 409


def test_service_proposal_has_no_effect_and_bound_tools(runtime):
    app, c, _ = runtime
    h = login(c)
    proposal = c.post("/v1/service-assistant", headers=h, json={"message": "Tôi muốn phúc khảo"}).json()
    assert proposal["intent"] == "GRADE_APPEAL" and proposal["effect"] == "NONE"
    assert c.get("/v1/service-requests", headers=h).json()["items"] == []
    tools = app.state.service_agent_tools
    assert not hasattr(tools, "submit_confirmed_request") and not hasattr(tools, "act")
    assert c.post("/v1/service-assistant", headers=login(c, "OF001"), json={"message": "phúc khảo"}).status_code == 403


def test_general_support_missing_source_reports_gap_and_persists_real_queue(runtime):
    _, c, _ = runtime
    a, b = login(c, "KA001"), login(c, "KA002")
    v = next(v for v in kstate(c, b)["versions"] if v["procedure"] == "GENERAL_SUPPORT")
    assert kc(c, b, v, kp(c, b, v, "withdraw")).status_code == 200
    student, r, _ = sent(c, SUPPORT)
    assert r["snapshot"]["guidance"]["unverified"] == "MISSING_SOURCE"
    assert c.get("/v1/staff/service-requests", headers=login(c, "OF001")).json()["items"][0]["id"] == r["id"]


def test_certificate_existing_endpoint_keeps_behavior_and_separate_type(runtime):
    _, c, _ = runtime
    h = login(c)
    response = c.post("/v1/document-requests/drafts", headers=h,
        json={"form": {"purpose": "Demo", "recipient": "Demo", "quantity": 1, "delivery_method": "DIGITAL"}})
    assert response.status_code == 201, response.text
    identifier = response.json()["id"]
    assert c.get(f"/v1/service-requests/{identifier}", headers=h).status_code == 404
    assert c.get("/v1/service-requests", headers=h).json()["items"] == []


def test_frontend_catchall_does_not_shadow_api(runtime):
    _, c, db = runtime
    with TestClient(create_service_demo_app(db, frontend_port=3005)) as shell:
        assert shell.get("/v1/service-course-records", headers=login(shell)).status_code == 200


def test_admin_confirmation_invalid_expired_and_session_have_no_publication(runtime):
    app, c, _ = runtime
    a, b = login(c, "KA001"), login(c, "KA002")
    _, v = candidate(c, a, b)
    before = kstate(c, b)["active"]
    pp = kp(c, b, v)
    assert kc(c, b, v, pp, confirmation_token="invalid").status_code == 422
    assert kc(c, login(c, "KA002"), v, pp).status_code == 422
    with app.state.service_requests.repository.transaction() as tx:
        row = tx.item("knowledge_preview", pp["preview_id"])
        old = preview_entity(row["preview"])
        expired = replace(old, created_at=datetime.now(timezone.utc)-timedelta(minutes=10), expires_at=datetime.now(timezone.utc)-timedelta(minutes=5))
        row["preview"] = serial(asdict(expired)); tx.update("knowledge_preview", row)
    assert kc(c, b, v, pp, confirmation_token=app.state.knowledge_operations.tokens.mint_token(expired)).status_code == 422
    assert kstate(c, b)["active"] == before


def test_source_rendition_tamper_is_detected(runtime):
    app, c, _ = runtime
    a, b = login(c, "KA001"), login(c, "KA002")
    source, v = candidate(c, a, b)
    with app.state.service_requests.repository.transaction() as tx:
        # Intentional corruption is limited to this newly generated fixture row.
        row = tx.item("source", source["id"])
        row["original_base64"] = base64.b64encode(b"changed bytes").decode(); tx.update("source", row)
    assert c.get(f"/v1/knowledge-operations/sources/{source['id']}", headers=b).status_code == 409
    assert c.post(f"/v1/knowledge-operations/versions/{v['id']}/publish/preview", headers=b, json={"expected_version": v["revision"]}).status_code == 409


def test_publish_previews_conflict_on_pointer_and_review_revision(runtime):
    _, c, _ = runtime
    a, b = login(c, "KA001"), login(c, "KA002")
    _, v1 = candidate(c, a, b); _, v2 = candidate(c, a, b)
    p1, p2 = kp(c, b, v1), kp(c, b, v2)
    assert kc(c, b, v1, p1).status_code == 200
    assert kc(c, b, v2, p2).status_code == 409
    response = c.post(f"/v1/knowledge-operations/versions/{v2['id']}/review", headers=b,
        json={"expected_version": v2["revision"], "verdict": "rejected", "note": "Source review changed"})
    assert response.status_code == 200
    assert kc(c, b, v2, p2).status_code == 409


def test_withdraw_switch_removes_current_search_and_keeps_historical_evidence(runtime):
    _, c, db = runtime
    h, b = login(c), login(c, "KA002")
    search = lambda: c.post("/v1/service-knowledge/search", headers=h, json={"message": "phúc khảo"}).json()
    v = next(v for v in kstate(c, b)["versions"] if v["procedure"] == "GRADE_APPEAL")
    assert any(r["version_id"] == v["id"] for r in search()["items"])
    assert kc(c, b, v, kp(c, b, v, "withdraw")).status_code == 200
    assert all(r["version_id"] != v["id"] for r in search()["items"])
    assert all(r["eligibility"] == "MISSING_SOURCE" for r in c.get("/v1/service-course-records", headers=h).json()["items"])
    with TestClient(create_service_demo_app(db)) as restarted:
        assert restarted.get("/v1/service-guidance/GRADE_APPEAL", headers=h).status_code == 422
        assert next(r for r in kstate(restarted, b)["versions"] if r["id"] == v["id"])["state"] == "WITHDRAWN"


def test_draft_revision_and_old_preview_are_retained_and_invalidated(runtime):
    _, c, _ = runtime
    h = login(c); r = draft(c, h); p = preview(c, h, r)
    edited = {**p["form"], "reason": "Lý do đã sửa"}
    response = c.post("/v1/service-requests/drafts", headers=h,
        json={"document_id": r["id"], "expected_version": 2, "form": edited})
    assert response.status_code == 201
    value = response.json()
    assert [entry["payload"]["reason"] for entry in value["draft_revisions"]] == [APPEAL["reason"], edited["reason"]]
    assert confirm(c, h, p).status_code == 409


def test_proxy_model_error_never_creates_fake_support_queue(tmp_path):
    import httpx
    app = create_service_demo_app(tmp_path / "proxy.sqlite3", rag_transport=httpx.MockTransport(
        lambda request: httpx.Response(503, json={"code": "MODEL_FAILURE"})))
    with TestClient(app) as c:
        h = login(c)
        response = c.post("/v1/conversations", headers=h, json={"title": "demo question"})
        assert response.status_code == 503 and response.json()["code"] == "MODEL_FAILURE"
        proposal = c.post("/v1/service-assistant", headers=h, json={"message": "Cần cán bộ hỗ trợ"}).json()
        assert proposal["effect"] == "NONE" and proposal["intent"] == "GENERAL_SUPPORT"
        assert c.get("/v1/staff/service-requests", headers=login(c, "OF001")).json()["items"] == []


def test_two_distinct_trusted_staff_contexts_conflict_and_assignment_guard(runtime):
    # Counterfactual server-issued fixture grants for two distinct officers in
    # one queue. This does not change the app directory, signed tokens or roles.
    from identities import generate_identities
    from campus247.application.document_request.certificates import CertificateError
    from campus247.infrastructure.identity.mock import SyntheticIdentityAdapter
    app, c, _ = runtime
    student, r, _ = sent(c, SUPPORT)
    directory = generate_identities()["records"]
    ids = [v["user_id"] for v in directory["role_binding"] if v["role"] == "SUPPORT_OFFICER"]
    adapter = SyntheticIdentityAdapter("campus247-demo-secret-key-huce", tenant_id="huce-local-public")
    a = adapter.resolve_token(adapter.mint_token(ids[0]))
    b = replace(adapter.resolve_token(adapter.mint_token(ids[1])), unit_ids=a.unit_ids)
    assert a.subject_id != b.subject_id
    service = app.state.service_requests
    def claim(actor):
        try:
            value = service.act(actor, r["id"], "claim", r["version"], "two-officers:"+actor.subject_id, "Synthetic concurrency fixture")
            return actor, 200, value
        except CertificateError as exc:
            return actor, exc.status, exc.code
    with concurrent.futures.ThreadPoolExecutor(2) as pool:
        results = list(pool.map(claim, (a, b)))
    assert sorted(v[1] for v in results) == [200, 409]
    latest = read(c, student, r["id"])
    assert latest["version"] == r["version"]+1
    assert sum(e["action"] == "request.claim" for e in latest["history"]) == 1
    loser = next(actor for actor, status, _ in results if status == 409)
    with pytest.raises(CertificateError) as denial:
        service.act(loser, r["id"], "respond", latest["version"], "loser-response:"+loser.subject_id, "Cannot process another assignee's request")
    assert denial.value.code == "ASSIGNED_ELSEWHERE"
