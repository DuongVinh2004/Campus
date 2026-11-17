"""Authorized certificate use cases. AI and routes cannot select an actor/state."""
from __future__ import annotations

from contextlib import nullcontext

import hashlib
import json
from dataclasses import asdict, fields
from datetime import datetime, timezone
from html import escape
from typing import Callable

from campus247.domain.action.confirmation import ConfirmationTokenService
from campus247.domain.action.preview import ActionPreviewValue, create_action_preview
from campus247.domain.document_request.certificate import CertificateForm, DISCLAIMER, QUEUE
from campus247.domain.document_request.model import (
    DocumentRequest, DocumentRequestStatus, DocumentDeliveryMethod,
    InvalidDocumentRequestStateError,
)
from campus247.domain.shared.values import generate_uuid7
from campus247.domain.certificate_workflow import certificate_workflow
from campus247.application.document_request.workflow_binding import capture_public_snapshot, checked_public_snapshot
from campus247.ports.certificate_repository import CertificateRepository
from campus247.ports.identity import IdentityContext, IdentityRole


class CertificateError(Exception):
    def __init__(self, status: int, code: str, detail: str):
        self.status, self.code, self.detail = status, code, detail
        super().__init__(detail)


def serial(value):
    return json.loads(json.dumps(value, ensure_ascii=False, default=lambda v: v.isoformat()))


def entity(record):
    value = {f.name: record[f.name] for f in fields(DocumentRequest)}
    for key in ("created_at", "updated_at", "submitted_at"):
        if value[key]:
            value[key] = datetime.fromisoformat(value[key])
    value["status"] = DocumentRequestStatus(value["status"])
    value["delivery_method"] = DocumentDeliveryMethod(value["delivery_method"])
    return DocumentRequest(**value)


def preview_entity(value):
    value = dict(value)
    for key in ("created_at", "expires_at", "consumed_at", "cancelled_at"):
        if value[key]:
            value[key] = datetime.fromisoformat(value[key])
    return ActionPreviewValue(**value)


