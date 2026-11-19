"""Native chat mode, actual HTTP preparer and memory projection boundaries."""
import asyncio
from dataclasses import replace
from datetime import timedelta
import json

import pytest
from fastapi.testclient import TestClient

from campus247.agent.state import AgentState, DraftResponse, Terminal, NormalizedTurn
from campus247.agent.nodes.definitions import grounded_request
from campus247.application.conversation.messages import ConversationMessageService, ConversationConflict
from campus247.application.conversation.personal_context import with_personal_context
from campus247.application.document_request.certificates import CertificateError
from campus247.application.retrieval.citations import CitationBundle
from campus247.bootstrap.app import create_app
from campus247.bootstrap.settings import Settings
from campus247.bootstrap.unified_demo import create_unified_demo_app
from campus247.domain.shared.values import generate_uuid7
from campus247.infrastructure.identity.mock import SyntheticIdentityAdapter
from campus247.infrastructure.llm.fake import DeterministicFakeProvider
from campus247.infrastructure.repositories.sqlite_actor_state import SQLiteActorStateStore
from campus247.infrastructure.repositories.sqlite_assistant_memory import SQLiteAssistantMemory
from campus247.infrastructure.repositories.sqlite_conversations import SQLiteConversationRepository
from tests.integration.test_unified_storage_completion import OWNER, OTHER, TENANT
from tests.unified_personal13b.test_memory_tracking import env, control, save, confirm, value
from unified_completion_scope import completion_fixture


@pytest.mark.parametrize('mode', ['persistent', 'temporary'])
def test_mode_restart_owned_reader_and_idempotency(tmp_path, mode):
    repo = SQLiteConversationRepository(tmp_path / 'history.sqlite3', tenant=TENANT)
    service = ConversationMessageService(repo)
    client_id = generate_uuid7()
    conv = asyncio.run(service.create_conversation(OWNER, client_id=client_id, mode=mode))
    adapter = SyntheticIdentityAdapter('campus247-demo-secret-key-huce', environment='development', tenant_id=TENANT)
    actor = adapter.resolve_token(adapter.mint_token(OWNER))
    reopened = SQLiteConversationRepository(repo.path, tenant=TENANT)
    assert reopened.read_owned_mode(actor, conv.id) == mode
    assert reopened.read_owned_mode(replace(actor, subject_id=OTHER), conv.id) is None
    assert reopened.read_owned_mode(replace(actor, tenant_id='other'), conv.id) is None
    assert asyncio.run(service.create_conversation(OWNER, client_id=client_id, mode=mode)) == conv
    with pytest.raises(ConversationConflict):
        asyncio.run(service.create_conversation(OWNER, client_id=client_id, mode='temporary' if mode == 'persistent' else 'persistent'))
    assert (conv.retention_expires_at - conv.created_at) == timedelta(days=30)


@pytest.mark.parametrize('boundary', ['temporary', 'off', 'consent', 'actor', 'session', 'unknown', 'revoke', 'forget'])
def test_fresh_model_context_boundaries(env, boundary):
    control(env)
    receipt = save(env)
    env.mode = 'persistent'
    turn = NormalizedTurn(generate_uuid7(), generate_uuid7(), env.actor.subject_id, 'Trả lời ngắn gọn')
    live = [env.actor]
    prepared = with_personal_context(turn, env.actor, env.memory, current_identity=lambda: live[0])
    request = grounded_request(AgentState(request=prepared), CitationBundle.build([]))
    assert 'Tôi muốn câu trả lời ngắn gọn' in ''.join(item['content'] for item in request.input_items)
    assert 'Tôi muốn câu trả lời ngắn gọn' not in request.system_instructions
    if boundary == 'temporary': env.mode = 'temporary'
    elif boundary == 'off': control(env, False, 1)
    elif boundary == 'consent': env.consent = False
    elif boundary == 'actor': live[0] = replace(env.actor, subject_id=generate_uuid7())
    elif boundary == 'session': live[0] = replace(env.actor, session_id=generate_uuid7())
    elif boundary == 'unknown': env.mode = None
    elif boundary == 'revoke': env.revoked = True
    else:
        confirm(env.memory, env.actor, env.memory.prepare(env.actor, {'operation': 'forget', 'key': receipt['key'],
            'expected_version': 1, 'client_id': generate_uuid7()}))
    with pytest.raises(CertificateError): prepared.context_guard()


def test_temporary_does_not_retrieve_or_write_memory(env, monkeypatch):
    env.mode = 'temporary'
    monkeypatch.setattr(env.memory, 'retrieve', lambda *a, **k: pytest.fail('temporary retrieved memory'))
    monkeypatch.setattr(env.store, 'page', lambda *a, **k: pytest.fail('temporary inspected personal store'))
    turn = NormalizedTurn(generate_uuid7(), generate_uuid7(), env.actor.subject_id, 'ngắn gọn', presentation=lambda: None)
    prepared = with_personal_context(turn, env.actor, env.memory)
    assert prepared.personal_memory is None and prepared.presentation is None
    prepared.context_guard()
    with pytest.raises(CertificateError):
        env.memory.prepare(env.actor, {'operation': 'save', 'conversation_id': turn.session_id, 'value': value(),
            'expected_version': 0, 'client_id': generate_uuid7()})


