"""Provenance-preserving lexical branch bound to the same active index as vector."""
import asyncio

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
from campus247.infrastructure.retrieval.postgres_vector import (
    authorized_rows_to_candidates,
)


class PostgresLexicalSearchAdapter:
    def __init__(self, *, pool, profile: RetrievalProfile, manifest: EmbeddingIndexManifest,
                 pointer: ActiveIndexPointer, expected_index_version: str, expected_corpus_version: str,
                 expected_artifact_sha256: str, filter_compiler: RetrievalFilterCompiler, issuer_resolver):
        if (pool is None or not isinstance(profile, RetrievalProfile)
                or not isinstance(manifest, EmbeddingIndexManifest) or not isinstance(pointer, ActiveIndexPointer)
                or not isinstance(filter_compiler, RetrievalFilterCompiler) or not callable(issuer_resolver)):
            raise RetrievalFilterError("complete explicit lexical dependencies required")
        validate_effective_profile(profile)
        if (manifest.profile_version != profile.profile_version or pointer.profile_version != profile.profile_version
                or pointer.index_version != expected_index_version or manifest.index_version != expected_index_version
                or manifest.corpus_version != expected_corpus_version or manifest.artifact_sha256 != expected_artifact_sha256
                or (manifest.embedding_model_id, manifest.embedding_model_revision, manifest.dimension,
                    manifest.normalization, manifest.distance_metric) !=
                   (profile.embedding_model_id, profile.embedding_model_revision, profile.embedding_dimension,
                    profile.normalization, profile.distance_metric)
                or manifest.build_status not in (BuildStatus.READY, BuildStatus.ACTIVE)
                or manifest.validated_at is None or pointer.activated_at < manifest.validated_at):
            raise RetrievalFilterError("lexical active index compatibility rejected")
        self._pool, self._profile, self._manifest, self._pointer = pool, profile, manifest, pointer
        self._compiler, self._issuer = filter_compiler, issuer_resolver

    async def search_candidates(self, query_text, top_k=30, *, context=None):
        predicate = self._compiler.compile(context)
        if type(top_k) is not int or not 1 <= top_k <= self._profile.lexical_k:
            raise RetrievalFilterError("lexical limit outside approved profile")
        if not isinstance(query_text, str) or not query_text.strip():
            raise RetrievalFilterError("non-empty lexical query required")
        async with asyncio.timeout(self._profile.lexical_timeout_ms / 1000):
            if hasattr(self._pool, "acquire"):
                async with self._pool.acquire() as conn:
                    return await self._fetch(conn, query_text.strip(), top_k, predicate)
            return await self._fetch(self._pool, query_text.strip(), top_k, predicate)

    async def _fetch(self, conn, query_text, top_k, predicate):
        rows = await conn.fetch("""
            WITH lexical_query AS (
                -- lexical-natural-v1: conversational words must not turn
                -- candidate recall into an all-words conjunction. Explicit
                -- web-search phrases/negation/operators keep their semantics.
                SELECT CASE WHEN $1 ~ '"|(^|[[:space:]])-|[[:space:]]OR[[:space:]]'
                    THEN websearch_to_tsquery('simple', $1)
                    ELSE COALESCE((SELECT string_agg(quote_literal(term), ' | ')::tsquery
                        FROM unnest(tsvector_to_array(to_tsvector('simple', $1))) AS terms(term)), ''::tsquery)
                    END AS query
            )
            SELECT c.id, c.document_version_id, c.content_text, c.content_checksum,
                   c.section_path, c.page_start, c.page_end, s.id AS source_id,
                   s.title, s.canonical_uri, s.is_synthetic, v.effective_from, v.effective_until,
                   v.version_label, v.status AS document_status, s.approval_status,
                   ts_rank_cd(c.content_tsv, q.query) AS rank_score
            FROM knowledge_chunk c
            CROSS JOIN lexical_query q
            JOIN document_version v ON v.id = c.document_version_id
            JOIN knowledge_source s ON s.id = v.knowledge_source_id
            JOIN embedding_index_manifest m ON m.index_version = v.index_version
            JOIN embedding_index_active_pointer p ON p.index_version = m.index_version
                AND p.profile_version = m.profile_version
            WHERE """ + predicate.asyncpg_sql + """
                AND m.index_version = $9 AND m.profile_version = $10
                AND m.corpus_version = $11 AND m.artifact_sha256 = $12
                AND m.build_status IN ('READY', 'ACTIVE') AND m.validated_at IS NOT NULL
                AND p.activated_at >= m.validated_at AND p.activated_at = $13
                AND c.content_tsv @@ q.query
            ORDER BY rank_score DESC, c.id ASC
            LIMIT $2
        """, query_text, top_k, *predicate.values, self._manifest.index_version, self._profile.profile_version,
            self._manifest.corpus_version, self._manifest.artifact_sha256, self._pointer.activated_at)
        return authorized_rows_to_candidates(rows, self._issuer, branch="lexical")
