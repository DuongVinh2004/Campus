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
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts"), str(ROOT / "services/api/src"),
    str(ROOT / "services/worker/src"), str(ROOT / "packages/synthetic/src"),
    str(ROOT / ".tooling/knowledge-platform-20261023/site-packages")]
from campus247.infrastructure.knowledge.storage import FileKnowledgeStorage, ReadThroughKnowledgeStorage, checked_path
from knowledge_parser_runtime import resolve_parser_python

STATE = checked_path(ROOT / "infra/local/knowledge-platform-20261023", ROOT)
PGROOT = checked_path(ROOT / ".tooling/knowledge-postgres-20261023/pgsql", ROOT)
CLUSTER = checked_path(ROOT / ".tooling/knowledge-postgres-20261023/cluster", ROOT)
CONNECTION = checked_path(STATE / "local-connection.json", ROOT)
DB_NAME, DB_PORT, TENANT = "campus247_knowledge_local_20261023", 55437, "huce-local-public"


def shared_secret(name):
    """A secret every API process of this runtime shares (a random value per process could not be verified by the
    others): created once with exclusive create, then read by all. Lives in the runtime state directory."""
    path = checked_path(STATE / name, ROOT)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        for _ in range(100):  # another process is still writing it
            value = path.read_text(encoding="ascii").strip()
            if len(value) == 64:
                return value
            time.sleep(0.05)
        raise RuntimeError("shared secret file is incomplete")
    value = secrets.token_hex(32)
    with os.fdopen(descriptor, "w", encoding="ascii") as stream:
        stream.write(value)
    return value


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
        or value.get("status") != "passed" or value.get("revision") not in {"0020", "0021", "0022", "0023", "0024"}
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
    if revision not in {"0018", "0022", "0023", "0024"}:
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
        # Plain HTTP on loopback: no TLS, so no certificate store to load for every client.
        lambda: httpx.AsyncClient(base_url="http://127.0.0.1:18081", trust_env=False, follow_redirects=False, verify=False))
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


