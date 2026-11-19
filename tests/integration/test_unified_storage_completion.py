"""Completion storage cases on exclusive retained synthetic fixtures only."""
import asyncio
import json
import sqlite3
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from campus247.application.conversation.messages import (
    ConversationMessageService,
    SenderType,
)
from campus247.application.identity.session_service import SessionService
from campus247.bootstrap.app import create_app
from campus247.bootstrap.run_storage import run_storage
from campus247.bootstrap.settings import Settings
from campus247.bootstrap.unified_demo import create_unified_demo_app
from campus247.domain.shared.values import generate_uuid7
from campus247.infrastructure.identity.mock import SyntheticIdentityAdapter
from campus247.infrastructure.llm.fake import DeterministicFakeProvider
from campus247.infrastructure.repositories.sqlite_actor_state import (
    SQLiteActorStateStore,
)
from campus247.infrastructure.repositories.sqlite_agent_runs import (
    RunConflict,
    RunStorageCorrupt,
    SQLiteAgentRunStore,
)
from campus247.infrastructure.repositories.sqlite_auxiliary import SQLiteRevocationStore
from campus247.infrastructure.repositories.sqlite_conversations import (
    SQLiteConversationRepository,
)
from fastapi.testclient import TestClient

from tests.api.test_service_stage6 import act, login, read, sent

TENANT = "huce-local-public"
OWNER = "4b419a1b-6d41-7dfb-8943-2edd9f071385"
OTHER = "97c5ab40-6399-7ad3-9838-eab50f267b2d"


def tables(path):
    with sqlite3.connect(path.as_uri()+"?mode=ro",uri=True) as connection:
        return {name:connection.execute('SELECT * FROM "'+name.replace('"','""')+'" ORDER BY rowid').fetchall()
                for name, in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}


@pytest.fixture
def main_runtime(tmp_path):
    state,history = tmp_path / "actor.sqlite3",tmp_path / "history.sqlite3"
    SQLiteActorStateStore(state);repository = SQLiteConversationRepository(history)
    settings = Settings(_env_file=None,OPENAI_API_KEY=None,GEMINI_API_KEY=None,DEEPSEEK_API_KEY=None,
        ACTOR_STATE_STORAGE_MODE="sqlite",ACTOR_STATE_SQLITE_PATH=state,
        CONSENT_STORAGE_MODE="sqlite",CONSENT_SQLITE_PATH=state)
    def app(tenant=TENANT):
        history_path = history if tenant == TENANT else tmp_path / "other-tenant-history.sqlite3"
        return create_app(runtime_settings=settings,synthetic_tenant_id=tenant,
            conversation_repository=SQLiteConversationRepository(history_path),llm_gateway=DeterministicFakeProvider.default())
    adapter = SyntheticIdentityAdapter(settings.IDENTITY_SECRET_KEY,environment="development",tenant_id=TENANT)
    headers = {"Authorization":"Bearer "+adapter.mint_token(OWNER)}
    other = {"Authorization":"Bearer "+adapter.mint_token(OTHER)}
    client = TestClient(app());service = ConversationMessageService(repository)
    try:yield app,client,headers,other,service,state,history
    finally:client.close()


