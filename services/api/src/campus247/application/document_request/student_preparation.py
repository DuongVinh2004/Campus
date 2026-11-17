"""Student U4 consumer over existing intent, proposal, workflow and draft services.

No model tool is registered here. Preparing is read-only; a separate explicit
user gesture saves a draft, with receipt in the existing business transaction.
"""
from datetime import datetime, timezone
from typing import Literal

from pydantic import Field, ValidationError, model_validator
from campus247.application.assistance.contracts import StrictDTO, ResourceRef
from campus247.application.assistance.unified_contracts import UUID, Hash, Workflow, DraftProposal, FieldChange
from campus247.application.assistance.workflow import WorkflowResolveRequest
from campus247.application.document_request.assistant import understand_student_goal
from campus247.application.document_request.certificates import CertificateError
from campus247.application.knowledge.operations import digest
from campus247.domain.document_request.certificate import CertificateForm
from campus247.domain.service_request import ServiceForm
from campus247.domain.service_workflow import workflow_at
from campus247.domain.certificate_workflow import CERTIFICATE_WORKFLOWS
from campus247.ports.identity import IdentityRole

KINDS = {"STUDENT_CERTIFICATE": "certificate_request", "GRADE_APPEAL": "service_request", "GENERAL_SUPPORT": "service_request"}
FIELDS = {"purpose", "recipient", "quantity", "delivery_method", "reason", "course_record_id", "contact_preference"}


class StudentGoal(StrictDTO):
    goal: str = Field(min_length=1, max_length=2000)
    workflow: Workflow | None = None
    resource: ResourceRef | None = None
    statements: dict[str, str | int] = Field(default_factory=dict, max_length=7)
    constraints: list[str] = Field(default_factory=list, max_length=8)
    operation_id: UUID

    @model_validator(mode="after")
    def plain_statements(self):
        if not self.goal.strip() or "\x00" in self.goal or set(self.statements) - FIELDS:
            raise ValueError("explicit supported user statements required")
        for key, value in self.statements.items():
            if key == "quantity":
                if type(value) is not int or not 1 <= value <= 3:
                    raise ValueError("quantity must be an integer from 1 to 3")
            elif not isinstance(value, str) or len(value) > 2000 or "\x00" in value:
                raise ValueError("bounded user statement required")
        if any(not v.strip() or len(v) > 2000 or "\x00" in v for v in self.constraints):
            raise ValueError("bounded constraints required")
        return self


class SavePreparedDraft(StrictDTO):
    request: StudentGoal
    expected_sha256: Hash
    reviewed: Literal[True]


def form_binding(service, actor, form, tx):
    kind = "STUDENT_CERTIFICATE" if isinstance(form, CertificateForm) else form.kind
    definition = (workflow_at(kind, datetime.now(timezone.utc), CERTIFICATE_WORKFLOWS)
                  if kind == "STUDENT_CERTIFICATE" else workflow_at(kind, datetime.now(timezone.utc)))
    snapshot = ({"guidance": service._guidance_snapshot(), "profile": service.profile_reader(actor.subject_id)}
                if kind == "STUDENT_CERTIFICATE" else service._snapshot(tx, actor, form))
    if kind == "STUDENT_CERTIFICATE" and snapshot["guidance"]:
        snapshot["guidance"] = {k: v for k, v in snapshot["guidance"].items() if k != "captured_at"}
    return {"workflow": kind, "workflow_version": definition.version, "template_version": definition.template.version,
            "queue": definition.queue, "snapshot": snapshot}


