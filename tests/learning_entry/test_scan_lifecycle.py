"""Scan evidence over a version's life: receipts, the daily re-scan, quarantine and the current-scan publication gate.

Uses the real HTTP service with a scripted scanner that reports receipts like the ClamAV daemon does, and a controllable
clock, so days of signature updates are replayed in milliseconds.
"""
import asyncio
import copy
import hashlib
import io
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from campus247.infrastructure.learning.blob import PortScannerAdapter
from campus247.ports.file_scanner import ScanReceipt, ScanRejected, ScannerUnavailable
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pypdf import PdfWriter

from campus247.application.identity.session_service import SessionService
from campus247.bootstrap.learning import load_local_learning
from campus247.presentation.identity import IdentityMiddleware
from campus247.presentation.learning import create_learning_router

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from learning_local_setup import setup  # noqa: E402

SIGNATURE = 'Test.Signature-1'


def make_pdf(marker=0, pages=2):
    writer = PdfWriter()
    for index in range(pages):
        writer.add_blank_page(width=612 + marker, height=792 + index)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


class ScriptedScanner:
    name = 'scripted'

    def __init__(self, clock):
        self.clock, self.hits, self.down, self.calls = clock, set(), False, []

    async def scan(self, path):
        data = Path(path).read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        self.calls.append(digest)
        if self.down:
            raise ScannerUnavailable('SCANNER_UNAVAILABLE')
        if digest in self.hits:
            raise ScanRejected('MALWARE_DETECTED', SIGNATURE)
        return ScanReceipt('clamav', '1.5.4', '28186', '2026-11-17T06:30:05+00:00', digest, len(data), 1, self.clock().isoformat())

    async def health(self):
        return {'up': not self.down, 'stale': False}


def build_room(tmp_path, make_scanner):
    """A running service (generator) whose scanner is `make_scanner(clock)`; yields the Room."""
    if not tmp_path.resolve().is_relative_to(ROOT):
        raise RuntimeError('Use an explicit new --basetemp inside the authorized repository')
    fixture = tmp_path / 'fixture.pdf'
    fixture.write_bytes(make_pdf())
    scope = tmp_path / 'runtime'
    setup(scope, 'test-scan-lifecycle', fixture, second_student=True)
    service, adapter = load_local_learning(scope / 'config.json', workspace=ROOT, tenant_id='test-scan-lifecycle')
    clock = [datetime.now(UTC)]
    scanner = make_scanner(lambda: clock[0])
    service.scanner = PortScannerAdapter(scanner)
    service.rescan_clock = lambda: clock[0]
    accounts = {a['role']: a for a in json.loads((scope / 'credentials.json').read_text())['accounts']}
    students = [a for a in json.loads((scope / 'credentials.json').read_text())['accounts'] if a['role'] == 'STUDENT']
    accounts['STUDENT'], accounts['STUDENT_2'] = students
    headers = {role: {'Authorization': 'Bearer ' + adapter.authenticate(a['username'], a['password'])} for role, a in accounts.items()}
    app = FastAPI()
    app.add_middleware(IdentityMiddleware, adapter=adapter, session_service=SessionService())
    app.include_router(create_learning_router(service))
    with TestClient(app) as client:
        yield Room(client, service, headers, accounts, scanner, clock)


@pytest.fixture
def env(tmp_path):
    yield from build_room(tmp_path, ScriptedScanner)


def call(client, method, path, headers, **kwargs):
    extra = {'Idempotency-Key': str(uuid4())} if method.upper() in {'POST', 'PUT', 'PATCH'} else {}
    return client.request(method, '/v1/learning' + path, headers=headers | extra, **kwargs)