def test_privacy_request_restart_replay_and_owner_tenant_concealment(main_runtime):
    factory,client,headers,other,_,state,_ = main_runtime
    body = {"request_type":"CORRECTION","correction_summary":"Private fixture correction","client_id":generate_uuid7()}
    before = tables(state)
    response = client.post("/v1/privacy/requests",headers=headers,json=body)
    assert response.status_code == 201,response.text
    replay = client.post("/v1/privacy/requests",headers=headers,json=body)
    assert replay.json() == response.json()
    with TestClient(factory()) as restarted:
        result = restarted.get(response.headers["location"],headers=headers)
        assert result.status_code == 200 and result.json()["status"] == "RECEIVED"
        assert "internal_notes" not in result.json() and "correction_summary" not in result.json()
        assert restarted.get(response.headers["location"],headers=other).status_code == 404
    with TestClient(factory("other-tenant")) as tenant_client:
        adapter = SyntheticIdentityAdapter("campus247-demo-secret-key-huce",environment="development",tenant_id="other-tenant")
        assert tenant_client.get(response.headers["location"],headers={"Authorization":"Bearer "+adapter.mint_token(OWNER)}).status_code == 404
    conflicting = {**body,"correction_summary":"Changed intent"}
    assert client.post("/v1/privacy/requests",headers=headers,json=conflicting).status_code == 409
    after = tables(state)
    assert len(after["unified_actor_state"]) == len(after["unified_state_revision"]) == len(after["unified_state_receipt"]) == 1
    assert before["unified_actor_state"] == []


def test_feedback_restart_replay_reference_readback_and_no_history_mutation(main_runtime):
    factory,client,headers,other,service,state,history = main_runtime
    conversation = asyncio.run(service.create_conversation(OWNER))
    message = asyncio.run(service.append_message(conversation.id,SenderType.ASSISTANT,"A retained fixture answer"))
    before = tables(history);path = f"/v1/conversations/{conversation.id}/messages/{message.id}/feedback"
    body = {"rating":"HELPFUL","comment":"Private fixture feedback","client_id":generate_uuid7()}
    response = client.post(path,headers=headers,json=body)
    assert response.status_code == 201,response.text
    assert response.json()["answer_reference"]["model_version"] == "unknown"
    assert client.post(path,headers=headers,json=body).json() == response.json()
    with TestClient(factory()) as restarted:
        result = restarted.get(response.headers["location"],headers=headers)
        assert result.status_code == 200 and result.json() == response.json()
        assert "comment" not in result.json()
        assert restarted.get(response.headers["location"],headers=other).status_code == 404
    assert client.post(path,headers=headers,json={**body,"rating":"NOT_HELPFUL"}).status_code == 409
    assert tables(history) == before
    assert len(tables(state)["unified_state_receipt"]) == 1


def test_logout_and_authentication_share_durable_store_across_restart(main_runtime):
    factory,client,headers,_,_,state,_ = main_runtime
    assert client.get("/v1/users/me",headers=headers).status_code == 200
    revoked = client.post("/v1/auth/logout",headers=headers)
    assert revoked.status_code == 200,revoked.text
    assert client.get("/v1/users/me",headers=headers).status_code == 401
    assert client.post("/v1/auth/logout",headers=headers).status_code == 200
    with TestClient(factory()) as restarted:
        assert restarted.get("/v1/users/me",headers=headers).status_code == 401
    encoded = json.dumps(tables(state),ensure_ascii=False)
    assert headers["Authorization"][7:] not in encoded
    assert len(tables(state)["unified_state_receipt"]) == 1


@pytest.mark.parametrize("operation",["privacy","feedback","revocation"])
@pytest.mark.parametrize("table",["unified_state_revision","unified_state_receipt"])
def test_auxiliary_audit_receipt_failure_has_no_partial_success(main_runtime,operation,table):
    _,client,headers,_,service,state,_ = main_runtime
    if operation == "feedback":
        conversation = asyncio.run(service.create_conversation(OWNER))
        message = asyncio.run(service.append_message(conversation.id,SenderType.ASSISTANT,"Fixture"))
    with sqlite3.connect(state) as connection:
        connection.execute("CREATE TRIGGER fixture_abort BEFORE INSERT ON "+table+" BEGIN SELECT RAISE(ABORT,'fixture failure'); END")
    if operation == "privacy": response = client.post("/v1/privacy/requests",headers=headers,json={"request_type":"EXPORT","client_id":generate_uuid7()})
    elif operation == "feedback": response = client.post(f"/v1/conversations/{conversation.id}/messages/{message.id}/feedback",headers=headers,json={"rating":"HELPFUL","client_id":generate_uuid7()})
    else: response = client.post("/v1/auth/logout",headers=headers)
    assert response.status_code == 503,response.text
    assert all(tables(state)[name] == [] for name in ("unified_actor_state","unified_state_revision","unified_state_receipt"))
    assert client.get("/v1/users/me",headers=headers).status_code == 200


