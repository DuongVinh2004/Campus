"""UNI-011–015 backend contracts on newly created synthetic fixtures only."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import sqlite3

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from campus247.agent.state import AgentState, DraftResponse, Route, Terminal
from campus247.application.conversation.messages import ConversationMessageService, ConversationConflict, SenderType
from campus247.application.conversation.stream_result import FinalChatResult
from campus247.bootstrap.unified_demo import create_unified_demo_app
from campus247.domain.shared.values import generate_uuid7
from campus247.infrastructure.identity.mock import SyntheticIdentityAdapter
from campus247.infrastructure.repositories.sqlite_conversations import SQLiteConversationRepository, encode
from campus247.presentation.chat import create_chat_router
from campus247.presentation.identity import IdentityMiddleware
from tests.integration.test_unified_actor_features import runtime as runtime_fixture, grant, use, confirm_http, tables
from tests.integration.test_unified_durable_services import actor
from tests.api.test_service_stage6 import draft, login

runtime = runtime_fixture


def metadata(client, headers, conversation, *, title="Hội thoại mới", version=0, client_id=None, **changes):
    return client.post(f"/v1/assistant/conversations/{conversation.id}:preview", headers=headers,
        json={"title": title, "expected_version": version, "client_id": client_id or generate_uuid7(), **changes})


def test_catalog_confirm_readback_replay_restart_preserves_held_history(runtime):
    app, client, identity, messages, conversation, _, paths = runtime
    headers = login(client)
    before = tables(paths[2])
    page = client.get("/v1/assistant/conversations", headers=headers)
    assert page.status_code == 200 and page.headers["cache-control"] == "no-store"
    assert [row["id"] for row in page.json()["items"]] == [conversation.id]
    preview = metadata(client, headers, conversation, title="Học bổng", pinned=True)
    receipt = confirm_http(client, headers, "/v1/assistant/conversations:confirm", preview)
    assert receipt["namespace"] == "conversation_metadata"
    assert confirm_http(client, headers, "/v1/assistant/conversations:confirm", preview)["is_replay"]
    restarted = create_unified_demo_app(paths[0], state_database=paths[1], consent_mode="sqlite", history_database=paths[2])
    value = asyncio.run(restarted.state.conversation_catalog.read(identity, conversation.id))
    assert (value["title"], value["pinned"], value["version"]) == ("Học bổng", True, 1)
    assert tables(paths[2]) == before
    assert client.get("/v1/assistant/conversations?title=học%20bổng", headers=headers).json()["items"][0]["id"] == conversation.id
    assert client.get("/v1/assistant/conversations?title=không", headers=headers).json()["items"] == []
    assert len(asyncio.run(messages.list_messages(conversation.id))) == 2


def test_metadata_cas_archive_keeps_source_and_rejects_proxy_stream(runtime):
    _, client, _, _, conversation, _, paths = runtime
    headers = login(client)
    a = metadata(client, headers, conversation, title="A", archived=True)
    b = metadata(client, headers, conversation, title="B")
    before = tables(paths[2])
    confirm_http(client, headers, "/v1/assistant/conversations:confirm", a)
    failed = client.post("/v1/assistant/conversations:confirm", headers=headers, json={**b.json(), "confirmed": True})
    assert failed.status_code == 422  # preview response has expiry/effect, not confirmation DTO
    body = b.json()
    failed = client.post("/v1/assistant/conversations:confirm", headers=headers, json={"normalized_payload": body["normalized_payload"], "confirmation_token": body["confirmation_token"], "confirmed": True})
    assert failed.status_code == 409
    assert client.get("/v1/assistant/conversations", headers=headers).json()["items"] == []
    value = client.get("/v1/assistant/conversations?archived=true", headers=headers).json()["items"][0]
    assert value["title"] == "A" and not value["can_continue"]
    assert client.post(f"/v1/conversations/{conversation.id}/messages:stream", headers=headers, json={"content": "retry"}).status_code == 409
    assert tables(paths[2]) == before


@pytest.mark.parametrize("account", ["SV024", "OF001", "KA001"])
def test_catalog_does_not_mix_actors_roles(runtime, account):
    _, client, _, _, conversation, _, _ = runtime
    headers = login(client, account)
    read = client.get(f"/v1/assistant/conversations/{conversation.id}", headers=headers)
    assert read.status_code in {403, 404}
    assert metadata(client, headers, conversation).status_code in {403, 404}
    page = client.get("/v1/assistant/conversations", headers=headers)
    assert page.status_code == 200 and page.json()["items"] == [] if account == "SV024" else page.status_code == 403


@pytest.mark.parametrize("change", [{"title": ""}, {"title": " x "}, {"title": "x\nsecret"}, {"expected_version": True}, {"roles": ["STUDENT"]}, {"owner": "forged"}, {"pinned": "true"}])
def test_metadata_dto_rejects_forged_or_ambiguous_input(runtime, change):
    _, client, _, _, conversation, _, _ = runtime
    assert metadata(client, login(client), conversation, **change).status_code == 422


def test_catalog_cursor_bound_to_owner_filter_and_storage_failure(runtime):
    _, client, identity, messages, _, _, paths = runtime
    for _ in range(3): asyncio.run(messages.create_conversation(identity.subject_id))
    headers = login(client)
    page = client.get("/v1/assistant/conversations?limit=2", headers=headers).json()
    cursor = page["page"]["next_cursor"]
    tail = client.get("/v1/assistant/conversations", headers=headers, params={"cursor": cursor, "limit": 2}).json()
    assert len({row["id"] for row in page["items"]+tail["items"]}) == 4
    assert client.get("/v1/assistant/conversations", headers=headers, params={"cursor": cursor, "title": "other"}).status_code == 422
    assert client.get("/v1/assistant/conversations", headers=login(client,"SV024"), params={"cursor": cursor}).status_code == 422
    with sqlite3.connect(paths[2]) as connection:
        connection.execute("UPDATE conversation_schema SET version=99 WHERE version=1")
    response = client.get("/v1/assistant/conversations", headers=headers)
    assert response.status_code == 503 and "items" not in response.json()


def test_retention_is_explicit_and_does_not_delete(runtime):
    _, client, _, _, conversation, _, paths = runtime
    expired = replace(conversation, retention_expires_at=datetime.now(timezone.utc)-timedelta(seconds=1))
    with sqlite3.connect(paths[2]) as connection:
        connection.execute("UPDATE conversation SET record=? WHERE id=?", (encode(expired), conversation.id))
    before = tables(paths[2]); headers = login(client)
    value = client.get(f"/v1/assistant/conversations/{conversation.id}", headers=headers).json()
    assert value["retention_state"] == "expired" and not value["can_continue"]
    page = client.get(f"/v1/conversations/{conversation.id}/messages", headers=headers).json()
    assert page["retention_state"] == "expired" and page["items"] == []
    assert tables(paths[2]) == before


@pytest.mark.parametrize("change", [{"owner": "fake"}, {"notes": "private"}, {"memory": "private"}, {"dom": "page"}, {"field": "internal_note"}, {"field": "purpose"}, {"surface": "certificate"}])
def test_surface_only_accepts_allowlisted_references(runtime, change):
    _, client, _, _, _, _, _ = runtime
    assert client.post("/v1/assistant/surface:resolve", headers=login(client), json={"surface": "chat", **change}).status_code == 422


@pytest.mark.parametrize("field", ["reason", "course_record_id", "contact_preference"])
def test_resource_field_projection_version_owner_and_no_private_notes(runtime, field):
    _, client, _, _, _, _, _ = runtime
    headers = login(client); record = draft(client, headers)
    body = {"surface": "service", "resource": {"kind": "service_request", "id": record["id"], "expected_version": record["version"]}, "field": field}
    result = client.post("/v1/assistant/surface:resolve", headers=headers, json=body)
    assert result.status_code == 200, result.text
    value = result.json()
    assert value["action_authority"] == "none" and value["field_guidance"]
    assert value["context"]["resource"]["version"] == record["version"]
    assert "unsaved_fields" in value["excluded"] and "staff_notes" in value["excluded"]
    assert client.post("/v1/assistant/surface:resolve", headers=login(client,"SV024"), json=body).status_code in {403,404}
    stale = {**body, "resource": {**body["resource"], "expected_version": record["version"]+1}}
    assert client.post("/v1/assistant/surface:resolve", headers=headers, json=stale).status_code == 409
    assert client.post("/v1/assistant/surface:resolve", headers=headers, json={**body, "surface": "certificate"}).status_code == 422


def test_grant_management_page_scope_expiry_last_use_revoke_receipt(runtime):
    app, client, identity, _, _, _, _ = runtime
    gid, target = grant(app, client, identity, lifetime="timed")
    operation = generate_uuid7(); used = use(app, identity, gid, target, operation)
    headers = login(client)
    page = client.get("/v1/assistant/grants", headers=headers).json()
    assert len(page["items"]) == 1
    item = page["items"][0]
    assert item["resource"] == target and item["last_used_at"] and item["use_count"] == 1
    assert item["locked_reason"] is None and item["action_authority"] == "read_or_prepare_only"
    assert client.get("/v1/assistant/grants", headers=login(client,"SV024")).json()["items"] == []
    preview = client.post(f"/v1/assistant/grants/{gid}:revoke-preview", headers=headers,
        json={"expected_version": item["version"], "client_id": generate_uuid7()})
    receipt = confirm_http(client, headers, "/v1/assistant/grants:confirm", preview)
    assert receipt["key"] == gid
    item = client.get("/v1/assistant/grants", headers=headers).json()["items"][0]
    assert item["state"] == "revoked" and item["locked_reason"] == "GRANT_NOT_ACTIVE"
    assert item["last_used_at"] == page["items"][0]["last_used_at"]
    assert used["receipt"].state == "committed"


def test_consumer_capabilities_and_new_notice_do_not_enable_old_declaration(runtime):
    _, client, _, _, _, _, _ = runtime
    headers = login(client)
    caps = client.get("/v1/assistant/consumer-capabilities", headers=headers).json()
    assert caps["history"] and caps["history_metadata"]
    assert not caps["model_preferences"] and not caps["stable_turns"] and not caps["memory"] and not caps["tools"]
    notice = client.get("/v1/assistant/consent-notice", headers=headers).json()
    assert notice["version"].endswith(".assistant-features.v1")
    old = client.get("/v1/privacy/notice").json()
    assert client.post("/v1/privacy/consents", headers=headers, json={"purpose":"OPTIONAL_PERSONALIZATION","decision":"GRANTED","notice_version":old["version"]}).status_code == 201
    states = client.get("/v1/assistant/consent-state", headers=headers).json()["items"]
    assert len(states) == 3 and all(not row["current_notice_consented"] for row in states)
    staff = client.get("/v1/assistant/consumer-capabilities", headers=login(client,"OF001")).json()
    assert staff["audience"] == "staff" and not staff["history"] and not staff["staff_model_chat"] and staff["account_preferences"]


def test_session_grant_management_reports_new_login_locked(runtime):
    app, client, identity, _, _, _, _ = runtime
    gid, _ = grant(app, client, identity, lifetime="session")
    page = client.get("/v1/assistant/grants", headers=login(client)).json()
    assert page["items"][0]["id"] == gid and page["items"][0]["locked_reason"] == "GRANT_NOT_ACTIVE"


@pytest.fixture
def native(tmp_path):
    repository = SQLiteConversationRepository(tmp_path/"native.sqlite3", tenant="huce-local-public")
    service = ConversationMessageService(repository)
    adapter = SyntheticIdentityAdapter("local-test-09", tenant_id="huce-local-public")
    identity = actor(); headers = {"Authorization": "Bearer "+adapter.mint_token(identity.subject_id)}
    calls = []
    def runner(turn, _):
        calls.append(turn.turn_id)
        return AgentState(turn, route=Route.PERSONAL_SCHEDULE, terminal=Terminal.ANSWERED, draft=DraftResponse("Thông tin mô phỏng"))
    app = FastAPI(); app.add_middleware(IdentityMiddleware, adapter=adapter)
    app.include_router(create_chat_router(service, trusted_agent_runner=runner))
    with TestClient(app) as client: yield client, headers, service, calls, repository


def test_native_stable_create_stream_receipt_replay_no_regeneration(native):
    client, headers, service, calls, repo = native
    create_id = generate_uuid7()
    first = client.post("/v1/conversations", headers=headers, json={"client_id":create_id})
    again = client.post("/v1/conversations", headers=headers, json={"client_id":create_id})
    assert first.status_code == again.status_code == 201 and first.json() == again.json()
    turn_id = generate_uuid7(); path = f"/v1/conversations/{create_id}/messages:stream"
    response = client.post(path, headers=headers, json={"content":"Question", "client_id":turn_id})
    assert response.status_code == 200 and "message.completed" in response.text
    receipt = client.get(f"/v1/conversations/{create_id}/receipts/{turn_id}",headers=headers).json()
    assert receipt["state"] == "completed" and receipt["assistant_message_id"]
    for content in ("Question", "changed"):
        assert client.post(path, headers=headers, json={"content":content,"client_id":turn_id}).status_code == 409
    assert calls == [turn_id]
    restarted = ConversationMessageService(SQLiteConversationRepository(repo.path, tenant=repo.tenant))
    assert asyncio.run(restarted.turn_receipt(actor().subject_id,create_id,turn_id))["state"] == "completed"
    messages = asyncio.run(service.list_messages(create_id))
    assert len(messages) == 2 and messages[1].finish_status


def test_pending_interrupted_and_final_transaction_are_distinct(native):
    _, _, service, _, repo = native
    identity = actor(); conv = asyncio.run(service.create_conversation(identity.subject_id))
    turn_id = generate_uuid7()
    asyncio.run(service.append_message(conv.id, SenderType.USER, "Question", identity.subject_id, message_id=turn_id, turn_client_id=turn_id))
    assert asyncio.run(service.turn_receipt(identity.subject_id,conv.id,turn_id))["state"] == "pending"
    asyncio.run(service.interrupt_turn(identity.subject_id,conv.id,turn_id))
    assert asyncio.run(service.turn_receipt(identity.subject_id,conv.id,turn_id))["state"] == "interrupted"
    result = FinalChatResult("completed","tool_result","Result")
    with pytest.raises(ConversationConflict):
        asyncio.run(service.append_message(conv.id,SenderType.ASSISTANT,result.content,final_result=result,turn_client_id=turn_id))
    assert len(asyncio.run(service.list_messages(conv.id))) == 1


def test_native_concurrent_client_id_allocates_exactly_one_sequence(native):
    _, _, service, _, _ = native
    identity=actor(); conv=asyncio.run(service.create_conversation(identity.subject_id)); cid=generate_uuid7()
    def append(_):
        try: return asyncio.run(service.append_message(conv.id,SenderType.USER,"Question",identity.subject_id,message_id=cid,turn_client_id=cid)).id
        except ConversationConflict: return "conflict"
    with ThreadPoolExecutor(max_workers=4) as executor: results=list(executor.map(append,range(4)))
    assert results.count(cid)==1 and results.count("conflict")==3
    assert [row.sequence_no for row in asyncio.run(service.list_messages(conv.id))]==[1]


def test_native_failed_runner_marks_interrupted_not_completed(tmp_path):
    repo=SQLiteConversationRepository(tmp_path/"failure.sqlite3"); service=ConversationMessageService(repo)
    adapter=SyntheticIdentityAdapter("test"); headers={"Authorization":"Bearer "+adapter.mint_token(actor().subject_id)}
    app=FastAPI(); app.add_middleware(IdentityMiddleware,adapter=adapter); app.include_router(create_chat_router(service))
    with TestClient(app) as client:
        cid=client.post("/v1/conversations",headers=headers).json()["id"]; turn=generate_uuid7()
        result=client.post(f"/v1/conversations/{cid}/messages:stream",headers=headers,json={"content":"Question","client_id":turn})
        assert "message.failed" in result.text and "message.completed" not in result.text
        receipt=client.get(f"/v1/conversations/{cid}/receipts/{turn}",headers=headers).json()
        assert receipt["state"]=="interrupted" and receipt["assistant_message_id"] is None


def test_client_intent_hash_precedes_minimization(native):
    _, _, original, _, repo=native
    service=ConversationMessageService(repo,minimize_content=lambda _:"redacted")
    conv=asyncio.run(original.create_conversation(actor().subject_id)); cid=generate_uuid7()
    asyncio.run(service.append_message(conv.id,SenderType.USER,"Original A",actor().subject_id,message_id=cid,turn_client_id=cid))
    with pytest.raises(ConversationConflict, match="TURN_INTENT_CHANGED"):
        asyncio.run(service.append_message(conv.id,SenderType.USER,"Original B",actor().subject_id,message_id=cid,turn_client_id=cid))
