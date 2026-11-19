"""SQL boundary/negative checks; no fake result is called a DB or model pass."""
import asyncio
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib

import pytest

from campus247.application.retrieval.filters import RetrievalFilterCompiler, RetrievalFilterError
from campus247.application.retrieval.profile import load_retrieval_profile
from campus247.domain.embedding_index import ActiveIndexPointer, BuildStatus, EmbeddingIndexManifest
from campus247.domain.retrieval import AuthorizedScope, RetrievalContext, SimulationPolicy
from campus247.infrastructure.retrieval.postgres_vector import PostgresVectorSearchAdapter
from campus247.infrastructure.retrieval.postgres_lexical import PostgresLexicalSearchAdapter
from campus247.infrastructure.retrieval.vector import VectorSearchAdapter
from campus247.ports.embedding import EmbeddingProfile, validate_embedding_vector


def fixture():
    now = datetime(2026, 10, 6, tzinfo=timezone.utc)
    profile = load_retrieval_profile()
    embedding = EmbeddingProfile(profile.embedding_model_id, profile.embedding_model_revision, 1024, timeout_ms=700)
    manifest = EmbeddingIndexManifest("synthetic-index", profile.profile_version, embedding.model_id,
        embedding.model_revision, "a" * 64, 1024, "l2", "cosine", "synthetic-corpus", 1, 1, "b" * 64,
        BuildStatus.READY, now - timedelta(days=1), now - timedelta(hours=1))
    pointer = ActiveIndexPointer(profile.profile_version, manifest.index_version, now)
    context = RetrievalContext(AuthorizedScope("synthetic-institution", "HUCE", "synthetic-actor",
        frozenset({"STUDENT"}), frozenset({"STUDENT"}), frozenset({"FIT"}), frozenset({"SYNTHETIC"})),
        "vi", now, SimulationPolicy.ALLOW_LABELED, "synthetic-trace")
    calls = []
    body = "Synthetic content."
    row = {"id": "synthetic-chunk", "document_version_id": "synthetic-version", "source_id": "synthetic-source",
        "content_text": body, "content_checksum": hashlib.sha256(body.encode()).hexdigest(),
        "section_path": "Section 1", "page_start": None, "page_end": None,
        "title": "Synthetic title", "canonical_uri": "synthetic://policy", "is_synthetic": True,
        "version_label": "synthetic-v1", "document_status": "PUBLISHED", "approval_status": "APPROVED",
        "effective_from": now - timedelta(days=1), "effective_until": None, "distance": 0.1}
    class DB:
        async def fetch(self, sql, *params):
            calls.append((sql, params))
            return [row]
    embedded = []
    async def embed(query):
        embedded.append(query)
        return validate_embedding_vector([1] + [0] * 1023, embedding)
    config = dict(pool=DB(), embed_query=embed, embedding_profile=embedding, profile=profile,
        manifest=manifest, pointer=pointer, expected_index_version=manifest.index_version,
        expected_corpus_version=manifest.corpus_version, expected_artifact_sha256="a" * 64,
        filter_compiler=RetrievalFilterCompiler(tenant_id="synthetic-institution", campus_id="HUCE",
            profile_allows_simulation=True), issuer_resolver=lambda source: "Declared synthetic issuer")
    return config, context, calls, embedded, row


@pytest.mark.asyncio
async def test_vector_sql_filters_and_profile_binding_precede_order_and_limit():
    config, ctx, calls, embedded, _ = fixture()
    results = await PostgresVectorSearchAdapter(**config).search_candidates(" synthetic question ", context=ctx)
    assert embedded == ["synthetic question"]
    sql, params = calls[0]
    where = sql[sql.index("WHERE"):sql.index("ORDER BY")]
    for term in ["approval_status", "PUBLISHED", "effective_from", "effective_until", "applicability_reviewed_at",
        "campus_scope", "faculty_scope", "program_scope", "audiences", "is_synthetic",
        "embedding_model_version", "m.index_version", "m.artifact_sha256", "p.activated_at"]:
        assert term in where
    assert "embedding_rag_v1 <=> $1::vector(1024)" in sql and "LIMIT $2" in sql
    assert "synthetic question" not in sql and "synthetic question" not in repr(params)
    assert params[1] == 30 and params[7] is True
    assert results[0].issuer == "Declared synthetic issuer" and results[0].source_id == "synthetic-source"
    assert results[0].quote_span_hash == hashlib.sha256(results[0].content_text.encode()).hexdigest()
    assert results[0].simulation_label and results[0].vector_rank == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("context", [None, "client claims"])
