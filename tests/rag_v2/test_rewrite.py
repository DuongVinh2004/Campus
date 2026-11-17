"""A follow-up question is rewritten from earlier user turns; every failure falls back unchanged."""
import asyncio
import json

import pytest
from campus247.application.conversation.context import TurnItem
from campus247.application.conversation.history import HistoryContext
from campus247.application.conversation.stream_result import prepare_chat_result
from campus247.ports.llm import LlmResponse, LlmResponseStatus
from campus247.rag_v2.generation.rewrite import rewrite_question

from tests.rag_v2.test_graph_integration import ACTOR, context, setup
from tests.rag_v2.test_service import FakeGateway


class RewriteGateway(FakeGateway):
    def __init__(self, rewritten, *, status=LlmResponseStatus.COMPLETED, delay=0, **kwargs):
        super().__init__(**kwargs)
        self.rewritten, self.status, self.rewrite_delay = rewritten, status, delay

    async def generate(self, request):
        if request.request_id != "rag_v2_rewrite":
            return await super().generate(request)
        self.requests.append(request)
        if self.rewrite_delay:
            await asyncio.sleep(self.rewrite_delay)
        value = {"question": self.rewritten}
        return LlmResponse(self.status, "fake", "fake", structured_output=value, output_text=json.dumps(value))


HISTORY = ["Học phí kỹ sư chính quy K64 trở về trước năm 2026-2027?"]


@pytest.mark.asyncio
async def test_rewrite_returns_the_standalone_question():
    gateway = RewriteGateway("Học phí kỹ sư chính quy K64 trở về trước năm 2026-2027 là bao nhiêu một tín chỉ?")
    result = await rewrite_question(gateway, "Nó bao nhiêu một tín chỉ?", HISTORY, deadline_ms=2000)
    assert result and "K64" in result
    sent = json.loads(gateway.requests[0].input_items[0]["content"])
    assert sent == {"previous_questions": HISTORY, "latest_question": "Nó bao nhiêu một tín chỉ?"}


@pytest.mark.asyncio
@pytest.mark.parametrize("rewritten", ["", "ok", "Xem https://evil.example/x", "Gửi tới a@b.vn", "x" * 500])
async def test_unsafe_or_unusable_rewrites_are_dropped(rewritten):
    assert await rewrite_question(RewriteGateway(rewritten), "Nó bao nhiêu?", HISTORY, deadline_ms=2000) is None


@pytest.mark.asyncio
async def test_no_history_a_failed_call_or_a_late_answer_gives_none():
    ok = RewriteGateway("Học phí K64 là bao nhiêu một tín chỉ?")
    assert await rewrite_question(ok, "Nó bao nhiêu?", [], deadline_ms=2000) is None
    assert not ok.requests
    failed = RewriteGateway("Học phí K64 là bao nhiêu?", status=LlmResponseStatus.FAILED)
    assert await rewrite_question(failed, "Nó bao nhiêu?", HISTORY, deadline_ms=2000) is None
    slow = RewriteGateway("Học phí K64 là bao nhiêu?", delay=0.5)
    assert await rewrite_question(slow, "Nó bao nhiêu?", HISTORY, deadline_ms=300) is None


@pytest.mark.asyncio
async def test_the_node_answers_the_rewritten_question_and_keeps_the_original_when_there_is_no_rewrite():
    from dataclasses import replace

    from tests.rag_v2.test_service import QUESTION

    for rewritten, expected in ((QUESTION + " cho K64", QUESTION + " cho K64"), ("", QUESTION)):
        gateway = RewriteGateway(rewritten)
        stack = setup(gateway=gateway)
        history = HistoryContext(ACTOR, stack.turn.session_id, (TurnItem("1", "user", "Câu hỏi trước về K64"),), 50, "test")
        state = await stack.workflow.arun(replace(stack.turn, history=history), retrieval_context=context())
        prepare_chat_result(state)
        ids = [r.request_id for r in gateway.requests]
        assert ids.count("rag_v2_rewrite") == 1 and ids.count("rag_v2_generation") == 1
        generated = next(r for r in gateway.requests if r.request_id == "rag_v2_generation")
        assert json.loads(generated.input_items[0]["content"])["question"].casefold() == expected.casefold()
        assert len(stack.authorizations) == 1
