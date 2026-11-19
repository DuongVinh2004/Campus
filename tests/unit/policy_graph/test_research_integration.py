"""Full Research/Verifier/claim pipeline with explicit scripted model ports."""
from dataclasses import replace

import pytest

from campus247.agent.state import Terminal
from campus247.application.policy_graph.service import PolicyGraphService
from campus247.domain.policy_graph import GraphProposal, PolicyNode, PolicyEdge, GraphScope, SourceRef, fingerprint
from campus247.infrastructure.repositories.sqlite_policy_graph import SQLitePolicyGraphRepository
from tests.unit.agent.test_multi_agent_integrated import setup


async def bind(workflow, ctx, reader, rows, tmp_path):
    ref = SourceRef(source_id=rows[0]["source_id"], document_version_id=rows[0]["document_version_id"],
        chunk_id=rows[0]["chunk_id"], content_sha256=rows[0]["quote_span_hash"], quote=rows[0]["content_text"], locator=rows[0]["locator"])
    scope = GraphScope(tenant_id="huce-local-public", campus_id="HUCE", audiences=("STUDENT",), faculties=("PUBLIC",), programs=("PUBLIC",))
    p = GraphProposal(id="graph-research-v1", author="test-author", origin="manual_candidate", acquired_at=ctx.effective_at,
        index_fingerprint="1"*64, source_fingerprint="2"*64,
        nodes=(PolicyNode(id="certificate", kind="Procedure", label="Giấy xác nhận", scope=scope, source=ref),
            PolicyNode(id="certificate-clause", kind="Clause", label="Căn cứ giấy xác nhận", scope=scope, source=ref)),
        edges=(PolicyEdge(id="relation", from_id="certificate", to_id="certificate-clause", relation="defined_by", scope=scope, source=ref),))
    repo = SQLitePolicyGraphRepository(tmp_path / "graph.sqlite3", workspace=tmp_path)
    repo.add(p, raw=p.model_dump_json())
    service = PolicyGraphService(repo, reader, index_fingerprint="1"*64, source_fingerprint="2"*64, graph_id=p.id)
    admin = replace(ctx, authorized_scope=replace(ctx.authorized_scope, actor_id="reviewer", roles=frozenset({"KNOWLEDGE_ADMIN"})))
    for i, record in enumerate((*p.nodes, *p.edges)):
        await service.review(p.id, admin, target=record.id, verdict="approved", note="Synthetic source review", expected_revision=i)
    preview = service.publication_preview(p.id, admin, expected_revision=3)
    await service.publish(p.id, admin, expected_revision=3, confirmation=fingerprint(preview))
    workflow.policy_graph = service
    workflow.snapshot = {**workflow.snapshot, "policy_graph": service.snapshot}
    async def search(query, context, *, relation_lookup):
        originals = await relation_lookup(query, context, [rows[0]["chunk_id"]])
        assert all(row["content_text"] == rows[0]["content_text"] for row in originals)
        return rows
    workflow.graph_search = search
    return service


@pytest.mark.asyncio
async def test_research_uses_reviewed_graph_but_verifier_reads_original_and_shared_budgets(tmp_path):
    workflow, turn, ctx, reader, model, rows = setup(tmp_path)
    service = await bind(workflow, ctx, reader, rows, tmp_path)
    result = await workflow.arun(turn, retrieval_context=ctx)
    assert result.terminal == Terminal.ANSWERED
    record = workflow.store.get(turn.turn_id, turn.user_id, turn.session_id)
    events = [e for e in record["events"] if e["tool"] == "search_policy_relations"]
    assert len(events) == 1 and events[0]["status"] == "completed" and events[0]["task_id"] == "T1"
    assert record["snapshot"]["policy_graph"] == service.snapshot
    assert record["usage"]["model_calls"] == len(model.calls) == 8
    assert record["usage"]["tool_calls"] <= workflow.policy.max_tool_calls
    tasks = workflow.store.tasks(turn.turn_id)
    assert "search_policy_relations" in tasks[0]["spec"]["tools"]
    assert "search_policy_relations" not in tasks[1]["spec"]["tools"]
    assert any(e["task_id"] == "T2" and e["tool"] == "read_source" for e in record["events"])
    assert all("graph" not in row["content_text"] for row in record["final_result"]["citations"] if "content_text" in row)


@pytest.mark.asyncio
async def test_graph_snapshot_outage_is_explicit_and_keeps_hybrid_fallback(tmp_path):
    workflow, turn, ctx, reader, _, rows = setup(tmp_path)
    service = await bind(workflow, ctx, reader, rows, tmp_path)
    service.index_fingerprint = "f"*64
    result = await workflow.arun(turn, retrieval_context=ctx)
    assert result.terminal == Terminal.ANSWERED
    record = workflow.store.get(turn.turn_id, turn.user_id, turn.session_id)
    assert any(e["tool"] == "search_policy_relations" and e["status"] == "unavailable"
        and e["data"]["code"] == "GRAPH_SNAPSHOT_MISMATCH" for e in record["events"])
