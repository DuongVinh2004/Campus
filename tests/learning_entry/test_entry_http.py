"""Learning HTTP integration with real session middleware and new synthetic storage.

This exercises module integration, not the PostgreSQL-dependent Campus process.
"""
import hashlib
import io
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from campus247.application.identity.session_service import SessionService
from campus247.bootstrap.learning import load_local_learning
from campus247.domain.learning import LearningError
from campus247.presentation.identity import IdentityMiddleware
from campus247.presentation.learning import create_learning_router
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from learning_local_setup import setup


@pytest.fixture
def entry(tmp_path, request):
    if not tmp_path.resolve().is_relative_to(ROOT):
        raise RuntimeError('Use an explicit new --basetemp inside the authorized repository')
    output = io.BytesIO()
    writer = PdfWriter()
    options = getattr(request, 'param', {})
    for _ in range(options.get('pages', 1)):
        page = writer.add_blank_page(width=612, height=792)
        if options.get('text'):
            name = NameObject
            font = DictionaryObject({name('/Type'): name('/Font'), name('/Subtype'): name('/Type1'), name('/BaseFont'): name('/Helvetica')})
            page[name('/Resources')] = DictionaryObject({name('/Font'): DictionaryObject({name('/F1'): font})})
            text = DecodedStreamObject()
            text.set_data(b'BT /F1 16 Tf 72 700 Td (Synthetic idea source) Tj ET')
            page[name('/Contents')] = writer._add_object(text)
    writer.write(output)
    pdf = ((ROOT / os.environ.get('LEARNING_OCR_FIXTURE_PDF', '.tooling/learning-ocr-spike-20261105-01/pdfs/synthetic-5.pdf')).read_bytes()
           if options.get('ocr_native') else output.getvalue())
    fixture = tmp_path / 'fixture.pdf'
    fixture.write_bytes(pdf)
    scope = tmp_path / 'runtime'
    setup(scope, 'test-learning-entry', fixture, second_student=options.get('second_student', False))
    config_path = scope / 'config.json'
    if options.get('optimize'):
        from campus247.infrastructure.learning.pdf_layout import balanced_view
        expected = tmp_path / 'expected-view.pdf'
        result = balanced_view(fixture, expected, ROOT)
        configuration = json.loads(config_path.read_text())
        configuration['pdf_web_view'] = True
        configuration['synthetic_fixture_sha256'].append(result['sha256'])
        config_path = scope / 'views-config.json'
        with config_path.open('x', encoding='utf-8') as stream:
            json.dump(configuration, stream)
    service, adapter = load_local_learning(config_path, workspace=ROOT, tenant_id='test-learning-entry')
    directory = json.loads((scope / 'credentials.json').read_text())['accounts']
    accounts = {a['role']: a for a in directory}
    students = [account for account in directory if account['role'] == 'STUDENT']
    if len(students) == 2:
        accounts['STUDENT'], accounts['STUDENT_2'] = students
    headers = {role: {'Authorization': 'Bearer ' + adapter.authenticate(a['username'], a['password'])}
               for role, a in accounts.items()}
    app = FastAPI()
    app.add_middleware(IdentityMiddleware, adapter=adapter, session_service=SessionService())
    app.include_router(create_learning_router(service))
    with TestClient(app) as client:
        yield client, service, headers, accounts, pdf


def post(client, path, body, headers):
    actions = {'/terms': 'term-create', '/courses': 'course-create', '/offerings': 'offering-create'}
    member = re.fullmatch(r'/offerings/([^/]+)/members', path)
    action = 'member-create' if member else actions.get(path)
    if action and 'preview_id' not in body:
        preview = client.post('/v1/learning/action-previews', json={
            'action': action, 'target_id': member.group(1) if member else None, 'payload': body}, headers=headers)
        if preview.status_code != 200:
            return preview
        body = body | {key: preview.json()[key] for key in ('preview_id', 'confirmation_token')}
    return client.post('/v1/learning' + path, json=body,
                       headers=headers | {'Idempotency-Key': str(uuid4())})


