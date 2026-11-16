"""Human-reviewed case work, executed through existing business transactions.

No model tool receives these write methods. All preparation is private and
readback is derived from the same business records used by existing consumers.
"""
from dataclasses import asdict
from datetime import datetime, timezone

from campus247.application.assistance.case_contracts import CaseDraftPrepare, CaseConfirm
from campus247.application.assistance.contracts import ResourceRef
from campus247.application.assistance.workflow import WorkflowResolveRequest
from campus247.application.document_request.certificates import CertificateError, preview_entity, serial
from campus247.application.knowledge.operations import digest
from campus247.domain.action.preview import create_action_preview
from campus247.domain.shared.values import generate_uuid7
from campus247.ports.identity import IdentityRole

def fail(code, text, status=409):
    raise CertificateError(status, code, text)

def stamp():
    return datetime.now(timezone.utc).isoformat()

class CaseWorkflowService:
    def __init__(self, resources, workspace, repository, tokens, *, tenant="huce-local-public"):
        self.resources, self.workspace, self.repository, self.tokens = resources, workspace, repository, tokens
        self.tenant = tenant

    def key(self, actor, *parts):
        return digest([self.tenant, actor.subject_id, *parts])

    def authorize(self, actor, *, staff=True):
        next(iter(self.resources.values())).authorize(actor, IdentityRole.SUPPORT_OFFICER if staff else IdentityRole.STUDENT)
        if actor.tenant_id != self.tenant:
            fail("TENANT_REQUIRED", "Cần đúng tenant", 403)

    def _current(self, tx, actor, target, *, assigned=True):
        return self.workspace.current(tx, actor, target, assigned=assigned)

    def _context(self, tx, actor, target):
        record = self._current(tx, actor, target)
        dossier = self.workspace._prepare(tx, actor, target, record)
        package = self.workspace.workflow.resolve(actor, WorkflowResolveRequest(resource=target), transaction=tx, tolerate_source_errors=True)
        return record, dossier, package

    def _drafts(self, tx, actor, target):
        return sorted([r for r in self.repository.records(tx, "draft") if r["owner"] == actor.subject_id
            and r["tenant"] == self.tenant and r["body"]["resource"]["kind"] == target.kind
            and r["body"]["resource"]["id"] == target.id], key=lambda r: r["version"])

    def _validate(self, tx, actor, body, record, dossier, package):
        if record["student_user_id"] != body.student_id or body.recipient_id != body.student_id:
            fail("RECIPIENT_MISMATCH", "Đích công khai phải là đúng sinh viên của hồ sơ")
        if (dossier.binding_hash != body.binding_hash or not package.binding or not package.template
                or package.definition_version != body.workflow_version or package.template.version != body.template_version):
            fail("STALE_CASE_BINDING", "Nguồn, quy trình, mẫu hoặc hồ sơ đã đổi; giữ nháp và đối chiếu lại")
        refs = {s.id for s in dossier.sources}
        if not set(body.fact_source_ids) <= refs:
            fail("FACT_SOURCE_MISMATCH", "Facts phải chọn đúng nguồn đã đối chiếu của hồ sơ", 422)
        if body.operation in {"resolve", "approve", "reject"}:
            if body.outcome not in package.template.outcomes:
                fail("OUTCOME_TEMPLATE_MISMATCH", "Kết luận không thuộc mẫu áp dụng", 422)
            if (body.operation == "reject") != (body.outcome == "REJECTED"):
                fail("OUTCOME_ACTION_MISMATCH", "Kết luận và thao tác không khớp", 422)
        elif body.outcome != {"respond": "RESPONDED", "request_supplement": "SUPPLEMENT_REQUIRED", "transfer": "TRANSFERRED"}[body.operation]:
            fail("OUTCOME_ACTION_MISMATCH", "Kết luận và thao tác không khớp", 422)
        if body.resource.kind == "certificate_request" and body.operation not in {"approve", "reject", "request_supplement"}:
            fail("ACTION_UNAVAILABLE", "Luồng giấy xác nhận chưa có consumer cho thao tác này", 422)
        if body.resource.kind == "service_request" and body.operation == "approve":
            fail("ACTION_UNAVAILABLE", "Dịch vụ dùng thao tác trả kết quả", 422)
        criteria = {f.id for f in dossier.findings}
        fields = set(record["payload"])
        formats = {"attachments": "text/plain", "course_record_id": "course_reference", "quantity": "integer",
            "delivery_method": "delivery_method", "contact_preference": "contact_preference"}
        for item in body.supplement_items:
            if (item.criterion_id not in criteria or not set(item.source_ids) <= refs or item.field not in fields
                    or item.accepted_format != formats.get(item.field, "text")):
                fail("SUPPLEMENT_ITEM_BINDING", "Mục bổ sung phải gắn đúng tiêu chí, nguồn, trường và định dạng", 422)
        if body.handover:
            self._target(actor, body.handover)
            if not set(body.handover.evidence_ids) <= refs:
                fail("HANDOVER_SOURCE_MISMATCH", "Bàn giao chỉ dùng nguồn đã chọn trong hồ sơ", 422)
            if any(len(s) > 500 or not s.strip() for s in [*body.handover.done, *body.handover.open]):
                fail("HANDOVER_SUMMARY_INVALID", "Cần tóm tắt từng phần trong giới hạn", 422)

    def _target(self, actor, summary):
        service = self.resources["service_request"]
        entry = service.staff_directory.get(summary.target_actor)
        if (not entry or summary.target_queue not in entry["queues"] or summary.target_actor == actor.subject_id):
            fail("TARGET_QUEUE_FORBIDDEN", "Người nhận phải có quyền hàng đợi đích và khác người gửi", 422)

    def _ready(self, body, dossier):
        pending = [f.id for f in dossier.findings if f.layer == "officer_review" and f.state != "checked"]
        errors = [f.id for f in dossier.findings if f.state in {"error", "conflicting"}
            or f.layer == "deterministic" and f.state != "checked"
            and not (body.operation == "request_supplement" and f.id in {i.criterion_id for i in body.supplement_items})]
        if pending or errors or dossier.readiness == "waiting" or "SUPPLEMENT_SOURCE_UNRESOLVED" in dossier.reasons or "TERMINAL_RECORD_READ_ONLY" in dossier.reasons:
            fail("OFFICER_REVIEW_REQUIRED", "Cần hoàn tất kiểm tra bắt buộc và xử lý nguồn thiếu/lỗi; nháp được giữ")

    def prepare(self, actor, body, *, revalidate=None):
        with self.resources[body.resource.kind].repository.transaction() as tx:
            actor = revalidate(tx) if revalidate else actor
            record, dossier, package = self._context(tx, actor, body.resource)
            self._validate(tx, actor, body, record, dossier, package)
            previous = self._drafts(tx, actor, body.resource)
            key = self.key(actor, "prepare", body.client_id)
            replay = self.repository.read(tx, "draft", key)
            if replay:
                if replay["body"] != body.model_dump(mode="json"):
                    fail("IDEMPOTENCY_CONFLICT", "Mã nháp đã dùng cho nội dung khác")
                return {**replay, "is_replay": True, "action_authority": "none"}
            if body.expected_draft_version != (previous[-1]["version"] if previous else 0):
                fail("DRAFT_CAS_CONFLICT", "Nháp server đã đổi; giữ nội dung và đọc lại")
            value = {"id": key, "owner": actor.subject_id, "tenant": self.tenant, "version": body.expected_draft_version + 1,
                "body": body.model_dump(mode="json"), "facts": [s.model_dump(mode="json") for s in dossier.sources if s.id in body.fact_source_ids],
                "created_at": stamp(), "institutional_rules_verified": False}
            self.repository.insert(tx, "draft", value)
            return {**value, "is_replay": False, "action_authority": "none"}

    def read_draft(self, actor, target, *, revalidate=None):
        with self.resources[target.kind].repository.transaction() as tx:
            actor = revalidate(tx) if revalidate else actor
            _, dossier, _ = self._context(tx, actor, target)
            drafts = self._drafts(tx, actor, target)
            value = drafts[-1] if drafts else None
            return {"draft": value, "binding_stale": bool(value and value["body"]["binding_hash"] != dossier.binding_hash), "action_authority": "none"}

    def _preview(self, tx, actor, body):
        record, dossier, package = self._context(tx, actor, body.resource)
        drafts = self._drafts(tx, actor, body.resource)
        if not drafts or drafts[-1]["version"] != body.draft_version:
            fail("DRAFT_CAS_CONFLICT", "Cần đọc đúng nháp server mới nhất")
        draft = drafts[-1]
        chosen = CaseDraftPrepare.model_validate(draft["body"])
        self._validate(tx, actor, chosen, record, dossier, package)
        self._ready(chosen, dossier)
        key = self.key(actor, "preview", body.client_id)
        stored = self.repository.read(tx, "preview", key)
        review_hash = digest([f.model_dump(mode="json") for f in dossier.findings])
        payload = {"draft_id": draft["id"], "draft_version": draft["version"], "resource": body.resource.model_dump(),
            "binding_hash": dossier.binding_hash, "reviews_hash": review_hash, "owner": actor.subject_id, "tenant": self.tenant}
        if stored:
            if stored["payload"] != payload or stored["session"] != actor.session_id:
                fail("IDEMPOTENCY_CONFLICT", "Mã xem trước đã dùng với dữ liệu/phiên khác")
            preview = preview_entity(stored["preview"])
            if not preview.is_active(datetime.now(timezone.utc)):
                fail("PREVIEW_EXPIRED", "Xem trước đã hết hạn; giữ nháp và xem trước lại")
        else:
            preview = create_action_preview(actor.subject_id, "STAFF_CASE_COMMIT", payload, session_id=actor.session_id)
            stored = {"id": key, "session": actor.session_id, "payload": payload, "preview": serial(asdict(preview))}
            self.repository.insert(tx, "preview", stored)
        # The public preview is explicitly constructed; internal_note never falls
        # through into a business note, message, result or student projection.
        public = {"resource": chosen.resource.model_dump(), "student_id": chosen.student_id, "recipient_id": chosen.recipient_id,
            "operation": chosen.operation, "outcome": chosen.outcome, "facts": draft["facts"], "reasons": chosen.public_reasons,
            "workflow_version": chosen.workflow_version, "template_version": chosen.template_version,
            "supplement_items": [i.model_dump() for i in chosen.supplement_items],
            "handover": chosen.handover.model_dump() if chosen.handover and chosen.handover.visibility == "public" else None}
        return {"preview_id": preview.id, "confirmation_token": self.tokens.mint_token(preview), "client_id": body.client_id,
            "expires_at": preview.expires_at.isoformat(), "public": public,
            "internal": {"note": chosen.internal_note, "handover": chosen.handover.model_dump() if chosen.handover and chosen.handover.visibility == "internal" else None},
            "action_authority": "none", "institutional_rules_verified": False}

    def preview(self, actor, body, *, revalidate=None):
        with self.resources[body.resource.kind].repository.transaction() as tx:
            actor = revalidate(tx) if revalidate else actor
            return self._preview(tx, actor, body)

    def _find_preview(self, tx, actor, preview_id):
        value = next((v for v in self.repository.records(tx, "preview") if v["preview"]["id"] == preview_id
            and v["payload"]["owner"] == actor.subject_id and v["payload"]["tenant"] == self.tenant), None)
        if not value:
            fail("PREVIEW_NOT_FOUND", "Không tìm thấy xem trước trong phạm vi", 404)
        return value

    def _confirm(self, tx, actor, body):
        self.authorize(actor)
        stored = self._find_preview(tx, actor, body.preview_id)
        preview = preview_entity(stored["preview"])
        key = self.key(actor, "receipt", body.client_id)
        receipt = self.repository.read(tx, "receipt", key)
        valid = self.tokens.validate_token(body.confirmation_token, preview.id, actor.subject_id, actor.session_id,
            "none", preview.action_type, "1.0", "1.0", preview.payload_hash, at_time=preview.created_at if receipt else None)
        if not valid.is_valid:
            fail("INVALID_CONFIRMATION", "Phiên hoặc xác nhận không hợp lệ/hết hạn", 422)
        if receipt:
            if receipt["preview_id"] != preview.id:
                fail("IDEMPOTENCY_CONFLICT", "Mã xác nhận đã dùng với xem trước khác")
            return {**receipt, "is_replay": True}
        consumed = next((r for r in self.repository.records(tx, "receipt") if r["preview_id"] == preview.id), None)
        if consumed or not preview.is_active(datetime.now(timezone.utc)):
            fail("PREVIEW_CONSUMED_OR_EXPIRED", "Đọc receipt trước khi thử lại; không tạo thao tác mới")
        payload = stored["payload"]
        draft = self.repository.read(tx, "draft", payload["draft_id"])
        chosen = CaseDraftPrepare.model_validate(draft["body"])
        record, dossier, package = self._context(tx, actor, chosen.resource)
        if self._drafts(tx, actor, chosen.resource)[-1]["id"] != draft["id"]:
            fail("DRAFT_CAS_CONFLICT", "Nháp đã sửa sau xem trước; giữ nháp và xem trước lại")
        self._validate(tx, actor, chosen, record, dossier, package)
        self._ready(chosen, dossier)
        if digest([f.model_dump(mode="json") for f in dossier.findings]) != payload["reviews_hash"]:
            fail("STALE_REVIEW", "Review đã đổi sau xem trước; giữ nháp và đối chiếu lại")
        service = self.resources[chosen.resource.kind]
        action = chosen.operation
        if chosen.resource.kind == "service_request" and action == "request_supplement":
            action = "request_information"
        note = "\n".join(chosen.public_reasons)
        extra = {} if chosen.resource.kind == "certificate_request" else {"outcome": chosen.outcome}
        if chosen.handover:
            self._target(actor, chosen.handover)
            extra.update(target_queue=chosen.handover.target_queue, target_user_id=chosen.handover.target_actor)
        service.act(actor, chosen.resource.id, action, chosen.resource.expected_version,
            "case-executor:" + preview.id, note, transaction=tx, **extra)
        current = service._owned(tx, actor, chosen.resource.id, staff=True) if not chosen.handover else tx.get(chosen.resource.id)
        if chosen.supplement_items:
            request = {"id": generate_uuid7(), "resource_kind": chosen.resource.kind, "resource_id": current["id"],
                "tenant": self.tenant, "student_id": chosen.student_id, "version": current["version"],
                "workflow_version": chosen.workflow_version, "template_version": chosen.template_version,
                "source_binding": package.binding.model_dump(mode="json"), "items": [i.model_dump() for i in chosen.supplement_items], "at": stamp()}
            self.repository.insert(tx, "supplement", request)
        if chosen.handover:
            self.repository.insert(tx, "handover", {"id": preview.id, "tenant": self.tenant, "resource_id": current["id"],
                "from_actor": actor.subject_id, "to_actor": current["assigned_user_id"], "queue": current["queue"],
                "version": current["version"], "summary": chosen.handover.model_dump(), "at": stamp()})
        receipt = {"id": key, "receipt_id": generate_uuid7(), "owner": actor.subject_id, "tenant": self.tenant,
            "preview_id": preview.id, "resource": {"kind": chosen.resource.kind, "id": current["id"], "version": current["version"]},
            "status": current["status"], "queue": current.get("queue", "HUCE_GENERAL"), "assigned_actor": current["assigned_user_id"],
            "operation": chosen.operation, "state": "committed", "at": stamp()}
        self.repository.insert(tx, "receipt", receipt)
        return {**receipt, "is_replay": False}

    def confirm(self, actor, body, *, revalidate=None):
        # Both resources share the configured local business DB, but choose the
        # exact repository transaction after resolving the actor-owned preview.
        with self.resources["service_request"].repository.transaction() as lookup:
            actor = revalidate(lookup) if revalidate else actor
            stored = self._find_preview(lookup, actor, body.preview_id)
            kind = stored["payload"]["resource"]["kind"]
        with self.resources[kind].repository.transaction() as tx:
            actor = revalidate(tx) if revalidate else actor
            return self._confirm(tx, actor, body)

    def receipt(self, actor, client_id, *, revalidate=None):
        with self.resources["service_request"].repository.transaction() as tx:
            actor = revalidate(tx) if revalidate else actor
            self.authorize(actor)
            value = self.repository.read(tx, "receipt", self.key(actor, "receipt", client_id))
            return {"receipt": value, "state": "committed" if value else "not_observed", "retry": "read_preview_before_retry"}

    def _student_record(self, tx, actor, target):
        self.authorize(actor, staff=False)
        service = self.resources[target.kind]
        record = service._owned(tx, actor, target.id)
        service._version(record, target.expected_version)
        return record

    def _supplements(self, tx, record, kind):
        return sorted([v for v in self.repository.records(tx, "supplement") if v["tenant"] == self.tenant
            and v["resource_kind"] == kind and v["resource_id"] == record["id"]
            and v["student_id"] == record["student_user_id"]], key=lambda v: v["version"])

    def checklist(self, actor, target, *, revalidate=None):
        with self.resources[target.kind].repository.transaction() as tx:
            actor = revalidate(tx) if revalidate else actor
            record = self._student_record(tx, actor, target)
            requests = self._supplements(tx, record, target.kind)
            responses = [v for v in self.repository.records(tx, "response") if v["tenant"] == self.tenant
                and v["student_id"] == actor.subject_id and v["resource_id"] == record["id"] and v["resource_kind"] == target.kind]
            return {"resource": target.model_dump(), "requests": requests, "responses": responses,
                "current_request": requests[-1] if requests and record["status"] == "WAITING_STUDENT" else None,
                "response_meaning": "submitted_for_officer_delta_recheck_not_accepted_evidence", "action_authority": "none"}

    def _response_data(self, tx, actor, body):
        from campus247.domain.service_request import ServiceForm
        from campus247.domain.document_request.certificate import CertificateForm
        record = self._student_record(tx, actor, body.resource)
        requests = self._supplements(tx, record, body.resource.kind)
        if (record["status"] != "WAITING_STUDENT" or not requests or requests[-1]["id"] != body.request_id
                or requests[-1]["version"] != body.request_version):
            fail("STALE_SUPPLEMENT_REQUEST", "Yêu cầu bổ sung đã đổi; giữ nội dung và đọc checklist mới")
        request = requests[-1]
        items = {i["id"]: i for i in request["items"]}
        if len({i.item_id for i in body.responses}) != len(body.responses) or {i.item_id for i in body.responses} != set(items):
            fail("SUPPLEMENT_ITEM_MAPPING", "Cần đáp ứng đúng từng item của yêu cầu, không thêm hoặc trùng mục", 422)
        form = {**record["payload"]}
        attachment_values = []
        fields = set()
        for response in body.responses:
            item = items[response.item_id]
            if response.field != item["field"]:
                fail("SUPPLEMENT_FIELD_MAPPING", "Phản hồi không đúng trường của item", 422)
            if response.field != "attachments" and response.field in fields:
                fail("SUPPLEMENT_FIELD_AMBIGUOUS", "Các item cùng trường cần được cán bộ nhóm lại", 422)
            fields.add(response.field)
            if response.field == "attachments":
                if not isinstance(response.value, str) or not response.value.strip() or len(response.value.encode()) > 16384:
                    fail("SUPPLEMENT_FORMAT", "Tài liệu text/plain cần nội dung trong giới hạn 16 KB", 422)
                attachment_values.append({"name": response.item_id + ".txt", "content": response.value,
                    **({"media_type": "text/plain"} if body.resource.kind == "service_request" else {})})
            else:
                if isinstance(response.value, str) and (not response.value.strip() or len(response.value) > 2000):
                    fail("SUPPLEMENT_FORMAT", "Cần nội dung trong giới hạn trường", 422)
                form[response.field] = response.value
        if attachment_values:
            form["attachments"] = [*record["payload"].get("attachments", []), *attachment_values]
        try:
            typed = (ServiceForm if body.resource.kind == "service_request" else CertificateForm).model_validate(form)
        except ValueError:
            fail("SUPPLEMENT_FORMAT", "Phản hồi không khớp định dạng/giới hạn của biểu mẫu; giữ nội dung để sửa", 422)
        package = self.workspace.workflow.resolve(actor, WorkflowResolveRequest(resource=body.resource), transaction=tx, tolerate_source_errors=True)
        if not package.binding or package.reasons or package.binding.model_dump(mode="json") != request["source_binding"]:
            fail("SUPPLEMENT_SOURCE_CHANGED", "Nguồn/quy trình đã đổi hoặc lỗi; giữ nội dung, không tự từ chối hồ sơ")
        service = self.resources[body.resource.kind]
        snapshot = service._snapshot(tx, actor, typed) if body.resource.kind == "service_request" else service._guidance_snapshot()
        if body.resource.kind == "certificate_request" and snapshot is not None:
            # The new observation timestamp changes on every read. Bind source
            # identities/hashes/fingerprint; the stored record/package capture
            # milestone remains exact in the other binding inputs below.
            snapshot = {k: v for k, v in snapshot.items() if k != "captured_at"}
        binding = digest({"record": record, "package": package.model_dump(mode="json"), "profile": service.profile_reader(actor.subject_id), "snapshot": snapshot})
        return record, typed, binding

    def response_preview(self, actor, body, *, revalidate=None):
        with self.resources[body.resource.kind].repository.transaction() as tx:
            actor = revalidate(tx) if revalidate else actor
            _, form, binding = self._response_data(tx, actor, body)
            key = self.key(actor, "response_preview", body.client_id)
            payload = {"owner": actor.subject_id, "tenant": self.tenant, "resource": body.resource.model_dump(),
                "body": body.model_dump(mode="json"), "form": form.model_dump(mode="json"), "binding": binding}
            stored = self.repository.read(tx, "student_preview", key)
            if stored:
                if stored["payload"] != payload:
                    fail("IDEMPOTENCY_CONFLICT", "Mã bổ sung đã dùng cho nội dung khác")
                p = preview_entity(stored["preview"])
                if p.session_id != actor.session_id or not p.is_active(datetime.now(timezone.utc)):
                    fail("PREVIEW_EXPIRED", "Phiên hoặc xem trước đã đổi; giữ nội dung và xem trước lại")
            else:
                p = create_action_preview(actor.subject_id, "STUDENT_ITEM_SUPPLEMENT", payload, session_id=actor.session_id)
                self.repository.insert(tx, "student_preview", {"id": key, "payload": payload, "preview": serial(asdict(p))})
            return {"preview_id": p.id, "client_id": body.client_id, "confirmation_token": self.tokens.mint_token(p),
                "expires_at": p.expires_at.isoformat(), "request_id": body.request_id,
                "responses": [r.model_dump() for r in body.responses], "form": form.model_dump(mode="json"), "action_authority": "none"}

    def response_confirm(self, actor, body, *, revalidate=None):
        from campus247.application.assistance.case_contracts import SupplementResponse
        self.authorize(actor, staff=False)
        with self.resources["service_request"].repository.transaction() as lookup:
            actor = revalidate(lookup) if revalidate else actor
            stored = next((v for v in self.repository.records(lookup, "student_preview") if v["preview"]["id"] == body.preview_id
                and v["payload"]["owner"] == actor.subject_id and v["payload"]["tenant"] == self.tenant), None)
        if not stored:
            fail("PREVIEW_NOT_FOUND", "Không tìm thấy xem trước của sinh viên", 404)
        chosen = SupplementResponse.model_validate(stored["payload"]["body"])
        service = self.resources[chosen.resource.kind]
        with service.repository.transaction() as tx:
            actor = revalidate(tx) if revalidate else actor
            self.authorize(actor, staff=False)
            key = self.key(actor, "student_receipt", body.client_id)
            receipt = self.repository.read(tx, "student_receipt", key)
            p = preview_entity(stored["preview"])
            valid = self.tokens.validate_token(body.confirmation_token, p.id, actor.subject_id, actor.session_id,
                "none", p.action_type, "1.0", "1.0", p.payload_hash, at_time=p.created_at if receipt else None)
            if not valid.is_valid:
                fail("INVALID_CONFIRMATION", "Xác nhận/phiên không hợp lệ", 422)
            if receipt:
                if receipt["preview_id"] != p.id:
                    fail("IDEMPOTENCY_CONFLICT", "Mã xác nhận đã dùng")
                return {**receipt, "is_replay": True}
            if (not p.is_active(datetime.now(timezone.utc)) or any(r["preview_id"] == p.id for r in self.repository.records(tx, "student_receipt"))):
                fail("PREVIEW_CONSUMED_OR_EXPIRED", "Đọc receipt trước khi thử lại")
            record, form, binding = self._response_data(tx, actor, chosen)
            if binding != stored["payload"]["binding"]:
                fail("STALE_SUPPLEMENT_BINDING", "Nguồn/hồ sơ đã đổi; giữ nội dung bổ sung")
            if chosen.resource.kind == "certificate_request":
                service.act(actor, record["id"], "supplement", record["version"], "case-student:" + p.id, chosen.note, form, transaction=tx)
            else:
                business_preview = service.preview(actor, record["id"], record["version"], form, chosen.note, transaction=tx)
                service.confirm(actor, record["id"], business_preview["preview_id"], business_preview["confirmation_token"],
                    "case-student:" + p.id, form, transaction=tx)
            current = tx.get(record["id"])
            mapped = {"id": generate_uuid7(), "tenant": self.tenant, "student_id": actor.subject_id,
                "resource_id": current["id"], "resource_kind": chosen.resource.kind, "request_id": chosen.request_id,
                "request_version": chosen.request_version, "responses": [r.model_dump() for r in chosen.responses],
                "version": current["version"], "workflow_version": self._supplements(tx, current, chosen.resource.kind)[-1]["workflow_version"],
                "source_binding": stored["payload"]["binding"], "review_state": "requires_officer_delta_recheck", "at": stamp()}
            self.repository.insert(tx, "response", mapped)
            receipt = {"id": key, "preview_id": p.id, "receipt_id": generate_uuid7(), "owner": actor.subject_id,
                "resource_id": current["id"], "resource_kind": chosen.resource.kind, "version": current["version"],
                "state": "committed", "status": current["status"], "at": stamp()}
            self.repository.insert(tx, "student_receipt", receipt)
            return {**receipt, "is_replay": False}

    def projection(self, actor, target, *, revalidate=None):
        service = self.resources[target.kind]
        with service.repository.transaction() as tx:
            actor = revalidate(tx) if revalidate else actor
            staff = actor.has_role(IdentityRole.SUPPORT_OFFICER)
            self.authorize(actor, staff=staff)
            record = self._current(tx, actor, target, assigned=False) if staff else self._student_record(tx, actor, target)
            package = self.workspace.workflow.resolve(actor, WorkflowResolveRequest(resource=target), transaction=tx, tolerate_source_errors=True)
            requests = self._supplements(tx, record, target.kind)
            common = {"schema_version": "case-projection.v1", "resource": {"kind": target.kind, "id": target.id,
                "version": record["version"], "status": record["status"]}, "view": "staff" if staff else "student",
                "queue": record.get("queue", "HUCE_GENERAL"), "supplement_requests": requests,
                "public_history": [{k: e[k] for k in ("id", "action", "status", "version", "occurred_at")} for e in record["history"]],
                "result": record.get("result"), "source_state": package.binding_status,
                "workflow_version": package.definition_version, "source_fingerprint": package.binding.sha256 if package.binding else None,
                "invalidates": ["business", "workflow", "staff_workspace", "draft_binding", "supplement", "queue", "tracking"],
                "refresh": "revalidate_each_read_including_source_and_current_session", "action_authority": "none"}
            handovers = [v for v in self.repository.records(tx, "handover") if v["tenant"] == self.tenant and v["resource_id"] == target.id]
            common["handovers"] = [{"version": v["version"], "queue": v["queue"], "summary": v["summary"]} for v in handovers
                if v["summary"]["visibility"] == "public" or staff and record["assigned_user_id"] == actor.subject_id and v["to_actor"] == actor.subject_id]
            if staff:
                common["assigned_actor"] = record["assigned_user_id"]
                common["staff_workspace"] = self.workspace._prepare(tx, actor, target, record).model_dump(mode="json")
            common["projection_hash"] = digest(common)
            return common

    def events(self, actor, target, *, revalidate=None):
        # Invalidation is durable; source/grant revocation additionally changes
        # the per-read projection hash even without a business transition.
        self.projection(actor, target, revalidate=revalidate)
        with self.resources[target.kind].repository.transaction() as tx:
            actor = revalidate(tx) if revalidate else actor
            staff = actor.has_role(IdentityRole.SUPPORT_OFFICER)
            self._current(tx, actor, target, assigned=False) if staff else self._student_record(tx, actor, target)
            rows = [v for v in self.repository.records(tx, "event") if v["tenant"] == self.tenant and v["resource_id"] == target.id and v["resource_kind"] == target.kind]
            return {"schema_version": "case-events.v1", "resource": target.model_dump(), "events": [
                {k: v[k] for k in ("id", "version", "status", "action", "occurred_at", "invalidate")} for v in sorted(rows, key=lambda r: (r["version"], r["id"]))],
                "delivery": "transactional_append_only_readback", "action_authority": "none"}

    def notification_open(self, actor, event_id, *, revalidate=None):
        with self.resources["service_request"].repository.transaction() as tx:
            actor = revalidate(tx) if revalidate else actor
            row = self.repository.read(tx, "tracking_event", event_id)
            if not row or row["tenant"] != actor.tenant_id or row["recipient_id"] != actor.subject_id:
                fail("NOTIFICATION_NOT_FOUND", "Không tìm thấy event trong phạm vi hiện tại", 404)
            target = ResourceRef.model_validate(row["resource"])
        value = self.projection(actor, target, revalidate=revalidate)
        return {"resource": target.model_dump(), "projection_hash": value["projection_hash"],
            "open_path": ("/services" if target.kind == "service_request" else "/staff" if value["view"] == "staff" else "/tickets") + "?request=" + target.id,
            "handover": value["handovers"], "action_authority": "none"}

    def staff_intent(self, actor, body, *, revalidate=None):
        self.authorize(actor)
        if len(body.resources) != 1 and body.surface != "queue":
            return {"status": "needs_clarification", "support": "manual", "reason": "SELECT_ONE_EXACT_CASE", "action_authority": "none"}
        for target in body.resources:
            self.projection(actor, target, revalidate=revalidate)
        supported = {"queue": {"read", "route"}, "detail": {"read"}, "checklist": {"read", "review"},
            "editor": {"read", "prepare"}, "error": {"read", "retry"}, "handover": {"read", "prepare"}, "admin": set()}
        state = "supported" if body.intent in supported[body.surface] else "unavailable"
        return {"status": "bound" if body.resources else "queue_scope_only", "support": state,
            "resources": [r.model_dump() for r in body.resources], "surface": body.surface, "intent": body.intent,
            "guidance": "Đọc hồ sơ đã lưu và nguồn; review/soạn tại workspace. Xem trước và xác nhận từng thao tác. Lỗi gửi: đọc receipt trước retry." if state == "supported" else "Mở trang quản trị nguồn để đối chiếu và thao tác theo quyền; chưa có consumer trợ lý thực hiện quản trị.",
            "excluded": ["unsaved_private_form", "DOM", "private_memory", "model_business_writes"], "action_authority": "none"}

    def batch_prepare(self, actor, body, *, revalidate=None):
        self.authorize(actor)
        key = self.key(actor, "batch", body.client_id)
        fingerprint = digest(body.model_dump(mode="json"))
        with self.resources["service_request"].repository.transaction() as tx:
            actor = revalidate(tx) if revalidate else actor
            previous = self.repository.read(tx, "batch", key)
            if previous:
                if previous["fingerprint"] != fingerprint or previous["session"] != actor.session_id:
                    fail("BATCH_TARGET_DRIFT", "Danh sách/phiên bản batch đã đổi; giữ bản cũ")
                return previous
        items = []
        for item in body.items:
            try:
                p = self.preview(actor, item, revalidate=revalidate)
                items.append({"resource": item.resource.model_dump(), "draft_version": item.draft_version,
                    "client_id": item.client_id, "preview_id": p["preview_id"], "public": p["public"], "state": "prepared"})
            except CertificateError as exc:
                items.append({"resource": item.resource.model_dump(), "draft_version": item.draft_version,
                    "client_id": item.client_id, "state": "blocked", "code": exc.code})
        value = {"id": key, "batch_id": body.client_id, "owner": actor.subject_id, "tenant": self.tenant,
            "session": actor.session_id, "fingerprint": fingerprint, "items": items, "target_hash": digest(items), "at": stamp(),
            "mode": "individual_human_reviewed_execution", "action_authority": "none"}
        with self.resources["service_request"].repository.transaction() as tx:
            actor = revalidate(tx) if revalidate else actor
            existing = self.repository.read(tx, "batch", key)
            if existing:
                if existing["fingerprint"] != fingerprint or existing["session"] != actor.session_id:
                    fail("BATCH_TARGET_DRIFT", "Batch đã được chuẩn bị với danh sách khác")
                return existing
            self.repository.insert(tx, "batch", value)
        return value

    def batch_confirm(self, actor, body, *, revalidate=None):
        self.authorize(actor)
        with self.resources["service_request"].repository.transaction() as tx:
            actor = revalidate(tx) if revalidate else actor
            value = self.repository.read(tx, "batch", self.key(actor, "batch", body.batch_id))
        if not value or value["target_hash"] != body.target_hash or value["session"] != actor.session_id:
            fail("BATCH_TARGET_DRIFT", "Cần đúng danh sách và phiên đã xem trước")
        results = []
        for item in value["items"]:
            if item["state"] == "blocked":
                results.append({"resource": item["resource"], "state": "blocked", "code": item["code"]})
                continue
            target = ResourceRef.model_validate(item["resource"])
            try:
                with self.resources[target.kind].repository.transaction() as tx:
                    actor = revalidate(tx) if revalidate else actor
                    self.authorize(actor)
                    # Each item's durable receipt is read before any retry.
                    receipt = self.repository.read(tx, "receipt", self.key(actor, "receipt", item["client_id"]))
                    if receipt:
                        if receipt["preview_id"] != item["preview_id"]:
                            fail("IDEMPOTENCY_CONFLICT", "Receipt không thuộc item")
                        results.append({"resource": item["resource"], "state": "committed", "receipt": receipt, "is_replay": True})
                        continue
                    stored = self._find_preview(tx, actor, item["preview_id"])
                    p = preview_entity(stored["preview"])
                    receipt = self._confirm(tx, actor, CaseConfirm(preview_id=p.id, confirmation_token=self.tokens.mint_token(p), client_id=item["client_id"], confirmed=True))
                    results.append({"resource": item["resource"], "state": "committed", "receipt": receipt})
            except CertificateError as exc:
                results.append({"resource": item["resource"], "state": "blocked", "code": exc.code})
            except (OSError, RuntimeError):
                results.append({"resource": item["resource"], "state": "uncertain", "next_action": "read_receipt_before_retry"})
        result = {"id": generate_uuid7(), "batch_id": body.batch_id, "owner": actor.subject_id, "tenant": self.tenant,
            "target_hash": value["target_hash"], "results": results,
            "state": "completed" if all(r["state"] == "committed" for r in results) else "uncertain" if any(r["state"] == "uncertain" for r in results) else "partial", "at": stamp()}
        with self.resources["service_request"].repository.transaction() as tx:
            actor = revalidate(tx) if revalidate else actor
            self.authorize(actor)
            self.repository.insert(tx, "batch_result", result)
        return result

    def batch_read(self, actor, batch_id, *, revalidate=None):
        with self.resources["service_request"].repository.transaction() as tx:
            actor = revalidate(tx) if revalidate else actor
            self.authorize(actor)
            batch = self.repository.read(tx, "batch", self.key(actor, "batch", batch_id))
            if not batch or batch["session"] != actor.session_id:
                fail("BATCH_NOT_FOUND", "Không tìm thấy batch trong phiên/phạm vi hiện tại", 404)
            results = [v for v in self.repository.records(tx, "batch_result") if v["batch_id"] == batch_id
                and v["owner"] == actor.subject_id and v["tenant"] == self.tenant]
            return {"batch": batch, "latest": sorted(results, key=lambda v: v["at"])[-1] if results else None,
                "retry": "read_individual_receipts_first", "action_authority": "none"}

    def queue(self, actor, body, *, revalidate=None):
        service = self.resources[body.kind]
        self.authorize(actor)
        with service.repository.transaction() as tx:
            actor = revalidate(tx) if revalidate else actor
            self.authorize(actor)
            rows = [r for r in tx.list(None) if r["document_type"] in ({"STUDENT_CERTIFICATE"} if body.kind == "certificate_request" else {"GENERAL_SUPPORT", "GRADE_APPEAL"})
                and r.get("queue", "HUCE_GENERAL") in actor.unit_ids and r["status"] not in {"DRAFT", "PENDING_CONFIRMATION"}]
            items = []
            for record in rows[:body.limit]:
                target = ResourceRef(kind=body.kind, id=record["id"], expected_version=record["version"])
                reason = "WAITING_FOR_STUDENT" if record["status"] == "WAITING_STUDENT" else "ASSIGNED_TO_ANOTHER" if record["assigned_user_id"] not in {None, actor.subject_id} else "OFFICER_REVIEW_REQUIRED"
                group = "waiting" if record["status"] == "WAITING_STUDENT" else "blocked"
                if reason == "OFFICER_REVIEW_REQUIRED":
                    try:
                        dossier = self.workspace._prepare(tx, actor, target, record)
                        if dossier.readiness == "ready":
                            group, reason = "ready", "EXPLICIT_REVIEWS_AND_SOURCE_CHECKS_CURRENT"
                        elif dossier.reasons:
                            reason = ";".join(dossier.reasons)
                    except CertificateError as exc:
                        reason = exc.code
                items.append({"resource": target.model_dump(), "group": group, "status": record["status"],
                    "queue": record.get("queue", "HUCE_GENERAL"), "assigned_actor": record["assigned_user_id"],
                    "reason": reason, "priority": "group_only_no_model_score", "deadline": None,
                    "deadline_reason": "PROCESSING_DEADLINE_SOURCE_UNCONFIGURED", "routing": "CURRENT_QUEUE_REQUIRES_EXPLICIT_AUTHORIZED_TRANSFER"})
            return {"items": items, "truncated": len(rows) > body.limit, "policy": "readiness_groups_preserve_business_order_within_each_group",
                "queue_mutations": False, "action_authority": "none"}

    def dashboard(self, actor, body, *, revalidate=None):
        queue = self.queue(actor, body, revalidate=revalidate)
        groups = {k: sum(i["group"] == k for i in queue["items"]) for k in ("ready", "waiting", "blocked")}
        counts = {"supplement": 0, "transfer": 0, "reopen": 0}
        waits = {"student_wait": 0.0, "unit_wait": 0.0}
        ages = {"under_1_day": 0, "1_to_7_days": 0, "over_7_days": 0}
        complexity = {}
        now = datetime.now(timezone.utc)
        with self.resources[body.kind].repository.transaction() as tx:
            actor = revalidate(tx) if revalidate else actor
            self.authorize(actor)
            for item in queue["items"]:
                record = self.resources[body.kind]._owned(tx, actor, item["resource"]["id"], staff=True)
                self.resources[body.kind]._version(record, item["resource"]["expected_version"])
                complexity[record["document_type"]] = complexity.get(record["document_type"], 0) + 1
                age = (now - datetime.fromisoformat(record["created_at"])).total_seconds()
                ages["under_1_day" if age < 86400 else "1_to_7_days" if age <= 604800 else "over_7_days"] += 1
                history = record["history"]
                for index, event in enumerate(history):
                    action = event["action"]
                    counts["supplement"] += action in {"request.request_information", "request.request_supplement"}
                    counts["transfer"] += action == "request.transfer"
                    counts["reopen"] += action == "request.reopen"
                    until = datetime.fromisoformat(history[index+1]["occurred_at"]) if index+1 < len(history) else now
                    elapsed = max(0, (until - datetime.fromisoformat(event["occurred_at"])).total_seconds())
                    if event["status"] == "WAITING_STUDENT": waits["student_wait"] += elapsed
                    if event["status"] == "SUBMITTED": waits["unit_wait"] += elapsed
        return {"schema_version": "case-dashboard.v1", "scope": "current_actor_queues", "sample_count": len(queue["items"]),
            "truncated": queue["truncated"], "groups": groups, "age_buckets": ages, "workflow_strata": complexity,
            "observed_event_counts": counts, "observed_state_seconds": waits, "active_work_seconds": None,
            "system_processing_seconds": None, "timing_meaning": "student_wait=WAITING_STUDENT; unit_wait=SUBMITTED; elapsed state time is not active labor or SLA",
            "blockers": {"officer_review_source_or_assignment": groups["blocked"]},
            "unobserved": ["active_labor", "system_processing", "institutional_deadline", "external_wait", "reopen_if_no_event"],
            "action_authority": "none"}
