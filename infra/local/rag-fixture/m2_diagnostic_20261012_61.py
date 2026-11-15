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
OUT = HERE / "m2-20261012-61"
SCHEMA, INDEX, CORPUS = "m2_20261012_61", "m2-diagnostic-20261012-61", "m2-diag-corpus-20261012-61"
ACTOR, TENANT = "4b419a1b-6d41-7dfb-8943-2edd9f071385", "synthetic-institution"
EMBED_SHA, RERANK_SHA = "1eebfb28493f67bba03ce0ef64bfdc7fc5a3bd9d7493f818bb1d78cd798416b4", "d9e3e081faff1eefb84019509b2f5558fd74c1a05a2c7db22f74174fcedb5286"
sys.path[:0] = [str(ROOT), str(HERE), str(ROOT / "services/api/src"), str(ROOT / "packages/synthetic/src")]


def put(name, value):
    import continuation_audit as audit
    path = audit.checked(OUT / (name + ".json"))
    with path.open("x", encoding="utf-8") as stream:
        json.dump({"run_id": "m2-20261012-61", "created_at": datetime.now(timezone.utc).isoformat(), **value},
                  stream, ensure_ascii=False, indent=2, sort_keys=True)
    print(json.dumps({"receipt": name}), flush=True)


def load(name):
    return json.loads((OUT / (name + ".json")).read_bytes())


