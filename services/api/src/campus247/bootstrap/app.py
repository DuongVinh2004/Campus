from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response, JSONResponse


from campus247.application.authorization.concealment import ResourceNotFoundError
from campus247.agent.graph import CampusAgentWorkflow
from campus247.application.retrieval.context import RetrievalContextFactory
from campus247.domain.retrieval import RetrievalContext, RetrievalQuery
from campus247.application.retrieval.canonical import CanonicalRetrievalService
from campus247.ports.llm import LlmGateway
from campus247.ports.citation_source import CitationSourceReader
from campus247.infrastructure.retrieval.public_knowledge import PublicKnowledgeStore
from campus247.application.conversation.citation_source import CitationSourceService
from campus247.presentation.citation_source import create_citation_source_router
from campus247.agent.state import NormalizedTurn
from campus247.ports.identity import IdentityContext
from campus247.bootstrap.telemetry import extract_trace_context
from campus247.application.action.idempotency import IdempotencyLedger
from campus247.presentation.errors import (
    http_exception_handler,
    validation_exception_handler,
)
from campus247.application.audit.writer import AuditWriter
from campus247.application.booking.availability import ExistingBooking, RoomInfo
from campus247.application.conversation.messages import ConversationMessageService, ConversationRepository, ConversationStorageUnavailable
from campus247.application.conversation.history import ConversationHistoryService
from campus247.application.conversations.feedback import FeedbackService
from campus247.application.identity.logout import InMemoryRevocationStore, LogoutService
from campus247.application.privacy.consent import PrivacyConsentService, PrivacyNoticeConfig, ServiceUnavailableError
from campus247.application.privacy.requests import PrivacyRequestService
from campus247.application.ticket.confirm import TicketConfirmationService
from campus247.application.ticket.preview import TicketPreviewService
from campus247.bootstrap.settings import Settings, get_settings
from campus247.domain.action.confirmation import ConfirmationTokenService
from campus247.domain.policy.student import StudentPolicyEngine
from campus247.domain.shared.values import generate_uuid7
from campus247.infrastructure.db import get_engine
from campus247.infrastructure.identity.mock import SyntheticIdentityAdapter
from campus247.infrastructure.llm.factory import create_llm_gateway
from campus247.infrastructure.retrieval.hybrid import HybridSearchAdapter
from campus247.infrastructure.retrieval.lexical import LexicalSearchAdapter
from campus247.infrastructure.retrieval.vector import VectorSearchAdapter
from campus247.infrastructure.schedule.synthetic import SyntheticScheduleAdapter
from campus247.presentation import (
    capabilities,
    chat,
    document_requests,
    feedback,
    handovers,
    health,
    identity,
    knowledge,
    logout,
    privacy_notice,
    privacy_requests,
    rooms,
    schedule,
    ticket_queries,
    tickets,
)
from campus247.presentation.capabilities import CapabilityManager
from campus247.presentation.identity import IdentityMiddleware


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Assign X-Request-Id header and state attribute to every incoming request."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("x-request-id") or generate_uuid7()
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage database engine startup and shutdown."""
    settings = app.state.runtime_settings
    engine = None
    app.state.database_initialization_failed = False
    try:
        engine = get_engine(settings.DATABASE_URL)
        app.state.db_engine = engine
    except Exception:
        app.state.database_initialization_failed = True
    knowledge_runtime = getattr(app.state, "knowledge_runtime", None)
    if knowledge_runtime is not None:
        await knowledge_runtime.start()
    warmup = None
    if settings.rag_engine == "v2" and knowledge_runtime is not None:
        from campus247.bootstrap.rag_v2 import start_rag_v2_warmup
        warmup = app.state.rag_v2_warmup_task = start_rag_v2_warmup(
            app.state.rag_v2_node, knowledge_runtime, app.state.retrieval_context_factory)
    try:
        yield
    finally:
        if warmup is not None:
            import asyncio
            from contextlib import suppress
            warmup.cancel()
            with suppress(asyncio.CancelledError):
                await warmup
        if knowledge_runtime is not None:
            await knowledge_runtime.close()
    if engine is not None:
        try:
            await engine.dispose()
        except Exception:
            pass


def create_app(*, retrieval_context_factory: RetrievalContextFactory | None = None,
               canonical_retrieval_service: CanonicalRetrievalService | None = None,
               llm_gateway: LlmGateway | None = None,
               conversation_repository: ConversationRepository | None = None,
               consent_repository=None,
               actor_state_store=None,
               personal_memory_store=None,
               citation_source_reader: CitationSourceReader | None = None,
               citation_source_audit_writer: AuditWriter | None = None,
               runtime_settings: Settings | None = None,
               synthetic_tenant_id: str | None = None,
               allow_labeled_simulation: bool = False,
               public_knowledge_store: PublicKnowledgeStore | None = None,
               claim_verifier=None, certificate_service=None,
               multi_agent_store=None, multi_agent_policy=None, multi_agent_admission=None, policy_graph=None,
               knowledge_runtime=None, identity_adapter_override=None, rag_v2_node=None) -> FastAPI:
    """Application factory for Campus 24/7 FastAPI backend service."""
    if runtime_settings is not None and not isinstance(runtime_settings, Settings):
        raise ValueError("validated runtime settings required")
    settings = runtime_settings if runtime_settings is not None else get_settings()
    # Fail before opening local stores or constructing a gateway. v1 never reads
    # or initializes the optional v2 index and adapters.
    if settings.rag_engine == "v2" and rag_v2_node is None:
        from campus247.rag_v2.adapters.index_store import ROOT as RAG_ROOT
        index_dir = settings.rag_v2_index_dir
        if not index_dir.is_absolute():
            index_dir = RAG_ROOT / index_dir
        if not index_dir.is_dir():
            raise ValueError("RAG_V2_INDEX_MISSING: configure CAMPUS247_RAG_V2_INDEX")
    if identity_adapter_override is not None and settings.ENVIRONMENT != "development":
        raise ValueError("Local identity injection is restricted to the development composition")
    if knowledge_runtime is not None:
        from campus247.infrastructure.knowledge.runtime import KnowledgeReleaseRuntime
        if (not isinstance(knowledge_runtime, KnowledgeReleaseRuntime) or public_knowledge_store is not None
            or canonical_retrieval_service is not None or multi_agent_store is not None):
            raise ValueError("knowledge runtime requires one explicit retrieval binding")
        citation_source_reader = knowledge_runtime
    from campus247.bootstrap.actor_storage import actor_storage, auxiliary_repositories
    from campus247.bootstrap.run_storage import run_storage
    actor_state_store, actor_profile = actor_storage(settings,synthetic_tenant_id,actor_state_store)
    multi_agent_store, run_profile = run_storage(settings,synthetic_tenant_id,multi_agent_store)
    feedback_repository, request_repository, revocation_store = auxiliary_repositories(actor_state_store,synthetic_tenant_id)
    from campus247.bootstrap.consent_storage import consent_storage
    consent_repository, consent_profile = consent_storage(settings, synthetic_tenant_id, consent_repository)
    if public_knowledge_store is not None and not isinstance(public_knowledge_store, PublicKnowledgeStore):
        raise ValueError("typed public knowledge store required")
    if citation_source_audit_writer is not None and not isinstance(citation_source_audit_writer, AuditWriter):
        raise ValueError("typed citation source audit writer required")
    if type(allow_labeled_simulation) is not bool:
        raise ValueError("explicit server simulation configuration required")
    if (synthetic_tenant_id is not None or allow_labeled_simulation) and (
        settings.ENVIRONMENT != "development" or not settings.DEMO_MODE
    ):
        raise ValueError("synthetic retrieval binding requires development demo mode")
    if allow_labeled_simulation and synthetic_tenant_id is None:
        raise ValueError("synthetic retrieval requires a configured tenant")
    retrieval_profile = settings.retrieval_profile
    if retrieval_context_factory is not None and not isinstance(retrieval_context_factory, RetrievalContextFactory):
        raise ValueError("trusted retrieval context factory required")
    if canonical_retrieval_service is not None and not isinstance(canonical_retrieval_service, CanonicalRetrievalService):
        raise ValueError("typed canonical retrieval service required")
    is_prod = str(settings.ENVIRONMENT).strip().lower() == "production"

    from campus247.infrastructure.identity.production_guard import (
        validate_identity_configuration,
    )
    validate_identity_configuration(
        environment=settings.ENVIRONMENT,
        auth_provider="mock" if getattr(settings, "DEMO_MODE", True) else "entra",
        allow_demo_login=not is_prod and getattr(settings, "DEMO_MODE", True),
    )

    app = FastAPI(
        title="Campus 24/7 API",
        version="0.1.0",
        description="Campus 24/7 — HUCE Demo backend application API",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )
    app.state.retrieval_profile = retrieval_profile
    app.state.runtime_settings = settings

    # 1. Request ID Middleware
    app.add_middleware(RequestIdMiddleware)

    # Register RFC 9457 Problem Details Exception Handlers
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)

    @app.exception_handler(ConversationStorageUnavailable)
    async def conversation_storage_failure(request: Request, exc):
        from campus247.presentation.errors import create_problem_details
        return create_problem_details(request=request, status=503, code="DEPENDENCY_UNAVAILABLE",
            title="Không thể lưu hoặc đọc lịch sử", detail="Dịch vụ lịch sử chưa sẵn sàng. Dữ liệu đã lưu được giữ.", retryable=False)

    @app.exception_handler(ServiceUnavailableError)
    async def consent_storage_failure(request: Request, exc):
        from campus247.presentation.errors import create_problem_details
        return create_problem_details(request=request,status=503,code="DEPENDENCY_UNAVAILABLE",
            title="Không thể lưu hoặc đọc consent",detail="Dịch vụ consent chưa sẵn sàng. Quyết định đã lưu được giữ.",retryable=False)

    from campus247.infrastructure.repositories.sqlite_agent_runs import (
        RunStorageUnavailable,
    )

    @app.exception_handler(RunStorageUnavailable)
    async def run_storage_failure(request,exc):
        from campus247.presentation.errors import create_problem_details
        return create_problem_details(request=request,status=503,code="DEPENDENCY_UNAVAILABLE",
            title="Không thể lưu hoặc đọc run",detail="Run storage chưa sẵn sàng; checkpoint đã commit được giữ.")

    @app.exception_handler(ResourceNotFoundError)
    async def resource_not_found_handler(request: Request, exc: ResourceNotFoundError) -> JSONResponse:
        from campus247.presentation.errors import create_problem_details
        return create_problem_details(
            request=request,
            status=404,
            code="RESOURCE_NOT_FOUND",
            title="Tài nguyên không tồn tại",
            detail=str(exc)
        )


    # 2. Rate Limiting and Abuse Prevention Middleware
    from campus247.presentation.middleware.abuse_limits import (
        AbuseLimiterMiddleware,
        InMemoryRateLimiterStore,
        RateLimitRule,
    )
    abuse_rules = [
        RateLimitRule(path_prefix="/v1/conversations", max_requests=30, window_seconds=60, fail_closed=True),
        RateLimitRule(path_prefix="/v1/tickets", max_requests=20, window_seconds=60, fail_closed=True),
        RateLimitRule(path_prefix="/v1/rooms/book", max_requests=10, window_seconds=60, fail_closed=True),
        RateLimitRule(path_prefix="/v1/privacy/operations", max_requests=10, window_seconds=60, fail_closed=True),
        RateLimitRule(path_prefix="/v1/privacy/requests", max_requests=10, window_seconds=60, fail_closed=True),
    ]
    app.add_middleware(AbuseLimiterMiddleware, store=InMemoryRateLimiterStore(), rules=abuse_rules)

    # 3. Synthetic Identity Middleware for Demo Mode
    identity_adapter = identity_adapter_override or SyntheticIdentityAdapter(
        secret_key=settings.IDENTITY_SECRET_KEY,
        environment=settings.ENVIRONMENT,
        tenant_id=synthetic_tenant_id,
    )
    from campus247.application.identity.session_service import (
        SessionService,
        get_session_service,
    )
    session_service = SessionService(revocation_store) if revocation_store is not None else get_session_service()
    app.state.current_session_service = session_service
    app.add_middleware(IdentityMiddleware, adapter=identity_adapter,session_service=session_service)

    # 3. CORS Middleware for Local Frontend Development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Initialize shared services and stores for demo mode
    from campus247.infrastructure.llm.egress_policy import EgressPolicy, EgressViolationError
    egress_policy = EgressPolicy()

    def minimize_history_content(content: str) -> str | None:
        try:
            egress_policy.validate_and_minimize({"purpose": "FAQ_ANSWERING",
                "messages": [{"role": "user", "content": content}]})
            return content
        except EgressViolationError:
            return None

    from campus247.bootstrap.conversation_storage import conversation_storage
    resolved_conversations, storage_profile = conversation_storage(settings, conversation_repository,tenant=synthetic_tenant_id)
    app.state.conversation_storage = storage_profile
    conv_service = ConversationMessageService(repository=resolved_conversations,
        minimize_content=minimize_history_content)
    history_service = ConversationHistoryService(conv_service, minimize=minimize_history_content)
    policy_engine = StudentPolicyEngine()
    from campus247.infrastructure.repositories.composition import RepositoryComposition
    repo_comp = RepositoryComposition(settings.ENVIRONMENT)
    
    schedule_adapter = repo_comp.schedule_adapter

    token_svc = ConfirmationTokenService(signing_key=settings.CONFIRMATION_SIGNING_KEY)
    app.state.assistant_settings = None
    if actor_state_store is not None and knowledge_runtime is None:
        from campus247.application.assistance.durable_services import (
            ActorSettingsService,
        )
        app.state.assistant_settings = ActorSettingsService(actor_state_store,tenant=synthetic_tenant_id,
            authorize=request_repository.scope,tokens=token_svc)
    preview_svc = TicketPreviewService(confirmation_service=token_svc, policy_engine=policy_engine)
    idempotency_ledger = IdempotencyLedger()
    audit_writer = AuditWriter()
    confirm_svc = TicketConfirmationService(
        confirmation_service=token_svc,
        idempotency_ledger=idempotency_ledger,
        audit_writer=audit_writer,
        policy_engine=policy_engine,
    )

    ticket_store = repo_comp.ticket_store
    doc_store = repo_comp.doc_store
    handover_store = repo_comp.handover_store
    sources_store = repo_comp.sources_store
    versions_store = repo_comp.versions_store

    rooms_list = repo_comp.rooms_list
    bookings_list = repo_comp.bookings_list

    feedback_service = FeedbackService(conv_service=conv_service,repository=feedback_repository)

    notice = PrivacyNoticeConfig(
        notice_id=generate_uuid7(),
        version="1.0.0",
        effective_at=datetime.now(timezone.utc),
        status="ACTIVE",
        disclaimer={"statement": ("Nguồn HUCE công khai trong phạm vi release đã duyệt kỹ thuật; chưa kết nối SSO hoặc dịch vụ hồ sơ HUCE."
            if knowledge_runtime is not None else "HUCE demo synthetic data only")},
        data_categories=["ACCOUNT_CONTEXT", "CONVERSATION_CONTENT", "REQUEST_METADATA", "AUDIT_METADATA"],
        purposes=["SERVICE_DELIVERY", "SAFETY_HANDOVER", "QUALITY_FEEDBACK", "SECURITY_AUDIT"],
        retention_summary=[{"data_class": "ACCOUNT_CONTEXT", "configured_rule": "PRIV-RET-001"}],
    )
    consent_service = PrivacyConsentService(active_notice=notice, audit_writer=audit_writer,repository=consent_repository)
    app.state.consent_storage = consent_profile
    privacy_request_service = PrivacyRequestService(audit_writer=audit_writer,repository=request_repository)
    logout_service = LogoutService(revocation_store=InMemoryRevocationStore())
    capability_manager = CapabilityManager()
    app.state.actor_state_store = actor_state_store
    app.state.auxiliary_storage = {"actor_state":actor_profile,"agent_runs":run_profile,
        "feedback":actor_profile["durability"],"privacy_requests":actor_profile["durability"],
        "session_revocation":actor_profile["durability"],"consent":consent_profile,"fallback":False}
    app.state.feedback_service, app.state.privacy_request_service = feedback_service, privacy_request_service
    assistant_context = None
    if actor_state_store is not None and knowledge_runtime is None:
        from campus247.bootstrap.assistant_features import wire_assistant_features
        assistant_context = wire_assistant_features(app, store=actor_state_store, tenant=synthetic_tenant_id,
            authorize=request_repository.scope, tokens=token_svc,
            notice=consent_service.get_active_notice if consent_repository is not None and consent_repository.store.path == actor_state_store.path else None,
            conversations=conv_service, personal_memory_store=personal_memory_store)

    async def prepare_assistant_turn(turn, actor, current_identity=None):
        from dataclasses import replace
        def coordination_identity():
            current = current_identity() if current_identity is not None else actor
            if (current.subject_id, current.tenant_id, current.roles, current.session_id) != (actor.subject_id, actor.tenant_id, actor.roles, actor.session_id):
                raise ValueError("coordination identity changed")
            return current
        turn = replace(turn, coordination_guard=coordination_identity)
        chat_context = getattr(app.state, 'chat_context_override', assistant_context)
        if chat_context is None:
            return turn
        conversation = await chat_context.conversation(actor, turn.session_id)
        preferences = chat_context.preferences
        history_allowed = preferences.consented(actor, "CONVERSATION_HISTORY")
        def fresh_actor():
            current = current_identity() if current_identity is not None else actor
            preferences.scope(current)
            if (current.subject_id, current.tenant_id, current.roles, current.session_id) != (actor.subject_id, actor.tenant_id, actor.roles, actor.session_id):
                raise ValueError("actor context changed")
            return current
        def guard():
            current = fresh_actor()
            if conversation.retention_expires_at <= datetime.now(timezone.utc):
                raise ValueError("history retention expired")
            if history_allowed and not preferences.consented(current, "CONVERSATION_HISTORY"):
                raise ValueError("history consent changed")
        def presentation():
            return preferences.resolve(fresh_actor(), turn.session_id)
        prepared = replace(turn, history=turn.history if history_allowed else None,
                       presentation=None if conversation.mode == 'temporary' else presentation, context_guard=guard)
        from campus247.application.conversation.personal_context import with_personal_context
        return with_personal_context(prepared, actor, getattr(app.state, 'chat_memory_override', getattr(app.state, 'assistant_memory', None)),
            current_identity=current_identity)

    # Mount all 15 presentation routers
    # Health: /health/live, /health/ready
    app.include_router(health.router)

    # Identity: /v1/users/me
    app.include_router(identity.create_identity_router(adapter=identity_adapter, environment=settings.ENVIRONMENT))

    if llm_gateway is None:
        llm_gateway = create_llm_gateway(settings=settings)
    if settings.rag_engine == "v2":
        if rag_v2_node is None:
            from campus247.bootstrap.rag_v2 import load_rag_v2
            rag_v2_node = load_rag_v2(settings, gateway=llm_gateway, knowledge_runtime=knowledge_runtime,
                inventory_reader=getattr(knowledge_runtime, "rag_v2_inventory", None))
        app.state.rag_v2_node = rag_v2_node
        app.state.retrieval_context_factory = retrieval_context_factory
    vec_adapter = VectorSearchAdapter()
    lex_adapter = LexicalSearchAdapter()
    hybrid_adapter = HybridSearchAdapter(vec_adapter, lex_adapter, profile=retrieval_profile)

    async def search_knowledge(query: str, context: RetrievalContext) -> list[dict[str, Any]]:
        try:
            if knowledge_runtime is not None:
                return await knowledge_runtime.search(query, context)
            if public_knowledge_store is not None:
                return await public_knowledge_store.search(query, context)
            if canonical_retrieval_service is not None:
                result = await canonical_retrieval_service.retrieve(RetrievalQuery(query, locale=context.locale), context)
                return [{"chunk_id": c.chunk_id, "source_id": c.source_id,
                    "document_version_id": c.document_version_id, "section_path": " / ".join(c.section_path),
                    "title": c.title, "issuer": c.issuer, "canonical_uri": c.canonical_uri,
                    "version_label": c.version_label, "source_status": c.source_status,
                    "locator": {"section_path": " / ".join(c.section_path),
                        "page_start": c.page_start, "page_end": c.page_end},
                    "content_text": c.content_text, "quote_span_hash": c.quote_span_hash,
                    "document_number": c.document_number, "page_start": c.page_start, "page_end": c.page_end,
                    "effective_from": c.effective_from.isoformat() if c.effective_from else None,
                    "effective_until": c.effective_until.isoformat() if c.effective_until else None,
                    "simulation_label": c.simulation_label, "score": c.rerank_score,
                    "profile_version": result.profile_version, "index_version": result.index_version}
                    for c in result.candidates]
            candidates = await hybrid_adapter.search(query, context=context)
            return [
                {
                    "chunk_id": c.chunk_id,
                    "document_version_id": c.document_version_id,
                    "section_path": c.section_path,
                    "title": c.section_path or "Văn bản quy định HUCE",
                    "content_text": c.content_text,
                    "score": c.score,
                }
                for c in candidates
            ]
        except TimeoutError:
            raise
        except Exception:
            raise RuntimeError("retrieval unavailable") from None

    workflow_kwargs = dict(
        context_search_fn=search_knowledge, llm_gateway=llm_gateway, require_retrieval_context=True,
        evidence_support_threshold=retrieval_profile.evidence_support_threshold,
        claim_verifier=claim_verifier,
        **({"rag_engine": "v2", "rag_v2_node": rag_v2_node} if settings.rag_engine == "v2" else {}),
        **({"parallel_classify": True} if settings.rag_engine == "v2" and settings.parallel_classify else {}),
    )
    if multi_agent_store is not None:
        from dataclasses import asdict, is_dataclass
        from campus247.agent.multi_rag import MultiAgentWorkflow
        from campus247.infrastructure.repositories.sqlite_agent_runs import SQLiteAgentRunStore
        if not isinstance(multi_agent_store, SQLiteAgentRunStore) or citation_source_reader is None:
            raise ValueError("multi-agent requires a durable run store and original source reader")
        graph_search = None
        if policy_graph is not None:
            from campus247.application.policy_graph.service import PolicyGraphService
            from campus247.infrastructure.retrieval.public_hybrid import PublicHybridKnowledgeStore
            if not isinstance(policy_graph, PolicyGraphService) or not isinstance(public_knowledge_store, PublicHybridKnowledgeStore):
                raise ValueError("graph retrieval requires typed graph and hybrid bindings")
            from campus247.domain.policy_graph import source_fingerprint
            if (policy_graph.reader is not citation_source_reader
                    or policy_graph.index_fingerprint != public_knowledge_store.fingerprint
                    or policy_graph.source_fingerprint != source_fingerprint(public_knowledge_store.rows)):
                raise ValueError("graph reader/index/source binding mismatch")
            graph_search = public_knowledge_store.search
        agent_workflow = MultiAgentWorkflow(store=multi_agent_store, source_reader=citation_source_reader, admission=multi_agent_admission,
            policy_graph=policy_graph, graph_search=graph_search,
            policy=multi_agent_policy, snapshot={"corpus": getattr(public_knowledge_store, "fingerprint", "unknown"),
                "index": getattr(public_knowledge_store, "fingerprint", "unknown"),
                "model": getattr(getattr(llm_gateway, "adapter", None), "_model_name", "unknown"),
                "retrieval": asdict(public_knowledge_store.policy) if is_dataclass(
                    getattr(public_knowledge_store, "policy", None)) else "unknown"}, **workflow_kwargs)
        app.state.multi_agent_workflow = agent_workflow
        app.state.coordination_capabilities = {"profile": "coordination-checkpoint.v1", "read": True,
            "resume": True, "transition_receipts": True, "writer": "native_current_composition"}
    else:
        agent_workflow = CampusAgentWorkflow(**workflow_kwargs, knowledge_only=knowledge_runtime is not None)

    def create_current_context(turn, identity, *, effective_at=None, trace_id=None):
        if retrieval_context_factory is None:
            return None
        return retrieval_context_factory.create(identity, effective_at=effective_at or datetime.now(timezone.utc),
            locale=turn.locale, trace_id=trace_id or extract_trace_context({})["trace_id"],
            allow_simulation=allow_labeled_simulation)

    async def run_trusted_agent(turn: NormalizedTurn, identity: IdentityContext, *, progress=None, current_identity=None):
        if turn.history is not None:
            turn.history.block(identity.subject_id, turn.session_id)
        context = None
        if retrieval_context_factory is not None:
            try:
                context = create_current_context(turn, identity)
            except Exception:
                # Missing/stale server scope never falls back to fabricated grants.
                context = None
        if multi_agent_store is not None:
            def refresh_context():
                actor = current_identity() if current_identity is not None else identity
                if actor.subject_id != turn.user_id:
                    raise ValueError("actor binding changed")
                return create_current_context(turn, actor,
                    effective_at=context.effective_at if context else None, trace_id=context.trace_id if context else None)
            result = await agent_workflow.arun(turn, retrieval_context=context, progress=progress,
                current_context=refresh_context)
        else:
            if knowledge_runtime is not None:
                from dataclasses import replace
                async with knowledge_runtime.turn(context) as snapshot:
                    result = await agent_workflow.arun(turn, retrieval_context=context)
                    await knowledge_runtime.assert_current(snapshot, create_current_context(turn, identity))
                    result = replace(result, knowledge_snapshot=snapshot)
            else:
                result = await agent_workflow.arun(turn, retrieval_context=context)
        if public_knowledge_store is not None:
            import logging
            safe_codes = [code for code in result.errors if isinstance(code, str)
                and code.startswith(("AI_", "EVIDENCE_", "UNAUTHORIZED_")) and len(code) < 80]
            if any(isinstance(code, str) and code.startswith("Policy violation:") for code in result.errors):
                safe_codes.append("OUTPUT_POLICY_REJECTED")
            logging.getLogger("campus247.chat").warning("chat_outcome route=%s terminal=%s codes=%s",
                result.route, result.terminal, safe_codes)
        return result

    # Chat / Conversations: /v1/conversations/{conversation_id}/messages:stream
    async def knowledge_result_guard(state, actor):
        if knowledge_runtime is not None and state.knowledge_snapshot:
            context = create_current_context(state.request, actor)
            await knowledge_runtime.assert_current(state.knowledge_snapshot, context)

    chat_router = chat.create_chat_router(
        conv_service=conv_service, trusted_agent_runner=run_trusted_agent,
        history_service=history_service, turn_preparer=prepare_assistant_turn,
        agent_progress=multi_agent_store is not None,
        result_guard=knowledge_result_guard if knowledge_runtime is not None else None,
        authorize_conversation=(knowledge_runtime.platform.reader
            if knowledge_runtime is not None and identity_adapter_override is not None else None),
    )
    app.include_router(chat_router)
    app.state.native_chat_router = chat_router
    app.state.native_conversations = conv_service
    if multi_agent_store is not None:
        from campus247.presentation.agent_runs import create_agent_run_router
        app.state.native_agent_run_router = create_agent_run_router(workflow=agent_workflow, conversations=conv_service,
            history=history_service, context_factory=create_current_context, turn_preparer=prepare_assistant_turn)
        app.include_router(app.state.native_agent_run_router)
    if policy_graph is not None:
        from campus247.presentation.policy_graph import create_policy_graph_router
        app.include_router(create_policy_graph_router(policy_graph, context_factory=create_current_context,
            gateway=llm_gateway, policy=multi_agent_policy, admission=multi_agent_admission))
        app.state.policy_graph = policy_graph
    app.state.native_citation_router = create_citation_source_router(service=CitationSourceService(
        conversations=conv_service, context_factory=retrieval_context_factory,
        reader=citation_source_reader, audit_writer=citation_source_audit_writer or audit_writer,
        allow_simulation=allow_labeled_simulation,
    ))
    app.include_router(app.state.native_citation_router)

    # Schedule: /v1/students/me/schedule
    app.include_router(schedule.create_schedule_router(schedule_adapter=schedule_adapter, policy_engine=policy_engine))

    # Tickets preview & confirm: /v1/tickets/preview, /v1/tickets/{preview_id}/confirm
    app.include_router(tickets.create_ticket_router(preview_svc=preview_svc, confirm_svc=confirm_svc))

    # Ticket queries: /v1/tickets, /v1/tickets/{ticket_id}
    app.include_router(ticket_queries.create_ticket_query_router(store=ticket_store))

    # Rooms & availability: /v1/rooms, /v1/rooms/{room_id}/availability
    app.include_router(rooms.create_rooms_router(rooms=rooms_list, bookings=bookings_list))

    # Knowledge: /v1/knowledge/sources, /v1/knowledge/document-versions/{id}
    if knowledge_runtime is not None:
        from campus247.presentation.knowledge_platform import create_knowledge_platform_router
        from campus247.application.knowledge.platform_models import PlatformError
        @app.exception_handler(PlatformError)
        async def knowledge_error(request, error):
            return JSONResponse({"code": error.code, "detail": error.detail}, status_code=error.status,
                                headers={"Cache-Control": "no-store"})
        def platform_context(actor):
            turn = NormalizedTurn(session_id=actor.session_id, turn_id=generate_uuid7(), user_id=actor.subject_id, query="preview")
            return create_current_context(turn, actor)
        app.state.knowledge_runtime = knowledge_runtime
        from campus247.infrastructure.knowledge.multipart import parse_upload
        app.include_router(create_knowledge_platform_router(knowledge_runtime.platform, knowledge_runtime, platform_context,
            upload_parser=parse_upload))
    else:
        app.include_router(knowledge.create_knowledge_router(sources=sources_store, versions=versions_store))

    # Document requests: /v1/document-requests, /v1/document-requests/{id}
    if certificate_service is not None:
        from campus247.application.document_request.certificates import CertificateService
        from campus247.presentation.certificates import create_certificate_router
        if not isinstance(certificate_service, CertificateService):
            raise ValueError("typed certificate application service required")
        app.include_router(create_certificate_router(certificate_service))
    else:
        app.include_router(document_requests.create_document_request_router(store=doc_store))

    # Handovers: /v1/staff/handovers, /v1/handovers/{id}
    app.include_router(handovers.create_handover_router(store=handover_store))

    # Answer feedback: /v1/conversations/{conversation_id}/messages/{message_id}/feedback
    app.include_router(feedback.create_feedback_router(feedback_service=feedback_service))

    # Privacy notice & consents: /v1/privacy/notice, /v1/privacy/consents
    app.include_router(privacy_notice.create_privacy_router(consent_service=consent_service))

    # Privacy requests: /v1/privacy/requests, /v1/privacy/requests/{id}
    app.include_router(privacy_requests.create_privacy_request_router(service=privacy_request_service))

    # Capabilities: /v1/capabilities, /v1/operations/capabilities
    app.include_router(capabilities.create_capabilities_router(manager=capability_manager))

    # Logout: /v1/auth/logout & /v1/logout
    app.include_router(logout.create_logout_router(logout_service=logout_service,session_service=session_service), prefix="/v1/auth")
    app.include_router(logout.create_logout_router(logout_service=logout_service,session_service=session_service), prefix="/v1")

    return app