async def components(*, rehearsal=None, learning_rehearsal=None):
    import asyncpg
    from campus247.application.knowledge.platform import KnowledgePlatform
    from campus247.bootstrap.settings import Settings
    from campus247.domain.action.confirmation import ConfirmationTokenService
    from campus247.infrastructure.knowledge.repository import KnowledgeRepository
    from campus247.infrastructure.knowledge.runtime import KnowledgeReleaseRuntime
    value = (learning_rehearsal.connection() if learning_rehearsal else
             rehearsal_connection(rehearsal) if rehearsal else connection())
    pool = await asyncpg.create_pool(**value, min_size=1, max_size=5, command_timeout=15,
        init=learning_rehearsal.verify_connection if learning_rehearsal else None)
    async with pool.acquire() as conn:
        revision = await conn.fetchval("SELECT version_num FROM alembic_version")
        accepted_revisions = {"0025", "0026", "0027", "0028", "0029", "0030", "0031"} if learning_rehearsal else ({"0020", "0021", "0022", "0023", "0024"} if rehearsal else {"0017", "0018", "0022", "0023", "0024"})
        if revision not in accepted_revisions:
            raise ValueError("Apply additive platform migrations before running services")
        if rehearsal and revision != json.loads(Path(rehearsal).read_text(encoding="utf-8"))["revision"]:
            raise ValueError("Rehearsal schema differs from the explicit receipt")
        if await conn.fetchval("SELECT current_database()") != value["database"]:
            raise ValueError("Database identity mismatch")
    scoped_settings = ({"rag_engine": "v1", "parallel_classify": False, "AGENT_RUN_STORAGE_MODE": "disabled",
                        "AGENT_RUN_SQLITE_PATH": None, "CONVERSATION_STORAGE_MODE": "ephemeral",
                        "CONVERSATION_SQLITE_PATH": None, "CONFIRMATION_SIGNING_KEY": secrets.token_hex(32)}
                       if learning_rehearsal else {})
    settings = Settings(_env_file=None, ENVIRONMENT="development", DEMO_MODE=True,
        OPENAI_API_KEY=None, GEMINI_API_KEY=None, DEEPSEEK_API_KEY=None,
        DATABASE_URL=__import__("sqlalchemy").engine.URL.create("postgresql+asyncpg", username=value["user"],
            password=value["password"], host=value["host"], port=value["port"], database=value["database"]).render_as_string(hide_password=False),
        # Every API process of the runtime must verify the confirmation tokens any other minted, so the key is one
        # persistent random secret in the runtime state directory (the built-in default is a fixed public string).
        **{"CONFIRMATION_SIGNING_KEY": shared_secret("confirmation-signing.key"), **scoped_settings})
    repository = KnowledgeRepository(pool, TENANT)
    bundle = ({"artifacts": learning_rehearsal.directory / "artifacts"} if learning_rehearsal
              else rehearsal_bundle_paths(rehearsal))
    storage = (FileKnowledgeStorage(ROOT, bundle["artifacts"]) if bundle else
        ReadThroughKnowledgeStorage(ROOT, STATE / "rehearsals" / value["database"] / "artifacts", STATE / "artifacts") if rehearsal else FileKnowledgeStorage(ROOT, STATE / "artifacts"))
    platform = KnowledgePlatform(repository, storage, ConfirmationTokenService(settings.CONFIRMATION_SIGNING_KEY))
    # Several API processes: share the agent write-flow's signing key (derived for that purpose only) and its previews.
    from campus247.agent.tools.write_flow import configure_shared_state
    configure_shared_state(checked_path(STATE / "write-previews.sqlite3", ROOT), hashlib.sha256(
        b"write-flow:" + bytes.fromhex(settings.CONFIRMATION_SIGNING_KEY)).digest())
    platform.operational = True
    platform.runtime_environment = "rehearsal" if rehearsal or learning_rehearsal else "operational"
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
    parser_python = resolve_parser_python(ROOT)
    pool, _, platform, runtime = await components(rehearsal=rehearsal)
    worker = KnowledgeIngestionWorker(platform.repo, platform.storage, runtime.embedding, owner="worker-" + str(uuid4()),
        parser_python=parser_python, platform=platform,
        ocr_adapter=LocalOcrAdapter(platform.storage,node=NODE,package_root=NODE.parents[1] / "package.json"))
    try:
        await serve_worker(worker, rehearsal_connection(rehearsal)["database"] if rehearsal else DB_NAME,
            heartbeat_file, once=once)
    finally:
        await pool.close()


