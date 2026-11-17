"""Minimal role projections resolved from existing authorized services.

Browser supplies an ID/version, never profile, tenant, role, notes, grants or
confirmation. No LLM, preview, draft save, confirmation or staff action occurs.
"""
from campus247.application.assistance.contracts import (
    AssistanceRequest, AssistanceResponse, EvidenceRef, ResourceState,
)
from campus247.application.document_request.certificates import CertificateError
from campus247.ports.identity import IdentityRole


class AssistanceContextService:
    def __init__(self, certificates, services, certificate_guidance):
        self.certificates = certificates
        self.services = services
        self.certificate_guidance = certificate_guidance

    def resolve(self, actor, request: AssistanceRequest):
        staff = actor.has_role(IdentityRole.SUPPORT_OFFICER)
        service = self.services if request.surface == "service" else self.certificates
        # Existing service reauthorizes tenant/session/role/queue/ownership and
        # conceals unauthorized IDs before any state or source is projected.
        record = service.read(actor, request.resource.id, staff=staff)
        if record["version"] != request.resource.expected_version:
            raise CertificateError(409, "STALE_VERSION", "Hồ sơ đã thay đổi; tải lại để trợ giúp đúng phiên bản.")
        evidence, status = [], "observed"
        limitations = ["Dữ liệu local/synthetic; chưa phải nghiệm thu người dùng.",
                       "Trợ giúp này chỉ đọc; quyết định và thao tác dùng luồng xác nhận hiện có."]
        if request.surface == "service":
            # These sources are explicitly demo guidance for the already
            # authorized case. Current/checksum is re-read; no staff notes pass.
            try:
                with self.services.repository.transaction() as tx:
                    source = self.services.knowledge.current(tx, record["document_type"])
                evidence = [EvidenceRef(source_id=source["source_id"], version_id=source["version_id"],
                    locator=source["locator"], sha256=source["rendition_sha256"], classification="synthetic")]
                guidance = source["text"]
                prior = record.get("snapshot", {}).get("guidance", {})
                if any(prior.get(key) != source.get(key) for key in ("version_id", "source_sha256", "rendition_sha256", "generation")):
                    status = "source_changed"
                    limitations.append("Nguồn hiện tại khác snapshot hồ sơ; cần đối chiếu phiên bản áp dụng, chưa kết luận readiness.")
            except CertificateError as exc:
                # Only a known source gap becomes a partial context. DB/access
                # failures remain failures; never claim a successful fallback.
                if exc.code not in {"MISSING_SOURCE", "SOURCE_NOT_CURRENT"}:
                    raise
                status, guidance = "missing_source", "Chưa đủ nguồn hiện hành để hướng dẫn hồ sơ."
                limitations.append(exc.code)
        else:
            source = self.certificate_guidance()
            guidance = source["summary"]
            limitations.append(source["demo_configuration"])
            evidence = [EvidenceRef(source_id=row["id"], version_id=row["version"], locator=row["locator"],
                sha256=row["content_sha256"], classification="public_snapshot") for row in source["sources"]]
        if request.field:
            limitations.append("Trường đang xem: " + request.field + "; chưa đọc hoặc thay đổi nội dung chưa lưu của bạn.")
        return AssistanceResponse(status=status, resource=ResourceState(kind=request.resource.kind,
            id=record["id"], version=record["version"], status=record["status"], workflow=record["document_type"],
            view="staff" if staff else "student"), evidence=evidence, guidance=guidance,
            limitations=limitations, open_path=f"/{'services' if request.surface == 'service' else 'tickets'}?request={record['id']}")