def test_admin_teacher_student_publication_and_range(entry, monkeypatch):
    client, service, headers, accounts, pdf = entry
    admin, teacher, student = (headers[r] for r in ('SYSTEM_ADMIN', 'LECTURER', 'STUDENT'))
    assert client.get('/v1/learning/offerings').status_code == 401
    assert post(client, '/courses', {'code': 'NO', 'name': 'Unauthorized'}, student).status_code == 403
    term = post(client, '/terms', {'name': 'Synthetic term', 'start_date': '2026-11-01', 'end_date': '2027-02-01'}, admin)
    assert term.status_code == 200, term.text
    course = post(client, '/courses', {'code': 'SYN-HTTP', 'name': 'Synthetic HTTP course'}, admin).json()
    offering = post(client, '/offerings', {'course_id': course['id'], 'term_id': term.json()['id'], 'section_code': 'A'}, admin).json()
    oid = offering['id']
    for role, member_role in [('LECTURER', 'INSTRUCTOR'), ('STUDENT', 'STUDENT')]:
        member = post(client, f'/offerings/{oid}/members', {'actor_subject_id': accounts[role]['subject_id'], 'role': member_role}, admin)
        assert member.status_code == 200, member.text
    session = post(client, f'/offerings/{oid}/sessions', {'title': 'Synthetic session'}, teacher).json()
    material = post(client, f'/offerings/{oid}/materials', {'title': 'Synthetic lecture', 'session_id': session['id']}, teacher).json()
    upload = post(client, f'/materials/{material["id"]}/upload-intents', {'filename': 'fixture.pdf', 'byte_size': len(pdf), 'content_type': 'application/pdf'}, teacher).json()
    received = client.put(f'/v1/learning/upload-intents/{upload["id"]}/content', content=pdf, headers=teacher | {'Content-Type': 'application/pdf'})
    assert received.status_code == 200, received.text
    complete = post(client, f'/upload-intents/{upload["id"]}/complete', {}, teacher)
    assert complete.status_code == 200, complete.text
    vid = complete.json()['id']
    client.portal.call(service.tick)
    version = client.get(f'/v1/learning/versions/{vid}', headers=teacher)
    assert version.json()['processing_state'] == 'READY', version.text
    contexts_path = f'/v1/learning/versions/{vid}/session-contexts'
    assert client.get(contexts_path, headers=student).status_code == 404
    assert client.get(f'/v1/learning/versions/{vid}/content', headers=student).status_code == 404
    preview = post(client, f'/versions/{vid}/publication-preview', {'action': 'publish'}, teacher).json()
    published = post(client, f'/versions/{vid}/publish', {k: preview[k] for k in ('preview_id', 'confirmation_token')}, teacher)
    assert published.status_code == 200, published.text
    later_session = post(client, f'/offerings/{oid}/sessions', {'title': 'Reuse in a later session'}, teacher).json()
    links_path = f'/v1/learning/sessions/{later_session["id"]}/material-links'
    assert client.put(links_path, json={'material_ids': [material['id']]}, headers=teacher).status_code == 200
    first_context = client.get(contexts_path, params={'limit': 1}, headers=student)
    assert first_context.status_code == 200 and first_context.headers['cache-control'] == 'no-store'
    assert first_context.json()['items'] == [{
        'id': session['id'], 'offering_id': oid, 'sequence_no': 1, 'title': 'Synthetic session',
    }]
    cursor = first_context.json()['page']['next_cursor']
    assert client.get(contexts_path, params={'cursor': cursor}, headers=teacher).status_code == 422
    second_context = client.get(contexts_path, params={'cursor': cursor}, headers=student)
    assert [item['id'] for item in second_context.json()['items']] == [later_session['id']]
    assert client.get(contexts_path, headers=admin).status_code == 404
    feedback_path = f'/v1/learning/versions/{vid}/pages/1/me/feedback'
    assert client.get(feedback_path, headers=student).status_code == 404
    service.page_feedback_offerings = frozenset({oid})
    instant = datetime(2030, 1, 1, tzinfo=UTC)
    monkeypatch.setattr('campus247.application.learning.page_feedback.feedback_clock', lambda: instant)
    monkeypatch.setattr('campus247.application.learning.service.feedback_clock', lambda: instant)
    cutoff = {'closes_at': '2030-01-01T00:30:00Z'}
    window = f'/v1/learning/sessions/{session["id"]}/page-feedback-window'
    summary_path = f'/v1/learning/sessions/{session["id"]}/page-feedback-summary'
    assert client.get(window, headers=student).json() == {'window': None}
    assert client.get(summary_path, headers=student).status_code == 404
    assert client.get(summary_path, headers=teacher).json()['state'] == 'NOT_OPENED'
    assert client.put(window, json=cutoff, headers=teacher | {'Idempotency-Key': str(uuid4())}).status_code == 409
    window_preview = post(client, '/action-previews', {
        'action': 'feedback-window-open', 'target_id': session['id'], 'payload': cutoff,
    }, teacher)
    assert window_preview.status_code == 200, window_preview.text
    proof = {field: window_preview.json()[field] for field in ('preview_id', 'confirmation_token')}
    opened = client.put(window, json=cutoff | proof, headers=teacher | {'Idempotency-Key': str(uuid4())})
    assert opened.status_code == 200, opened.text
    assert client.get(summary_path, headers=teacher).json()['state'] == 'WAITING'
    assert client.get(feedback_path, headers=student).json() == {'feedback': None}
    feedback_payload = {'session_id': session['id'], 'revision': 0, 'category': 'NEED_EXAMPLE'}
    stable_key = student | {'Idempotency-Key': str(uuid4())}
    created = client.put(feedback_path, json=feedback_payload, headers=stable_key)
    assert created.status_code == 200, created.text
    assert created.headers['cache-control'] == 'no-store'
    original = created.json()
    assert set(original) == {'id', 'session_id', 'version_id', 'page_no', 'category', 'status', 'revision'}
    assert client.put(feedback_path, json=feedback_payload, headers=stable_key).json() == original
    assert client.get(feedback_path, headers=teacher).status_code == 404
    assert client.put(feedback_path, json=feedback_payload | {'revision': 1, 'session_id': later_session['id']},
                      headers=student | {'Idempotency-Key': str(uuid4())}).json()['code'] == 'FEEDBACK_SESSION_FIXED'
    instant = datetime(2030, 1, 1, 0, 30, tzinfo=UTC)
    edited = client.put(feedback_path, json=feedback_payload | {'revision': 1, 'category': 'POSSIBLE_ERROR'},
                        headers=student | {'Idempotency-Key': str(uuid4())})
    assert edited.json()['revision'] == 2
    withdrawal_path = '/v1/learning/me/page-feedback/' + original['id']
    withdrawn = client.patch(withdrawal_path, json={'revision': 2},
                             headers=student | {'Idempotency-Key': str(uuid4())})
    assert withdrawn.json()['status'] == 'WITHDRAWN'
    assert client.put(feedback_path, json=feedback_payload | {'revision': 3},
                      headers=student | {'Idempotency-Key': str(uuid4())}).json()['code'] == 'FEEDBACK_WINDOW_CLOSED'
    client.portal.call(service.tick)
    suppressed = client.get(summary_path, headers=teacher)
    assert suppressed.json() == {'state': 'AVAILABLE', 'closes_at': '2030-01-01T00:30:00.000000Z', 'pages': []}
    assert suppressed.headers['cache-control'] == 'no-store'
    explanation_path = f'/v1/learning/sessions/{later_session["id"]}/page-explanations'
    explanation_payload = {'version_id': vid, 'page_no': 1, 'category': 'ADD_EXAMPLE', 'body': 'Ví dụ ban đầu'}
    explanation_key = teacher | {'Idempotency-Key': str(uuid4())}
    draft_response = client.post(explanation_path, json=explanation_payload, headers=explanation_key)
    assert draft_response.status_code == 200, draft_response.text
    draft = draft_response.json()
    assert draft['status'] == 'DRAFT' and draft['session_id'] == later_session['id']
    assert client.get(explanation_path, headers=student).json()['items'] == []
    assert client.get(explanation_path, headers=admin).status_code == 404
    assert client.post(explanation_path, json=explanation_payload, headers=student | {'Idempotency-Key': str(uuid4())}).status_code == 403
    draft_path = '/v1/learning/page-explanations/' + draft['id']

    def preview_explanation(revision):
        proof = post(client, '/action-previews', {
            'action': 'page-explanation-update', 'target_id': draft['id'], 'payload': {'revision': revision, 'publish': True},
        }, teacher)
        assert proof.status_code == 200, proof.text
        return proof.json()

    stale = preview_explanation(1)
    example = 'Ví dụ mới dành cho cả lớp'
    amended = client.patch(draft_path, json={'revision': 1, 'body': example, 'category': 'ADD_EXAMPLE'},
                           headers=teacher | {'Idempotency-Key': str(uuid4())})
    assert amended.status_code == 200, amended.text
    old_proof = {field: stale[field] for field in ('preview_id', 'confirmation_token')}
    assert client.patch(draft_path, json={'revision': 1, 'publish': True} | old_proof,
                        headers=teacher | {'Idempotency-Key': str(uuid4())}).json()['code'] == 'REVISION_CONFLICT'
    publish_key = teacher | {'Idempotency-Key': str(uuid4())}
    assert client.patch(draft_path, json={'revision': 2, 'publish': True}, headers=publish_key).json()['code'] == 'CONFIRMATION_REQUIRED'
    ready = preview_explanation(2)
    assert ready['page_explanation']['body'] == example
    publish_payload = {'revision': 2, 'publish': True} | {field: ready[field] for field in ('preview_id', 'confirmation_token')}
    released = client.patch(draft_path, json=publish_payload, headers=publish_key)
    assert released.status_code == 200 and released.json()['status'] == 'PUBLISHED'
    assert client.patch(draft_path, json=publish_payload, headers=publish_key).json() == released.json()
    assert client.get(explanation_path, headers=student).json()['items'] == [released.json()]
    notifications = '/v1/learning/me/notifications'
    notices = [item for item in client.get(notifications, headers=student).json()['items']
               if item.get('event_type') == 'PAGE_EXPLANATION_PUBLISHED']
    assert len(notices) == 1 and notices[0]['session_id'] == later_session['id']
    assert notices[0]['title'] == 'Cập nhật học liệu' and 'body' not in notices[0] and 'category' not in notices[0]
    assert client.put(links_path, json={'material_ids': []}, headers=teacher).status_code == 200
    assert client.get(explanation_path, headers=student).json()['items'] == []
    assert client.post(explanation_path, json=explanation_payload, headers=explanation_key).status_code == 404
    assert not any(item.get('event_type') == 'PAGE_EXPLANATION_PUBLISHED'
                   for item in client.get(notifications, headers=student).json()['items'])
    assert [item['id'] for item in client.get(contexts_path, headers=student).json()['items']] == [session['id']]
    position_path = f'/v1/learning/me/reader-state/{vid}'
    old_reader = {'X-Campus-Reader-Actor': accounts['STUDENT']['subject_id']}
    assert client.get(position_path, headers=teacher | old_reader).status_code == 401
    changed_account = client.put(position_path, json={'page_no': 1, 'revision': 0}, headers=teacher | old_reader)
    assert changed_account.status_code == 401
    assert changed_account.json()['code'] == 'READER_SESSION_CHANGED'
    assert client.get(position_path, headers=teacher).json()['revision'] == 0
    assert client.put(position_path, json={'page_no': 1, 'revision': 0}, headers=student | old_reader).status_code == 200
    response = client.get(f'/v1/learning/versions/{vid}/content', headers=student | {'Range': 'bytes=0-15'})
    assert response.status_code == 206 and response.content == pdf[:16]
    assert response.headers['content-range'] == f'bytes 0-15/{len(pdf)}'
    assert response.headers['cache-control'] == 'private, no-store'
    full = client.get(f'/v1/learning/versions/{vid}/content', headers=student)
    assert hashlib.sha256(full.content).digest() == hashlib.sha256(pdf).digest()
    # An administrator with no class assignment cannot read the lecture bytes.
    assert client.get(f'/v1/learning/versions/{vid}/content', headers=admin).status_code == 404
    head = client.head(f'/v1/learning/versions/{vid}/content', headers=student | {'Range': 'bytes=0-15'})
    assert head.status_code == 200 and not head.content
    invalid = client.get(f'/v1/learning/versions/{vid}/content', headers=student | {'Range': f'bytes={len(pdf)+1}-'})
    assert invalid.status_code == 416
    preview = post(client, f'/versions/{vid}/publication-preview', {'action': 'retract'}, teacher).json()
    retracted = post(client, f'/versions/{vid}/retract', {k: preview[k] for k in ('preview_id', 'confirmation_token')}, teacher)
    assert retracted.status_code == 200, retracted.text
    assert client.get(f'/v1/learning/versions/{vid}/content', headers=student).status_code == 404
    assert client.get(contexts_path, headers=student).status_code == 404
    assert client.get(feedback_path, headers=student).status_code == 404


