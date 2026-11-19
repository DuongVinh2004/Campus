"""The scan lifecycle against a REAL ClamAV daemon.

A test-only instance (its own port and database directory) loads the current official daily database plus signatures for
harmless marker strings, so no EICAR file is ever written to disk and the Windows real-time protection has nothing to
delete. The daemon the system itself runs is not touched.
"""
import asyncio
import hashlib
import os
import socket
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from campus247.infrastructure.scanning.clamd import ClamdScanner
from campus247.ports.file_scanner import ScanRejected, ScannerUnavailable

sys.path.insert(0, str(Path(__file__).parent))
from test_scan_lifecycle import build_room, make_pdf, published  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PORTABLE = ROOT / '.tooling/learning-clamav-20261104-01/portable/clamav-1.5.4.win.x64'
SERVICE_DB = ROOT / 'infra/local/clamav-service/database'
MARKER = b'CAMPUS-AV-TEST-MARKER-0001'
LATE_MARKER = b'CAMPUS-AV-LATE-MARKER-0002'

AVAILABLE = os.name == 'nt' and (PORTABLE / 'clamd.exe').is_file() and (SERVICE_DB / 'daily.cld').is_file()
pytestmark = pytest.mark.skipif(not AVAILABLE, reason='needs the retained ClamAV bundle and a refreshed database')


def ndb(name, marker):
    return f'{name}:0:*:{marker.hex()}\n'


