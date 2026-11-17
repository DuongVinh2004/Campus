"""Synthetic propagation evidence, never model/quality or production-binding evidence."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
from threading import Barrier

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "services/api/src"))

from campus247.agent import graph
from campus247.agent.nodes import definitions
from campus247.agent.state import AgentState, DraftResponse, NormalizedTurn, Terminal
from campus247.application.retrieval.citations import CitationBundle
from campus247.application.retrieval.context import ResolvedRetrievalScope, RetrievalContextFactory
from campus247.bootstrap.settings import Settings
from campus247.domain.shared.values import generate_uuid7
from campus247.infrastructure.retrieval.hybrid import HybridSearchAdapter
from campus247.infrastructure.retrieval.vector import VectorSearchAdapter
from campus247.ports.identity import IdentityContext, IdentityRole
from campus247.ports.retrieval import ChunkResult


NOW = datetime(2026, 10, 4, tzinfo=timezone.utc)
CHUNKS = [{"chunk_id": "synthetic-c1", "source_id": "synthetic-s1",
           "document_version_id": "synthetic-v1", "title": "Học phí",
           "content_text": "Mức học phí là 480.000 VNĐ.", "score": 1.0}]


class Resolver:
    def resolve(self, identity):
        return ResolvedRetrievalScope("synthetic-institution", "HUCE", frozenset({"STUDENT"}),
                                      frozenset({"FIT"}), frozenset({"SYNTHETIC_PROGRAM"}))


def actor():
    return IdentityContext(generate_uuid7(), "synthetic-subject", "urn:synthetic",
        (IdentityRole.STUDENT,), "Synthetic Student", NOW - timedelta(minutes=5),
        NOW + timedelta(hours=1), tenant_id="synthetic-institution", student_code="SYN001", faculty_code="FIT")


def factory():
    return RetrievalContextFactory(scope_resolver=Resolver(), configured_tenant_id="synthetic-institution",
                                    configured_campus_id="HUCE", clock=lambda: NOW)


def turn_and_context(trace="1" * 32):
    identity = actor()
    turn = NormalizedTurn("synthetic-session", generate_uuid7(), identity.subject_id, "Học phí HUCE là bao nhiêu?")
    return turn, factory().create(identity, effective_at=NOW, locale=turn.locale, trace_id=trace)


def test_graph_carries_identical_context_to_branches_rerank_and_citation(monkeypatch):
    turn, context = turn_and_context()
    seen = []

    class Branch:
        async def search(self, query, top_k, *, context):
            seen.append(("branch", context))
            return [ChunkResult("synthetic-c1", "synthetic-v1", CHUNKS[0]["content_text"], "Synthetic / 1", 1.0)]

    hybrid = HybridSearchAdapter(Branch(), Branch())

    def search(query, ctx):
        seen.append(("search", ctx))
        assert definitions.run_sync(hybrid.search(query, context=ctx))
        return CHUNKS

    original_rerank = graph.rerank_evidence_node
    original_build = CitationBundle.build.__func__

    def rerank(state, *, context):
        seen.append(("rerank", context))
        return original_rerank(state, context=context)

    def build(cls, chunks, *, context=None):
        bundle = original_build(cls, chunks, context=context)
        seen.append(("citation", bundle.context))
        assert bundle.resolve("CIT-001")
        assert context.authorized_scope.actor_id not in bundle.to_prompt_context()
        assert context.trace_id not in bundle.to_prompt_context()
        return bundle

    monkeypatch.setattr(graph, "rerank_evidence_node", rerank)
    monkeypatch.setattr(CitationBundle, "build", classmethod(build))
    workflow = graph.CampusAgentWorkflow(context_search_fn=search, require_retrieval_context=True)
    result = workflow.run(turn, retrieval_context=context)
    assert result.terminal == Terminal.ANSWERED
    assert result.trusted_context_ref == context.trace_id
    assert [name for name, _ in seen].count("branch") == 2
    assert [name for name, _ in seen].count("citation") == 2
    assert {name for name, _ in seen} == {"search", "branch", "rerank", "citation"}
    assert all(ctx is context for _, ctx in seen)


def test_shared_workflow_concurrent_turns_do_not_exchange_context(monkeypatch):
    turns = [turn_and_context("1" * 32), turn_and_context("2" * 32)]
    barrier = Barrier(2)
    seen = []
    # Concurrency here exercises request/graph isolation with synchronous fakes.
    # The retained harness's socketpair guard is process-wide; avoid unrelated
    # Windows asyncio loop creation racing in two threads.
    monkeypatch.setattr(graph, "sensitive_classifier_node", lambda state, **kw: definitions.sensitive_classifier_node(state))
    monkeypatch.setattr(graph, "route_intent_node", lambda state, **kw: definitions.route_intent_node(state))
    monkeypatch.setattr(graph, "compose_grounded_node", lambda state, **kw: definitions.compose_grounded_node(state, context=kw["context"]))

    def search(query, context):
        barrier.wait(timeout=5)
        seen.append(context)
        return CHUNKS

    workflow = graph.CampusAgentWorkflow(context_search_fn=search, require_retrieval_context=True)
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(workflow.run, turn, retrieval_context=ctx) for turn, ctx in turns]
        results = [future.result(timeout=10) for future in futures]
    assert {id(ctx) for ctx in seen} == {id(ctx) for _, ctx in turns}
    assert all(result.terminal == Terminal.ANSWERED and result.trusted_context_ref == ctx.trace_id
               for result, (_, ctx) in zip(results, turns))


def test_retrying_invocation_preserves_context_and_failure_does_not_use_legacy_callback():
    turn, context = turn_and_context()
    seen = []

    def search(query, ctx):
        seen.append(ctx)
        if len(seen) == 1:
            raise TimeoutError("private-query-and-provider-secret")
        return CHUNKS

    workflow = graph.CampusAgentWorkflow(search_fn=lambda q: pytest.fail("unsafe legacy fallback"),
        context_search_fn=search, require_retrieval_context=True)
    failed = workflow.run(turn, retrieval_context=context)
    assert failed.terminal == Terminal.ABSTAINED
    assert failed.errors == ("AI_RETRIEVAL_UNAVAILABLE",)
    assert failed.trusted_context_ref == context.trace_id
    assert "private-query" not in repr(failed)
    # Caller retry of an invocation; does not claim canonical branch retry policy.
    retried = workflow.run(turn, retrieval_context=context)
    assert retried.terminal == Terminal.ANSWERED and seen == [context, context]


def test_required_missing_context_and_missing_context_callback_abstain_before_search():
    turn, context = turn_and_context()
    workflow = graph.CampusAgentWorkflow(search_fn=lambda q: pytest.fail("context must not be dropped"),
                                         require_retrieval_context=True)
    for ctx in (None, context):
        result = workflow.run(turn, retrieval_context=ctx)
        assert result.terminal == Terminal.ABSTAINED
        assert result.errors == ("AI_RETRIEVAL_UNAVAILABLE",)


def test_dict_context_and_cross_actor_context_are_rejected_before_graph():
    turn, context = turn_and_context()
    workflow = graph.CampusAgentWorkflow(context_search_fn=lambda *args: pytest.fail("must reject"))
    with pytest.raises(ValueError, match="typed"):
        workflow.run(turn, retrieval_context=context.to_dict())
    with pytest.raises(ValueError, match="actor"):
        workflow.run(replace(turn, user_id=generate_uuid7()), retrieval_context=context)
    with pytest.raises(ValueError, match="typed"):
        graph.build_agent_graph(retrieval_context=context.to_dict())


def test_direct_retrieval_node_rejects_lost_or_swapped_context_before_callback():
    turn, context = turn_and_context()
    state = AgentState(request=turn, trusted_context_ref=context.trace_id)
    for ctx in (None, context.to_dict(), replace(context, trace_id="3" * 32)):
        result = definitions.retrieve_evidence_node(state, context=ctx,
            search_fn=lambda q: pytest.fail("must reject before retrieval"))
        assert result.terminal == Terminal.ABSTAINED
        assert result.errors == ("AI_RETRIEVAL_UNAVAILABLE",)


@pytest.mark.parametrize("node", [definitions.rerank_evidence_node, definitions.compose_grounded_node,
                                  definitions.evidence_gate_node])
def test_downstream_nodes_reject_lost_or_swapped_context(node):
    turn, context = turn_and_context()
    state = AgentState(request=turn, trusted_context_ref=context.trace_id)
    for ctx in (None, context.to_dict(), replace(context, trace_id="3" * 32)):
        with pytest.raises(ValueError):
            node(state, context=ctx)


@pytest.mark.asyncio
async def test_hybrid_rejects_dict_before_access_and_vector_stays_disabled():
    _, context = turn_and_context()
    class Forbidden:
        def search(self, *args, **kwargs):
            pytest.fail("must reject before branch access")
    with pytest.raises(ValueError, match="typed"):
        await HybridSearchAdapter(Forbidden(), Forbidden()).search("synthetic", context=context.to_dict())
    with pytest.raises(RuntimeError, match="approved embedding"):
        await VectorSearchAdapter(environment="development").search("synthetic", context=context)


@pytest.mark.parametrize("configured", [False, True])
def test_bootstrap_uses_server_identity_and_never_fabricates_missing_scope(monkeypatch, configured):
    from campus247.bootstrap import app as bootstrap
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from campus247.application.conversation.messages import ConversationMessageService
    from campus247.presentation.chat import create_chat_router
    identity = actor()
    # Scope missing in the synthetic adapter must remain missing, even with a resolver.
    if not configured:
        identity = replace(identity, tenant_id=None)
    captured = {}

    class Workflow:
        def __init__(self, **kwargs):
            assert kwargs["require_retrieval_context"] is True
        async def arun(self, turn, *, retrieval_context):
            captured.update(turn=turn, context=retrieval_context)
            return AgentState(request=turn, terminal=Terminal.ABSTAINED, draft=DraftResponse("Synthetic abstention"))

    real_router = create_chat_router
    def capture_router(**kwargs):
        captured["runner"] = kwargs["trusted_agent_runner"]
        return real_router(**kwargs)
    monkeypatch.setattr(bootstrap, "get_settings", lambda: Settings(_env_file=None, ENVIRONMENT="development"))
    monkeypatch.setattr(bootstrap, "CampusAgentWorkflow", Workflow)
    monkeypatch.setattr(bootstrap, "create_llm_gateway", lambda **kwargs: object())
    monkeypatch.setattr(bootstrap.chat, "create_chat_router", capture_router)
    # Use current auth times for the real factory; no credentials/provider/DB access.
    now = datetime.now(timezone.utc)
    identity = replace(identity, auth_time=now-timedelta(minutes=1), expires_at=now+timedelta(hours=1))
    trusted_factory = RetrievalContextFactory(scope_resolver=Resolver(), configured_tenant_id="synthetic-institution",
                                             configured_campus_id="HUCE")
    bootstrap.create_app(retrieval_context_factory=trusted_factory if configured else None)
    app = FastAPI()
    @app.middleware("http")
    async def trusted_identity(request, call_next):
        request.state.identity = identity
        return await call_next(request)
    app.include_router(real_router(conv_service=ConversationMessageService(), trusted_agent_runner=captured["runner"]))
    client = TestClient(app)
    conversation = client.post("/v1/conversations").json()["id"]
    # Client-supplied scope fields are rejected outright by the strict message schema.
    forged = client.post(f"/v1/conversations/{conversation}/messages:stream", json={
        "content": "synthetic", "tenant_id": "forged", "roles": ["SYSTEM_ADMIN"], "program": "ALL"})
    assert forged.status_code == 422 and "turn" not in captured
    response = client.post(f"/v1/conversations/{conversation}/messages:stream", json={"content": "synthetic"})
    assert response.status_code == 200 and "message.completed" in response.text
    assert captured["turn"].user_id == identity.subject_id
    ctx = captured["context"]
    if configured:
        assert ctx.authorized_scope.roles == frozenset({"STUDENT"})
        assert ctx.authorized_scope.program_codes == frozenset({"SYNTHETIC_PROGRAM"})
        assert ctx.authorized_scope.tenant_id == "synthetic-institution"
    else:
        assert ctx is None