def sha(path):
    if os.name != "nt":  # recorded relative paths use Windows separators
        path = Path(str(path).replace("\\", "/"))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare():
    import acceptance_continuation_20261005_10 as base
    previous = json.loads((HERE / "acceptance-20261012-53-baseline.json").read_bytes())
    checks = [base.command(row["command"]) for row in previous["preflight"]]
    put("preflight", {"exit_code": int(any(row["exit_code"] for row in checks)), "commands": checks})
    assert not any(row["exit_code"] for row in checks)
    # Original diagnostic facts, reviewed here before candidate execution. All
    # titles, identifiers and numerical rules are fictional, with exact locators.
    specs = [
        ("academic", "SYN-ACA-60", "đăng ký học", "Giới hạn đăng ký theo SYN-ACA-60 là 18 tín chỉ mỗi học kỳ.", "Giới hạn đăng ký theo SYN-ACA-60 là bao nhiêu tín chỉ mỗi học kỳ?", "18"),
        ("administrative", "SYN-ADM-60", "thời gian xử lý", "Thời gian xử lý theo SYN-ADM-60 là 4 ngày làm việc.", "Thời gian xử lý theo SYN-ADM-60 là bao nhiêu ngày làm việc?", "4"),
        ("exam", "SYN-EXM-60", "đến phòng thi", "Theo SYN-EXM-60, sinh viên đến phòng thi trước 25 phút.", "Theo SYN-EXM-60, sinh viên đến phòng thi trước bao nhiêu phút?", "25"),
        ("library", "SYN-LIB-60", "mượn sách", "Theo SYN-LIB-60, thời hạn mượn sách là 12 ngày.", "Theo SYN-LIB-60, thời hạn mượn sách là bao nhiêu ngày?", "12"),
        ("facilities", "SYN-FAC-60", "sức chứa phòng", "Theo SYN-FAC-60, sức chứa phòng sinh hoạt là 35 người.", "Theo SYN-FAC-60, sức chứa phòng sinh hoạt là bao nhiêu người?", "35"),
        ("it", "SYN-ITC-60", "phiên đăng nhập", "Theo SYN-ITC-60, phiên đăng nhập hết hạn sau 45 phút không hoạt động.", "Theo SYN-ITC-60, phiên đăng nhập hết hạn sau bao nhiêu phút không hoạt động?", "45"),
        ("complaints", "SYN-CMP-60", "phản hồi kiến nghị", "Theo SYN-CMP-60, hạn phản hồi kiến nghị là 6 ngày làm việc.", "Theo SYN-CMP-60, hạn phản hồi kiến nghị là bao nhiêu ngày làm việc?", "6"),
        ("privacy", "SYN-PRV-60", "bản xuất dữ liệu", "Theo SYN-PRV-60, bản xuất dữ liệu khả dụng trong 9 ngày.", "Theo SYN-PRV-60, bản xuất dữ liệu khả dụng trong bao nhiêu ngày?", "9"),
    ]
    documents = []
    for i, (domain, code, title, fact, query, number) in enumerate(specs, 1):
        text = "DỮ LIỆU MÔ PHỎNG; không phải quy định chính thức. " + fact
        documents.append({"case_id": f"EVAL-M2DIAG-{i:03}", "domain": domain,
            "source_id": f"019a0060-0000-7000-8000-{i:012d}",
            "document_version_id": f"019a0060-0001-7000-8000-{i:012d}",
            "chunk_id": f"019a0060-0002-7000-8000-{i:012d}",
            "document_number": code, "title": title + " — mô phỏng", "text": text,
            "section_path": code + " / Điều 1", "page_start": 1, "page_end": 1,
            "text_sha256": hashlib.sha256(text.encode()).hexdigest(), "query": query,
            "expected_number": number, "expected_source_id": f"019a0060-0000-7000-8000-{i:012d}",
            "synthetic": True, "split": "dev", "review": "executor technical review under DEC-022/023; original exact fact and locator; frozen before runs"})
    put("corpus", {"documents": documents, "seed": 2472060, "version": "1.0.0", "release_gold": False,
                   "sealed_data": False, "M2_quota_satisfied": False, "generator_sha256": sha(Path(__file__))})
    put("plan", {"authority": "Direct user 1 USD whole M2 cycle + DEC-023/DEC-022", "financial_hard_cap_usd": "1.00",
        "provider": "deepseek-flash", "endpoint": "https://api.deepseek.com", "price_peak_usd_per_million": {"input": "0.3", "output": "1.2"},
        "diagnostic_cases": 8, "semantic_repeats": 3, "planned_turns": 24,
        "generation_cap": 96, "provider_HTTP_cap": 97, "payload_input_reservation_cap": 28000,
        "output_per_turn_cap": 2200, "worst_reservation_USD": "0.86976", "max_response_bytes": 1048576,
        "batch_seconds": 600, "controller_seconds": 900, "CPU": 4, "memory_GiB": 5, "concurrency": 1,
        "native_before": {"calls": 80, "tokens": 9376, "HTTP": 80}, "native_caps": {"calls": 140, "tokens": 50000, "HTTP": 220},
        "provider_predecessor_sha256": sha(HERE / "acceptance-20261012-56-provider-budget-ledger.json"),
        "native_predecessor_sha256": sha(HERE / "m2-20261012-60/native-dual-model-serve-final.json"),
        "corpus_sha256": sha(OUT / "corpus.json"), "schema": SCHEMA, "schema_must_be_absent_before_mutation": True,
        "frozen_code_sha256": {str(path.relative_to(ROOT)): sha(path) for path in (
            Path(__file__), HERE / "m2_runtime_20261012_61.py", ROOT / "evals/runners/paid_budget.py",
            HERE / "m1_config_20261012_56.py", HERE / "m1_provider_20261012_56.py",
            ROOT / "services/api/src/campus247/application/retrieval/canonical.py",
            ROOT / "services/api/src/campus247/agent/nodes/definitions.py")},
        "public_M1_changes": False, "static_requests": 0, "static_predecessor": {"requests": 374, "bytes": 27871262},
        "new_rows": {"knowledge_source": 8, "document_version": 8, "knowledge_chunk": 8, "retrieval_profile": 1,
                     "embedding_index_manifest": 1, "embedding_index_active_pointer": 1, "conversation_max": 24, "message_max": 48},
        "not_full_M2": True, "fakes_pre_supplied_candidates": False, "no_candidate_promotion_to_public": True,
        "stop": "record attempts; stop on hard cap, deadline or two materially different repairs; no automatic retry or discarded failure"})


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


