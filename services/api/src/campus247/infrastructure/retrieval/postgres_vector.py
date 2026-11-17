"""Profile-bound pgvector branch with eligibility before ranking and LIMIT.

Construction is not fixture/runtime clearance. The composition root supplies an
already owned pool, authorized async embedding callback, immutable manifest,
independent activation expectations and an explicit trusted issuer resolver.
No default DSN, profile selection, model calls, index activation or fallback.
"""
from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Awaitable, Callable

from campus247.application.retrieval.filters import (
    RetrievalFilterCompiler,
    RetrievalFilterError,
)
from campus247.application.retrieval.profile import RetrievalProfile
from campus247.application.retrieval.runtime_config import validate_effective_profile
from campus247.domain.embedding_index import (
    ActiveIndexPointer,
    BuildStatus,
    EmbeddingIndexManifest,
)
from campus247.domain.retrieval import RetrievalCandidate, RetrievalContext
from campus247.ports.embedding import EmbeddingProfile, EmbeddingVector
from campus247.ports.retrieval import ChunkResult


def authorized_rows_to_candidates(rows, issuer_resolver, *, branch):
    """Preserve provenance after an authorized SQL candidate relation."""
    if branch not in {"lexical", "vector"}:
        raise RetrievalFilterError("known retrieval branch required")
    candidates = []
    for rank, row in enumerate(rows, 1):
        digest = hashlib.sha256(row["content_text"].encode("utf-8")).hexdigest()
        if digest != row["content_checksum"] or not row["section_path"]:
            raise RetrievalFilterError("stored candidate content/locator integrity rejected")
        if (row["document_status"] != "PUBLISHED" or row["approval_status"] != "APPROVED"
                or type(row["is_synthetic"]) is not bool
                or not isinstance(row["version_label"], str) or not row["version_label"].strip()):
            raise RetrievalFilterError("stored candidate publication/version provenance rejected")
        issuer = issuer_resolver(str(row["source_id"]))
        if not isinstance(issuer, str) or not issuer.strip():
            raise RetrievalFilterError("trusted source issuer binding required")
        candidates.append(RetrievalCandidate(str(row["source_id"]), str(row["document_version_id"]),
            str(row["id"]), row["content_text"], row["title"], issuer, row["canonical_uri"], digest,
            (row["section_path"],), page_start=row["page_start"], page_end=row["page_end"],
            effective_from=row["effective_from"], effective_until=row["effective_until"],
            simulation_label=row["is_synthetic"], version_label=row["version_label"],
            source_status="SYNTHETIC" if row["is_synthetic"] else "CURRENT",
            **{branch + "_rank": rank}))
    if len({c.chunk_id for c in candidates}) != len(candidates):
        raise RetrievalFilterError("duplicate retrieval candidates rejected")
    return candidates


