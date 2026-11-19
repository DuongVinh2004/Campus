"""AUD-001 / AUD-002: a session revoked while a request is already past authentication must not write or stream.

The identity is checked once at the router. A revocation that lands while the request waits for the storage lock
(write) or for the checksum (download) used to be ignored. Evidence is synthetic accounts, a synthetic PDF and the
real HTTP entry with the real IdentityMiddleware and SessionService.
"""
import hashlib
import io
import json
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

import pytest
from campus247.application.identity.session_service import SessionService
from campus247.bootstrap.learning import load_local_learning
from campus247.presentation.identity import IdentityMiddleware
from campus247.presentation.learning import create_learning_router
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pypdf import PdfWriter

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from learning_local_setup import setup  # noqa: E402


def make_pdf(pages=1):
    writer = PdfWriter()
    for index in range(pages):
        writer.add_blank_page(width=612, height=792 + index)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def call(client, method, path, headers, **kwargs):
    extra = {'Idempotency-Key': str(uuid4())} if method.upper() in {'POST', 'PUT', 'PATCH'} else {}
    return client.request(method, '/v1/learning' + path, headers=headers | extra, **kwargs)


def confirmed(client, action, target, payload, headers):
    preview = call(client, 'POST', '/action-previews', headers, json={'action': action, 'target_id': target, 'payload': payload})
    assert preview.status_code == 200, preview.text
    return payload | {k: preview.json()[k] for k in ('preview_id', 'confirmation_token')}


class Class:
    """One class: a lecturer, a student and one session."""

    def __init__(self, env):
        self.client, self.service, self.headers, self.accounts = env
        client, admin = self.client, self.headers['SYSTEM_ADMIN']
        self.teacher, self.student = self.headers['LECTURER'], self.headers['STUDENT']
        term = call(client, 'POST', '/terms', admin, json=confirmed(client, 'term-create', None, {'name': 'T', 'start_date': '2026-11-01', 'end_date': '2027-02-01'}, admin)).json()
        course = call(client, 'POST', '/courses', admin, json=confirmed(client, 'course-create', None, {'code': 'REVO', 'name': 'Revocation'}, admin)).json()
        offering = call(client, 'POST', '/offerings', admin, json=confirmed(client, 'offering-create', None, {'course_id': course['id'], 'term_id': term['id'], 'section_code': 'A'}, admin)).json()
        self.oid = offering['id']
        for role, member_role in (('LECTURER', 'INSTRUCTOR'), ('STUDENT', 'STUDENT')):
            payload = {'actor_subject_id': self.accounts[role]['subject_id'], 'role': member_role}
            made = call(client, 'POST', f'/offerings/{self.oid}/members', admin, json=confirmed(client, 'member-create', self.oid, payload, admin))
            assert made.status_code == 200, made.text
        self.sid = call(client, 'POST', f'/offerings/{self.oid}/sessions', self.teacher, json={'title': 'Buổi 1'}).json()['id']

    def material(self, title='Bài giảng'):
        row = call(self.client, 'POST', f'/offerings/{self.oid}/materials', self.teacher, json={'title': title, 'session_id': self.sid})
        assert row.status_code == 200, row.text
        return row.json()

    def upload_and_publish(self, material_id, data):
        self.service.scanner.hashes = frozenset(self.service.scanner.hashes | {hashlib.sha256(data).hexdigest()})
        intent = call(self.client, 'POST', f'/materials/{material_id}/upload-intents', self.teacher,
                      json={'filename': 'bai-giang.pdf', 'byte_size': len(data), 'content_type': 'application/pdf'}).json()
        sent = self.client.put(f'/v1/learning/upload-intents/{intent["id"]}/content', content=data,
                               headers=self.teacher | {'Content-Type': 'application/pdf'})
        assert sent.status_code == 200, sent.text
        done = call(self.client, 'POST', f'/upload-intents/{intent["id"]}/complete', self.teacher, json={})
        assert done.status_code == 200, done.text
        self.client.portal.call(self.service.tick)
        version_id = done.json()['id']
        preview = call(self.client, 'POST', f'/versions/{version_id}/publication-preview', self.teacher, json={'action': 'publish'}).json()
        published = call(self.client, 'POST', f'/versions/{version_id}/publish', self.teacher,
                         json={k: preview[k] for k in ('preview_id', 'confirmation_token')})
        assert published.status_code == 200, published.text
        return version_id


