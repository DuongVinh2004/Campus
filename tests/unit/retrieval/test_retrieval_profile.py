from dataclasses import FrozenInstanceError, replace
import math

import pytest

from campus247.application.retrieval.profile import (
    PROFILE_VERSION, RetrievalProfile, RetrievalProfileError, RuntimeRetrievalBinding, load_retrieval_profile,
)
from campus247.bootstrap.settings import Settings


def test_accepted_profile_preserves_documented_values_and_is_immutable():
    profile = load_retrieval_profile()
    assert profile.profile_version == PROFILE_VERSION
    assert (profile.embedding_model_id, profile.embedding_model_revision, profile.embedding_dimension) == (
        "BAAI/bge-m3", "5617a9f61b028005a4858fdac845db406aefb181", 1024)
    assert (profile.reranker_model_id, profile.reranker_model_revision) == (
        "BAAI/bge-reranker-v2-m3", "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e")
    assert (profile.lexical_k, profile.semantic_k, profile.rrf_constant, profile.fusion_k) == (30, 30, 60, 20)
    assert (profile.rerank_input_limit, profile.rerank_k, profile.context_k, profile.context_token_budget) == (20, 8, 8, 6000)
    assert (profile.lexical_timeout_ms, profile.semantic_timeout_ms, profile.reranker_timeout_ms, profile.overall_timeout_ms) == (400, 700, 700, 1800)
    assert (profile.evidence_support_threshold, profile.evidence_repair_limit, profile.transient_retry_limit) == (0.78, 1, 1)
    assert (profile.recall_at_10_min, profile.critical_subgroup_recall_min, profile.citation_precision_min,
            profile.grounded_correctness_min, profile.exact_identifier_recall_at_5_min, profile.conflict_handling_min) == (0.90, 0.85, 0.95, 0.90, 0.98, 0.98)
    assert (profile.invalid_source_leakage_max, profile.latency_p95_max_ms, profile.latency_p99_max_ms,
            profile.error_rate_exclusive_max, profile.performance_load_profile) == (0, 1800, 3000, 0.01, "TP-RAG")
    assert RetrievalProfile.from_mapping(profile.to_dict()) == profile
    with pytest.raises(FrozenInstanceError):
        profile.lexical_k = 10
    copied = profile.to_dict()
    copied["lexical_k"] = 10
    assert profile.lexical_k == 30


@pytest.mark.parametrize("field", list(load_retrieval_profile().to_dict()))
def test_every_profile_field_is_required(field):
    payload = load_retrieval_profile().to_dict()
    del payload[field]
    with pytest.raises(RetrievalProfileError, match="complete"):
        RetrievalProfile.from_mapping(payload)


@pytest.mark.parametrize("field,value", [
    ("embedding_dimension", 1536), ("embedding_model_revision", "main"), ("reranker_model_revision", "main"),
    ("lexical_k", "30"), ("lexical_k", 30.0), ("transient_retry_limit", True),
    ("invalid_source_leakage_max", False), ("evidence_support_threshold", math.nan),
    ("evidence_support_threshold", math.inf), ("evidence_support_threshold", 0.77),
    ("branch_fallback", "allow_all"), ("overall_timeout_ms", 3000), ("profile_version", "rag-prod-v2.0.0"),
])
def test_profile_changes_cannot_reuse_an_accepted_version(field, value):
    with pytest.raises(RetrievalProfileError, match="accepted"):
        replace(load_retrieval_profile(), **{field: value})


@pytest.mark.parametrize("version", ["", " rag-prod-v1.0.0", "rag-prod-v1.0.1", "fake", None, 1])
def test_unknown_profile_fails_configuration_loading(version):
    with pytest.raises(RetrievalProfileError):
        load_retrieval_profile(version)
    with pytest.raises(ValueError):
        Settings(_env_file=None, RETRIEVAL_PROFILE_VERSION=version)


def test_settings_load_profile_without_network_and_revalidate_assignment(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "testing")
    monkeypatch.setenv("RETRIEVAL_PROFILE_VERSION", PROFILE_VERSION)
    settings = Settings(_env_file=None)
    assert settings.retrieval_profile == load_retrieval_profile()
    settings.RETRIEVAL_PROFILE_VERSION = "unapproved"
    with pytest.raises(RetrievalProfileError):
        _ = settings.retrieval_profile


