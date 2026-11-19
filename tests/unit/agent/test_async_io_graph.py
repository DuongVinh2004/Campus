"""Offline graph/API composition checks; all model and storage ports are fakes."""
import asyncio
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import json

import pytest

from campus247.agent.budget import RunBudget
from campus247.agent.graph import CampusAgentWorkflow
from campus247.agent.nodes import definitions
from campus247.agent.state import Terminal
from campus247.application.retrieval.canonical import CanonicalRetrievalService
from campus247.infrastructure.llm.fake import DeterministicFakeProvider
from campus247.ports.llm import LlmResponse, LlmResponseStatus
from tests.unit.retrieval.test_context_propagation import CHUNKS, Resolver, actor, turn_and_context


class LoopBoundFake(DeterministicFakeProvider):
    def __init__(self, loop=None):
        super().__init__({})
        self.loop = loop
        self.calls = []

    async def generate(self, request):
        if self.loop is not None:
            assert asyncio.get_running_loop() is self.loop
        self.calls.append(request)
        return await super().generate(request)


@pytest.mark.asyncio
async def test_async_graph_awaits_retrieval_and_provider_on_the_same_loop(monkeypatch):
    turn, ctx = turn_and_context()
    loop = asyncio.get_running_loop()
    gateway = LoopBoundFake(loop)
    seen = []
    async def search(query, context):
        assert asyncio.get_running_loop() is loop
        seen.append(context)
        await asyncio.sleep(0)
        return CHUNKS
    monkeypatch.setattr(definitions, "run_sync", lambda *_: pytest.fail("API must not create another loop"))
    workflow = CampusAgentWorkflow(context_search_fn=search, llm_gateway=gateway, require_retrieval_context=True)
    result = await workflow.arun(turn, retrieval_context=ctx)
    assert result.terminal == Terminal.ANSWERED and seen == [ctx]
    assert result.trusted_context_ref == ctx.trace_id
    request = next(r for r in gateway.calls if r.route_id == "grounded_faq")
    assert CHUNKS[0]["content_text"] not in request.system_instructions
    assert 'domain="retrieved_evidence"' in request.input_items[0]["content"]
    assert 'trust="UNTRUSTED_DATA"' in request.input_items[0]["content"]
    assert ctx.authorized_scope.actor_id not in request.input_items[0]["content"]
    assert ctx.trace_id not in request.input_items[0]["content"]


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["exception", "failed", "malformed"])
async def test_generation_failure_never_copies_source_as_an_answer(fault):
    turn, ctx = turn_and_context()
    class FaultFake(LoopBoundFake):
        async def generate(self, request):
            if request.route_id == "grounded_faq":
                if fault == "exception":
                    raise RuntimeError("private-provider-error")
                if fault == "malformed":
                    return None
                return LlmResponse(LlmResponseStatus.FAILED, "fake", "fake")
            return await super().generate(request)
    workflow = CampusAgentWorkflow(context_search_fn=lambda *_: CHUNKS, llm_gateway=FaultFake())
    result = await workflow.arun(turn, retrieval_context=ctx)
    assert result.terminal == Terminal.SAFE_FAILURE
    assert "AI_GENERATION_UNAVAILABLE" in result.errors
    assert CHUNKS[0]["content_text"] not in result.draft.text
    assert "private-provider-error" not in str(result)


