import asyncio
from fastapi.testclient import TestClient
from campus247.bootstrap.unified_demo import create_unified_demo_app
from campus247.application.conversation.messages import ConversationMessageService, SenderType
from campus247.infrastructure.repositories.sqlite_conversations import SQLiteConversationRepository
from campus247.infrastructure.identity.mock import SyntheticIdentityAdapter
from tests.integration.test_unified_staff12 import runtime
from tests.api.test_service_stage6 import read


def test_feature_off_manual_history_and_private_draft_restore_without_reset(runtime):
    app, client, student, staff, record, path = runtime
    adapter = SyntheticIdentityAdapter('campus247-demo-secret-key-huce', environment='development', tenant_id='huce-local-public')
    officer = adapter.resolve_token(staff['Authorization'].split(' ')[1])
    owner = adapter.resolve_token(student['Authorization'].split(' ')[1])
    resource = {'kind': 'service_request', 'id': record['id'], 'expected_version': record['version']}
    from campus247.domain.shared.values import generate_uuid7
    app.state.staff_drafts.save(officer, resource, 'Synthetic retained private draft', 0, generate_uuid7())
    history = path / 'history.sqlite3'
    service = ConversationMessageService(SQLiteConversationRepository(history, tenant='huce-local-public'))
    conv = asyncio.run(service.create_conversation(owner.subject_id))
    asyncio.run(service.append_message(conv.id, SenderType.USER, 'Synthetic retained history', owner.subject_id))
    disabled = create_unified_demo_app(path / 'business.sqlite3', history_database=history)
    with TestClient(disabled) as off:
        assert read(off, student, record['id'])['version'] == record['version']
        page = off.get(f'/v1/conversations/{conv.id}/messages', headers=student)
        assert page.status_code == 200 and len(page.json()['items']) == 1
    restored = create_unified_demo_app(path / 'business.sqlite3', state_database=path / 'state.sqlite3')
    draft = restored.state.staff_drafts.read(officer, resource)
    assert draft['text'] == 'Synthetic retained private draft' and draft['draft_version'] == 1