def test_revocation_db_failure_returns_503_rather_than_authenticated_or_fake_401(main_runtime,tmp_path):
    _,client,headers,_,_,_,_ = main_runtime
    store = client.app.state.current_session_service._store.store
    missing = tmp_path / "missing.sqlite3";store.path = missing
    response = client.get("/v1/users/me",headers=headers)
    assert response.status_code == 503 and response.json()["code"] == "DEPENDENCY_UNAVAILABLE"
    assert not missing.exists()


def test_concurrent_revocation_once_and_tenant_isolation(tmp_path):
    path = tmp_path / "state.sqlite3";SQLiteActorStateStore(path)
    def revoke(_):
        service = SessionService(SQLiteRevocationStore(SQLiteActorStateStore(path),tenant=TENANT))
        return service.revoke_session("fixture.raw.token",actor_id=OWNER)
    with ThreadPoolExecutor(max_workers=2) as pool:results = list(pool.map(revoke,range(2)))
    assert all(result["status"] == "revoked" for result in results)
    assert len(tables(path)["unified_state_receipt"]) == 1
    other = SessionService(SQLiteRevocationStore(SQLiteActorStateStore(path),tenant="other-tenant"))
    assert not other.is_revoked("fixture.raw.token")


@pytest.fixture
def candidate(tmp_path):
    business,state = tmp_path / "business.sqlite3",tmp_path / "state.sqlite3"
    app = create_unified_demo_app(business,state_database=state,consent_mode="sqlite")
    with TestClient(app) as client:yield app,client,business,state


def staff_record(client):
    _,record,_ = sent(client)
    headers = login(client,"OF002")
    claimed = act(client,headers,record,"claim")
    assert claimed.status_code == 200,claimed.text
    return headers,claimed.json()["document_request"]


def draft_body(record,text="Unsent private manual text",version=0,client_id=None):
    return {"resource":{"kind":"service_request","id":record["id"],"expected_version":record["version"]},
        "text":text,"expected_draft_version":version,"client_id":client_id if client_id is not None else generate_uuid7()}


def test_staff_draft_commit_restart_cas_and_private_readback(candidate):
    _,client,business,state = candidate;headers,record = staff_record(client)
    before = tables(business);body = draft_body(record)
    saved = client.post("/v1/assistant/staff-drafts/save",headers=headers,json=body)
    assert saved.status_code == 201,saved.text
    assert saved.json()["saved"] and saved.json()["action_authority"] == "none"
    assert client.post("/v1/assistant/staff-drafts/save",headers=headers,json=body).json()["is_replay"]
    with TestClient(create_unified_demo_app(business,state_database=state)) as restarted:
        restored = restarted.post("/v1/assistant/staff-drafts/read",headers=headers,json={"resource":body["resource"]})
        assert restored.status_code == 200 and restored.json()["text"] == body["text"] and restored.json()["saved"]
        conflict = restarted.post("/v1/assistant/staff-drafts/save",headers=headers,json=draft_body(record,"Another tab",version=0))
        assert conflict.status_code == 409 and "receipt_id" not in conflict.json()
        assert restarted.post("/v1/assistant/staff-drafts/read",headers=login(restarted),json={"resource":body["resource"]}).status_code == 403
    assert tables(business) == before
    assert len(tables(state)["unified_state_receipt"]) == 1


