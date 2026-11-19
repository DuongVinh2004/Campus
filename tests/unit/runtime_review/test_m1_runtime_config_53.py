"""Explicit deadline propagation and unchanged grounding/index identity."""
from dataclasses import replace
import sys
from pathlib import Path

import pytest

from campus247.application.retrieval.profile import load_retrieval_profile, RetrievalProfileError
from campus247.application.retrieval.runtime_config import RuntimeDeadlines
from campus247.application.retrieval.runtime_config import validate_effective_profile
from campus247.bootstrap.settings import Settings

HERE = Path(__file__).resolve().parents[3] / "infra/local/rag-fixture"
sys.path.insert(0, str(HERE))


def test_effective_config_propagates_without_modifying_baseline():
    baseline = load_retrieval_profile()
    timing = RuntimeDeadlines("synthetic-config-test")
    effective = timing.apply(baseline)
    assert (effective.semantic_timeout_ms, effective.reranker_timeout_ms, effective.overall_timeout_ms) == (1400, 1400, 3300)
    assert baseline.overall_timeout_ms == 1800
    changed = {k for k,v in baseline.to_dict().items() if getattr(effective, k) != v}
    assert changed == {"semantic_timeout_ms", "reranker_timeout_ms", "overall_timeout_ms"}
    assert effective.evidence_support_threshold == .78
    configured = Settings(_env_file=None, ENVIRONMENT="testing", DEMO_MODE=True, RETRIEVAL_RUNTIME_DEADLINES=timing)
    assert configured.retrieval_profile == effective
    validate_effective_profile(effective)
    validate_effective_profile(baseline)


def test_revalidation_rejects_even_forged_overlay_without_relaxing_grounding():
    effective = RuntimeDeadlines("test").apply(load_retrieval_profile())
    object.__setattr__(effective, "evidence_support_threshold", .77)
    with pytest.raises(RetrievalProfileError):
        validate_effective_profile(effective)


@pytest.mark.parametrize("updates", [{"native_ms": True}, {"native_ms": 0}, {"native_ms": 5000}, {"adapter_ms": 1100}, {"retrieval_ms": 1800}, {"native_batch_seconds": 0}, {"controller_seconds": 500}, {"revision": ""}, {"adapter_ms": float("inf")}])
def test_invalid_deadlines_fail_before_runtime(updates):
    with pytest.raises(RetrievalProfileError):
        replace(RuntimeDeadlines("test"), **updates)


@pytest.mark.parametrize("updates", [{"ENVIRONMENT": "production"}, {"ENVIRONMENT": "staging"}, {"DEMO_MODE": False}])
def test_overlay_is_scoped_to_local_synthetic(updates):
    with pytest.raises(ValueError):
        Settings(_env_file=None, **dict({"ENVIRONMENT": "testing", "DEMO_MODE": True, "RETRIEVAL_RUNTIME_DEADLINES": RuntimeDeadlines("test")}, **updates))


def test_overlay_cannot_change_evidence_or_model_identity():
    effective = RuntimeDeadlines("test").apply(load_retrieval_profile())
    for updates in ({"evidence_support_threshold": .77}, {"reranker_model_revision": "main"}, {"context_token_budget": 1}, {"semantic_timeout_ms": 900}):
        with pytest.raises(RetrievalProfileError):
            replace(effective, **updates)


def test_bootstrap_real_adapter_construction_uses_same_effective_profile(monkeypatch):
    from campus247.bootstrap.app import create_app
    from campus247.infrastructure.retrieval.hybrid import HybridSearchAdapter
    from campus247.application.retrieval.profile import RetrievalProfileError
    timing = RuntimeDeadlines("bootstrap-test")
    settings = Settings(_env_file=None, ENVIRONMENT="development", DEMO_MODE=True, RETRIEVAL_RUNTIME_DEADLINES=timing)
    app = create_app(runtime_settings=settings, llm_gateway=object())
    assert app.state.retrieval_profile.runtime_deadlines == timing
    with pytest.raises(RetrievalProfileError):
        HybridSearchAdapter(object(), object(), profile=settings.retrieval_profile, fusion_k=1)


def test_new_journal_keeps_eight_failed_users_and_rejects_changed_history():
    import m1_chat_journal_20261012_53 as journal
    import json
    original = journal.original()
    journal.validate(original, original)
    target = [r for r in original["message"] if r["conversation_id"] == journal.CONVERSATION]
    assert len(target) == 8 and all(r["sender_type"] == "USER" for r in target)
    changed = json.loads(json.dumps(original))
    changed["message"][0]["content_redacted"] = "changed history"
    with pytest.raises(AssertionError):
        journal.validate(changed, original)


@pytest.mark.asyncio
async def test_both_sql_adapters_accept_overlay_and_preserve_scope_and_index_checks():
    import importlib.util
    from campus247.infrastructure.retrieval.postgres_vector import PostgresVectorSearchAdapter
    from campus247.infrastructure.retrieval.postgres_lexical import PostgresLexicalSearchAdapter
    from campus247.application.retrieval.filters import RetrievalFilterError
    fixture_path = Path(__file__).resolve().parents[1] / "retrieval/test_postgres_vector_adapter.py"
    spec = importlib.util.spec_from_file_location("overlay_adapter_fixture53", fixture_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    config, context, calls, embedded, _ = module.fixture()
    config["profile"] = RuntimeDeadlines("test").apply(config["profile"])
    config["embedding_profile"] = replace(config["embedding_profile"], timeout_ms=1400)
    vector = PostgresVectorSearchAdapter(**config)
    lexical_config = {k:v for k,v in config.items() if k not in {"embedding_profile", "embed_query"}}
    lexical = PostgresLexicalSearchAdapter(**lexical_config)
    result = await vector.search_candidates("synthetic", context=context)
    assert result[0].source_id == "synthetic-source" and embedded == ["synthetic"]
    assert calls and "m.profile_version" in calls[0][0]
    with pytest.raises(RetrievalFilterError):
        await lexical.search_candidates("synthetic", context=None)
    lexical_config["expected_index_version"] = "foreign-index"
    with pytest.raises(RetrievalFilterError):
        PostgresLexicalSearchAdapter(**lexical_config)