async def make_app(*, generation=False, frontend_port=None, rehearsal=None, learning_rehearsal=None, api_port=8015):
    learning_flag = os.environ.get("CAMPUS_LEARNING_ENABLED", "true").lower()
    if learning_flag not in {"true", "false"}:
        raise ValueError("CAMPUS_LEARNING_ENABLED must be true or false")
    if learning_rehearsal:
        from learning_campus_rehearsal import LearningCampusRehearsal
        if (rehearsal or generation or api_port == 8015 or frontend_port == 3015
                or os.environ.get("CAMPUS_LEARNING_AI_ENABLED", "false").lower() != "false"):
            raise ValueError("Learning rehearsal must be isolated from the retained runtime and provider")
        learning_rehearsal = LearningCampusRehearsal.load(learning_rehearsal, ROOT)
    if not learning_rehearsal and os.environ.get("CAMPUS247_RAG_ENGINE", "v1") == "v2":
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
    pool, settings, platform, runtime = await components(rehearsal=rehearsal, learning_rehearsal=learning_rehearsal)
    if learning_rehearsal:
        runtime.instance_id = f"knowledge-local-learning-rehearsal-{api_port}"
    elif settings.rag_engine == "v2":
        runtime.instance_id = f"knowledge-local-api-v2-{api_port}"
    platform.operational = True
    identity_root = learning_rehearsal.directory if learning_rehearsal else STATE
    owner_path = identity_root / ("owner/identity.json" if learning_rehearsal else "owner-identity.json")
    student_path = identity_root / ("student/identity.json" if learning_rehearsal else "student-identity.json")
    owner_adapter = LocalOwnerIdentityAdapter(checked_path(owner_path, ROOT), TENANT)
    owner_adapter.directory()  # Explicitly provisioned account required; no synthetic fallback.
    learning_service, learning_adapter = None, None
    learning_config_override = (str(identity_root / "learning/config.json") if learning_rehearsal
                                else os.environ.get("CAMPUS_LEARNING_CONFIG"))
    learning_config = Path(learning_config_override) if learning_config_override else ROOT / "infra/local/learning-materials-20261104-01/config.json"
    if learning_flag == "true" and (learning_config_override or learning_config.is_file()):
        from campus247.bootstrap.learning import load_local_learning
        verified_learning_database = await pool.fetchval("SELECT current_database()")
        verified_learning_revision = await pool.fetchval("SELECT version_num FROM alembic_version")
        learning_service, learning_adapter = load_local_learning(learning_config, workspace=ROOT, tenant_id=TENANT,
            postgres_pool=pool, verified_database_name=verified_learning_database, verified_schema_revision=verified_learning_revision)
    from campus247.infrastructure.identity.local_staff import LocalStaffIdentityAdapter
    staff_adapter = LocalStaffIdentityAdapter(checked_path(identity_root / "staff-identity.json", ROOT), TENANT)
    campus_adapter = LocalCampusIdentityAdapter(owner_adapter,
        LocalStudentIdentityAdapter(checked_path(student_path, ROOT), TENANT), learning=learning_adapter, staff=staff_adapter)
    if learning_service is not None:
        learning_service.directory = campus_adapter.learning_directory
    from campus247.infrastructure.repositories.sqlite_actor_state import SQLiteActorStateStore
    bundle = ({name: identity_root / name for name in ("actor-state.sqlite3", "action-idempotency.sqlite3", "conversations.sqlite3")}
              if learning_rehearsal else rehearsal_bundle_paths(rehearsal))
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
        if os.environ.get("CAMPUS247_GATEWAY_URL"):
            # Several API processes share one paid gateway: it runs as a sidecar that owns the credential, the ledger
            # lease, the budget and the spend cap. This process can reach the provider only through it.
            from campus247.infrastructure.llm.remote_gateway import RemoteGateway, read_token
            gateway = RemoteGateway(os.environ["CAMPUS247_GATEWAY_URL"], read_token(os.environ["CAMPUS247_GATEWAY_TOKEN_FILE"]))
        else:
            from run_public_rag import Gateway
            from multi_agent_live_resources import restore_paid
            class RetainedGateway(Gateway):
                json_mode = True
                def _restore_budget(self, snapshot, pending):
                    return restore_paid(snapshot, pending)
            gateway = RetainedGateway()  # Retains paid accounting, lease and egress controls.
        verifier = SemanticClaimVerifier(gateway)
    learning_ai_flag = os.environ.get("CAMPUS_LEARNING_AI_ENABLED", "false").lower()
    if learning_ai_flag not in {"true", "false"}:
        raise ValueError("CAMPUS_LEARNING_AI_ENABLED must be true or false")
    if learning_ai_flag == "true":
        if not generation:
            raise ValueError("Learning AI requires the explicitly enabled guarded generation runtime")
        from campus247.bootstrap.learning import configure_learning_ai
        configure_learning_ai(learning_service, gateway, enabled=True)
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
    # Durable campus operations (rooms, timetable, notifications, tickets, staff queue, admin overview).
    # The older in-memory demo routes for the same paths are removed so nothing writes to a volatile store.
    from campus247.application.campus_ops.service import CampusOpsService
    from campus247.infrastructure.repositories.sqlite_campus_ops import CampusOpsStore
    from campus247.presentation.campus_ops import create_campus_ops_router, register_ops_errors
    ops_service = CampusOpsService(CampusOpsStore(checked_path(identity_root / "campus-ops.sqlite3", ROOT)))
    # FastAPI nests included routers, so route.path cannot be filtered; put the durable routes first so they
    # win, and the boundary middleware below rejects the volatile demo paths that remain behind them.
    ops_count = len(app.router.routes)
    app.include_router(create_campus_ops_router(ops_service))
    ops_branches = app.router.routes[ops_count:]
    app.router.routes[ops_count:] = []
    app.router.routes[0:0] = ops_branches
    register_ops_errors(app)
    app.state.campus_ops = ops_service
    from campus247.presentation.learning import create_learning_router
    app.include_router(create_learning_router(learning_service))
    app.state.learning_service = learning_service

    # Operations page: numbers from every API worker (snapshot files), probes of the services around the API.
    from campus247.observability.ops_status import OpsConfig
    from campus247.infrastructure.llm.remote_gateway import read_token
    from campus247.presentation.admin_ops import create_admin_ops_router
    gateway_url = os.environ.get("CAMPUS247_GATEWAY_URL")
    gateway_token_file = os.environ.get("CAMPUS247_GATEWAY_TOKEN_FILE")
    backup_dir = os.environ.get("CAMPUS247_BACKUP_DIR")
    ops_config = OpsConfig(
        metrics_dir=STATE / "ops-metrics", data_dir=ROOT, backup_dir=Path(backup_dir) if backup_dir else None,
        quality_dir=ROOT / "evals/results/nightly",
        model_urls={"embedding": "http://127.0.0.1:18081/info", "reranker": "http://127.0.0.1:18082/info"},
        gateway_url=gateway_url,
        gateway_token=read_token(gateway_token_file) if gateway_url and gateway_token_file else None,
        background=lambda: {"leader": bool(getattr(getattr(app.state, "background_leader", None), "is_leader", False)),
                            "learning_worker": getattr(app.state, "learning_worker_status", "disabled")})
    app.include_router(create_admin_ops_router(ops_config))

    # Freshness of the sources in the current release, for knowledge managers (reads the release pointer, writes only its own file).
    from campus247.application.knowledge.freshness_service import FreshnessService, SourceReviewStore
    from campus247.presentation.knowledge_freshness import create_freshness_router
    freshness_service = FreshnessService(pool, SourceReviewStore(STATE / "source-reviews.sqlite3"), tenant=TENANT)
    app.include_router(create_freshness_router(freshness_service))

    # Which sources are behind answers people mark "not helpful": counts per source only, no question and no person.
    from campus247.application.knowledge.answer_quality import AnswerQualityStore, attach_quality_recording
    from campus247.presentation.knowledge_quality import create_quality_router
    quality_store = AnswerQualityStore(STATE / "answer-quality.sqlite3")
    attach_quality_recording(app.state.feedback_service, quality_store)
    app.include_router(create_quality_router(quality_store, freshness_service))

    # Sign in with the university account: only when the owner supplied a provider configuration (CAMPUS247_OIDC_CONFIG).
    if os.environ.get("CAMPUS247_OIDC_CONFIG"):
        import httpx as oidc_httpx
        from campus247.infrastructure.identity.oidc import OidcClient, OidcConfig
        from campus247.infrastructure.identity.oidc_accounts import OidcAccountStore, validate_config as validate_oidc_config
        from campus247.infrastructure.identity.oidc_session import OidcSessionAdapter, load_or_create_key
        from campus247.presentation.oidc import create_oidc_router
        oidc_config = OidcConfig.from_dict(json.loads(Path(os.environ["CAMPUS247_OIDC_CONFIG"]).read_text(encoding="utf-8")),
                                           secret_reader=lambda name: Path(name).read_text(encoding="utf-8").strip())
        validate_oidc_config(oidc_config)  # refuses a configuration that would let the provider grant an administrator role
        oidc_sessions = OidcSessionAdapter(load_or_create_key(STATE / "oidc-session.key"), TENANT)
        campus_adapter.oidc = oidc_sessions
        app.include_router(create_oidc_router(oidc_config, OidcClient(oidc_config, oidc_httpx.AsyncClient(trust_env=False)),
                                              OidcAccountStore(STATE / "oidc.sqlite3"), oidc_sessions))

    @app.get("/health/entry", include_in_schema=False)
    def entry_health():
        return {"entry_url": f"http://127.0.0.1:{api_port}", "api_same_origin": True,
            "authentication": "password_local", "knowledge": "current_release",
            "student_services": "owned_local_preparations", "university_connected": False,
            "synthetic_rehearsal": bool(learning_rehearsal),
            "shared_history": True, "shared_actor_storage": True,
            "learning": {"configured": learning_service is not None,
                "worker": getattr(app.state, "learning_worker_status", "starting" if learning_service else "disabled"),
                "last_success_at": getattr(app.state, "learning_worker_last_success", None)}}

    @asynccontextmanager
    async def owned_lifespan(application):
        leader_task = None
        async def learning_worker():
            import logging
            while True:
                try:
                    await learning_service.tick()
                    application.state.learning_worker_status = "ready"
                    application.state.learning_worker_last_success = datetime.now(UTC).isoformat()
                except asyncio.CancelledError:
                    raise
                except Exception as error:
                    application.state.learning_worker_status = "unavailable"
                    logging.getLogger("campus247.learning").warning("Learning worker unavailable", extra={"error_type": type(error).__name__})
                await asyncio.sleep(5)
        try:
            async with original_lifespan(application):
                # Only explicitly configured schedules with a still-valid signed
                # session can run. No token minting or authority on startup.
                # With several API processes exactly one (the holder of a Postgres advisory lock) runs the
                # background jobs; the others stand by and take over if the leader's session is lost.
                from campus247.infrastructure.leader import BackgroundLeader
                leader = application.state.background_leader = BackgroundLeader(lambda: pool)

                from campus247.application.campus_ops.reminder_job import run_reminders

                def student_subjects():
                    # student code -> subject id for the local student account (the only account with a schedule here)
                    student = campus_adapter.student.directory()
                    return {student["student_code"]: student["subject_id"]}.get

                async def start_jobs():
                    jobs = [asyncio.create_task(platform.schedules.serve())]
                    jobs.append(asyncio.create_task(run_reminders(ops_service.store, student_subjects)))
                    from campus247.application.knowledge.freshness_reminders import run_freshness_reminders
                    jobs.append(asyncio.create_task(run_freshness_reminders(
                        freshness_service, ops_service.store, lambda: [owner_adapter.directory()["owner_id"]])))
                    from campus247.observability.alert_job import run_alerts
                    from campus247.observability.alert_notifiers import build_notifier
                    from campus247.observability.alerts import AlertManager
                    from campus247.observability.ops_status import ProbeCache, build_status
                    import httpx
                    alert_client, alert_cache = httpx.AsyncClient(trust_env=False), ProbeCache()
                    alert_manager = AlertManager(STATE / "ops-alerts", build_notifier(os.environ))
                    jobs.append(asyncio.create_task(run_alerts(
                        alert_manager, lambda: build_status(ops_config, client=alert_client, cache=alert_cache))))
                    if learning_service is not None:
                        jobs.append(asyncio.create_task(learning_worker()))
                        if learning_service.accessible_text_pipeline is not None:
                            jobs.append(asyncio.create_task(learning_service.serve_accessible_text()))
                    return jobs

                def standby():
                    if learning_service is not None:
                        application.state.learning_worker_status = "standby"

                leader_task = asyncio.create_task(leader.run(start_jobs, standby))
                from campus247.infrastructure.loop_watchdog import LoopWatchdog
                watchdog = LoopWatchdog(asyncio.get_running_loop()).start()
                from campus247.observability.ops_metrics import OPS, run_writer
                from campus247.rag_v2.observability.vector_stats import VECTOR_STATS
                ops_writer = asyncio.create_task(run_writer(OPS, ops_config.metrics_dir, retrieval=VECTOR_STATS.snapshot))
                try:
                    yield
                finally:
                    watchdog.stop()
                    ops_writer.cancel()
        finally:
            if leader_task is not None:
                leader_task.cancel()  # its own cleanup cancels the jobs and releases the lock
                try:
                    await leader_task
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
        import re as _re
        if _re.fullmatch(r"/v1/tickets/preview|/v1/tickets/[^/]+/confirm|/v1/handovers(/.*)?|/v1/staff/handovers", path):
            return JSONResponse({"detail":"Chức năng này chưa kết nối dữ liệu vận hành."}, status_code=404)
        if path.startswith("/v1/") and not (path.startswith(("/v1/knowledge/", "/v1/conversations", "/v1/privacy/", "/v1/assistant/", "/v1/student-preparations", "/v1/learning/",
                "/v1/rooms", "/v1/tickets", "/v1/students/me/schedule", "/v1/staff/tickets", "/v1/notifications", "/v1/admin/overview"))
                or path in {"/v1/users/me", "/v1/auth/logout"}):
            return JSONResponse({"detail":"Chức năng này chưa kết nối dữ liệu vận hành."}, status_code=404)
        if path in {"/v1/auth/demo-session", "/v1/knowledge/platform/local-session"}:
            return JSONResponse({"detail":"Đăng nhập thử không được dùng trong phiên vận hành."}, status_code=404)
        response = await call_next(request)
        if path.startswith("/v1/student-preparations"):
            response.headers["Cache-Control"] = "no-store"
        return response

    if frontend_port is not None:
        from knowledge_frontend_proxy import proxy_frontend
        @app.get("/{page_path:path}", include_in_schema=False)
        async def frontend(page_path: str, request: Request):
            if page_path in {"", "knowledge"}:
                from starlette.responses import RedirectResponse
                return RedirectResponse("/chat" if not page_path else "/knowledge/sources")
            if (not (page_path in {"", "chat", "login", "knowledge/sources", "knowledge", "services", "tickets", "schedule", "rooms", "privacy", "staff", "notifications", "admin"}
                     or page_path == "learning" or page_path.startswith(("learning/", "_next/", "images/", "fonts/"))) or ".." in page_path or "\\" in page_path):
                raise HTTPException(404)
            return await proxy_frontend(page_path, request, frontend_port)
    return app


