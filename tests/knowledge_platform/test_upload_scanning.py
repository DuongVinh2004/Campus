"""Every original that enters the knowledge store (upload, crawl, bulk import) is scanned before it is registered."""
import asyncio
import json
import logging
import sys
from uuid import uuid4

import pytest

from campus247.application.knowledge.platform_models import PlatformError
from campus247.bootstrap.scanner import scanner_from_environment
from campus247.infrastructure.knowledge import fetch
from campus247.infrastructure.knowledge.storage import FileKnowledgeStorage, ReadThroughKnowledgeStorage
from campus247.ports.file_scanner import ScanReceipt, ScanRejected, ScannerUnavailable
from .conftest import ROOT
from .test_document_fetch import fake_pool


class Scripted:
    name = "scripted"

    def __init__(self, outcome=None):
        self.outcome, self.seen = outcome, []

    async def scan(self, path):
        self.seen.append((path, path.read_bytes()))
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return ScanReceipt("clamav", "1.5.4", "28186", "2026-11-17T06:30:05+00:00", "a" * 64, path.stat().st_size, 1, "2026-11-17T08:00:00+00:00")


class Upload:
    def __init__(self, data):
        self.data, self.offset = data, 0

    async def read(self, size):
        chunk, self.offset = self.data[self.offset:self.offset + size], self.offset + size
        return chunk


PDF = b"%PDF-1.4\nfixture body\n%%EOF\n"


def storage(retained_directory, scanner):
    result = FileKnowledgeStorage(ROOT, retained_directory / "artifacts")
    result.scanner = scanner
    return result


def test_a_clean_original_is_scanned_where_it_was_stored_and_returned(retained_directory, caplog):
    scanner = Scripted()
    store = storage(retained_directory, scanner)
    with caplog.at_level(logging.INFO, logger="campus247.knowledge.scan"):
        artifact = asyncio.run(store.receive(Upload(PDF), "application/pdf"))
    assert [data for _, data in scanner.seen] == [PDF] and scanner.seen[0][0] == store.path(artifact.object_key)
    assert store.read(artifact.__dict__) == PDF
    assert artifact.scan["database_version"] == "28186" and artifact.scan["result"] == "CLEAN"  # carried to the audit record
    assert any(json.loads(r.message)["result"] == "clean" and json.loads(r.message)["database_version"] == "28186" for r in caplog.records)


def test_a_hit_is_rejected_without_the_signature_and_the_bytes_are_kept(retained_directory, caplog):
    store = storage(retained_directory, Scripted(ScanRejected("MALWARE_DETECTED", "Pdf.Exploit.Secret-Name")))
    with caplog.at_level(logging.WARNING, logger="campus247.knowledge.scan"), pytest.raises(PlatformError) as raised:
        asyncio.run(store.receive(Upload(PDF), "application/pdf"))
    assert (raised.value.status, raised.value.code) == (422, "FILE_REJECTED")
    assert "Secret-Name" not in raised.value.detail
    assert [path.read_bytes() for path in store.root.iterdir()] == [PDF]  # kept for inspection, never registered or deleted
    assert any(json.loads(r.message)["signature"] == "Pdf.Exploit.Secret-Name" for r in caplog.records)  # audit trail only


@pytest.mark.parametrize("code,expected", [("SCANNER_STALE", "SCANNER_STALE"), ("SCANNER_ERROR", "SCANNER_UNAVAILABLE"),
                                           ("SCANNER_UNAVAILABLE", "SCANNER_UNAVAILABLE")])
def test_no_verdict_is_a_retryable_503(retained_directory, code, expected):
    store = storage(retained_directory, Scripted(ScannerUnavailable(code)))
    with pytest.raises(PlatformError) as raised:
        asyncio.run(store.receive(Upload(PDF), "application/pdf"))
    assert (raised.value.status, raised.value.code) == (503, expected)


def test_a_wrong_file_type_is_refused_before_the_scanner_is_asked(retained_directory):
    scanner = Scripted()
    with pytest.raises(PlatformError, match="MIME_MISMATCH"):
        asyncio.run(storage(retained_directory, scanner).receive(Upload(b"not a pdf at all"), "application/pdf"))
    assert scanner.seen == []


def test_without_a_scanner_nothing_changes(retained_directory):
    store = storage(retained_directory, None)
    artifact = asyncio.run(store.receive(Upload(PDF), "application/pdf"))
    assert store.read(artifact.__dict__) == PDF and artifact.scan is None


def test_the_evidence_never_takes_part_in_equality_or_in_rebuilding_an_artifact_from_a_row():
    from campus247.application.knowledge.values import StoredArtifact
    plain = StoredArtifact("i", "k", "s", 1, "application/pdf", "original")
    scanned = StoredArtifact("i", "k", "s", 1, "application/pdf", "original", scan={"database_version": "1"})
    assert plain == scanned
    row = {k: v for k, v in scanned.__dict__.items() if k != "scan"}  # a database row has no scan column
    assert StoredArtifact(**{k: row[k] for k in StoredArtifact.__dataclass_fields__ if k != "scan"}) == plain


