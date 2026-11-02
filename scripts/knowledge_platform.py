"""Explicit local entrypoint: inventory, fresh portable DB, API and durable worker.

Never selects a database from an application default. The local connection
record is created exclusively by bootstrap-local; no production target accepted.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import secrets
import socket
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts"), str(ROOT / "services/api/src"),
    str(ROOT / "services/worker/src"), str(ROOT / "packages/synthetic/src"),
    str(ROOT / ".tooling/knowledge-platform-20261023/site-packages")]
from campus247.infrastructure.knowledge.storage import FileKnowledgeStorage, ReadThroughKnowledgeStorage, checked_path

STATE = checked_path(ROOT / "infra/local/knowledge-platform-20261023", ROOT)
PGROOT = checked_path(ROOT / ".tooling/knowledge-postgres-20261023/pgsql", ROOT)
CLUSTER = checked_path(ROOT / ".tooling/knowledge-postgres-20261023/cluster", ROOT)
CONNECTION = checked_path(STATE / "local-connection.json", ROOT)
DB_NAME, DB_PORT, TENANT = "campus247_knowledge_local_20261023", 55437, "huce-local-public"


def retain(path, value):
    path = checked_path(path, ROOT)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, default=str)


def connection():
    value = json.loads(CONNECTION.read_text(encoding="utf-8"))
    if (value["host"], value["port"], value["database"], value["user"]) != (
        "127.0.0.1", DB_PORT, DB_NAME, "knowledge_owner"):
        raise ValueError("Only the task-owned loopback database is accepted")
    return value


def rehearsal_connection(manifest):
    """Explicit new test DB only; never replaces the retained/default connection."""
    import re
    manifest = checked_path(Path(manifest).absolute(), ROOT)
    value = json.loads(manifest.read_text(encoding="utf-8"))
    if (manifest.parent != ROOT / "infra/local/knowledge-automation-20261026"
        or value.get("status") != "passed" or value.get("revision") not in {"0020", "0021", "0022"}
        or not re.fullmatch(r"campus247_automation_20261026_[0-9a-f]{12}", value.get("database", ""))
        or value.get("host") != "127.0.0.1" or value.get("port") != DB_PORT):
        raise ValueError("Only an exact successful local rehearsal database manifest is accepted")
    return connection() | {"database": value["database"]}


def rehearsal_bundle_paths(manifest):
    """A complete explicit bundle never falls back to current actor/artifact data."""
    if not manifest:
        return None
    import re
    manifest = checked_path(Path(manifest).absolute(), ROOT)
    value = json.loads(manifest.read_text(encoding="utf-8"))
    if "restored_sqlite" not in value and "restored_artifact_store" not in value:
        return None
    rehearsal_connection(manifest)
    folder = checked_path(Path(value["backup_directory"]), ROOT)
    if (folder.parent != ROOT / "infra/local/knowledge-automation-20261026"
        or not re.fullmatch(r"restore-bundle-\d{8}T\d{12}", folder.name)
        or value.get("cross_store_capture_verified") is not True
        or value.get("restored_operational_artifacts_hash_checked") is not True
        or value.get("artifact_scope_tenant") != TENANT):
        raise ValueError("Only a verified complete scoped restore bundle is accepted")
    artifact_root = checked_path(Path(value["restored_artifact_store"]), ROOT)
    if artifact_root != folder / "artifact-restored" or not artifact_root.is_dir():
        raise ValueError("Restored artifact root is missing or outside the exact bundle")
    names = ("actor-state.sqlite3", "action-idempotency.sqlite3", "conversations.sqlite3")
    if set(value["restored_sqlite"]) != set(names):
        raise ValueError("All restored SQLite stores must be explicitly bound")
    paths = {}
    for name in names:
        path = checked_path(Path(value["restored_sqlite"][name]), ROOT)
        if path != folder / ("restored-"+name) or not path.is_file():
            raise ValueError("Restored SQLite file is missing or outside the exact bundle")
        paths[name] = path
    return {"artifacts":artifact_root, **paths}


def inventory():
    rows = []
    for directory in ("huce-public-20261013", "huce-faq-20261013", "huce-document-pipeline", "huce-discovery-20261020"):
        base = checked_path(ROOT / "data" / directory, ROOT)
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            checked_path(path, ROOT)
            if path.is_file():
                checksum = hashlib.sha256()
                with path.open("rb") as stream:
                    while block := stream.read(1024*1024):
                        checksum.update(block)
                rows.append({"path": str(path.relative_to(ROOT)), "sha256": checksum.hexdigest(), "bytes": path.stat().st_size})
    ports = {}
    for port in (5432, 5433, DB_PORT, 8000, 8001, 8015, 3000, 3001, 3015, 18081, 18082):
        with socket.socket() as client:
            client.settimeout(.3)
            ports[port] = client.connect_ex(("127.0.0.1", port)) == 0
    from campus247_worker.knowledge import available_memory
    report = {"at": datetime.now(UTC).isoformat(), "workspace": str(ROOT), "python": sys.version,
        "ports": ports, "available_memory_bytes": available_memory(), "files": rows,
        "input_file_count": len(rows), "input_byte_count": sum(r["bytes"] for r in rows),
        "legacy_binding": "sources UI -> synthetic service catalog; advanced chat -> file PublicHybridKnowledgeStore",
        "target_binding": f"sources UI -> platform API -> {DB_NAME} PostgreSQL releases -> shared BGE -> existing chat graph",
        "git_status": subprocess.run(["git", "status", "--short"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8").stdout,
        "model_smoke": "not measured by inventory", "active_citation_baseline": "no legacy API listener at initial inspection"}
    target = STATE / ("inventory-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f") + ".json")
    retain(target, report)
    print(json.dumps({"inventory": str(target), "files": len(rows), "bytes": report["input_byte_count"], "ports": ports}))


async def bootstrap_local():
    if CONNECTION.exists() or CLUSTER.exists():
        raise ValueError("Fresh database targets required; retained state is never reinitialized")
    if not (PGROOT / "bin/initdb.exe").is_file():
        raise ValueError("Run the optional portable acquisition/build first")
    # Install exactly three newly built extension files, never a wildcard install/overwrite.
    extension = checked_path(ROOT / ".tooling/knowledge-postgres-20261023/pgvector-0.8.7", ROOT)
    for source, destination in (
        (extension / "vector.dll", PGROOT / "lib/vector.dll"),
        (extension / "vector.control", PGROOT / "share/extension/vector.control"),
        (extension / "sql/vector--0.8.7.sql", PGROOT / "share/extension/vector--0.8.7.sql"),
    ):
        source, destination = checked_path(source, ROOT), checked_path(destination, ROOT)
        content = source.read_bytes()
        with destination.open("xb") as stream:
            stream.write(content)
    STATE.mkdir(parents=True, exist_ok=True)
    password = secrets.token_urlsafe(36)
    password_file = checked_path(STATE / "bootstrap-password.txt", ROOT)
    with password_file.open("x", encoding="utf-8") as stream:
        stream.write(password + "\n")
    subprocess.run([str(PGROOT / "bin/initdb.exe"), "-D", str(CLUSTER), "--no-clean", "--encoding=UTF8",
        "--locale=C", "--username=knowledge_owner", "--auth=scram-sha-256", "--pwfile=" + str(password_file)], cwd=ROOT, check=True)
    with socket.socket() as client:
        if client.connect_ex(("127.0.0.1", DB_PORT)) == 0:
            raise ValueError("Target port already occupied; existing listener preserved")
    subprocess.run([str(PGROOT / "bin/pg_ctl.exe"), "-D", str(CLUSTER), "-l", str(STATE / "postgres-first-start.log"),
        "-o", f"-h 127.0.0.1 -p {DB_PORT} -c shared_buffers=128MB -c max_connections=20 -c log_min_error_statement=panic", "start"], cwd=ROOT, check=True)
    import asyncpg
    parameters = {"host": "127.0.0.1", "port": DB_PORT, "user": "knowledge_owner", "password": password}
    conn = await asyncpg.connect(**parameters, database="postgres")
    try:
        if await conn.fetchval("SELECT EXISTS(SELECT 1 FROM pg_database WHERE datname=$1)", DB_NAME):
            raise ValueError("Database name already exists; no existing data will be changed")
        await conn.execute('CREATE DATABASE "campus247_knowledge_local_20261023"')
    finally:
        await conn.close()
    parameters["database"] = DB_NAME
    conn = await asyncpg.connect(**parameters)
    try:
        await conn.execute("CREATE EXTENSION vector")
        await conn.execute("CREATE EXTENSION btree_gist")
    finally:
        await conn.close()
    retain(CONNECTION, parameters)
    print(json.dumps({"database_created": DB_NAME, "port": DB_PORT, "cluster": str(CLUSTER), "credentials_printed": False}))


def migrate(revision="0018"):
    if revision not in {"0018", "0022"}:
        raise ValueError("Explicit reviewed local migration revision required")
    value = connection()
    from alembic import command
    from alembic.config import Config
    from sqlalchemy.engine import URL
    url = URL.create("postgresql+asyncpg", username=value["user"], password=value["password"],
                     host=value["host"], port=value["port"], database=value["database"])
    config = Config(str(ROOT / "services/api/alembic.ini"))
    config.set_main_option("sqlalchemy.url", url.render_as_string(hide_password=False).replace("%", "%%"))
    command.upgrade(config, revision)
    if revision == "0018":
        asyncio.run(backfill_known_inputs())
    print(json.dumps({"migration": revision, "database": DB_NAME, "destructive": False}))


async def backfill_known_inputs():
    """Add metadata only for this task's known normalized-text processor, never infer legacy inputs."""
    import asyncpg
    from campus247.application.knowledge.platform_models import PROCESSOR, EMBED_MODEL, EMBED_REVISION, digest
    from campus247.infrastructure.retrieval.public_knowledge import normalized
    conn = await asyncpg.connect(**connection())
    try:
        rows = await conn.fetch("""SELECT c.id,c.content_text FROM knowledge_chunk c
            JOIN knowledge_ingest_version x ON x.version_id=c.document_version_id
            WHERE x.processor_profile=$1 AND c.embedding_model_version=$2
            AND NOT EXISTS(SELECT 1 FROM knowledge_chunk_input i WHERE i.chunk_id=c.id)""", PROCESSOR, EMBED_MODEL+"@"+EMBED_REVISION)
        async with conn.transaction():
            for row in rows:
                value = normalized(row["content_text"])
                await conn.execute("""INSERT INTO knowledge_chunk_input
                    (chunk_id,index_text,input_sha256,processor_profile,provenance)
                    VALUES ($1,$2,$3,$4,'{"binding":"known processor input retained additively"}'::jsonb) ON CONFLICT DO NOTHING""",
                    row["id"],value,digest(value.encode()),PROCESSOR)
    finally:
        await conn.close()


