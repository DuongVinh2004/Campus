"""Authorized, read-only workflow/source/template binding for both role views.

Use the record's configured milestone and exact snapshot source. A newer active
source never silently replaces it. No checklist tick or model confidence can
complete mandatory officer reviews through this API.
"""
from dataclasses import asdict
from contextlib import nullcontext
from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from campus247.application.assistance.contracts import StrictDTO, ResourceRef, ResourceState
from campus247.application.document_request.certificates import CertificateError
from campus247.application.knowledge.operations import digest
from campus247.domain.service_workflow import record_workflow
from campus247.domain.certificate_workflow import certificate_workflow
from campus247.application.document_request.workflow_binding import checked_public_snapshot
from campus247.ports.identity import IdentityRole


class WorkflowResolveRequest(StrictDTO):
    schema_version: Literal["unified-workflow.v1"] = "unified-workflow.v1"
    resource: ResourceRef

class AppliedSource(StrictDTO):
    source_id: str = Field(min_length=1, max_length=100)
    version_id: str = Field(min_length=1, max_length=100)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    rendition_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    locator: str = Field(min_length=1, max_length=1000)
    effective_from: str | None = Field(default=None, max_length=64)
    effective_until: str | None = Field(default=None, max_length=64)
    classification: Literal["synthetic", "public_snapshot"] = "synthetic"
    effective_status: Literal["demo_interval", "unknown"] = "demo_interval"

    @model_validator(mode="after")
    def authority(self):
        if self.classification == "public_snapshot":
            if self.effective_status != "unknown" or self.effective_from is not None or self.effective_until is not None:
                raise ValueError("public snapshot does not establish institutional dates")
        elif self.effective_status != "demo_interval" or self.effective_from is None:
            raise ValueError("synthetic source requires its configured interval")
        return self


class WorkflowBinding(StrictDTO):
    workflow_version: str = Field(min_length=1, max_length=100)
    template_version: str = Field(min_length=1, max_length=100)
    milestone: Literal["submitted_at_or_created_at"]
    as_of: str = Field(max_length=64)
    source: AppliedSource
    supporting_sources: list[AppliedSource] = Field(default_factory=list, max_length=5)
    source_capture_at: str | None = Field(default=None, max_length=64)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class SupplementApplicability(StrictDTO):
    sequence: int = Field(ge=1)
    at: str | None = Field(default=None, max_length=64)
    binding_status: Literal["bound", "unresolved"]
    source: AppliedSource | None
    source_changed_from_submission: bool | None
    reasons: list[str] = Field(max_length=10)


class MandatoryReview(StrictDTO):
    id: str = Field(pattern=r"^[a-z_]{1,100}$")
    label: str = Field(min_length=1, max_length=300)
    reviewer: Literal["SUPPORT_OFFICER"]
    required: Literal[True]
    status: Literal["required"]


class TemplateDefinition(StrictDTO):
    version: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    required_fields: list[str] = Field(min_length=1, max_length=10)
    outcomes: list[str] = Field(min_length=1, max_length=10)


class WorkflowResolveResponse(StrictDTO):
    schema_version: Literal["unified-workflow.v1"] = "unified-workflow.v1"
    resource: ResourceState
    definition_version: str = Field(min_length=1, max_length=100)
    classification: Literal["synthetic"]
    binding_status: Literal["bound", "unresolved"]
    binding: WorkflowBinding | None
    current_source_differs: bool
    reasons: list[str] = Field(max_length=10)
    required_form_fields: list[str] = Field(min_length=1, max_length=10)
    mandatory_reviews: list[MandatoryReview] = Field(min_length=1, max_length=10)
    template: TemplateDefinition | None
    readiness: Literal["requires_officer_review", "undetermined"]
    action_authority: Literal["none"] = "none"
    limitations: list[str] = Field(max_length=6)
    supplements: list[SupplementApplicability] = Field(default_factory=list, max_length=50)
    institutional_rules_verified: Literal[False] = False

    @model_validator(mode="after")
    def bound_template(self):
        bound = self.binding_status == "bound"
        if bound != (self.binding is not None and self.template is not None):
            raise ValueError("source/template binding required")
        expected_readiness = "undetermined" if any(s.binding_status == "unresolved" for s in self.supplements) else "requires_officer_review"
        if bound and (self.reasons or self.binding.workflow_version != self.definition_version
                      or self.binding.template_version != self.template.version
                      or self.readiness != expected_readiness):
            raise ValueError("binding versions or readiness inconsistent")
        if not bound and (self.binding is not None or self.template is not None or self.readiness != "undetermined"):
            raise ValueError("unresolved source cannot produce readiness or a template")
        return self


def bound_workflow(definition, anchor, source, *, supporting_sources=None, captured_at=None):
    value = WorkflowBinding(workflow_version=definition.version, template_version=definition.template.version,
        milestone=definition.applicability_milestone, as_of=anchor, source=AppliedSource.model_validate(source),
        supporting_sources=[AppliedSource.model_validate(s) for s in supporting_sources or []],
        source_capture_at=captured_at, sha256="0" * 64).model_dump(mode="json", exclude={"sha256"})
    return {**value, "sha256": digest(value)}