def _log_config():
    from copy import deepcopy

    import uvicorn
    logs = deepcopy(uvicorn.config.LOGGING_CONFIG)
    logs["loggers"]["campus247.learning.metrics"] = {"handlers": ["default"], "level": "INFO", "propagate": False}
    return logs


async def serve(port, generation=False, frontend_port=None, *, rehearsal=None, learning_rehearsal=None):
    import uvicorn
    app = await make_app(generation=generation, frontend_port=frontend_port, rehearsal=rehearsal,
        learning_rehearsal=learning_rehearsal, api_port=port)
    await uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, access_log=False, log_config=_log_config())).serve()


class DeferredApp:
    """ASGI app that builds the real application inside the worker's own event loop at lifespan startup.

    make_app is a coroutine (it opens the database pool), but uvicorn starts several workers from an import string and a
    synchronous factory. The first ASGI scope of a worker is its lifespan, so the real app is built there and then
    handles every scope, including that lifespan, exactly as when served by a single process.
    """

    def __init__(self, build):
        self._build, self._app = build, None

    async def __call__(self, scope, receive, send):
        if self._app is None:
            if scope["type"] != "lifespan":
                raise RuntimeError("application not started")
            try:
                self._app = await self._build()
            except BaseException:
                # Without this the cause stays hidden (uvicorn reports only "lifespan unsupported" in its default mode).
                import logging
                logging.getLogger("campus247.worker").exception("application failed to start")
                raise
        await self._app(scope, receive, send)