def models():
    import httpx
    from campus247.application.knowledge.platform_models import EMBED_MODEL, EMBED_REVISION, RERANK_MODEL, RERANK_REVISION
    from campus247.infrastructure.retrieval.tei import TEIEmbeddingAdapter, TEIRerankerAdapter
    from campus247.ports.embedding import EmbeddingProfile
    from campus247.ports.reranker import RerankerProfile
    embedding = TEIEmbeddingAdapter(EmbeddingProfile(EMBED_MODEL, EMBED_REVISION, 1024, batch_limit=1, timeout_ms=30000),
        lambda: httpx.AsyncClient(base_url="http://127.0.0.1:18081", trust_env=False, follow_redirects=False))
    reranker = TEIRerankerAdapter(RerankerProfile(RERANK_MODEL, RERANK_REVISION, 6, 10000),
        lambda: httpx.AsyncClient(base_url="http://127.0.0.1:18082", trust_env=False, follow_redirects=False))
    return embedding, reranker


def model_budget():
    policy_path=checked_path(STATE / "model-accounting.json", ROOT)
    if policy_path.is_file():
        policy=json.loads(policy_path.read_text(encoding="utf-8"))
        namespace=checked_path(ROOT / policy["native_namespace"], ROOT)
        from model_usage_accounting import native_snapshot
        latest=native_snapshot(namespace, lambda p: checked_path(p, ROOT))
        if policy["aggregate_limits"]!="removed" or any(v is not None for v in latest["caps"].values()):
            raise ValueError("Accounting-only runtime binding mismatch")
        return {"remaining_inferences":None,"inference_cap":None,"status":"ACCOUNTING_ONLY",
            "usage_counts":latest["counts"]}
    namespace=checked_path(ROOT / "infra/local/rag-advanced-models-20261013-18", ROOT)
    reservations=sorted(namespace.glob("native-*-reservation.json"))
    if not reservations:
        return {"remaining_inferences":0,"status":"UNKNOWN"}
    latest=json.loads(checked_path(reservations[-1],ROOT).read_text(encoding="utf-8"))
    return {"remaining_inferences":max(0,latest["caps"]["inference"]-latest["counts"]["inference"]),
        "inference_cap":latest["caps"]["inference"],"status":"BOUNDED_EXISTING_LEDGER"}


