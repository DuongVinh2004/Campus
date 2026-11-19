from __future__ import annotations

from typing import Sequence

from campus247.ports.reranker import RerankRequest, RerankResult, RerankerContractError


class StrictRerankOutputValidator:
    """Reject invalid model output; fallback is an explicit caller policy.

    Returns the original result so model order and diagnostic metadata survive.
    No input text or provenance can be replaced by a reranker response.
    """

    def validate(self, request: RerankRequest, result: RerankResult) -> RerankResult:
        if not isinstance(request, RerankRequest) or not isinstance(result, RerankResult):
            raise RerankerContractError("typed reranker request and result are required")
        if (result.model_id, result.model_revision) != (
            request.profile.model_id, request.profile.model_revision
        ):
            raise RerankerContractError("reranker model or revision mismatch")
        if len(result.ranked) > len(request.candidates):
            raise RerankerContractError("output candidate count exceeds supplied candidates")
        if request.candidates and not result.ranked:
            raise RerankerContractError("non-empty input requires a non-empty ranking")
        allowed = {candidate.chunk_id for candidate in request.candidates}
        seen: set[str] = set()
        for item in result.ranked:
            if item.chunk_id not in allowed:
                raise RerankerContractError("reranker returned a foreign candidate ID")
            if item.chunk_id in seen:
                raise RerankerContractError("reranker returned duplicate candidate IDs")
            seen.add(item.chunk_id)
        return result


class RerankOutputValidator:
    """Legacy tolerant helper; not the production reranker contract validator."""

    def __init__(self, allowlisted_ids: Sequence[str], top_k: int = 5) -> None:
        self._allowlisted_order = list(allowlisted_ids)
        self._allowlist_set = set(allowlisted_ids)
        self._top_k = top_k

    def validate_and_filter(self, candidate_ids: Sequence[str]) -> list[str]:
        valid_ordered: list[str] = []
        seen: set[str] = set()

        for cid in candidate_ids:
            if cid in self._allowlist_set and cid not in seen:
                valid_ordered.append(cid)
                seen.add(cid)

        # Fallback to original order if model output is empty or completely hallucinated
        if not valid_ordered:
            return self._allowlisted_order[: self._top_k]

        return valid_ordered[: self._top_k]
