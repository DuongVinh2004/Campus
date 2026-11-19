from __future__ import annotations

import asyncio
from typing import Any, Sequence

from campus247.application.retrieval.profile import (
    RetrievalProfile,
    RetrievalProfileError,
    RuntimeRetrievalBinding,
    load_retrieval_profile,
)
from campus247.application.retrieval.runtime_config import validate_effective_profile
from campus247.domain.retrieval import RetrievalContext
from campus247.ports.retrieval import ChunkResult


def hybrid_search(
    vector_results: Sequence[ChunkResult],
    lexical_results: Sequence[ChunkResult],
    fusion_k: int | None = None,
    k: int | None = None,
) -> list[ChunkResult]:
    """Combines vector and lexical retrieval results using Reciprocal Rank Fusion (RRF).

    Formula: rrf_score = sum(1 / (k + rank)) where rank is 1-indexed.
    Deduplicates on chunk_id and returns top fusion_k results ordered by rrf_score DESC.
    """
    profile = load_retrieval_profile()
    fusion_k = profile.fusion_k if fusion_k is None else fusion_k
    k = profile.rrf_constant if k is None else k
    scores: dict[str, float] = {}
    meta: dict[str, tuple[str, str | None, str]] = {}

    for idx, cand in enumerate(vector_results):
        rank = idx + 1
        cid = cand.chunk_id
        scores[cid] = scores.get(cid, 0.0) + (1.0 / (k + rank))
        if cid not in meta:
            meta[cid] = (cand.document_version_id, cand.section_path, cand.content_text)

    for idx, cand in enumerate(lexical_results):
        rank = idx + 1
        cid = cand.chunk_id
        scores[cid] = scores.get(cid, 0.0) + (1.0 / (k + rank))
        if cid not in meta:
            meta[cid] = (cand.document_version_id, cand.section_path, cand.content_text)

    fused_results: list[ChunkResult] = []
    for cid, score in scores.items():
        doc_ver_id, sec_path, text = meta[cid]
        fused_results.append(
            ChunkResult(
                chunk_id=cid,
                document_version_id=doc_ver_id,
                content_text=text,
                section_path=sec_path,
                score=round(score, 6),
            )
        )

    # Sort descending by rrf_score, tie-break by chunk_id ascending
    fused_results.sort(key=lambda c: (-c.score, c.chunk_id))
    return fused_results[:fusion_k]


reciprocal_rank_fusion = hybrid_search


class HybridSearchAdapter:
    """Orchestrates vector and lexical adapters followed by RRF fusion."""

    def __init__(
        self,
        vector_adapter: Any,
        lexical_adapter: Any,
        fusion_k: int | None = None,
        k: int | None = None,
        *,
        profile: RetrievalProfile | None = None,
        runtime_binding: RuntimeRetrievalBinding | None = None,
        expected_index_version: str = "",
        expected_embedding_artifact_sha256: str = "",
        expected_reranker_artifact_sha256: str = "",
    ) -> None:
        self._vector_adapter = vector_adapter
        self._lexical_adapter = lexical_adapter
        self._profile = profile
        accepted = load_retrieval_profile()
        if profile is not None:
            if not isinstance(profile, RetrievalProfile):
                raise RetrievalProfileError("typed retrieval profile required")
            validate_effective_profile(profile)
            if ((fusion_k is not None and (type(fusion_k) is not int or fusion_k != profile.fusion_k))
                    or (k is not None and (type(k) is not int or k != profile.rrf_constant))):
                raise RetrievalProfileError("production profile overrides are forbidden")
            accepted = profile
        self._fusion_k = accepted.fusion_k if fusion_k is None else fusion_k
        self._k = accepted.rrf_constant if k is None else k
        self._runtime_binding = runtime_binding
        self._expected_binding = dict(
            expected_index_version=expected_index_version,
            expected_embedding_artifact_sha256=expected_embedding_artifact_sha256,
            expected_reranker_artifact_sha256=expected_reranker_artifact_sha256,
        )

    async def search(self, query_text: str, top_k: int | None = None, *, context: RetrievalContext | None = None) -> list[ChunkResult]:
        if context is not None and not isinstance(context, RetrievalContext):
            raise ValueError("typed retrieval context required")
        profile = self._profile
        if profile is not None:
            if context is None:
                raise RetrievalProfileError("trusted retrieval context required")
            if top_k is not None:
                raise RetrievalProfileError("branch counts must come from production profile")
            # Caller supplies independently trusted activation metadata. This is
            # a compatibility guard, not storage verification or model activation.
            profile.validate_runtime_binding(self._runtime_binding, **self._expected_binding)
        accepted = profile or load_retrieval_profile()
        vector_k = accepted.semantic_k if top_k is None else top_k
        lexical_k = accepted.lexical_k if top_k is None else top_k
        # Delegate only; both branches receive the identical trusted object.
        binding = {"context": context} if context is not None else {}
        async def branch(adapter, count, timeout_ms):
            return await asyncio.wait_for(
                adapter.search(query_text, top_k=count, **binding), timeout=timeout_ms / 1000,
            )
        if profile is None:
            vec_res, lex_res = await asyncio.gather(
                self._vector_adapter.search(query_text, top_k=vector_k, **binding),
                self._lexical_adapter.search(query_text, top_k=lexical_k, **binding),
            )
        else:
            # Failure cancels and joins the sibling; no unapproved degraded result.
            tasks = [asyncio.create_task(branch(self._vector_adapter, vector_k, profile.semantic_timeout_ms)),
                     asyncio.create_task(branch(self._lexical_adapter, lexical_k, profile.lexical_timeout_ms))]
            try:
                async with asyncio.timeout(profile.overall_timeout_ms / 1000):
                    vec_res, lex_res = await asyncio.gather(*tasks)
            finally:
                for task in tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
        return hybrid_search(vec_res, lex_res, fusion_k=self._fusion_k, k=self._k)