async def components(*, rehearsal=None):
    import asyncpg
    from campus247.application.knowledge.platform import KnowledgePlatform
    from campus247.bootstrap.settings import Settings
    from campus247.domain.action.confirmation import ConfirmationTokenService
    from campus247.infrastructure.knowledge.repository import KnowledgeRepository
    from campus247.infrastructure.knowledge.runtime import KnowledgeReleaseRuntime
    value = rehearsal_connection(rehearsal) if rehearsal else connection()
    pool = await asyncpg.create_pool(**value, min_size=1, max_size=5, command_timeout=15)
    async with pool.acquire() as conn:
        revision = await conn.fetchval("SELECT version_num FROM alembic_version")
        if revision not in ({"0020", "0021", "0022"} if rehearsal else {"0017", "0018", "0022"}):
            raise ValueError("Apply additive platform migrations before running services")
        if rehearsal and revision != json.loads(Path(rehearsal).read_text(encoding="utf-8"))["revision"]:
            raise ValueError("Rehearsal schema differs from the explicit receipt")
        if await conn.fetchval("SELECT current_database()") != value["database"]:
            raise ValueError("Database identity mismatch")
    settings = Settings(_env_file=None, ENVIRONMENT="development", DEMO_MODE=True,
        OPENAI_API_KEY=None, GEMINI_API_KEY=None, DEEPSEEK_API_KEY=None,
        DATABASE_URL=__import__("sqlalchemy").engine.URL.create("postgresql+asyncpg", username=value["user"],
            password=value["password"], host=value["host"], port=value["port"], database=value["database"]).render_as_string(hide_password=False))
    repository = KnowledgeRepository(pool, TENANT)
    bundle = rehearsal_bundle_paths(rehearsal)
    storage = (FileKnowledgeStorage(ROOT, bundle["artifacts"]) if bundle else
        ReadThroughKnowledgeStorage(ROOT, STATE / "rehearsals" / value["database"] / "artifacts", STATE / "artifacts") if rehearsal else FileKnowledgeStorage(ROOT, STATE / "artifacts"))
    platform = KnowledgePlatform(repository, storage, ConfirmationTokenService(settings.CONFIRMATION_SIGNING_KEY))
    platform.operational = True
    platform.runtime_environment = "rehearsal" if rehearsal else "operational"
    platform.model_budget = model_budget
    embedding, reranker = models()
    runtime = KnowledgeReleaseRuntime(platform, embedding, reranker, instance_id="knowledge-local-api")
    return pool, settings, platform, runtime


