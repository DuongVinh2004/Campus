"""Strict actor-owned HTTP boundary for settings, import, context and grants."""
from datetime import datetime, timezone, timedelta
import hashlib
import json
from typing import Literal

from fastapi import APIRouter, Query, Request
from pydantic import Field, field_validator, model_validator
from starlette.responses import JSONResponse

from campus247.application.assistance.contracts import StrictDTO, ResourceRef, AssistanceRequest
from campus247.application.assistance.durable_services import ConfirmedPreview
from campus247.application.assistance.feature_contracts import AssistantPreferences, GrantSpec
from campus247.application.assistance.scoped_context import ContextRequest
from campus247.application.assistance.unified_contracts import UUID, DraftProposal
from campus247.application.document_request.certificates import CertificateError
from campus247.domain.action.preview import ActionPreviewValue
from campus247.presentation.identity import get_current_identity


class SettingsBody(StrictDTO):
    preferences: AssistantPreferences
    expected_version: int = Field(ge=0)
    client_id: UUID


class ChatSettingsBody(SettingsBody):
    enabled: bool = True


class ImportBody(StrictDTO):
    source_json: str = Field(min_length=1, max_length=48000)
    client_id: UUID


class ConsentBody(StrictDTO):
    purpose: Literal["OPTIONAL_PERSONALIZATION", "QUALITY_FEEDBACK", "CONVERSATION_HISTORY"]
    decision: Literal["GRANTED", "WITHDRAWN"]
    notice_version: str = Field(min_length=1, max_length=100)
    expected_version: int = Field(ge=0)
    client_id: UUID


class RevokeBody(StrictDTO):
    expected_version: int = Field(ge=1)
    client_id: UUID


class ConfirmBody(StrictDTO):
    normalized_payload: str = Field(min_length=1, max_length=100000)
    confirmation_token: str = Field(min_length=1, max_length=4000)
    confirmed: Literal[True]

    @field_validator("confirmed", mode="before")
    @classmethod
    def exact_confirmation(cls, value):
        if value is not True:
            raise ValueError("explicit true required")
        return value


class CachedContextBody(StrictDTO):
    request: ContextRequest
    expected_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ResourceReadBody(StrictDTO):
    grant_id: UUID
    resource: ResourceRef
    operation_id: UUID


class PrepareCandidateBody(StrictDTO):
    grant_id: UUID
    proposal: DraftProposal
    operation_id: UUID


class MetadataBody(StrictDTO):
    title: str = Field(min_length=1, max_length=120)
    pinned: bool = False
    archived: bool = False
    expected_version: int = Field(ge=0)
    client_id: UUID

    @field_validator("title")
    @classmethod
    def plain_title(cls, value):
        if value != value.strip() or any(ord(char) < 32 for char in value):
            raise ValueError("plain bounded title required")
        return value


from campus247.application.document_request.student_preparation import StudentGoal, SavePreparedDraft


class SurfaceBody(StrictDTO):
    surface: Literal["chat", "student_home", "staff_queue", "settings", "certificate", "service"]
    resource: ResourceRef | None = None
    operation_id: UUID | None = None
    field: Literal["reason", "course_record_id", "contact_preference", "purpose", "recipient", "quantity", "delivery_method"] | None = None
    # No browser labels, private notes, DOM, unsaved fields or role claims.

    @model_validator(mode="after")
    def exact_resource(self):
        if self.resource is not None:
            AssistanceRequest(surface=self.surface, resource=self.resource, field=self.field)
        elif self.field is not None or self.operation_id is not None or self.surface in {"certificate", "service"}:
            raise ValueError("saved resource required for form/field")
        return self


FIELD_GUIDANCE = {
    "reason": "Nêu mục đích và lý do yêu cầu; đối chiếu thông tin trước khi xác nhận.",
    "course_record_id": "Chọn học phần từ danh sách được cấp cho tài khoản; không suy đoán mã học phần.",
    "contact_preference": "Chọn cách nhận thông báo trong các lựa chọn biểu mẫu.",
    "purpose": "Nêu giấy xác nhận dùng để làm gì. Không tự khai thông tin chưa xác minh.",
    "recipient": "Điền đơn vị nhận theo yêu cầu của bạn và kiểm tra trước khi gửi.",
    "quantity": "Chọn số lượng trong giới hạn biểu mẫu; kiểm tra chi phí nếu có.",
    "delivery_method": "Chọn hình thức nhận đang được cung cấp; không suy đoán thời gian hoàn tất.",
}