class DraftSaveGuard:
    def __init__(self, request, prepared, fingerprint):
        self.request, self.prepared, self.fingerprint = request, prepared, fingerprint
        self.key = "student-draft:" + request.operation_id
        self.replayed = False

    def check(self, tx, service, actor, form, document_id):
        receipt = tx.replay(actor.subject_id, self.key)
        if receipt:
            if receipt["fingerprint"] != self.fingerprint:
                raise CertificateError(409, "IDEMPOTENCY_CONFLICT", "Mã lưu đã dùng cho nội dung hoặc phiên khác")
            self.replayed = True
            return service._public(service._owned(tx, actor, receipt["result"]["document_request_id"]))
        if document_id is None and any(r["document_type"] == self.prepared["intent"]["workflow"] and
                r["status"] in {"DRAFT", "PENDING_CONFIRMATION"} for r in tx.list(actor.subject_id)):
            raise CertificateError(409, "DRAFT_SELECTION_REQUIRED", "Đã có bản nháp; chọn hồ sơ trước khi lưu")
        if form_binding(service, actor, form, tx) != self.prepared["binding"]:
            raise CertificateError(409, "SOURCE_OR_WORKFLOW_CHANGED", "Nguồn, hồ sơ hoặc mẫu đã đổi; chuẩn bị lại")

    def complete(self, tx, record, actor):
        if record["document_type"] == "STUDENT_CERTIFICATE":
            guidance = record.get("guidance_snapshot")
            snapshot = {"profile": record["profile"], "guidance":
                {key: value for key, value in guidance.items() if key != "captured_at"} if guidance else None}
        else:
            snapshot = record["snapshot"]
        if snapshot != self.prepared["binding"]["snapshot"] or record["payload"] != self.prepared["form"]:
            raise CertificateError(409, "PREPARATION_CHANGED", "Dữ liệu đổi trong khi lưu; giữ nháp và chuẩn bị lại")
        record.setdefault("student_preparations", []).append({"operation_id": self.request.operation_id,
            "goal": self.request.goal, "constraints": self.request.constraints,
            "statements": self.request.statements, "origin": "explicit_user_statement",
            "version": record["version"], "binding_sha256": digest(self.prepared["binding"])})
        tx.save(record)
        tx.complete(actor.subject_id, self.key, self.fingerprint,
                    {"document_request_id": record["id"], "resource_kind": KINDS[record["document_type"]],
                     "version": record["version"], "effect": "draft_saved"})