def test_reassignment_blocks_old_officer_draft_but_retains_text(candidate):
    _,client,_,state = candidate;headers,record = staff_record(client);body = draft_body(record)
    assert client.post("/v1/assistant/staff-drafts/save",headers=headers,json=body).status_code == 201
    before = tables(state)
    directory = client.get("/v1/service-staff-directory",headers=headers)
    assert directory.status_code == 200
    target = next(item for item in directory.json()["items"] if "HUCE_GENERAL" in item["queues"])
    transfer = act(client,headers,record,"transfer",target_user_id=target["user_id"],target_queue="HUCE_GENERAL")
    assert transfer.status_code == 200,transfer.text
    assert client.post("/v1/assistant/staff-drafts/read",headers=headers,json={"resource":body["resource"]}).status_code == 404
    assert client.post("/v1/assistant/staff-drafts/save",headers=headers,json=draft_body(record,"Old proposal",1)).status_code == 404
    moved = read(client,login(client,"OF001"),record["id"],staff=True)
    incoming = client.post("/v1/assistant/staff-drafts/read",headers=login(client,"OF001"),json={"resource":draft_body(moved)["resource"]})
    assert incoming.status_code == 200 and not incoming.json()["saved"] and incoming.json()["text"] == ""
    assert tables(state) == before


@pytest.mark.parametrize("target",["unified_state_revision","unified_state_receipt"])
def test_staff_draft_commit_error_does_not_claim_saved(candidate,target):
    _,client,_,state = candidate;headers,record = staff_record(client)
    with sqlite3.connect(state) as connection:
        connection.execute("CREATE TRIGGER fixture_abort BEFORE INSERT ON "+target+" BEGIN SELECT RAISE(ABORT,'fixture failure'); END")
    response = client.post("/v1/assistant/staff-drafts/save",headers=headers,json=draft_body(record))
    assert response.status_code == 503 and "saved" not in response.json()
    assert tables(state)["unified_actor_state"] == []


def test_concurrent_staff_tabs_commit_one_and_keep_manual_text(candidate):
    from campus247.application.assistance.state_storage import StorageConflict
    app,client,_,state = candidate;_,record = staff_record(client)
    directory = client.post("/v1/auth/demo-login",json={"account":"OF002"}).json()
    adapter = SyntheticIdentityAdapter("campus247-demo-secret-key-huce",environment="development",tenant_id=TENANT)
    identity = adapter.resolve_token(directory["token"])
    resource = draft_body(record)["resource"]
    def save(text):
        try:return app.state.staff_drafts.save(identity,resource,text,0,generate_uuid7())
        except StorageConflict:return "StorageConflict"
    with ThreadPoolExecutor(max_workers=2) as pool:outcomes = list(pool.map(save,["Tab A manual text","Tab B manual text"]))
    assert sum(outcome == "StorageConflict" for outcome in outcomes) == 1
    restored = app.state.staff_drafts.read(identity,resource)
    assert restored["text"] in {"Tab A manual text","Tab B manual text"}
    assert len(tables(state)["unified_state_receipt"]) == 1


def test_explicit_run_store_tenant_restart_lease_and_no_duplicate_transition(tmp_path):
    path = tmp_path / "runs.sqlite3";store = SQLiteAgentRunStore(path,tenant=TENANT)
    run,conversation = generate_uuid7(),generate_uuid7()
    store.create(run,OWNER,conversation,{"goal":"Retained fixture"},10)
    store.save(run,OWNER,conversation,1,"waiting_user",{"goal":"Retained fixture"},event={"type":"waiting"})
    def resume(_):
        try:return SQLiteAgentRunStore(path,tenant=TENANT).claim_resume(run,OWNER,conversation,2,10)
        except RunConflict:return "conflict"
    with ThreadPoolExecutor(max_workers=2) as pool:results = list(pool.map(resume,range(2)))
    assert sorted(str(result) for result in results) == ["3","conflict"]
    final = SQLiteAgentRunStore(path,tenant=TENANT)
    final.save(run,OWNER,conversation,3,"completed",{"final_result":{"content":"committed fixture result"}},event={"type":"done"})
    assert SQLiteAgentRunStore(path,tenant=TENANT).get(run,OWNER,conversation)["final_result"]["content"] == "committed fixture result"
    assert len(final.get(run,OWNER,conversation)["events"]) == 2
    before = tables(path)
    with pytest.raises(RunStorageCorrupt):SQLiteAgentRunStore(path,tenant="other-tenant")
    assert tables(path) == before


