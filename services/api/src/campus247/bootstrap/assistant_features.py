"""One composition for UNI-007–010; no implicit legacy ownership or fallback."""
from dataclasses import replace

from campus247.application.assistance.preferences import AssistantPreferenceService
from campus247.application.assistance.legacy_import import LegacyImportService
from campus247.application.assistance.grants import AssistantGrantService
from campus247.application.assistance.scoped_context import ScopedContextService
from campus247.application.assistance.state_storage import StorageUnavailable, StorageCorrupt, StorageConflict
from campus247.application.document_request.certificates import CertificateError
from campus247.application.conversation.history import ConversationHistoryService
from campus247.application.conversation.messages import ConversationStorageUnavailable
from campus247.infrastructure.llm.egress_policy import EgressPolicy, EgressViolationError
from campus247.presentation.assistant_state import create_assistant_state_router
from campus247.presentation.errors import create_problem_details


def wire_assistant_features(app, *, store, tenant, authorize, tokens, notice,
                            conversations=None, resource_context=None, resources=None, legacy_ownership=None, proposals=None, coordination_store=None,
                            personal_memory_store=None, personal_tracking_store=None):
    options = {"tenant": tenant, "authorize": authorize, "tokens": tokens, "resources": resources}
    def feature_notice():
        original = notice()
        # Older notices explicitly recorded declarations without enabling
        # these consumers. Never silently reinterpret that prior consent.
        return replace(original, version=original.version+".assistant-features.v1",
            disclaimer={"statement": "Local/synthetic: OPTIONAL_PERSONALIZATION dùng settings trình bày và chỉ dẫn cá nhân như dữ liệu không đáng tin; CONVERSATION_HISTORY chỉ dùng tối đa 5 lượt cùng chat. QUALITY_FEEDBACK không bật training. Tắt một mục đích không xóa lịch sử hoặc mở quyền tài nguyên."},
            purposes=["OPTIONAL_PERSONALIZATION", "CONVERSATION_HISTORY", "QUALITY_FEEDBACK"])
    preferences = AssistantPreferenceService(store, notice=feature_notice if notice else None, **options)
    imports = LegacyImportService(store, ownership=legacy_ownership, **options)
    grants = AssistantGrantService(store, context=resource_context, **options) if resource_context else None
    policy = EgressPolicy()
    def minimize(text):
        try:
            policy.validate_and_minimize({"purpose": "FAQ_ANSWERING", "messages": [{"role": "user", "content": text}]})
            return text
        except EgressViolationError:
            return None
    context = ScopedContextService(preferences=preferences, grants=grants, conversations=conversations,
        history=ConversationHistoryService(conversations, minimize=minimize) if conversations else None, minimize=minimize)
    # These repositories are explicitly supplied, never initialized/migrated on
    # a retained DB by this composition. Unknown legacy chat modes fail closed.
    from campus247.bootstrap.assistant_personal_features import wire_assistant_personal_features
    from campus247.infrastructure.repositories.held_history import HeldHistoryRepository
    native_mode = bool(conversations and not isinstance(conversations._repo, HeldHistoryRepository)
        and callable(getattr(conversations._repo, 'read_owned_mode', None)))
    def conversation_mode(actor, conversation_id):
        preferences.scope(actor)
        if conversation_id is None:
            return "settings"
        reader = getattr(conversations._repo, "read_owned_mode", None) if native_mode else None
        return reader(actor, conversation_id) if callable(reader) else None
    case_service = getattr(app.state, "case_workflow", None)
    source = registry = None
    if case_service is not None and personal_tracking_store is not None:
        from campus247.application.assistance.personal_consumers import CaseTrackingSource, CurrentRecipientRegistry
        source, registry = CaseTrackingSource(case_service, grants), CurrentRecipientRegistry(case_service)
        app.state.assistant_recipient_registry = registry
        from campus247.presentation.identity import get_current_identity
        @app.middleware("http")
        async def retain_verified_recipient_session(request, call_next):
            result = await call_next(request)
            if request.url.path.startswith("/v1/") and getattr(request.state, "identity", None) is not None:
                actor = get_current_identity(request)
                token = request.headers.get("authorization", "").removeprefix("Bearer ").strip() or request.cookies.get("auth_token", "")
                registry.capture(actor, token)
            return result
    def notification_projection(actor, spec, event):
        fresh = registry.resolve(actor.tenant_id, actor.subject_id, actor.session_id)
        return source.project(fresh, spec, event)
    memory, tracking = wire_assistant_personal_features(app, memory_store=personal_memory_store,
        tracking_store=personal_tracking_store, tenant=tenant, authorize=authorize, tokens=tokens,
        preferences=preferences, grants=grants, conversation_mode=conversation_mode, minimize=minimize,
        tracking_source=source, resolve_recipient=registry.resolve if registry else None,
        project_notification=notification_projection if registry and source else None,
        memory_context_consumer=personal_memory_store is not None)
    context.memory = memory
    app.state.assistant_personal_capabilities['temporary_chat'] = native_mode
    app.state.assistant_personal_capabilities['model_memory'] = bool(memory and native_mode)
    app.state.assistant_tracking_source = source
    app.state.assistant_preferences = preferences
    app.state.assistant_imports, app.state.assistant_grants, app.state.scoped_context = imports, grants, context
    from campus247.application.assistance.grant_consumers import GrantConsumerService
    consumers = GrantConsumerService(grants, proposals) if grants is not None and proposals is not None else None
    app.state.assistant_grant_consumers = consumers
    from campus247.application.document_request.student_preparation import StudentPreparationService
    student_preparation = StudentPreparationService(resources, proposals) if resources and proposals else None
    app.state.student_preparation = student_preparation
    if getattr(app.state, "staff_workspace", None) is None:
        from campus247.presentation.staff_workspace import create_staff_workspace_router
        app.include_router(create_staff_workspace_router(None))
    if getattr(app.state, "case_workflow", None) is None:
        from campus247.presentation.case_workflow import create_case_workflow_router
        app.include_router(create_case_workflow_router(None))
    from campus247.application.conversation.catalog import ConversationCatalogService
    catalog = ConversationCatalogService(store, tenant=tenant, authorize=authorize, tokens=tokens, conversations=conversations)
    app.state.conversation_catalog = catalog
    app.include_router(create_assistant_state_router(preferences=preferences, imports=imports, grants=grants,
        context=context, consumers=consumers, catalog=catalog, resource_context=resource_context, coordination_store=coordination_store,
        student_preparation=student_preparation))

    @app.exception_handler(CertificateError)
    async def feature_error(request, exc):
        response = create_problem_details(request=request, status=exc.status, code=exc.code,
            title="Không thể thực hiện", detail=exc.detail)
        response.headers["Cache-Control"] = "no-store"
        return response

    for error in (StorageUnavailable, StorageCorrupt, ConversationStorageUnavailable):
        @app.exception_handler(error)
        async def unavailable(request, exc):
            response = create_problem_details(request=request, status=503, code="STATE_STORAGE_UNAVAILABLE",
                title="Không thể lưu hoặc đọc", detail="Dữ liệu đã commit được giữ; storage chưa sẵn sàng.")
            response.headers["Cache-Control"] = "no-store"
            return response

    @app.exception_handler(StorageConflict)
    async def conflict(request, exc):
        response = create_problem_details(request=request, status=409, code="STATE_CONFLICT",
            title="Dữ liệu đã thay đổi", detail="Giữ nội dung hiện tại và đọc lại phiên bản hoặc receipt.")
        response.headers["Cache-Control"] = "no-store"
        return response

    return context