def test_version_changes_pin_preview_and_redact_an_unavailable_base(entry, monkeypatch):
    client, service, headers, accounts, pdf = entry
    admin, teacher, student = (headers[role] for role in ('SYSTEM_ADMIN', 'LECTURER', 'STUDENT'))
    term = post(client, '/terms', {'name': 'Synthetic term', 'start_date': '2026-11-01', 'end_date': '2027-02-01'}, admin).json()
    course = post(client, '/courses', {'code': 'SYN-CHANGES', 'name': 'Change notes'}, admin).json()
    offering = post(client, '/offerings', {'course_id': course['id'], 'term_id': term['id'], 'section_code': 'A'}, admin).json()
    oid = offering['id']
    for role, member_role in [('LECTURER', 'INSTRUCTOR'), ('STUDENT', 'STUDENT')]:
        added = post(client, f'/offerings/{oid}/members', {'actor_subject_id': accounts[role]['subject_id'], 'role': member_role}, admin)
        assert added.status_code == 200, added.text
    service.version_change_offerings = frozenset({oid})
    session = post(client, f'/offerings/{oid}/sessions', {'title': 'Synthetic session'}, teacher).json()
    material = post(client, f'/offerings/{oid}/materials', {'title': 'Notes', 'session_id': session['id']}, teacher).json()

    def upload_version():
        upload = post(client, f'/materials/{material["id"]}/upload-intents', {
            'filename': 'fixture.pdf', 'byte_size': len(pdf), 'content_type': 'application/pdf',
        }, teacher).json()
        received = client.put(f'/v1/learning/upload-intents/{upload["id"]}/content', content=pdf, headers=teacher)
        assert received.status_code == 200, received.text
        completed = post(client, f'/upload-intents/{upload["id"]}/complete', {}, teacher)
        assert completed.status_code == 200, completed.text
        client.portal.call(service.tick)
        return completed.json()['id']

    def preview_version(version_id, payload):
        response = post(client, f'/versions/{version_id}/publication-preview', payload, teacher)
        assert response.status_code == 200, response.text
        return response.json()

    def confirm_version(version_id, action, preview, payload=None):
        proof = {key: preview[key] for key in ('preview_id', 'confirmation_token')}
        return post(client, f'/versions/{version_id}/{action}', proof | (payload or {}), teacher)

    base = upload_version()
    assert confirm_version(base, 'publish', preview_version(base, {'action': 'publish'})).status_code == 200
    target = upload_version()
    path = f'/v1/learning/versions/{target}/change-set'
    payload = {'revision': 0, 'base_version_id': base, 'mode': 'PAGE_MAP', 'reason': 'So sánh nội dung cũ',
               'target_guidance': 'Đọc công thức trong bản mới',
               'items': [{'kind': 'EDITED', 'old_page': 1, 'new_page': 1, 'description': 'So với bản cũ', 'guidance': 'Xem công thức trang 1'}]}

    def save(values):
        return client.put(path, json=values, headers=teacher | {'Idempotency-Key': str(uuid4())})

    assert save(payload | {'base_version_id': target}).json()['code'] == 'INVALID_CHANGE_BASE'
    assert save(payload | {'items': [payload['items'][0] | {'new_page': 2}]}).json()['code'] == 'INVALID_PAGE'
    assert save(payload).status_code == 200
    assert client.get(path, headers=student).status_code == 404
    stale = preview_version(target, {'action': 'publish', 'change_set_revision': 1})
    assert stale['change_set']['base_version_id'] == base
    assert save(payload | {'revision': 1, 'reason': 'So sánh sau chỉnh sửa'}).status_code == 200
    assert confirm_version(target, 'publish', stale, {'change_set_revision': 1}).json()['code'] == 'CHANGE_SET_STALE'
    due = datetime.now(UTC) + timedelta(hours=1)
    scheduled = {'change_set_revision': 2, 'scheduled_at': due.isoformat().replace('+00:00', 'Z')}
    assert confirm_version(target, 'publish', preview_version(target, {'action': 'publish'} | scheduled), scheduled).status_code == 200
    assert save(payload | {'revision': 2, 'reason': 'Chỉnh revision trong thời gian chờ'}).status_code == 200
    with monkeypatch.context() as clock:
        clock.setattr('campus247.application.learning.service.now', lambda: (due + timedelta(seconds=1)).isoformat().replace('+00:00', 'Z'))
        client.portal.call(service.tick)
    current = client.get(f'/v1/learning/versions/{target}', headers=teacher).json()
    assert current['publication_state'] == 'DRAFT' and current['schedule_error'] == 'CHANGE_SET_STALE'
    assert current['current_published_version_id'] == base
    assert confirm_version(target, 'publish', preview_version(target, {'action': 'publish', 'change_set_revision': 3}),
                           {'change_set_revision': 3}).status_code == 200
    visible = client.get(path, headers=student).json()['change_set']
    assert visible['revision'] == 3 and visible['base_version_id'] == base and visible['items'][0]['old_page'] == 1
    correction = payload | {'revision': 3, 'reason': 'Đính chính sau công bố'}
    assert save(correction).json()['code'] == 'CONFIRMATION_REQUIRED'
    proof = post(client, '/action-previews', {'action': 'version-change-save', 'target_id': target, 'payload': correction}, teacher).json()
    confirmed = save(correction | {key: proof[key] for key in ('preview_id', 'confirmation_token')})
    assert confirmed.status_code == 200, confirmed.text
    assert client.get(path, headers=student).json()['change_set']['revision'] == 4
    assert client.get(f'/v1/learning/versions/{base}/content', headers=student).content == pdf
    assert confirm_version(base, 'retract', preview_version(base, {'action': 'retract'})).status_code == 200
    independent = client.get(path, headers=student).json()['change_set']
    assert not independent['base_available'] and 'base_version_id' not in independent and 'reason' not in independent
    assert independent['items'] == [{'new_page': 1, 'guidance': 'Xem công thức trang 1'}]
    assert client.get(f'/v1/learning/versions/{base}/content', headers=student).status_code == 404


