"""Explicit runtime storage wiring; read-only HTTP and internal fixture writes."""
import asyncio
from copy import deepcopy
import sqlite3

from fastapi.testclient import TestClient
import pytest

from campus247.application.assistance.state_storage import StateScope
from campus247.application.conversation.messages import ConversationMessageService, SenderType, ConversationStorageUnavailable
from campus247.bootstrap.app import create_app
from campus247.bootstrap.settings import Settings
from campus247.bootstrap.unified_demo import create_unified_demo_app
from campus247.infrastructure.identity.mock import SyntheticIdentityAdapter
from campus247.infrastructure.llm.fake import DeterministicFakeProvider
from campus247.infrastructure.repositories.sqlite_conversations import SQLiteConversationRepository
from tests.api.test_certificate_stage1 import login
from tests.api.test_service_stage6 import sent
from tests.unit.assistance.test_unified_contracts import PROPOSAL


def test_main_factory_resolves_configured_conversation_store_and_preserves_http_owner_scope(tmp_path,monkeypatch):
    monkeypatch.setenv("CAMPUS247_IDEMPOTENCY_DB",str(tmp_path / "idempotency.sqlite3"))
    path=tmp_path / "history.sqlite3"
    settings=Settings(_env_file=None,ENVIRONMENT="development",DEMO_MODE=True,OPENAI_API_KEY=None,GEMINI_API_KEY=None,DEEPSEEK_API_KEY=None,
        CONVERSATION_STORAGE_MODE="sqlite",CONVERSATION_SQLITE_PATH=path)
    owner="4b419a1b-6d41-7dfb-8943-2edd9f071385";other="97c5ab40-6399-7ad3-9838-eab50f267b2d"
    adapter=SyntheticIdentityAdapter(settings.IDENTITY_SECRET_KEY,environment="development")
    headers={"Authorization":"Bearer "+adapter.mint_token(owner)}
    app=create_app(runtime_settings=settings,llm_gateway=DeterministicFakeProvider.default())
    assert app.state.conversation_storage=={"mode":"sqlite","durability":"durable","fallback":False}
    # Plain clients keep this fixture independent of the PostgreSQL lifespan.
    client=TestClient(app)
    response=client.post("/v1/conversations",headers=headers,json={});assert response.status_code==201,response.text
    cid=response.json()["id"]
    saved=asyncio.run(ConversationMessageService(SQLiteConversationRepository(path)).append_message(cid,SenderType.USER,"Synthetic retained question",owner))
    restarted=TestClient(create_app(runtime_settings=settings,llm_gateway=DeterministicFakeProvider.default()))
    response=restarted.get(f"/v1/conversations/{cid}/messages",headers=headers);assert response.status_code==200,response.text
    assert response.json()["items"][0]["id"]==saved.id
    denied=restarted.get(f"/v1/conversations/{cid}/messages",headers={"Authorization":"Bearer "+adapter.mint_token(other)})
    assert denied.status_code==404
    client.close();restarted.close()


def test_candidate_storage_profile_reports_confirmed_actor_features_without_model_proxy_activation(tmp_path):
    path=tmp_path / "state.sqlite3";app=create_unified_demo_app(tmp_path / "business.sqlite3",state_database=path)
    with TestClient(app) as client:
        assert client.get("/v1/assistant/storage").status_code==401
        for actor in ["SV001","OF001","KA001"]:
            response=client.get("/v1/assistant/storage",headers=login(client,actor));assert response.status_code==200
            value=response.json()
            assert value["actor_state"]=="sqlite_internal" and value["fallback"] is False
            assert value["product_preferences_or_grants_enabled"] is True and response.headers["cache-control"]=="no-store"
            assert "path" not in response.text and "token" not in response.text
        h=login(client)
        assert client.post("/v1/assistant/storage",headers=h,json={"owner":"another","grant":"active"}).status_code==405
        with sqlite3.connect(path.as_uri()+"?mode=ro",uri=True) as connection:
            assert connection.execute("SELECT COUNT(*) FROM unified_actor_state").fetchone()[0]==0
        capability=client.get("/v1/assistant/capabilities",headers=h).json()
        assert capability["preferences"]=="durable_confirmed"
        assert capability["preference_model_consumer"]=="main_factory_only_existing_proxy_unchanged"