class CertificateService:
    def __init__(self, repository: CertificateRepository, tokens: ConfirmationTokenService,
                 profile_reader: Callable[[str], dict | None], *, guidance_reader=None):
        self.repository, self.tokens, self.profile_reader = repository, tokens, profile_reader
        self.guidance_reader = guidance_reader

    def _guidance_snapshot(self):
        if self.guidance_reader is None:
            return None  # Legacy library adapter; runtime injects its verified reader.
        try:
            return capture_public_snapshot(self.guidance_reader())
        except (ValueError, TypeError, KeyError):
            raise CertificateError(422, "PUBLIC_SOURCE_INVALID", "Chưa xác minh được metadata bản chụp nguồn") from None

    def _check_guidance(self, record, preview_payload=None):
        if self.guidance_reader is None:
            return
        snapshot = record.get("guidance_snapshot")
        if not snapshot:
            raise CertificateError(409, "WORKFLOW_BINDING_UNRECORDED", "Hồ sơ cũ chưa lưu nguồn áp dụng; cần đối chiếu, không tự gán nguồn hiện tại")
        if preview_payload is not None and preview_payload.get("guidance_snapshot") != snapshot:
            raise CertificateError(409, "SOURCE_OR_WORKFLOW_CHANGED", "Nguồn khác bản xem trước; lưu nháp và xem trước lại")
        try:
            checked_public_snapshot(snapshot, self.guidance_reader())
            definition = certificate_workflow(record)
        except (ValueError, TypeError, KeyError) as exc:
            code = str(exc) if str(exc) in {"PUBLIC_SOURCE_CHANGED_OR_UNAVAILABLE", "SOURCE_SNAPSHOT_MISMATCH"} else "WORKFLOW_VERSION_UNRESOLVED"
            raise CertificateError(409, code, "Chưa đối chiếu được nguồn/quy trình áp dụng; không thực hiện từ bản cũ") from None
        if preview_payload is not None and preview_payload.get("workflow_version") != definition.version:
            raise CertificateError(409, "SOURCE_OR_WORKFLOW_CHANGED", "Quy trình khác bản xem trước; cần đối chiếu lại")

    def authorize(self, actor: IdentityContext, role=None):
        if (not actor.is_synthetic or not actor.is_active or actor.expires_at <= datetime.now(timezone.utc)
                or not actor.session_id or actor.tenant_id != "huce-local-public"):
            raise CertificateError(403, "DEMO_SCOPE_REQUIRED", "Cần phiên đăng nhập đang hoạt động")
        if role and not actor.has_role(role):
            raise CertificateError(403, "ROLE_REQUIRED", "Vai trò không có quyền thực hiện")
        if role == IdentityRole.SUPPORT_OFFICER and QUEUE not in actor.unit_ids:
            raise CertificateError(403, "QUEUE_FORBIDDEN", "Cán bộ không được cấp quyền hàng đợi này")

    def _owned(self, tx, actor, document_id, staff=False):
        self.authorize(actor, IdentityRole.SUPPORT_OFFICER if staff else IdentityRole.STUDENT)
        record = tx.get(document_id)
        if not record or record["document_type"] != "STUDENT_CERTIFICATE" or (not staff and record["student_user_id"] != actor.subject_id) or (
            staff and record["status"] in {"DRAFT", "PENDING_CONFIRMATION"}
        ):
            raise CertificateError(404, "RESOURCE_NOT_FOUND", "Không tìm thấy hồ sơ")
        return record

    def _version(self, record, expected):
        if record["version"] != expected:
            raise CertificateError(409, "STALE_VERSION", "Hồ sơ đã thay đổi. Tải lại trước khi thao tác.")

    def _event(self, tx, record, actor, action, note=""):
        event = {"id": generate_uuid7(), "document_id": record["id"],
                 "actor_id": actor.subject_id, "actor_role": "SUPPORT_OFFICER" if actor.has_role(IdentityRole.SUPPORT_OFFICER) else "STUDENT",
                 "action": action, "status": record["status"], "version": record["version"],
                 "occurred_at": datetime.now(timezone.utc).isoformat(), "note": note}
        record["history"].append(event)
        tx.save(record)
        tx.audit(event)
        sink = getattr(self, "business_event_sink", None)
        if sink is not None:
            sink(tx, record, actor, event)

    def _public(self, record):
        return {k: v for k, v in record.items() if k != "preview"}

    def save_draft(self, actor, form: CertificateForm, document_id=None, expected_version=None, *, preparation=None):
        self.authorize(actor, IdentityRole.STUDENT)
        with self.repository.transaction() as tx:
            if preparation is not None:
                replay = preparation.check(tx, self, actor, form, document_id)
                if replay is not None:
                    return replay
            if document_id:
                record = self._owned(tx, actor, document_id)
                self._version(record, expected_version)
                try:
                    doc = entity(record).revise_draft()
                except InvalidDocumentRequestStateError as exc:
                    raise CertificateError(409, "INVALID_STATE", "Hồ sơ đã gửi không thể sửa bản nháp") from exc
            else:
                profile = self.profile_reader(actor.subject_id)
                if not profile or profile.get("academic_status") != "ACTIVE":
                    raise CertificateError(422, "PROFILE_UNAVAILABLE", "Chưa đủ dữ liệu hồ sơ sinh viên; cần hỗ trợ")
                doc = DocumentRequest.create_draft(actor.subject_id, "STUDENT_CERTIFICATE", "GENERAL", form.delivery_method)
                record = {"profile": profile, "history": [], "assigned_user_id": None,
                          "supplement_request": None, "supplements": [], "result": None}
            record.update(serial(asdict(doc)))
            record["delivery_method"] = form.delivery_method
            record["disclaimer"] = DISCLAIMER
            record["payload"] = form.model_dump(mode="json")
            snapshot = self._guidance_snapshot()
            if snapshot is not None:
                record["guidance_snapshot"] = snapshot
                record.setdefault("draft_provenance", []).append({"version": record["version"], "source": snapshot})
            record["preview"] = None
            self._event(tx, record, actor, "draft.saved")
            if preparation is not None:
                preparation.complete(tx, record, actor)
            return self._public(record)

    def _preview_response(self, record):
        preview = preview_entity(record["preview"])
        return {"document_request": self._public(record), "preview_id": preview.id,
                "confirmation_token": self.tokens.mint_token(preview), "expires_at": preview.expires_at.isoformat(),
                "policy_decision": "ALLOW_WITH_CONFIRMATION"}

    def _submission_binding(self, actor, record):
        definition = certificate_workflow(record)
        return {"tenant": actor.tenant_id, "actor": actor.subject_id, "session": actor.session_id,
                "target": record["id"], "version": record["version"], "queue": definition.queue,
                "rule": definition.version, "template": definition.template.version}

    def _check_submission(self, actor, record, payload):
        if (payload.get("submission_binding") != self._submission_binding(actor, record)
                or payload["document_id"] != record["id"] or payload["version"] != record["version"]
                or payload["form"] != record["payload"] or payload["profile"] != record["profile"]
                or self.profile_reader(actor.subject_id) != record["profile"]):
            raise CertificateError(409, "SUBMISSION_BINDING_CHANGED", "Hồ sơ, danh tính, mẫu hoặc đích gửi đã đổi; xem trước lại")
        CertificateForm.model_validate(record["payload"])

    def preview(self, actor, document_id, expected_version):
        with self.repository.transaction() as tx:
            record = self._owned(tx, actor, document_id)
            self._version(record, expected_version)
            self._check_guidance(record)
            if record["status"] == "PENDING_CONFIRMATION":
                return self._resume(record, actor)
            try:
                doc = entity(record).request_confirmation()
            except InvalidDocumentRequestStateError as exc:
                raise CertificateError(409, "INVALID_STATE", "Chỉ bản nháp được xem trước") from exc
            record.update(serial(asdict(doc)))
            payload = {"document_id": doc.id, "version": doc.version, "student_user_id": actor.subject_id,
                       "form": record["payload"], "profile": record["profile"],
                       "submission_binding": self._submission_binding(actor, record)}
            if record.get("guidance_snapshot"):
                payload.update(guidance_snapshot=record["guidance_snapshot"], workflow_version=certificate_workflow(record).version)
            preview = create_action_preview(actor.subject_id, "SUBMIT_STUDENT_CERTIFICATE", payload,
                                            session_id=actor.session_id, policy_decision="ALLOW_WITH_CONFIRMATION")
            record["preview"] = serial(asdict(preview))
            self._event(tx, record, actor, "confirmation.prepared")
            return self._preview_response(record)

    def _resume(self, record, actor):
        if record["status"] != "PENDING_CONFIRMATION" or not record.get("preview"):
            raise CertificateError(409, "NO_PENDING_CONFIRMATION", "Không có bản xem trước đang chờ")
        p = preview_entity(record["preview"])
        if p.session_id != actor.session_id:
            raise CertificateError(409, "SESSION_MISMATCH", "Phiên đã đổi; lưu lại bản nháp và xem trước mới")
        if not p.is_active(datetime.now(timezone.utc)):
            raise CertificateError(409, "TOKEN_EXPIRED", "Xem trước đã hết hạn; lưu bản nháp và xem trước mới")
        self._check_guidance(record, json.loads(p.normalized_payload))
        self._check_submission(actor, record, json.loads(p.normalized_payload))
        return self._preview_response(record)

    def resume(self, actor, document_id):
        with self.repository.transaction() as tx:
            return self._resume(self._owned(tx, actor, document_id), actor)

    def confirm(self, actor, document_id, preview_id, token, key, form: CertificateForm):
        with self.repository.transaction() as tx:
            record = self._owned(tx, actor, document_id)
            raw = record.get("preview")
            if not raw:
                raise CertificateError(409, "NO_PENDING_CONFIRMATION", "Cần xem trước hồ sơ")
            p = preview_entity(raw)
            if form.model_dump(mode="json") != json.loads(p.normalized_payload)["form"]:
                raise CertificateError(422, "PAYLOAD_HASH_MISMATCH", "Dữ liệu khác bản đã xem trước")
            fingerprint = hashlib.sha256((document_id + preview_id + p.payload_hash).encode()).hexdigest()
            replay = tx.replay(actor.subject_id, key)
            if replay and replay["fingerprint"] != fingerprint:
                raise CertificateError(409, "IDEMPOTENCY_CONFLICT", "Mã thử lại đã dùng cho yêu cầu khác")
            validation = self.tokens.validate_token(token, preview_id, actor.subject_id, actor.session_id, "none",
                "SUBMIT_STUDENT_CERTIFICATE", "1.0", "1.0", p.payload_hash,
                at_time=p.created_at if replay else None)
            if not validation.is_valid:
                raise CertificateError(422, validation.error_code or "INVALID_TOKEN", "Xác nhận không hợp lệ hoặc đã hết hạn")
            if replay:
                return {**replay["result"], "is_replay": True}
            if p.is_consumed():
                raise CertificateError(409, "PREVIEW_CONSUMED", "Bản xem trước đã được gửi; mở hồ sơ để theo dõi")
            self._check_guidance(record, json.loads(p.normalized_payload))
            self._check_submission(actor, record, json.loads(p.normalized_payload))
            try:
                doc = entity(record).confirm_submit(generate_uuid7())
            except InvalidDocumentRequestStateError as exc:
                raise CertificateError(409, "INVALID_STATE", "Hồ sơ không còn chờ xác nhận") from exc
            record.update(serial(asdict(doc)))
            record["preview"]["consumed_at"] = datetime.now(timezone.utc).isoformat()
            self._event(tx, record, actor, "request.submitted")
            result = {"document_request_id": doc.id, "status": doc.status.value,
                      "tracking_url": f"/tickets?request={doc.id}", "is_replay": False}
            tx.complete(actor.subject_id, key, fingerprint, result)
            return result

    def list(self, actor, staff=False, offset=0, limit=20):
        self.authorize(actor, IdentityRole.SUPPORT_OFFICER if staff else IdentityRole.STUDENT)
        with self.repository.transaction() as tx:
            rows = [r for r in tx.list(None if staff else actor.subject_id) if r["document_type"] == "STUDENT_CERTIFICATE"]
            if staff:
                rows = [r for r in rows if r["status"] not in {"DRAFT", "PENDING_CONFIRMATION"}]
            return {"items": [self._public(r) for r in rows[offset:offset+limit]],
                    "page": {"next_cursor": str(offset+limit) if offset+limit < len(rows) else None,
                             "has_more": offset+limit < len(rows), "limit": limit}}

    def read(self, actor, document_id, staff=False):
        with self.repository.transaction() as tx:
            return self._public(self._owned(tx, actor, document_id, staff))

    def act(self, actor, document_id, action, expected_version, key, note="", form=None, *, revalidate=None, transaction=None):
        staff = action != "supplement"
        with nullcontext(transaction) if transaction is not None else self.repository.transaction() as tx:
            actor = revalidate(tx) if revalidate else actor
            record = self._owned(tx, actor, document_id, staff)
            if staff and record["assigned_user_id"] not in {None, actor.subject_id}:
                raise CertificateError(409, "ASSIGNED_ELSEWHERE", "Quyền phụ trách đã thay đổi; giữ nháp và đọc lại")
            fingerprint = hashlib.sha256(json.dumps({"id": document_id, "action": action,
                "version": expected_version, "note": note, "form": form.model_dump(mode="json") if form else None}, sort_keys=True).encode()).hexdigest()
            replay = tx.replay(actor.subject_id, key)
            if replay:
                if replay["fingerprint"] != fingerprint:
                    raise CertificateError(409, "IDEMPOTENCY_CONFLICT", "Mã thử lại đã dùng cho yêu cầu khác")
                return {**replay["result"], "is_replay": True}
            self._version(record, expected_version)
            if staff and record["assigned_user_id"] not in {None, actor.subject_id}:
                raise CertificateError(409, "ASSIGNED_ELSEWHERE", "Hồ sơ đã được cán bộ khác tiếp nhận")
            if staff and action != "accept" and record["assigned_user_id"] != actor.subject_id:
                raise CertificateError(409, "ACCEPT_REQUIRED", "Cần tiếp nhận trước khi xử lý")
            if action in {"request_supplement", "approve", "reject", "supplement"} and not note.strip():
                raise CertificateError(422, "REASON_REQUIRED", "Cần ghi lý do hoặc nội dung bổ sung")
            doc = entity(record)
            try:
                if action == "accept":
                    doc = doc.start_validation()
                    record["assigned_user_id"] = actor.subject_id
                elif action == "request_supplement":
                    doc = doc.request_supplement()
                    record["supplement_request"] = note.strip()
                elif action == "supplement":
                    if form is None:
                        raise CertificateError(422, "FORM_REQUIRED", "Cần dữ liệu bổ sung")
                    doc = doc.submit_supplement()
                    before_payload = record["payload"]
                    record["payload"] = form.model_dump(mode="json")
                    record["delivery_method"] = form.delivery_method
                    source = self._guidance_snapshot()
                    record["supplements"].append({"note": note.strip(), "before": before_payload,
                        "payload": record["payload"], "at": datetime.now(timezone.utc).isoformat(), "source_snapshot": source,
                        "committed_version": doc.version,
                        "workflow_version": certificate_workflow(record).version,
                        "template_version": certificate_workflow(record).template.version})
                    record["supplement_request"] = None
                elif action == "approve":
                    self._check_guidance(record)
                    if doc.status == DocumentRequestStatus.VALIDATING:
                        doc = doc.start_processing()
                    doc = doc.mark_ready()
                    record["result"] = {"title": certificate_workflow(record).template.title, "disclaimer": DISCLAIMER,
                        "issued_at": doc.updated_at.isoformat(), "profile": record["profile"], "payload": record["payload"]}
                    record["result"].update(template_version=certificate_workflow(record).template.version,
                        workflow_version=certificate_workflow(record).version,
                        source_fingerprint=(record.get("guidance_snapshot") or {}).get("fingerprint"),
                        institutional_rules_verified=False)
                elif action == "reject":
                    doc = doc.reject("DEMO_OFFICER_REJECTION")
                else:
                    raise CertificateError(422, "UNKNOWN_ACTION", "Thao tác không được hỗ trợ")
            except InvalidDocumentRequestStateError as exc:
                raise CertificateError(409, "INVALID_STATE", "Chuyển trạng thái không hợp lệ") from exc
            record.update(serial(asdict(doc)))
            self._event(tx, record, actor, "request." + action, note.strip())
            result = {"document_request": self._public(record), "is_replay": False}
            tx.complete(actor.subject_id, key, fingerprint, result)
            return result

    def result_html(self, actor, document_id):
        record = self.read(actor, document_id, actor.has_role(IdentityRole.SUPPORT_OFFICER))
        result = record.get("result")
        if not result:
            raise CertificateError(409, "RESULT_NOT_READY", "Chưa có kết quả")
        profile, form = result["profile"], result["payload"]
        return ("<!doctype html><html lang='vi'><meta charset='utf-8'><title>Giấy xác nhận sinh viên</title>"
                "<style>body{font:17px system-ui;max-width:760px;margin:60px auto;padding:24px;line-height:1.7}"
                "h1{text-align:center;font-size:25px}header{border-bottom:1px solid #ddd;padding-bottom:12px}</style>"
                f"<header>Campus 24/7 · Dịch vụ sinh viên</header><h1>{escape(result['title'].upper())}</h1>"
                f"<p>Mã hồ sơ: {escape(document_id)}</p><p>Họ và tên: {escape(profile['display_name'])}<br>"
                f"Mã sinh viên: {escape(profile['student_code'])}<br>Chương trình: {escape(profile['program_code'])}</p>"
                f"<p>Mục đích: {escape(form['purpose'])}<br>Nơi nộp: {escape(form['recipient'])}</p>"
                f"<p>Ngày cấp: {escape(result['issued_at'][:10])}</p></html>")