def binding():
    p = load_retrieval_profile()
    # Synthetic metadata for a contract test, not model quality/release evidence.
    return RuntimeRetrievalBinding("synthetic-index-v1", p.profile_version, p.embedding_model_id,
        p.embedding_model_revision, p.embedding_dimension, p.normalization, p.distance_metric,
        "a" * 64, p.reranker_model_id, p.reranker_model_revision, "b" * 64)


def validate(value, **overrides):
    expected = {"expected_index_version": "synthetic-index-v1",
        "expected_embedding_artifact_sha256": "a" * 64, "expected_reranker_artifact_sha256": "b" * 64}
    expected.update(overrides)
    load_retrieval_profile().validate_runtime_binding(value, **expected)


def test_runtime_binding_matches_independently_supplied_activation_metadata():
    validate(binding())


@pytest.mark.parametrize("field,value", [
    ("index_version", ""), ("index_version", "different-index"), ("profile_version", "different-profile"),
    ("embedding_model_id", "test-only/deterministic-fake"), ("embedding_model_revision", "main"),
    ("embedding_dimension", 1536), ("embedding_dimension", 1024.0), ("normalization", "none"),
    ("distance_metric", "l2"), ("reranker_model_revision", "main"), ("reranker_model_id", "fake"),
    ("embedding_artifact_sha256", "c" * 64), ("embedding_artifact_sha256", "0" * 64),
    ("reranker_artifact_sha256", ""), ("reranker_artifact_sha256", "B" * 64),
])
def test_index_model_and_artifact_mismatches_fail_closed(field, value):
    with pytest.raises(RetrievalProfileError):
        validate(replace(binding(), **{field: value}))


def test_missing_activation_metadata_and_arbitrary_dict_bindings_are_rejected():
    with pytest.raises(RetrievalProfileError, match="typed"):
        validate({"index_version": "synthetic-index-v1"})
    with pytest.raises(RetrievalProfileError, match="required"):
        validate(binding(), expected_index_version="")
    with pytest.raises(RetrievalProfileError, match="checksum"):
        validate(binding(), expected_embedding_artifact_sha256="")
    payload = load_retrieval_profile().to_dict()
    payload["extra"] = "unapproved"
    with pytest.raises(RetrievalProfileError, match="complete"):
        RetrievalProfile.from_mapping(payload)


def test_bootstrap_loads_profile_configuration_without_activating_live_dependencies(monkeypatch):
    from campus247.bootstrap import app as bootstrap
    # Existing identity composition permits development, not Settings' testing label.
    # Runtime counts/deadlines must wait for SQL filters and canonical retrieval.
    monkeypatch.setattr(bootstrap, "get_settings", lambda: Settings(_env_file=None, ENVIRONMENT="development"))
    monkeypatch.setattr(bootstrap, "VectorSearchAdapter", lambda: object())
    monkeypatch.setattr(bootstrap, "LexicalSearchAdapter", lambda: object())
    monkeypatch.setattr(bootstrap, "HybridSearchAdapter", lambda *args, **kwargs: object())
    monkeypatch.setattr(bootstrap, "CampusAgentWorkflow", lambda **kwargs: object())
    monkeypatch.setattr(bootstrap, "create_llm_gateway", lambda **kwargs: object())
    app = bootstrap.create_app()
    assert app.state.retrieval_profile == load_retrieval_profile()


def test_app_startup_rejects_unknown_profile_before_adapter_construction(monkeypatch):
    from campus247.bootstrap import app as bootstrap
    monkeypatch.setenv("RETRIEVAL_PROFILE_VERSION", "unapproved")
    monkeypatch.setattr(bootstrap, "get_settings", lambda: Settings(_env_file=None, ENVIRONMENT="testing"))
    monkeypatch.setattr(bootstrap, "VectorSearchAdapter", lambda: pytest.fail("must reject before adapter construction"))
    with pytest.raises(ValueError):
        bootstrap.create_app()
