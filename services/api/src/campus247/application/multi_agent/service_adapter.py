"""Only the existing certificate draft/preview service is exposed to agents.

No confirm/submit/staff methods are part of this adapter. Confirmation remains
an explicit human operation through the established transactional API.
"""
from typing import Literal

from pydantic import Field, StrictStr

from campus247.application.document_request.assistant import propose_certificate
from campus247.application.single_agent.contracts import StrictRecord
from campus247.domain.document_request.certificate import CertificateForm
from campus247.ports.identity import IdentityRole


def prepare_certificate_response(state):
    from dataclasses import replace
    from campus247.agent.state import DraftResponse, Terminal, Route
    if state.route != Route.DOCUMENT_REQUEST:
        return replace(state, terminal=Terminal.ABSTAINED,
            draft=DraftResponse(text="Công cụ cho yêu cầu này chưa có consumer được xác nhận trong trợ lý. Mở chức năng tương ứng để đọc dữ liệu hoặc xem trước và xác nhận thao tác; công việc hiện tại chưa tạo kết quả nghiệp vụ."),
            errors=(*state.errors, "AI_SERVICE_CAPABILITY_UNAVAILABLE"))
    from campus247.application.document_request.assistant import understand_student_goal
    intent = understand_student_goal(state.request.query[:2000])
    return replace(state, terminal=Terminal.ABSTAINED,
        draft=DraftResponse(text=(intent.clarification or "Chọn hồ sơ cần chuẩn bị.") + " Mở Chuẩn bị thủ tục sinh viên để dùng các trường đã lưu theo quyền; khi đủ thông tin, xem đề xuất nháp rồi xác nhận riêng bước gửi."),
        errors=(*state.errors, "AI_CLARIFICATION_REQUIRED", "AI_SERVICE_DRAFT_REQUIRED"))


def prepare_unavailable_handover(state):
    from dataclasses import replace
    from campus247.agent.state import DraftResponse, Terminal
    from campus247.agent.nodes.intent import is_other_person_data_request
    if is_other_person_data_request(state.request.query):
        return replace(state, terminal=Terminal.ABSTAINED,
            draft=DraftResponse(text="Tôi không thể cung cấp thông tin cá nhân của người khác. Bạn có thể hỏi về quy định hoặc thủ tục công khai của trường."),
            errors=(*state.errors, "AI_PERSONAL_DATA_DENIED"))
    return replace(state, terminal=Terminal.ABSTAINED,
        draft=DraftResponse(text="Hiện chưa có kênh gửi yêu cầu trong Campus 24/7. Bạn vui lòng liên hệ đơn vị phụ trách qua kênh chính thức được công bố trên website của trường."),
        errors=(*state.errors, "AI_HANDOVER_CAPABILITY_UNAVAILABLE"))


class ActionProposal(StrictRecord):
    operation: Literal["prepare_student_certificate"]
    missing_fields: list[Literal["purpose", "recipient"]] = Field(max_length=2)
    preview_reference: StrictStr | None = None
    requires_explicit_confirmation: Literal[True] = True


class CertificateDraftAdapter:
    def __init__(self, service, guidance):
        self.service, self.guidance = service, guidance

    def propose(self, actor, message):
        self.service.authorize(actor, IdentityRole.STUDENT)
        value = propose_certificate(message, self.guidance)
        if value["intent"] is None:
            return None
        return ActionProposal(operation="prepare_student_certificate", missing_fields=value["missing_fields"])

    def preview_for_user(self, actor, document_id, expected_version):
        # The established HTTP/form path retains the exact version check and
        # all transactional service rules, including a stale-preview rejection.
        self.service.authorize(actor, IdentityRole.STUDENT)
        return self.service.preview(actor, document_id, expected_version)

    def prepare_service_draft(self, actor, form: CertificateForm, *, document_id, expected_version):
        self.service.authorize(actor, IdentityRole.STUDENT)
        if not isinstance(form, CertificateForm):
            raise ValueError("validated certificate form required")
        # Stable draft identity is allocated by the existing user-facing service,
        # never by an agent retry. A retry only resumes this exact preview.
        record = self.service.read(actor, document_id)
        if record["payload"] != form.model_dump(mode="json"):
            raise ValueError("draft payload changed; save through the existing form service")
        if record["status"] == "PENDING_CONFIRMATION":
            if expected_version not in {record["version"], record["version"]-1}:
                raise ValueError("draft version changed")
            return self.service.resume(actor, document_id)
        if record["version"] != expected_version:
            raise ValueError("draft version changed")
        preview = self.service.preview(actor, record["id"], expected_version)
        # Return the established preview to the authorized user. The token is
        # never retained in the orchestration checkpoint or passed to a model.
        return preview


