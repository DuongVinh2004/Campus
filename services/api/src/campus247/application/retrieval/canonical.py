"""Typed canonical fusion/reranking/context; readiness is established externally.

Branches must supply prefiltered authorized candidates from the same immutable
index tuple. This service does not turn client claims into trusted context or
authorize a runtime. Missing/failed branches and reranker failures propagate:
the accepted degraded modes require separate evaluation evidence.
"""
from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass, replace
from time import monotonic

from campus247.application.retrieval.identifiers import (
    matches_requested_document,
    requested_identifiers,
)
from campus247.application.retrieval.profile import (
    RetrievalProfile,
    RuntimeRetrievalBinding,
)
from campus247.application.retrieval.rerank import StrictRerankOutputValidator
from campus247.domain.retrieval import (
    RetrievalCandidate,
    RetrievalContext,
    RetrievalQuery,
)
from campus247.ports.reranker import (
    RerankerContractError,
    RerankerProfile,
    RerankRequest,
)


class CanonicalRetrievalError(ValueError):
    pass


@dataclass(frozen=True)
class CanonicalContext:
    candidates: tuple[RetrievalCandidate, ...]
    token_count: int
    lexical_count: int
    vector_count: int
    fused_count: int
    reranked_count: int
    profile_version: str
    index_version: str
    total_ms: float


class CanonicalRetrievalService:
    def __init__(self, *, profile: RetrievalProfile, binding: RuntimeRetrievalBinding,
                 expected_index_version: str, expected_embedding_artifact_sha256: str,
                 expected_reranker_artifact_sha256: str, lexical, vector, reranker,
                 token_counter, tokenizer_model_id: str, tokenizer_model_revision: str):
        if not isinstance(profile, RetrievalProfile):
            raise CanonicalRetrievalError("approved typed retrieval profile required")
        profile.validate_runtime_binding(binding, expected_index_version=expected_index_version,
            expected_embedding_artifact_sha256=expected_embedding_artifact_sha256,
            expected_reranker_artifact_sha256=expected_reranker_artifact_sha256)
        expected = RerankerProfile(profile.reranker_model_id, profile.reranker_model_revision,
                                   profile.rerank_input_limit, profile.reranker_timeout_ms)
        if (getattr(reranker, "profile", None) != expected or not callable(getattr(reranker, "rerank", None))
                or not callable(lexical) or not callable(vector) or not callable(token_counter)
                or (tokenizer_model_id, tokenizer_model_revision) !=
                (profile.embedding_model_id, profile.embedding_model_revision)):
            raise CanonicalRetrievalError("complete exact branch/reranker/tokenizer bindings required")
        self._profile, self._binding = profile, binding
        self._lexical, self._vector, self._reranker, self._tokens = lexical, vector, reranker, token_counter

    def _count(self, text):
        count = self._tokens(text)
        if type(count) is not int or count < 0 or (text and count == 0):
            raise CanonicalRetrievalError("tokenizer output rejected")
        return count

    def _fuse(self, lexical, vector):
        profile = self._profile
        records, ranks, scores = {}, {}, {}
        for branch, values, limit in (("lexical", lexical, profile.lexical_k), ("vector", vector, profile.semantic_k)):
            if (not isinstance(values, (tuple, list)) or len(values) > limit
                    or any(not isinstance(c, RetrievalCandidate) for c in values)):
                raise CanonicalRetrievalError("typed bounded authorized branch candidates required")
            seen = set()
            for rank, candidate in enumerate(values, 1):
                cid = candidate.chunk_id
                if cid in seen:
                    raise CanonicalRetrievalError("branch duplicate IDs rejected")
                seen.add(cid)
                if hashlib.sha256(candidate.content_text.encode()).hexdigest() != candidate.quote_span_hash:
                    raise CanonicalRetrievalError("candidate checksum rejected")
                stripped = replace(candidate, lexical_rank=None, vector_rank=None, fused_score=None, rerank_score=None)
                if cid in records and records[cid] != stripped:
                    raise CanonicalRetrievalError("cross-branch provenance/content drift rejected")
                records[cid] = stripped
                ranks.setdefault(cid, {})[branch] = rank
                scores[cid] = scores.get(cid, 0) + 1 / (profile.rrf_constant + rank)
        ordered = sorted(scores, key=lambda cid: (-scores[cid], cid))[:profile.fusion_k]
        return tuple(replace(records[cid], lexical_rank=ranks[cid].get("lexical"),
            vector_rank=ranks[cid].get("vector"), fused_score=scores[cid]) for cid in ordered)

    async def retrieve(self, query: RetrievalQuery, context: RetrievalContext) -> CanonicalContext:
        if not isinstance(query, RetrievalQuery) or not isinstance(context, RetrievalContext):
            raise CanonicalRetrievalError("typed query and trusted context required")
        RetrievalContext.from_dict(context.to_dict())
        profile, started = self._profile, monotonic()
        async def branch(call, limit, timeout_ms):
            async with asyncio.timeout(timeout_ms / 1000):
                return await call(query.text, top_k=limit, context=context)
        async with asyncio.timeout(profile.overall_timeout_ms / 1000):
            tasks = [asyncio.create_task(branch(self._lexical, profile.lexical_k, profile.lexical_timeout_ms)),
                     asyncio.create_task(branch(self._vector, profile.semantic_k, profile.semantic_timeout_ms))]
            try:
                lexical, vector = await asyncio.gather(*tasks)
            finally:
                for task in tasks:
                    if not task.done(): task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
            identifiers = requested_identifiers(query)
            if identifiers:
                lexical = tuple(candidate for candidate in lexical if matches_requested_document(candidate, identifiers))
                vector = tuple(candidate for candidate in vector if matches_requested_document(candidate, identifiers))
            fused = self._fuse(lexical, vector)
            ranked = ()
            if fused:
                request = RerankRequest(self._reranker.profile, query, context, fused)
                async with asyncio.timeout(profile.reranker_timeout_ms / 1000):
                    result = await self._reranker.rerank(request)
                StrictRerankOutputValidator().validate(request, result)
                if len(result.ranked) != len(fused):
                    raise RerankerContractError("canonical reranker must score every supplied candidate")
                # Do not accept a model-provided order that disagrees with its
                # scores. Preserve all original content/provenance by chunk ID.
                order = sorted(result.ranked, key=lambda score: (-score.score, score.chunk_id))
                records = {c.chunk_id: c for c in fused}
                ranked = tuple(replace(records[s.chunk_id], rerank_score=s.score) for s in order)
            selected, section_counts = [], {}
            for candidate in ranked[:profile.rerank_k]:
                key = (candidate.source_id, candidate.document_version_id, candidate.section_path)
                if section_counts.get(key, 0) >= profile.near_duplicate_section_limit:
                    continue
                if self._count(candidate.content_text) > 900:
                    raise CanonicalRetrievalError("chunk exceeds embedding tokenizer hard limit")
                proposed = "\n\n".join(c.content_text for c in [*selected, candidate])
                if self._count(proposed) > profile.context_token_budget:
                    continue
                selected.append(candidate)
                section_counts[key] = section_counts.get(key, 0) + 1
                if len(selected) >= profile.context_k:
                    break
            count = self._count("\n\n".join(c.content_text for c in selected)) if selected else 0
            return CanonicalContext(tuple(selected), count, len(lexical), len(vector), len(fused), len(ranked),
                profile.profile_version, self._binding.index_version, (monotonic() - started) * 1000)