@pytest.mark.parametrize('entry', [{'text': True, 'second_student': True}], indirect=True)
def test_idea_snapshot_citation_and_grant_suspension(entry):
    client, service, headers, accounts, pdf = entry
    admin, teacher, owner, peer = (headers[role] for role in ('SYSTEM_ADMIN', 'LECTURER', 'STUDENT', 'STUDENT_2'))
    term = post(client, '/terms', {'name': 'Synthetic term', 'start_date': '2026-11-01', 'end_date': '2027-02-01'}, admin).json()
    course = post(client, '/courses', {'code': 'SYN-IDEA', 'name': 'Synthetic idea course'}, admin).json()
    oid = post(client, '/offerings', {'course_id': course['id'], 'term_id': term['id'], 'section_code': 'A'}, admin).json()['id']
    members = {}
    for role, member_role in [('LECTURER', 'INSTRUCTOR'), ('STUDENT', 'STUDENT'), ('STUDENT_2', 'STUDENT')]:
        added = post(client, f'/offerings/{oid}/members', {
            'actor_subject_id': accounts[role]['subject_id'], 'role': member_role,
        }, admin)
        assert added.status_code == 200, added.text
        members[role] = added.json()['id']
    service.idea_card_offerings = frozenset({oid})
    session = post(client, f'/offerings/{oid}/sessions', {'title': 'Synthetic idea session'}, teacher).json()
    material = post(client, f'/offerings/{oid}/materials', {'title': 'Cited file', 'session_id': session['id']}, teacher).json()
    upload = post(client, f'/materials/{material["id"]}/upload-intents', {'filename': 'fixture.pdf', 'byte_size': len(pdf)}, teacher).json()
    assert client.put(f'/v1/learning/upload-intents/{upload["id"]}/content', content=pdf, headers=teacher).status_code == 200
    vid = post(client, f'/upload-intents/{upload["id"]}/complete', {}, teacher).json()['id']
    client.portal.call(service.tick)

    def proof(action, target, payload, actor):
        result = post(client, '/action-previews', {'action': action, 'target_id': target, 'payload': payload}, actor)
        assert result.status_code == 200, result.text
        return {key: result.json()[key] for key in ('preview_id', 'confirmation_token')}

    def publication(action):
        preview = post(client, f'/versions/{vid}/publication-preview', {'action': action}, teacher).json()
        return post(client, f'/versions/{vid}/{action}', {key: preview[key] for key in ('preview_id', 'confirmation_token')}, teacher)

    def patch(path, data, actor):
        return client.patch('/v1/learning' + path, json=data, headers=actor | {'Idempotency-Key': str(uuid4())})

    assert publication('publish').status_code == 200
    topic = post(client, '/me/idea-topics', {'title': 'Đề tài riêng'}, owner).json()
    prose = {'topic_id': topic['id'], 'problem': 'Vấn đề riêng', 'idea': 'Ý tưởng ban đầu', 'verification': 'Kiểm chứng'}
    source = {'version_id': vid, 'page_no': 1, 'kind': 'TEXT', 'quote': 'Synthetic  idea source'}
    false_quote = post(client, '/me/idea-cards', prose | {'source': source | {'quote': 'Missing text'}}, owner)
    assert false_quote.json()['code'] == 'IDEA_QUOTE_UNVERIFIED'
    card_body = prose | {'source': source}
    card_headers = owner | {'Idempotency-Key': str(uuid4())}
    accepted = client.post('/v1/learning/me/idea-cards', json=card_body, headers=card_headers)
    assert accepted.status_code == 200, accepted.text
    card = accepted.json()
    assert card['source']['quote'] == 'Synthetic idea source'
    assert client.get('/v1/learning/me/idea-cards/' + card['id'], headers=peer).status_code == 404
    region = {'version_id': vid, 'page_no': 1, 'kind': 'REGION', 'rects': [{'x': .9, 'y': .2, 'width': .2, 'height': .1}]}
    assert post(client, '/me/idea-cards', prose | {'source': region}, owner).json()['code'] == 'INVALID_IDEA_REGION'
    candidate = {'revision': 1, 'recipient_ids': [accounts['STUDENT_2']['subject_id']]}
    share_path = f'/me/idea-cards/{card["id"]}/shares'
    assert post(client, share_path, candidate, owner).json()['code'] == 'CONFIRMATION_REQUIRED'
    confirmed_body = candidate | proof('idea-share-create', card['id'], candidate, owner)
    share_headers = owner | {'Idempotency-Key': str(uuid4())}
    confirmed = client.post('/v1/learning' + share_path, json=confirmed_body, headers=share_headers)
    assert confirmed.status_code == 200, confirmed.text
    share_id = confirmed.json()['id']
    incoming = f'/v1/learning/shared-idea-cards/{share_id}'
    assert client.get(incoming, headers=admin).status_code == 404
    assert client.get(incoming, headers=peer).json()['idea'] == 'Ý tưởng ban đầu'
    assert patch(f'/me/idea-cards/{card["id"]}', prose | {'idea': 'Ý tưởng mới', 'status': 'ACTIVE', 'revision': 1}, owner).status_code == 200
    assert client.get(incoming, headers=peer).json()['idea'] == 'Ý tưởng ban đầu'
    for revision, status in [(1, 'INACTIVE'), (2, 'ACTIVE')]:
        member = members['STUDENT_2']
        payload = {'revision': revision, 'status': status}
        assert patch(f'/offerings/{oid}/members/{member}', payload | proof('member-update', member, payload, admin), admin).status_code == 200
    assert client.get(incoming, headers=peer).status_code == 404
    suspended = client.post('/v1/learning' + share_path, json=confirmed_body, headers=share_headers)
    assert suspended.status_code == 200 and suspended.json()['status'] == 'SUSPENDED'
    assert client.get('/v1/learning/me/idea-shares', headers=owner).json()['items'][0]['status'] == 'SUSPENDED'
    candidate['revision'] = 2
    before_retract = proof('idea-share-create', card['id'], candidate, owner)
    assert publication('retract').status_code == 200
    hidden = client.get('/v1/learning/me/idea-cards/' + card['id'], headers=owner).json()
    assert hidden['idea'] == 'Ý tưởng mới' and hidden['source'] is None
    recovered = client.post('/v1/learning/me/idea-cards', json=card_body, headers=card_headers)
    assert recovered.status_code == 200, recovered.text
    assert recovered.json()['id'] == card['id'] and recovered.json()['source'] is None
    conflict = client.post('/v1/learning/me/idea-cards', json=card_body | {'idea': 'Khác'}, headers=card_headers)
    assert conflict.status_code == 409 and conflict.json()['code'] == 'IDEMPOTENCY_CONFLICT'
    assert patch('/me/idea-shares/' + share_id, {'revision': 1}, owner).json()['status'] == 'WITHDRAWN'
    withdrawn = client.post('/v1/learning' + share_path, json=confirmed_body, headers=share_headers)
    assert withdrawn.status_code == 200 and withdrawn.json()['status'] == 'WITHDRAWN'
    assert publication('publish').status_code == 200
    stale = post(client, share_path, candidate | before_retract, owner)
    assert stale.json()['code'] == 'STALE_PREVIEW'


