"""The streamed document upload must go through the malware scanner before anything is registered."""
import asyncio

import pytest

from campus247.application.knowledge.platform_models import PlatformError
from campus247.infrastructure.knowledge.multipart import parse_upload
from campus247.infrastructure.knowledge.storage import FileKnowledgeStorage
from campus247.ports.file_scanner import ScanRejected, ScannerUnavailable

from .conftest import ROOT
from .test_intake import multipart

EICAR_LIKE = b"X5O-fake-test-marker-not-a-real-signature"


class FakeScanner:
    def __init__(self, verdict):
        self.verdict, self.seen = verdict, []

    async def scan(self, path):
        self.seen.append(path.read_bytes())
        if self.verdict == "infected":
            raise ScanRejected("MALWARE", signature="Test-Signature")
        if self.verdict == "down":
            raise ScannerUnavailable("SCANNER_UNAVAILABLE")
        return type("Receipt", (), {"as_dict": lambda self: {"engine": "fake", "result": "clean"}})()


def run(storage, payload):
    return asyncio.run(parse_upload(multipart(payload), storage))


def test_a_clean_upload_is_scanned_and_carries_the_evidence(retained_directory):
    storage = FileKnowledgeStorage(ROOT, retained_directory / "artifacts")
    storage.scanner = FakeScanner("clean")
    _, artifact, _ = run(storage, "Nội dung hợp lệ.".encode())
    assert storage.scanner.seen == ["Nội dung hợp lệ.".encode()]
    assert artifact.scan == {"engine": "fake", "result": "clean"}


def test_an_infected_upload_is_rejected_before_it_can_be_registered(retained_directory):
    storage = FileKnowledgeStorage(ROOT, retained_directory / "artifacts")
    storage.scanner = FakeScanner("infected")
    with pytest.raises(PlatformError, match="FILE_REJECTED"):
        run(storage, EICAR_LIKE)
    assert len(list(storage.root.iterdir())) == 1  # the bytes are kept for inspection, never registered


def test_an_upload_with_no_scanner_verdict_is_not_accepted(retained_directory):
    storage = FileKnowledgeStorage(ROOT, retained_directory / "artifacts")
    storage.scanner = FakeScanner("down")
    with pytest.raises(PlatformError, match="SCANNER_UNAVAILABLE"):
        run(storage, b"anything")


def test_without_a_configured_scanner_uploads_still_work(retained_directory):
    storage = FileKnowledgeStorage(ROOT, retained_directory / "artifacts")
    _, artifact, _ = run(storage, b"plain text")
    assert artifact.scan is None