class PostgresVectorSearchAdapter:
    def __init__(self, *, pool, embed_query: Callable[[str], Awaitable[EmbeddingVector]],
                 embedding_profile: EmbeddingProfile, profile: RetrievalProfile,
                 manifest: EmbeddingIndexManifest, pointer: ActiveIndexPointer,
                 expected_index_version: str, expected_corpus_version: str,
                 expected_artifact_sha256: str, filter_compiler: RetrievalFilterCompiler,
                 issuer_resolver: Callable[[str], str]):
        if (pool is None or not callable(embed_query) or not callable(issuer_resolver)
                or not isinstance(filter_compiler, RetrievalFilterCompiler)
                or not isinstance(profile, RetrievalProfile) or not isinstance(embedding_profile, EmbeddingProfile)
                or not isinstance(manifest, EmbeddingIndexManifest) or not isinstance(pointer, ActiveIndexPointer)):
            raise RetrievalFilterError("complete trusted vector dependencies required")
        validate_effective_profile(profile)
        model = (profile.embedding_model_id, profile.embedding_model_revision, profile.embedding_dimension)
        if ((embedding_profile.model_id, embedding_profile.model_revision, embedding_profile.dimension) != model
                or embedding_profile.normalization != profile.normalization
                or embedding_profile.timeout_ms > profile.semantic_timeout_ms
                or (manifest.embedding_model_id, manifest.embedding_model_revision, manifest.dimension) != model
                or manifest.normalization != profile.normalization or manifest.distance_metric != profile.distance_metric
                or manifest.profile_version != profile.profile_version or pointer.profile_version != profile.profile_version
                or manifest.index_version != expected_index_version or pointer.index_version != expected_index_version
                or manifest.corpus_version != expected_corpus_version or manifest.artifact_sha256 != expected_artifact_sha256
                or manifest.build_status not in (BuildStatus.READY, BuildStatus.ACTIVE)
                or manifest.validated_at is None or pointer.activated_at < manifest.validated_at):
            raise RetrievalFilterError("vector storage/model/index compatibility rejected")
        # The only qualified physical mapping is the immutable 0013 mapping.
        if model != ("BAAI/bge-m3", "5617a9f61b028005a4858fdac845db406aefb181", 1024):
            raise RetrievalFilterError("qualified vector physical mapping required")
        self._pool, self._embed, self._profile = pool, embed_query, profile
        self._embedding_profile, self._manifest, self._pointer = embedding_profile, manifest, pointer
        self._compiler, self._issuer = filter_compiler, issuer_resolver
        self._expected = {"expected_corpus_version": expected_corpus_version,
                          "expected_artifact_sha256": expected_artifact_sha256}

    async def search(self, query_text: str, top_k: int = 30, *, context: RetrievalContext | None = None):
        candidates = await self.search_candidates(query_text, top_k, context=context)
        # Compatibility projection for the historical RetrievalPort. Canonical
        # pipelines use search_candidates to retain provenance without defaults.
        return [ChunkResult(c.chunk_id, c.document_version_id, c.content_text,
            " / ".join(c.section_path), 1.0 / c.vector_rank) for c in candidates]

    async def search_candidates(self, query_text: str, top_k: int = 30, *, context: RetrievalContext | None = None):
        predicate = self._compiler.compile(context)
        if type(top_k) is not int or not 1 <= top_k <= self._profile.semantic_k:
            raise RetrievalFilterError("vector limit outside approved profile")
        if not isinstance(query_text, str) or not query_text.strip():
            raise RetrievalFilterError("non-empty minimized vector query required")
        async with asyncio.timeout(self._profile.semantic_timeout_ms / 1000):
            vector = await self._embed(query_text.strip())
            self._manifest.validate_query(vector, self._pointer, self._profile, **self._expected)
            # Exact numeric serialization only; query content is never SQL.
            literal = "[" + ",".join(str(v) for v in vector.values) + "]"
            if hasattr(self._pool, "acquire"):
                async with self._pool.acquire() as conn:
                    return await self._fetch(conn, literal, top_k, predicate)
            return await self._fetch(self._pool, literal, top_k, predicate)

    async def _fetch(self, conn, literal, top_k, predicate):
        rows = await conn.fetch("""
            SELECT c.id, c.document_version_id, c.content_text, c.content_checksum,
                   c.section_path, c.page_start, c.page_end, s.id AS source_id,
                   s.title, s.canonical_uri, s.is_synthetic, v.effective_from, v.effective_until,
                   v.version_label, v.status AS document_status, s.approval_status,
                   c.embedding_rag_v1 <=> $1::vector(1024) AS distance
            FROM knowledge_chunk c
            JOIN document_version v ON v.id = c.document_version_id
            JOIN knowledge_source s ON s.id = v.knowledge_source_id
            JOIN embedding_index_manifest m ON m.index_version = v.index_version
            JOIN embedding_index_active_pointer p ON p.index_version = m.index_version
                AND p.profile_version = m.profile_version
            WHERE """ + predicate.asyncpg_sql + """
                AND c.embedding_rag_v1 IS NOT NULL
                AND c.embedding_model_version = $9 AND c.embedding_dimension = 1024
                AND m.index_version = $10 AND m.profile_version = $11
                AND m.corpus_version = $12 AND m.artifact_sha256 = $13
                AND m.build_status IN ('READY', 'ACTIVE') AND m.validated_at IS NOT NULL
                AND p.activated_at >= m.validated_at AND p.activated_at = $14
                AND m.embedding_model_id = 'BAAI/bge-m3'
                AND m.embedding_model_revision = '5617a9f61b028005a4858fdac845db406aefb181'
                AND m.dimension = 1024 AND m.normalization = 'l2' AND m.distance_metric = 'cosine'
            ORDER BY distance ASC, c.id ASC
            LIMIT $2
        """, literal, top_k, *predicate.values,
            self._profile.embedding_model_id + "@" + self._profile.embedding_model_revision,
            self._manifest.index_version, self._profile.profile_version,
            self._manifest.corpus_version, self._manifest.artifact_sha256, self._pointer.activated_at)
        return authorized_rows_to_candidates(rows, self._issuer, branch="vector")