class Daemon:
    def __init__(self, directory):
        self.directory = directory
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0))
            self.port = probe.getsockname()[1]
        (directory / 'db').mkdir()
        (directory / 'tmp').mkdir()
        (directory / 'db' / 'marker.ndb').write_text(ndb('Campus.Test.Marker', MARKER), encoding='ascii')
        (directory / 'db' / 'daily.cld').write_bytes((SERVICE_DB / 'daily.cld').read_bytes())
        (directory / 'clamd.conf').write_text('\n'.join([
            f'DatabaseDirectory {(directory / "db").as_posix()}', f'TemporaryDirectory {(directory / "tmp").as_posix()}',
            f'TCPSocket {self.port}', 'TCPAddr 127.0.0.1', 'Foreground yes', 'MaxThreads 4', 'StreamMaxLength 105M',
            'AlertExceedsMax yes', '']), encoding='ascii')
        self.process = subprocess.Popen([str(PORTABLE / 'clamd.exe'), '-c', str(directory / 'clamd.conf')], cwd=str(PORTABLE),
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
        deadline = time.time() + 90
        while time.time() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError('test clamd exited')
            if self.command(b'zPING') == 'PONG':
                return
            time.sleep(0.5)
        raise RuntimeError('test clamd did not start')

    def command(self, data):
        try:
            with socket.create_connection(('127.0.0.1', self.port), timeout=3) as connection:
                connection.sendall(data + b'\0')
                return connection.recv(256).strip(b'\0\n ').decode()
        except OSError:
            return ''

    def detects(self, data):
        import struct
        nul = bytes([0])
        try:
            with socket.create_connection(('127.0.0.1', self.port), timeout=5) as connection:
                connection.sendall(b'zINSTREAM' + nul + struct.pack('>I', len(data)) + data + struct.pack('>I', 0))
                return connection.recv(256).strip(nul + b' ').decode().endswith('FOUND')
        except OSError:
            return False

    def add_signature(self, name, marker):
        (self.directory / 'db' / f'{name}.ndb').write_text(ndb(name, marker), encoding='ascii')
        assert self.command(b'zRELOAD') == 'RELOADING'
        deadline = time.time() + 120
        while time.time() < deadline:  # the daemon keeps answering during a reload; wait until the new signature is live
            time.sleep(1)
            if self.detects(b'x' + marker + b'x'):
                return
        raise RuntimeError('reload did not finish')

    def stop(self):
        self.process.kill()
        self.process.wait()


@pytest.fixture(scope='module')
def daemon():
    base = ROOT / '.tooling' / f'clamd-test-{uuid4().hex[:8]}'
    base.mkdir()
    running = Daemon(base)
    try:
        yield running
    finally:
        running.stop()


def scanner_for(daemon, clock=None, **kwargs):
    kwargs.setdefault('max_database_age', timedelta(days=30))
    if clock is not None:
        kwargs['clock'] = clock
    return ClamdScanner(host='127.0.0.1', port=daemon.port, **kwargs)


def test_clean_file_and_marker_file(daemon, tmp_path):
    scanner = scanner_for(daemon)
    clean = tmp_path / 'clean.pdf'
    clean.write_bytes(make_pdf())
    receipt = asyncio.run(scanner.scan(clean))
    assert receipt.result == 'CLEAN' and receipt.database_version.isdigit()
    assert receipt.sha256 == hashlib.sha256(clean.read_bytes()).hexdigest()
    hit = tmp_path / 'marker.pdf'
    hit.write_bytes(make_pdf() + b'\n%' + MARKER + b'\n')
    with pytest.raises(ScanRejected) as raised:
        asyncio.run(scanner.scan(hit))
    assert raised.value.signature.startswith('Campus.Test.Marker')  # clamd adds .UNOFFICIAL to custom signatures


def test_marker_straddling_frame_boundaries_is_still_detected(daemon, tmp_path):
    body = make_pdf() + b'\n%' + MARKER + b'\n'
    start = body.index(MARKER)
    for chunk in (7, 13, 64, start + 5, start + len(MARKER) // 2):  # the marker is cut by the frame boundary in each case
        path = tmp_path / f'cut-{chunk}.pdf'
        path.write_bytes(body)
        with pytest.raises(ScanRejected):
            asyncio.run(scanner_for(daemon, chunk_bytes=chunk).scan(path))


def test_stale_gate_uses_the_daemons_own_version(daemon, tmp_path):
    clean = tmp_path / 'clean.pdf'
    clean.write_bytes(make_pdf())
    late = scanner_for(daemon, max_database_age=timedelta(hours=1), clock=lambda: datetime.now(UTC) + timedelta(days=2))
    with pytest.raises(ScannerUnavailable) as raised:
        asyncio.run(late.scan(clean))
    assert raised.value.code == 'SCANNER_STALE'
    assert asyncio.run(scanner_for(daemon).health())['stale'] is False


def test_http_upload_with_a_hit_is_rejected_and_nothing_is_published(daemon, tmp_path):
    (tmp_path / 'a').mkdir()
    for room in build_room(tmp_path / 'a', lambda clock: scanner_for(daemon, clock=clock)):
        clean = room.upload(make_pdf(marker=21))
        row, _ = room.stored(clean)
        assert row['processing_state'] == 'READY' and row['scan_receipts'][0]['database_version'].isdigit()
        bad = room.upload(make_pdf(marker=22) + b'\n%' + MARKER + b'\n')
        row, _ = room.stored(bad)
        assert row['processing_state'] == 'REJECTED' and row['error_code'] == 'FILE_REJECTED'
        assert room.publish(bad).status_code == 409
        assert all('Campus.Test.Marker' not in body for body in room.bodies)


def test_a_signature_added_tomorrow_quarantines_a_version_published_today(daemon, tmp_path):
    late = make_pdf(marker=31) + b'\n%' + LATE_MARKER + b'\n'
    (tmp_path / 'b').mkdir()
    for room in build_room(tmp_path / 'b', lambda clock: scanner_for(daemon, clock=clock)):
        previous = published(room, marker=30)
        version = room.upload(late)  # no signature knows this marker yet: it is clean today
        assert room.publish(version).status_code == 200
        assert room.stored(version)[0]['publication_state'] == 'PUBLISHED'
        daemon.add_signature('late', LATE_MARKER)  # tomorrow's signature update
        room.advance(25)
        room.tick()
        row, material = room.stored(version)
        assert row['publication_state'] == 'QUARANTINED' and row['scan_quarantine']['signature'].startswith('late')
        assert material['current_published_version_id'] == previous
        assert room.get(f'/versions/{version}/content', 'student').status_code == 404
        assert room.get(f'/versions/{version}/content', 'teacher').status_code == 423
        assert room.stored(previous)[0]['publication_state'] == 'PUBLISHED'
