"""Revoke at dispatch boundaries using fake gateways and server callbacks."""
from dataclasses import replace

import pytest

from campus247.application.conversation.context import TurnItem
from campus247.application.conversation.history import HistoryContext
from campus247.application.conversation.stream_result import prepare_chat_result
from tests.rag_v2.test_graph_integration import ACTOR, context, setup
from tests.rag_v2.test_rewrite import RewriteGateway
from tests.rag_v2.test_service import QUESTION, TEXT, FakeGateway, answer


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["before_generation", "after_generation", "before_repair", "after_semantic"])
async def test_node_revalidates_before_each_dispatch_and_final_return(stage):
    revoked = stage == "before_generation"
    dispatches = []
    class Revoking(FakeGateway):
        async def generate(self, request):
            nonlocal revoked
            if request.request_id.startswith("rag_v2_"):
                dispatches.append((request.request_id, revoked))
            response = await super().generate(request)
            if ((stage in {"after_generation", "before_repair"} and request.request_id == "rag_v2_generation")
                    or stage == "after_semantic" and request.request_id == "rag_v2_semantic"):
                revoked = True
            return response
    async def revalidate(query, ctx, chunks):
        if revoked:
            raise ValueError("revoked")
    gateway = Revoking(drafts=[["Nộp 999 hồ sơ."]] if stage == "before_repair" else None)
    stack = setup(gateway=gateway, revalidate=revalidate)
    final = prepare_chat_result(await stack.workflow.arun(stack.turn, retrieval_context=context()))
    assert final.response_class == "system_error" and not final.citations and TEXT not in final.content
    assert all(not was_revoked for _, was_revoked in dispatches)
    ids = [r.request_id for r in gateway.requests if r.request_id.startswith("rag_v2_")]
    assert len(ids) == {"before_generation": 0, "after_generation": 1, "before_repair": 1, "after_semantic": 2}[stage]


@pytest.mark.asyncio
@pytest.mark.parametrize("year", ["2026-2027", "2028-2029", "2031-2032"])
async def test_followup_year_uses_the_resolved_question_for_authorization_and_revalidation(year):
    rewritten = QUESTION + " năm học " + year
    gateway = RewriteGateway(rewritten)
    seen = []
    async def revalidate(query, ctx, chunks):
        if chunks:
            assert query == rewritten
            seen.append(query)
    stack = setup(gateway=gateway, revalidate=revalidate)
    original_authorize = stack.node.authorize_sources
    async def authorize(query, ctx):
        assert query == rewritten
        return await original_authorize(query, ctx)
    stack.node.authorize_sources = authorize
    history = HistoryContext(ACTOR, stack.turn.session_id,
        (TurnItem("1", "user", "Tôi hỏi năm học " + year),), 50, "test")
    final = prepare_chat_result(await stack.workflow.arun(replace(stack.turn, history=history), retrieval_context=context()))
    assert final.response_class == "grounded_answer" and len(seen) >= 3


@pytest.mark.asyncio
async def test_service_callback_blocks_semantic_dispatch_after_revocation():
    revoked = False
    class Revoking(FakeGateway):
        async def generate(self, request):
            nonlocal revoked
            result = await super().generate(request)
            revoked = True
            return result
    async def revalidate(chunks):
        assert chunks == ("chunk",)
        if revoked:
            raise ValueError("revoked")
    gateway = Revoking()
    result = await answer(gateway=gateway, revalidate=revalidate)
    assert result.kind == "transient_error" and len(gateway.requests) == 1 and not result.citations


@pytest.mark.asyncio
@pytest.mark.parametrize("revoke_at", ["disconnect", "after_citation"])
async def test_sse_revocation_in_disconnect_await_cannot_publish_citations_or_terminal(monkeypatch, revoke_at):
    from fastapi import FastAPI, Request
    from fastapi.testclient import TestClient
    from campus247.application.conversation.messages import ConversationMessageService
    from campus247.infrastructure.identity.mock import SyntheticIdentityAdapter
    from campus247.presentation.chat import create_chat_router
    from campus247.presentation.identity import IdentityMiddleware
    from tests.api.test_chat_sse import parse_events

    stack = setup()
    adapter = SyntheticIdentityAdapter("i1-synthetic-test-key", tenant_id="tenant")
    messages = ConversationMessageService()
    conv = await messages.create_conversation(owner_user_id=ACTOR)
    armed = revoked = False
    async def runner(turn, identity):
        return await stack.workflow.arun(turn, retrieval_context=context())
    async def result_guard(state, identity):
        nonlocal armed
        if revoked:
            raise ValueError("revoked")
        # The assistant is persisted after deltas, just before the final scope check.
        armed = len(await messages.list_messages(conv.id)) >= 2
    async def disconnect(request):
        nonlocal revoked
        if armed and revoke_at == "disconnect":
            revoked = True
        return False
    class RevokeAfterCitation:
        def __init__(self, app):
            self.app = app

        async def __call__(self, scope, receive, send):
            async def observe(message):
                nonlocal revoked
                await send(message)
                if revoke_at == "after_citation" and b"event: citation.added" in message.get("body", b""):
                    revoked = True
            await self.app(scope, receive, observe)
    monkeypatch.setattr(Request, "is_disconnected", disconnect)
    app = FastAPI()
    app.add_middleware(RevokeAfterCitation)
    app.add_middleware(IdentityMiddleware, adapter=adapter)
    app.include_router(create_chat_router(messages, trusted_agent_runner=runner, result_guard=result_guard))
    with TestClient(app) as client:
        response = client.post(f"/v1/conversations/{conv.id}/messages:stream",
            headers={"Authorization": "Bearer " + adapter.mint_token(ACTOR)}, json={"content": QUESTION})
    events = parse_events(response.text)
    assert revoked and any(e["event"] == "message.failed" for e in events)
    assert not any(e["event"] == "message.completed" for e in events)
    assert sum(e["event"] == "citation.added" for e in events) == (revoke_at == "after_citation")