def runtime_guards(addresses):
    # Reuse unchanged restrictions, but use a fresh exact owned SQLite target.
    from m1_server_20261012_56 import guards
    guards(addresses)


class Gateway:
    def __init__(self, endpoint, key):
        from evals.runners.paid_budget import PaidBudget
        from m1_provider_20261012_56 import ObservedAdapter
        self.adapter = ObservedAdapter("deepseek", endpoint, key, "deepseek-flash", default_timeout_sec=5, disable_thinking=True)
        self.budget = PaidBudget(cap_usd="1", call_cap=96)
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
            except Exception as error:
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
                    document_count=8, chunk_count=8, built_at=now, validated_at=now,
                    content_checksum=sha(OUT / "corpus.json"))
    rows["embedding_index_manifest"] = [manifest]
    rows["embedding_index_active_pointer"] = [dict(old["embedding_index_active_pointer"][0], index_version=INDEX, activated_at=now)]
    async with pool.acquire() as conn:
        assert await conn.fetchval("SELECT count(*) FROM pg_namespace WHERE nspname=$1", SCHEMA) == 0
        for doc, vector in zip(documents, vectors, strict=True):
            source = dict(old["knowledge_source"][0], id=doc["source_id"], title=doc["title"],
                          canonical_uri="synthetic://m2-diag/" + doc["document_number"].lower(),
                          owner_unit="SYNTHETIC M2 DIAGNOSTIC — executor curated", created_at=now, updated_at=now)
            version = dict(old["document_version"][0], id=doc["document_version_id"], knowledge_source_id=doc["source_id"],
                           content_checksum=doc["text_sha256"], index_version=INDEX, version_label="m2-diag-v1", created_at=now, updated_at=now)
            chunk = dict(old["knowledge_chunk"][0], id=doc["chunk_id"], document_version_id=doc["document_version_id"],
                         content_text=doc["text"], content_checksum=doc["text_sha256"], section_path=doc["section_path"],
                         content_tsv=await conn.fetchval("SELECT to_tsvector('simple',$1)::text", doc["text"]),
                         embedding_rag_v1=json.dumps(vector), page_start=1, page_end=1, created_at=now, updated_at=now, embedded_at=now)
            rows["knowledge_source"].append(source)
            rows["document_version"].append(version)
            rows["knowledge_chunk"].append(chunk)
        put("additive-row-plan", {"rows": rows, "schema": SCHEMA, "only_INSERT_CREATE": True,
                                   "public_M1_changes": False, "DB_source_vector_inference_actual": True})
        async with conn.transaction():
            await conn.execute("CREATE SCHEMA m2_20261012_61")
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
    from m1_config_20261012_56 import config
    profile, envelope = config().apply(load_retrieval_profile()), TokenEnvelope()
    pool = await asyncpg.create_pool(dsn.replace("postgresql+asyncpg://", "postgresql://", 1), min_size=1, max_size=2,
                                    command_timeout=5, server_settings={"search_path": SCHEMA + ",public"})
    model_profile = EmbeddingProfile(profile.embedding_model_id, profile.embedding_model_revision, 1024, "l2", timeout_ms=2100)
    model_http = [80]
    runtime_ssl = ssl.create_default_context()
    async def before_request(request):
        await envelope.before_request(request)
        assert model_http[0] < 220
        model_http[0] += 1
        put(f"model-http-{model_http[0]:03}", {"endpoint": str(request.url), "method": request.method,
            "counted_before_transport": True, "failed_attempts_retained": True, "cumulative_cap": 220})
    def client(port):
        return lambda: httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}", trust_env=False, verify=runtime_ssl,
            event_hooks={"request": [before_request]}, follow_redirects=False)
    embedding = TEIEmbeddingAdapter(model_profile, client(18081))
    async def embed(text):
        return (await embedding._embed(validate_embedding_inputs((text,), model_profile))).vectors[0]
    docs = load("corpus")["documents"]
    try:
        vectors = []
        for i, doc in enumerate(docs, 1):
            value = await embed(doc["text"])
            vectors.append(list(value.values))
            put(f"document-embedding-{i:02}", {"source_id": doc["source_id"], "text_sha256": doc["text_sha256"],
                "actual_checkpoint": profile.embedding_model_id, "dimension": len(value.values), "vector_sha256": hashlib.sha256(json.dumps(value.values).encode()).hexdigest()})
        await install_candidate(pool, vectors)
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
        reranker = TEIRerankerAdapter(RerankerProfile(profile.reranker_model_id, profile.reranker_model_revision, 20, 2100), client(18082))
        binding = RuntimeRetrievalBinding(INDEX, profile.profile_version, profile.embedding_model_id, profile.embedding_model_revision, 1024, "l2", "cosine", EMBED_SHA, profile.reranker_model_id, profile.reranker_model_revision, RERANK_SHA)
        class Recorded(CanonicalRetrievalService):
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
                return len(text) <= 10000
            except Exception:
                return False
        repo = PostgresConversationRepository(pool=pool, validate_content=content_policy)
        app = create_app(runtime_settings=settings, synthetic_tenant_id=TENANT, allow_labeled_simulation=True,
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
                for attempt in (1, 2, 3):
                    for doc in docs:
                        created = await api.post("/v1/conversations", headers=headers, json={})
                        assert created.status_code in {200, 201}
                        conversation_id = created.json()["id"]
                        response = await api.post(f"/v1/conversations/{conversation_id}/messages:stream", headers=headers, json={"content": doc["query"]})
                        events = []
                        for block in response.text.replace("\r\n", "\n").split("\n\n"):
                            parts = {line.split(":", 1)[0]: line.split(":", 1)[1].strip() for line in block.splitlines() if ":" in line}
                            if "data" in parts:
                                events.append({"event": parts.get("event"), "data": json.loads(parts["data"])})
                        final = next((row["data"] for row in reversed(events) if row["event"] == "message.completed"), None)
                        case = {"case_id": doc["case_id"], "attempt": attempt, "HTTP_status": response.status_code,
                                "final": final, "events": events, "retrieval_attempt": retrieval_ordinal[0], "provider_snapshot": gateway.budget.snapshot()}
                        put(f"case-{doc['case_id']}-{attempt}", case)
                        results.append(case)
                        if final is None or final.get("status") in {"failed", "safe_failure"}:
                            put("diagnostic-stop", {"reason": "actual pipeline failed; retain attempt and stop for diagnosis", "case_id": doc["case_id"], "attempt": attempt})
                            return results
        return results
    finally:
        put("model-http-final-ledger", {"cumulative_HTTP": model_http[0], "before": 80, "cap": 220,
            "failed_connects_retained": True, "predecessor_sha256": sha(HERE / "m2-20261012-60/native-dual-model-serve-final.json")})
        if "gateway" in locals():
            put("provider-final-ledger", {"predecessor_sha256": sha(HERE / "acceptance-20261012-56-provider-budget-ledger.json"),
                "snapshot": gateway.budget.snapshot(), "M2_limit_usd": "1", "budget_reset": False,
                "new_M2_calls": gateway.budget.calls, "all_prior_M1_failures_retained": True})
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
    models = BoundedProcess([sys.executable, "-B", "-u", str(HERE / "m2_runtime_20261012_61.py"), "worker", "serve"], cwd=ROOT, env=base.clean_env())
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
        put("public-before", before)
        assert before["counts"] == {"conversation": 3, "message": 27}
        runtime_guards(addresses)
        results = await diagnostic(dsn, endpoint, key)
        put("diagnostic-results", {"observed_attempts": len(results), "planned_attempts": 24,
            "full_M2_status": "not_verified", "diagnostic_only": True, "case_attempts": [{"case_id": r["case_id"], "attempt": r["attempt"]} for r in results]})
    except Exception as error:
        put("worker-failure", {"exit_code": 1, "error_type": type(error).__name__, "sensitive_details_suppressed": True})
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
