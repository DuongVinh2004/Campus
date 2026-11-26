"""Guard cadence on real SSE frames with synthetic, source-checked RAG v2 results."""
from datetime import UTC, datetime, timedelta

import pytest
from starlette.requests import Request

from campus247.application.conversation.messages import ConversationMessageService
from campus247.ports.identity import IdentityContext, IdentityRole
from campus247.presentation.chat import CreateMessagePayload, create_chat_router
from tests.api.test_chat_sse import parse_events
from tests.rag_v2.test_graph_integration import ACTOR, context, setup
from tests.rag_v2.test_service import QUESTION, TEXT, FakeGateway


async def open_stream(source, guard, *, early_persistence=False):
    stack = setup(source=source, gateway=FakeGateway(drafts=[[source]]))
    messages = ConversationMessageService()
    conversation = await messages.create_conversation(owner_user_id=ACTOR)
    now = datetime.now(UTC)
    request = Request({"type": "http", "method": "POST", "path": "/synthetic", "headers": [],
                       "query_string": b""})
    request.state.identity = IdentityContext(ACTOR, "tenant", "urn:synthetic", (IdentityRole.STUDENT,),
        "Synthetic", now, now + timedelta(hours=1), student_code="SYN-STREAM")
    async def connected():
        return False
    request.is_disconnected = connected
    async def runner(turn, identity, **kwargs):
        return await stack.workflow.arun(turn, retrieval_context=context())
    async def result_guard(state, identity):
        assert identity.subject_id == ACTOR and "RAG_V2_ANSWER" in state.errors
        await guard(state, await messages.list_messages(conversation.id))
    router = create_chat_router(messages, trusted_agent_runner=runner, result_guard=result_guard,
                                agent_progress=early_persistence)
    endpoint = next(route.endpoint for route in router.routes if "messages:stream" in route.path)
    response = await endpoint(conversation.id, CreateMessagePayload(content=QUESTION), request)
    return response, messages, conversation


@pytest.mark.asyncio
@pytest.mark.parametrize("repeats", [6, 12, 13])
@pytest.mark.parametrize("early_persistence", [False, True])
async def test_result_guard_calls_are_constant_across_delta_counts(repeats, early_persistence):
    source = " ".join([TEXT] * repeats)
    assert len(source.split()) >= 60
    events, checks = [], []
    async def guard(state, stored):
        checks.append((sum(e["event"] == "message.delta" for e in events), len(stored)))
    response, messages, conversation = await open_stream(
        source, guard, early_persistence=early_persistence)
    async for frame in response.body_iterator:
        events.extend(parse_events(frame))
    assert events[-1]["event"] == "message.completed"
    final = events[-1]["data"]
    assert final["response_class"] == "grounded_answer" and len(final["citations"]) == 1
    citation = final["citations"][0]["citation"]
    assert citation["unit_id"] and citation["release_generation"] == 27
    assert citation["quote"] in "Đoạn mở đầu của tài liệu.\n" + source
    deltas = [e["data"]["delta"] for e in events if e["event"] == "message.delta"]
    assert len(deltas) >= 20 and "".join(deltas) == final["content"]
    # Before content, after all content, after persistence, before citation and completion.
    assert checks == [(0, 1), (len(deltas), 2 if early_persistence else 1),
                      (len(deltas), 2), (len(deltas), 2), (len(deltas), 2)]
    stored = await messages.list_messages(conversation.id)
    assert len(stored) == 2 and stored[-1].content_redacted == final["content"]


@pytest.mark.asyncio
async def test_revocation_during_deltas_fails_before_persistence_and_citations():
    source = " ".join([TEXT] * 6)
    checks, events = [], []
    async def guard(state, stored):
        checks.append(len(stored))
        if len(checks) > 1:
            raise ValueError("SYNTHETIC_REVOKED_SOURCE")
    response, messages, conversation = await open_stream(source, guard)
    async for frame in response.body_iterator:
        events.extend(parse_events(frame))
    names = [e["event"] for e in events]
    assert names[-1] == "message.failed" and "message.completed" not in names
    assert "citation.added" not in names
    deltas = [e["data"]["delta"] for e in events if e["event"] == "message.delta"]
    assert source in "".join(deltas)
    assert checks == [1, 1] and len(await messages.list_messages(conversation.id)) == 1
    assert "SYNTHETIC_REVOKED_SOURCE" not in str(events)


async def _stream_with_receipts(service):
    stack = setup(source=TEXT, gateway=FakeGateway(drafts=[[TEXT]]))
    messages = ConversationMessageService()
    conversation = await messages.create_conversation(owner_user_id=ACTOR)
    now = datetime.now(UTC)
    from types import SimpleNamespace
    app = SimpleNamespace(state=SimpleNamespace(answer_receipts=service))
    request = Request({"type": "http", "method": "POST", "path": "/synthetic", "headers": [], "query_string": b"", "app": app})
    request.state.identity = IdentityContext(ACTOR, "tenant", "urn:synthetic", (IdentityRole.STUDENT,), "Synthetic", now, now + timedelta(hours=1), student_code="SYN-STREAM")
    async def connected():
        return False
    request.is_disconnected = connected
    async def runner(turn, identity, **kwargs):
        return await stack.workflow.arun(turn, retrieval_context=context())
    router = create_chat_router(messages, trusted_agent_runner=runner)
    endpoint = next(route.endpoint for route in router.routes if "messages:stream" in route.path)
    response = await endpoint(conversation.id, CreateMessagePayload(content=QUESTION), request)
    events = []
    async for frame in response.body_iterator:
        events.extend(parse_events(frame))
    return events, conversation, stack


@pytest.mark.asyncio
async def test_answer_receipt_is_written_after_the_message_is_saved(tmp_path):
    from campus247.application.answer_evidence.receipts import AnswerReceiptService
    from campus247.infrastructure.repositories.sqlite_answer_receipts import AnswerReceiptStore
    store = AnswerReceiptStore(tmp_path / "r.sqlite3")
    service = AnswerReceiptService(store, current_unit_sha=lambda unit_id: "sha-" + unit_id, current_release=lambda: "rel")
    events, conversation, stack = await _stream_with_receipts(service)
    assert events[-1]["event"] == "message.completed"
    message_id = events[-1]["data"]["message_id"] if "message_id" in events[-1]["data"] else events[-1]["data"].get("id")
    row = store.for_message(conversation.id, message_id)
    assert row and row["owner_subject_id"] == ACTOR and row["outcome_kind"] == "answer"
    assert TEXT not in str(row)  # the receipt keeps hashes, not the statement text
    assert row["checks"][0]["verbatim"] is True and row["sources"][0]["text_sha256"].startswith("sha-")


@pytest.mark.asyncio
async def test_failing_receipt_store_never_breaks_the_answer():
    class Broken:
        def enabled(self):
            return True
        def current_unit_sha(self, unit_id):
            raise RuntimeError("store down")
        def on_error(self, error):
            pass
    events, _, _ = await _stream_with_receipts(Broken())
    assert events[-1]["event"] == "message.completed" and events[-1]["data"]["response_class"] == "grounded_answer"
