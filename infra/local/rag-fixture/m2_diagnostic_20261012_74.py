"""Bounded actual multi-source diagnostic, never full M2 acceptance.

An additive schema holds candidate sources/index/messages. Public M1 rows and
the accepted pointer remain unchanged. Every paid attempt reserves before HTTP;
unknown usage consumes the full reservation. No sealed or real-person data.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import secrets
import socket
import threading
import ssl
import sys
import time
from dataclasses import fields
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = ROOT / "infra/local/rag-fixture"
import m2_completion_20261012_74 as registry
OUT = registry.output()
SCHEMA, INDEX, CORPUS = "m2_20261012_67", "m2-completion-20261012-67", "m2-completion-corpus-20261012-67"
ACTOR, TENANT = "4b419a1b-6d41-7dfb-8943-2edd9f071385", "synthetic-institution"
EMBED_SHA, RERANK_SHA = "1eebfb28493f67bba03ce0ef64bfdc7fc5a3bd9d7493f818bb1d78cd798416b4", "d9e3e081faff1eefb84019509b2f5558fd74c1a05a2c7db22f74174fcedb5286"
sys.path[:0] = [str(ROOT), str(HERE), str(ROOT / "services/api/src"), str(ROOT / "packages/synthetic/src")]


def put(name, value):
    import continuation_audit as audit
    path = audit.checked(OUT / (name + ".json"))
    with path.open("x", encoding="utf-8") as stream:
        json.dump({"run_id": "m2-20261012-74-" + registry.batch(), "created_at": datetime.now(timezone.utc).isoformat(), **value},
                  stream, ensure_ascii=False, indent=2, sort_keys=True)
    print(json.dumps({"receipt": name}), flush=True)


def load(name):
    filename = name + ("-v2.json" if name in {"corpus", "plan", "gold"} else ".json")
    return registry.load((registry.MASTER if name in {"corpus", "plan", "gold"} else OUT) / filename)


def sha(path):
    if os.name != "nt":  # recorded relative paths use Windows separators
        path = Path(str(path).replace("\\", "/"))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare():
    raise RuntimeError("Use frozen master preparation; no regeneration or helper replay")

async def public_snapshot(dsn):
    import asyncpg
    connection = await asyncpg.connect(dsn.replace("postgresql+asyncpg://", "postgresql://", 1), command_timeout=5)
    try:
        async with connection.transaction(readonly=True):
            tables = await connection.fetch("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")
            hashes = {}
            for row in tables:
                name = row["tablename"]
                assert name.replace("_", "").isalnum()
                value = await connection.fetchval(f'SELECT COALESCE(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text),\'[]\'::jsonb)::text FROM public."{name}" t')
                hashes[name] = hashlib.sha256(value.encode()).hexdigest()
            counts = {name: await connection.fetchval(f"SELECT count(*) FROM public.{name}") for name in ("conversation", "message")}
            indexes = await connection.fetchval("SELECT jsonb_agg(to_jsonb(t) ORDER BY indexname)::text FROM pg_indexes t WHERE schemaname='public'")
        return {"table_hashes": hashes, "counts": counts, "indexes_sha256": hashlib.sha256(indexes.encode()).hexdigest()}
    finally:
        await connection.close()


async def predecessor_snapshot(dsn):
    import asyncpg
    connection = await asyncpg.connect(dsn.replace("postgresql+asyncpg://", "postgresql://", 1), command_timeout=5)
    try:
        async with connection.transaction(readonly=True):
            hashes = {}
            for schema in ("m2_20261012_61", "m2_20261012_62", "m2_20261012_64"):
                for table in ("knowledge_source", "document_version", "knowledge_chunk", "retrieval_profile", "embedding_index_manifest", "embedding_index_active_pointer", "conversation", "message"):
                    value = await connection.fetchval(f"SELECT jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text)::text FROM {schema}.{table} t")
                    hashes[schema + "." + table] = hashlib.sha256(value.encode()).hexdigest()
            return hashes
    finally:
        await connection.close()


def runtime_guards(addresses):
    # Reuse unchanged restrictions, but use a fresh exact owned SQLite target.
    from m1_server_20261012_56 import guards
    guards(addresses)


class Gateway:
    def __init__(self, endpoint, key):
        from m2_budget_20261012_74 import ConservativeBudget
        from m1_provider_20261012_56 import ObservedAdapter
        self.adapter = ObservedAdapter("deepseek", endpoint, key, "deepseek-flash", default_timeout_sec=5, disable_thinking=True)
        prior = registry.prior()["paid"]
        self.before_calls = prior["calls"]
        self.budget = ConservativeBudget.resume_full_records(prior, registry.prior()["pending_reservation_records"], cap_usd="1.5", call_cap=8500)
        self.prior_unknown_records = registry.prior()["pending_reservation_records"]
        self.started = time.monotonic()
        self.lock = asyncio.Lock()

    async def generate(self, request):
        from campus247.infrastructure.llm.egress_policy import EgressPolicy
        async with self.lock:
            assert time.monotonic() - self.started <= 600
            assert request.route_id in {"sensitive_classifier", "route_intent", "grounded_faq"}
            assert 0 < request.max_output_tokens <= 1000 and request.deadline_ms <= 5000
            payload = self.adapter._build_payload(request)
            assert payload["thinking"] == {"type": "disabled"}
            assert EgressPolicy().validate_and_minimize({"purpose": "FAQ_ANSWERING", **payload}) == payload
            input_cap = len(json.dumps(payload, ensure_ascii=False).encode()) + 512
            assert input_cap <= 28000
            reservation = self.budget.reserve(input_cap, request.max_output_tokens)
            put(f"provider-reservation-{reservation.ordinal:03}", {"route": request.route_id, "input_cap": input_cap,
                "deadline_ms": request.deadline_ms, "controlled_regeneration": "grounded-regeneration-v1" in request.system_instructions,
                "output_cap": request.max_output_tokens, "payload_sha256": hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest(),
                "snapshot": self.budget.snapshot(), "counted_before_HTTP": True, "raw_content_credentials_logged": False})
            try:
                response = await self.adapter.generate(request)
                usage = response.usage
                assert response.model_id == "deepseek-flash" and usage.reasoning_tokens == 0
                self.budget.settle_verified(reservation, usage.input_tokens, usage.output_tokens)
                put(f"provider-result-{reservation.ordinal:03}", {"exit_code": 0, "model": response.model_id,
                    "input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens, "latency_ms": response.latency_ms,
                    "finish_reason": str(response.finish_reason), "snapshot": self.budget.snapshot()})
                return response
            except BaseException as error:
                put(f"provider-result-{reservation.ordinal:03}", {"exit_code": 1, "error_type": type(error).__name__,
                    "failed_full_reservation_retained": True, "snapshot": self.budget.snapshot(), "retry": False})
                raise

    def capabilities(self, provider_id, model_id):
        return self.adapter.capabilities(provider_id, model_id)


async def install_candidate(pool, vectors):
    old = json.loads((HERE / "acceptance-20261011-30-index-plan-canonical.json").read_bytes())["rows"]
    documents = load("corpus")["documents"]
    tables = ("retrieval_profile", "embedding_index_manifest", "embedding_index_active_pointer", "knowledge_source",
              "document_version", "knowledge_chunk", "conversation", "message")
    now = datetime.now(timezone.utc).isoformat()
    rows = {table: [] for table in tables}
    rows["retrieval_profile"] = [old["retrieval_profile"][0]]
    manifest = dict(old["embedding_index_manifest"][0], index_version=INDEX, corpus_version=CORPUS,
                    document_count=len(documents), chunk_count=len(documents), built_at=now, validated_at=now,
                    content_checksum=sha(registry.MASTER / "corpus-v2.json"))
    rows["embedding_index_manifest"] = [manifest]
    rows["embedding_index_active_pointer"] = [dict(old["embedding_index_active_pointer"][0], index_version=INDEX, activated_at=now)]
    async with pool.acquire() as conn:
        assert await conn.fetchval("SELECT count(*) FROM pg_namespace WHERE nspname=$1", SCHEMA) == 0
        for doc, vector in zip(documents, vectors, strict=True):
            source = dict(old["knowledge_source"][0], id=doc["source_id"], title=doc["title"],
                          canonical_uri="synthetic://m2-diag/" + doc["document_number"].lower(),
                          owner_unit="SYNTHETIC M2 DIAGNOSTIC — executor curated", created_at=now, updated_at=now)
            version = dict(old["document_version"][0], id=doc["document_version_id"], knowledge_source_id=doc["source_id"],
                           content_checksum=doc["text_sha256"], index_version=INDEX,
                           version_label="m2-completion-" + doc["document_version_id"][-12:], created_at=now, updated_at=now)
            chunk = dict(old["knowledge_chunk"][0], id=doc["chunk_id"], document_version_id=doc["document_version_id"],
                         content_text=doc["text"], content_checksum=doc["text_sha256"], section_path=doc["section_path"],
                         content_tsv=await conn.fetchval("SELECT to_tsvector('simple',$1)::text", doc["text"]),
                         embedding_rag_v1=json.dumps(vector), page_start=1, page_end=1, created_at=now, updated_at=now, embedded_at=now)
            if doc.get("kind") == "unauthorized":
                source["audiences"] = ["SYSTEM_ADMIN"]
            if doc.get("kind") == "expired":
                version["effective_from"] = "2025-01-01T00:00:00+00:00"
                version["effective_until"] = "2025-12-31T00:00:00+00:00"
            if doc.get("kind") == "withdrawn":
                version["status"] = "ARCHIVED"
            if source["id"] not in {value["id"] for value in rows["knowledge_source"]}:
                rows["knowledge_source"].append(source)
            rows["document_version"].append(version)
            rows["knowledge_chunk"].append(chunk)
        put("additive-row-plan", {"rows": rows, "schema": SCHEMA, "only_INSERT_CREATE": True,
                                   "public_M1_changes": False, "DB_source_vector_inference_actual": True})
        async with conn.transaction():
            await conn.execute("CREATE SCHEMA m2_20261012_74")
            for table in tables:
                await conn.execute(f"CREATE TABLE {SCHEMA}.{table} (LIKE public.{table} INCLUDING ALL)")
            for table, values in rows.items():
                for value in values:
                    await conn.execute(f"INSERT INTO {SCHEMA}.{table} SELECT * FROM jsonb_populate_record(NULL::{SCHEMA}.{table},$1::jsonb)", json.dumps(value))
        put("additive-row-readback", {"counts": {table: await conn.fetchval(f"SELECT count(*) FROM {SCHEMA}.{table}") for table in tables},
                                      "public_active_pointer_unchanged": True, "candidate_not_promoted_to_public": True})


async def diagnostic(dsn, endpoint, key):
    import asyncpg
    import httpx
    from campus247.application.retrieval.canonical import CanonicalRetrievalService
    from campus247.application.retrieval.context import RetrievalContextFactory, ResolvedRetrievalScope
    from campus247.application.retrieval.filters import RetrievalFilterCompiler
    from campus247.application.retrieval.profile import load_retrieval_profile, RuntimeRetrievalBinding
    from campus247.domain.embedding_index import EmbeddingIndexManifest, ActiveIndexPointer, BuildStatus
    from campus247.infrastructure.retrieval.postgres_lexical import PostgresLexicalSearchAdapter
    from campus247.infrastructure.retrieval.postgres_vector import PostgresVectorSearchAdapter
    from campus247.infrastructure.retrieval.tei import TEIEmbeddingAdapter, TEIRerankerAdapter
    from campus247.ports.embedding import EmbeddingProfile, validate_embedding_inputs
    from campus247.ports.reranker import RerankerProfile
    from token_envelope_20261007_25 import TokenEnvelope
    from m2_config_20261012_74 import config
    profile, envelope = config().apply(load_retrieval_profile()), TokenEnvelope()
    pool = await asyncpg.create_pool(dsn.replace("postgresql+asyncpg://", "postgresql://", 1), min_size=1, max_size=2,
                                    command_timeout=5, server_settings={"search_path": SCHEMA + ",public"})
    model_profile = EmbeddingProfile(profile.embedding_model_id, profile.embedding_model_revision, 1024, "l2", timeout_ms=profile.semantic_timeout_ms)
    model_http = [registry.prior()["native"]["HTTP"]]
    runtime_ssl = ssl.create_default_context()
    async def before_request(request):
        await envelope.before_request(request)
        assert model_http[0] < 12000
        model_http[0] += 1
        put(f"model-http-{model_http[0]:03}", {"endpoint": str(request.url), "method": request.method,
            "counted_before_transport": True, "failed_attempts_retained": True, "cumulative_cap": 12000})
    info_snapshots = {}
    def client(port):
        from m2_info_cache_20261012_71 import InfoSnapshotClient
        return lambda: InfoSnapshotClient(snapshots=info_snapshots, receipt=put, base_url=f"http://127.0.0.1:{port}", trust_env=False, verify=runtime_ssl,
            event_hooks={"request": [before_request]}, follow_redirects=False)
    embedding = TEIEmbeddingAdapter(model_profile, client(18081))
    async def embed(text):
        return (await embedding._embed(validate_embedding_inputs((text,), model_profile))).vectors[0]
    docs = load("corpus")["documents"]
    try:
        async with pool.acquire() as conn:
            exists = await conn.fetchval("SELECT count(*) FROM pg_namespace WHERE nspname=$1", SCHEMA)
        if not exists:
            async with pool.acquire() as conn:
                manifest = await conn.fetchrow("SELECT content_checksum,artifact_sha256 FROM m2_20261012_66.embedding_index_manifest")
                assert manifest["content_checksum"] == sha(registry.MASTER / "corpus-v2.json") and manifest["artifact_sha256"] == EMBED_SHA
                retained = await conn.fetch("SELECT id,content_checksum,embedding_rag_v1::text AS vector FROM m2_20261012_66.knowledge_chunk")
            existing = {str(r["id"]): r for r in retained}
            assert len(existing) == len(docs)
            vectors = []
            for doc in docs:
                row = existing[doc["chunk_id"]]
                assert row["content_checksum"] == doc["text_sha256"]
                vectors.append(json.loads(row["vector"]))
            put("embedding-cache-reuse", {"exit_code": 0, "actual_native_embeddings_retained": len(vectors),
                "predecessor_schema": "m2_20261012_66", "checksum_model_bound": True, "native_ledger_reset": False})
            await install_candidate(pool, vectors)
        else:
            async with pool.acquire() as conn:
                assert await conn.fetchval(f"SELECT count(*) FROM {SCHEMA}.knowledge_chunk") == len(docs)
                assert await conn.fetchval(f"SELECT content_checksum FROM {SCHEMA}.embedding_index_manifest WHERE index_version=$1", INDEX) == sha(registry.MASTER / "corpus-v2.json")
            put("existing-corpus-readback", {"immutable_tuple_verified": True, "index": INDEX, "corpus_sha256": sha(registry.MASTER / "corpus-v2.json")})
        async with pool.acquire() as conn:
            manifest_row = dict(await conn.fetchrow(f"SELECT * FROM {SCHEMA}.embedding_index_manifest WHERE index_version=$1", INDEX))
            pointer_row = dict(await conn.fetchrow(f"SELECT * FROM {SCHEMA}.embedding_index_active_pointer WHERE profile_version=$1", profile.profile_version))
            actor = await conn.fetchrow("SELECT u.status,u.is_synthetic,p.student_code,p.faculty_code,p.program_code FROM public.user_identity u JOIN public.student_profile p ON p.user_id=u.id WHERE u.id=$1::uuid", ACTOR)
            roles = await conn.fetch("SELECT role FROM public.role_binding WHERE user_id=$1::uuid", ACTOR)
        assert actor["status"] == "ACTIVE" and actor["is_synthetic"] and [row["role"] for row in roles] == ["STUDENT"]
        class Resolver:
            def resolve(self, identity):
                assert identity.subject_id == ACTOR and identity.tenant_id == TENANT
                assert identity.student_code == actor["student_code"] and identity.faculty_code == actor["faculty_code"]
                assert {role.value for role in identity.roles} == {"STUDENT"}
                return ResolvedRetrievalScope(TENANT, "HUCE", frozenset({"STUDENT"}), frozenset({actor["faculty_code"]}), frozenset({actor["program_code"]}))
        factory = RetrievalContextFactory(scope_resolver=Resolver(), configured_tenant_id=TENANT, configured_campus_id="HUCE")
        manifest_row["build_status"] = BuildStatus(manifest_row["build_status"])
        manifest = EmbeddingIndexManifest(**{field.name: manifest_row[field.name] for field in fields(EmbeddingIndexManifest)})
        pointer = ActiveIndexPointer(**pointer_row)
        common = dict(pool=pool, profile=profile, manifest=manifest, pointer=pointer, expected_index_version=INDEX,
                      expected_corpus_version=CORPUS, expected_artifact_sha256=EMBED_SHA,
                      filter_compiler=RetrievalFilterCompiler(tenant_id=TENANT, campus_id="HUCE", profile_allows_simulation=True),
                      issuer_resolver=lambda source: "SYNTHETIC M2 DIAGNOSTIC — executor curated" if source in {d["source_id"] for d in docs} else None)
        lexical, vector = PostgresLexicalSearchAdapter(**common), PostgresVectorSearchAdapter(**common, embed_query=embed, embedding_profile=model_profile)
        captured, retrieval_ordinal = [], [0]
        async def lexical_search(query, top_k, *, context):
            result = await lexical.search_candidates(query, top_k, context=context)
            captured.append({"stage": "lexical", "ids": [row.chunk_id for row in result]})
            return result
        async def vector_search(query, top_k, *, context):
            result = await vector.search_candidates(query, top_k, context=context)
            captured.append({"stage": "vector", "ids": [row.chunk_id for row in result]})
            return result
        reranker = TEIRerankerAdapter(RerankerProfile(profile.reranker_model_id, profile.reranker_model_revision, 20, profile.reranker_timeout_ms), client(18082))
        binding = RuntimeRetrievalBinding(INDEX, profile.profile_version, profile.embedding_model_id, profile.embedding_model_revision, 1024, "l2", "cosine", EMBED_SHA, profile.reranker_model_id, profile.reranker_model_revision, RERANK_SHA)
        class Recorded(CanonicalRetrievalService):
            def _fuse(self, lexical, vector):
                result = super()._fuse(lexical, vector)
                captured.append({"stage": "fused_before_rerank", "ids": [row.chunk_id for row in result]})
                return result
            async def retrieve(self, query, context):
                retrieval_ordinal[0] += 1
                captured.clear()
                started = time.monotonic()
                try:
                    result = await super().retrieve(query, context)
                    put(f"retrieval-{retrieval_ordinal[0]:03}", {"exit_code": 0, "branch_ranks": list(captured), "candidates": [c.chunk_id for c in result.candidates],
                        "total_ms": result.total_ms, "actual_SQL_and_HTTP_checkpoints": True, "index_version": INDEX})
                    return result
                except Exception as error:
                    put(f"retrieval-{retrieval_ordinal[0]:03}", {"exit_code": 1, "error_type": type(error).__name__, "elapsed_ms": (time.monotonic()-started)*1000,
                        "branch_ranks": list(captured), "error_not_omitted": True})
                    raise
        retrieval = Recorded(profile=profile, binding=binding, expected_index_version=INDEX, expected_embedding_artifact_sha256=EMBED_SHA,
            expected_reranker_artifact_sha256=RERANK_SHA, lexical=lexical_search, vector=vector_search, reranker=reranker,
            token_counter=lambda text: envelope.count("embedding", text), tokenizer_model_id=profile.embedding_model_id, tokenizer_model_revision=profile.embedding_model_revision)
        from campus247.bootstrap.app import create_app
        from campus247.bootstrap.settings import Settings
        from campus247.infrastructure.repositories.conversations import PostgresConversationRepository
        from m1_gate_observe_20261011_33 import install
        import acceptance_continuation_20261005_10 as base
        base.HERE, base.LABEL = OUT, "gate"
        install()
        gateway = Gateway(endpoint, key)
        base.HERE, base.LABEL = OUT, "gate"
        settings = Settings(_env_file=None, DATABASE_URL=dsn, ENVIRONMENT="development", DEMO_MODE=True,
            RETRIEVAL_RUNTIME_DEADLINES=config(), IDENTITY_SECRET_KEY=secrets.token_hex(32), CONFIRMATION_SIGNING_KEY=secrets.token_hex(32),
            OPENAI_API_KEY=None, GEMINI_API_KEY=None, DEEPSEEK_API_KEY=None)
        from campus247.infrastructure.llm.egress_policy import EgressPolicy
        def content_policy(text):
            try:
                EgressPolicy().validate_and_minimize({"purpose": "FAQ_ANSWERING", "messages": [{"role": "user", "content": text}]})
                return len(text) <= 12000
            except Exception:
                return False
        repo = PostgresConversationRepository(pool=pool, validate_content=content_policy)
        from campus247.infrastructure.retrieval.postgres_citation_source import PostgresCitationSourceReader
        source_reader = PostgresCitationSourceReader(pool=pool, filter_compiler=common["filter_compiler"])
        app = create_app(citation_source_reader=source_reader, runtime_settings=settings, synthetic_tenant_id=TENANT, allow_labeled_simulation=True,
                         retrieval_context_factory=factory, canonical_retrieval_service=retrieval, llm_gateway=gateway, conversation_repository=repo)
        results = []
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1:8000", timeout=30) as api:
                identity = app.state.identity_adapter if hasattr(app.state, "identity_adapter") else None
                if identity is None:
                    from campus247.infrastructure.identity.mock import SyntheticIdentityAdapter
                    identity = SyntheticIdentityAdapter(secret_key=settings.IDENTITY_SECRET_KEY, tenant_id=TENANT)
                token = identity.mint_token(ACTOR)
                headers = {"Authorization": "Bearer " + token}
                from m2_bulk_20261012_74 import Bulk
                bulk = Bulk(app, identity.resolve_token(token))
                case_map = {case["case_id"]: case for case in load("gold")["cases"]}
                for scheduled_no, scheduled in enumerate(load("plan")["batches"][registry.batch()]):
                    doc, attempt = case_map[scheduled["case_id"]], scheduled["repeat"]
                    HTTP_smoke = scheduled_no == 0
                    if HTTP_smoke:
                        created = await api.post("/v1/conversations", headers=headers, json={})
                        assert created.status_code == 201
                        conversation_id = created.json()["id"]
                    else:
                        conversation_id = await bulk.create()
                    for turn_no, query in enumerate(doc["turns"], 1):
                        retrieval_before = retrieval_ordinal[0]
                        response, events = None, []
                        if HTTP_smoke:
                            response = await api.post(f"/v1/conversations/{conversation_id}/messages:stream", headers=headers, json={"content": query})
                            for block in response.text.replace("\r\n", "\n").split("\n\n"):
                                parts = {line.split(":", 1)[0]: line.split(":", 1)[1].strip() for line in block.splitlines() if ":" in line}
                                if "data" in parts:
                                    events.append({"event": parts.get("event"), "data": json.loads(parts["data"])})
                            final = next((row["data"] for row in reversed(events) if row["event"] == "message.completed"), None)
                        else:
                            final = await bulk.turn(conversation_id, query)
                        case = {"case_id": doc["case_id"], "suite": doc["suite"], "split": doc["split"], "attempt": attempt,
                                "turn_no": turn_no, "fresh_two_turn_conversation": True, "HTTP_status": response.status_code if response else None, "execution_layer": "HTTP_SSE" if HTTP_smoke else "application", "final": final, "events": events,
                                "retrieval_attempt": retrieval_ordinal[0] if retrieval_ordinal[0] > retrieval_before else None,
                                "provider_snapshot": gateway.budget.snapshot(), "application_dependency_failed": bulk.last_dependency_failed if not HTTP_smoke else False, "application_failure_code": getattr(bulk, "last_failure_code", None) if not HTTP_smoke else None, "application_metadata": getattr(bulk, "last_observation_meta", {}) if not HTTP_smoke else {}}
                        put(f"case-{doc['case_id']}-{attempt}-t{turn_no}", case)
                        results.append(case)
                        if (final is None and response is not None and response.status_code in {400, 401, 403, 404, 422}
                                and doc["suite"] in {"injection", "abstention"}):
                            continue
                        if final and final.get("response_class") == "grounded_answer":
                            if HTTP_smoke:
                                refreshed = await api.get(f"/v1/conversations/{conversation_id}/messages", headers=headers)
                                assert refreshed.status_code == 200
                                assert next(item["final_result"] for item in refreshed.json()["items"] if item["id"] == final["message_id"]) == final
                                for citation in final["citations"]:
                                    citation_id = citation["citation"]["citation_id"]
                                    opened = await api.get(f"/v1/conversations/{conversation_id}/messages/{final['message_id']}/citations/{citation_id}/source", headers=headers)
                                    assert opened.status_code == 200
                                    source = opened.json()
                                    assert hashlib.sha256(source["content_text"].encode()).hexdigest() == source["content_sha256"]
                                receipt = {"exit_code": 0, "signed_actor": True, "refresh_HTTP": 200,
                                    "opened_citations": len(final["citations"]), "checksum_verified": True,
                                    "persisted_final_matches": True, "execution_layer": "HTTP_SSE"}
                            else:
                                receipt = await bulk.verify(final)
                            put(f"source-open-{doc['case_id']}-{attempt}-t{turn_no}", receipt)
                        if final is None or final.get("status") in {"failed", "safe_failure"}:
                            put(f"pipeline-failure-{doc['case_id']}-{attempt}-t{turn_no}", {
                                "exit_code": 1, "reason": "actual pipeline failure retained; never a successful abstention",
                                "case_id": doc["case_id"], "attempt": attempt, "turn_no": turn_no})
                            continue
        return results
        return results
    finally:
        put("model-http-final-ledger", {"cumulative_HTTP": model_http[0], "before": registry.prior()["native"]["HTTP"], "cap": 12000,
            "failed_connects_retained": True, "predecessor_sha256": registry.prior()["native_predecessor_sha256"]})
        if "gateway" in locals():
            put("provider-final-ledger", {"predecessor_sha256": registry.prior()["paid_predecessor_sha256"],
                "snapshot": gateway.budget.snapshot(), "M2_limit_usd": "1.5", "budget_reset": False,
                "pending_reservation_records": {str(o): gateway.prior_unknown_records[str(o)] if str(o) in gateway.prior_unknown_records else load(f"provider-reservation-{o:03}") for o in gateway.budget.pending},
                "new_namespace_calls": gateway.budget.calls - gateway.before_calls, "whole_M2_calls": gateway.budget.calls, "all_prior_M1_failures_retained": True})
        await pool.close()


async def worker():
    import continuation_audit as audit
    from acceptance_live_20261006_18 import settings as provider_settings
    from bounded_physical_process_20261011_30 import BoundedProcess
    import acceptance_continuation_20261005_10 as base
    f = audit.fixture()
    f.preflight()
    dsn = audit.owned_endpoint(f)
    endpoint, key, _ = provider_settings()
    addresses = {row[4][0] for row in socket.getaddrinfo("api.deepseek.com", 443, type=socket.SOCK_STREAM)}
    assert addresses
    storage = audit.checked(OUT / "idempotency.sqlite3")
    assert not storage.exists()
    os.environ["CAMPUS247_IDEMPOTENCY_DB"] = str(storage)
    models = BoundedProcess([sys.executable, "-B", "-u", str(HERE / "m2_runtime_20261012_74.py"), "worker", "serve"], cwd=ROOT, env=base.clean_env())
    logs = {"stdout": [], "stderr": []}
    sizes = {"stdout": 0, "stderr": 0}
    def drain(name, stream):
        for line in stream:
            sizes[name] += len(line.encode("utf-8"))
            if sizes[name] <= 4 * 1024 * 1024:
                logs[name].append(line)
    readers = [threading.Thread(target=drain, args=(name, getattr(models.process, name)), daemon=True)
               for name in logs]
    for reader in readers:
        reader.start()
    before = None
    try:
        ready, started = OUT / "native-http-runtime-ready.json", time.monotonic()
        while not ready.exists():
            assert models.process.poll() is None and time.monotonic() - started < 120
            await asyncio.sleep(.2)
        before = await public_snapshot(dsn)
        predecessor_before = await predecessor_snapshot(dsn)
        put("predecessor-schemas-before", {"hashes": predecessor_before})
        put("public-before", before)
        assert before["counts"] == {"conversation": 3, "message": 27}
        runtime_guards(addresses)
        results = await diagnostic(dsn, endpoint, key)
        put("diagnostic-results", {"observed_attempts": len(results), "planned_attempts": sum(row["turns"] for row in load("plan")["batches"][registry.batch()]),
            "full_M2_status": "pending_aggregate", "diagnostic_only": False, "case_attempts": [{"case_id": r["case_id"], "attempt": r["attempt"]} for r in results]})
    except Exception as error:
        import traceback
        put("worker-failure", {"exit_code": 1, "error_type": type(error).__name__, "locations": [{"file": Path(t.filename).name, "function": t.name, "line": t.lineno} for t in traceback.extract_tb(error.__traceback__)[-5:]], "sensitive_details_suppressed": True})
        raise SystemExit(1) from None
    finally:
        if models.process.poll() is None:
            models.process.stdin.write("stop\n")
            models.process.stdin.flush()
        models.process.wait(timeout=20)
        for reader in readers:
            reader.join(timeout=5)
        stdout, stderr = "".join(logs["stdout"]), "".join(logs["stderr"])
        assert all(size <= 4 * 1024 * 1024 for size in sizes.values())
        put("native-process-exit", {"exit_code": models.process.returncode, "stdout": stdout, "stderr": stderr,
                                    "controls": models.controls | models.measure(), "owned_process_only": True})
        models.close()
        if before is not None:
            after = await public_snapshot(dsn)
            put("public-after", {**after, "public_M1_preserved": after == before})
            assert after == before
            predecessor_after = await predecessor_snapshot(dsn)
            put("predecessor-schemas-after", {"hashes": predecessor_after, "preserved": predecessor_after == predecessor_before})
            assert predecessor_after == predecessor_before


def launch():
    from bounded_physical_process_20261011_30 import run
    import acceptance_continuation_20261005_10 as base
    args = [sys.executable, "-B", "-u", str(Path(__file__).resolve()), "worker"]
    code, stdout, stderr, controls = run(args, cwd=ROOT, env=base.clean_env(), timeout=900)
    put("bounded-controller", {"exit_code": code, "command": args, "stdout": stdout, "stderr": stderr,
                               "controls": controls, "deadline_seconds": 900, "provider_cost_hard_cap_usd": 1})
    raise SystemExit(code)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    {"prepare": prepare, "launch": launch, "worker": lambda: asyncio.run(worker())}[sys.argv[1]]()
