"""The lost-vector-branch counter: exact counts, rollup lines, and the retrieval hook."""
import asyncio
import logging

import pytest

from campus247.rag_v2.observability import vector_stats
from campus247.rag_v2.observability.vector_stats import VectorStats
from campus247.rag_v2.retrieval.hybrid import retrieve
from campus247.rag_v2.understanding.analyze import analyze
from tests.rag_v2.retrieval.test_hybrid import Index, Reranker, unit


def test_counts_failures_timeouts_and_rate():
    stats = VectorStats(rollup_every=1000)
    stats.record(failed=False, seconds=0.2)
    stats.record(failed=True, timeout=True, seconds=1.0)
    stats.record(failed=True, timeout=False, seconds=0.01)
    stats.record(failed=False, seconds=0.05)
    snap = stats.snapshot()
    assert (snap["retrievals"], snap["failed"], snap["timeouts"]) == (4, 2, 1)
    assert snap["failed_rate"] == 0.5 and snap["vector_ms_max"] == 1000


def test_rollup_line_every_n_retrievals_and_failure_line_without_text(caplog):
    stats = VectorStats(rollup_every=3)
    with caplog.at_level(logging.WARNING, logger="campus247.rag_v2"):
        stats.record(failed=True, timeout=True, seconds=1.0)
        stats.record(failed=False)
        stats.record(failed=False)
    lines = [record.getMessage() for record in caplog.records]
    assert lines[0] == "rag_v2_vector_failed reason=timeout ms=1000"
    assert lines[1] == "rag_v2_vector_stats retrievals=3 failed=1 timeouts=1 failed_rate=0.333 vector_ms_max=1000"
    assert len(lines) == 2


@pytest.fixture
def fresh(monkeypatch):
    stats = VectorStats(rollup_every=1000)
    monkeypatch.setattr(vector_stats, "VECTOR_STATS", stats)
    from campus247.rag_v2.retrieval import hybrid
    monkeypatch.setattr(hybrid, "VECTOR_STATS", stats)
    return stats


U = analyze("Điều kiện bảo lưu học tập là gì?", ())


@pytest.mark.asyncio
async def test_retrieval_counts_a_stalled_vector_branch_as_timeout(fresh):
    index = Index([unit(1)])

    async def stalled(*args, **kwargs):
        await asyncio.sleep(30)

    index.vector = stalled
    result = await asyncio.wait_for(retrieve(U, index, Reranker()), timeout=2)
    assert result.trace["vector_failed"]
    snap = fresh.snapshot()
    assert (snap["retrievals"], snap["failed"], snap["timeouts"]) == (1, 1, 1)
    assert snap["vector_ms_max"] >= 900


@pytest.mark.asyncio
async def test_retrieval_counts_adapter_error_and_success_separately(fresh):
    broken = Index([unit(1)])

    async def boom(*args, **kwargs):
        raise ValueError("embedding unavailable")

    broken.vector = boom
    await retrieve(U, broken, Reranker(), rerank_deadline_s=1)
    await retrieve(U, Index([unit(1)]), Reranker(), rerank_deadline_s=1)
    snap = fresh.snapshot()
    assert (snap["retrievals"], snap["failed"], snap["timeouts"]) == (2, 1, 0)