def test_the_restored_database_storage_scans_too(retained_directory):
    scanner = Scripted(ScanRejected("MALWARE_DETECTED", "X"))
    store = ReadThroughKnowledgeStorage(ROOT, retained_directory / "new", retained_directory / "old")
    store.scanner = scanner
    with pytest.raises(PlatformError, match="FILE_REJECTED"):
        asyncio.run(store.receive(Upload(PDF), "application/pdf"))


def test_a_crawled_document_with_a_hit_never_becomes_an_artifact(monkeypatch, retained_directory):
    fake_pool(monkeypatch, [(200, {"content-type": "application/pdf"}, PDF)])
    store = storage(retained_directory, Scripted(ScanRejected("MALWARE_DETECTED", "Crawl.Hit")))
    with pytest.raises(PlatformError, match="FILE_REJECTED"):
        asyncio.run(fetch.PublicDocumentFetcher().fetch("https://huce.edu.vn/a.pdf", store))


def test_a_crawled_clean_document_is_scanned_and_returned(monkeypatch, retained_directory):
    fake_pool(monkeypatch, [(200, {"content-type": "application/pdf"}, PDF)])
    scanner = Scripted()
    store = storage(retained_directory, scanner)
    artifact, _ = asyncio.run(fetch.PublicDocumentFetcher().fetch("https://huce.edu.vn/a.pdf", store))
    assert len(scanner.seen) == 1 and store.read(artifact.__dict__) == PDF


@pytest.mark.parametrize("inside_loop", [False, True])
def test_bulk_import_scans_from_sync_code_even_inside_a_running_loop(retained_directory, inside_loop):
    import hashlib
    source = retained_directory / "inventory.pdf"
    source.write_bytes(PDF)
    digest = hashlib.sha256(PDF).hexdigest()
    bad = storage(retained_directory, Scripted(ScanRejected("MALWARE_DETECTED", "Bulk.Hit")))
    good_scanner = Scripted()
    good = storage(retained_directory, good_scanner)

    def attempt(store):
        return store.copy_original(source, digest, "application/pdf")

    async def inside():
        with pytest.raises(PlatformError, match="FILE_REJECTED"):
            attempt(bad)
        attempt(good)

    if inside_loop:
        asyncio.run(inside())
    else:
        with pytest.raises(PlatformError, match="FILE_REJECTED"):
            attempt(bad)
        attempt(good)
    assert len(good_scanner.seen) == 1


def test_environment_builds_the_shared_scanner_and_the_cloud_profile_requires_one():
    assert scanner_from_environment({}) is None
    scanner = scanner_from_environment({"CAMPUS247_SCANNER_PORT": "33100", "CAMPUS247_SCANNER_MAX_DATABASE_AGE_HOURS": "24"})
    assert scanner.port == 33100 and scanner.max_database_age.total_seconds() == 24 * 3600
    assert scanner_from_environment({"CAMPUS247_SCANNER_SOCKET": "/run/clamav/clamd.ctl"}).socket_path == "/run/clamav/clamd.ctl"
    with pytest.raises(ValueError, match="cloud profile requires"):
        scanner_from_environment({"CAMPUS247_PROFILE": "cloud"})
    assert scanner_from_environment({"CAMPUS247_PROFILE": "cloud", "CAMPUS247_SCANNER_PORT": "33100"}).port == 33100
    for bad in ({"CAMPUS247_SCANNER_PORT": "33100", "CAMPUS247_SCANNER_SOCKET": "/x"}, {"CAMPUS247_SCANNER_PORT": "abc"},
                {"CAMPUS247_SCANNER_PORT": "70000"}, {"CAMPUS247_SCANNER_SOCKET": "relative.sock"},
                {"CAMPUS247_SCANNER_PORT": "33100", "CAMPUS247_SCANNER_MAX_DATABASE_AGE_HOURS": "0"},
                {"CAMPUS247_SCANNER_PORT": "33100", "CAMPUS247_SCANNER_MAX_DATABASE_AGE_HOURS": "x"}):
        with pytest.raises(ValueError):
            scanner_from_environment(bad)


# A real daemon (the test-only instance from the learning suite) behind the same storage.
sys.path.insert(0, str(ROOT / "tests/learning_entry"))
import test_scan_real_daemon as real  # noqa: E402


@pytest.fixture(scope="module")
def daemon():
    if not real.AVAILABLE:
        pytest.skip("needs the retained ClamAV bundle and a refreshed database")
    base = ROOT / ".tooling" / f"clamd-test-{uuid4().hex[:8]}"
    base.mkdir()
    running = real.Daemon(base)
    try:
        yield running
    finally:
        running.stop()


def test_real_daemon_clean_pdf_is_stored_and_a_marker_pdf_is_refused(daemon, retained_directory):
    from datetime import timedelta
    from campus247.infrastructure.scanning.clamd import ClamdScanner
    store = storage(retained_directory, ClamdScanner(host="127.0.0.1", port=daemon.port, max_database_age=timedelta(days=30)))
    clean = asyncio.run(store.receive(Upload(PDF), "application/pdf"))
    assert store.read(clean.__dict__) == PDF
    with pytest.raises(PlatformError, match="FILE_REJECTED"):
        asyncio.run(store.receive(Upload(PDF + b"\n%" + real.MARKER + b"\n"), "application/pdf"))