@pytest.fixture
def env(tmp_path):
    if not tmp_path.resolve().is_relative_to(ROOT):
        raise RuntimeError('Use an explicit new --basetemp inside the authorized repository')
    fixture = tmp_path / 'fixture.pdf'
    fixture.write_bytes(make_pdf())
    scope = tmp_path / 'runtime'
    setup(scope, 'test-learning-revocation', fixture, second_student=True)
    service, adapter = load_local_learning(scope / 'config.json', workspace=ROOT, tenant_id='test-learning-revocation')
    directory = json.loads((scope / 'credentials.json').read_text())['accounts']
    accounts = {a['role']: a for a in directory}
    students = [a for a in directory if a['role'] == 'STUDENT']
    accounts['STUDENT'], accounts['STUDENT_2'] = students
    tokens = {role: adapter.authenticate(a['username'], a['password']) for role, a in accounts.items()}
    headers = {role: {'Authorization': 'Bearer ' + token} for role, token in tokens.items()}
    sessions = SessionService()
    app = FastAPI()
    app.add_middleware(IdentityMiddleware, adapter=adapter, session_service=sessions)
    app.include_router(create_learning_router(service))
    with TestClient(app) as client:
        yield (client, service, headers, accounts), sessions, tokens, adapter


def revoke_when_transaction_opens(service, sessions, token):
    """Revoke the session at the moment the request starts waiting for the storage transaction."""
    original = service.repository.transaction

    @asynccontextmanager
    async def revoking(*args, **kwargs):
        sessions.revoke(token)
        async with original(*args, **kwargs) as state:
            yield state

    service.repository.transaction = revoking


def test_write_after_revocation_during_the_storage_wait_is_refused(env):
    lifecycle, sessions, tokens, adapter = env
    room = Class(lifecycle)
    material = room.material('Tên cũ')
    path = f'/materials/{material["id"]}'
    revision = call(room.client, 'GET', path, room.teacher).json()['revision']
    body = confirmed(room.client, 'material-update', material['id'], {'title': 'Tên mới', 'revision': revision}, room.teacher)

    revoke_when_transaction_opens(room.service, sessions, tokens['LECTURER'])
    refused = call(room.client, 'PATCH', path, room.teacher, json=body)

    assert refused.status_code == 401, refused.text
    # The request was rejected inside the transaction, so nothing was saved. Sign in again to read it back.
    account = lifecycle[3]['LECTURER']
    again = {'Authorization': 'Bearer ' + adapter.authenticate(account['username'], account['password'])}
    assert call(room.client, 'GET', path, again).json()['title'] == 'Tên cũ'


def test_download_after_revocation_during_checksum_sends_no_bytes(env):
    lifecycle, sessions, tokens, adapter = env
    room = Class(lifecycle)
    data = make_pdf()
    material = room.material()
    version_id = room.upload_and_publish(material['id'], data)

    original = room.service.blobs.verify

    async def verify_then_revoke(*args, **kwargs):
        result = await original(*args, **kwargs)
        sessions.revoke(tokens['STUDENT'])
        return result

    room.service.blobs.verify = verify_then_revoke
    refused = call(room.client, 'GET', f'/versions/{version_id}/content', room.student)

    assert refused.status_code == 401, refused.status_code
    assert hashlib.sha256(data).hexdigest() not in refused.text
    assert not refused.content.startswith(b'%PDF')
