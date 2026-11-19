"""The retry window: a daemon that is busy reloading its database stalls or drops connections for tens of seconds
(measured 42 s on 2026-11-17), so "unavailable" is retried inside a bounded window; verdicts and limits never are."""
import asyncio
import struct
import time
from datetime import UTC, datetime, timedelta

import pytest
from campus247.infrastructure.scanning.clamd import ClamdScanner
from campus247.ports.file_scanner import ScanRejected, ScannerUnavailable

BUILT = datetime(2026, 11, 3, 13, 27, 52, tzinfo=UTC)
VERSION = "ClamAV 1.5.4/28173/Tue Nov  3 13:27:52 2026"


class Daemon:
    """A fake clamd that drops the first `failures` INSTREAM connections (like a daemon in the middle of a reload)."""

    def __init__(self, failures=0, reply=b"stream: OK\0"):
        self.failures, self.reply, self.attempts, self.streams = failures, reply, 0, 0

    async def __aenter__(self):
        self.server = await asyncio.start_server(self.handle, "127.0.0.1", 0)
        self.port = self.server.sockets[0].getsockname()[1]
        return self

    async def __aexit__(self, *exc):
        self.server.close()
        await self.server.wait_closed()

    async def handle(self, reader, writer):
        try:
            command = (await reader.readuntil(b"\0")).rstrip(b"\0")
            if command == b"zVERSION":
                writer.write(VERSION.encode() + b"\0")
            elif command == b"zINSTREAM":
                self.attempts += 1
                if self.attempts <= self.failures:
                    return
                while True:
                    size = struct.unpack(">I", await reader.readexactly(4))[0]
                    if size == 0:
                        break
                    await reader.readexactly(size)
                self.streams += 1
                writer.write(self.reply)
            await writer.drain()
        except (asyncio.IncompleteReadError, ConnectionError):
            pass
        finally:
            writer.close()


def scanner(port, **kwargs):
    kwargs.setdefault("clock", lambda: BUILT + timedelta(hours=5))
    kwargs.setdefault("database_timezone", UTC)
    return ClamdScanner(host="127.0.0.1", port=port, **kwargs)


def sample(tmp_path):
    path = tmp_path / "file.pdf"
    path.write_bytes(b"%PDF-1.4\nbody\n")
    return path


def run(coroutine):
    return asyncio.run(coroutine)


def test_a_daemon_that_recovers_within_the_window_gives_a_verdict(tmp_path):
    async def go():
        async with Daemon(failures=2) as daemon:
            events = []
            receipt = await scanner(daemon.port, retry_window=30, observer=events.append).scan(sample(tmp_path))
            return receipt, daemon.attempts, events

    receipt, attempts, events = run(go())
    assert receipt.result == "CLEAN" and attempts == 3
    assert events[-1]["result"] == "clean" and events[-1]["attempts"] == 3


def test_without_a_window_the_first_failure_is_reported(tmp_path):
    async def go():
        async with Daemon(failures=1) as daemon:
            await scanner(daemon.port).scan(sample(tmp_path))

    with pytest.raises(ScannerUnavailable):
        run(go())


def test_a_daemon_that_stays_down_fails_closed_when_the_window_ends(tmp_path):
    async def go():
        async with Daemon(failures=10**6) as daemon:
            started = time.perf_counter()
            with pytest.raises(ScannerUnavailable) as raised:
                await scanner(daemon.port, retry_window=3).scan(sample(tmp_path))
            return raised.value.code, time.perf_counter() - started, daemon.attempts

    code, seconds, attempts = run(go())
    assert code in {"SCANNER_UNAVAILABLE", "SCANNER_ERROR"} and 2.5 <= seconds < 8 and attempts >= 2


def test_hits_stale_databases_and_limits_are_never_retried(tmp_path):
    async def hit():
        async with Daemon(reply=b"stream: X FOUND\0") as daemon:
            with pytest.raises(ScanRejected):
                await scanner(daemon.port, retry_window=30).scan(sample(tmp_path))
            return daemon.streams

    async def stale():
        async with Daemon() as daemon:
            late = scanner(daemon.port, retry_window=30, clock=lambda: BUILT + timedelta(days=9))
            with pytest.raises(ScannerUnavailable) as raised:
                await late.scan(sample(tmp_path))
            return raised.value.code, daemon.streams

    async def limit():
        async with Daemon(reply=b"INSTREAM size limit exceeded. ERROR\0") as daemon:
            with pytest.raises(ScanRejected):
                await scanner(daemon.port, retry_window=30).scan(sample(tmp_path))
            return daemon.streams

    assert run(hit()) == 1 and run(limit()) == 1  # exactly one attempt each
    assert run(stale()) == ("SCANNER_STALE", 0)


def test_the_window_is_bounded():
    for bad in (601, -1):
        with pytest.raises(ValueError):
            ClamdScanner(host="127.0.0.1", port=3310, retry_window=bad)
    assert ClamdScanner(host="127.0.0.1", port=3310, retry_window=600).retry_window == 600


def test_configuration_carries_the_window_with_a_safe_default():
    from campus247.bootstrap.scanner import scanner_from_environment
    assert scanner_from_environment({"CAMPUS247_SCANNER_PORT": "33100"}).retry_window == 75
    assert scanner_from_environment({"CAMPUS247_SCANNER_PORT": "33100", "CAMPUS247_SCANNER_RETRY_SECONDS": "0"}).retry_window == 0
    for bad in ("x", "601", "-1"):
        with pytest.raises(ValueError):
            scanner_from_environment({"CAMPUS247_SCANNER_PORT": "33100", "CAMPUS247_SCANNER_RETRY_SECONDS": bad})
