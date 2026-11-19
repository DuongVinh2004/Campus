"""Instructor upload -> student read lifecycle, probed through the real HTTP entry.

Evidence is machine-checked synthetic PDFs: hostile/invalid bytes, several versions,
hidden materials and the filename of the downloaded original.
"""
import io
import json
import hashlib
import sys
from pathlib import Path
from urllib.parse import unquote
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


def make_pdf(pages=1, *, password=None, marker=0):
    writer = PdfWriter()
    for index in range(pages):
        writer.add_blank_page(width=612 + marker, height=792 + index)
    if password:
        writer.encrypt(password)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


@pytest.fixture
def lifecycle(tmp_path):
    if not tmp_path.resolve().is_relative_to(ROOT):
        raise RuntimeError('Use an explicit new --basetemp inside the authorized repository')
    base = make_pdf()
    fixture = tmp_path / 'fixture.pdf'
    fixture.write_bytes(base)
    scope = tmp_path / 'runtime'
    setup(scope, 'test-learning-lifecycle', fixture, second_student=True)
    service, adapter = load_local_learning(scope / 'config.json', workspace=ROOT, tenant_id='test-learning-lifecycle')
    directory = json.loads((scope / 'credentials.json').read_text())['accounts']
    accounts = {a['role']: a for a in directory}
    students = [a for a in directory if a['role'] == 'STUDENT']
    accounts['STUDENT'], accounts['STUDENT_2'] = students
    headers = {role: {'Authorization': 'Bearer ' + adapter.authenticate(a['username'], a['password'])}
               for role, a in accounts.items()}
    app = FastAPI()
    app.add_middleware(IdentityMiddleware, adapter=adapter, session_service=SessionService())
    app.include_router(create_learning_router(service))
    with TestClient(app) as client:
        yield client, service, headers, accounts


def call(client, method, path, headers, **kwargs):
    extra = {'Idempotency-Key': str(uuid4())} if method.upper() in {'POST', 'PUT', 'PATCH'} else {}
    return client.request(method, '/v1/learning' + path, headers=headers | extra, **kwargs)


def confirmed(client, action, target, payload, headers):
    preview = call(client, 'POST', '/action-previews', headers, json={'action': action, 'target_id': target, 'payload': payload})
    assert preview.status_code == 200, preview.text
    return payload | {k: preview.json()[k] for k in ('preview_id', 'confirmation_token')}


class Class:
    """A class with one lecturer, two students and one session."""

    def __init__(self, env):
        self.client, self.service, self.headers, self.accounts = env
        client, admin = self.client, self.headers['SYSTEM_ADMIN']
        self.teacher, self.student, self.other = (self.headers[r] for r in ('LECTURER', 'STUDENT', 'STUDENT_2'))
        term = call(client, 'POST', '/terms', admin, json=confirmed(client, 'term-create', None, {'name': 'T', 'start_date': '2026-11-01', 'end_date': '2027-02-01'}, admin)).json()
        course = call(client, 'POST', '/courses', admin, json=confirmed(client, 'course-create', None, {'code': 'LIFE', 'name': 'Lifecycle'}, admin)).json()
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

    def upload(self, material_id, data, *, filename='bai-giang.pdf', declared=None, allow=True):
        if allow:
            self.service.scanner.hashes = frozenset(self.service.scanner.hashes | {hashlib.sha256(data).hexdigest()})
        intent = call(self.client, 'POST', f'/materials/{material_id}/upload-intents', self.teacher,
                      json={'filename': filename, 'byte_size': len(data) if declared is None else declared, 'content_type': 'application/pdf'})
        if intent.status_code != 200:
            return intent, None
        sent = self.client.put(f'/v1/learning/upload-intents/{intent.json()["id"]}/content', content=data,
                               headers=self.teacher | {'Content-Type': 'application/pdf'})
        if sent.status_code != 200:
            return sent, None
        done = call(self.client, 'POST', f'/upload-intents/{intent.json()["id"]}/complete', self.teacher, json={})
        assert done.status_code == 200, done.text
        self.client.portal.call(self.service.tick)
        return done, done.json()['id']

    def state(self, version_id):
        return call(self.client, 'GET', f'/versions/{version_id}', self.teacher).json()

    def publish(self, version_id):
        preview = call(self.client, 'POST', f'/versions/{version_id}/publication-preview', self.teacher, json={'action': 'publish'}).json()
        return call(self.client, 'POST', f'/versions/{version_id}/publish', self.teacher,
                    json={k: preview[k] for k in ('preview_id', 'confirmation_token')})

    def retract(self, version_id, replacement=None):
        body = {'action': 'retract'} | ({'replacement_version_id': replacement} if replacement else {})
        preview = call(self.client, 'POST', f'/versions/{version_id}/publication-preview', self.teacher, json=body)
        if preview.status_code != 200:
            return preview
        preview = preview.json()
        return call(self.client, 'POST', f'/versions/{version_id}/retract', self.teacher,
                    json={k: preview[k] for k in ('preview_id', 'confirmation_token')} | ({'replacement_version_id': replacement} if replacement else {}))

    def student_items(self, headers=None):
        rows = call(self.client, 'GET', f'/sessions/{self.sid}/materials', headers or self.student)
        assert rows.status_code == 200, rows.text
        return rows.json()['items']


