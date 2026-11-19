import json
from datetime import datetime, timezone

import pytest

from campus247.application.policy_graph.extraction import extract_candidate
from campus247.application.multi_agent.contracts import MultiAgentPolicy
from campus247.application.single_agent.resources import BoundedGateway, RunResources
from campus247.ports.llm import LlmResponse, LlmResponseStatus, TokenUsage
from tests.unit.policy_graph.test_policy_graph import service, proposal
from tests.unit.retrieval.test_public_hybrid_advanced import store, context


class Model:
    def __init__(self, output):
        self.output, self.calls = output, 0
    async def generate(self, request):
        self.calls += 1
        return LlmResponse(LlmResponseStatus.COMPLETED, "scripted", "test-extractor",
            output_text=self.output, usage=TokenUsage(10, 0, 20))


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid", [False, True])
async def test_extraction_is_unpublished_and_retains_exact_model_bytes(tmp_path, invalid):
    s, p = service(tmp_path)
    value = {"nodes": [{"id": n.id, "kind": n.kind, "label": n.label, "operator": n.operator,
        "members": n.members, "source_span_id": "S1"} for n in p.nodes], "edges": [
        {"id": e.id, "from_id": e.from_id, "to_id": e.to_id, "relation": e.relation, "source_span_id": "S1"} for e in p.edges]}
    raw = "  " + json.dumps(value, ensure_ascii=False) if not invalid else '{"nodes": [], "grant_admin": true}'
    model = Model(raw)
    resources = RunResources(MultiAgentPolicy())
    kwargs = dict(gateway=BoundedGateway(model, resources), repository=s.repository,
        source_inputs=[{"span_id": "S1", "source": p.nodes[0].source.model_dump(mode="json"), "scope": p.nodes[0].scope.model_dump(mode="json")}], request_id="extraction-test", author="test-model",
        graph_id="extracted", index_fingerprint="1"*64, source_fingerprint="2"*64, acquired_at=datetime.now(timezone.utc))
    if invalid:
        with pytest.raises(ValueError):
            await extract_candidate(**kwargs)
        assert s.repository.get("extracted") is None
    else:
        candidate, output = await extract_candidate(**kwargs)
        assert candidate.origin == "llm_candidate" and output["raw_model_output"] == raw
        assert s.repository.publication("extracted") is None
        assert s.repository.reviews("extracted") == []
    with s.repository.connect() as db:
        assert db.execute("SELECT raw FROM policy_extraction WHERE request_id='extraction-test'").fetchone()[0] == raw
    assert model.calls == resources.usage["model_calls"] == 1


@pytest.mark.asyncio
async def test_graph_sources_enter_original_hybrid_reranker_without_extra_pairs(store):
    value, _ = store
    from dataclasses import replace
    value.policy = replace(value.policy, fusion_k=4, query_limit=1)
    await value.build_vectors()
    observed = []
    async def relations(query, ctx, seeds):
        observed.append((query, ctx, seeds))
        row = value.rows[1]
        original = await value.read(row["source_id"], row["document_version_id"], row["chunk_id"], context=ctx)
        assert original.content_sha256 == row["quote_span_hash"]
        return [dict(row)]
    rows = await value.search("Học bổng và học phí", context(), relation_lookup=relations)
    assert observed and rows
    requests = value.reranker.requests
    assert sum(len(r.candidates) for r in requests) <= 4
    assert any("Học phí" in c.title for r in requests for c in r.candidates)
    assert all(row["content_text"] in [p["content_text"] for p in value.rows] for row in rows)


@pytest.mark.asyncio
async def test_graph_cannot_replace_source_text_or_leak_foreign_candidate(store):
    value, _ = store
    await value.build_vectors()
    async def relations(query, ctx, seeds):
        return [dict(value.rows[1], content_text="Invented graph summary"),
            dict(value.rows[1], source_id="foreign-source")]
    await value.search("Học phí", context(), relation_lookup=relations)
    assert all("Invented" not in c.content_text and c.source_id != "foreign-source"
        for r in value.reranker.requests for c in r.candidates)


@pytest.mark.asyncio
async def test_legacy_citation_bytes_cannot_be_published_in_current_graph_snapshot(store):
    import hashlib
    from campus247.domain.policy_graph import SourceRef
    from campus247.application.policy_graph.service import PolicyGraphService
    value, _ = store
    old = dict(value.rows[0], document_version_id="retained-old-version", chunk_id="retained-old-chunk",
        content_text="Retained historical citation bytes.")
    old["quote_span_hash"] = hashlib.sha256(old["content_text"].encode()).hexdigest()
    value.legacy_rows.append(old)
    assert await value.read(old["source_id"], old["document_version_id"], old["chunk_id"], context=context()) is not None
    graph = PolicyGraphService(None, value, index_fingerprint="1"*64, source_fingerprint="2"*64)
    ref = SourceRef(source_id=old["source_id"], document_version_id=old["document_version_id"], chunk_id=old["chunk_id"],
        content_sha256=old["quote_span_hash"], locator=old["locator"], quote=old["content_text"])
    assert await graph.source(ref, context()) is None