async def work(once=False, *, rehearsal=None, heartbeat_file=None):
    from campus247_worker.knowledge import KnowledgeIngestionWorker
    from campus247_worker.knowledge_ocr import LocalOcrAdapter
    from advanced_rag_frontend import NODE
    from knowledge_worker_loop import serve_worker
    if heartbeat_file:
        heartbeat_file = checked_path(Path(heartbeat_file).absolute(), ROOT)
        if heartbeat_file.parent.parent != STATE or not heartbeat_file.parent.name.startswith("resume-") or heartbeat_file.name != "worker-health.jsonl":
            raise ValueError("Exact new retained runtime worker pulse path required")
    pool, _, platform, runtime = await components(rehearsal=rehearsal)
    parser_python = checked_path(ROOT / ".venv/Scripts/python.exe", ROOT)
    worker = KnowledgeIngestionWorker(platform.repo, platform.storage, runtime.embedding, owner="worker-" + str(uuid4()),
        parser_python=parser_python if parser_python.is_file() else None, platform=platform,
        ocr_adapter=LocalOcrAdapter(platform.storage,node=NODE,package_root=NODE.parents[1] / "package.json"))
    try:
        await serve_worker(worker, rehearsal_connection(rehearsal)["database"] if rehearsal else DB_NAME,
            heartbeat_file, once=once)
    finally:
        await pool.close()


