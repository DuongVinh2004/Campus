"""A file that the host's own malware protection removed or locked right after we wrote it is a rejection, not "scanner unavailable".

On Windows, Defender deletes a file holding the EICAR test string the moment it is closed; reading it then fails with winerror 225
("the file contains a virus") or the file is simply gone. Reporting that as an unavailable scanner made the person retry for 75 seconds
and then see a service error for what is in fact a detected threat.
"""
import asyncio
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from campus247.infrastructure.scanning.clamd import ClamdScanner
from campus247.ports.file_scanner import ScanRejected, ScannerUnavailable

from test_clamd_scanner import BUILT, FakeClamd, run, scanner


def test_a_file_that_vanished_after_it_was_written_is_rejected_at_once(tmp_path):
    async def go():
        async with FakeClamd() as daemon:
            started = time.perf_counter()
            with pytest.raises(ScanRejected) as raised:
                await scanner(daemon.port, retry_window=30).scan(tmp_path / "removed-by-defender")
            assert raised.value.code == "HOST_PROTECTION_BLOCKED"
            assert time.perf_counter() - started < 5  # no retry window
    run(go())


class VirusLocked(OSError):
    """What Python raises on Windows when the antivirus blocks a read (errno 22, winerror 225)."""
    winerror = 225


def test_a_read_blocked_by_the_host_antivirus_is_rejected_not_retried(tmp_path, monkeypatch):
    target = tmp_path / "locked.txt"
    target.write_text("x")
    original = Path.open

    def blocked(self, *args, **kwargs):
        if self == target:
            raise VirusLocked(22, "Invalid argument")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", blocked)

    async def go():
        async with FakeClamd() as daemon:
            with pytest.raises(ScanRejected) as raised:
                await scanner(daemon.port, retry_window=30).scan(target)
            assert raised.value.code == "HOST_PROTECTION_BLOCKED"
            assert daemon.streams == []
    run(go())


def test_other_read_errors_and_a_missing_daemon_still_mean_unavailable(tmp_path, monkeypatch):
    target = tmp_path / "ok.txt"
    target.write_text("x")

    async def go():
        async with FakeClamd() as daemon:
            monkeypatch.setattr(Path, "open", lambda self, *a, **k: (_ for _ in ()).throw(PermissionError(13, "denied")) if self == target else open(self, *a, **k))
            with pytest.raises(ScannerUnavailable):
                await scanner(daemon.port, retry_window=0).scan(target)
        monkeypatch.undo()
        with pytest.raises(ScannerUnavailable):
            await scanner(1, retry_window=0).scan(target)  # nothing listens on port 1
    run(go())


def test_a_clean_file_still_scans_clean(tmp_path):
    target = tmp_path / "clean.txt"
    target.write_text("hello")

    async def go():
        async with FakeClamd() as daemon:
            receipt = await scanner(daemon.port).scan(target)
            assert receipt.byte_size == 5 and daemon.streams == [b"hello"]
    run(go())
