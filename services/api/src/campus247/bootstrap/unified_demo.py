"""One local application entry point; reuse the existing single RAG writer.

Candidate has its own retained DB copy. No new paid Gateway is created. This
bootstrap deliberately reports unsupported features rather than mock success.
"""
from pathlib import Path
from datetime import datetime, timezone
import json

import httpx
from fastapi import HTTPException, Request
from starlette.responses import Response

from campus247.application.assistance.context import AssistanceContextService
from campus247.application.assistance.baseline import BaselineMeasurementService
from campus247.application.assistance.workflow import WorkflowPackageService
from campus247.bootstrap.certificate_demo import public_guidance
from campus247.bootstrap.service_demo import create_service_demo_app
from campus247.presentation.assistance import create_assistance_router
from campus247.presentation.baseline import create_baseline_router
from campus247.presentation.identity import get_current_identity
from campus247.presentation.middleware.abuse_limits import AbuseLimiterMiddleware, InMemoryRateLimiterStore, RateLimitRule


def create_unified_demo_app(database: Path, *, frontend_port=None, frontend_build_id=None, rag_transport=None, settings=None,
                            state_database: Path | None = None, consent_mode="disabled", history_database: Path | None = None,
                            legacy_ownership=None, coordination_store=None, personal_memory_store=None, personal_tracking_store=None,
                            chat_application=None):
    if frontend_port not in {None, 3006}:
        raise ValueError("explicit unified candidate frontend3006 required")
    if consent_mode not in {"disabled", "sqlite"} or consent_mode == "sqlite" and state_database is None:
        raise ValueError("explicit disabled/sqlite consent mode and separate state database required")
    app = create_service_demo_app(database, rag_transport=rag_transport, settings=settings)
    app.title = "Campus 24/7 — Unified local candidate"
    app.state.actor_state_store = None
    if state_database is not None:
        from campus247.infrastructure.repositories.sqlite_actor_state import SQLiteActorStateStore
        from campus247.infrastructure.repositories.sqlite_certificates import workspace_path
        if workspace_path(state_database) == workspace_path(database):
            raise ValueError("explicit separate actor state database required")
        app.state.actor_state_store = SQLiteActorStateStore(state_database)
    storage_profile = {"actor_state":"sqlite_internal" if app.state.actor_state_store is not None else "not_configured",
        "actor_state_writes":"server_internal_only", "business":"retained_candidate_sqlite",
        "conversations":"existing8003_proxy", "agent_runs":"existing8003_proxy", "consent":consent_mode, "fallback":False}
    app.state.storage_profile = storage_profile
    if chat_application is not None:
        from campus247.infrastructure.repositories.sqlite_conversations import SQLiteConversationRepository
        native = chat_application.state.native_conversations
        if (history_database is not None or state_database is None
                or not isinstance(native._repo, SQLiteConversationRepository)
                or native._repo.tenant != 'huce-local-public'
                or chat_application.state.actor_state_store.path != app.state.actor_state_store.path
                or getattr(chat_application.state, 'assistant_memory', None) is None
                or chat_application.state.assistant_memory.store is not personal_memory_store):
            raise ValueError('explicit tenant-bound chat and shared actor/memory stores required; no held/proxy mixing')
        app.state.held_history = native
        app.state.native_chat_local = True
        for route in reversed(chat_application.state.native_chat_router.routes):
            app.router.routes.insert(0, route)
        storage_profile['conversations'] = 'explicit_native_local_writer'
        storage_profile['conversation_reads'] = 'explicit_native_owned'
    from campus247.application.assistance.staff_workspace import StaffWorkspaceService
    from campus247.infrastructure.repositories.staff_workspace import StaffWorkspaceRepository
    from campus247.presentation.staff_workspace import create_staff_workspace_router
    staff_workflow = WorkflowPackageService(app.state.service_requests, app.state.certificate_service)
    app.state.staff_workspace = StaffWorkspaceService(
        {"service_request": app.state.service_requests, "certificate_request": app.state.certificate_service},
        staff_workflow, StaffWorkspaceRepository())
    app.include_router(create_staff_workspace_router(app.state.staff_workspace))
    from campus247.application.assistance.case_workflow import CaseWorkflowService
    from campus247.infrastructure.repositories.case_workflow import CaseWorkflowRepository
    from campus247.presentation.case_workflow import create_case_workflow_router
    case_repository = CaseWorkflowRepository()
    resources = {"service_request": app.state.service_requests, "certificate_request": app.state.certificate_service}
    app.state.case_workflow = CaseWorkflowService(resources, app.state.staff_workspace, case_repository, app.state.service_requests.tokens)
    for business_service in resources.values():
        business_service.business_event_sink = case_repository.event
    app.include_router(create_case_workflow_router(app.state.case_workflow))
    if coordination_store is not None:
        from campus247.infrastructure.repositories.sqlite_agent_runs import SQLiteAgentRunStore
        if not isinstance(coordination_store, SQLiteAgentRunStore) or coordination_store.tenant != "huce-local-public":
            raise ValueError("explicit tenant-bound resource run store required")
        if app.state.actor_state_store is None:
            raise ValueError("resource run consumers require actor state")
        app.state.resource_coordination_store = coordination_store
        storage_profile["resource_agent_runs"] = "explicit_tenant_sqlite"
    if history_database is not None:
        from campus247.application.conversation.messages import (
            ConversationMessageService,
        )
        from campus247.infrastructure.repositories.held_history import (
            HeldHistoryRepository,
        )
        from campus247.presentation.held_history import create_held_history_router
        app.state.held_history = ConversationMessageService(HeldHistoryRepository(history_database,tenant="huce-local-public"))
        router = create_held_history_router(app.state.held_history,app.state.certificate_service.authorize)
        # Put exact owned GET routes ahead of the retained generic RAG proxy.
        for route in reversed(router.routes):app.router.routes.insert(0,route)
        storage_profile["conversation_reads"] = "validated_held_read_only"
        if app.state.actor_state_store is not None:
            from campus247.application.conversations.feedback import FeedbackService
            from campus247.infrastructure.repositories.sqlite_auxiliary import (
                SQLiteFeedbackRepository,
            )
            from campus247.ports.identity import IdentityRole
            from campus247.presentation.feedback import create_feedback_router
            app.state.feedback_service = FeedbackService(app.state.held_history,repository=SQLiteFeedbackRepository(
                app.state.actor_state_store,tenant="huce-local-public"))
            router = create_feedback_router(app.state.feedback_service,
                authorize=lambda actor:app.state.certificate_service.authorize(actor,IdentityRole.STUDENT))
            for route in reversed(router.routes):app.router.routes.insert(0,route)
            storage_profile["feedback"] = "sqlite"
    context = AssistanceContextService(app.state.certificate_service, app.state.service_requests, public_guidance)
    workflow = WorkflowPackageService(app.state.service_requests, app.state.certificate_service)
    app.include_router(create_assistance_router(context, workflow))
    app.state.workflow_packages = workflow
    app.state.assistance_context = context
    app.state.assistant_settings = app.state.assistant_grant_requests = app.state.assistant_proposals = None
    if app.state.actor_state_store is not None:
        from campus247.application.assistance.durable_services import ActorSettingsService, GrantRequestService, ProposalStorageService
        from campus247.domain.action.confirmation import ConfirmationTokenService
        from campus247.bootstrap.settings import Settings
        configuration = settings if settings is not None else Settings(_env_file=None, OPENAI_API_KEY=None, GEMINI_API_KEY=None, DEEPSEEK_API_KEY=None)
        options = {"tenant":"huce-local-public", "authorize":app.state.certificate_service.authorize,
            "tokens":ConfirmationTokenService(configuration.CONFIRMATION_SIGNING_KEY),
            "resources":{"certificate_request":app.state.certificate_service,"service_request":app.state.service_requests},
            "workflow":workflow}
        app.state.assistant_settings = ActorSettingsService(app.state.actor_state_store, **options)
        app.state.assistant_grant_requests = GrantRequestService(app.state.actor_state_store, **options)
        app.state.assistant_proposals = ProposalStorageService(app.state.actor_state_store, **options)
        from campus247.application.assistance.staff_drafts import StaffDraftService
        from campus247.application.assistance.state_storage import (
            StorageConflict,
            StorageCorrupt,
            StorageUnavailable,
        )
        from campus247.presentation.errors import create_problem_details
        from campus247.presentation.staff_drafts import create_staff_draft_router
        app.state.staff_drafts = StaffDraftService(app.state.actor_state_store,tenant=options["tenant"],
            resources=options["resources"],workflow=workflow)
        app.include_router(create_staff_draft_router(app.state.staff_drafts))
        for failure in (StorageUnavailable,StorageCorrupt):
            @app.exception_handler(failure)
            async def state_unavailable(request,exc):
                return create_problem_details(request=request,status=503,code="STATE_STORAGE_UNAVAILABLE",
                    title="Không thể lưu hoặc đọc",detail="State storage chưa sẵn sàng; nội dung đã commit được giữ.")

        @app.exception_handler(StorageConflict)
        async def state_conflict(request,exc):
            return create_problem_details(request=request,status=409,code="STATE_CONFLICT",
                title="Nháp đã thay đổi",detail="Giữ nội dung đang soạn và đối chiếu phiên bản trên server.")
    if consent_mode == "sqlite":
        from campus247.application.privacy.consent import PrivacyConsentService, PrivacyNoticeConfig, ServiceUnavailableError
        from campus247.infrastructure.repositories.sqlite_consents import SQLiteConsentRepository
        from campus247.presentation.privacy_notice import create_privacy_router
        from campus247.presentation.errors import create_problem_details
        notice = PrivacyNoticeConfig("unified-local-consent", "unified-local-consent.v1",
            datetime(2026,10,14,tzinfo=timezone.utc), "ACTIVE",
            {"statement":"Local/synthetic: chỉ lưu lựa chọn consent; chưa bật personalization, memory, feedback training hoặc quyền tài nguyên."},
            ["CONSENT_DECLARATION"], ["OPTIONAL_PERSONALIZATION","QUALITY_FEEDBACK"],
            [{"data_class":"CONSENT_DECLARATION","configured_rule":"Append-only local history; không tự xóa dữ liệu hoặc áp dụng retention mới."}])
        app.state.consent_service = PrivacyConsentService(active_notice=notice,
            repository=SQLiteConsentRepository(app.state.actor_state_store,tenant="huce-local-public"))
        app.include_router(create_privacy_router(app.state.consent_service, authorize=app.state.certificate_service.authorize))
        from campus247.application.privacy.requests import PrivacyRequestService
        from campus247.infrastructure.repositories.sqlite_auxiliary import (
            SQLitePrivacyRequestRepository,
        )
        from campus247.presentation.privacy_requests import (
            create_privacy_request_router,
        )
        app.state.privacy_request_service = PrivacyRequestService(repository=SQLitePrivacyRequestRepository(
            app.state.actor_state_store,tenant="huce-local-public"))
        app.include_router(create_privacy_request_router(app.state.privacy_request_service))

        @app.exception_handler(ServiceUnavailableError)
        async def consent_unavailable(request, exc):
            return create_problem_details(request=request,status=503,code="DEPENDENCY_UNAVAILABLE",
                title="Không thể lưu hoặc đọc consent", detail="Lựa chọn đã commit được giữ; dịch vụ chưa sẵn sàng.")
    baseline = BaselineMeasurementService(app.state.service_requests.repository, app.state.certificate_service.authorize)
    if app.state.actor_state_store is not None:
        from campus247.bootstrap.assistant_features import wire_assistant_features
        wire_assistant_features(app, store=app.state.actor_state_store, tenant="huce-local-public",
            authorize=app.state.certificate_service.authorize, tokens=options["tokens"],
            notice=app.state.consent_service.get_active_notice if consent_mode == "sqlite" else None,
            conversations=getattr(app.state, "held_history", None), resource_context=context,
            resources=options["resources"], legacy_ownership=legacy_ownership, proposals=app.state.assistant_proposals, coordination_store=coordination_store,
            personal_memory_store=personal_memory_store, personal_tracking_store=personal_tracking_store)
        storage_profile["assistant_features"] = "uni007_015_local_source"
        if chat_application is not None:
            chat_application.state.chat_context_override = app.state.scoped_context
            chat_application.state.chat_memory_override = app.state.assistant_memory
    app.include_router(create_baseline_router(baseline))
    app.state.baseline_measurements = baseline
    app.add_middleware(AbuseLimiterMiddleware, store=InMemoryRateLimiterStore(), rules=[
        RateLimitRule(path_prefix="/v1/assistant", max_requests=120, window_seconds=60, fail_closed=True),
    ])

    @app.get("/v1/assistant/capabilities")
    def capabilities(request: Request):
        actor = get_current_identity(request)
        app.state.certificate_service.authorize(actor)
        return {"schema_version": "unified-assistance.v1", "mode": "local_synthetic_candidate",
                "context": "server_read_only", "confirmation": "existing_workflow",
                "baseline_measurement": "opt_in_actor_owned", "contract_pack": "unified-contracts.v1",
                "workflow_definitions": "read_only_shared_workflow_v1",
                "actor_state_storage": storage_profile["actor_state"],
                "consent_declarations":consent_mode,
                "staff_drafts":"durable_private" if app.state.actor_state_store is not None else "not_configured",
                "staff_workspace":"staff-workspace.v1:internal_synthetic",
                "staff_readiness":"deterministic_and_explicit_officer_reviews",
                "staff_preparation":"bounded_synchronous_no_provider",
                "case_workflow":"case-projection.v1:reviewed_transactional_local",
                "structured_supplement":"typed_items_preview_confirmation_delta_recheck",
                "batch_execution":"exact_manifest_per_item_authorized_receipts",
                "case_events":"transactional_metadata_outbox",
                "personal_features":getattr(app.state, "assistant_personal_capabilities", {"memory_management":False,"memory_context":False,"tracking":False}),
                "model_writer": "explicit_native_local_writer" if chat_application is not None else "existing_loopback8003", "new_paid_writer": False,
                "preferences": "durable_confirmed" if app.state.actor_state_store is not None else "not_configured",
                "grants": "resource_bound_read_prepare" if app.state.actor_state_store is not None else "not_configured",
                "legacy_import": "server_verified_ownership_required",
                "preference_model_consumer": "explicit_native_shared_context" if chat_application is not None else "main_factory_only_existing_proxy_unchanged",
                "history_discovery": "actor_owned_metadata_overlay" if (history_database is not None or chat_application is not None) and app.state.actor_state_store is not None else "not_configured",
                "unsupported": ["staff_model_chat", "production", "official_rules_templates_eligibility", "processing_sla", "unmeasured_active_labor"]}

    # The old shell's health route remains; this endpoint identifies the exact
    # unified candidate without claiming model availability or production use.
    @app.get("/v1/assistant/runtime")
    def runtime():
        return {"runtime": "unified-local-completion-candidate" if chat_application is not None else "unified-local-v13-source-candidate", "frontend_port": frontend_port, "frontend_build_id": frontend_build_id,
                "workflow_definitions": "unified-workflow.v1",
                "business_storage": "retained_candidate_sqlite", "rag": "explicit_native_local_writer" if chat_application is not None else "existing8003_proxy",
                "owns_paid_ledger": False, "storage_profile": storage_profile}

    @app.get("/v1/assistant/storage")
    def storage(request: Request):
        actor = get_current_identity(request)
        app.state.certificate_service.authorize(actor)
        if app.state.actor_state_store is not None:
            from campus247.application.assistance.state_storage import StorageUnavailable, StorageCorrupt
            from campus247.application.document_request.certificates import CertificateError
            try:
                app.state.actor_state_store.check_available()
            except (StorageUnavailable,StorageCorrupt):
                raise CertificateError(503,"STATE_STORAGE_UNAVAILABLE","Storage chưa sẵn sàng; dữ liệu đã commit được giữ") from None
        return Response(json.dumps({"schema_version":"unified-storage.v1",**storage_profile,
            "state_namespaces":["preferences","consent","grant_request","draft","evidence","grant_lifecycle","proposal_bundle","feedback","privacy_request","revocation","staff_draft","assistant_preferences","chat_preferences","legacy_import","active_grant","conversation_metadata"] if app.state.actor_state_store is not None else [],
            "receipts":"atomic_with_state_revision" if app.state.actor_state_store is not None else "not_configured", "application_permissions":"existing_workflow",
            "product_preferences_or_grants_enabled":app.state.actor_state_store is not None}), media_type="application/json", headers={"Cache-Control":"no-store"})

    if frontend_port is not None:
        @app.get("/{page_path:path}", include_in_schema=False)
        async def frontend(page_path: str, request: Request):
            path = "/" + page_path
            allowed = {"/", "/login", "/services", "/tickets", "/staff", "/chat", "/privacy",
                       "/knowledge/policy-graph", "/knowledge/sources", "/memory", "/notifications"}
            if (path not in allowed and not path.startswith(("/_next/static/", "/images/"))
                    or ".." in path or "\\" in path or len(request.url.query) > 1024):
                raise HTTPException(404)
            try:
                async with httpx.AsyncClient(timeout=10, trust_env=False, follow_redirects=False) as client:
                    upstream = await client.get(f"http://127.0.0.1:{frontend_port}" + path, params=request.query_params)
                    if len(upstream.content) > 4_194_304:
                        raise HTTPException(502)
                    return Response(upstream.content, status_code=upstream.status_code,
                                    headers={"Content-Type": upstream.headers.get("content-type", "application/octet-stream")})
            except httpx.HTTPError:
                raise HTTPException(503, "Unified frontend unavailable") from None
    return app