def _serialize_accepts_between_workers():
    """Windows only. Worker processes share one listening socket whose operating-system mode is blocking, and asyncio keeps
    calling accept() until it is told "would block". The worker that lost the race for a connection (or asked for a second
    one) therefore sat inside accept() with its whole event loop parked until the next client connected: measured stalls of
    5 to 8 s, enough for a turn on that worker to run into its 30 s budget. Here the workers take turns (an exclusive lock
    file), accept only when the socket is readable and only one connection per call, so accept() can never wait."""
    if os.name != "nt":
        return
    import asyncio.selector_events as selector_events
    import msvcrt
    import select
    original = selector_events.BaseSelectorEventLoop._accept_connection
    if getattr(original, "_campus247_serialized", False):
        return
    descriptor = os.open(str(STATE / "api-accept.lock"), os.O_RDWR | os.O_CREAT)

    class OneConnection:
        """The listening socket, but a second accept() in the same call reports "would block"."""
        def __init__(self, sock):
            self._sock, self._used = sock, False

        def __getattr__(self, name):
            return getattr(self._sock, name)

        def accept(self):
            if self._used:
                raise BlockingIOError
            self._used = True
            return self._sock.accept()

    def accept_connection(self, protocol_factory, sock, *args, **kwargs):
        try:
            msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
        except OSError:
            return None          # another worker is accepting right now; the loop asks again at its next turn
        try:
            if select.select([sock], [], [], 0)[0]:
                return original(self, protocol_factory, OneConnection(sock), *args, **kwargs)
        finally:
            try:
                msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
        return None
    accept_connection._campus247_serialized = True
    selector_events.BaseSelectorEventLoop._accept_connection = accept_connection


