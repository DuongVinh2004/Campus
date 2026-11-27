"""The ClamAV daemon client against a fake daemon: framing, verdicts, freshness and fail-closed behaviour."""
import asyncio
import hashlib
import struct
import time
from datetime import UTC, datetime, timedelta, timezone

import pytest
from campus247.infrastructure.scanning.clamd import ClamdScanner, parse_reply, parse_version
from campus247.ports.file_scanner import ScanRejected, ScannerUnavailable

BUILT = datetime(2026, 11, 3, 13, 27, 52, tzinfo=UTC)
VERSION = "ClamAV 1.5.4/28173/Tue Nov  3 13:27:52 2026"


class FakeClamd:
    """Speaks just enough of the clamd protocol; `reply` decides the verdict for INSTREAM."""

    def __init__(self, *, reply=b"stream: OK\0", version=VERSION, hang=False, drop=False):
        self.reply, self.version, self.hang, self.drop = reply, version, hang, drop
        self.streams, self.commands = [], []
        self.server = None
        self.port = None

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
            self.commands.append(command)
            if command == b"zPING":
                writer.write(b"PONG\0")
            elif command == b"zVERSION":
                writer.write(self.version.encode() + b"\0")
            elif command == b"zINSTREAM":
                received = bytearray()
                while True:
                    size = struct.unpack(">I", await reader.readexactly(4))[0]
                    if size == 0:
                        break
                    received += await reader.readexactly(size)
                self.streams.append(bytes(received))
                if self.hang:
                    await asyncio.sleep(30)
                if self.drop:
                    return
                writer.write(self.reply)
            await writer.drain()
        except (asyncio.IncompleteReadError, ConnectionError):
            pass
        finally:
            writer.close()


def run(coroutine):
    return asyncio.run(coroutine)


def scanner(port, **kwargs):
    kwargs.setdefault("clock", lambda: BUILT + timedelta(hours=5))
    kwargs.setdefault("chunk_bytes", 1000)
    kwargs.setdefault("database_timezone", UTC)
    return ClamdScanner(host="127.0.0.1", port=port, **kwargs)


def sample(tmp_path, size=4500):
    path = tmp_path / "file.pdf"
    path.write_bytes((b"%PDF-1.4\n" + bytes(range(256)) * 40)[:size])
    return path


def test_clean_file_is_framed_exactly_and_returns_a_receipt(tmp_path):
    path = sample(tmp_path)

    async def go():
        async with FakeClamd() as daemon:
            receipt = await scanner(daemon.port).scan(path)
            return receipt, daemon

    receipt, daemon = run(go())
    assert daemon.streams == [path.read_bytes()]  # several 1000-byte frames reassemble to the exact file
    assert receipt.result == "CLEAN" and receipt.engine == "clamav"
    assert (receipt.engine_version, receipt.database_version) == ("1.5.4", "28173")
    assert receipt.database_built_at == BUILT.isoformat()
    assert receipt.sha256 == hashlib.sha256(path.read_bytes()).hexdigest() and receipt.byte_size == path.stat().st_size


def test_a_signature_hit_rejects_and_names_the_signature_for_audit_only(tmp_path):
    async def go():
        async with FakeClamd(reply=b"stream: Pdf.Exploit.Test-1 FOUND\0") as daemon:
            await scanner(daemon.port).scan(sample(tmp_path))

    with pytest.raises(ScanRejected) as raised:
        run(go())
    assert raised.value.code == "MALWARE_DETECTED" and raised.value.signature == "Pdf.Exploit.Test-1"


# An empty reply (the daemon closed without a verdict) is "unavailable" and retried: see the dropped-connection test.
@pytest.mark.parametrize("reply", [b"stream: Can't allocate memory ERROR\0", b"garbage\0"])
def test_anything_that_is_not_a_verdict_fails_closed(tmp_path, reply):
    async def go():
        async with FakeClamd(reply=reply) as daemon:
            await scanner(daemon.port).scan(sample(tmp_path))

    with pytest.raises(ScannerUnavailable) as raised:
        run(go())
    assert raised.value.code == "SCANNER_ERROR"


def test_the_daemons_size_limit_is_a_rejection_not_a_pass(tmp_path):
    async def go():
        async with FakeClamd(reply=b"INSTREAM size limit exceeded. ERROR\0") as daemon:
            await scanner(daemon.port).scan(sample(tmp_path))

    with pytest.raises(ScanRejected) as raised:
        run(go())
    assert raised.value.code == "SCAN_LIMIT_EXCEEDED"


def test_a_stale_database_blocks_scanning_before_any_bytes_are_sent(tmp_path):
    async def go():
        async with FakeClamd() as daemon:
            late = scanner(daemon.port, clock=lambda: BUILT + timedelta(hours=73))
            with pytest.raises(ScannerUnavailable) as raised:
                await late.scan(sample(tmp_path))
            return raised.value.code, daemon.streams

    code, streams = run(go())
    assert code == "SCANNER_STALE" and streams == []


def test_a_database_exactly_at_the_limit_still_scans(tmp_path):
    async def go():
        async with FakeClamd() as daemon:
            return await scanner(daemon.port, clock=lambda: BUILT + timedelta(hours=72)).scan(sample(tmp_path))

    assert run(go()).result == "CLEAN"