class Room:
    def __init__(self, client, service, headers, accounts, scanner, clock):
        self.client, self.service, self.headers, self.accounts = client, service, headers, accounts
        self.scanner, self.clock = scanner, clock
        self.teacher, self.student, admin = headers['LECTURER'], headers['STUDENT'], headers['SYSTEM_ADMIN']
        self.bodies = []

        def confirmed(action, target, payload):
            preview = call(client, 'POST', '/action-previews', admin, json={'action': action, 'target_id': target, 'payload': payload})
            assert preview.status_code == 200, preview.text
            return payload | {k: preview.json()[k] for k in ('preview_id', 'confirmation_token')}

        term = call(client, 'POST', '/terms', admin, json=confirmed('term-create', None, {'name': 'T', 'start_date': '2026-11-01', 'end_date': '2027-02-01'})).json()
        course = call(client, 'POST', '/courses', admin, json=confirmed('course-create', None, {'code': 'SCAN', 'name': 'Scan'})).json()
        self.oid = call(client, 'POST', '/offerings', admin, json=confirmed('offering-create', None, {'course_id': course['id'], 'term_id': term['id'], 'section_code': 'A'})).json()['id']
        for role, member_role in (('LECTURER', 'INSTRUCTOR'), ('STUDENT', 'STUDENT')):
            made = call(client, 'POST', f'/offerings/{self.oid}/members', admin, json=confirmed('member-create', self.oid, {'actor_subject_id': accounts[role]['subject_id'], 'role': member_role}))
            assert made.status_code == 200, made.text
        self.sid = call(client, 'POST', f'/offerings/{self.oid}/sessions', self.teacher, json={'title': 'Buổi 1'}).json()['id']
        self.mid = call(client, 'POST', f'/offerings/{self.oid}/materials', self.teacher, json={'title': 'Bài giảng', 'session_id': self.sid}).json()['id']

    def get(self, path, who='teacher'):
        response = call(self.client, 'GET', path, getattr(self, who))
        self.bodies.append(response.text)
        return response

    def upload(self, data):
        intent = call(self.client, 'POST', f'/materials/{self.mid}/upload-intents', self.teacher,
                      json={'filename': 'a.pdf', 'byte_size': len(data), 'content_type': 'application/pdf'}).json()
        sent = self.client.put(f'/v1/learning/upload-intents/{intent["id"]}/content', content=data, headers=self.teacher | {'Content-Type': 'application/pdf'})
        assert sent.status_code == 200, sent.text
        done = call(self.client, 'POST', f'/upload-intents/{intent["id"]}/complete', self.teacher, json={})
        assert done.status_code == 200, done.text
        self.tick()
        return done.json()['id']

    def tick(self):
        self.client.portal.call(self.service.tick)

    def publish(self, version_id):
        preview = call(self.client, 'POST', f'/versions/{version_id}/publication-preview', self.teacher, json={'action': 'publish'}).json()
        return call(self.client, 'POST', f'/versions/{version_id}/publish', self.teacher, json={k: preview[k] for k in ('preview_id', 'confirmation_token')})

    def stored(self, version_id):
        async def read():
            async with self.service.repository.transaction() as s:
                return copy.deepcopy(s['versions'][version_id]), copy.deepcopy(s['materials'][self.mid])
        return self.client.portal.call(read)

    def advance(self, hours):
        self.clock[0] += timedelta(hours=hours)


def notes(room, who):
    body = room.get('/me/notifications', who).json()
    return body['items'] if isinstance(body, dict) else body


def published(room, marker=0):
    version = room.upload(make_pdf(marker))
    assert room.publish(version).status_code == 200
    return version


def test_upload_records_a_receipt_that_no_api_response_exposes(env):
    version = published(env)
    row, _ = env.stored(version)
    receipt = row['scan_receipts'][-1]
    assert receipt['result'] == 'CLEAN' and receipt['database_version'] == '28186' and len(receipt['sha256']) == 64
    for who in ('teacher', 'student'):
        response = env.get(f'/versions/{version}', who)
        assert response.status_code == 200 and 'scan_receipts' not in response.json() and 'scan_quarantine' not in response.json()


def test_daily_rescan_refreshes_receipts_and_leaves_clean_versions_alone(env):
    version = published(env)
    before = len(env.stored(version)[0]['scan_receipts'])
    env.tick()  # too early: nothing is due
    assert len(env.stored(version)[0]['scan_receipts']) == before
    env.advance(25)
    env.tick()
    row, _ = env.stored(version)
    assert len(row['scan_receipts']) == before + 1 and row['publication_state'] == 'PUBLISHED'
    assert row['scan_receipts'][-1]['scanned_at'] > row['scan_receipts'][0]['scanned_at']


def test_a_late_detection_quarantines_hides_notifies_and_keeps_the_bytes(env):
    v1 = published(env, marker=0)
    data2 = make_pdf(marker=9)
    v2 = published(env, marker=9)
    assert env.stored(v2)[1]['current_published_version_id'] == v2
    storage_key = env.stored(v2)[0]['storage_key']
    env.scanner.hits.add(hashlib.sha256(data2).hexdigest())
    env.advance(25)
    env.tick()
    row, material = env.stored(v2)
    assert row['publication_state'] == 'QUARANTINED'
    assert row['scan_quarantine']['signature'] == SIGNATURE and row['scan_quarantine']['previous_state'] == 'PUBLISHED'
    assert material['current_published_version_id'] == v1  # students are back on the last clean version
    assert env.service.blobs.path(storage_key).read_bytes() == data2  # nothing is deleted
    # Students see neither the version nor its bytes; instructors cannot open or download it either.
    assert env.get(f'/versions/{v2}', 'student').status_code == 404
    assert env.get(f'/versions/{v2}/content', 'student').status_code == 404
    refused = env.get(f'/versions/{v2}/content', 'teacher')
    assert refused.status_code == 423 and refused.json()['code'] == 'FILE_QUARANTINED'
    assert env.get(f'/versions/{v1}/content', 'student').status_code == 200
    listed = env.get(f'/sessions/{env.sid}/materials', 'student').json()['items']
    assert all(item.get('current_published_version_id') in {v1, None} for item in listed)
    assert [n.get('event_type') for n in notes(env, 'teacher') if n['version_id'] == v2].count('MATERIAL_QUARANTINED') == 1
    assert not [n for n in notes(env, 'student') if n.get('event_type') == 'MATERIAL_QUARANTINED']
    assert all(SIGNATURE not in body for body in env.bodies)  # the signature name never reaches a response