@pytest.mark.parametrize('composition', ['native', 'unified'])
def test_actual_native_main_chat_memory_temporary_history_and_relogin(tmp_path, monkeypatch, composition):
    state = tmp_path / 'actor.sqlite3'
    SQLiteActorStateStore(state)
    memory = SQLiteAssistantMemory(tmp_path / 'memory.sqlite3', initialize=True)
    settings = Settings(_env_file=None, OPENAI_API_KEY=None, GEMINI_API_KEY=None, DEEPSEEK_API_KEY=None,
        ACTOR_STATE_STORAGE_MODE='sqlite', ACTOR_STATE_SQLITE_PATH=state,
        CONSENT_STORAGE_MODE='sqlite', CONSENT_SQLITE_PATH=state)
    def factory():
        native = create_app(runtime_settings=settings, synthetic_tenant_id=TENANT,
            conversation_repository=SQLiteConversationRepository(tmp_path / 'history.sqlite3'),
            personal_memory_store=memory, llm_gateway=DeterministicFakeProvider.default())
        if composition == 'native': return native
        return create_unified_demo_app(tmp_path / 'business.sqlite3', state_database=state, consent_mode='sqlite',
            personal_memory_store=memory, chat_application=native)
    app = factory()
    adapter = SyntheticIdentityAdapter(settings.IDENTITY_SECRET_KEY, environment='development', tenant_id=TENANT)
    actor = adapter.resolve_token(adapter.mint_token(OWNER))
    headers = {'Authorization': 'Bearer ' + adapter.mint_token(OWNER)}
    preferences = app.state.assistant_preferences
    preferences.confirm(actor, preferences.prepare_consent(actor, 'OPTIONAL_PERSONALIZATION', 'GRANTED',
        preferences.notice().version, 0, generate_uuid7()), confirmed=True)
    svc = app.state.assistant_memory
    confirm(svc, actor, svc.prepare(actor, {'operation': 'control', 'enabled': True, 'expected_version': 0, 'client_id': generate_uuid7()}))
    confirm(svc, actor, svc.prepare(actor, {'operation': 'save', 'value': value(), 'expected_version': 0, 'client_id': generate_uuid7()}))
    captured = []
    async def run(self, turn, **kwargs):
        captured.append(grounded_request(AgentState(request=turn), CitationBundle.build([])))
        return AgentState(request=turn, terminal=Terminal.ABSTAINED,
            draft=DraftResponse(text='Không đủ nguồn; hãy đối chiếu hồ sơ.'))
    monkeypatch.setattr('campus247.agent.graph.CampusAgentWorkflow.arun', run)
    with TestClient(app) as client:
        ids = {}
        for mode in ['persistent', 'temporary']:
            created = client.post('/v1/conversations', headers=headers, json={'client_id': generate_uuid7(), 'mode': mode})
            assert created.status_code == 201, created.text
            ids[mode] = created.json()['id']
            result = client.post(f"/v1/conversations/{ids[mode]}/messages:stream", headers=headers,
                json={'content': 'Trả lời ngắn gọn', 'client_id': generate_uuid7()})
            assert result.status_code == 200 and 'message.completed' in result.text, result.text
        assert any('Tôi muốn câu trả lời ngắn gọn' in p['content'] for p in captured[0].input_items)
        assert all('Tôi muốn câu trả lời ngắn gọn' not in p['content'] for p in captured[1].input_items)
        page = client.get('/v1/assistant/conversations', headers=headers).json()['items']
        assert [row['id'] for row in page] == [ids['persistent']]
        assert client.post('/v1/conversations', headers=headers, json={'mode': 'unknown'}).status_code == 422
    with TestClient(factory()) as reopened:
        for mode, identifier in ids.items():
            result = reopened.get(f'/v1/conversations/{identifier}/messages', headers={'Authorization': 'Bearer ' + adapter.mint_token(OWNER)})
            assert result.status_code == 200 and result.json()['mode'] == mode
            assert len(result.json()['items']) == 2
            assert reopened.get(f'/v1/conversations/{identifier}/messages', headers={'Authorization': 'Bearer ' + adapter.mint_token(OTHER)}).status_code == 404


def test_registered_process_scope_denies_outside_and_unregistered(tmp_path):
    assert completion_fixture(tmp_path)
    assert not completion_fixture(tmp_path.parent)
    assert not completion_fixture(tmp_path / 'child')
    assert not completion_fixture(tmp_path.parents[3] / 'preimages')


@pytest.mark.parametrize('timing', ['before_context', 'after_context_memory_off'])
def test_forget_cannot_reconstruct_personal_fact_from_retained_history(env, timing):
    from campus247.application.conversation.history import HistoryContext
    from campus247.application.conversation.context import TurnItem
    control(env)
    receipt = save(env)
    env.mode = 'persistent'
    history = HistoryContext(env.actor.subject_id, generate_uuid7(),
        (TurnItem(generate_uuid7(), 'user', value()['text']),), 100, 'fixture')
    turn = NormalizedTurn(history.conversation_id, generate_uuid7(), env.actor.subject_id, 'ngắn gọn', history=history)
    def forget():
        confirm(env.memory, env.actor, env.memory.prepare(env.actor, {'operation': 'forget', 'key': receipt['key'],
            'expected_version': 1, 'client_id': generate_uuid7()}))
    if timing == 'before_context':
        forget()
        prepared = with_personal_context(turn, env.actor, env.memory)
        assert prepared.history is None and prepared.personal_memory() is None
    else:
        control(env, False, 1)
        prepared = with_personal_context(turn, env.actor, env.memory)
        assert prepared.history == history
        forget()
        with pytest.raises(CertificateError, match='Suppression'): prepared.context_guard()
    assert history.turns[0].content == value()['text']  # No erasure of the source.
