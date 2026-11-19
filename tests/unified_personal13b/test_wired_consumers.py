"""Actual A+B composition, business outbox, fresh identity and B worker readback."""
from datetime import datetime, timedelta, timezone
import json

from fastapi.testclient import TestClient
import pytest

from campus247.bootstrap.unified_demo import create_unified_demo_app
from campus247.domain.shared.values import generate_uuid7
from campus247.infrastructure.identity.mock import SyntheticIdentityAdapter
from campus247.infrastructure.repositories.sqlite_assistant_memory import SQLiteAssistantMemory
from campus247.infrastructure.repositories.sqlite_assistant_tracking import SQLiteAssistantTracking
from campus247_worker.assistant_tracking.worker import AssistantTrackingWorker
from tests.api.test_service_stage6 import sent, login, act, read
from tests.integration.test_unified_staff12 import target
from tests.unified_personal13b.test_memory_tracking import value


@pytest.fixture
def wired(tmp_path):
    memory = SQLiteAssistantMemory(tmp_path/'memory.sqlite3', initialize=True)
    tracking = SQLiteAssistantTracking(tmp_path/'tracking.sqlite3', initialize=True)
    app = create_unified_demo_app(tmp_path/'business.sqlite3', state_database=tmp_path/'actor.sqlite3', consent_mode='sqlite',
        personal_memory_store=memory, personal_tracking_store=tracking)
    with TestClient(app) as client:
        student, record, _ = sent(client)
        staff = login(client, 'OF002')
        result = act(client, staff, record, 'claim')
        assert result.status_code == 200, result.text
        yield app, client, student, staff, result.json()['document_request'], tmp_path


def actor(headers):
    adapter = SyntheticIdentityAdapter('campus247-demo-secret-key-huce', environment='development', tenant_id='huce-local-public')
    return adapter.resolve_token(headers['Authorization'].split(' ')[1])


def consent(app, headers):
    identity = actor(headers)
    service = app.state.assistant_preferences
    preview = service.prepare_consent(identity, 'OPTIONAL_PERSONALIZATION', 'GRANTED', service.notice().version, 0, generate_uuid7())
    return service.confirm(identity, preview, confirmed=True)


def preview_confirm(client, headers, feature, change):
    prepared = client.post('/v1/assistant/'+feature+'/preview', headers=headers, json=change)
    assert prepared.status_code == 200, prepared.text
    body = prepared.json()
    result = client.post('/v1/assistant/'+feature+'/confirm', headers=headers, json={
        **{key: body[key] for key in ('normalized_payload', 'confirmation_token')}, 'confirmed': True})
    assert result.status_code == 200, result.text
    return result.json()


def grant(client, headers, record, *, kind='service_request'):
    resource = {**target(record), 'kind': kind}
    prepared = client.post('/v1/assistant/grants:preview', headers=headers, json={'client_id': generate_uuid7(), 'resource': resource,
        'capability': 'read_source', 'purpose': 'source_assistance', 'lifetime': 'timed', 'lifetime_seconds': 600})
    assert prepared.status_code == 200, prepared.text
    body = prepared.json()
    result = client.post('/v1/assistant/grants:confirm', headers=headers, json={
        **{key: body[key] for key in ('normalized_payload', 'confirmation_token')}, 'confirmed': True})
    assert result.status_code == 200, result.text
    return result.json()['receipt']


def subscribe(client, headers, record, *, trigger='feedback', kind='service_request'):
    permission = grant(client, headers, record, kind=kind)
    subscription_id = generate_uuid7()
    change = {'operation': 'subscribe', 'subscription_id': subscription_id, 'client_id': subscription_id, 'expected_version': 0,
        'spec': {'resource': {**target(record), 'kind': kind}, 'trigger': trigger, 'channel': 'in_app',
            'expires_at': (datetime.now(timezone.utc)+timedelta(minutes=5)).isoformat(),
            'permission_id': permission['key'], 'permission_version': permission['version'], 'quiet_start_hour': 0, 'quiet_end_hour': 0}}
    return preview_confirm(client, headers, 'tracking', change)