def test_cookie_mutation_requires_csrf_boundary(entry):
    client, _, headers, _, _ = entry
    token = headers['SYSTEM_ADMIN']['Authorization'].removeprefix('Bearer ')
    client.cookies.set('auth_token', token)
    response = post(client, '/courses', {'code': 'SYN-CSRF', 'name': 'CSRF boundary'}, {})
    assert response.status_code == 403
    response = post(client, '/courses', {'code': 'SYN-CSRF', 'name': 'CSRF boundary'},
                    {'X-Campus-Request': 'learning', 'Origin': 'https://another-origin.invalid'})
    assert response.status_code == 403


def test_admin_cannot_bypass_management_preview(entry):
    client, _, headers, _, _ = entry
    response = client.post('/v1/learning/courses', json={'code': 'SYN-NO-PREVIEW', 'name': 'Unconfirmed'},
        headers=headers['SYSTEM_ADMIN'] | {'Idempotency-Key': str(uuid4())})
    assert response.status_code == 409


@pytest.mark.parametrize('entry', [{'pages': 33, 'optimize': True}], indirect=True)
def test_web_view_is_scanned_and_original_download_is_unchanged(entry):
    client, service, headers, accounts, original = entry
    admin, teacher, student = (headers[r] for r in ('SYSTEM_ADMIN', 'LECTURER', 'STUDENT'))
    term = post(client, '/terms', {'name': 'View term', 'start_date': '2026-11-01', 'end_date': '2027-02-01'}, admin).json()
    course = post(client, '/courses', {'code': 'VIEW', 'name': 'View course'}, admin).json()
    offering = post(client, '/offerings', {'course_id': course['id'], 'term_id': term['id'], 'section_code': 'A'}, admin).json()
    for role, member_role in [('LECTURER', 'INSTRUCTOR'), ('STUDENT', 'STUDENT')]:
        response = post(client, f'/offerings/{offering["id"]}/members', {'actor_subject_id': accounts[role]['subject_id'], 'role': member_role}, admin)
        assert response.status_code == 200, response.text
    material = post(client, f'/offerings/{offering["id"]}/materials', {'title': '33-page view'}, teacher).json()
    upload = post(client, f'/materials/{material["id"]}/upload-intents', {'filename': 'view.pdf', 'byte_size': len(original), 'content_type': 'application/pdf'}, teacher).json()
    received = client.put(f'/v1/learning/upload-intents/{upload["id"]}/content', content=original, headers=teacher)
    assert received.status_code == 200, received.text
    completed = post(client, f'/upload-intents/{upload["id"]}/complete', {}, teacher)
    assert completed.status_code == 200, completed.text
    vid = completed.json()['id']
    client.portal.call(service.tick)
    metadata = client.get(f'/v1/learning/versions/{vid}', headers=teacher).json()
    assert metadata['processing_state'] == 'READY', metadata
    assert metadata['web_optimized'] is True
    assert 'view_blob_id' not in metadata
    preview = post(client, f'/versions/{vid}/publication-preview', {'action': 'publish'}, teacher).json()
    published = post(client, f'/versions/{vid}/publish', {key: preview[key] for key in ('preview_id', 'confirmation_token')}, teacher)
    assert published.status_code == 200, published.text
    view = client.get(f'/v1/learning/versions/{vid}/content', headers=student)
    download = client.get(f'/v1/learning/versions/{vid}/download', headers=student)
    assert view.status_code == download.status_code == 200
    assert hashlib.sha256(view.content).digest() != hashlib.sha256(original).digest()
    assert download.content == original
    assert len(PdfReader(io.BytesIO(view.content)).pages) == 33


