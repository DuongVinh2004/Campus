from __future__ import annotations

import json
from pathlib import Path
import sys
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

ROOT = Path(__file__).resolve().parents[2]
API_SRC = ROOT / "services" / "api" / "src"
SYNTH_SRC = ROOT / "packages" / "synthetic" / "src"
if str(API_SRC) not in sys.path:
    sys.path.insert(0, str(API_SRC))
if str(SYNTH_SRC) not in sys.path:
    sys.path.insert(0, str(SYNTH_SRC))

from campus247.application.conversation.messages import ConversationMessageService
from campus247.infrastructure.identity.mock import SyntheticIdentityAdapter
from campus247.presentation.chat import create_chat_router
from campus247.presentation.identity import IdentityMiddleware
from campus247.agent.state import AgentState, DraftResponse, Route, Terminal


def synthetic_read_runner(turn, identity):
    return AgentState(turn, route=Route.PERSONAL_SCHEDULE, terminal=Terminal.ANSWERED,
                      draft=DraftResponse("Thời khóa biểu mô phỏng của tuần này."))


@pytest.fixture
def setup_app():
    app = FastAPI()
    identity_adapter = SyntheticIdentityAdapter(secret_key="secret-test-key-247")
    app.add_middleware(IdentityMiddleware, adapter=identity_adapter)

    conv_service = ConversationMessageService()
    # A successful response requires a configured runner. An absent runner is
    # separately tested as INTEGRATION_NOT_ENABLED by the approved stream binding.
    chat_router = create_chat_router(conv_service, trusted_agent_runner=synthetic_read_runner)
    app.include_router(chat_router)

    client = TestClient(app)
    return client, identity_adapter, conv_service


def test_chat_sse_unauthenticated(setup_app):
    client, _, _ = setup_app
    resp = client.post(
        "/v1/conversations/01923456-789a-7def-8123-456789abcdef/messages:stream",
        json={"content": "Xin chào"},
    )
    assert resp.status_code == 401