def test_actual_scoped_context_consumer_and_forget_readback(wired):
    app, client, student, _, record, _ = wired
    consent(app, student)
    preview_confirm(client, student, 'memory', {'operation': 'control', 'enabled': True, 'client_id': generate_uuid7(), 'expected_version': 0})
    memory = preview_confirm(client, student, 'memory', {'operation': 'save', 'value': value(), 'client_id': generate_uuid7(), 'expected_version': 0})
    permission = grant(client, student, record)
    query = {'resource': target(record), 'grant_id': permission['key'], 'operation_id': generate_uuid7(), 'memory_terms': ['ngắn gọn']}
    result = client.post('/v1/assistant/context:compose', headers=student, json=query)
    assert result.status_code == 200, result.text
    original = result.json()
    assert original['content']['personal_memory']['items'][0]['text'] == value()['text']
    assert original['content']['personal_memory']['action_authority'] == 'none'
    preview_confirm(client, student, 'memory', {'operation': 'forget', 'key': memory['key'], 'client_id': generate_uuid7(), 'expected_version': 1})
    stale = client.post('/v1/assistant/context:revalidate', headers=student, json={'request': query, 'expected_sha256': original['manifest']['sha256']})
    assert stale.status_code == 409, stale.text
    current = client.post('/v1/assistant/context:compose', headers=student, json={**query, 'operation_id': generate_uuid7()})
    assert current.status_code == 200 and current.json()['content']['personal_memory']['items'] == []


@pytest.mark.parametrize('recipient', ['student', 'staff'])
def test_actual_business_event_worker_delivery_and_restart(wired, recipient):
    app, client, student, staff, record, path = wired
    headers = student if recipient == 'student' else staff
    subscribe(client, headers, record)
    result = act(client, staff, record, 'respond')
    assert result.status_code == 200, result.text
    changed = read(client, student, record['id'])
    worker = AssistantTrackingWorker(app.state.assistant_tracking)
    result = worker.tick()
    assert result['delivered'] == 1, result
    assert worker.tick()['delivered'] == 0
    response = client.get('/v1/assistant/tracking/notifications', headers=headers)
    assert response.status_code == 200, response.text
    items = response.json()['items']
    assert len(items) == 1 and items[0]['resource'] == target(changed)
    assert items[0]['audience'] == recipient
    assert 'PRIVATE' not in json.dumps(items)
    reopened = create_unified_demo_app(path/'business.sqlite3', state_database=path/'actor.sqlite3', consent_mode='sqlite',
        personal_memory_store=SQLiteAssistantMemory(path/'memory.sqlite3'), personal_tracking_store=SQLiteAssistantTracking(path/'tracking.sqlite3'))
    with TestClient(reopened) as restarted:
        assert AssistantTrackingWorker(reopened.state.assistant_tracking).tick()['delivered'] == 0
        readback = restarted.get('/v1/assistant/tracking/notifications', headers=headers)
        assert readback.status_code == 200 and len(readback.json()['items']) == 1


def test_actual_worker_revoke_recipient_before_delivery(wired):
    app, client, student, staff, record, _ = wired
    subscribe(client, student, record)
    assert act(client, staff, record, 'respond').status_code == 200
    token = student['Authorization'].split(' ')[1]
    app.state.service_requests.repository.revoke(app.state.current_session_service.hash_token(token))
    assert AssistantTrackingWorker(app.state.assistant_tracking).tick()['delivered'] == 0
    assert client.get('/v1/assistant/tracking/notifications', headers=student).status_code == 401


def test_no_preoptin_event_delivery(wired):
    app, client, student, _, record, _ = wired
    subscribe(client, student, record, trigger='status')
    assert AssistantTrackingWorker(app.state.assistant_tracking).tick()['delivered'] == 0
    assert client.get('/v1/assistant/tracking/notifications', headers=student).json()['items'] == []


def test_actual_notification_open_and_cross_recipient(wired):
    app, client, student, staff, record, _ = wired
    subscribe(client, student, record)
    assert act(client, staff, record, 'respond').status_code == 200
    assert AssistantTrackingWorker(app.state.assistant_tracking).tick()['delivered'] == 1
    item = client.get('/v1/assistant/tracking/notifications', headers=student).json()['items'][0]
    opened = client.post('/v1/assistant/cases/notification:open', headers=student, json={'event_id': item['event_id']})
    assert opened.status_code == 200, opened.text
    assert opened.json()['resource'] == item['resource']
    assert opened.json()['open_path'] == '/services?request='+record['id']
    other = login(client, 'SV024')
    assert client.post('/v1/assistant/cases/notification:open', headers=other, json={'event_id': item['event_id']}).status_code == 404