def test_daemon_down_hang_and_dropped_connection_all_fail_closed(tmp_path):
    async def down():
        async with FakeClamd() as daemon:
            port = daemon.port
        await scanner(port).scan(sample(tmp_path))  # the daemon is gone

    async def hang():
        async with FakeClamd(hang=True) as daemon:
            await scanner(daemon.port, scan_timeout=0.5).scan(sample(tmp_path))

    async def drop():
        async with FakeClamd(drop=True) as daemon:
            await scanner(daemon.port).scan(sample(tmp_path))

    # A dropped connection is what a daemon reloading its database does: "unavailable", so a retry window retries it.
    for case, code in ((down, "SCANNER_UNAVAILABLE"), (hang, "SCANNER_UNAVAILABLE"), (drop, "SCANNER_UNAVAILABLE")):
        with pytest.raises(ScannerUnavailable) as raised:
            run(case())
        assert raised.value.code == code, case.__name__


def test_a_file_over_the_limit_is_rejected_without_connecting(tmp_path):
    async def go():
        async with FakeClamd() as daemon:
            with pytest.raises(ScanRejected) as raised:
                await scanner(daemon.port, max_bytes=1000).scan(sample(tmp_path))
            return raised.value.code, daemon.commands

    code, commands = run(go())
    assert code == "SCAN_LIMIT_EXCEEDED"
    assert b"zINSTREAM" not in commands


def test_an_unparsable_version_is_not_trusted(tmp_path):
    async def go():
        async with FakeClamd(version="ClamAV 1.5.4") as daemon:
            await scanner(daemon.port).scan(sample(tmp_path))

    with pytest.raises(ScannerUnavailable) as raised:
        run(go())
    assert raised.value.code == "SCANNER_ERROR"


def test_health_reports_age_and_staleness_and_never_raises(tmp_path):
    async def go():
        async with FakeClamd() as daemon:
            fresh = await scanner(daemon.port).health()
            stale = await scanner(daemon.port, clock=lambda: BUILT + timedelta(hours=100)).health()
            port = daemon.port
        down = await scanner(port).health()
        return fresh, stale, down

    fresh, stale, down = run(go())
    assert fresh["up"] and fresh["database_age_hours"] == 5.0 and fresh["stale"] is False and fresh["database_version"] == "28173"
    assert stale["up"] and stale["stale"] is True
    assert down == {"up": False, "code": "SCANNER_UNAVAILABLE"}


def test_the_daemon_must_be_loopback_and_exactly_one_transport_is_configured():
    with pytest.raises(ValueError, match="loopback"):
        ClamdScanner(host="10.0.0.5", port=3310)
    with pytest.raises(ValueError, match="exactly one"):
        ClamdScanner(host="127.0.0.1", port=3310, socket_path="/run/clamav/clamd.ctl")
    with pytest.raises(ValueError, match="exactly one"):
        ClamdScanner(host="127.0.0.1")
    ClamdScanner(host="127.0.0.1", port=3310)
    ClamdScanner(host="::1", port=3310)
    ClamdScanner(socket_path="/run/clamav/clamd.ctl")


def test_observer_gets_result_and_duration_without_file_identity(tmp_path):
    events = []

    async def go():
        async with FakeClamd() as daemon:
            await scanner(daemon.port, observer=events.append).scan(sample(tmp_path))

    run(go())
    assert [event["result"] for event in events] == ["clean"] and set(events[0]) == {"result", "code", "attempts", "duration_ms"}


def test_parsers():
    assert parse_version(VERSION, UTC) == ("1.5.4", "28173", BUILT)
    assert parse_version("ClamAV 1.4.2/27500/Fri Dec 12 08:00:01 2025", UTC)[2] == datetime(2025, 12, 12, 8, 0, 1, tzinfo=UTC)
    # clamd prints its LOCAL time: 13:27:52 in UTC+7 is 06:27:52 UTC
    assert parse_version(VERSION, timezone(timedelta(hours=7)))[2] == datetime(2026, 11, 3, 6, 27, 52, tzinfo=UTC)
    local = parse_version(VERSION)[2]  # default: this machine's zone
    assert local == datetime(2026, 11, 3, 13, 27, 52).astimezone(UTC)
    for bad in ("", "ClamAV", "ClamAV 1.5.4/x/Tue Nov 3 13:27:52 2026", "ClamAV 1.5.4/1/Tue Foo 3 13:27:52 2026",
                "ClamAV 1.5.4/1/Tue Feb 31 13:27:52 2026"):
        with pytest.raises(ScannerUnavailable):
            parse_version(bad)
    assert parse_reply("stream: OK\0") is None and parse_reply("stream: Win.Test.EICAR_HDB-1 FOUND\0") == "Win.Test.EICAR_HDB-1"
    with pytest.raises(ScannerUnavailable):
        parse_reply(" FOUND")


def test_a_build_time_in_the_future_means_a_clock_or_zone_mismatch_and_is_refused(tmp_path):
    async def go():
        async with FakeClamd() as daemon:
            early = scanner(daemon.port, clock=lambda: BUILT - timedelta(hours=2))
            await early.scan(sample(tmp_path))

    with pytest.raises(ScannerUnavailable) as raised:
        run(go())
    assert raised.value.code == "SCANNER_ERROR"