class StudentPreparationService:
    def __init__(self, resources, proposals):
        self.resources, self.proposals = resources, proposals

    def service(self, actor, kind):
        service = self.resources.get(kind)
        if service is None:
            raise CertificateError(503, "STUDENT_DRAFT_UNAVAILABLE", "Chưa cấu hình dịch vụ nháp này")
        service.authorize(actor, IdentityRole.STUDENT)
        return service

    def action_inventory(self, actor):
        self.service(actor, "certificate_request")
        # This composition's student inventory; other writers must advertise
        # their own consumers. Presence of a legacy endpoint is not support.
        rows = [
            ("navigation", "/", "manual", "Mở dịch vụ từ điều hướng"),
            ("identity", "/login", "manual", "Đăng nhập hoặc đổi tài khoản"),
            ("chat", "/chat", "read_prepare", "Hỏi nguồn; capability model tùy writer"),
            ("certificate.prepare", "/tickets", "prepare", "Chuẩn bị hoặc chọn nháp giấy xác nhận"),
            ("certificate.fields", "/tickets", "read_prepare", "Đối chiếu trường và nguồn đã lưu"),
            ("certificate.attachments", "/tickets", "manual", "Tệp .txt UTF-8 tối đa 16 KB; OCR chưa có"),
            ("certificate.submit", "/tickets", "explicit_confirmation", "Xem trước và xác nhận đúng hồ sơ"),
            ("certificate.result", "/tickets", "read", "Đọc trạng thái, lịch sử và kết quả"),
            ("service.prepare", "/services", "prepare", "Chọn phúc khảo hoặc hỗ trợ chung và nháp cụ thể"),
            ("service.fields", "/services", "read_prepare", "Đọc học phần được cấp và sửa trường còn thiếu"),
            ("service.attachments", "/services", "manual", "Tệp .txt UTF-8 tối đa 16 KB; OCR chưa có"),
            ("service.submit", "/services", "explicit_confirmation", "Xem trước và xác nhận gửi hoặc bổ sung"),
            ("service.result", "/services", "read", "Đọc receipt, lịch sử và kết quả"),
            ("requests", "/tickets", "read", "Mở hồ sơ theo ID đã được máy chủ kiểm quyền"),
            ("privacy", "/privacy", "manual", "Đọc consent/settings và xác nhận thay đổi riêng"),
            ("schedule", "/schedule", "unavailable", "Lịch cá nhân chưa kết nối; mở Hỏi đáp để tra nguồn lịch công khai"),
            ("rooms", "/rooms", "unavailable", "Đặt phòng chưa có consumer; mở Hỗ trợ để hỏi đơn vị quản lý"),
            ("ticket.handover", "/services", "unavailable", "Chuyển từ chat chưa có consumer; tự chọn nội dung chia sẻ trong Hỗ trợ chung"),
            ("legacy.forms", "/services", "unavailable", "Giữ nháp cục bộ; mở biểu mẫu dịch vụ có máy chủ"),
        ]
        return {"items": [{"action": action, "route": route, "support": support, "next_step": step}
                          for action, route, support, step in rows], "writer": "business_services",
                "institutional_rules_verified": False, "mobile_verified": False}

    def prepare(self, actor, request):
        # Authorize even ambiguous/unsupported requests before returning context.
        self.service(actor, "certificate_request")
        record = None
        if request.resource:
            service = self.service(actor, request.resource.kind)
            record = service.read(actor, request.resource.id)
            service._version(record, request.resource.expected_version)
            if record["status"] != "DRAFT":
                raise CertificateError(409, "DRAFT_REQUIRED", "Mở và lưu bản nháp trước khi chuẩn bị thay đổi")
        fields = {key: value for key, value in (record["payload"] if record else {}).items() if key in FIELDS}
        fields.update({key: value.strip() if isinstance(value, str) else value for key, value in request.statements.items()})
        intent = understand_student_goal(request.goal, workflow=request.workflow or (record["document_type"] if record else None), fields=fields,
            resource=request.resource, constraints=request.constraints)
        result = {"intent": intent.model_dump(mode="json"), "effect": "NONE", "action_authority": "none",
            "candidates": [], "diff": [], "field_errors": [], "binding": None, "form": None,
            "provenance": {key: {"origin": "explicit_user_statement" if key in request.statements else "saved_resource",
                "resource": request.resource.model_dump(mode="json") if request.resource else None} for key in fields},
            "next_action": "clarify", "ocr": {"available": False, "reason": "OCR_CONSUMER_NOT_CONFIGURED"}}
        if not intent.workflow:
            return result
        kind = KINDS[intent.workflow]
        service = self.service(actor, kind)
        if record and (request.resource.kind != kind or record["document_type"] != intent.workflow):
            result.update(next_action="choose_workflow", field_errors=[{"field": "workflow", "code": "GOAL_CHANGED",
                "detail": "Mục đích mới cần hồ sơ riêng; bản nháp hiện tại được giữ nguyên."}])
            return result
        if not record:
            # Enumerate all owned drafts inside the existing repository, not a
            # truncated list page and never the most recent arbitrary record.
            with service.repository.transaction() as tx:
                candidates = [r for r in tx.list(actor.subject_id) if r["document_type"] == intent.workflow
                              and r["status"] in {"DRAFT", "PENDING_CONFIRMATION"}]
            result["candidates"] = [{"kind": kind, "id": r["id"], "expected_version": r["version"], "status": r["status"]} for r in candidates]
            if candidates:
                result["next_action"] = "choose_draft"
                return result
        if intent.missing_fields:
            return result
        payload = dict(record["payload"]) if record else {}
        payload.update(fields)
        if kind == "service_request":
            payload["kind"] = intent.workflow
        try:
            form = (CertificateForm if kind == "certificate_request" else ServiceForm).model_validate(payload)
        except ValidationError as exc:
            result["field_errors"] = [{"field": ".".join(map(str, error["loc"])) or "form",
                "code": error["type"], "detail": error["msg"], "source": "server_form_schema"}
                for error in exc.errors(include_input=False, include_url=False)]
            return result
        try:
            with service.repository.transaction() as tx:
                result["binding"] = form_binding(service, actor, form, tx)
        except CertificateError as exc:
            result["field_errors"] = [{"field": "course_record_id" if exc.code.startswith(("COURSE", "APPEAL", "ELIGIBILITY")) else "form",
                "code": exc.code, "detail": exc.detail, "source": "server_domain_validator"}]
            return result
        result["form"] = form.model_dump(mode="json")
        if record:
            changes = [FieldChange(field=key, before=record["payload"].get(key), candidate=value, origin="user_statement")
                       for key, value in fields.items() if value != record["payload"].get(key)]
            result["diff"] = [change.model_dump(mode="json") for change in changes]
            if changes:
                # Reuse the same validated draft specialist/proposal package.
                evidence = self.proposals.workflow.resolve(actor, WorkflowResolveRequest(resource=request.resource))
                result["workflow_package"] = evidence.model_dump(mode="json")
                binding = evidence.binding
                if binding and binding.source.classification == "synthetic":
                    source = binding.source
                    proposal = DraftProposal.model_validate({"client_id": request.operation_id,
                        "target": request.resource.model_dump(mode="json"), "operation": "revise_draft", "audience": "student",
                        "changes": result["diff"], "workflow_binding": {"workflow": evidence.resource.workflow,
                            "version": binding.workflow_version, "source": {"source_id": source.source_id,
                                "version_id": source.version_id, "locator": source.locator,
                                "sha256": source.rendition_sha256, "classification": source.classification},
                            "effective_from": source.effective_from, "effective_until": source.effective_until}})
                    result["proposal"] = self.proposals.bundle(actor, proposal).model_dump(mode="json")
        result["next_action"] = "review_diff" if record else "review_new_draft"
        result["sha256"] = digest({"actor": actor.subject_id, "tenant": actor.tenant_id,
            "session": actor.session_id, "request": request.model_dump(mode="json"), "prepared": result})
        return result

    def _read_saved(self, actor, request, fingerprint):
        for kind in ("certificate_request", "service_request"):
            service = self.service(actor, kind)
            with service.repository.transaction() as tx:
                replay = tx.replay(actor.subject_id, "student-draft:" + request.operation_id)
            if replay:
                if replay["fingerprint"] != fingerprint:
                    raise CertificateError(409, "IDEMPOTENCY_CONFLICT", "Mã lưu đã dùng cho nội dung hoặc phiên khác")
                # Service and certificate tables share a replay namespace but
                # their get() readers target different tables. Close this
                # transaction before reopening with the receipt's exact service.
                correct = self.service(actor, replay["result"]["resource_kind"])
                value = correct.read(actor, replay["result"]["document_request_id"])
                return {"document_request": value, "receipt": replay["result"], "is_replay": True}
        return None

    def save(self, actor, body):
        request = body.request
        fingerprint = digest({"request": request.model_dump(mode="json"), "sha256": body.expected_sha256,
                              "tenant": actor.tenant_id, "session": actor.session_id})
        replay = self._read_saved(actor, request, fingerprint)
        if replay:
            return replay
        try:
            prepared = self.prepare(actor, request)
        except CertificateError:
            # A concurrent same-operation commit may have advanced the version
            # between the first receipt lookup and preparation.
            replay = self._read_saved(actor, request, fingerprint)
            if replay:
                return replay
            raise
        if prepared.get("sha256") != body.expected_sha256 or not prepared["form"]:
            replay = self._read_saved(actor, request, fingerprint)
            if replay:
                return replay
            raise CertificateError(409, "PREPARATION_CHANGED", "Nháp, mục đích hoặc nguồn đã đổi; xem lại đề xuất")
        kind = KINDS[prepared["intent"]["workflow"]]
        service = self.service(actor, kind)
        form = (CertificateForm if kind == "certificate_request" else ServiceForm).model_validate(prepared["form"])
        guard = DraftSaveGuard(request, prepared, fingerprint)
        service.save_draft(actor, form, request.resource.id if request.resource else None,
            request.resource.expected_version if request.resource else None,
            preparation=guard)
        result = self._read_saved(actor, request, fingerprint)
        if result is None:
            raise CertificateError(503, "DRAFT_RECEIPT_UNAVAILABLE", "Chưa đọc được receipt; giữ mã lưu để thử lại")
        return {**result, "is_replay": guard.replayed}