async def make_app(*, generation=False, frontend_port=None, rehearsal=None, api_port=8015):
    if os.environ.get("CAMPUS247_RAG_ENGINE", "v1") == "v2":
        index_dir = Path(os.environ.get("CAMPUS247_RAG_V2_INDEX", "data/rag_v2_index"))
        index_dir = checked_path(index_dir if index_dir.is_absolute() else ROOT / index_dir, ROOT)
        if not index_dir.is_dir():
            raise ValueError("RAG_V2_INDEX_MISSING: configure CAMPUS247_RAG_V2_INDEX")
    from contextlib import asynccontextmanager
    from fastapi import HTTPException, Query, Request
    from pydantic import BaseModel
    from starlette.responses import JSONResponse, Response
    from campus247.bootstrap.app import create_app
    from campus247.application.retrieval.context import RetrievalContextFactory, ResolvedRetrievalScope
    from campus247.infrastructure.repositories.sqlite_conversations import SQLiteConversationRepository
    from campus247.ports.llm import LlmResponse, LlmResponseStatus
    from campus247.infrastructure.identity.local_owner import LocalOwnerIdentityAdapter
    from campus247.infrastructure.identity.local_student import LocalCampusIdentityAdapter, LocalStudentIdentityAdapter
    pool, settings, platform, runtime = await components(rehearsal=rehearsal)
    if settings.rag_engine == "v2":
        runtime.instance_id = f"knowledge-local-api-v2-{api_port}"
    platform.operational = True
    owner_adapter = LocalOwnerIdentityAdapter(checked_path(STATE / "owner-identity.json", ROOT), TENANT)
    owner_adapter.directory()  # Explicitly provisioned account required; no synthetic fallback.
    campus_adapter = LocalCampusIdentityAdapter(owner_adapter,
        LocalStudentIdentityAdapter(checked_path(STATE / "student-identity.json", ROOT), TENANT))
    from campus247.infrastructure.repositories.sqlite_actor_state import SQLiteActorStateStore
    bundle = rehearsal_bundle_paths(rehearsal)
    actor_database=bundle["actor-state.sqlite3"] if bundle else checked_path(STATE / "actor-state.sqlite3",ROOT)
    if not bundle:
        actor_marker=checked_path(STATE / "actor-storage-initialized.json",ROOT)
        if actor_marker.exists() and not actor_database.exists():
            raise RuntimeError("Durable actor storage missing; refuse an empty revocation/consent store")
        if not actor_marker.exists():
            # Exclusive creation also prevents adopting an unrelated pre-existing store.
            with actor_database.open("xb"):
                pass
        SQLiteActorStateStore(actor_database)
        if not actor_marker.exists():
            retain(actor_marker,{"database":"actor-state.sqlite3","scope":TENANT,"fallback":False})
    settings=type(settings)(_env_file=None,**(settings.model_dump() | {
        "ACTOR_STATE_STORAGE_MODE":"sqlite","ACTOR_STATE_SQLITE_PATH":actor_database,
        "CONSENT_STORAGE_MODE":"sqlite","CONSENT_SQLITE_PATH":actor_database}))

    class LocalScope:
        def resolve(self, identity):
            return ResolvedRetrievalScope(TENANT, "HUCE", frozenset(r.value for r in identity.roles),
                frozenset({identity.faculty_code or "FIT"}), frozenset({"PUBLIC"}))

    class UnavailableGateway:
        async def generate(self, request):
            return LlmResponse(LlmResponseStatus.FAILED, "disabled", "generation-not-enabled")

    gateway = UnavailableGateway()
    verifier = None
    if generation:
        import logging
        class GateDiagnostics(logging.Handler):
            def emit(self, record):
                value = getattr(record, "gate_diagnostic", None)
                if isinstance(value, dict):
                    print(json.dumps({"gate_diagnostic": value}), flush=True)
        gate_logger = logging.getLogger("campus247.evidence_gate")
        gate_logger.setLevel(logging.INFO)
        gate_logger.addHandler(GateDiagnostics())
        from campus247.application.retrieval.semantic_support import SemanticClaimVerifier
        from run_public_rag import Gateway
        from multi_agent_live_resources import restore_paid
        class RetainedGateway(Gateway):
            json_mode = True
            def _restore_budget(self, snapshot, pending):
                return restore_paid(snapshot, pending)
        gateway = RetainedGateway()  # Retains paid accounting, lease and egress controls.
        verifier = SemanticClaimVerifier(gateway)
    factory = RetrievalContextFactory(scope_resolver=LocalScope(), configured_tenant_id=TENANT, configured_campus_id="HUCE")
    os.environ["CAMPUS247_IDEMPOTENCY_DB"] = str(bundle["action-idempotency.sqlite3"] if bundle else checked_path(STATE / "action-idempotency.sqlite3", ROOT))
    conversations = SQLiteConversationRepository(bundle["conversations.sqlite3"] if bundle else checked_path(STATE / "conversations.sqlite3", ROOT))
    app = create_app(runtime_settings=settings, synthetic_tenant_id=TENANT, retrieval_context_factory=factory,
        knowledge_runtime=runtime, llm_gateway=gateway, claim_verifier=verifier,
        conversation_repository=conversations,
        identity_adapter_override=campus_adapter)
    app.router.routes[:] = [route for route in app.router.routes
        if getattr(route, "path", None) not in {"/docs", "/docs/oauth2-redirect", "/redoc", "/openapi.json"}]
    app.docs_url = app.redoc_url = app.openapi_url = None
    original_lifespan = app.router.lifespan_context
    from campus247.application.document_request.local_preparation import LocalPreparationService
    from campus247.presentation.local_preparation import create_local_preparation_router
    app.include_router(create_local_preparation_router(LocalPreparationService(app.state.actor_state_store, platform)))

    @app.get("/health/entry", include_in_schema=False)
    def entry_health():
        return {"entry_url": f"http://127.0.0.1:{api_port}", "api_same_origin": True,
            "authentication": "password_local", "knowledge": "current_release",
            "student_services": "owned_local_preparations", "university_connected": False,
            "shared_history": True, "shared_actor_storage": True}

    @asynccontextmanager
    async def owned_lifespan(application):
        scheduler_task = None
        try:
            async with original_lifespan(application):
                # Only explicitly configured schedules with a still-valid signed
                # session can run. No token minting or authority on startup.
                scheduler_task = asyncio.create_task(platform.schedules.serve())
                yield
        finally:
            if scheduler_task is not None:
                scheduler_task.cancel()
                try:
                    await scheduler_task
                except asyncio.CancelledError:
                    pass
            await pool.close()
            if hasattr(gateway, "close"):
                gateway.close()
    app.router.lifespan_context = owned_lifespan

    class LoginBody(BaseModel):
        username: str
        password: str
    # The app builds endpoint annotations at registration time under postponed annotations.
    globals().update(Request=Request, LoginBody=LoginBody)

    @app.post("/v1/knowledge/platform/session")
    async def local_session(body: LoginBody, request: Request):
        if request.client and request.client.host not in {"127.0.0.1", "::1", "testclient"}:
            raise HTTPException(403)
        if request.headers.get("origin", str(request.base_url).rstrip("/")).rstrip("/") != str(request.base_url).rstrip("/"):
            raise HTTPException(403)
        if len(body.username)>100 or len(body.password)>200:
            raise HTTPException(401)
        try:
            token = campus_adapter.authenticate(body.username, body.password)
        except ValueError:
            raise HTTPException(401, "Tài khoản hoặc mật khẩu không hợp lệ.") from None
        actor = campus_adapter.resolve_token(token)
        response = JSONResponse({"user_id": actor.subject_id, "roles": [r.value for r in actor.roles],
            "is_synthetic_identity": actor.is_synthetic, "identity_provider":"local", "university_identity_verified":False}, headers={"Cache-Control":"no-store"})
        response.set_cookie("auth_token", token, httponly=True, samesite="strict", max_age=3600)
        return response

    from campus247.application.assistance.state_storage import ConversationMetadata, StateScope
    from campus247.application.conversation.messages import SenderType
    from campus247.ports.identity import IdentityRole
    from campus247.presentation.identity import get_current_identity

    @app.get("/v1/assistant/conversations")
    async def conversation_list(request: Request, limit: int = Query(20, ge=1, le=100),
                                cursor: str | None = Query(None, max_length=200),
                                title: str = Query("", max_length=120)):
        actor = get_current_identity(request)
        if (actor.tenant_id != TENANT or not actor.is_active or not actor.session_id
            or actor.expires_at <= datetime.now(UTC) or actor.is_synthetic
            or set(actor.roles) != {IdentityRole.STUDENT}):
            raise HTTPException(403, "Cần phiên sinh viên local đang hoạt động đúng phạm vi.")
        # The shared catalog's scope accepts synthetic actors only. Project the
        # same read contract here without enabling its metadata write routes.
        scope = StateScope(TENANT, actor.subject_id)
        title = title.strip().casefold()
        binding = hashlib.sha256(json.dumps([TENANT, actor.subject_id, title, False]).encode()).hexdigest()[:24]
        rows = []
        for conversation in await conversations.list_owned_conversations(actor.subject_id):
            if conversation.owner_user_id != actor.subject_id or conversation.mode == "temporary":
                continue
            record = app.state.actor_state_store.get(scope, "conversation_metadata", conversation.id)
            value = ConversationMetadata.model_validate(record.payload) if record else ConversationMetadata(
                conversation_id=conversation.id, title="Hội thoại mới")
            if value.conversation_id != conversation.id:
                raise HTTPException(409, "Thông tin lịch sử không khớp hội thoại.")
            expired = conversation.retention_expires_at <= datetime.now(UTC)
            legacy_title = "Hội thoại " + conversation.created_at.strftime("%d/%m/%Y %H:%M")
            if not record or value.title == legacy_title:
                label = "Hội thoại mới"
                if not expired:
                    messages = await conversations.list_messages(conversation.id)
                    first = next((message for message in sorted(messages, key=lambda message: message.sequence_no)
                        if message.sender_type == SenderType.USER and message.conversation_id == conversation.id
                        and message.sender_user_id == actor.subject_id), None)
                    if first is not None and first.redacted_at is None:
                        label = "".join(char for char in " ".join(first.content_redacted.split()) if ord(char) >= 32)[:120] or label
                value = value.model_copy(update={"title": label})
            if value.archived or title not in value.title.casefold():
                continue
            rows.append({**value.model_dump(mode="json"), "id": conversation.id,
                "version": record.version if record else 0, "history_version": conversation.version,
                "created_at": conversation.created_at.isoformat(), "updated_at": conversation.updated_at.isoformat(),
                "status": str(conversation.status), "retention_expires_at": conversation.retention_expires_at.isoformat(),
                "retention_state": "expired" if expired else "available", "saved": True, "mode": conversation.mode,
                "can_continue": not expired and str(conversation.status) not in {"CLOSED", "ARCHIVED"}})
        rows.sort(key=lambda row: row["id"])
        offset = 0
        if cursor:
            try:
                identity, fingerprint = cursor.split(":")
                if fingerprint != binding:
                    raise ValueError()
                offset = next(i+1 for i, row in enumerate(rows) if row["id"] == identity)
            except (ValueError, StopIteration):
                raise HTTPException(422, "Mã trang không thuộc danh sách hiện tại.") from None
        items = rows[offset:offset+limit]
        more = offset+limit < len(rows)
        return JSONResponse({"items": items, "page": {"next_cursor": items[-1]["id"]+":"+binding if more else None,
            "has_more": more, "limit": limit}, "order": "stable_conversation_id",
            "retention_effect": "preserve_source_no_deletion"}, headers={"Cache-Control": "no-store"})

    @app.middleware("http")
    async def operational_boundary(request, call_next):
        path = request.url.path
        if path.startswith("/v1/") and not (path.startswith(("/v1/knowledge/", "/v1/conversations", "/v1/privacy/", "/v1/assistant/", "/v1/student-preparations"))
                or path in {"/v1/users/me", "/v1/auth/logout"}):
            return JSONResponse({"detail":"Chức năng này chưa kết nối dữ liệu vận hành."}, status_code=404)
        if path in {"/v1/auth/demo-session", "/v1/knowledge/platform/local-session"}:
            return JSONResponse({"detail":"Đăng nhập thử không được dùng trong phiên vận hành."}, status_code=404)
        response = await call_next(request)
        if path.startswith("/v1/student-preparations"):
            response.headers["Cache-Control"] = "no-store"
        return response

    if frontend_port is not None:
        import httpx
        from fastapi.responses import StreamingResponse
        @app.get("/{page_path:path}", include_in_schema=False)
        async def frontend(page_path: str, request: Request):
            if page_path in {"", "knowledge"}:
                from starlette.responses import RedirectResponse
                return RedirectResponse("/chat" if not page_path else "/knowledge/sources")
            if (not (page_path in {"", "chat", "login", "knowledge/sources", "knowledge", "services", "tickets", "schedule", "rooms", "privacy"}
                     or page_path.startswith(("_next/", "images/", "fonts/"))) or ".." in page_path or "\\" in page_path):
                raise HTTPException(404)
            async with httpx.AsyncClient(trust_env=False, timeout=15) as client:
                response = await client.get(f"http://127.0.0.1:{frontend_port}/" + page_path, params=request.query_params)
            if len(response.content) > 10*1024**2:
                raise HTTPException(502)
            return Response(response.content, status_code=response.status_code,
                            media_type=response.headers.get("content-type"))
    return app