def test_actual_source_corruption_suppresses_delivery(wired):
    app, client, student, staff, record, _ = wired
    subscribe(client, student, record)
    assert act(client, staff, record, 'respond').status_code == 200
    with app.state.service_requests.repository.transaction() as tx:
        source = tx.item('knowledge_version', record['snapshot']['guidance']['version_id'])
        source['text'] += 'synthetic stale source'
        tx.update('knowledge_version', source)
    assert AssistantTrackingWorker(app.state.assistant_tracking).tick()['delivered'] == 0
    assert client.get('/v1/assistant/tracking/notifications', headers=student).json()['items'] == []


def test_actual_reassignment_blocks_old_officer_delivery(wired):
    app, client, _, staff, record, _ = wired
    subscribe(client, staff, record)
    assert act(client, staff, record, 'respond').status_code == 200
    with app.state.service_requests.repository.transaction() as tx:
        changed = tx.get(record['id'])
        changed['assigned_user_id'] = generate_uuid7()
        tx.save(changed)
    assert AssistantTrackingWorker(app.state.assistant_tracking).tick()['delivered'] == 0
    assert client.get('/v1/assistant/tracking/notifications', headers=staff).json()['items'] == []


def test_private_preparation_events_do_not_enter_notification_outbox(wired):
    from tests.api.test_service_stage6 import draft, preview
    app, client, student, _, _, _ = wired
    with app.state.service_requests.repository.transaction() as tx:
        before = len(app.state.case_workflow.repository.records(tx, 'tracking_event'))
        audit_before = len(app.state.case_workflow.repository.records(tx, 'event'))
    record = draft(client, student)
    preview(client, student, record)
    with app.state.service_requests.repository.transaction() as tx:
        assert len(app.state.case_workflow.repository.records(tx, 'tracking_event')) == before
        assert len(app.state.case_workflow.repository.records(tx, 'event')) > audit_before


@pytest.mark.parametrize('recipient', ['student', 'staff'])
def test_certificate_event_inbox_and_exact_role_open_path(wired, recipient):
    from tests.api.test_certificate_stage1 import submitted, action
    app, client, _, _, _, _ = wired
    student, identifier = submitted(client)
    record = client.get('/v1/document-requests/'+identifier, headers=student).json()
    staff = login(client, 'OF001')
    claimed = action(client, staff, identifier, 'accept', record['version'], generate_uuid7())
    assert claimed.status_code == 200, claimed.text
    record = claimed.json()['document_request']
    headers = student if recipient == 'student' else staff
    subscribe(client, headers, record, trigger='supplement', kind='certificate_request')
    updated = action(client, staff, identifier, 'request_supplement', record['version'], generate_uuid7(), note='Bổ sung thông tin mô phỏng')
    assert updated.status_code == 200, updated.text
    result = AssistantTrackingWorker(app.state.assistant_tracking).tick()
    assert result['delivered'] == 1, result
    inbox = client.get('/v1/assistant/tracking/notifications', headers=headers)
    assert inbox.status_code == 200, inbox.text
    item = inbox.json()['items'][0]
    opened = client.post('/v1/assistant/cases/notification:open', headers=headers, json={'event_id': item['event_id']})
    assert opened.status_code == 200, opened.text
    assert opened.json()['open_path'] == ('/tickets' if recipient == 'student' else '/staff')+'?request='+identifier


def test_actual_A_business_outbox_two_process_recovery(wired):
    import os
    from pathlib import Path
    import subprocess
    import sys
    _, client, student, staff, record, path = wired
    subscribe(client, student, record)
    assert act(client, staff, record, 'respond').status_code == 200
    config = path/'unified-worker-config.json'
    with config.open('x', encoding='utf-8') as handle:
        json.dump({'kind': 'unified', 'business_path': str(path/'business.sqlite3'), 'actor_path': str(path/'actor.sqlite3'),
            'memory_path': str(path/'memory.sqlite3'), 'tracking_path': str(path/'tracking.sqlite3')}, handle)
    script = Path(__file__).resolve().parents[2]/'scripts/unified_parallel_b_fixture_worker.py'
    outcomes = []
    for attempt in (1, 2):
        command = [sys.executable, '-B', str(script), str(config)]
        result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'}, timeout=30)
        with (path/f'unified-process-{attempt}.json').open('x', encoding='utf-8') as handle:
            json.dump({'command': command, 'exit': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr}, handle)
        assert result.returncode == 0, result.stderr
        outcomes.append(json.loads(result.stdout))
    assert [result['delivered'] for result in outcomes] == [1, 0]
    assert len(client.get('/v1/assistant/tracking/notifications', headers=student).json()['items']) == 1