def test_invalid_uploads_never_reach_students(lifecycle):
    room = Class(lifecycle)
    material = room.material()
    cases = {
        'not-a-pdf': b'%PDF-1.7\nthis is not a real pdf body',
        'encrypted': make_pdf(password='secret', marker=1),
        'too-many-pages': make_pdf(501, marker=2),
    }
    for name, data in cases.items():
        response, version_id = room.upload(material['id'], data)
        if version_id is None:
            assert response.status_code in {415, 422}, (name, response.status_code, response.text)
            continue
        state = room.state(version_id)
        assert state['processing_state'] in {'REJECTED', 'FAILED'}, (name, state)
        published = room.publish(version_id)
        assert published.status_code == 409, (name, published.text)
        assert call(room.client, 'GET', f'/versions/{version_id}/content', room.student).status_code == 404
    assert room.student_items() == []


def test_byte_size_mismatch_and_non_pdf_extension_are_refused(lifecycle):
    room = Class(lifecycle)
    material = room.material()
    data = make_pdf()
    short, version_id = room.upload(material['id'], data, declared=len(data) + 10)
    assert version_id is None and short.status_code in {400, 409, 413, 422}, short.text
    renamed = call(room.client, 'POST', f'/materials/{material["id"]}/upload-intents', room.teacher,
                   json={'filename': 'virus.exe', 'byte_size': len(data), 'content_type': 'application/pdf'})
    assert renamed.status_code == 415
    huge = call(room.client, 'POST', f'/materials/{material["id"]}/upload-intents', room.teacher,
                json={'filename': 'x.pdf', 'byte_size': 10 ** 12, 'content_type': 'application/pdf'})
    assert huge.status_code == 413
    assert call(room.client, 'POST', f'/materials/{material["id"]}/upload-intents', room.teacher,
                json={'filename': 'x.pdf', 'byte_size': 0, 'content_type': 'application/pdf'}).status_code == 413
    assert room.student_items() == []


def test_students_cannot_upload_publish_or_see_drafts(lifecycle):
    room = Class(lifecycle)
    material = room.material()
    data = make_pdf()
    _, version_id = room.upload(material['id'], data)
    assert room.state(version_id)['processing_state'] == 'READY'
    assert room.student_items() == []
    assert call(room.client, 'GET', f'/materials/{material["id"]}', room.student).status_code == 404
    assert call(room.client, 'GET', f'/versions/{version_id}', room.student).status_code == 404
    assert call(room.client, 'POST', f'/materials/{material["id"]}/upload-intents', room.student,
                json={'filename': 'x.pdf', 'byte_size': len(data), 'content_type': 'application/pdf'}).status_code == 403
    assert call(room.client, 'POST', f'/offerings/{room.oid}/materials', room.student, json={'title': 'x'}).status_code == 403
    assert call(room.client, 'POST', f'/versions/{version_id}/publication-preview', room.student, json={'action': 'publish'}).status_code in {403, 404}
    # A student of another class (not a member) sees nothing at all.
    assert call(room.client, 'GET', f'/sessions/{room.sid}/materials', room.other).status_code == 404
    assert call(room.client, 'GET', '/offerings', room.other).json()['items'] == []
    assert room.publish(version_id).status_code == 200
    assert [item['id'] for item in room.student_items()] == [material['id']]
    assert call(room.client, 'GET', f'/versions/{version_id}/content', room.other).status_code == 404