@pytest.mark.asyncio
async def test_cancelled_generation_is_joined_and_not_converted_to_source_fallback():
    turn, ctx = turn_and_context()
    entered, stopped = asyncio.Event(), asyncio.Event()
    class WaitingFake(LoopBoundFake):
        async def generate(self, request):
            if request.route_id == "grounded_faq":
                entered.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    stopped.set()
            return await super().generate(request)
    workflow = CampusAgentWorkflow(context_search_fn=lambda *_: CHUNKS, llm_gateway=WaitingFake())
    task = asyncio.create_task(workflow.arun(turn, retrieval_context=ctx))
    await asyncio.wait_for(entered.wait(), 2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert stopped.is_set()


@pytest.mark.asyncio
async def test_overall_budget_cancels_retrieval_and_returns_safe_constant_error():
    turn, ctx = turn_and_context()
    stopped = asyncio.Event()
    async def search(*_):
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()
    workflow = CampusAgentWorkflow(context_search_fn=search, llm_gateway=LoopBoundFake(),
        budget=RunBudget(max_latency_seconds=0.05))
    result = await workflow.arun(turn, retrieval_context=ctx)
    assert result.terminal == Terminal.SAFE_FAILURE and stopped.is_set()
    assert result.errors == ("AI_WORKFLOW_UNAVAILABLE",)


def test_lowered_evidence_threshold_is_rejected_by_graph_binding():
    with pytest.raises(ValueError, match="accepted evidence"):
        CampusAgentWorkflow(evidence_support_threshold=0.25)


def test_bootstrap_injects_actual_canonical_service_into_api_runner(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from campus247.bootstrap import app as bootstrap
    from campus247.bootstrap.settings import Settings
    from campus247.application.retrieval.context import RetrievalContextFactory
    from campus247.application.conversation.messages import ConversationMessageService
    from campus247.presentation.chat import create_chat_router
    from campus247.domain.shared.values import generate_uuid7
    from tests.unit.retrieval.test_canonical_retrieval import fixture

    config, _, candidates, rerank_requests, scopes = fixture()
    content = "Mức học phí là 480.000 VNĐ / tín chỉ theo quy định học phí Đại học Xây dựng Hà Nội."
    candidate = replace(candidates[0], source_id=generate_uuid7(), document_version_id=generate_uuid7(),
        chunk_id=generate_uuid7(), content_text=content, quote_span_hash=hashlib.sha256(content.encode()).hexdigest(),
        title="Synthetic tuition policy", canonical_uri="https://synthetic.example/tuition",
        version_label="synthetic-v1", source_status="SYNTHETIC",
        effective_from=datetime(2026, 10, 1, tzinfo=timezone.utc), effective_until=datetime(2026, 12, 1, tzinfo=timezone.utc))
    async def branch(query, top_k, context):
        scopes.append(context)
        return [candidate]
    config["lexical"] = config["vector"] = branch
    service = CanonicalRetrievalService(**config)
    gateway = LoopBoundFake()
    captured = {}
    original_grounded_request = definitions.grounded_request
    def capture_grounded_request(state, bundle):
        captured["evidence"] = bundle
        return original_grounded_request(state, bundle)
    monkeypatch.setattr(definitions, "grounded_request", capture_grounded_request)
    def capture_router(**kwargs):
        captured["runner"] = kwargs["trusted_agent_runner"]
        return create_chat_router(**kwargs)
    monkeypatch.setattr(bootstrap, "get_settings", lambda: Settings(_env_file=None, ENVIRONMENT="development"))
    monkeypatch.setattr(bootstrap.chat, "create_chat_router", capture_router)
    factory = RetrievalContextFactory(scope_resolver=Resolver(), configured_tenant_id="synthetic-institution",
        configured_campus_id="HUCE")
    bootstrap.create_app(retrieval_context_factory=factory, canonical_retrieval_service=service, llm_gateway=gateway)
    now = datetime.now(timezone.utc)
    identity = replace(actor(), auth_time=now-timedelta(minutes=1), expires_at=now+timedelta(hours=1))
    app = FastAPI()
    @app.middleware("http")
    async def declared_test_identity(request, call_next):
        request.state.identity = identity
        return await call_next(request)
    app.include_router(create_chat_router(ConversationMessageService(), trusted_agent_runner=captured["runner"]))
    client = TestClient(app)
    conversation = client.post("/v1/conversations").json()["id"]
    response = client.post(f"/v1/conversations/{conversation}/messages:stream", json={"content": "Học phí là bao nhiêu?"})
    assert response.status_code == 200 and "message.completed" in response.text
    assert '"status": "answered"' in response.text and candidate.chunk_id in response.text
    from campus247.application.conversation.stream_result import ApiCitation
    events = [json.loads(line.removeprefix("data: ")) for line in response.text.splitlines()
              if line.startswith("data: ")]
    citations = [mapping for event in events for mapping in event.get("citations", [])]
    assert len(citations) == 1
    mapping = citations[0]
    assert mapping["turn_citation_id"] == "CIT-001"
    citation = ApiCitation.model_validate(mapping["citation"])
    assert citation.source_id == candidate.source_id
    assert citation.document_version_id == candidate.document_version_id
    assert citation.chunk_id == candidate.chunk_id
    assert citation.canonical_uri == candidate.canonical_uri
    assert citation.source_title == candidate.title
    assert citation.version_label == candidate.version_label
    assert citation.source_status == candidate.source_status
    assert citation.locator.section_path == " / ".join(candidate.section_path)
    assert citation.locator.page_start == candidate.page_start
    assert citation.locator.page_end == candidate.page_end
    assert citation.quote == candidate.content_text
    evidence = captured["evidence"].resolve(mapping["turn_citation_id"])
    assert evidence.issuer == candidate.issuer
    assert evidence.chunk_id == candidate.chunk_id
    grounded = next(request for request in gateway.calls if request.route_id == "grounded_faq")
    assert candidate.content_text in grounded.input_items[0]["content"]
    assert 'domain="retrieved_evidence"' in grounded.input_items[0]["content"]
    assert candidate.content_text not in grounded.system_instructions
    assert len(rerank_requests) == 1 and len(scopes) == 2
    assert all(s is scopes[0] for s in scopes)
    assert scopes[0].authorized_scope.actor_id == identity.subject_id