def worker_app():
    """Import-string factory for `uvicorn ... --workers N`; settings arrive as JSON in the environment."""
    _serialize_accepts_between_workers()
    config = json.loads(os.environ["CAMPUS247_SERVE_CONFIG"])
    return DeferredApp(lambda: make_app(**config))


def serve_workers(port, workers, generation=False, frontend_port=None):
    """Several API processes on one port. Not for rehearsals (they run a single process)."""
    import uvicorn
    os.environ["CAMPUS247_SERVE_CONFIG"] = json.dumps({"generation": generation, "frontend_port": frontend_port, "api_port": port})
    # lifespan="on": a worker whose application cannot start exits (the supervisor restarts it) instead of serving errors.
    uvicorn.run("knowledge_platform:worker_app", factory=True, host="127.0.0.1", port=port, workers=workers,
                access_log=False, log_config=_log_config(), lifespan="on")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["inventory", "bootstrap-local", "migrate", "worker", "worker-once", "serve"])
    parser.add_argument("--port", type=int, default=8015)
    parser.add_argument("--workers", type=int, default=1, help="API processes sharing the port (serve only)")
    parser.add_argument("--frontend-port", type=int)
    parser.add_argument("--generation", action="store_true", help="Use the existing paid gateway only if its retained guards accept")
    parser.add_argument("--rehearsal", help="Exact successful new local test DB manifest; serving DB remains unchanged")
    parser.add_argument("--learning-rehearsal", help="Exact isolated Campus learning bundle; never uses the retained database or provider")
    parser.add_argument("--worker-heartbeat", help="Exact new worker pulse log within a retained runtime resume directory")
    parser.add_argument("--revision", choices=("0018", "0022", "0023", "0024"), default="0018", help="Explicit additive local migrate target; default is unchanged")
    args = parser.parse_args()
    if args.learning_rehearsal and args.command != "serve":
        parser.error("--learning-rehearsal is only valid with serve")
    if args.command == "inventory":
        inventory()
    elif args.command == "bootstrap-local":
        asyncio.run(bootstrap_local())
    elif args.command == "migrate":
        migrate(args.revision)
    elif args.command in {"worker", "worker-once"}:
        asyncio.run(work(args.command == "worker-once", rehearsal=args.rehearsal, heartbeat_file=args.worker_heartbeat))
    elif args.workers > 1:
        if args.rehearsal or args.learning_rehearsal:
            parser.error("--workers above 1 is only for the retained runtime, not rehearsals")
        serve_workers(args.port, args.workers, args.generation, args.frontend_port)
    else:
        asyncio.run(serve(args.port, args.generation, args.frontend_port, rehearsal=args.rehearsal,
            learning_rehearsal=args.learning_rehearsal))


if __name__ == "__main__":
    main()