def test_configured_run_selection_is_explicit_and_requires_existing_file(tmp_path):
    path = tmp_path / "runs.sqlite3";SQLiteAgentRunStore(path,tenant=TENANT)
    settings = Settings(_env_file=None,AGENT_RUN_STORAGE_MODE="sqlite",AGENT_RUN_SQLITE_PATH=path)
    store,profile = run_storage(settings,TENANT)
    assert isinstance(store,SQLiteAgentRunStore) and profile["tenant_binding"] == "bound" and not profile["fallback"]
    with pytest.raises(ValueError):run_storage(settings,TENANT,store)
    missing = tmp_path / "missing.sqlite3"
    with pytest.raises(sqlite3.OperationalError):run_storage(Settings(_env_file=None,AGENT_RUN_STORAGE_MODE="sqlite",AGENT_RUN_SQLITE_PATH=missing),TENANT)
    assert not missing.exists()


def test_run_record_initially_corrupt_is_rejected_without_repair(tmp_path):
    path = tmp_path / "runs.sqlite3";store = SQLiteAgentRunStore(path)
    identifier,conversation = generate_uuid7(),generate_uuid7()
    with sqlite3.connect(path) as connection:
        connection.execute("INSERT INTO agent_run VALUES(?,?,?,?,?,?,?,?)",(identifier,OWNER,conversation,1,"running",0,0,"{"))
    before = tables(path)
    with pytest.raises(RunStorageCorrupt):store.get(identifier,OWNER,conversation)
    assert tables(path) == before


@pytest.mark.parametrize("kind",["preferences","resume"])
def test_actual_two_process_cas_or_resume_has_one_commit(tmp_path,kind):
    root = Path(__file__).resolve().parents[2];database = tmp_path / "process.sqlite3"
    run,conversation = generate_uuid7(),generate_uuid7()
    if kind == "preferences":SQLiteActorStateStore(database)
    else:
        store = SQLiteAgentRunStore(database,tenant=TENANT)
        store.create(run,OWNER,conversation,{"goal":"Process fixture"},10)
        store.save(run,OWNER,conversation,1,"waiting_user",{"goal":"Process fixture"})
    gate = tmp_path / "gate.json";processes = []
    for index in range(2):
        command = [sys.executable,"-B",str(root / "scripts/probe_unified_storage_process07.py"),"--kind",kind,
            "--database",str(database),"--gate",str(gate),"--ready",str(tmp_path / f"ready-{index}.json"),
            "--output",str(tmp_path / f"result-{index}.json"),"--client",generate_uuid7(),"--run",run,"--conversation",conversation,"--fixture-root",str(tmp_path)]
        with (tmp_path / f"worker-{index}.log").open("xb") as log:
            processes.append(subprocess.Popen(command,cwd=root,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,creationflags=0x08000000))
    deadline = time.monotonic()+10
    while not all((tmp_path / f"ready-{index}.json").exists() for index in range(2)):
        assert time.monotonic() < deadline
        time.sleep(.02)
    with gate.open("x",encoding="utf-8") as stream:json.dump({"go":True},stream)
    for process in processes:assert process.wait(timeout=15) == 0
    results = [json.loads((tmp_path / f"result-{index}.json").read_text()) for index in range(2)]
    assert sum(result["state"] == "conflict" for result in results) == 1
    if kind == "preferences":assert len(tables(database)["unified_state_receipt"]) == 1
    else:assert SQLiteAgentRunStore(database,tenant=TENANT).get(run,OWNER,conversation)["version"] == 3