async def serve(port, generation=False, frontend_port=None, *, rehearsal=None):
    import uvicorn
    app = await make_app(generation=generation, frontend_port=frontend_port, rehearsal=rehearsal, api_port=port)
    await uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, access_log=False)).serve()


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["inventory", "bootstrap-local", "migrate", "worker", "worker-once", "serve"])
    parser.add_argument("--port", type=int, default=8015)
    parser.add_argument("--frontend-port", type=int)
    parser.add_argument("--generation", action="store_true", help="Use the existing paid gateway only if its retained guards accept")
    parser.add_argument("--rehearsal", help="Exact successful new local test DB manifest; serving DB remains unchanged")
    parser.add_argument("--worker-heartbeat", help="Exact new worker pulse log within a retained runtime resume directory")
    parser.add_argument("--revision", choices=("0018", "0022"), default="0018", help="Explicit additive local migrate target; default is unchanged")
    args = parser.parse_args()
    if args.command == "inventory":
        inventory()
    elif args.command == "bootstrap-local":
        asyncio.run(bootstrap_local())
    elif args.command == "migrate":
        migrate(args.revision)
    elif args.command in {"worker", "worker-once"}:
        asyncio.run(work(args.command == "worker-once", rehearsal=args.rehearsal, heartbeat_file=args.worker_heartbeat))
    else:
        asyncio.run(serve(args.port, args.generation, args.frontend_port, rehearsal=args.rehearsal))


if __name__ == "__main__":
    main()
