"""Contract regression only; live HUCE measurements are retained separately."""
import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace as NS

import pytest

from campus247.infrastructure.knowledge import runtime as module


@pytest.mark.parametrize("score,query,evidence,expected", [
    (-10.364471435546875,"Contract relevance question","Contract fixture for relevance gating only.",0),
    (module.MIN_RERANK_LOGIT,"Contract relevance question","Contract fixture for relevance gating only.",0),
    (module.MIN_RERANK_LOGIT + 0.01,"Contract relevance question","Contract fixture for relevance gating only.",1),
    (0.0,"Contract relevance question","Contract fixture for relevance gating only.",1),
    (4.016305923461914,"Contract relevance question","Contract fixture for relevance gating only.",1),
    (4.0,"Contract tuition 2024-2025","Contract tuition academic year 2026-2027",0),
    (4.0,"Contract tuition 2026–2027","Contract tuition academic year 2026-2027",1),
    (4.0,"Không mang thẻ K68 năm học 2026-2027 thì có tự động bị từ chối trong mọi trường hợp không?",
        "Synthetic original evidence for K68, academic year 2026-2027, retaining every condition.",1)])
def test_logits_at_or_below_the_measured_threshold_never_enter_evidence(monkeypatch,score,query,evidence,expected):
    row={"id":"chunk","source_id":"source","document_version_id":"version","content_checksum":"a"*64,
         "content_text":evidence,"rerank_text":evidence,
         "owner_unit":"Test","title":"Contract test","canonical_uri":"https://example.invalid/test","version_label":"test",
         "section_path":"test","page_start":1,"page_end":1,"effective_from":datetime.now(UTC),"effective_until":None}
    class Conn:
        @asynccontextmanager
        async def transaction(self,**kwargs): yield self
        async def fetchval(self,*args): return True
        async def fetch(self,*args): return [{"version_id":"version"}]
        async def execute(self,*args): pass
    class Pool:
        @asynccontextmanager
        async def acquire(self): yield Conn()
    async def embed(values): return NS(vectors=[NS(values=[1.0])])
    async def rerank(request):
        from campus247.application.retrieval.conditional_query import conditional_retrieval_question
        assert request[1].text == conditional_retrieval_question(query)
        return NS(ranked=[NS(chunk_id="chunk",score=score)])
    async def version(*args): return {"processor_profile":"legacy-test"}
    async def release_versions(*args): return [{"version_id":"version", "processor_profile":"legacy-test", "title":"Contract test"}]
    runtime=module.KnowledgeReleaseRuntime(NS(repo=NS(pool=Pool(),tenant="test",campus="HUCE",version=version,release_versions=release_versions),model_budget=lambda:{"remaining_inferences":None}),
        NS(_embed=embed),NS(rerank=rerank,profile=None),instance_id="test")
    runtime.compiler=NS(compile=lambda context:NS(values=[]))
    async def rows(*args,**kwargs):
        assert kwargs["scope_query"] == query  # Full negation, time and cohort remain authoritative.
        return [row]
    runtime._rows=rows
    async def editions(*args):
        assert args[2] == query
        return None, {}
    runtime._edition_selection=editions  # This fixture isolates the relevance-logit gate.
    monkeypatch.setattr(module,"authorized_rows_to_candidates",lambda *args,**kwargs:())
    monkeypatch.setattr(module,"RerankRequest",lambda *args:args)
    result=asyncio.run(runtime._search(query,None,{"release_id":"test"},preview=True))
    assert len(result)==expected
    if result:
        assert result[0]["content_text"] == evidence


def test_empty_authorized_release_spends_no_model_calls():
    class Conn:
        async def fetchval(self,*args): return False
    class Pool:
        @asynccontextmanager
        async def acquire(self): yield Conn()
    async def forbidden(*args): raise AssertionError("Empty release invoked a model")
    runtime=module.KnowledgeReleaseRuntime(NS(repo=NS(pool=Pool(),tenant="test",campus="HUCE")),
        NS(_embed=forbidden),NS(rerank=forbidden),instance_id="test")
    runtime.compiler=NS(compile=lambda context:NS(values=[]))
    assert asyncio.run(runtime._search("No eligible documents",None,{"release_id":"test"},preview=True))==[]


def test_insufficient_remaining_budget_prevents_partial_model_work():
    from campus247.application.knowledge.platform_models import PlatformError
    class Conn:
        async def fetchval(self,*args): return True
    class Pool:
        @asynccontextmanager
        async def acquire(self): yield Conn()
    async def forbidden(*args): raise AssertionError("Insufficient budget invoked a model")
    platform=NS(repo=NS(pool=Pool(),tenant="test",campus="HUCE"),model_budget=lambda:{"remaining_inferences":3})
    runtime=module.KnowledgeReleaseRuntime(platform,NS(_embed=forbidden),NS(rerank=forbidden),instance_id="test")
    runtime.compiler=NS(compile=lambda context:NS(values=[]))
    with pytest.raises(PlatformError,match="MODEL_BUDGET_UNAVAILABLE"):
        asyncio.run(runtime._search("Budget-limited request",None,{"release_id":"test"},preview=True))


def test_focused_search_keeps_original_academic_year_for_row_applicability(monkeypatch):
    from campus247.application.knowledge import source_snapshot
    from campus247.application.knowledge.platform_models import digest
    text = "Ảnh 4x6\nSĐT bố/ mẹ:........"
    row = {"id": "chunk", "document_version_id": "version", "processor_profile": "contract-fixture",
        "content_text": text, "content_checksum": digest(text.encode()), "index_text": text,
        "input_sha256": digest(text.encode())}
    scope = {"kind": "INFORMATION_SNAPSHOT", "reviewed_at": datetime.now(UTC).isoformat(),
        "academic_years": ["2025-2026"], "requires_academic_year": True,
        "_evidence_hashes": {row["content_checksum"]}}
    class Conn:
        async def fetch(self, sql, *values):
            assert values[0] == module.normalized("Cần ảnh cỡ nào?")
            return [dict(row)]
    async def version(*args): return {"metadata_sha256": "bound"}
    async def snapshot(*args): return scope
    monkeypatch.setattr(module, "metadata_binding", lambda version: "bound")
    monkeypatch.setattr(source_snapshot, "read_snapshot", snapshot)
    runtime = module.KnowledgeReleaseRuntime(NS(repo=NS(tenant="test", campus="HUCE", version=version)),
        None, None, instance_id="test")
    runtime.compiler = NS(compile=lambda context: NS(values=[]))
    async def editions(*args): return None, {}
    runtime._edition_selection = editions  # Legacy original-snapshot scope fixture.
    async def search(original):
        return await runtime._rows(Conn(), "Cần ảnh cỡ nào?", None, "release", scope_query=original)
    assert len(asyncio.run(search("Mẫu học bổng năm học 2025-2026, cần ảnh cỡ nào?"))) == 1
    assert asyncio.run(search("Mẫu học bổng năm học 2026-2027, cần ảnh cỡ nào?")) == []
    assert asyncio.run(search(None)) == []