def test_chat_sse_conversation_not_found(setup_app):
    client, identity_adapter, _ = setup_app
    student_id = "4b419a1b-6d41-7dfb-8943-2edd9f071385"
    token = identity_adapter.mint_token(student_id)

    resp = client.post(
        "/v1/conversations/01923456-789a-7def-8123-456789abcdef/messages:stream",
        headers={"Authorization": f"Bearer {token}"},
        json={"content": "Xin chào"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_chat_sse_conversation_forbidden(setup_app):
    client, identity_adapter, conv_service = setup_app
    student_1 = "4b419a1b-6d41-7dfb-8943-2edd9f071385"
    student_2 = "97c5ab40-6399-7ad3-9838-eab50f267b2d"

    conv = await conv_service.create_conversation(owner_user_id=student_1)
    token_2 = identity_adapter.mint_token(student_2)

    resp = client.post(
        f"/v1/conversations/{conv.id}/messages:stream",
        headers={"Authorization": f"Bearer {token_2}"},
        json={"content": "Xin chào"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_chat_sse_streaming_success(setup_app):
    client, identity_adapter, conv_service = setup_app
    student_id = "4b419a1b-6d41-7dfb-8943-2edd9f071385"
    token = identity_adapter.mint_token(student_id)

    conv = await conv_service.create_conversation(owner_user_id=student_id)

    resp = client.post(
        f"/v1/conversations/{conv.id}/messages:stream",
        headers={"Authorization": f"Bearer {token}"},
        json={"content": "Lịch học của tôi tuần này?"},
    )
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("content-type", "")

    body = resp.text
    assert "event: message.started" in body
    assert "event: message.delta" in body
    assert "event: message.completed" in body
    events = parse_events(body)
    validate_events(events)
    assert events[-1]["data"]["status"] == "answered"
    assert events[0]["data"]["message_id"] == events[-1]["data"]["message_id"]

    # Verify conversation stored both user and assistant messages
    msgs = await conv_service.list_messages(conv.id)
    assert len(msgs) == 2
    assert msgs[0].sender_type == "USER"
    assert msgs[1].sender_type == "ASSISTANT"
    assert msgs[1].id == events[-1]["data"]["message_id"]
    assert msgs[1].content_redacted == events[-1]["data"]["content"]
    assert msgs[1].finish_status == "answered"


@pytest.mark.asyncio
async def test_chat_sse_with_agent_workflow():
    from campus247.agent.graph import CampusAgentWorkflow

    app = FastAPI()
    identity_adapter = SyntheticIdentityAdapter(secret_key="secret-test-key-247")
    app.add_middleware(IdentityMiddleware, adapter=identity_adapter)

    conv_service = ConversationMessageService()
    workflow = CampusAgentWorkflow()
    chat_router = create_chat_router(conv_service, agent_runner=workflow)
    app.include_router(chat_router)

    client = TestClient(app)
    student_id = "4b419a1b-6d41-7dfb-8943-2edd9f071385"
    token = identity_adapter.mint_token(student_id)

    conv = await conv_service.create_conversation(owner_user_id=student_id)
    resp = client.post(
        f"/v1/conversations/{conv.id}/messages:stream",
        headers={"Authorization": f"Bearer {token}"},
        json={"content": "Thời khóa biểu tuần này của tôi?"},
    )
    assert resp.status_code == 200
    assert "event: message.started" in resp.text
    assert "event: message.delta" in resp.text
    assert "event: message.completed" in resp.text

    msgs = await conv_service.list_messages(conv.id)
    assert len(msgs) == 2
    # No schedule source is connected: the answer says so instead of presenting a timetable.
    assert "chưa kết nối" in msgs[1].content_redacted
    assert "Tiết" not in msgs[1].content_redacted


def parse_events(body):
    events = []
    for frame in body.strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in frame.splitlines())
        events.append({"id": fields["id"], "event": fields["event"], "data": json.loads(fields["data"])})
    return events


def validate_events(events):
    import jsonschema
    schemas = [json.loads((ROOT / path).read_text(encoding="utf-8")) for path in (
        "contracts/json-schema/chat/stream-event.schema.json",
        "contracts/json-schema/common/error.schema.json",
        "contracts/json-schema/citations/citation.schema.json",
    )]
    for schema in schemas:
        jsonschema.Draft202012Validator.check_schema(schema)
    validator = jsonschema.Draft202012Validator(
        schemas[0], resolver=jsonschema.RefResolver.from_schema(schemas[0], store={s["$id"]: s for s in schemas}),
        format_checker=jsonschema.FormatChecker(),
    )
    for event in events:
        validator.validate(event)


async def stream_case(runner, *, service=None, headers=None):
    """Actual router/middleware, synthetic identity, in-memory storage, no lifespan."""
    app = FastAPI()
    identity_adapter = SyntheticIdentityAdapter(secret_key="synthetic-stream-test")
    app.add_middleware(IdentityMiddleware, adapter=identity_adapter)
    service = service or ConversationMessageService()
    app.include_router(create_chat_router(service, trusted_agent_runner=runner))
    actor = "4b419a1b-6d41-7dfb-8943-2edd9f071385"
    conversation = await service.create_conversation(owner_user_id=actor)
    token = identity_adapter.mint_token(actor)
    response = TestClient(app).post(
        f"/v1/conversations/{conversation.id}/messages:stream",
        headers={"Authorization": f"Bearer {token}", **(headers or {})}, json={"content": "Synthetic query"},
    )
    return response, await service.list_messages(conversation.id)


@pytest.mark.asyncio
async def test_abstention_is_completed_with_abstained_finish_and_safe_persistence():
    def runner(turn, identity):
        return AgentState(turn, terminal=Terminal.ABSTAINED,
                          draft=DraftResponse("Chưa có nguồn; bạn có thể làm rõ câu hỏi."))
    response, stored = await stream_case(runner)
    events = parse_events(response.text)
    validate_events(events)
    final = events[-1]["data"]
    assert final["status"] == "abstained" and final["response_class"] == "safe_refusal"
    assert final["citations"] == [] and stored[-1].content_redacted == final["content"]


@pytest.mark.asyncio
@pytest.mark.parametrize("fault,code", [(TimeoutError, "DEPENDENCY_UNAVAILABLE"), (RuntimeError, "INTERNAL_ERROR")])
async def test_runner_failure_is_safe_problem_and_never_success(fault, code):
    calls = []
    def runner(turn, identity):
        calls.append(turn.turn_id)
        raise fault("SYNTHETIC_PRIVATE_EXCEPTION")
    response, stored = await stream_case(runner)
    events = parse_events(response.text)
    validate_events(events)
    assert [e["event"] for e in events] == ["message.started", "message.failed"]
    assert events[-1]["data"]["code"] == code
    assert events[-1]["data"]["request_id"] == response.headers["X-Request-Id"]
    assert events[-1]["data"]["retryable"] is False
    assert "SYNTHETIC_PRIVATE_EXCEPTION" not in response.text
    assert len(stored) == 1 and len(calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("terminal", [Terminal.SAFE_FAILURE, None])
async def test_graph_failure_or_incomplete_graph_never_completed(terminal):
    def runner(turn, identity):
        return AgentState(turn, terminal=terminal, draft=DraftResponse("Synthetic unvalidated draft"))
    response, stored = await stream_case(runner)
    events = parse_events(response.text)
    validate_events(events)
    assert events[-1]["event"] == "message.failed"
    assert "Synthetic unvalidated draft" not in response.text and len(stored) == 1


@pytest.mark.asyncio
async def test_missing_runner_is_integration_not_enabled():
    response, stored = await stream_case(None)
    events = parse_events(response.text)
    validate_events(events)
    assert events[-1]["data"]["code"] == "INTEGRATION_NOT_ENABLED"
    assert len(stored) == 1


@pytest.mark.asyncio
async def test_retrieval_service_failure_is_distinct_from_no_source():
    def runner(turn, identity):
        return AgentState(turn, terminal=Terminal.ABSTAINED, errors=("AI_RETRIEVAL_UNAVAILABLE",),
                          draft=DraftResponse("Synthetic no-source wording"))
    response, stored = await stream_case(runner)
    events = parse_events(response.text)
    validate_events(events)
    assert events[-1]["event"] == "message.failed"
    assert events[-1]["data"]["code"] == "DEPENDENCY_UNAVAILABLE" and len(stored) == 1


@pytest.mark.asyncio
async def test_grounded_router_persists_exact_final_citation_identity_and_metadata():
    from dataclasses import replace
    from tests.unit.conversation.test_stream_result import grounded_state
    def runner(turn, identity):
        state = grounded_state()
        state.tool_flow.candidates[0]["canonical_uri"] = "https://SYNTHETIC.example"
        return replace(state, request=turn)
    response, stored = await stream_case(runner)
    events = parse_events(response.text)
    validate_events(events)
    started, final = events[0]["data"], events[-1]["data"]
    added = [e["data"] for e in events if e["event"] == "citation.added"]
    assert final["status"] == "answered" and final["response_class"] == "grounded_answer"
    assert started["message_id"] == final["message_id"] == stored[-1].id
    assert added == [{"message_id": stored[-1].id, "citation": final["citations"][0]}]
    assert final["citations"] == [mapping.to_dict() for mapping in stored[-1].citations]
    assert final["content"] == stored[-1].content_redacted
    assert final["citations"][0]["citation"]["canonical_uri"] == "https://SYNTHETIC.example"


@pytest.mark.asyncio
async def test_async_runner_failure_is_awaited_once_and_safely_reported():
    calls = []
    async def runner(turn, identity):
        calls.append(turn)
        raise TimeoutError("SYNTHETIC_ASYNC_PRIVATE_ERROR")
    response, stored = await stream_case(runner)
    events = parse_events(response.text)
    validate_events(events)
    assert events[-1]["event"] == "message.failed"
    assert events[-1]["data"]["code"] == "DEPENDENCY_UNAVAILABLE"
    assert len(calls) == 1 and len(stored) == 1 and "SYNTHETIC_ASYNC_PRIVATE_ERROR" not in response.text


@pytest.mark.parametrize("invalid_data", [
    {"conversation_id": "4b419a1b-6d41-7dfb-8943-2edd9f071385", "message_id": "4b419a1b-6d41-7dfb-8943-2edd9f071385",
     "status": "safe_failure", "response_class": "grounded_answer", "content": "Synthetic", "citations": []},
    {"conversation_id": "4b419a1b-6d41-7dfb-8943-2edd9f071385", "message_id": "4b419a1b-6d41-7dfb-8943-2edd9f071385",
     "status": "answered", "response_class": "safe_refusal", "content": "Synthetic", "citations": []},
])
def test_contract_rejects_false_success_terminal_combinations(invalid_data):
    import jsonschema
    with pytest.raises(jsonschema.ValidationError):
        validate_events([{"id": invalid_data["message_id"], "event": "message.completed", "data": invalid_data}])


@pytest.mark.asyncio
async def test_guard_rejection_never_publishes_or_persists_rejected_draft():
    def runner(turn, identity):
        return AgentState(turn, route=Route.PERSONAL_SCHEDULE, terminal=Terminal.ANSWERED,
                          draft=DraftResponse("Synthetic __internal_prompt__ rejected draft"))
    response, stored = await stream_case(runner)
    events = parse_events(response.text)
    validate_events(events)
    assert events[-1]["data"]["status"] == "abstained"
    assert "__internal_prompt__" not in response.text
    assert all("__internal_prompt__" not in message.content_redacted for message in stored)
    assert events[-1]["data"]["citations"] == []


@pytest.mark.asyncio
async def test_failure_after_provisional_deltas_has_no_completed_event():
    class FailingAssistantService(ConversationMessageService):
        async def append_message(self, **kwargs):
            if kwargs["sender_type"] == "ASSISTANT":
                raise RuntimeError("SYNTHETIC_STORAGE_PRIVATE_ERROR")
            return await super().append_message(**kwargs)
    response, stored = await stream_case(synthetic_read_runner, service=FailingAssistantService())
    events = parse_events(response.text)
    validate_events(events)
    assert any(e["event"] == "message.delta" for e in events)
    assert events[-1]["event"] == "message.failed" and len(stored) == 1
    assert "SYNTHETIC_STORAGE_PRIVATE_ERROR" not in response.text


@pytest.mark.asyncio
async def test_persistence_content_policy_is_checked_before_any_legacy_content_delta():
    from campus247.infrastructure.llm.egress_policy import EgressPolicy, EgressViolationError
    def minimize(content):
        try:
            EgressPolicy().validate_and_minimize({"purpose": "FAQ_ANSWERING",
                "messages": [{"role": "user", "content": content}]})
            return content
        except EgressViolationError:
            return None
    def runner(turn, identity):
        return AgentState(turn, route=Route.PERSONAL_SCHEDULE, terminal=Terminal.ANSWERED,
            draft=DraftResponse("Synthetic private contact 0900000000, private@example.org"))
    response, stored = await stream_case(runner, service=ConversationMessageService(minimize_content=minimize))
    events = parse_events(response.text)
    validate_events(events)
    assert events[-1]["event"] == "message.completed" and events[-1]["data"]["status"] == "abstained"
    assert "0900000000" not in response.text and "private@example.org" not in response.text
    assert all("0900000000" not in m.content_redacted and "private@example.org" not in m.content_redacted for m in stored)
    assert not any(e["event"] == "message.failed" for e in events)


@pytest.mark.asyncio
async def test_user_persistence_error_is_safe_pre_stream_problem():
    class FailingUserService(ConversationMessageService):
        async def append_message(self, **kwargs):
            raise RuntimeError("SYNTHETIC_USER_STORAGE_ERROR")
    response, stored = await stream_case(synthetic_read_runner, service=FailingUserService())
    assert response.status_code == 500
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["request_id"] == response.headers["X-Request-Id"]
    assert "SYNTHETIC_USER_STORAGE_ERROR" not in response.text and stored == []


@pytest.mark.asyncio
async def test_resume_never_regenerates_a_turn():
    calls = []
    def runner(turn, identity):
        calls.append(turn)
        return synthetic_read_runner(turn, identity)
    response, stored = await stream_case(runner, headers={"Last-Event-ID": "synthetic-prior-event"})
    assert response.status_code == 409 and calls == [] and stored == []
    assert 'rel="alternate"' in response.headers["Link"]


@pytest.mark.asyncio
@pytest.mark.parametrize("disconnect_at", [0, 1, 2, 100])
async def test_disconnect_and_cancellation_do_not_commit_partial_message(disconnect_at):
    import asyncio
    from datetime import datetime, timedelta, timezone
    from starlette.requests import Request
    from campus247.ports.identity import IdentityContext, IdentityRole
    from campus247.presentation.chat import CreateMessagePayload
    service = ConversationMessageService()
    actor = "4b419a1b-6d41-7dfb-8943-2edd9f071385"
    conv = await service.create_conversation(owner_user_id=actor)
    now = datetime.now(timezone.utc)
    request = Request({"type": "http", "method": "POST", "path": "/synthetic", "headers": [], "query_string": b""})
    request.state.identity = IdentityContext(actor, "synthetic", "urn:synthetic", (IdentityRole.STUDENT,),
        "Synthetic", now, now + timedelta(hours=1), student_code="SYN-STREAM")
    checks = 0
    async def is_disconnected():
        nonlocal checks
        checks += 1
        return checks > disconnect_at
    request.is_disconnected = is_disconnected
    router = create_chat_router(service, trusted_agent_runner=synthetic_read_runner)
    endpoint = next(route.endpoint for route in router.routes if "messages:stream" in route.path)
    response = await endpoint(conv.id, CreateMessagePayload(content="Synthetic"), request)
    frames = []
    if disconnect_at == 100:
        frames.append(await anext(response.body_iterator))
        frames.append(await anext(response.body_iterator))
        with pytest.raises(asyncio.CancelledError):
            await response.body_iterator.athrow(asyncio.CancelledError())
    else:
        frames = [frame async for frame in response.body_iterator]
    await response.body_iterator.aclose()
    assert all("message.completed" not in frame for frame in frames)
    assert len(await service.list_messages(conv.id)) == 1