class WorkflowPackageService:
    def __init__(self, services, certificates=None):
        self.services, self.certificates = services, certificates

    def _public_sources(self, snapshot, *, tolerate_source_errors=False):
        if not snapshot:
            return [], ["SOURCE_SNAPSHOT_MISSING"]
        if not self.certificates or self.certificates.guidance_reader is None:
            return [], ["PUBLIC_SOURCE_UNAVAILABLE"]
        try:
            return checked_public_snapshot(snapshot, self.certificates.guidance_reader()), []
        except (ValueError, TypeError, KeyError) as exc:
            known = {"SOURCE_SNAPSHOT_MISSING", "SOURCE_SNAPSHOT_MISMATCH", "PUBLIC_SOURCE_CHANGED_OR_UNAVAILABLE", "SOURCE_CAPTURE_TIME_INVALID"}
            return [], [str(exc) if str(exc) in known else "PUBLIC_SOURCE_INVALID"]
        except CertificateError as exc:
            if not tolerate_source_errors:
                raise
            return [], [exc.code]
        except OSError:
            if not tolerate_source_errors:
                raise
            return [], ["PUBLIC_SOURCE_UNAVAILABLE"]

    def _service_source(self, tx, snapshot, definition, at):
        reasons = []
        if not snapshot or not snapshot.get("version_id"):
            return None, ["SOURCE_SNAPSHOT_MISSING"]
        source = self.services.knowledge._version(tx, snapshot["version_id"])
        review = source["reviews"][-1] if source["reviews"] else None
        build = dict(source["build"]) if source["build"] else {}
        checksum = build.pop("checksum", None)
        if (source["procedure"] != definition.kind or source["campus"] != "HUCE_DEMO"
                or source["audience"] != "STUDENT" or not source["is_simulation"]):
            reasons.append("SOURCE_SCOPE_MISMATCH")
        if any(snapshot.get(key) != source.get(key) for key in ("source_id", "source_sha256", "rendition_sha256")):
            reasons.append("SOURCE_SNAPSHOT_MISMATCH")
        if (source["state"] not in {"PUBLISHED", "SUPERSEDED"} or not source["published_at"]
                or datetime.fromisoformat(source["published_at"]) > at
                or datetime.fromisoformat(source["effective_from"]) > at
                or source["effective_until"] and at >= datetime.fromisoformat(source["effective_until"])):
            reasons.append("SOURCE_NOT_APPLICABLE_AT_MILESTONE")
        if (not review or review["verdict"] != "approved" or review["reviewer"] == source["created_by"]
                or any(review.get(key) != source[key] for key in ("source_sha256", "rendition_sha256"))):
            reasons.append("SOURCE_REVIEW_UNVERIFIED")
        if (not build or checksum != digest(build) or build.get("error") or build.get("compatibility") != "demo-lexical-v1"
                or build.get("version_id") != source["id"]
                or any(build.get(key) != source[key] for key in ("source_sha256", "rendition_sha256"))):
            reasons.append("SOURCE_BUILD_UNVERIFIED")
        if reasons:
            return None, reasons
        original = self.services.knowledge._source(tx, source["source_id"])
        result = {key: snapshot[key] for key in ("version_id", "source_id", "source_sha256", "rendition_sha256")}
        result.update(locator=original["locator"], effective_from=source["effective_from"], effective_until=source["effective_until"],
                      classification="synthetic", effective_status="demo_interval")
        return result, []

    def _supplements(self, tx, record, definition, submitted_source, certificate, *, tolerate_source_errors=False):
        entries = record.get("supplements", [])
        if len(entries) > 50:
            raise CertificateError(413, "PROVENANCE_LIMIT", "Cần đối chiếu lịch sử bổ sung theo từng phần")
        result = []
        for index, entry in enumerate(entries, 1):
            source, reasons, at = None, [], entry.get("at")
            if not at or not entry.get("source_snapshot") or not entry.get("committed_version"):
                reasons.append("SUPPLEMENT_SOURCE_UNRECORDED")
            else:
                try:
                    timestamp = datetime.fromisoformat(at)
                    event = next(e for e in record["history"] if e["action"] == "request.supplement" and e["version"] == entry["committed_version"])
                    previous = next(e for e in record["history"] if e["version"] == entry["committed_version"] - 1)
                    if (timestamp.utcoffset() is None or timestamp < datetime.fromisoformat(record["submitted_at"])
                            or timestamp < datetime.fromisoformat(previous["occurred_at"])
                            or timestamp > datetime.fromisoformat(event["occurred_at"]) or event["actor_role"] != "STUDENT"
                            or event["actor_id"] != record["student_user_id"]):
                        reasons.append("SUPPLEMENT_PROVENANCE_INCONSISTENT")
                    if certificate:
                        sources, source_reasons = self._public_sources(entry["source_snapshot"],tolerate_source_errors=tolerate_source_errors)
                        source = sources[-1] if sources else None
                        captured = datetime.fromisoformat(entry["source_snapshot"]["captured_at"])
                        if captured > timestamp or captured < datetime.fromisoformat(previous["occurred_at"]):
                            reasons.append("SUPPLEMENT_PROVENANCE_INCONSISTENT")
                    else:
                        source, source_reasons = self._service_source(tx, entry["source_snapshot"], definition, timestamp)
                    reasons.extend(source_reasons)
                    if entry.get("workflow_version") != definition.version or entry.get("template_version") != definition.template.version:
                        reasons.append("SUPPLEMENT_WORKFLOW_VERSION_MISMATCH")
                except (ValueError, TypeError, KeyError, StopIteration):
                    reasons.append("SUPPLEMENT_PROVENANCE_INCONSISTENT")
                except CertificateError as exc:
                    if not tolerate_source_errors:
                        raise
                    reasons.append(exc.code)
            changed = None if reasons or not source or not submitted_source else any(source[k] != submitted_source[k]
                for k in ("source_id", "version_id", "source_sha256", "rendition_sha256"))
            result.append({"sequence": index, "at": at, "binding_status": "unresolved" if reasons else "bound",
                           "source": source if not reasons else None, "source_changed_from_submission": changed,
                           "reasons": sorted(set(reasons))})
        return result

    def resolve(self, actor, request: WorkflowResolveRequest, *, transaction=None, tolerate_source_errors=False):
        staff = actor.has_role(IdentityRole.SUPPORT_OFFICER)
        certificate = request.resource.kind == "certificate_request"
        service = self.certificates if certificate else self.services
        if service is None:
            raise CertificateError(503, "WORKFLOW_NOT_CONFIGURED", "Nguồn/quy trình chưa được cấu hình")
        with nullcontext(transaction) if transaction is not None else service.repository.transaction() as tx:
            record = service._owned(tx, actor, request.resource.id, staff=staff)
            service._version(record, request.resource.expected_version)
            anchor = record.get("submitted_at") or record.get("created_at")
            try:
                definition = certificate_workflow(record) if certificate else record_workflow(record)
            except (ValueError, TypeError, KeyError):
                raise CertificateError(409, "WORKFLOW_VERSION_UNRESOLVED", "Chưa xác định quy trình áp dụng theo mốc hồ sơ") from None
            if certificate:
                snapshot = record.get("guidance_snapshot")
                sources, reasons = self._public_sources(snapshot,tolerate_source_errors=tolerate_source_errors)
                source_binding = sources[-1] if sources else None
                current_differs = "PUBLIC_SOURCE_CHANGED_OR_UNAVAILABLE" in reasons
                binding = bound_workflow(definition, anchor, source_binding, supporting_sources=sources[:-1],
                    captured_at=snapshot["captured_at"]) if source_binding else None
            else:
                snapshot = record.get("snapshot", {}).get("guidance", {})
                try:
                    source_binding, reasons = self._service_source(tx, snapshot, definition, datetime.fromisoformat(anchor))
                except CertificateError as exc:
                    if not tolerate_source_errors:
                        raise
                    source_binding, reasons = None, [exc.code]
                active = tx.item("knowledge_active", definition.kind)
                current_differs = not active or active["version_id"] != snapshot.get("version_id")
                binding = bound_workflow(definition, anchor, source_binding) if source_binding else None
            supplements = self._supplements(tx, record, definition, source_binding, certificate,tolerate_source_errors=tolerate_source_errors)
            return WorkflowResolveResponse.model_validate({"schema_version": "unified-workflow.v1", "resource": {
                        "id": record["id"], "kind": request.resource.kind, "version": record["version"],
                        "workflow": record["document_type"], "status": record["status"], "view": "staff" if staff else "student"},
                    "definition_version": definition.version, "classification": definition.classification,
                    "binding_status": "bound" if binding else "unresolved", "binding": binding,
                    "current_source_differs": current_differs, "reasons": reasons,
                    "required_form_fields": list(definition.required_form_fields),
                    "mandatory_reviews": [{**asdict(check), "status": "required"} for check in definition.mandatory_reviews],
                    "template": {"version": definition.template.version, "title": definition.template.title,
                                 "required_fields": list(definition.template.required_fields),
                                 "outcomes": list(definition.template.outcomes)} if binding else None,
                    "readiness": "requires_officer_review" if binding and all(s["binding_status"] == "bound" for s in supplements) else "undetermined",
                    "supplements": supplements, "action_authority": "none",
                    "limitations": ["Quy trình và mẫu local/synthetic; chưa xác minh mẫu/quy định chính thức HUCE.",
                                    "Binding không chứng minh đã hoàn thành kiểm tra bắt buộc hoặc cho phép thực hiện.",
                                    "Nguồn hiện tại khác snapshot cần đối chiếu; không tự chuyển sang phiên bản mới.",
                                    "Bản chụp công khai không xác minh hiệu lực, điều kiện cấp, mẫu hoặc phí hiện hành của trường."]})
