"""Accepted immutable retrieval settings; loading does not activate an index/model.

Values come from DOC-RAG-001 v1.1.0 / ADR-005 v1.1.0. Runtime binding
validation must precede retrieval when the active manifest is wired in.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, fields
import re
from types import MappingProxyType


PROFILE_VERSION = "rag-prod-v1.0.0"


class RetrievalProfileError(ValueError):
    """Safe configuration failure without echoing untrusted settings or metadata."""


@dataclass(frozen=True)
class RetrievalProfile:
    profile_version: str
    embedding_model_id: str
    embedding_model_revision: str
    embedding_dimension: int
    normalization: str
    distance_metric: str
    reranker_model_id: str
    reranker_model_revision: str
    lexical_k: int
    semantic_k: int
    rrf_constant: int
    fusion_k: int
    rerank_input_limit: int
    rerank_k: int
    context_k: int
    context_token_budget: int
    near_duplicate_section_limit: int
    lexical_timeout_ms: int
    semantic_timeout_ms: int
    reranker_timeout_ms: int
    overall_timeout_ms: int
    transient_retry_limit: int
    evidence_support_threshold: float
    evidence_repair_limit: int
    branch_fallback: str
    reranker_fallback: str
    recall_at_10_min: float
    critical_subgroup_recall_min: float
    citation_precision_min: float
    grounded_correctness_min: float
    exact_identifier_recall_at_5_min: float
    conflict_handling_min: float
    invalid_source_leakage_max: int
    latency_p95_max_ms: int
    latency_p99_max_ms: int
    error_rate_exclusive_max: float
    performance_load_profile: str

    def __post_init__(self) -> None:
        # Exact type checks also reject True == 1, numeric strings and float ints.
        # A value change under the same version is never an override.
        for name, accepted in _ACCEPTED.items():
            actual = getattr(self, name)
            if type(actual) is not type(accepted) or actual != accepted:
                raise RetrievalProfileError("retrieval profile differs from accepted specification")

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> RetrievalProfile:
        if not isinstance(value, Mapping) or set(value) != {field.name for field in fields(cls)}:
            raise RetrievalProfileError("complete retrieval profile fields are required")
        return cls(**value)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def validate_runtime_binding(
        self, binding: RuntimeRetrievalBinding, *, expected_index_version: str,
        expected_embedding_artifact_sha256: str, expected_reranker_artifact_sha256: str,
    ) -> None:
        """Compare independently trusted activation metadata; never infer an index.

        Expected pointer/checksums must come from the approved activation record,
        not be copied from the returned model/manifest metadata.
        """
        if not isinstance(binding, RuntimeRetrievalBinding):
            raise RetrievalProfileError("typed runtime binding is required")
        if not _identifier(expected_index_version) or not _identifier(binding.index_version):
            raise RetrievalProfileError("active index version is required")
        if binding.index_version != expected_index_version or binding.profile_version != self.profile_version:
            raise RetrievalProfileError("active index or profile version mismatch")
        actual = (binding.embedding_model_id, binding.embedding_model_revision, binding.embedding_dimension,
                  binding.normalization, binding.distance_metric, binding.reranker_model_id, binding.reranker_model_revision)
        expected = (self.embedding_model_id, self.embedding_model_revision, self.embedding_dimension,
                    self.normalization, self.distance_metric, self.reranker_model_id, self.reranker_model_revision)
        if any(type(a) is not type(e) or a != e for a, e in zip(actual, expected)):
            raise RetrievalProfileError("embedding or reranker compatibility mismatch")
        for actual_hash, expected_hash in (
            (binding.embedding_artifact_sha256, expected_embedding_artifact_sha256),
            (binding.reranker_artifact_sha256, expected_reranker_artifact_sha256),
        ):
            if not _checksum(actual_hash) or not _checksum(expected_hash) or actual_hash != expected_hash:
                raise RetrievalProfileError("model artifact checksum missing or mismatched")


@dataclass(frozen=True)
class RuntimeRetrievalBinding:
    index_version: str
    profile_version: str
    embedding_model_id: str
    embedding_model_revision: str
    embedding_dimension: int
    normalization: str
    distance_metric: str
    embedding_artifact_sha256: str
    reranker_model_id: str
    reranker_model_revision: str
    reranker_artifact_sha256: str


def _identifier(value: str) -> bool:
    return isinstance(value, str) and bool(value) and value == value.strip()


def _checksum(value: str) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None and value != "0" * 64


# No mutable registry or runtime override of an accepted version.
_ACCEPTED = MappingProxyType({
    "profile_version": PROFILE_VERSION,
    "embedding_model_id": "BAAI/bge-m3",
    "embedding_model_revision": "5617a9f61b028005a4858fdac845db406aefb181",
    "embedding_dimension": 1024, "normalization": "l2", "distance_metric": "cosine",
    "reranker_model_id": "BAAI/bge-reranker-v2-m3",
    "reranker_model_revision": "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e",
    "lexical_k": 30, "semantic_k": 30, "rrf_constant": 60, "fusion_k": 20,
    "rerank_input_limit": 20, "rerank_k": 8, "context_k": 8, "context_token_budget": 6000,
    "near_duplicate_section_limit": 3,
    "lexical_timeout_ms": 400, "semantic_timeout_ms": 700, "reranker_timeout_ms": 700,
    "overall_timeout_ms": 1800, "transient_retry_limit": 1,
    "evidence_support_threshold": 0.78, "evidence_repair_limit": 1,
    "branch_fallback": "remaining_branch_requires_sql_filter_assurance_and_evidence_gate",
    "reranker_fallback": "rrf_requires_eval_approval_and_degraded_reason",
    "recall_at_10_min": 0.90, "critical_subgroup_recall_min": 0.85,
    "citation_precision_min": 0.95, "grounded_correctness_min": 0.90,
    "exact_identifier_recall_at_5_min": 0.98, "conflict_handling_min": 0.98,
    "invalid_source_leakage_max": 0, "latency_p95_max_ms": 1800, "latency_p99_max_ms": 3000,
    "error_rate_exclusive_max": 0.01, "performance_load_profile": "TP-RAG",
})


def load_retrieval_profile(version: str = PROFILE_VERSION) -> RetrievalProfile:
    if type(version) is not str or version != PROFILE_VERSION:
        raise RetrievalProfileError("unknown or unapproved retrieval profile version")
    return RetrievalProfile.from_mapping(_ACCEPTED)
