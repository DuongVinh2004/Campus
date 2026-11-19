"""Fresh local B fixtures. No provider, retained DB, browser or DOM tests."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
import sqlite3
from types import SimpleNamespace

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
import pytest
from pydantic import ValidationError

from campus247.application.assistance.state_storage import StateScope, StorageConflict, StorageCorrupt
from campus247.application.assistant_memory.service import AssistantMemoryService
from campus247.application.assistant_tracking.service import AssistantTrackingService
from campus247.application.document_request.certificates import CertificateError
from campus247.bootstrap.assistant_personal_features import wire_assistant_personal_features
from campus247.domain.action.confirmation import ConfirmationTokenService
from campus247.domain.assistant_memory import MemoryValue, MemoryChange
from campus247.domain.assistant_tracking import BusinessTrackingEvent, NotificationProjection, SubscriptionSpec
from campus247.domain.shared.values import generate_uuid7
from campus247.infrastructure.repositories.sqlite_assistant_memory import SQLiteAssistantMemory
from campus247.infrastructure.repositories.sqlite_assistant_tracking import SQLiteAssistantTracking
from campus247.ports.identity import IdentityContext, IdentityRole


def identity(role=IdentityRole.STUDENT):
    now = datetime.now(timezone.utc)
    return IdentityContext(generate_uuid7(), 'fixture', 'fixture', (role,), 'Synthetic B', now,
        now+timedelta(hours=2), tenant_id='fixture-b', session_id=generate_uuid7(), student_code='B-SYNTHETIC' if role == IdentityRole.STUDENT else None)


@pytest.fixture
def env(tmp_path, request):
    actor = identity(getattr(request, 'param', IdentityRole.STUDENT))
    state = SimpleNamespace(consent=True, revoked=False, mode='settings', actor=actor, grant_revoked=False, source_version=1)
    def authorize(value):
        if state.revoked:
            raise CertificateError(403, 'SESSION_REVOKED', 'Synthetic session revoked')
    preferences = SimpleNamespace(consented=lambda actor, purpose: state.consent)
    def mode(actor, conversation):
        return state.mode
    store = SQLiteAssistantMemory(tmp_path/'memory.sqlite3', initialize=True)
    tokens = ConfirmationTokenService('synthetic-b-test-signing-key')
    memory = AssistantMemoryService(store, tenant='fixture-b', authorize=authorize, tokens=tokens,
        preferences=preferences, conversation_mode=mode, minimize=lambda text: text)
    state.memory, state.store, state.tokens, state.authorize, state.preferences, state.mode_reader = memory, store, tokens, authorize, preferences, mode
    return state


def confirm(service, actor, preview):
    return service.confirm(actor, preview['normalized_payload'], preview['confirmation_token'], confirmed=True)


def control(env, enabled=True, version=0):
    return confirm(env.memory, env.actor, env.memory.prepare(env.actor, {'operation': 'control', 'enabled': enabled, 'expected_version': version, 'client_id': generate_uuid7()}))


def value(**changes):
    return {'kind': 'preference', 'topic': 'Cách trả lời', 'text': 'Tôi muốn câu trả lời ngắn gọn', 'valid_until': (datetime.now(timezone.utc)+timedelta(days=30)).isoformat(), **changes}


def save(env, content=None, version=0, client_id=None):
    return confirm(env.memory, env.actor, env.memory.prepare(env.actor, {'operation': 'save', 'value': content or value(), 'expected_version': version, 'client_id': client_id or generate_uuid7()}))


def query(**changes):
    return {'terms': ['ngắn gọn'], **changes}


def test_opt_in_fresh_retrieval_source_and_authority(env):
    with pytest.raises(CertificateError, match='Memory'):
        save(env)
    control(env)
    receipt = save(env)
    result = env.memory.retrieve(env.actor, query())
    assert result['items'][0]['text'] == 'Tôi muốn câu trả lời ngắn gọn'
    assert result['items'][0]['source']['actor'] == env.actor.subject_id
    assert result['items'][0]['version'] == receipt['version']
    assert result['items'][0]['purpose'] == 'personal_assistance'
    assert result['action_authority'] == 'none'
    assert env.memory.retrieve(env.actor, query(terms=['không liên quan']))['items'] == []


@pytest.mark.parametrize('boundary', ['actor', 'tenant', 'role', 'session', 'revoked', 'consent'])
def test_memory_isolation_and_live_reauthorization(env, boundary):
    control(env)
    save(env)
    actor = env.actor
    if boundary == 'actor':
        actor = replace(actor, subject_id=generate_uuid7())
    elif boundary == 'tenant':
        actor = replace(actor, tenant_id='other')
    elif boundary == 'role':
        actor = replace(actor, roles=(IdentityRole.SUPPORT_OFFICER,))
    elif boundary == 'session':
        actor = replace(actor, auth_time=datetime.now(timezone.utc)-timedelta(hours=1), expires_at=datetime.now(timezone.utc)-timedelta(seconds=1))
    elif boundary == 'revoked':
        env.revoked = True
    else:
        env.consent = False
    if boundary == 'role':
        assert env.memory.retrieve(actor, query())['items'] == []
    else:
        with pytest.raises(CertificateError):
            env.memory.retrieve(actor, query())


def test_cas_correction_receipt_restart_and_conflict(env):
    control(env)
    original = value()
    receipt = save(env, original)
    changed = {**original, 'text': 'Tôi muốn giải thích từng bước ngắn gọn'}
    preview = env.memory.prepare(env.actor, {'operation': 'save', 'value': changed, 'expected_version': 1, 'client_id': generate_uuid7()})
    result = confirm(env.memory, env.actor, preview)
    assert result['version'] == 2
    assert confirm(env.memory, env.actor, preview)['is_replay']
    with pytest.raises(StorageConflict):
        save(env, original, version=1)
    reopened = SQLiteAssistantMemory(env.store.path)
    assert reopened.get(StateScope('fixture-b', env.actor.subject_id), 'memory', receipt['key'])['payload']['value']['text'] == changed['text']
    assert reopened.receipt(StateScope('fixture-b', env.actor.subject_id), result['client_id'])['version'] == 2


def test_forget_invalidates_derived_context_and_blocks_regeneration(env):
    control(env)
    original = value()
    receipt = save(env, original)
    prior = env.memory.retrieve(env.actor, query())
    preview = env.memory.prepare(env.actor, {'operation': 'forget', 'key': receipt['key'], 'expected_version': 1, 'client_id': generate_uuid7()})
    confirm(env.memory, env.actor, preview)
    assert env.memory.retrieve(env.actor, query())['items'] == []
    called = []
    with pytest.raises(CertificateError):
        env.memory.use(env.actor, query(), prior['sha256'], lambda result: called.append(result))
    assert called == []
    with pytest.raises(CertificateError, match='Topic'):
        save(env, original, version=2)
    page = env.memory.management(env.actor)
    assert page['items'][0]['state'] == 'suppressed' and 'value' not in page['items'][0]
    with sqlite3.connect(env.store.path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM personal_revision WHERE namespace='memory'").fetchone()[0] == 2


def test_temporary_no_read_write_control_or_forget(env):
    control(env)
    receipt = save(env)
    env.mode = 'temporary'
    assert env.memory.retrieve(env.actor, query())['items'] == []
    with pytest.raises(CertificateError):
        save(env)
    with pytest.raises(CertificateError):
        control(env, False, 1)
    with pytest.raises(CertificateError):
        env.memory.prepare(env.actor, {'operation': 'forget', 'key': receipt['key'], 'expected_version': 1, 'client_id': generate_uuid7()})


def test_off_retains_bytes_and_history_is_not_imported(env):
    control(env)
    save(env)
    control(env, False, 1)
    assert len(env.memory.management(env.actor)['items']) == 1
    with pytest.raises(CertificateError):
        env.memory.retrieve(env.actor, query())
    with pytest.raises(ValidationError):
        MemoryValue.model_validate(value(origin='ocr'))
    with pytest.raises(ValidationError):
        MemoryChange.model_validate({'operation': 'save', 'value': value(), 'expected_version': 0, 'client_id': generate_uuid7(), 'history': 'unowned'})


def test_preview_actor_session_payload_tamper_and_revoke(env):
    preview = env.memory.prepare(env.actor, {'operation': 'control', 'enabled': True, 'expected_version': 0, 'client_id': generate_uuid7()})
    for actor in (replace(env.actor, subject_id=generate_uuid7()), replace(env.actor, session_id=generate_uuid7())):
        with pytest.raises(CertificateError):
            confirm(env.memory, actor, preview)
    tampered = {**preview, 'normalized_payload': preview['normalized_payload'].replace('true', 'false')}
    with pytest.raises(CertificateError):
        confirm(env.memory, env.actor, tampered)
    env.consent = False
    with pytest.raises(CertificateError):
        confirm(env.memory, env.actor, preview)


def test_missing_mode_and_minimizer_fail_closed(env):
    env.memory.conversation_mode = None
    with pytest.raises(CertificateError) as error:
        control(env)
    assert error.value.status == 503
    env.memory.conversation_mode = env.mode_reader
    control(env)
    env.memory.minimize = None
    with pytest.raises(CertificateError) as error:
        env.memory.retrieve(env.actor, query())
    assert error.value.status == 503


def test_staff_resource_memory_prohibited(env):
    env.actor = identity(IdentityRole.SUPPORT_OFFICER)
    control(env)
    with pytest.raises(CertificateError) as error:
        save(env, value(scope='resource', resource={'kind': 'service_request', 'id': generate_uuid7(), 'expected_version': 1}, grant_id=generate_uuid7()))
    assert error.value.code == 'STAFF_CASE_MEMORY_PROHIBITED'


class DurableBusinessSource:
    """New synthetic business store: event and public record commit together."""
    def __init__(self, path):
        self.path = path
        with path.open('xb'):
            pass
        with sqlite3.connect(path) as connection:
            connection.execute('CREATE TABLE business(id TEXT PRIMARY KEY, version INTEGER, owner TEXT, assignment TEXT, public TEXT)')
            connection.execute('CREATE TABLE outbox(id TEXT PRIMARY KEY,body TEXT,acked INTEGER DEFAULT 0)')

    def emit(self, actor, resource, *, event_id=None, source_hash='a'*64, classification=None):
        audience = 'student' if actor.roles == (IdentityRole.STUDENT,) else 'staff'
        event = BusinessTrackingEvent(event_id=event_id or generate_uuid7(), tenant='fixture-b', recipient_id=actor.subject_id,
            audience=audience, resource=resource, trigger='status', source_id='synthetic-public-status', source_sha256=source_hash,
            changed_at=datetime.now(timezone.utc).isoformat(), classification=classification or ('public_student' if audience == 'student' else 'internal_staff'))
        with sqlite3.connect(self.path) as connection:
            connection.execute('INSERT INTO business VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET version=excluded.version,owner=excluded.owner,assignment=excluded.assignment,public=excluded.public', (resource['id'], resource['expected_version'], actor.subject_id, actor.subject_id, source_hash))
            connection.execute('INSERT INTO outbox(id,body) VALUES(?,?)', (event.event_id, event.model_dump_json()))
        return event

    def read_batch(self, *, limit):
        with sqlite3.connect(self.path) as connection:
            return [json.loads(row[0]) for row in connection.execute('SELECT body FROM outbox WHERE acked=0 ORDER BY id LIMIT ?', (limit,))]

    def ack(self, event_id):
        with sqlite3.connect(self.path) as connection:
            connection.execute('UPDATE outbox SET acked=1 WHERE id=?', (event_id,))

    def project(self, actor, spec, event):
        with sqlite3.connect(self.path) as connection:
            row = connection.execute('SELECT version,owner,assignment,public FROM business WHERE id=?', (event.resource.id,)).fetchone()
        if row is None or row != (event.resource.expected_version, actor.subject_id, actor.subject_id, event.source_sha256):
            raise CertificateError(403, 'SOURCE_OR_ASSIGNMENT_CHANGED', 'Exact synthetic source unavailable')
        return NotificationProjection(recipient_id=actor.subject_id, audience=event.audience, resource=event.resource,
            reason='Hồ sơ có cập nhật mới', source_id=event.source_id, source_sha256=event.source_sha256,
            updated_at=event.changed_at, next_action='review_status', classification=event.classification)


@pytest.fixture
def tracking(env, tmp_path):
    from campus247.application.assistance.feature_contracts import ActiveGrant, GrantSpec
    target = {'kind': 'service_request', 'id': generate_uuid7(), 'expected_version': 1}
    permission_id = generate_uuid7()
    now = datetime.now(timezone.utc)
    spec = GrantSpec(client_id=permission_id, resource=target, capability='read_source', purpose='source_assistance', lifetime='timed', lifetime_seconds=600)
    grant = ActiveGrant(spec=spec, audience='student' if env.actor.roles == (IdentityRole.STUDENT,) else 'staff', roles=sorted(str(role) for role in env.actor.roles), units=[], session_id=env.actor.session_id,
        evidence=[], created_at=now.isoformat(), expires_at=(now+timedelta(seconds=600)).isoformat())
    def get(scope, namespace, key):
        if key != permission_id or env.grant_revoked:
            return None
        return SimpleNamespace(version=1, payload=grant.model_dump(mode='json'))
    def check(actor, grant, **kwargs):
        if env.grant_revoked or env.source_version != target['expected_version']:
            raise CertificateError(403, 'GRANT_CHANGED', 'Permission/source changed')
    grants = SimpleNamespace(store=SimpleNamespace(get=get), check=check,
        observe=lambda actor, target: SimpleNamespace(evidence=grant.evidence, resource=SimpleNamespace(view=grant.audience)))
    source = DurableBusinessSource(tmp_path/'business-outbox.sqlite3')
    store = SQLiteAssistantTracking(tmp_path/'tracking.sqlite3', initialize=True)
    def resolve(tenant, owner, session):
        env.authorize(env.actor)
        if (tenant, owner, session) != (env.actor.tenant_id, env.actor.subject_id, env.actor.session_id):
            raise CertificateError(403, 'RECIPIENT_SESSION_CHANGED', 'Recipient not authorized')
        return env.actor
    service = AssistantTrackingService(store, tenant='fixture-b', authorize=env.authorize, tokens=env.tokens,
        grants=grants, source=source, resolve_recipient=resolve, project_notification=source.project, minimize=lambda text: text)
    subscription = {'resource': target, 'trigger': 'status', 'channel': 'in_app', 'expires_at': (now+timedelta(seconds=500)).isoformat(), 'permission_id': permission_id, 'permission_version': 1, 'quiet_start_hour': 0, 'quiet_end_hour': 0}
    env.tracking, env.source, env.tracking_store, env.subscription, env.target, env.grant = service, source, store, subscription, target, grant
    return env


@pytest.mark.parametrize('env', [IdentityRole.STUDENT, IdentityRole.SUPPORT_OFFICER], indirect=True)
def test_two_role_notifications_and_source_classification(tracking):
    env = tracking
    subscribe(env)
    env.source.emit(env.actor, env.target)
    assert worker(env).tick()['delivered'] == 1
    item = env.tracking.notifications(env.actor)['items'][0]
    assert item['recipient_id'] == env.actor.subject_id
    assert item['classification'] == ('public_student' if env.actor.roles == (IdentityRole.STUDENT,) else 'internal_staff')


def test_resource_memory_rechecks_grant_and_source_each_context(tracking):
    env = tracking
    env.memory.grants = env.tracking.grants
    control(env)
    resource_value = value(scope='resource', resource=env.target, grant_id=env.subscription['permission_id'])
    save(env, resource_value)
    assert env.memory.retrieve(env.actor, query())['items'] == []
    assert len(env.memory.retrieve(env.actor, query(resource=env.target))['items']) == 1
    env.source_version = 2
    assert env.memory.retrieve(env.actor, query(resource=env.target))['items'] == []
    assert 'value' not in env.memory.management(env.actor)['items'][0]
    env.source_version = 1
    env.grant_revoked = True
    assert env.memory.retrieve(env.actor, query(resource=env.target))['items'] == []


def test_memory_corruption_has_no_fallback(env):
    control(env)
    receipt = save(env)
    with sqlite3.connect(env.store.path) as connection:
        connection.execute("UPDATE personal_revision SET body='{}' WHERE namespace='memory' AND key=?", (receipt['key'],))
    with pytest.raises(StorageCorrupt):
        env.memory.retrieve(env.actor, query())


def test_tracking_permission_version_change_and_event_binding(tracking):
    env = tracking
    subscribe(env)
    env.source.emit(env.actor, env.target)
    original = env.tracking.grants.store.get
    env.tracking.grants.store.get = lambda *args: SimpleNamespace(version=2, payload=original(*args).payload)
    assert worker(env).tick()['delivered'] == 0
    assert env.tracking.notifications(env.actor)['items'] == []


def test_new_resource_version_does_not_silently_grant_new_source(tracking):
    env = tracking
    subscribe(env)
    env.source.emit(env.actor, {**env.target, 'expected_version': 2})
    env.tracking.grants.observe = lambda actor, target: SimpleNamespace(evidence=['changed-source'], resource=SimpleNamespace(view='student'))
    assert worker(env).tick()['delivered'] == 0
    assert env.tracking.notifications(env.actor)['items'] == []


def test_forget_topic_cannot_reappear_as_another_memory_kind(env):
    control(env)
    original = value()
    receipt = save(env, original)
    confirm(env.memory, env.actor, env.memory.prepare(env.actor, {'operation': 'forget', 'key': receipt['key'], 'expected_version': 1, 'client_id': generate_uuid7()}))
    with pytest.raises(CertificateError, match='Topic'):
        save(env, {**original, 'kind': 'confirmed_fact'}, version=2)


def test_consent_revoke_hides_management_and_export_text(env):
    control(env)
    save(env)
    env.consent = False
    item = env.memory.management(env.actor)['items'][0]
    assert 'value' not in item and item['locked_reason'] == 'MEMORY_CONSENT_REQUIRED'


def test_stop_after_delivery_hides_inbox_and_replay_stays_stopped(tracking):
    env = tracking
    receipt = subscribe(env)
    env.source.emit(env.actor, env.target)
    worker(env).tick()
    prepared = env.tracking.prepare(env.actor, {'operation': 'stop', 'subscription_id': receipt['key'], 'client_id': generate_uuid7(), 'expected_version': 1})
    assert confirm(env.tracking, env.actor, prepared)['version'] == 2
    assert confirm(env.tracking, env.actor, prepared)['is_replay']
    assert env.tracking.notifications(env.actor)['items'] == []


def test_expired_memory_abstains_without_erasing(env):
    control(env)
    receipt = save(env)
    scope = env.memory.scope(env.actor)
    row = env.store.get(scope, 'memory', receipt['key'])
    payload = {**row['payload'], 'value': {**row['payload']['value'], 'valid_until': (datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()}}
    env.store.commit(scope, 'memory', receipt['key'], 1, payload, generate_uuid7(), guard=lambda *args: None)
    assert env.memory.retrieve(env.actor, query())['items'] == []
    assert env.memory.management(env.actor)['items'][0]['version'] == 2


def test_exact_schema_exports_match_models():
    from pathlib import Path
    from campus247.domain.assistant_memory import MemoryQuery
    from campus247.domain.assistant_tracking import TrackingChange
    root = Path(__file__).resolve().parents[2]/'contracts/json-schema/assistance'
    for folder, models in [('memory-v1-01', [MemoryValue, MemoryChange, MemoryQuery]), ('tracking-v1-01', [SubscriptionSpec, TrackingChange, BusinessTrackingEvent, NotificationProjection])]:
        for model in models:
            assert json.loads((root/folder/(model.__name__+'.schema.json')).read_text(encoding='utf-8')) == model.model_json_schema()


def test_concurrent_memory_correction_one_cas_winner(env):
    from concurrent.futures import ThreadPoolExecutor
    control(env)
    original = value()
    save(env, original)
    previews = [env.memory.prepare(env.actor, {'operation': 'save', 'value': {**original, 'text': text}, 'expected_version': 1, 'client_id': generate_uuid7()}) for text in ('Lựa chọn một', 'Lựa chọn hai')]
    def commit(preview):
        try:
            return confirm(env.memory, env.actor, preview)['version']
        except StorageConflict:
            return 'conflict'
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(commit, previews))
    assert sorted(map(str, outcomes)) == ['2', 'conflict']


def test_worker_real_process_restart_does_not_redeliver(tracking, tmp_path):
    from dataclasses import asdict
    from pathlib import Path
    import os
    import subprocess
    import sys
    env = tracking
    subscribe(env)
    env.source.emit(env.actor, env.target)
    fields = asdict(env.actor)
    fields['auth_time'], fields['expires_at'] = env.actor.auth_time.isoformat(), env.actor.expires_at.isoformat()
    config = tmp_path/'worker-config.json'
    with config.open('x', encoding='utf-8') as handle:
        json.dump({'actor': fields, 'tracking_path': str(env.tracking_store.path), 'source_path': str(env.source.path), 'grant': env.grant.model_dump(mode='json')}, handle)
    script = Path(__file__).resolve().parents[2]/'scripts/unified_parallel_b_fixture_worker.py'
    results = []
    for number in (1, 2):
        command = [sys.executable, '-B', str(script), str(config)]
        completed = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'}, timeout=30)
        with (tmp_path/f'process-{number}.json').open('x', encoding='utf-8') as handle:
            json.dump({'command': command, 'exit': completed.returncode, 'stdout': completed.stdout, 'stderr': completed.stderr}, handle)
        assert completed.returncode == 0, completed.stderr
        results.append(json.loads(completed.stdout))
    assert [result['delivered'] for result in results] == [1, 0]
    assert len(env.tracking.notifications(env.actor)['items']) == 1


def test_concurrent_workers_deliver_once(tracking):
    from concurrent.futures import ThreadPoolExecutor
    env = tracking
    subscribe(env)
    env.source.emit(env.actor, env.target)
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda index: worker(env).tick(), range(2)))
    assert sum(result['delivered'] for result in outcomes) == 1
    assert len(env.tracking.notifications(env.actor)['items']) == 1


def test_http_revalidation_can_block_mid_confirmation(env):
    control(env)
    original = value()
    preview = env.memory.prepare(env.actor, {'operation': 'save', 'value': original, 'expected_version': 0, 'client_id': generate_uuid7()})
    calls = []
    def live_identity():
        calls.append(1)
        if len(calls) >= 3:
            raise ValueError('revoked during confirm')
        return env.actor
    with env.memory.request_guard(live_identity):
        with pytest.raises(CertificateError):
            confirm(env.memory, env.actor, preview)
    assert env.memory.management(env.actor)['items'] == []


def test_worker_final_session_resolution_blocks_delivery(tracking):
    env = tracking
    subscribe(env)
    env.source.emit(env.actor, env.target)
    original = env.tracking.resolve_recipient
    calls = []
    def resolve(*args):
        calls.append(1)
        if len(calls) == 2:
            raise CertificateError(403, 'SESSION_REVOKED', 'fixture revoke before delivery')
        return original(*args)
    env.tracking.resolve_recipient = resolve
    assert worker(env).tick()['delivered'] == 0


def test_real_unified_app_registrar_authenticated_memory_readback(tmp_path):
    from campus247.bootstrap.unified_demo import create_unified_demo_app
    from tests.api.test_certificate_stage1 import login
    from tests.integration.test_unified_actor_features import consent
    from tests.integration.test_unified_durable_services import actor
    app = create_unified_demo_app(tmp_path/'real-business.sqlite3', state_database=tmp_path/'real-actor.sqlite3', consent_mode='sqlite')
    identity_value = actor()
    consent(app, identity_value)
    def server_mode(current, conversation_id):
        app.state.certificate_service.authorize(current)
        if conversation_id is not None:
            raise CertificateError(503, 'CHAT_MODE_UNVERIFIED', 'No temporary marker in legacy chat')
        return 'settings'
    wire_assistant_personal_features(app, memory_store=SQLiteAssistantMemory(tmp_path/'real-memory.sqlite3', initialize=True),
        tenant='huce-local-public', authorize=app.state.certificate_service.authorize,
        tokens=app.state.service_requests.tokens, preferences=app.state.assistant_preferences, grants=app.state.assistant_grants,
        conversation_mode=server_mode, minimize=lambda text: text)
    with TestClient(app) as client:
        assert client.get('/v1/assistant/memory').status_code == 401
        headers = login(client)
        for change in ({'operation': 'control', 'enabled': True}, {'operation': 'save', 'value': value()}):
            preview = client.post('/v1/assistant/memory/preview', headers=headers, json={**change, 'client_id': generate_uuid7(), 'expected_version': 0})
            assert preview.status_code == 200, preview.text
            body = preview.json()
            result = client.post('/v1/assistant/memory/confirm', headers=headers, json={**{key: body[key] for key in ('normalized_payload', 'confirmation_token')}, 'confirmed': True})
            assert result.status_code == 200, result.text
            receipt = client.get('/v1/assistant/memory/receipts/'+result.json()['client_id'], headers=headers)
            assert receipt.status_code == 200 and receipt.json()['version'] == 1
        page = client.get('/v1/assistant/memory', headers=headers)
        assert page.status_code == 200 and page.json()['items'][0]['value']['text'] == value()['text']
        assert client.get('/v1/assistant/memory', headers=login(client, 'SV024')).json()['items'] == []
        caps = client.get('/v1/assistant/personal-capabilities', headers=headers).json()
        assert caps['memory_management'] and not caps['memory_context'] and not caps['tracking']


def subscribe(env):
    subscription_id = generate_uuid7()
    receipt = confirm(env.tracking, env.actor, env.tracking.prepare(env.actor, {'operation': 'subscribe', 'client_id': subscription_id, 'subscription_id': subscription_id, 'expected_version': 0, 'spec': env.subscription}))
    return receipt


def worker(env):
    from campus247_worker.assistant_tracking.worker import AssistantTrackingWorker
    return AssistantTrackingWorker(env.tracking)


def test_real_fixture_outbox_worker_restart_and_no_change_dedup(tracking):
    env = tracking
    subscribe(env)
    event = env.source.emit(env.actor, env.target)
    assert worker(env).tick()['delivered'] == 1
    env.tracking.store = SQLiteAssistantTracking(env.tracking_store.path)
    assert worker(env).tick()['delivered'] == 0
    env.source.emit(env.actor, env.target)
    result = worker(env).tick()
    assert result['suppressed'] == 1
    inbox = env.tracking.notifications(env.actor)
    assert len(inbox['items']) == 1 and inbox['items'][0]['action_authority'] == 'none'
    assert inbox['items'][0]['resource'] == event.resource.model_dump()


@pytest.mark.parametrize('revocation', ['grant', 'session', 'stop', 'assignment', 'source_version'])
def test_delivery_rechecks_all_boundaries(tracking, revocation):
    env = tracking
    receipt = subscribe(env)
    env.source.emit(env.actor, env.target)
    if revocation == 'grant':
        env.grant_revoked = True
    elif revocation == 'session':
        env.revoked = True
    elif revocation == 'stop':
        confirm(env.tracking, env.actor, env.tracking.prepare(env.actor, {'operation': 'stop', 'client_id': generate_uuid7(), 'subscription_id': receipt['key'], 'expected_version': 1}))
    else:
        with sqlite3.connect(env.source.path) as connection:
            if revocation == 'assignment':
                connection.execute('UPDATE business SET assignment=? WHERE id=?', (generate_uuid7(), env.target['id']))
            else:
                connection.execute('UPDATE business SET version=2 WHERE id=?', (env.target['id'],))
    assert worker(env).tick()['delivered'] == 0
    with sqlite3.connect(env.tracking_store.path) as connection:
        assert connection.execute('SELECT COUNT(*) FROM tracking_inbox').fetchone()[0] == 0


def test_crash_before_ack_recovers_scheduling_and_exact_once_delivery(tracking):
    env = tracking
    subscribe(env)
    env.source.emit(env.actor, env.target)
    original = env.source.ack
    env.source.ack = lambda event_id: (_ for _ in ()).throw(ConnectionError('synthetic crash before ack'))
    with pytest.raises(ConnectionError):
        worker(env).tick()
    env.source.ack = original
    assert worker(env).tick()['delivered'] == 1
    assert worker(env).tick()['delivered'] == 0


def test_quiet_hours_durable_delay_then_delivery(tracking):
    env = tracking
    now = datetime.now(timezone.utc)
    env.subscription.update(quiet_start_hour=now.hour, quiet_end_hour=(now.hour+1)%24, utc_offset_minutes=0)
    subscribe(env)
    env.source.emit(env.actor, env.target)
    assert worker(env).tick(now=now+timedelta(seconds=1))['quiet'] == 1
    with sqlite3.connect(env.tracking_store.path) as connection:
        assert connection.execute('SELECT state FROM tracking_job').fetchone()[0] == 'quiet'


def test_retry_three_bounds_preserves_failures(tracking):
    env = tracking
    subscribe(env)
    env.source.emit(env.actor, env.target)
    env.tracking.project_notification = lambda *args: (_ for _ in ()).throw(TimeoutError('synthetic source timeout'))
    now = datetime.now(timezone.utc)
    for seconds in (1, 4, 10):
        assert worker(env).tick(now=now+timedelta(seconds=seconds))['retry'] == 1
    assert worker(env).tick(now=now+timedelta(seconds=30))['retry'] == 0
    with sqlite3.connect(env.tracking_store.path) as connection:
        assert connection.execute('SELECT state,attempts,last_code FROM tracking_job').fetchone() == ('failed', 3, 'SOURCE_UNAVAILABLE')


def test_inbox_reauthorizes_after_delivery_and_wrong_actor(tracking):
    env = tracking
    subscribe(env)
    env.source.emit(env.actor, env.target)
    worker(env).tick()
    assert len(env.tracking.notifications(env.actor)['items']) == 1
    env.grant_revoked = True
    assert env.tracking.notifications(env.actor)['items'] == []
    assert env.tracking.notifications(replace(env.actor, subject_id=generate_uuid7()))['items'] == []


def test_missing_source_and_remote_channel_fail_closed(tracking):
    env = tracking
    with pytest.raises(ValidationError):
        SubscriptionSpec.model_validate({**env.subscription, 'channel': 'email'})
    env.tracking.source = None
    with pytest.raises(CertificateError) as error:
        subscribe(env)
    assert error.value.status == 503
    with pytest.raises(CertificateError):
        worker(env).tick()


def test_deadline_without_sourced_consumer_unavailable(tracking):
    env = tracking
    env.subscription['trigger'] = 'deadline'
    with pytest.raises(CertificateError) as error:
        subscribe(env)
    assert error.value.code == 'TRACKING_DEADLINE_UNAVAILABLE'


def test_event_id_mutation_and_classification_fail_closed(tracking):
    env = tracking
    event = env.source.emit(env.actor, env.target)
    env.tracking_store.ingest(event)
    with pytest.raises(StorageConflict):
        env.tracking_store.ingest(event.model_copy(update={'source_sha256': 'b'*64}))
    with pytest.raises(ValidationError):
        BusinessTrackingEvent.model_validate({**event.model_dump(mode='json'), 'classification': 'internal_staff'})


def test_actual_registrar_http_fixture_and_missing_capabilities(env):
    app = FastAPI()
    @app.middleware('http')
    async def actor_boundary(request: Request, call_next):
        request.state.identity = env.actor
        request.state.revalidate_identity = lambda: env.actor
        return await call_next(request)
    env.preferences.scope = env.memory.scope
    wire_assistant_personal_features(app, memory_store=env.store, tenant='fixture-b', authorize=env.authorize,
        tokens=env.tokens, preferences=env.preferences, conversation_mode=env.mode_reader, minimize=lambda text: text)
    with TestClient(app) as client:
        caps = client.get('/v1/assistant/personal-capabilities')
        assert caps.status_code == 200 and not caps.json()['memory_context'] and not caps.json()['tracking']
        prepared = client.post('/v1/assistant/memory/preview', json={'operation': 'control', 'enabled': True, 'expected_version': 0, 'client_id': generate_uuid7()})
        assert prepared.status_code == 200, prepared.text
        body = prepared.json()
        result = client.post('/v1/assistant/memory/confirm', json={**{key: body[key] for key in ('normalized_payload', 'confirmation_token')}, 'confirmed': True})
        assert result.status_code == 200, result.text
        assert client.get('/v1/assistant/memory').json()['control']['version'] == 1
        assert client.get('/v1/assistant/memory').headers['cache-control'] == 'no-store'