def test_exit_ticket_wall_time_requires_real_fold_or_rejects_gap():
    from campus247.application.learning.exit_tickets import class_wall_time

    repeated = {'local': '2026-11-01T01:30'}
    with pytest.raises(LearningError) as ambiguous:
        class_wall_time(repeated, 'America/New_York')
    assert ambiguous.value.code == 'AMBIGUOUS_WALL_TIME'
    assert class_wall_time(repeated | {'offset_minutes': -240}, 'America/New_York')['utc'] == '2026-11-01T05:30:00Z'
    assert class_wall_time(repeated | {'offset_minutes': -300}, 'America/New_York')['utc'] == '2026-11-01T06:30:00Z'
    with pytest.raises(LearningError) as gap:
        class_wall_time({'local': '2026-03-08T02:30', 'offset_minutes': -300}, 'America/New_York')
    assert gap.value.code == 'NONEXISTENT_WALL_TIME'
    with pytest.raises(LearningError) as false_offset:
        class_wall_time(repeated | {'offset_minutes': -360}, 'America/New_York')
    assert false_offset.value.code == 'INVALID_TIME_OFFSET'


@pytest.mark.parametrize('entry', [{'second_student': True}], indirect=True)
def test_exit_ticket_deadline_receipts_review_and_revocation(entry, monkeypatch):
    client, service, headers, accounts, pdf = entry
    admin, teacher, student, peer = (headers[r] for r in ('SYSTEM_ADMIN', 'LECTURER', 'STUDENT', 'STUDENT_2'))
    prefix = '/v1/learning'
    instant = datetime(2026, 11, 1, 5, 0, tzinfo=UTC)
    monkeypatch.setattr('campus247.application.learning.exit_tickets.exit_clock', lambda: instant)

    def checked(response):
        assert response.status_code == 200, response.text
        return response.json()

    def write(method, path, body, actor, key=None):
        return client.request(method, prefix + path, json=body, headers=actor | {'Idempotency-Key': key or str(uuid4())})

    def confirm(action, target, payload, actor):
        preview = checked(post(client, '/action-previews', {'action': action, 'target_id': target, 'payload': payload}, actor))
        return preview, payload | {name: preview[name] for name in ('preview_id', 'confirmation_token')}

    def publication(version_id, action):
        version_path = f'/versions/{version_id}'
        preview = checked(post(client, version_path + '/publication-preview', {'action': action}, teacher))
        return checked(post(client, version_path + '/' + action,
                            {name: preview[name] for name in ('preview_id', 'confirmation_token')}, teacher))

    term = checked(post(client, '/terms', {
        'name': 'Synthetic term', 'start_date': '2026-10-01', 'end_date': '2027-02-01', 'timezone': 'America/New_York',
    }, admin))
    course = checked(post(client, '/courses', {'code': 'EXIT-RL', 'name': 'Synthetic exit ticket'}, admin))
    offering = checked(post(client, '/offerings', {'course_id': course['id'], 'term_id': term['id'], 'section_code': 'A'}, admin))
    oid = offering['id']
    members = {}
    for role, member_role in [('LECTURER', 'INSTRUCTOR'), ('STUDENT', 'STUDENT'), ('STUDENT_2', 'STUDENT')]:
        members[role] = checked(post(client, f'/offerings/{oid}/members', {
            'actor_subject_id': accounts[role]['subject_id'], 'role': member_role,
        }, admin))
    session = checked(post(client, f'/offerings/{oid}/sessions', {'title': 'Synthetic lesson'}, teacher))
    material = checked(post(client, f'/offerings/{oid}/materials', {'title': 'Synthetic source', 'session_id': session['id']}, teacher))
    upload = checked(post(client, f'/materials/{material["id"]}/upload-intents', {
        'filename': 'fixture.pdf', 'byte_size': len(pdf), 'content_type': 'application/pdf',
    }, teacher))
    checked(client.put(f'{prefix}/upload-intents/{upload["id"]}/content', content=pdf, headers=teacher))
    source = checked(post(client, f'/upload-intents/{upload["id"]}/complete', {}, teacher))['id']
    client.portal.call(service.tick)
    publication(source, 'publish')
    instruction = checked(post(client, f'/sessions/{session["id"]}/reading-instructions', {
        'version_id': source, 'page_ranges': [{'start': 1, 'end': 1}], 'purpose': 'Read the synthetic page',
        'timing': 'AFTER', 'questions': ['Independent reading question'],
    }, teacher))
    list_path = f'/sessions/{session["id"]}/exit-tickets'
    assert client.get(prefix + list_path, headers=student).status_code == 404
    service.exit_ticket_offerings = frozenset({oid})
    assert checked(client.get(f'{prefix}/offerings/{oid}', headers=student))['capabilities']['exit_tickets']
    draft = {
        'version_id': source, 'page_no': 1, 'question': 'Explain the synthetic point.',
        'opens': {'local': '2026-11-01T01:30', 'offset_minutes': -240},
        'closes': {'local': '2026-11-01T01:30', 'offset_minutes': -300},
        'instruction': {'id': instruction['id'], 'revision': instruction['revision']},
    }
    create_key = str(uuid4())
    ticket = checked(write('POST', list_path, draft, teacher, create_key))
    assert ticket['state'] == 'DRAFT'
    assert checked(client.get(prefix + list_path, headers=student))['items'] == []
    path = f'/exit-tickets/{ticket["id"]}'
    mine = path + '/me/submission'
    assert client.get(prefix + path, headers=student).status_code == 404
    assert client.get(prefix + path, headers=admin).status_code == 404
    payload = {'revision': 1, 'operation': 'PUBLISH'}
    assert write('PATCH', path, payload, teacher).json()['code'] == 'CONFIRMATION_REQUIRED'
    preview, publication_body = confirm('exit-ticket-update', ticket['id'], payload, teacher)
    assert preview['exit_ticket']['students'] == 2 and preview['exit_ticket']['submissions'] == 0
    assert checked(write('PATCH', path, publication_body, teacher))['state'] == 'SCHEDULED'
    checked(write('PUT', f'/reading-instructions/{instruction["id"]}/seen', {'revision': instruction['revision']}, student))
    assert checked(client.get(prefix + mine, headers=student)) == {'submission': None}
    answer = {'revision': 0, 'answer': 'A private synthetic answer'}
    assert write('PUT', mine, answer, student).json()['code'] == 'TICKET_NOT_OPEN'
    instant = datetime(2026, 11, 1, 5, 30, tzinfo=UTC)
    assert checked(client.get(prefix + path, headers=student))['state'] == 'OPEN'
    key = str(uuid4())
    response = write('PUT', mine, answer, student, key)
    receipt = checked(response)
    assert response.headers['cache-control'] == 'no-store' and receipt['submitted_at'] == '2026-11-01T05:30:00Z'
    assert checked(write('PUT', mine, answer, student, key)) == receipt
    assert checked(client.get(prefix + mine, headers=peer)) == {'submission': None}
    assert client.get(prefix + path + '/submissions', headers=peer).status_code == 404
    with ThreadPoolExecutor(max_workers=2) as pool:
        edits = [pool.submit(write, 'PUT', mine, {'revision': 1, 'answer': candidate}, student)
                 for candidate in ('First concurrent edit', 'Second concurrent edit')]
        assert sorted(job.result().status_code for job in edits) == [200, 409]
    result = checked(client.get(prefix + mine, headers=student))['submission']
    assert result['revision'] == 2 and [entry['revision'] for entry in result['history']] == [1, 2]
    extend = {'revision': 2, 'operation': 'EXTEND', 'closes': {'local': '2026-11-01T02:00', 'offset_minutes': -300}}
    preview, extension = confirm('exit-ticket-update', ticket['id'], extend, teacher)
    assert preview['exit_ticket']['submissions'] == 1
    assert checked(write('PATCH', path, extension, teacher))['closes']['utc'] == '2026-11-01T07:00:00Z'
    instant = datetime(2026, 11, 1, 7, 0, tzinfo=UTC)
    assert checked(client.get(prefix + path, headers=student))['state'] == 'CLOSED'
    assert write('PUT', mine, {'revision': 2, 'answer': 'Too late'}, student).json()['code'] == 'TICKET_NOT_OPEN'
    assert checked(write('PUT', mine, answer, student, key)) == receipt
    assert post(client, '/action-previews', {'action': 'exit-ticket-update', 'target_id': ticket['id'],
                'payload': extend | {'revision': 3}}, teacher).json()['code'] == 'TICKET_CLOSED'
    submissions = checked(client.get(prefix + path + '/submissions', headers=teacher))['items']
    assert len(submissions) == 1 and submissions[0]['answer'] == result['answer'] and 'history' not in submissions[0]
    review = path + '/review'
    private_notes = {'revision': 0, 'operation': 'SAVE_DRAFT', 'topics': 'Private observation',
                     'next_plan': 'Private plan', 'explanation': 'Class-wide synthetic explanation'}
    assert checked(write('PUT', review, private_notes, teacher))['published'] is None
    assert checked(client.get(prefix + review, headers=peer)) == {'review': None}
    _, shared = confirm('exit-review-save', ticket['id'], {'revision': 1, 'operation': 'PUBLISH'}, teacher)
    checked(write('PUT', review, shared, teacher))
    assert checked(client.get(prefix + review, headers=peer)) == {'review': {
        'published': {'explanation': private_notes['explanation'], 'published_at': '2026-11-01T07:00:00Z'},
    }}
    preview, cancellation = confirm('exit-ticket-update', ticket['id'], {'revision': 3, 'operation': 'CANCEL'}, teacher)
    assert preview['exit_ticket']['submissions'] == 1
    assert checked(write('PATCH', path, cancellation, teacher))['state'] == 'CANCELLED'
    notices = checked(client.get(prefix + '/me/notifications', headers=student))['items']
    exit_notices = [item for item in notices if item.get('event_type') == 'EXIT_TICKET_UPDATED']
    assert len(exit_notices) == 4 and all(item['title'] == 'Cập nhật phiếu ra lớp' for item in exit_notices)
    publication(source, 'retract')
    redacted = checked(client.get(prefix + path, headers=student))
    assert redacted == {'id': ticket['id'], 'session_id': session['id'], 'revision': 4, 'state': 'SOURCE_UNAVAILABLE'}
    assert checked(write('POST', list_path, draft, teacher, create_key))['state'] == 'SOURCE_UNAVAILABLE'
    assert checked(client.get(prefix + mine, headers=student))['submission'] == result
    assert checked(write('PUT', mine, answer, student, key)) == receipt
    assert client.get(prefix + review, headers=peer).status_code == 404
    assert client.get(prefix + path + '/submissions', headers=teacher).status_code == 404
    notices = checked(client.get(prefix + '/me/notifications', headers=student))['items']
    assert not [item for item in notices if item.get('event_type') == 'EXIT_TICKET_UPDATED']
    member = members['STUDENT']
    _, removal = confirm('member-update', member['id'], {'revision': member['revision'], 'status': 'INACTIVE'}, admin)
    checked(write('PATCH', f'/offerings/{oid}/members/{member["id"]}', removal, admin))
    assert client.get(prefix + mine, headers=student).status_code == 404
    assert write('PUT', mine, answer, student, key).status_code == 404
