"""One local backend composition. Historical stores are copied, never reset.

Native chat, service workflows, history and actor state share one application.
Guarded mode dispatches no model. Explicit retained mode reuses the existing
exclusive paid writer and cumulative budget; it never creates new quota.
"""
from pathlib import Path
import json
import os
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / p) for p in (".", "scripts", "services/api/src", "packages/synthetic/src")]
TENANT = "huce-local-public"
STATE = Path(os.environ.get("CAMPUS_RUNTIME_DIR", str(ROOT / ".tooling/campus-single-entry-20261015-01/runtime")))
SOURCES = {
    "business": "infra/local/unified-ai-20261014-01/business-candidate01.sqlite3",
    "actor": "infra/local/unified-ai-20261014-05/actor-state.sqlite3",
    "history": "infra/local/public-rag-20261013/conversations.sqlite3",
    "runs": "infra/local/multi-agent-integrated-20261013-01/agent-runs.sqlite3",
}


def checked(path):
    path = Path(path).absolute()
    if path.resolve() == ROOT or not path.resolve().is_relative_to(ROOT):
        raise ValueError("Exact workspace descendant required")
    for parent in (path, *path.parents):
        if parent == ROOT:
            break
        if parent.is_symlink() or parent.is_junction() or (
            parent.exists() and getattr(parent.stat(), "st_file_attributes", 0) & 0x400
        ):
            raise ValueError("Reparse target denied")
    return path.resolve()


def initialize():
    """Create an independent consistent copy once; restart uses that same copy."""
    target = checked(STATE)
    if target.exists():
        if not (target / "initialized.json").is_file():
            raise RuntimeError("Incomplete initialization retained; inspect runtime directory")
        return
    sources = {name: checked(ROOT / source) for name, source in SOURCES.items()}
    if not all(path.is_file() for path in sources.values()):
        raise FileNotFoundError("Retained local source database missing")
    checked(target.parent).mkdir(parents=True, exist_ok=True)
    target.mkdir()
    for name, source in sources.items():
        destination = checked(target / (name + ".sqlite3"))
        with destination.open("xb"):
            pass
        with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as origin:
            with sqlite3.connect(destination) as copy:
                origin.backup(copy)
    from campus247.infrastructure.repositories.sqlite_assistant_memory import SQLiteAssistantMemory
    from campus247.infrastructure.repositories.sqlite_assistant_tracking import SQLiteAssistantTracking
    SQLiteAssistantMemory(checked(target / "memory.sqlite3"), initialize=True)
    SQLiteAssistantTracking(checked(target / "tracking.sqlite3"), initialize=True)
    with checked(target / "initialized.json").open("x", encoding="utf-8") as stream:
        json.dump({"method": "sqlite_read_only_source_backup", "sources": SOURCES,
                   "originals_preserved": True, "model_calls": 0}, stream, indent=2)