def test_conversation_tenant_binding_prevents_cross_tenant_factory_reuse(tmp_path):
    path = tmp_path / "history.sqlite3"
    repo = SQLiteConversationRepository(path,tenant=TENANT)
    record = asyncio.run(ConversationMessageService(repo).create_conversation(OWNER))
    before = tables(path)
    with pytest.raises(Exception,match="TENANT_MISMATCH"):
        SQLiteConversationRepository(path,tenant="other-tenant")
    assert tables(path) == before
    assert asyncio.run(SQLiteConversationRepository(path,tenant=TENANT).get_conversation(record.id)) is not None


def test_unknown_legacy_tenant_is_not_assigned_by_inference(tmp_path):
    path = tmp_path / "legacy.sqlite3";repo = SQLiteConversationRepository(path)
    asyncio.run(ConversationMessageService(repo).create_conversation(OWNER))
    before = tables(path)
    with pytest.raises(Exception,match="LEGACY_CONVERSATION_TENANT_UNBOUND"):repo.bind_tenant(TENANT)
    assert tables(path) == before


def test_candidate_validated_held_history_and_feedback_use_no_writer_dispatch(tmp_path):
    import httpx
    from campus247.application.conversation.stream_result import FinalChatResult
    history = tmp_path / "history.sqlite3";repo = SQLiteConversationRepository(history)
    messages = ConversationMessageService(repo)
    conversation = asyncio.run(messages.create_conversation(OWNER))
    user = asyncio.run(messages.append_message(conversation.id,SenderType.USER,"Fixture history",OWNER))
    final = FinalChatResult("abstained","clarification_request","A retained clarification")
    answer = asyncio.run(messages.append_message(conversation.id,SenderType.ASSISTANT,final.content,final_result=final))
    before = tables(history)
    def unexpected(request):raise AssertionError("Held GET/feedback must not dispatch to the writer")
    app = create_unified_demo_app(tmp_path / "business.sqlite3",state_database=tmp_path / "state.sqlite3",
        history_database=history,rag_transport=httpx.MockTransport(unexpected))
    with TestClient(app) as client:
        headers = login(client)
        response = client.get(f"/v1/conversations/{conversation.id}/messages",headers=headers)
        assert response.status_code == 200,response.text
        assert [item["id"] for item in response.json()["items"]] == [user.id,answer.id]
        assert response.json()["items"][1]["final_result"]["response_class"] == "clarification_request"
        assert client.get(f"/v1/conversations/{conversation.id}/messages",headers=login(client,"SV024")).status_code == 404
        assert client.get(f"/v1/conversations/{conversation.id}/messages",headers=login(client,"OF001")).status_code == 403
        feedback = client.post(f"/v1/conversations/{conversation.id}/messages/{answer.id}/feedback",headers=headers,
            json={"rating":"HELPFUL","client_id":generate_uuid7()})
        assert feedback.status_code == 201,feedback.text
    assert tables(history) == before


def test_held_history_missing_path_fails_without_creating_replacement(tmp_path):
    from campus247.application.conversation.messages import (
        ConversationStorageUnavailable,
    )
    from campus247.infrastructure.repositories.held_history import HeldHistoryRepository
    missing = tmp_path / "missing.sqlite3"
    with pytest.raises(ConversationStorageUnavailable):HeldHistoryRepository(missing,tenant=TENANT)
    assert not missing.exists()


@pytest.mark.parametrize("field,bad",[("created_at",None),("retention_expires_at","2026-10-14T00:00:00"),("version",True)])
def test_corrupt_history_feedback_fails_503_without_empty_success_or_repair(main_runtime,field,bad):
    _,client,headers,_,service,_,history = main_runtime
    conversation = asyncio.run(service.create_conversation(OWNER))
    answer = asyncio.run(service.append_message(conversation.id,SenderType.ASSISTANT,"Fixture answer"))
    with sqlite3.connect(history) as connection:
        value = json.loads(connection.execute("SELECT record FROM conversation WHERE id=?",(conversation.id,)).fetchone()[0])
        value[field] = bad
        connection.execute("UPDATE conversation SET record=? WHERE id=?",(json.dumps(value),conversation.id))
    before = tables(history)
    response = client.post(f"/v1/conversations/{conversation.id}/messages/{answer.id}/feedback",headers=headers,
        json={"rating":"HELPFUL","client_id":generate_uuid7()})
    assert response.status_code == 503 and "recorded_at" not in response.json()
    assert tables(history) == before