def test_quarantine_of_the_only_published_version_leaves_the_material_unpublished(env):
    data = make_pdf(marker=3)
    version = published(env, marker=3)
    env.scanner.hits.add(hashlib.sha256(data).hexdigest())
    env.advance(25)
    env.tick()
    row, material = env.stored(version)
    assert row['publication_state'] == 'QUARANTINED' and material['current_published_version_id'] is None


def test_a_quarantined_version_cannot_be_published_again(env):
    data = make_pdf(marker=4)
    version = published(env, marker=4)
    env.scanner.hits.add(hashlib.sha256(data).hexdigest())
    env.advance(25)
    env.tick()
    preview = call(env.client, 'POST', f'/versions/{version}/publication-preview', env.teacher, json={'action': 'publish'})
    if preview.status_code == 200:
        body = preview.json()
        again = call(env.client, 'POST', f'/versions/{version}/publish', env.teacher, json={k: body[k] for k in ('preview_id', 'confirmation_token')})
        assert again.status_code == 409 and again.json()['code'] == 'FILE_QUARANTINED'
    else:
        assert preview.status_code == 409


def test_no_verdict_during_a_rescan_changes_nothing_and_backs_off(env):
    version = published(env)
    calls = len(env.scanner.calls)
    env.scanner.down = True
    env.advance(25)
    env.tick()
    row, _ = env.stored(version)
    assert row['publication_state'] == 'PUBLISHED'
    assert len(env.scanner.calls) == calls + 1  # one attempt, then it stops instead of spinning on a dead daemon
    env.tick()
    assert len(env.scanner.calls) == calls + 1  # still backing off
    env.service._rescan_wait_until = 0.0
    env.scanner.down = False
    env.tick()
    assert len(env.stored(version)[0]['scan_receipts']) == 2


def test_publication_waits_for_a_current_scan_instead_of_trusting_an_old_one(env):
    version = env.upload(make_pdf(marker=5))
    env.advance(40)  # the upload-time verdict is now 40 h old
    env.scanner.down = True
    blocked = env.publish(version)
    assert blocked.status_code == 503 and blocked.json()['code'] == 'SCAN_NOT_CURRENT'
    env.scanner.down = False
    env.tick()  # the re-scan refreshes it
    assert env.publish(version).status_code == 200


def test_a_scheduled_publication_does_not_go_live_on_a_stale_verdict(env):
    version = env.upload(make_pdf(marker=6))
    preview = call(env.client, 'POST', f'/versions/{version}/publication-preview', env.teacher,
                   json={'action': 'publish', 'scheduled_at': (datetime.now(UTC) + timedelta(hours=1)).isoformat().replace('+00:00', 'Z')}).json()
    scheduled = call(env.client, 'POST', f'/versions/{version}/publish', env.teacher,
                     json={'scheduled_at': preview['payload']['scheduled_at'], **{k: preview[k] for k in ('preview_id', 'confirmation_token')}})
    assert scheduled.status_code == 200, scheduled.text

    async def due():
        async with env.service.repository.transaction() as s:
            s['versions'][version]['scheduled_at'] = '2000-01-01T00:00:00Z'
    env.client.portal.call(due)
    env.advance(40)
    env.scanner.down = True  # the re-scan cannot refresh the verdict
    env.tick()
    assert env.stored(version)[0]['publication_state'] == 'SCHEDULED'
    env.scanner.down = False
    env.service._rescan_wait_until = 0.0
    env.tick()  # re-scan first or publish first, either way it must not publish unscanned: run once more
    env.tick()
    assert env.stored(version)[0]['publication_state'] == 'PUBLISHED'


def test_scanners_without_receipts_keep_the_old_behaviour(env):
    class Plain:
        name = 'plain'

        async def scan(self, path):
            return None

    env.service.scanner = Plain()
    version = published(env, marker=7)
    env.advance(100)
    env.tick()
    row, _ = env.stored(version)
    assert 'scan_receipts' not in row and row['publication_state'] == 'PUBLISHED'