def create_runtime_app(*, model_mode=None):
    from campus247.bootstrap.app import create_app
    from campus247.bootstrap.settings import Settings
    from campus247.bootstrap.unified_demo import create_unified_demo_app
    from campus247.application.retrieval.context import RetrievalContextFactory
    from campus247.infrastructure.repositories.sqlite_agent_runs import SQLiteAgentRunStore
    from campus247.infrastructure.repositories.sqlite_assistant_memory import SQLiteAssistantMemory
    from campus247.infrastructure.repositories.sqlite_assistant_tracking import SQLiteAssistantTracking
    from campus247.infrastructure.repositories.sqlite_conversations import SQLiteConversationRepository
    from scripts.public_rag_retrieval import load_public_hybrid_store
    from scripts.run_public_rag import ScopeResolver
    from scripts.run_multi_agent import GuardedGateway, headroom
    from campus247.application.multi_agent.contracts import MultiAgentPolicy

    from scripts.multi_agent_live_resources import UNCAPPED_AUTHORIZATION
    mode = model_mode or os.environ.get("CAMPUS_MODEL_MODE") or ("retained" if UNCAPPED_AUTHORIZATION.exists() else "guarded")
    if mode not in {"guarded", "retained"}:
        raise ValueError("CAMPUS_MODEL_MODE must be guarded or retained")
    policy = MultiAgentPolicy()
    gateway = GuardedGateway()
    admission = lambda _: False
    if mode == "retained":
        import httpx
        from scripts.run_public_rag import Gateway
        from scripts.multi_agent_live_resources import restore_paid
        # Reuse the existing exclusive writer lease and cumulative budget.
        # Never mint an authorization, reset a counter or substitute a fake.
        if not headroom(policy):
            raise RuntimeError("Existing model budget cannot admit a full run")
        for port in (18081, 18082):
            response = httpx.get(f"http://127.0.0.1:{port}/info", trust_env=False, timeout=5)
            response.raise_for_status()
        class RetainedGateway(Gateway):
            json_mode = True
            def __init__(self):
                import asyncio
                self.test_dispatch_lock = asyncio.Lock()
                super().__init__()
            def _restore_budget(self, snapshot, pending):
                return restore_paid(snapshot, pending)
            async def generate(self, request):
                async with self.test_dispatch_lock:
                    ceiling = os.environ.get("CAMPUS_E2E_PAID_CALL_CEILING")
                    if ceiling is not None and self.budget.snapshot()["calls"] >= int(ceiling):
                        raise ValueError("provider operation bound")
                    return await super().generate(request)
        gateway = RetainedGateway()
        admission = headroom

    initialize()
    def database(name):
        path = checked(STATE / (name + ".sqlite3"))
        if not path.is_file():
            raise FileNotFoundError(path)
        return path
    settings = Settings(_env_file=None, ENVIRONMENT="development", DEMO_MODE=True,
        OPENAI_API_KEY=None, GEMINI_API_KEY=None, DEEPSEEK_API_KEY=None,
        ACTOR_STATE_STORAGE_MODE="sqlite", ACTOR_STATE_SQLITE_PATH=database("actor"),
        CONSENT_STORAGE_MODE="sqlite", CONSENT_SQLITE_PATH=database("actor"))
    # Historical runs have no verified tenant binding. Keep their copied DB as
    # evidence; new runs use a separate explicitly bound store, never reassign it.
    runs = SQLiteAgentRunStore(checked(STATE / "coordination.sqlite3"), tenant=TENANT)
    memory = SQLiteAssistantMemory(database("memory"))
    tracking = SQLiteAssistantTracking(database("tracking"))
    corpus = load_public_hybrid_store(ROOT / "data/huce-public-20261013", tenant_id=TENANT,
        campus_id="HUCE", faq_directory=ROOT / "data/huce-faq-20261013")
    os.environ["CAMPUS247_IDEMPOTENCY_DB"] = str(checked(STATE / "idempotency.sqlite3"))
    native = create_app(runtime_settings=settings, synthetic_tenant_id=TENANT,
        retrieval_context_factory=RetrievalContextFactory(scope_resolver=ScopeResolver(),
            configured_tenant_id=TENANT, configured_campus_id="HUCE"),
        personal_memory_store=memory,
        conversation_repository=SQLiteConversationRepository(checked(STATE / "conversations.sqlite3"), tenant=TENANT),
        public_knowledge_store=corpus, citation_source_reader=corpus,
        llm_gateway=gateway, multi_agent_store=runs, multi_agent_policy=policy, multi_agent_admission=admission)
    app = create_unified_demo_app(database("business"), settings=settings,
        state_database=database("actor"), consent_mode="sqlite", coordination_store=runs,
        personal_memory_store=memory, personal_tracking_store=tracking, chat_application=native)
    # FastAPI includes routers lazily. Inspecting route.path misses included
    # branches; explicitly compose source/run readers ahead of the old proxy.
    from fastapi import APIRouter
    readers = APIRouter()
    readers.include_router(native.state.native_agent_run_router)
    readers.include_router(native.state.native_citation_router)
    count = len(app.router.routes)
    app.include_router(readers)
    branches = app.router.routes[count:]
    app.router.routes[count:] = []
    app.router.routes[0:0] = branches
    app.state.coordination_capabilities = native.state.coordination_capabilities
    app.state.owns_paid_ledger = mode == "retained"
    if mode == "retained":
        from contextlib import asynccontextmanager
        previous_lifespan = app.router.lifespan_context
        @asynccontextmanager
        async def lifespan(application):
            try:
                async with previous_lifespan(application):
                    yield
            finally:
                gateway.close()
        app.router.lifespan_context = lifespan

    @app.get("/health/entry")
    def entry():
        ceiling = os.environ.get("CAMPUS_E2E_PAID_CALL_CEILING")
        remaining = max(0, int(ceiling) - gateway.budget.snapshot()["calls"]) if mode == "retained" and ceiling else None
        return {"entry_port": 3115, "api": "same_origin", "storage": "durable_local_copy",
                "generation": "retained_live" if mode == "retained" else "not_enabled",
                "test_paid_calls_remaining": remaining,
                "test_ceiling_reached": remaining == 0,
                "budget": "accounting_only" if UNCAPPED_AUTHORIZATION.exists() else "existing_cumulative_caps_unchanged",
                "aggregate_paid_caps": "removed_by_user" if UNCAPPED_AUTHORIZATION.exists() else "retained",
                "generation_detail": "Existing exclusive gateway and BGE services" if mode == "retained"
                    else "Existing model services and budget must be connected before live generation."}
    return app


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(create_runtime_app(), host="127.0.0.1", port=8006, access_log=False)