def test_new_version_replaces_current_only_when_published_and_retract_falls_back(lifecycle):
    room = Class(lifecycle)
    material = room.material()
    first_bytes, second_bytes = make_pdf(1, marker=5), make_pdf(2, marker=6)
    _, v1 = room.upload(material['id'], first_bytes)
    assert room.publish(v1).status_code == 200
    _, v2 = room.upload(material['id'], second_bytes)
    assert room.state(v2)['version_no'] == 2 and room.state(v2)['processing_state'] == 'READY'
    # While v2 is a draft students still read v1 only.
    listed = room.student_items()[0]
    assert [v['version_id'] for v in listed['versions']] == [v1]
    assert call(room.client, 'GET', f'/versions/{v2}/content', room.student).status_code == 404
    full = call(room.client, 'GET', f'/versions/{v1}/content', room.student)
    assert full.status_code == 200 and full.content == first_bytes
    # Publishing v2 makes it current; v1 stays published and readable.
    assert room.publish(v2).status_code == 200
    again = room.publish(v2)
    assert again.status_code == 409
    material_view = call(room.client, 'GET', f'/materials/{material["id"]}', room.student).json()
    assert material_view['current_published_version_id'] == v2
    assert call(room.client, 'GET', f'/versions/{v2}/content', room.student).content == second_bytes
    # Retracting the current version without a replacement is refused; with v1 as replacement it falls back.
    refused = room.retract(v2, replacement=str(uuid4()))
    assert refused.status_code == 409
    done = room.retract(v2, replacement=v1)
    assert done.status_code == 200, done.text
    material_view = call(room.client, 'GET', f'/materials/{material["id"]}', room.student).json()
    assert material_view['current_published_version_id'] == v1
    assert call(room.client, 'GET', f'/versions/{v2}/content', room.student).status_code == 404
    assert call(room.client, 'GET', f'/versions/{v1}/content', room.student).content == first_bytes


def test_hidden_material_disappears_for_students_and_returns(lifecycle):
    room = Class(lifecycle)
    material = room.material()
    _, version_id = room.upload(material['id'], make_pdf())
    assert room.publish(version_id).status_code == 200
    path = f'/materials/{material["id"]}'
    revision = call(room.client, 'GET', path, room.teacher).json()['revision']
    hide = confirmed(room.client, 'material-update', material['id'], {'visibility': 'HIDDEN', 'revision': revision}, room.teacher)
    assert call(room.client, 'PATCH', path, room.teacher, json=hide).status_code == 200
    assert room.student_items() == []
    assert call(room.client, 'GET', path, room.student).status_code == 404
    assert call(room.client, 'GET', f'/versions/{version_id}/content', room.student).status_code == 404
    assert [item['id'] for item in room.student_items(room.teacher)] == [material['id']]
    revision = call(room.client, 'GET', path, room.teacher).json()['revision']
    show = confirmed(room.client, 'material-update', material['id'], {'visibility': 'VISIBLE', 'revision': revision}, room.teacher)
    assert call(room.client, 'PATCH', path, room.teacher, json=show).status_code == 200
    assert [item['id'] for item in room.student_items()] == [material['id']]
    stale = call(room.client, 'PATCH', path, room.teacher, json={'title': 'Tên mới', 'revision': revision})
    assert stale.status_code == 409 and stale.json()['code'] == 'REVISION_CONFLICT'


def test_publish_notifies_students_and_download_keeps_a_useful_name(lifecycle):
    room = Class(lifecycle)
    material = room.material('Chương 1 – Giới thiệu')
    data = make_pdf()
    _, version_id = room.upload(material['id'], data, filename='slide-v1.pdf')
    assert call(room.client, 'GET', '/me/notifications', room.student).json()['items'] == []
    assert room.publish(version_id).status_code == 200
    notices = call(room.client, 'GET', '/me/notifications', room.student).json()['items']
    assert [n['version_id'] for n in notices] == [version_id] and notices[0]['title'] == 'Chương 1 – Giới thiệu'
    assert call(room.client, 'GET', '/me/notifications', room.other).json()['items'] == []
    download = call(room.client, 'GET', f'/versions/{version_id}/download', room.student)
    assert download.status_code == 200 and download.content == data
    disposition = download.headers['content-disposition']
    assert disposition.startswith('attachment;')
    assert unquote(disposition.split("filename*=UTF-8''", 1)[1]) == 'Chương 1 – Giới thiệu.pdf'
    assert 'filename="' in disposition and disposition.encode('ascii')
    inline = call(room.client, 'GET', f'/versions/{version_id}/content', room.student)
    assert inline.headers['content-disposition'].startswith('inline;')