def create_assistant_state_router(*, preferences, imports, grants=None, context=None, consumers=None, catalog=None, resource_context=None, coordination_store=None, student_preparation=None):
    router = APIRouter(tags=["Assistant actor state"])

    def response(value):
        if isinstance(value, ConfirmedPreview):
            return JSONResponse({"normalized_payload": value.preview.normalized_payload,
                "confirmation_token": value.confirmation_token, "expires_at": value.preview.expires_at.isoformat(),
                "effect": "actor_state_only"}, headers={"Cache-Control": "no-store"})
        return JSONResponse(value, headers={"Cache-Control": "no-store"})

    @router.post("/v1/assistant/student:prepare")
    def prepare_student(body: StudentGoal, request: Request):
        if student_preparation is None:
            raise CertificateError(503, "STUDENT_DRAFT_UNAVAILABLE", "Dịch vụ này chưa có consumer chuẩn bị nháp")
        return response(student_preparation.prepare(get_current_identity(request), body))

    @router.get("/v1/assistant/student-actions")
    def student_actions(request: Request):
        if student_preparation is None:
            raise CertificateError(503, "STUDENT_DRAFT_UNAVAILABLE", "Chưa có inventory student consumer ở composition này")
        return response(student_preparation.action_inventory(get_current_identity(request)))

    @router.post("/v1/assistant/student:save-draft")
    def save_student(body: SavePreparedDraft, request: Request):
        if student_preparation is None:
            raise CertificateError(503, "STUDENT_DRAFT_UNAVAILABLE", "Dịch vụ này chưa có consumer lưu nháp")
        return response(student_preparation.save(get_current_identity(request), body))

    async def confirmation(service, body, request):
        actor = get_current_identity(request)
        scope = service.scope(actor)
        try:
            payload = json.loads(body.normalized_payload)
            if not isinstance(payload, dict) or payload["namespace"] not in service.namespaces:
                raise ValueError("namespace mismatch")
            namespace = payload["namespace"]
            # Only payload/hash are reconstructed. Signed token validates every
            # binding and original expiry; fresh dates cannot extend its TTL.
            now = datetime.now(timezone.utc)
            preview = ActionPreviewValue(id=payload["client_id"], actor_user_id=scope.owner,
                session_id=actor.session_id, conversation_id=scope.tenant, action_type="assistant.state."+namespace,
                tool_version="state-service.v1", policy_version="internal-state-only.v1",
                normalized_payload=body.normalized_payload,
                payload_hash="sha256:"+hashlib.sha256(body.normalized_payload.encode()).hexdigest(),
                policy_decision="allow", confirmation_secret_hash="unused", created_at=now, expires_at=now+timedelta(seconds=1))
        except (ValueError, TypeError, KeyError):
            raise CertificateError(422, "PREVIEW_INVALID", "Preview không hợp lệ") from None
        if namespace == "chat_preferences":
            if context is None:
                raise CertificateError(503, "CHAT_NOT_CONFIGURED", "Chưa cấu hình chat context")
            await context.conversation(actor, payload["key"])
        if namespace == "conversation_metadata":
            await service.owned(actor, payload["key"])
        receipt = service.confirm(actor, ConfirmedPreview(preview, body.confirmation_token), confirmed=body.confirmed)
        return response({"receipt": receipt.model_dump(mode="json"), "saved": True})

    @router.get("/v1/assistant/preferences")
    def read_settings(request: Request):
        return response(preferences.read(get_current_identity(request)))

    @router.get("/v1/assistant/consumer-capabilities")
    def consumer_capabilities(request: Request):
        actor = get_current_identity(request)
        preferences.scope(actor)
        audience = preferences.audience(actor)
        repository = context.conversations._repo if context and context.conversations else None
        native = getattr(repository, "supports_stable_turns", False) is True
        coordination = getattr(request.app.state, "coordination_capabilities", None)
        return response({"audience": audience, "tenant_id": actor.tenant_id, "history": audience == "student" and repository is not None,
            "history_metadata": audience == "student" and catalog is not None,
            "stable_create": native and audience == "student", "stable_turns": native and audience == "student",
            "temporary_chat": native and audience == "student",
            "student_model_chat": audience == "student", "staff_model_chat": False,
            "model_preferences": native, "resource_context": resource_context is not None,
            "account_preferences": True, "chat_preferences": audience == "student" and repository is not None,
            "grants": grants is not None, "memory": False, "tools": False, "templates": False,
            "quality_training": False, "context_transport": "refs_only_server_projection",
            "coordination": coordination or {"profile": None, "read": False, "resume": False,
                "transition_receipts": False, "writer": "EXISTING_PROXY_WRITER_UNCHANGED"},
            "resource_runs": coordination_store is not None,
            "student_preparation": student_preparation is not None and audience == "student",
            "student_draft_writer": "business_services" if student_preparation is not None else None,
            "student_ocr": False,
            "staff_workspace": audience == "staff" and getattr(request.app.state, "staff_workspace", None) is not None,
            "staff_ocr": False,
            "staff_sla": "unverified",
            "locked_reasons": {"staff_model_chat": "STAFF_CHAT_CONSUMER_NOT_CONFIGURED", "memory": "MEMORY_CONSUMER_NOT_CONFIGURED",
                "tools": "BUSINESS_CONFIRMATION_REQUIRED", "templates": "TEMPLATE_CONSUMER_NOT_CONFIGURED",
                **({"model_preferences": "EXISTING_PROXY_WRITER_UNCHANGED"} if not native else {})}})

    @router.get("/v1/assistant/consent-state")
    def consent_state(request: Request):
        actor = get_current_identity(request)
        scope = preferences.scope(actor)
        result = []
        for purpose in ("OPTIONAL_PERSONALIZATION", "CONVERSATION_HISTORY", "QUALITY_FEEDBACK"):
            record = preferences.store.get(scope, "consent", purpose)
            result.append({"purpose": purpose, "version": record.version if record else 0,
                "decision": record.payload["decision"] if record else "WITHDRAWN",
                "notice_version": record.payload["notice_version"] if record else None,
                "current_notice_consented": preferences.consented(actor, purpose),
                "consumer": "declaration_only_no_training" if purpose == "QUALITY_FEEDBACK" else "main_factory_only"})
        return response({"items": result})

    @router.post("/v1/assistant/preferences:preview")
    def preview_settings(body: SettingsBody, request: Request):
        return response(preferences.prepare(get_current_identity(request), body.preferences,
                                            body.expected_version, body.client_id))

    @router.post("/v1/assistant/preferences:confirm")
    async def confirm_settings(body: ConfirmBody, request: Request):
        return await confirmation(preferences, body, request)

    @router.post("/v1/assistant/consents:preview")
    def preview_consent(body: ConsentBody, request: Request):
        return response(preferences.prepare_consent(get_current_identity(request), **body.model_dump()))

    @router.get("/v1/assistant/consent-notice")
    def consent_notice(request: Request):
        preferences.scope(get_current_identity(request))
        if preferences.notice is None:
            raise CertificateError(503, "CONSENT_NOT_CONFIGURED", "Chưa cấu hình consent consumer")
        notice = preferences.notice()
        return response({"notice_id": notice.notice_id, "version": notice.version, "status": notice.status,
            "effective_at": notice.effective_at.isoformat(), "disclaimer": notice.disclaimer,
            "purposes": notice.purposes, "retention_summary": notice.retention_summary})

    @router.get("/v1/assistant/consents/{purpose}")
    def consent_history(purpose: str, request: Request, after_version: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=99)):
        return response(preferences.consent_page(get_current_identity(request), purpose, after_version, limit))

    @router.post("/v1/assistant/legacy-imports:preview")
    def preview_import(body: ImportBody, request: Request):
        return response(imports.prepare(get_current_identity(request), body.source_json, body.client_id))

    @router.post("/v1/assistant/legacy-imports:confirm")
    async def confirm_import(body: ConfirmBody, request: Request):
        return await confirmation(imports, body, request)

    @router.get("/v1/assistant/legacy-imports/{import_id}")
    def export_import(import_id: str, request: Request):
        if len(import_id) != 64 or any(char not in "0123456789abcdef" for char in import_id):
            raise CertificateError(422, "IMPORT_ID_INVALID", "Mã import không hợp lệ")
        return response(imports.export(get_current_identity(request), import_id))

    @router.get("/v1/assistant/receipts/{client_id}")
    def receipt(client_id: UUID, request: Request):
        value = preferences.store.receipt(preferences.scope(get_current_identity(request)), client_id)
        if value is None or value.namespace not in {"assistant_preferences", "chat_preferences", "legacy_import", "active_grant", "consent", "conversation_metadata"}:
            raise CertificateError(404, "RESOURCE_NOT_FOUND", "Không tìm thấy receipt")
        return response(value.model_dump(mode="json"))

    if catalog is not None:
        @router.get("/v1/assistant/conversations")
        async def conversation_list(request: Request, title: str = Query("", max_length=120),
                                    archived: bool = False, cursor: str | None = Query(None, max_length=100),
                                    limit: int = Query(20, ge=1, le=100)):
            return response(await catalog.page(get_current_identity(request), title=title, archived=archived, cursor=cursor, limit=limit))

        @router.get("/v1/assistant/conversations/{conversation_id}")
        async def conversation_read(conversation_id: UUID, request: Request):
            return response(await catalog.read(get_current_identity(request), conversation_id))

        @router.post("/v1/assistant/conversations/{conversation_id}:preview")
        async def conversation_preview(conversation_id: UUID, body: MetadataBody, request: Request):
            metadata = body.model_dump(exclude={"expected_version", "client_id"})
            return response(await catalog.prepare(get_current_identity(request), conversation_id, metadata, body.expected_version, body.client_id))

        @router.post("/v1/assistant/conversations:confirm")
        async def conversation_confirm(body: ConfirmBody, request: Request):
            return await confirmation(catalog, body, request)

    @router.post("/v1/assistant/surface:resolve")
    async def surface_context(body: SurfaceBody, request: Request):
        actor = get_current_identity(request)
        preferences.scope(actor)
        audience = preferences.audience(actor)
        if body.surface == "staff_queue" and audience != "staff" or body.surface == "student_home" and audience != "student":
            raise CertificateError(403, "SURFACE_ROLE_MISMATCH", "Surface không thuộc vai trò hiện tại")
        if body.resource is not None:
            if resource_context is None:
                raise CertificateError(503, "CONTEXT_NOT_CONFIGURED", "Chưa cấu hình context tài nguyên")
            from campus247.application.multi_agent.orchestrator import MultiAgentOrchestrator
            if body.operation_id is not None and coordination_store is None:
                raise CertificateError(409, "RESOURCE_RUN_CONSUMER_UNAVAILABLE", "Chưa cấu hình công việc hồ sơ bền vững")
            specialist = MultiAgentOrchestrator.resolve_resource(actor=actor,
                request=AssistanceRequest(surface=body.surface, resource=body.resource, field=body.field),
                operation_id=body.operation_id, context_service=resource_context,
                workflow_service=consumers.proposals.workflow if consumers is not None else None, store=coordination_store)
            value = specialist.context
            if value.status != "observed":
                raise CertificateError(409, "SOURCE_CHANGED", "Nguồn chưa thể xác nhận")
            return response({"context": value.model_dump(mode="json"), "field_guidance": FIELD_GUIDANCE.get(body.field),
                "specialist": specialist.model_dump(mode="json", exclude={"context"}),
                "audience": audience, "action_authority": "none", "excluded": ["staff_notes", "private_memory", "unsaved_fields"]})
        if body.field is not None or body.surface in {"certificate", "service"}:
            raise CertificateError(422, "RESOURCE_REQUIRED", "Cần tham chiếu hồ sơ đã lưu đúng phiên bản")
        return response({"context": {"surface": body.surface}, "audience": audience, "action_authority": "none",
            "field_guidance": None, "excluded": ["staff_notes", "private_memory", "unsaved_fields"]})

    if coordination_store is not None:
        @router.get("/v1/assistant/resource-runs/{run_id}")
        def resource_run_read(run_id: UUID, request: Request):
            actor = get_current_identity(request)
            preferences.scope(actor)
            record = coordination_store.owned_resource_run(run_id, actor.subject_id)
            if record is None:
                raise CertificateError(404, "RESOURCE_NOT_FOUND", "Không tìm thấy công việc hồ sơ")
            from campus247.application.multi_agent.orchestrator import MultiAgentOrchestrator
            value = MultiAgentOrchestrator.resolve_resource(actor=actor, request=AssistanceRequest.model_validate(record["request"]),
                operation_id=run_id, context_service=resource_context, workflow_service=consumers.proposals.workflow,
                store=coordination_store)
            return response({"run": value.run.model_dump(), "continuation": record["continuation"],
                "specialist": value.model_dump(exclude={"context"})})

    if context is not None:
        @router.post("/v1/assistant/chats/{conversation_id}/preferences:preview")
        async def preview_chat_settings(conversation_id: UUID, body: ChatSettingsBody, request: Request):
            actor = get_current_identity(request)
            await context.conversation(actor, conversation_id)
            return response(preferences.prepare_chat(actor, conversation_id, **body.model_dump()))

        @router.get("/v1/assistant/chats/{conversation_id}/preferences")
        async def read_chat_settings(conversation_id: UUID, request: Request):
            actor = get_current_identity(request)
            await context.conversation(actor, conversation_id)
            record = preferences.store.get(preferences.scope(actor), "chat_preferences", conversation_id)
            return response({"version": record.version if record else 0, "saved": record is not None,
                "override": record.payload if record else None,
                "effective": preferences.resolve(actor, conversation_id).preferences.model_dump(mode="json")})

        @router.post("/v1/assistant/context:compose")
        async def compose_context(body: ContextRequest, request: Request):
            memory = getattr(context, "memory", None)
            if body.memory_terms and memory is not None:
                with memory.request_guard(getattr(request.state, "revalidate_identity", None)):
                    return response(await context.compose(get_current_identity(request), body))
            return response(await context.compose(get_current_identity(request), body))

        @router.post("/v1/assistant/context:revalidate")
        async def revalidate_context(body: CachedContextBody, request: Request):
            memory = getattr(context, "memory", None)
            if body.request.memory_terms and memory is not None:
                with memory.request_guard(getattr(request.state, "revalidate_identity", None)):
                    return response(await context.revalidate(get_current_identity(request), body.request, body.expected_sha256))
            return response(await context.revalidate(get_current_identity(request), body.request, body.expected_sha256))

    if grants is not None:
        @router.get("/v1/assistant/grants")
        def grant_list(request: Request, cursor: str = Query("", max_length=100), limit: int = Query(20, ge=1, le=99)):
            return response(grants.page(get_current_identity(request), cursor=cursor, limit=limit))
        @router.post("/v1/assistant/grants:preview")
        def preview_grant(body: GrantSpec, request: Request):
            return response(grants.prepare(get_current_identity(request), body))

        @router.post("/v1/assistant/grants:confirm")
        async def confirm_grant(body: ConfirmBody, request: Request):
            return await confirmation(grants, body, request)

        @router.get("/v1/assistant/grants/{grant_id}")
        def read_grant(grant_id: UUID, request: Request):
            return response(grants.read(get_current_identity(request), grant_id))

        @router.post("/v1/assistant/grants/{grant_id}:revoke-preview")
        def revoke_grant(grant_id: UUID, body: RevokeBody, request: Request):
            return response(grants.prepare_revoke(get_current_identity(request), grant_id, **body.model_dump()))

    if consumers is not None:
        def use_response(value):
            return response({"result": value["result"], "receipt": value["receipt"].model_dump(mode="json")})

        @router.post("/v1/assistant/resources:read")
        def read_resource(body: ResourceReadBody, request: Request):
            return use_response(consumers.read_own(get_current_identity(request), **body.model_dump()))

        @router.post("/v1/assistant/proposals:prepare")
        def prepare_candidate(body: PrepareCandidateBody, request: Request):
            return use_response(consumers.prepare_candidate(get_current_identity(request), **body.model_dump()))

    return router
