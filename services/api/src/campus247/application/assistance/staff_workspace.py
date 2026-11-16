"""Bounded synchronous staff preparation; no worker, provider or business action.

Cache/review updates share the business lock. Every read rechecks source hashes,
role, session, queue, assignment and record version before using cached findings.
"""
from datetime import datetime, timezone
from time import monotonic
from campus247.application.assistance.staff_contracts import StaffDossier, StaffFinding, StaffRead
from campus247.application.assistance.workflow import WorkflowResolveRequest
from campus247.application.document_request.certificates import CertificateError
from campus247.application.knowledge.operations import digest
from campus247.ports.identity import IdentityRole


class StaffWorkspaceService:
    def __init__(self, resources, workflow, cache, *, tenant="huce-local-public"):
        self.resources, self.workflow, self.cache, self.tenant = resources, workflow, cache, tenant

    def current(self, tx, actor, target, *, assigned=False):
        service = self.resources[target.kind]
        service.authorize(actor, IdentityRole.SUPPORT_OFFICER)
        if actor.tenant_id != self.tenant:
            raise CertificateError(403, "TENANT_REQUIRED", "Cần đúng tenant")
        record = service._owned(tx, actor, target.id, staff=True)
        service._version(record, target.expected_version)
        if (record.get("queue", "HUCE_GENERAL") not in actor.unit_ids
                or record["assigned_user_id"] not in {None, actor.subject_id}
                or assigned and record["assigned_user_id"] != actor.subject_id):
            raise CertificateError(404, "RESOURCE_NOT_FOUND", "Cần đúng hàng đợi và người phụ trách hồ sơ")
        return record

    def prepare(self, actor, body: StaffRead, *, revalidate=None):
        with self.resources[body.resource.kind].repository.transaction() as tx:
            actor = revalidate(tx) if revalidate else actor
            record = self.current(tx, actor, body.resource)
            return self._prepare(tx, actor, body.resource, record)

    def _prepare(self, tx, actor, target, record):
        started = monotonic()
        if len(record.get("history", [])) > 200 or len(record.get("supplements", [])) > 50:
            raise CertificateError(413, "STAFF_PROVENANCE_LIMIT", "Cần mở lịch sử theo từng phần để đối chiếu")
        package = self.workflow.resolve(actor, WorkflowResolveRequest(resource=target), transaction=tx,tolerate_source_errors=True)
        if len(package.required_form_fields) + len(package.mandatory_reviews) > 24:
            raise CertificateError(413, "STAFF_CRITERIA_LIMIT", "Cần thu hẹp bộ tiêu chí")
        key = digest([self.tenant, target.kind, target.id, record["student_user_id"]])
        previous = self.cache.read(tx, key)
        payload, profile = record["payload"], record["profile"]
        latest_profile = self.resources[target.kind].profile_reader(record["student_user_id"])
        binding = digest({"resource": target.model_dump(), "student": record["student_user_id"],
            "tenant": self.tenant, "queue": record.get("queue", "HUCE_GENERAL"),
            "assignment": record["assigned_user_id"], "workflow": package.model_dump(mode="json"),
            "payload": payload, "profile": profile, "latest_profile": latest_profile, "history": record["history"],
            "snapshot": record.get("snapshot")})
        sources, values, facts = [], {}, []

        def source(identifier, value, locator, version, classification="synthetic", kind="record"):
            sources.append({"id": identifier, "kind": kind, "version": str(version), "locator": locator,
                            "sha256": digest(value), "classification": classification})
            values[identifier] = value
            return identifier

        for field, value in payload.items():
            if field == "attachments":
                continue
            sid = source("payload:" + field, value, f"{target.kind}/{target.id}@{record['version']}#/payload/{field}", record["version"])
            facts.append({"field": field, "value": value, "origin": "student_declaration", "source_id": sid})
        profile_id = source("profile", profile, f"{target.kind}/{target.id}@{record['version']}#/profile", record["version"])
        facts.append({"field": "profile", "value": profile, "origin": "synthetic_profile_snapshot", "source_id": profile_id})
        course = record.get("snapshot", {}).get("course")
        if course:
            course_id = source("snapshot:course", course, f"{target.kind}/{target.id}@{record['version']}#/snapshot/course", record["version"])
            facts.append({"field": "course", "value": course, "origin": "synthetic_course_snapshot_not_current_eligibility", "source_id": course_id})
        attachments = payload.get("attachments", [])
        if len(attachments) > 3:
            raise CertificateError(413, "STAFF_DOCUMENT_LIMIT", "Cần đối chiếu tài liệu theo từng phần")
        documents = []
        for index, attachment in enumerate(attachments):
            sid = source(f"attachment:{index}", attachment, f"{target.kind}/{target.id}@{record['version']}#/payload/attachments/{index}", record["version"])
            documents.append({"name": attachment["name"], "source_id": sid, "ocr_state": "unchecked",
                              "reason": "OCR_NOT_CONFIGURED"})
        workflow_sources = []
        if package.binding:
            for index, applied in enumerate([package.binding.source, *package.binding.supporting_sources]):
                sid = f"workflow:{index}"
                # Preserve the source's actual rendition hash, not a metadata hash.
                sources.append({"id": sid, "kind": "workflow", "version": applied.version_id,
                    "locator": applied.locator, "sha256": applied.rendition_sha256, "classification": applied.classification})
                values[sid] = applied.model_dump(mode="json")
                workflow_sources.append(sid)
        findings, reused, checked = [], [], []
        source_binding = package.model_dump(mode="json", exclude={"resource", "readiness", "supplements"})
        dependencies = {"workflow": source_binding, "criteria_version": "staff-criteria.v1",
                        "tenant": self.tenant, "kind": target.kind, "case": target.id, "student": record["student_user_id"]}
        old_findings = {f["id"]: f for f in previous["findings"]} if previous else {}
        reviews = previous.get("reviews", {}) if previous else {}

        def finding(identifier, label, layer, state, reason, data, refs):
            dependency = digest({**dependencies, "criterion": identifier, "data": data})
            old = old_findings.get(identifier)
            fresh = {"id": identifier, "label": label, "layer": layer, "state": state, "reason": reason,
                     "dependency_hash": dependency, "source_ids": refs}
            if old and old["dependency_hash"] == dependency:
                reused.append(identifier)
                if layer == "deterministic":
                    fresh = {**old, "source_ids": refs}
            else:
                checked.append(identifier)
            review = reviews.get(identifier)
            if layer == "officer_review" and review and review["dependency_hash"] == dependency:
                fresh.update(state=review["verdict"], reason="OFFICER_RECORDED_REVIEW", reviewed_by=review["actor"],
                             reviewed_at=review["at"], note=review["note"])
            findings.append(StaffFinding.model_validate(fresh).model_dump(mode="json"))

        for field in package.required_form_fields:
            if field not in payload:
                source("payload:" + field, None, f"{target.kind}/{target.id}@{record['version']}#/payload/{field}", record["version"])
            present = payload.get(field) not in (None, "", [])
            finding("field_" + field, "Trường khai báo: " + field, "deterministic", "checked" if present else "missing_source",
                "DECLARATION_PRESENT_NOT_VALIDATED" if present else "REQUIRED_DECLARATION_MISSING", payload.get(field), ["payload:" + field])
        finding("profile_snapshot", "Đối chiếu bản chụp thông tin sinh viên", "deterministic",
                "missing_source" if latest_profile is None else "checked" if profile == latest_profile else "conflicting",
                "PROFILE_UNAVAILABLE" if latest_profile is None else "PROFILE_SNAPSHOT_MATCH" if profile == latest_profile else "PROFILE_SNAPSHOT_DIFFERS",
                [profile, latest_profile], [profile_id])
        source_state = "checked" if package.binding_status == "bound" and not package.reasons else "missing_source"
        if any("UNAVAILABLE" in reason or "INVALID" in reason for reason in package.reasons):
            source_state = "error"
        if any("MISMATCH" in reason or "CHANGED" in reason for reason in package.reasons):
            source_state = "conflicting"
        finding("source_binding", "Nguồn/quy trình áp dụng", "deterministic", source_state,
            "SNAPSHOT_BOUND_NOT_INSTITUTIONAL_APPROVAL" if source_state == "checked" else ",".join(package.reasons), source_binding, workflow_sources)
        review_data = {"payload": payload, "profile": [profile, latest_profile], "queue": record.get("queue", "HUCE_GENERAL"),
                       "assignment": record["assigned_user_id"], "supplements": record.get("supplements", []), "course": course}
        for criterion in package.mandatory_reviews:
            data = {**review_data, "messages": record.get("messages"), "result": record.get("result"), "status": record["status"]} if criterion.id == "decision_reason" else review_data
            finding(criterion.id, criterion.label, "officer_review", "unchecked", "MANDATORY_OFFICER_REVIEW_REQUIRED", data,
                [*workflow_sources, profile_id, *(["snapshot:course"] if course else [])])
        reasons = [f["id"] + ":" + f["reason"] for f in findings if f["state"] != "checked"]
        if not record["assigned_user_id"]:
            reasons.append("CLAIM_REQUIRED")
        if any(s.binding_status != "bound" for s in package.supplements):
            reasons.append("SUPPLEMENT_SOURCE_UNRESOLVED")
        if record["status"] in {"READY", "REJECTED", "FULFILLED", "CANCELLED"}:
            readiness = "blocked"
            reasons.append("TERMINAL_RECORD_READ_ONLY")
        elif record["status"] == "WAITING_STUDENT":
            readiness = "waiting"
            reasons.append("WAITING_FOR_STUDENT")
        elif any(f["state"] in {"conflicting", "error"} for f in findings):
            readiness = "blocked"
        elif any(f["state"] == "missing_source" for f in findings):
            readiness = "missing"
        elif reasons:
            readiness = "needs_verification"
        else:
            readiness = "ready"
        before = previous.get("payload", {}) if previous else {}
        changed_fields = sorted(k for k in set(before) | set(payload) if before.get(k) != payload.get(k)) if previous else []
        delta = {"previous_version": previous["version"] if previous else None, "current_version": record["version"],
            "changes": [{"field": field, "before": before.get(field), "after": payload.get(field)} for field in changed_fields],
            "rechecked": checked, "reused": reused, "draft_invalidated": bool(previous and previous["binding_hash"] != binding)}
        if previous and previous["binding_hash"] == binding and previous.get("delta"):
            delta = {**previous["delta"], "rechecked": checked, "reused": reused}
        dossier = StaffDossier(resource=target, student_id=record["student_user_id"], tenant=self.tenant,
            queue=record.get("queue", "HUCE_GENERAL"), assigned_actor=record["assigned_user_id"],
            purpose=payload.get("purpose") or payload.get("reason"), facts=facts, timeline=record["history"], documents=documents,
            sources=sources, findings=findings, readiness=readiness, reasons=reasons, binding_hash=binding,
            workflow_version=package.definition_version, delta=delta,
            next_action="Đọc nguồn và hoàn thành từng kiểm tra bắt buộc; giữ nháp khi dữ liệu thiếu hoặc xung đột." if reasons else "Cán bộ xem lại nháp và xác nhận thao tác qua luồng nghiệp vụ hiện có.",
            capabilities={"ocr": "unavailable: đối chiếu tệp thủ công", "sla": "unverified: hỏi đơn vị tiếp nhận",
                          "ai_proposals": "unavailable: soạn thủ công", "institutional_rules": "unverified: cần xác minh chính thức"})
        if monotonic() - started > 2:
            raise CertificateError(503, "STAFF_PREPARATION_TIMEOUT", "Chưa hoàn tất đối chiếu; thử lại thủ công, nháp được giữ")
        if not previous or previous["binding_hash"] != binding or previous["findings"] != findings:
            self.cache.write(tx, {"id": key, "version": record["version"], "binding_hash": binding, "payload": payload,
                                  "findings": findings, "reviews": reviews, "delta": delta})
        return dossier

    def review(self, actor, body, *, revalidate=None):
        with self.resources[body.resource.kind].repository.transaction() as tx:
            actor = revalidate(tx) if revalidate else actor
            record = self.current(tx, actor, body.resource, assigned=True)
            dossier = self._prepare(tx, actor, body.resource, record)
            key = digest([self.tenant, body.resource.kind, body.resource.id, record["student_user_id"]])
            receipt_key = digest([self.tenant, actor.subject_id, body.client_id])
            fingerprint = digest(body.model_dump())
            receipt = self.cache.replay(tx, receipt_key)
            if receipt:
                if receipt["fingerprint"] != fingerprint:
                    raise CertificateError(409, "IDEMPOTENCY_CONFLICT", "Mã lưu kiểm tra đã dùng cho nội dung khác")
                return {**receipt, "is_replay": True}
            selected = next((f for f in dossier.findings if f.id == body.criterion_id and f.layer == "officer_review"), None)
            if (not selected or dossier.binding_hash != body.binding_hash or selected.dependency_hash != body.dependency_hash):
                raise CertificateError(409, "STALE_EVIDENCE", "Hồ sơ/nguồn đã đổi; cần đối chiếu lại")
            if not body.note.strip():
                raise CertificateError(422, "REVIEW_NOTE_REQUIRED", "Cần ghi căn cứ kiểm tra")
            value = self.cache.read(tx, key)
            value["reviews"][body.criterion_id] = {"dependency_hash": selected.dependency_hash, "verdict": body.verdict,
                "note": body.note.strip(), "actor": actor.subject_id, "at": datetime.now(timezone.utc).isoformat()}
            self.cache.write(tx, value)
            receipt = {"id": receipt_key, "fingerprint": fingerprint, "criterion_id": body.criterion_id,
                       "binding_hash": dossier.binding_hash, "saved": True, "action_authority": "none",
                       "review": value["reviews"][body.criterion_id]}
            self.cache.receipt(tx, receipt)
            return {**receipt, "is_replay": False}

    def open_source(self, actor, body, *, revalidate=None):
        with self.resources[body.resource.kind].repository.transaction() as tx:
            actor = revalidate(tx) if revalidate else actor
            record = self.current(tx, actor, body.resource)
            dossier = self._prepare(tx, actor, body.resource, record)
            if dossier.binding_hash != body.binding_hash:
                raise CertificateError(409, "STALE_EVIDENCE", "Nguồn hoặc hồ sơ đã đổi; mở lại bộ hồ sơ")
            ref = next((s for s in dossier.sources if s.id == body.source_id), None)
            if ref is None:
                raise CertificateError(404, "SOURCE_NOT_FOUND", "Nguồn không thuộc bộ hồ sơ này")
            if ref.kind == "workflow":
                package = self.workflow.resolve(actor, WorkflowResolveRequest(resource=body.resource), transaction=tx,tolerate_source_errors=True)
                applied = [package.binding.source, *package.binding.supporting_sources][int(ref.id.split(":")[1])]
                if body.resource.kind == "service_request":
                    version = self.resources[body.resource.kind].knowledge._version(tx, applied.version_id)
                    content = version["text"]
                else:
                    rows = self.resources[body.resource.kind].guidance_reader()["sources"]
                    row = next((r for r in rows if r["content_sha256"] == ref.sha256 and r["locator"] == ref.locator), None)
                    if row is None:
                        raise CertificateError(409, "STALE_EVIDENCE", "Bản nguồn đã thay đổi")
                    content = row["content_text"]
                if digest(content.encode()) != ref.sha256:
                    raise CertificateError(409, "SOURCE_HASH_MISMATCH", "Nội dung nguồn không khớp")
            elif ref.id == "profile":
                content = record["profile"]
            elif ref.id == "snapshot:course":
                content = record["snapshot"]["course"]
            elif ref.id.startswith("attachment:"):
                content = record["payload"]["attachments"][int(ref.id.split(":")[1])]
            else:
                content = record["payload"].get(ref.id.split(":", 1)[1])
            return {"source": ref.model_dump(), "content": content, "binding_hash": dossier.binding_hash, "action_authority": "none"}