def test_redaction_timestamp_restores_for_immutable_feedback_binding(main_runtime):
    _,client,headers,_,service,_,history = main_runtime
    conversation = asyncio.run(service.create_conversation(OWNER))
    answer = asyncio.run(service.append_message(conversation.id,SenderType.ASSISTANT,"Retained redacted fixture"))
    with sqlite3.connect(history) as connection:
        value = json.loads(connection.execute("SELECT record FROM message WHERE id=?",(answer.id,)).fetchone()[0])
        value["redacted_at"] = answer.created_at.isoformat()
        connection.execute("UPDATE message SET record=? WHERE id=?",(json.dumps(value),answer.id))
    body = {"rating":"HELPFUL","client_id":generate_uuid7()}
    path = f"/v1/conversations/{conversation.id}/messages/{answer.id}/feedback"
    result = client.post(path,headers=headers,json=body)
    assert result.status_code == 201,result.text
    assert client.post(path,headers=headers,json=body).json() == result.json()


@pytest.mark.parametrize("namespace,payload_field",[("privacy_request","request_id"),("revocation","token_sha256")])
def test_state_commit_cannot_bind_payload_to_different_key(tmp_path,namespace,payload_field):
    from campus247.application.assistance.state_storage import StateScope
    store = SQLiteActorStateStore(tmp_path / "state.sqlite3")
    key = generate_uuid7() if namespace == "privacy_request" else "a"*64
    wrong = generate_uuid7() if namespace == "privacy_request" else "b"*64
    payload = {payload_field:wrong,"request_type":"EXPORT"} if namespace == "privacy_request" else {payload_field:wrong,"reason":"logout"}
    before = tables(store.path)
    with pytest.raises(ValueError,match="resource/key mismatch"):
        store.commit(StateScope(TENANT,OWNER),namespace,key,0,payload,generate_uuid7())
    assert tables(store.path) == before


@pytest.mark.parametrize("target",["event","task","cache"])
def test_corrupt_run_records_fail_closed_and_keep_evidence(tmp_path,target):
    from campus247.application.multi_agent.contracts import TaskSpec
    path = tmp_path / "runs.sqlite3";store = SQLiteAgentRunStore(path,tenant=TENANT)
    identifier,conversation = generate_uuid7(),generate_uuid7()
    store.create(identifier,OWNER,conversation,{"goal":"Fixture run"},10)
    store.save(identifier,OWNER,conversation,1,"waiting_user",{},event={"type":"waiting","seq":999})
    assert store.get(identifier,OWNER,conversation)["events"][0]["seq"] == 1
    store.add_tasks(identifier,[TaskSpec(id="T1",role="research",goal="Fixture",coverage_ids=["Q1"],tools=["read_source"])])
    with sqlite3.connect(path) as connection:
        if target == "event":connection.execute("UPDATE agent_event SET record=? WHERE run_id=?",(json.dumps({"seq":2}),identifier))
        elif target == "task":connection.execute("UPDATE agent_task SET record=? WHERE run_id=?",(json.dumps({"spec":{"id":"T2"}}),identifier))
        else:connection.execute("INSERT INTO agent_cache VALUES('fixture','null')")
    before = tables(path)
    with pytest.raises(RunStorageCorrupt):
        if target == "event":store.get(identifier,OWNER,conversation)
        elif target == "task":store.tasks(identifier)
        else:store.cache_get("fixture")
    assert tables(path) == before
