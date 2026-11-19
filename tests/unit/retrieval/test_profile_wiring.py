"""Offline synthetic compatibility/wiring; no active index or inference claim."""
import asyncio
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "services/api/src"))

from campus247.application.retrieval.profile import RetrievalProfileError, RuntimeRetrievalBinding, load_retrieval_profile
from campus247.domain.retrieval import AuthorizedScope, RetrievalContext, SimulationPolicy
from campus247.infrastructure.retrieval.hybrid import HybridSearchAdapter
from campus247.ports.retrieval import ChunkResult


def context():
    return RetrievalContext(AuthorizedScope("synthetic-institution", "HUCE", "synthetic-actor",
        frozenset({"STUDENT"}), frozenset({"STUDENT"}), frozenset({"FIT"}), frozenset({"SYNTHETIC"})),
        "vi", datetime(2026, 10, 4, tzinfo=timezone.utc), SimulationPolicy.DENY, "1" * 32)


def kwargs():
    p = load_retrieval_profile()
    return dict(profile=p, runtime_binding=RuntimeRetrievalBinding("synthetic-index", p.profile_version,
        p.embedding_model_id, p.embedding_model_revision, p.embedding_dimension, p.normalization, p.distance_metric,
        "a" * 64, p.reranker_model_id, p.reranker_model_revision, "b" * 64),
        expected_index_version="synthetic-index", expected_embedding_artifact_sha256="a" * 64,
        expected_reranker_artifact_sha256="b" * 64)


class ForbiddenBranch:
    def search(self, *args, **kwargs):
        pytest.fail("must reject before branch/provider/database access")


@pytest.mark.asyncio
async def test_profile_drives_both_branch_counts_rrf_and_fusion_limit():
    seen = []
    ctx = context()
    class Branch:
        async def search(self, query, *, top_k, context):
            seen.append((top_k, context))
            return [ChunkResult(f"synthetic-{i:02}", "v1", "Synthetic content", "Synthetic / 1", 1.0)
                    for i in range(top_k)]
    results = await HybridSearchAdapter(Branch(), Branch(), **kwargs()).search("synthetic", context=ctx)
    assert seen == [(30, ctx), (30, ctx)]
    assert len(results) == 20 and results[0].score == round(2 / 61, 6)


@pytest.mark.parametrize("field,value", [
    ("profile_version", "unapproved"), ("embedding_dimension", 1536),
    ("embedding_model_revision", "main"), ("reranker_model_revision", "main"),
    ("index_version", "wrong-index"), ("embedding_artifact_sha256", "c" * 64),
    ("reranker_artifact_sha256", "c" * 64),
])
@pytest.mark.asyncio
async def test_runtime_metadata_mismatch_fails_before_branch_access(field, value):
    args = kwargs()
    args["runtime_binding"] = replace(args["runtime_binding"], **{field: value})
    with pytest.raises(RetrievalProfileError):
        await HybridSearchAdapter(ForbiddenBranch(), ForbiddenBranch(), **args).search("synthetic", context=context())


@pytest.mark.parametrize("field", ["runtime_binding", "expected_index_version",
    "expected_embedding_artifact_sha256", "expected_reranker_artifact_sha256"])
@pytest.mark.asyncio
async def test_missing_runtime_or_independent_activation_metadata_fails_closed(field):
    args = kwargs()
    args.pop(field)
    with pytest.raises(RetrievalProfileError):
        await HybridSearchAdapter(ForbiddenBranch(), ForbiddenBranch(), **args).search("synthetic", context=context())


@pytest.mark.parametrize("override", [{"fusion_k": 10}, {"k": 30}, {"k": 60.0}, {"fusion_k": True}])
def test_production_profile_does_not_accept_count_or_rrf_overrides(override):
    with pytest.raises(RetrievalProfileError):
        HybridSearchAdapter(ForbiddenBranch(), ForbiddenBranch(), **kwargs(), **override)


@pytest.mark.asyncio
async def test_missing_context_and_per_call_count_override_fail_before_branches():
    adapter = HybridSearchAdapter(ForbiddenBranch(), ForbiddenBranch(), **kwargs())
    with pytest.raises(RetrievalProfileError):
        await adapter.search("synthetic")
    with pytest.raises(RetrievalProfileError):
        await adapter.search("synthetic", top_k=10, context=context())


@pytest.mark.asyncio
async def test_lexical_deadline_cancels_and_joins_both_branches():
    completed = []
    class Slow:
        def __init__(self, name): self.name = name
        async def search(self, *args, **kwargs):
            try:
                await asyncio.sleep(5)
            finally:
                completed.append(self.name)
    with pytest.raises(TimeoutError):
        await HybridSearchAdapter(Slow("vector"), Slow("lexical"), **kwargs()).search("synthetic", context=context())
    assert set(completed) == {"vector", "lexical"}


@pytest.mark.asyncio
async def test_bootstrap_passes_the_immutable_profile_and_has_no_top10_override(monkeypatch):
    from campus247.bootstrap import app as bootstrap
    from campus247.bootstrap.settings import Settings
    captured = {}
    class Hybrid:
        def __init__(self, vector, lexical, **kw): captured.update(kw)
        async def search(self, query, **kw):
            assert set(kw) == {"context"}
            captured["context"] = kw["context"]
            return []
    class Workflow:
        def __init__(self, **kw): captured["callback"] = kw["context_search_fn"]
    monkeypatch.setattr(bootstrap, "get_settings", lambda: Settings(_env_file=None, ENVIRONMENT="development"))
    monkeypatch.setattr(bootstrap, "HybridSearchAdapter", Hybrid)
    monkeypatch.setattr(bootstrap, "CampusAgentWorkflow", Workflow)
    monkeypatch.setattr(bootstrap, "create_llm_gateway", lambda **kw: object())
    app = bootstrap.create_app()
    assert captured["profile"] is app.state.retrieval_profile
    assert await captured["callback"]("synthetic", context()) == []
    assert captured["context"].authorized_scope.actor_id == "synthetic-actor"