async def test_missing_trusted_context_rejects_before_embedding_and_db(context):
    config, _, calls, embedded, _ = fixture()
    with pytest.raises(RetrievalFilterError):
        await PostgresVectorSearchAdapter(**config).search_candidates("synthetic", context=context)
    assert not calls and not embedded


@pytest.mark.parametrize("change", ["artifact", "index", "model", "dimension", "not_ready"])
def test_mismatched_manifest_rejects_at_construction(change):
    config, _, calls, embedded, _ = fixture()
    if change == "artifact": config["expected_artifact_sha256"] = "c" * 64
    elif change == "index": config["expected_index_version"] = "other-index"
    elif change == "model": config["embedding_profile"] = replace(config["embedding_profile"], model_id="other")
    elif change == "dimension": config["embedding_profile"] = replace(config["embedding_profile"], dimension=1536)
    else: config["manifest"] = replace(config["manifest"], build_status=BuildStatus.BUILDING)
    with pytest.raises(RetrievalFilterError): PostgresVectorSearchAdapter(**config)
    assert not calls and not embedded


@pytest.mark.asyncio
async def test_stored_checksum_and_missing_issuer_fail_closed():
    config, ctx, _, _, row = fixture()
    row["content_text"] = "tampered"
    with pytest.raises(RetrievalFilterError, match="integrity"):
        await PostgresVectorSearchAdapter(**config).search_candidates("synthetic", context=ctx)
    row["content_checksum"] = hashlib.sha256(row["content_text"].encode()).hexdigest()
    config["issuer_resolver"] = lambda source: ""
    with pytest.raises(RetrievalFilterError, match="issuer"):
        await PostgresVectorSearchAdapter(**config).search_candidates("synthetic", context=ctx)


@pytest.mark.asyncio
async def test_existing_vector_entrypoint_delegates_only_to_verified_binding():
    config, ctx, calls, _, _ = fixture()
    backend = PostgresVectorSearchAdapter(**config)
    adapter = VectorSearchAdapter(verified_backend=backend)
    result = await adapter.search("synthetic", context=ctx)
    assert result[0].chunk_id == "synthetic-chunk" and len(calls) == 1
    with pytest.raises(ValueError, match="overridden"):
        await adapter.search("synthetic", context=ctx, conn=object())
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_cancellation_closes_acquired_pool_connection():
    config, ctx, _, _, _ = fixture()
    entered, released = asyncio.Event(), asyncio.Event()
    class Lease:
        async def __aenter__(self):
            entered.set()
            return self
        async def __aexit__(self, *args): released.set()
        async def fetch(self, *args): await asyncio.sleep(60)
    class Pool:
        def acquire(self): return Lease()
    config["pool"] = Pool()
    task = asyncio.create_task(PostgresVectorSearchAdapter(**config).search_candidates("synthetic", context=ctx))
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError): await task
    assert released.is_set()


@pytest.mark.asyncio
async def test_canonical_lexical_branch_retains_source_metadata_and_prefilters():
    config, ctx, calls, _, _ = fixture()
    config.pop("embed_query")
    config.pop("embedding_profile")
    result = await PostgresLexicalSearchAdapter(**config).search_candidates("synthetic question", context=ctx)
    sql, params = calls[0]
    where = sql[sql.index("WHERE"):sql.index("ORDER BY")]
    for term in ["approval_status", "PUBLISHED", "effective_from", "effective_until", "applicability_reviewed_at",
        "campus_scope", "faculty_scope", "program_scope", "audiences", "is_synthetic", "m.index_version",
        "m.artifact_sha256", "p.activated_at"]:
        assert term in where
    assert params[0] == "synthetic question" and "synthetic question" not in sql
    assert result[0].source_id == "synthetic-source" and result[0].issuer == "Declared synthetic issuer"
    assert result[0].lexical_rank == 1 and result[0].vector_rank is None


@pytest.mark.asyncio
async def test_lexical_unknown_context_no_database_access():
    config, _, calls, _, _ = fixture()
    config.pop("embed_query")
    config.pop("embedding_profile")
    with pytest.raises(RetrievalFilterError):
        await PostgresLexicalSearchAdapter(**config).search_candidates("synthetic")
    assert not calls