class ResourceRunMetadata(StrictRecord):
    id: StrictStr
    version: int = Field(ge=1)
    state: Literal["partial", "interrupted"]
    receipt_id: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")
    is_replay: bool


class ResourceSpecialistResult(StrictRecord):
    schema_version: Literal["resource-specialist.v1"] = "resource-specialist.v1"
    status: Literal["observed", "partial", "abstained"]
    context: "AssistanceResponse"
    workflow: "WorkflowResolveResponse | None" = None
    blockers: list[StrictStr] = Field(default_factory=list, max_length=16)
    next_action: Literal["review_resource", "read_sources"]
    action_authority: Literal["none"] = "none"
    run: ResourceRunMetadata | None = None


from campus247.application.assistance.contracts import AssistanceRequest, AssistanceResponse
from campus247.application.assistance.workflow import WorkflowResolveRequest, WorkflowResolveResponse

ResourceSpecialistResult.model_rebuild()


class ResourceSpecialistAdapter:
    """Short deterministic document/verifier path for student and staff surfaces."""
    def __init__(self, context, workflow=None):
        self.context, self.workflow = context, workflow

    def resolve(self, actor, candidate):
        from campus247.agent.tools.executor import ScopedSpecialistExecutor
        from campus247.agent.tools.registry import ToolRegistry, ToolDefinition
        from campus247.application.document_request.certificates import CertificateError
        registry = ToolRegistry({"read_document": ToolDefinition("read_document", "read_document",
            "Read minimal current authorized document/source projection", False, False)})
        observations, packages = [], []
        def authorize(tool, request):
            if tool != "read_document" or self.context is None:
                raise CertificateError(503, "DOCUMENT_CONSUMER_UNAVAILABLE", "Chưa có consumer tài liệu")
            # The existing context service checks actor, tenant, role, queue,
            # assignment, ownership and resource version on every execution.
            observations.append(self.context.resolve(actor, request))
            packages.append(self.workflow.resolve(actor, WorkflowResolveRequest(resource=request.resource)) if self.workflow else None)
            if len(observations) > 1 and observations[-1] != observations[0]:
                raise CertificateError(409, "DOCUMENT_CHANGED", "Nguồn hoặc hồ sơ đã thay đổi")
            if len(packages) > 1 and packages[-1] != packages[0]:
                raise CertificateError(409, "WORKFLOW_EVIDENCE_CHANGED", "Quy tắc hoặc mẫu áp dụng đã thay đổi")
        def read(request):
            projection = observations[0]
            package = packages[0]
            blockers = []
            if projection.status != "observed":
                blockers.append("SOURCE_CHANGED_OR_MISSING")
            if package is None:
                blockers.append("WORKFLOW_CONSUMER_UNAVAILABLE")
            elif package.binding_status != "bound" or package.readiness == "undetermined":
                blockers.extend(package.reasons or ["WORKFLOW_EVIDENCE_UNRESOLVED"])
            # Preserve conflicting versions independently; no majority vote or
            # invented merge between current guidance and milestone binding.
            return ResourceSpecialistResult(status="partial" if blockers else "observed", context=projection,
                workflow=package, blockers=blockers, next_action="read_sources" if blockers else "review_resource")
        return ScopedSpecialistExecutor(registry, authorize=authorize).execute(
            "read_document", candidate, AssistanceRequest, ResourceSpecialistResult, read)
