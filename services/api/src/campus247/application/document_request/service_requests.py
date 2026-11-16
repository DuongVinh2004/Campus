"""Service Agent proposes; authorized transactional application code executes."""
from __future__ import annotations

from contextlib import nullcontext

import json
from dataclasses import asdict
from datetime import UTC, datetime
from html import escape

from campus247.application.document_request.certificates import (
    CertificateError,
    CertificateService,
    entity,
    preview_entity,
    serial,
)
from campus247.application.knowledge.operations import digest, now
from campus247.domain.action.preview import create_action_preview
from campus247.domain.document_request.model import (
    DocumentRequest,
    InvalidDocumentRequestStateError,
)
from campus247.domain.service_request import (
    DISCLAIMER,
    KINDS,
    QUEUES,
    ServiceForm,
    staff_transition,
)
from campus247.domain.shared.values import generate_uuid7
from campus247.domain.service_workflow import record_workflow
from campus247.ports.identity import IdentityRole


class ServiceRequestService(CertificateService):
    def __init__(self, repository, tokens, profile_reader, staff_directory, knowledge):
        super().__init__(repository, tokens, profile_reader)
        self.staff_directory, self.knowledge = staff_directory, knowledge

    def authorize(self, actor, role=None):
        super().authorize(actor)
        if role and not actor.has_role(role):
            raise CertificateError(403, "ROLE_REQUIRED", "Vai trò không có quyền thực hiện")
        if role == IdentityRole.SUPPORT_OFFICER and not set(actor.unit_ids) & QUEUES:
            raise CertificateError(403, "QUEUE_FORBIDDEN", "Cán bộ chưa được cấp quyền hàng đợi")

    def _owned(self, tx, actor, identifier, staff=False):
        self.authorize(actor, IdentityRole.SUPPORT_OFFICER if staff else IdentityRole.STUDENT)
        r = tx.get(identifier)
        if (not r or r["document_type"] not in KINDS
                or not staff and r["student_user_id"] != actor.subject_id
                or staff and (r["queue"] not in actor.unit_ids or r["status"] in {"DRAFT", "PENDING_CONFIRMATION"})):
            raise CertificateError(404, "RESOURCE_NOT_FOUND", "Không tìm thấy hồ sơ trong phạm vi được cấp")
        return r

    def courses(self, actor):
        self.authorize(actor, IdentityRole.STUDENT)
        with self.repository.transaction() as tx:
            rows = [r for r in tx.items("course") if r["owner"] == actor.subject_id]
            for r in rows:
                try:
                    guidance = self.knowledge.current(tx, "GRADE_APPEAL")
                    self._course(tx, actor, r["id"])
                    r["eligibility"] = "ELIGIBLE_DEMO"
                    r["guidance_version_id"] = guidance["version_id"]
                except CertificateError as exc:
                    r["eligibility"], r["eligibility_reason"] = exc.code, exc.detail
            return {"items": rows, "is_simulation": True, "real_school_eligibility": "unknown"}

    def _course(self, tx, actor, identifier):
        r = tx.item("course", identifier)
        if not r or r["owner"] != actor.subject_id:
            raise CertificateError(404, "COURSE_NOT_FOUND", "Học phần không thuộc sinh viên đang đăng nhập")
        source = tx.item("fixture", r["fixture_id"])
        if not source or digest(source["content"].encode()) != source["sha256"]:
            raise CertificateError(422, "ELIGIBILITY_DATA_MISSING", "Chưa xác minh nguồn dữ liệu học phần")
        expected = next((v for v in json.loads(source["content"])["courses"] if v["id"] == identifier), None)
        if not expected or any(r.get(k) != v for k, v in expected.items()):
            raise CertificateError(409, "COURSE_HASH_MISMATCH", "Course record không khớp nguồn mô phỏng")
        if not r.get("deadline") or r.get("eligible") is None:
            raise CertificateError(422, "ELIGIBILITY_DATA_MISSING", "Thiếu eligibility/hạn nộp; cần cán bộ hỗ trợ")
        if not r["eligible"] or r["exam_type"] != "WRITTEN":
            raise CertificateError(422, "COURSE_INELIGIBLE", "Cấu hình demo không cho phúc khảo học phần này")
        if datetime.now(UTC) >= datetime.fromisoformat(r["deadline"]):
            raise CertificateError(422, "APPEAL_DEADLINE_PASSED", "Đã quá hạn nộp mô phỏng")
        return r

    def _snapshot(self, tx, actor, form):
        profile = self.profile_reader(actor.subject_id)
        if not profile or profile.get("academic_status") != "ACTIVE":
            raise CertificateError(422, "PROFILE_UNAVAILABLE", "Chưa đủ dữ liệu identity/profile")
        try:
            guidance = self.knowledge.current(tx, form.kind)
        except CertificateError as exc:
            if form.kind != "GENERAL_SUPPORT" or exc.code not in {"MISSING_SOURCE", "SOURCE_NOT_CURRENT"}:
                raise
            guidance = {"unverified": exc.code}
        for ref in form.evidence_refs:
            version = tx.item("knowledge_version", ref)
            if not version or not version["published_at"]:
                raise CertificateError(422, "EVIDENCE_REFERENCE_INVALID", "Chỉ chia sẻ evidence được backend xác minh")
        version = self.knowledge._version(tx, guidance["version_id"]) if guidance.get("version_id") else None
        effectivity = {key: version[key] for key in ("id", "effective_from", "effective_until", "state")} if version else None
        return {"profile": profile, "guidance": guidance, "source_effectivity": effectivity,
                "course": self._course(tx, actor, form.course_record_id) if form.kind == "GRADE_APPEAL" else None}

    def save_draft(self, actor, form: ServiceForm, document_id=None, expected_version=None, *, preparation=None):
        self.authorize(actor, IdentityRole.STUDENT)
        with self.repository.transaction() as tx:
            if preparation is not None:
                replay = preparation.check(tx, self, actor, form, document_id)
                if replay is not None:
                    return replay
            snapshot = self._snapshot(tx, actor, form)
            if document_id:
                r = self._owned(tx, actor, document_id)
                self._version(r, expected_version)
                if r["document_type"] != form.kind:
                    raise CertificateError(422, "REQUEST_TYPE_MISMATCH", "Không đổi loại hồ sơ")
                try:
                    doc = entity(r).revise_draft()
                except InvalidDocumentRequestStateError:
                    raise CertificateError(409, "INVALID_STATE", "Hồ sơ đã gửi không thể sửa bản nháp") from None
            else:
                doc = DocumentRequest.create_draft(actor.subject_id, form.kind, "GENERAL")
                r = {"history": [], "profile": snapshot["profile"], "assigned_user_id": None,
                    "queue": "ACADEMIC_SERVICES" if form.kind == "GRADE_APPEAL" else "HUCE_GENERAL",
                    "supplement_request": None, "supplements": [], "messages": [], "result": None}
            r.update(serial(asdict(doc)))
            r.update(payload=form.model_dump(mode="json"), snapshot=snapshot, preview=None, disclaimer=DISCLAIMER)
            r.setdefault("draft_revisions", []).append({"version": r["version"], "payload": r["payload"], "snapshot": snapshot, "at": now()})
            r["attachment_manifest"] = [digest(a["content"].encode()) for a in r["payload"]["attachments"]]
            self._event(tx, r, actor, "draft.saved")
            if preparation is not None:
                preparation.complete(tx, r, actor)
            return self._public(r)

    def preview(self, actor, identifier, expected_version, form=None, note="", *, transaction=None):
        with nullcontext(transaction) if transaction is not None else self.repository.transaction() as tx:
            r = self._owned(tx, actor, identifier)
            self._version(r, expected_version)
            if form is None and r["status"] == "PENDING_CONFIRMATION":
                return self._resume_checked(tx, r, actor)
            supplement = form is not None
            chosen = form if supplement else ServiceForm.model_validate(r["payload"])
            if chosen.kind != r["document_type"] or supplement and chosen.course_record_id != r["payload"]["course_record_id"]:
                raise CertificateError(422, "REQUEST_TYPE_MISMATCH", "Không đổi học phần/loại khi bổ sung")
            snapshot = self._snapshot(tx, actor, chosen)
            if supplement:
                if r["status"] != "WAITING_STUDENT" or not note.strip():
                    raise CertificateError(409, "INVALID_STATE", "Cần yêu cầu bổ sung và nội dung phản hồi")
                r["version"] += 1
            else:
                try:
                    r.update(serial(asdict(entity(r).request_confirmation())))
                except InvalidDocumentRequestStateError:
                    raise CertificateError(409, "INVALID_STATE", "Chỉ bản nháp được xem trước") from None
                r["snapshot"] = snapshot
            p = create_action_preview(actor.subject_id, "SERVICE_SUPPLEMENT" if supplement else "SERVICE_SUBMIT",
                {"document_id": identifier, "version": r["version"], "form": chosen.model_dump(mode="json"),
                 "snapshot": snapshot, "note": note.strip(), "queue": r["queue"],
                 "submission_binding": self._submission_binding(actor, r)}, session_id=actor.session_id)
            r["preview"] = serial(asdict(p))
            self._event(tx, r, actor, "supplement.prepared" if supplement else "confirmation.prepared")
            response = self._preview_response(r)
            response.update(form=chosen.model_dump(mode="json"), operation=p.action_type, note=note.strip(), disclaimer=DISCLAIMER)
            return response

    def _resume_checked(self, tx, r, actor):
        if not r.get("preview"):
            raise CertificateError(409, "NO_PENDING_CONFIRMATION", "Cần preview mới")
        p = preview_entity(r["preview"])
        payload = json.loads(p.normalized_payload)
        if p.session_id != actor.session_id or not p.is_active(datetime.now(UTC)):
            raise CertificateError(409, "PREVIEW_EXPIRED_OR_SESSION_CHANGED", "Preview hết hạn/phiên thay đổi; xem trước lại")
        self._version(r, payload["version"])
        self._check_snapshot(tx, actor, payload, r)
        return {**self._preview_response(r), "form": payload["form"], "operation": p.action_type,
                "note": payload["note"], "disclaimer": DISCLAIMER}

    def _submission_binding(self, actor, record):
        definition = record_workflow(record)
        return {"tenant": actor.tenant_id, "actor": actor.subject_id, "session": actor.session_id,
            "target": record["id"], "version": record["version"], "queue": record["queue"],
            "rule": definition.version, "template": definition.template.version,
            "base_form_sha256": digest(record["payload"])}

    def _check_snapshot(self, tx, actor, payload, record=None):
        if record is not None and (payload.get("submission_binding") != self._submission_binding(actor, record)
                or payload["document_id"] != record["id"] or payload["queue"] != record["queue"]):
            raise CertificateError(409, "SUBMISSION_BINDING_CHANGED", "Đích gửi, mẫu hoặc hồ sơ đã đổi; xem trước lại")
        current = self._snapshot(tx, actor, ServiceForm.model_validate(payload["form"]))
        if current != payload["snapshot"]:
            raise CertificateError(409, "SOURCE_OR_ELIGIBILITY_CHANGED", "Nguồn/điều kiện đã đổi; lưu bản nháp và xem trước lại")

    def resume(self, actor, identifier):
        with self.repository.transaction() as tx:
            return self._resume_checked(tx, self._owned(tx, actor, identifier), actor)

    def confirm(self, actor, identifier, preview_id, token, key, form: ServiceForm, *, transaction=None):
        with nullcontext(transaction) if transaction is not None else self.repository.transaction() as tx:
            r = self._owned(tx, actor, identifier)
            if not r.get("preview"):
                raise CertificateError(409, "NO_PENDING_CONFIRMATION", "Cần preview trước xác nhận")
            p = preview_entity(r["preview"])
            payload = json.loads(p.normalized_payload)
            if form.model_dump(mode="json") != payload["form"]:
                raise CertificateError(422, "PAYLOAD_HASH_MISMATCH", "Payload khác bản xem trước")
            fingerprint = digest({"id": identifier, "preview_id": preview_id, "payload_hash": p.payload_hash})
            replay = tx.replay(actor.subject_id, key)
            valid = self.tokens.validate_token(token, preview_id, actor.subject_id, actor.session_id, "none",
                p.action_type, "1.0", "1.0", p.payload_hash, at_time=p.created_at if replay else None)
            if not valid.is_valid:
                raise CertificateError(422, valid.error_code, "Xác nhận không hợp lệ hoặc đã hết hạn")
            if replay:
                if replay["fingerprint"] != fingerprint:
                    raise CertificateError(409, "IDEMPOTENCY_CONFLICT", "Mã thử lại đã dùng cho payload khác")
                return {**replay["result"], "is_replay": True}
            if not p.is_active(datetime.now(UTC)):
                raise CertificateError(409, "PREVIEW_CONSUMED", "Preview đã dùng/hết hạn; đọc hồ sơ trước khi thử lại")
            self._version(r, payload["version"])
            self._check_snapshot(tx, actor, payload, r)
            if p.action_type == "SERVICE_SUPPLEMENT":
                if r["status"] != "WAITING_STUDENT":
                    raise CertificateError(409, "INVALID_STATE", "Hồ sơ không còn chờ bổ sung")
                definition = record_workflow(r)
                r["supplements"].append({"before": r["payload"], "form": payload["form"], "note": payload["note"], "at": now(),
                    "source_snapshot": payload["snapshot"]["guidance"], "workflow_version": definition.version,
                    "template_version": definition.template.version, "preview_id": p.id, "committed_version": r["version"]+1})
                r.update(payload=payload["form"], status="VALIDATING", version=r["version"]+1, supplement_request=None)
                r["attachment_manifest"] = [digest(a["content"].encode()) for a in r["payload"]["attachments"]]
                action = "request.supplement"
            else:
                try:
                    r.update(serial(asdict(entity(r).confirm_submit(generate_uuid7()))))
                except InvalidDocumentRequestStateError:
                    raise CertificateError(409, "INVALID_STATE", "Hồ sơ không còn chờ xác nhận") from None
                action = "request.submitted"
            r["preview"]["consumed_at"] = now()
            # This persisted request IS the queue record. No separate fake handover receipt.
            self._event(tx, r, actor, action, payload["note"])
            result = {"document_request_id": identifier, "status": r["status"], "queue": r["queue"],
                "tracking_url": f"/services?request={identifier}", "is_replay": False}
            tx.complete(actor.subject_id, key, fingerprint, result)
            return result

    def list(self, actor, staff=False, offset=0, limit=100):
        self.authorize(actor, IdentityRole.SUPPORT_OFFICER if staff else IdentityRole.STUDENT)
        with self.repository.transaction() as tx:
            rows = [r for r in tx.list(None if staff else actor.subject_id) if r["document_type"] in KINDS]
            if staff:
                rows = [r for r in rows if r["queue"] in actor.unit_ids and r["status"] not in {"DRAFT", "PENDING_CONFIRMATION"}]
            return {"items": [self._public(r) for r in rows[offset:offset+limit]], "page": {
                "next_cursor": str(offset+limit) if offset+limit < len(rows) else None, "has_more": offset+limit < len(rows)}}

    def staff(self, actor):
        self.authorize(actor, IdentityRole.SUPPORT_OFFICER)
        return {"items": [{"user_id": uid, **value} for uid, value in self.staff_directory.items()]}

    def act(self, actor, identifier, action, expected, key, note, target_user_id=None, target_queue=None, outcome=None, *, revalidate=None, transaction=None):
        with nullcontext(transaction) if transaction is not None else self.repository.transaction() as tx:
            actor = revalidate(tx) if revalidate else actor
            r = self._owned(tx, actor, identifier, staff=True)
            if r["assigned_user_id"] not in {None, actor.subject_id}:
                raise CertificateError(409, "ASSIGNED_ELSEWHERE", "Quyền phụ trách đã thay đổi; giữ nháp và đọc lại")
            fp = digest({"id": identifier, "action": action, "version": expected, "note": note,
                         "target": target_user_id, "queue": target_queue, "outcome": outcome})
            replay = tx.replay(actor.subject_id, key)
            if replay:
                if replay["fingerprint"] != fp:
                    raise CertificateError(409, "IDEMPOTENCY_CONFLICT", "Mã thử lại đã dùng")
                return {**replay["result"], "is_replay": True}
            self._version(r, expected)
            if not note.strip():
                raise CertificateError(422, "REASON_REQUIRED", "Cần lý do/nội dung xử lý")
            if r["assigned_user_id"] not in {None, actor.subject_id}:
                raise CertificateError(409, "ASSIGNED_ELSEWHERE", "Đã được cán bộ khác tiếp nhận")
            if action not in {"claim", "assign"} and r["assigned_user_id"] != actor.subject_id:
                raise CertificateError(409, "CLAIM_REQUIRED", "Cần tiếp nhận trước khi xử lý")
            try:
                state = staff_transition(r["status"], action)
            except ValueError:
                raise CertificateError(409, "INVALID_STATE", "Thao tác không phù hợp trạng thái") from None
            before = {"queue": r["queue"], "assigned_user_id": r["assigned_user_id"], "status": r["status"]}
            if action in {"assign", "transfer"}:
                queue = target_queue if action == "transfer" else r["queue"]
                target = self.staff_directory.get(target_user_id)
                if queue not in QUEUES or not target or queue not in target["queues"]:
                    raise CertificateError(422, "TARGET_QUEUE_FORBIDDEN", "Người nhận chưa được cấp quyền queue đích")
                r["queue"], r["assigned_user_id"] = queue, target_user_id
                r["preview"] = None
            elif action == "claim":
                r["assigned_user_id"] = actor.subject_id
            elif action == "request_information":
                r["supplement_request"] = note.strip()
                r["preview"] = None
            elif action == "resolve":
                if r["document_type"] == "GRADE_APPEAL" and outcome not in {"UNCHANGED", "CORRECTED", "UNABLE_TO_REVIEW"}:
                    raise CertificateError(422, "OUTCOME_REQUIRED", "Cán bộ phải chọn kết luận demo; AI không quyết định điểm")
                r["result"] = self._render(r, note.strip(), outcome or "RESPONDED")
            elif action == "reject":
                r["result"] = self._render(r, note.strip(), "REJECTED")
            r["messages"].append({"action": action, "text": note.strip(), "actor_id": actor.subject_id,
                                   "before": before, "after": {"queue": r["queue"], "assigned_user_id": r["assigned_user_id"]}, "at": now()})
            r.update(status=state, version=r["version"]+1, updated_at=now())
            self._event(tx, r, actor, "request." + action, note.strip())
            result = {"document_request": self._public(r), "is_replay": False}
            tx.complete(actor.subject_id, key, fp, result)
            return result

    def _render(self, r, note, outcome):
        try:
            template = record_workflow(r).template
        except (ValueError, TypeError, KeyError):
            raise CertificateError(409, "WORKFLOW_VERSION_UNRESOLVED", "Chưa xác định phiên bản mẫu theo mốc hồ sơ") from None
        if outcome not in template.outcomes:
            raise CertificateError(422, "OUTCOME_REQUIRED", "Kết luận không thuộc mẫu kết quả áp dụng")
        title = template.title
        html = ("<!doctype html><html lang='vi'><meta charset='utf-8'><title>" + escape(title) + "</title>"
            "<style>body{font:17px system-ui;max-width:760px;margin:40px auto;padding:24px;line-height:1.7}</style>"
            f"<h1>{escape(title)}</h1><strong>{DISCLAIMER}</strong><p>Hồ sơ: {escape(r['id'])}</p>"
            f"<p>Sinh viên: {escape(r['profile']['display_name'])}</p><p>Kết luận demo: {escape(outcome)}</p>"
            f"<p>{escape(note)}</p><p>Template: {template.version}. Không giả chữ ký/số hiệu chính thức.</p></html>")
        return {"title": title, "outcome": outcome, "note": note, "html": html, "checksum": digest(html.encode()),
                "template_version": template.version, "disclaimer": DISCLAIMER, "issued_at": now()}

    def result_html(self, actor, identifier):
        r = self.read(actor, identifier, staff=actor.has_role(IdentityRole.SUPPORT_OFFICER))
        if not r["result"]:
            raise CertificateError(409, "RESULT_NOT_READY", "Chưa có kết quả")
        value = r["result"]
        if digest(value["html"].encode()) != value["checksum"]:
            raise CertificateError(409, "RESULT_HASH_MISMATCH", "Kết quả không khớp checksum")
        return value["html"], value["checksum"]

    def attachment(self, actor, identifier, index):
        r = self.read(actor, identifier, staff=actor.has_role(IdentityRole.SUPPORT_OFFICER))
        items = r["payload"]["attachments"]
        if index < 0 or index >= len(items):
            raise CertificateError(404, "ATTACHMENT_NOT_FOUND", "Không có tệp")
        if digest(items[index]["content"].encode()) != r["attachment_manifest"][index]:
            raise CertificateError(409, "ATTACHMENT_HASH_MISMATCH", "Tệp không khớp checksum")
        return items[index]

    def propose(self, actor, message):
        self.authorize(actor, IdentityRole.STUDENT)
        from campus247.application.document_request.assistant import understand_student_goal
        intent = understand_student_goal(message)
        return {"intent": intent.workflow, "missing_fields": intent.missing_fields,
            "understanding": intent.model_dump(mode="json"), "message": intent.clarification or "Mở bản nháp để kiểm tra.",
            "requires_explicit_confirmation": True, "effect": "NONE", "proposal_engine": "deterministic demo intent adapter"}


class ServiceAgentTools:
    """Server binds actor. No grade, signature, staff transition or confirmation tool."""
    def __init__(self, service):
        self.service = service

    def read_own_requests(self, actor):
        return self.service.list(actor)

    def read_eligible_course_records(self, actor):
        return self.service.courses(actor)

    def explain_procedure(self, actor, kind):
        return self.service.knowledge.guidance(actor, kind)

    def prepare_request_draft(self, actor, form, document_id, expected_version):
        # User allocates stable draft; agent retries cannot create duplicates.
        r = self.service.read(actor, document_id)
        if r["payload"] != form.model_dump(mode="json") or r["version"] != expected_version:
            raise CertificateError(409, "STALE_VERSION", "Lưu dữ liệu qua form trước khi agent chuẩn bị preview")
        return self.service.preview(actor, document_id, expected_version)

    def build_action_preview(self, actor, document_id, expected_version):
        return self.service.preview(actor, document_id, expected_version)