def test_unavailable_actor_state_returns_503_without_fallback_or_replacement(tmp_path):
    state=tmp_path / "state.sqlite3";missing=tmp_path / "missing.sqlite3"
    app=create_unified_demo_app(tmp_path / "business.sqlite3",state_database=state)
    app.state.actor_state_store.path=missing
    with TestClient(app) as client:
        response=client.get("/v1/assistant/storage",headers=login(client))
        assert response.status_code==503 and response.json()["code"]=="STATE_STORAGE_UNAVAILABLE"
        assert "sqlite_internal" not in response.text and not missing.exists()
    assert state.is_file()


def test_history_dependency_failure_returns_503_without_success_or_empty_history(tmp_path,monkeypatch):
    monkeypatch.setenv("CAMPUS247_IDEMPOTENCY_DB",str(tmp_path / "idempotency.sqlite3"))
    settings=Settings(_env_file=None,ENVIRONMENT="development",DEMO_MODE=True,OPENAI_API_KEY=None,GEMINI_API_KEY=None,DEEPSEEK_API_KEY=None,
        CONVERSATION_STORAGE_MODE="sqlite",CONVERSATION_SQLITE_PATH=tmp_path / "history.sqlite3")
    app=create_app(runtime_settings=settings,llm_gateway=DeterministicFakeProvider.default())
    adapter=SyntheticIdentityAdapter(settings.IDENTITY_SECRET_KEY,environment="development")
    h={"Authorization":"Bearer "+adapter.mint_token("4b419a1b-6d41-7dfb-8943-2edd9f071385")}
    async def unavailable(*args,**kwargs):raise ConversationStorageUnavailable("fixture unavailable")
    monkeypatch.setattr(SQLiteConversationRepository,"get_conversation",unavailable)
    monkeypatch.setattr(SQLiteConversationRepository,"save_conversation",unavailable)
    client=TestClient(app)
    for method,path in [("GET","/v1/conversations/019a0000-0000-7000-8000-000000000001/messages"),("POST","/v1/conversations")]:
        response=client.request(method,path,headers=h,json={} if method=="POST" else None)
        assert response.status_code==503 and response.json()["code"]=="DEPENDENCY_UNAVAILABLE"
        assert "items" not in response.json() and "id" not in response.json()
    client.close()


def test_unconfigured_candidate_reports_no_state_storage_instead_of_false_durability(tmp_path):
    app=create_unified_demo_app(tmp_path / "business.sqlite3")
    with TestClient(app) as client:
        value=client.get("/v1/assistant/storage",headers=login(client)).json()
        assert value["actor_state"]=="not_configured" and value["state_namespaces"]==[] and value["receipts"]=="not_configured"


def test_draft_and_evidence_receipts_survive_candidate_restart_without_claiming_business_execution(tmp_path):
    business,state=tmp_path / "business.sqlite3",tmp_path / "state.sqlite3"
    app=create_unified_demo_app(business,state_database=state)
    with TestClient(app) as client:
        h,record,_=sent(client)
        package=client.post("/v1/assistant/workflows/resolve",headers=h,json={"resource":{"kind":"service_request","id":record["id"],"expected_version":record["version"]}}).json()
        scope=StateScope("huce-local-public",record["student_user_id"])
        receipts=[]
        for kind,payload in [("draft",deepcopy(PROPOSAL)),("evidence",package)]:
            receipts.append(app.state.actor_state_store.commit(scope,kind,"case-fixture",0,payload,"client-"+kind+"-001"))
    restarted=create_unified_demo_app(business,state_database=state)
    assert restarted.state.actor_state_store.get(scope,"draft","case-fixture").payload["action_authority"]=="none"
    assert restarted.state.actor_state_store.get(scope,"evidence","case-fixture").payload==package
    for kind,payload,receipt in [("draft",deepcopy(PROPOSAL),receipts[0]),("evidence",package,receipts[1])]:
        replay=restarted.state.actor_state_store.commit(scope,kind,"case-fixture",0,payload,"client-"+kind+"-001")
        assert replay.is_replay and replay.receipt_id==receipt.receipt_id


def test_candidate_rejects_shared_business_state_path_and_missing_state_directory(tmp_path):
    business=tmp_path / "business.sqlite3"
    with pytest.raises(ValueError,match="separate actor state"):create_unified_demo_app(business,state_database=business)
    with pytest.raises(ValueError,match="existing workspace directory"):
        create_unified_demo_app(business,state_database=tmp_path / "missing/state.sqlite3")
    assert not (tmp_path / "missing").exists()
