from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Protocol

from campus247.domain.retrieval import RetrievalCandidate, RetrievalContext, RetrievalQuery


class RerankerContractError(ValueError):
    """Safe, deterministic contract failure; never includes input text or IDs."""


class RerankerTimeoutError(TimeoutError):
    pass


def _identifier(value: str) -> bool:
    return isinstance(value, str) and bool(value) and value == value.strip()


@dataclass(frozen=True)
class RerankerProfile:
    model_id: str
    model_revision: str
    max_candidates: int
    timeout_ms: int

    def __post_init__(self) -> None:
        if not _identifier(self.model_id) or not _identifier(self.model_revision):
            raise RerankerContractError("model ID and exact revision are required")
        for value in (self.max_candidates, self.timeout_ms):
            if type(value) is not int or value <= 0:
                raise RerankerContractError("candidate limit and timeout must be positive integers")


@dataclass(frozen=True)
class RerankRequest:
    profile: RerankerProfile
    query: RetrievalQuery = field(repr=False)
    context: RetrievalContext = field(repr=False)
    candidates: tuple[RetrievalCandidate, ...] = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.profile, RerankerProfile):
            raise RerankerContractError("typed reranker profile is required")
        if not isinstance(self.query, RetrievalQuery) or not isinstance(self.context, RetrievalContext):
            raise RerankerContractError("typed query and trusted retrieval context are required")
        if not isinstance(self.candidates, tuple) or any(
            not isinstance(candidate, RetrievalCandidate) for candidate in self.candidates
        ):
            raise RerankerContractError("immutable typed candidates are required")
        if len(self.candidates) > self.profile.max_candidates:
            raise RerankerContractError("reranker candidate limit exceeded")
        if len({candidate.chunk_id for candidate in self.candidates}) != len(self.candidates):
            raise RerankerContractError("input candidate IDs must be unique")


@dataclass(frozen=True)
class RerankScore:
    chunk_id: str
    score: float

    def __post_init__(self) -> None:
        if not _identifier(self.chunk_id):
            raise RerankerContractError("output candidate ID is required")
        # Cross-encoder logits need not be probabilities. Reject non-finite values,
        # coercible strings and booleans instead of silently normalizing them.
        try:
            finite = type(self.score) in (int, float) and math.isfinite(self.score)
        except OverflowError:
            finite = False
        if not finite:
            raise RerankerContractError("reranker score must be a finite number")


@dataclass(frozen=True)
class RerankResult:
    ranked: tuple[RerankScore, ...]
    model_id: str
    model_revision: str
    latency_ms: int

    def __post_init__(self) -> None:
        if not isinstance(self.ranked, tuple) or any(
            not isinstance(item, RerankScore) for item in self.ranked
        ):
            raise RerankerContractError("immutable typed rankings are required")
        if not _identifier(self.model_id) or not _identifier(self.model_revision):
            raise RerankerContractError("result model ID and revision are required")
        if type(self.latency_ms) is not int or self.latency_ms < 0:
            raise RerankerContractError("reranker latency must be a non-negative integer")


class RerankerPort(Protocol):
    @property
    def profile(self) -> RerankerProfile:
        ...

    async def rerank(self, request: RerankRequest) -> RerankResult:
        """Rank only supplied candidates without changing text or provenance."""
        ...
