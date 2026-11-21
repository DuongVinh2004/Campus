"""ClamAV daemon client: stream the file over INSTREAM, never ask the daemon to open a path.

Why INSTREAM: no path or permission mapping between Windows, WSL and Linux, and no gap between check and use. Why a
daemon: the signature database loads once (about 1 GB resident) instead of on every file (11-13 s and ~1 GB each).

The client refuses to scan when the daemon's database is older than `max_database_age`, and treats every error,
timeout or size-limit answer as "no verdict" (ScannerUnavailable / ScanRejected), so callers fail closed.
"""
from __future__ import annotations

import asyncio
import hashlib
import re
import struct
import time
from datetime import UTC, datetime, timedelta
from ipaddress import ip_address
from pathlib import Path

from campus247.ports.file_scanner import ScanReceipt, ScanRejected, ScannerUnavailable

_MONTHS = {name: number for number, name in enumerate(
    ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), start=1)}
_VERSION = re.compile(r"^ClamAV (?P<engine>[0-9][0-9A-Za-z.\-]*)/(?P<database>\d+)/"
                      r"(?:\w{3}) (?P<month>\w{3})\s+(?P<day>\d{1,2}) (?P<time>\d{2}:\d{2}:\d{2}) (?P<year>\d{4})$")
_LOOPBACK_NAMES = {"localhost"}
MIN_SCAN_BYTES_PER_SECOND = 2 * 1024**2  # slowest throughput a scan may have before it counts as hung


def parse_version(text: str, timezone=None) -> tuple[str, str, datetime]:
    """`ClamAV 1.5.4/28173/Tue Nov  3 13:27:52 2026` -> (engine version, database version, database build time, UTC).

    clamd prints the build time in ITS local time zone, not UTC. The daemon is on this machine (loopback or Unix
    socket), so by default the text is read in this machine's local zone; pass a tzinfo when the daemon runs in another.
    """
    match = _VERSION.match(text.strip())
    if match is None or match["month"] not in _MONTHS:
        raise ScannerUnavailable("SCANNER_ERROR")
    hour, minute, second = (int(part) for part in match["time"].split(":"))
    try:
        naive = datetime(int(match["year"]), _MONTHS[match["month"]], int(match["day"]), hour, minute, second)
        built = (naive.replace(tzinfo=timezone) if timezone is not None else naive.astimezone()).astimezone(UTC)
    except (ValueError, OverflowError, OSError):
        raise ScannerUnavailable("SCANNER_ERROR") from None
    return match["engine"], match["database"], built


def parse_reply(reply: str) -> str | None:
    """Return None for a clean file, the signature name for a hit; raise for anything that is not a verdict."""
    text = reply.strip("\0\n\r ")
    if text.endswith("size limit exceeded. ERROR") or "size limit exceeded" in text:
        raise ScanRejected("SCAN_LIMIT_EXCEEDED")
    if text.startswith("stream:"):
        text = text[len("stream:"):].strip()
    if text == "OK":
        return None
    if text.endswith(" FOUND") and len(text) > len(" FOUND"):
        return text[: -len(" FOUND")].strip() or "UNKNOWN"
    raise ScannerUnavailable("SCANNER_ERROR")


def removed_by_host(error: OSError) -> bool:
    """The file we had just written is gone, or the operating system refuses to read it as "contains a virus" (Windows error 225/226).
    The host's own malware protection acted on it, which is a detection, not a scanner outage: retrying would only repeat it."""
    return isinstance(error, FileNotFoundError) or getattr(error, "winerror", None) in (225, 226)


class ClamdScanner:
    name = "clamd"

    def __init__(self, *, host: str | None = "127.0.0.1", port: int | None = None, socket_path: str | None = None,
                 max_database_age: timedelta = timedelta(hours=72), max_bytes: int = 100 * 1024**2,
                 connect_timeout: float = 2.0, scan_timeout: float = 30.0, chunk_bytes: int = 256 * 1024,
                 status_cache_seconds: float = 60.0, database_timezone=None, retry_window: float = 0.0,
                 clock=None, observer=None):
        if (port is None) == (socket_path is None):
            raise ValueError("Configure exactly one of a loopback TCP port or a Unix socket")
        if port is not None:
            if not 1 <= port <= 65535 or not self._is_loopback(host or ""):
                raise ValueError("The scanner daemon must listen on a loopback address; files never leave this machine")
        if max_database_age <= timedelta(0) or max_bytes <= 0 or chunk_bytes <= 0 or chunk_bytes > 4 * 1024**2:
            raise ValueError("Invalid scanner limits")
        self.host, self.port, self.socket_path = host, port, socket_path
        self.max_database_age, self.max_bytes = max_database_age, max_bytes
        self.connect_timeout, self.scan_timeout, self.chunk_bytes = connect_timeout, scan_timeout, chunk_bytes
        self.status_cache_seconds, self.database_timezone = status_cache_seconds, database_timezone
        if not 0 <= retry_window <= 600:
            raise ValueError("retry_window must be 0-600 seconds")
        self.retry_window = retry_window
        self.clock = clock or (lambda: datetime.now(UTC))
        self.observer = observer
        self._status: tuple[float, tuple[str, str, datetime]] | None = None

    @staticmethod
    def _is_loopback(host: str) -> bool:
        if host in _LOOPBACK_NAMES:
            return True
        try:
            return ip_address(host).is_loopback
        except ValueError:
            return False

    async def _open(self):
        try:
            if self.socket_path is not None:
                opening = asyncio.open_unix_connection(self.socket_path)
            else:
                opening = asyncio.open_connection(self.host, self.port)
            return await asyncio.wait_for(opening, self.connect_timeout)
        except (OSError, TimeoutError, NotImplementedError):
            raise ScannerUnavailable("SCANNER_UNAVAILABLE") from None

    async def _command(self, command: bytes) -> str:
        reader, writer = await self._open()
        try:
            writer.write(command + b"\0")
            await writer.drain()
            data = await asyncio.wait_for(reader.read(4096), self.connect_timeout + 5)
        except (OSError, TimeoutError):
            raise ScannerUnavailable("SCANNER_UNAVAILABLE") from None
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except OSError:
                pass
        return data.decode("utf-8", errors="replace").strip("\0\n\r ")

    async def ping(self) -> bool:
        try:
            return await self._command(b"zPING") == "PONG"
        except ScannerUnavailable:
            return False

    async def database(self, *, refresh: bool = False) -> tuple[str, str, datetime]:
        """(engine version, database version, database build time) from the live daemon, cached briefly."""
        now = time.monotonic()
        if not refresh and self._status is not None and now - self._status[0] < self.status_cache_seconds:
            return self._status[1]
        value = parse_version(await self._command(b"zVERSION"), self.database_timezone)
        if value[2] > self.clock() + timedelta(hours=1):
            # A build time in the future means the daemon and this process disagree about the time zone or clock.
            raise ScannerUnavailable("SCANNER_ERROR")
        self._status = (now, value)
        return value

    async def health(self) -> dict:
        """Cheap state for /health/ready and metrics; never raises."""
        try:
            engine, database, built = await self.database(refresh=True)
        except ScannerUnavailable as failure:
            return {"up": False, "code": failure.code}
        age = self.clock() - built
        return {"up": True, "engine_version": engine, "database_version": database, "database_built_at": built.isoformat(),
                "database_age_hours": round(age.total_seconds() / 3600, 1), "stale": age > self.max_database_age}

    async def scan(self, path: Path) -> ScanReceipt:
        """Scan one file. A daemon that is busy reloading its database may stall for tens of seconds (measured 42 s with
        ConcurrentDatabaseReload off), so "unavailable" is retried inside `retry_window` before it is reported.
        A signature hit, a limit, a stale database or an unreadable verdict are never retried."""
        started = time.perf_counter()
        attempts = 0
        while True:
            attempts += 1
            try:
                # Measured 2026-11-17: 20 simultaneous 50 MB scans took up to 23 s each, so the allowance grows with size.
                allowance = self.scan_timeout + Path(path).stat().st_size / MIN_SCAN_BYTES_PER_SECOND
                receipt = await asyncio.wait_for(self._scan(Path(path)), allowance)
            except ScanRejected as failure:
                self._observe("rejected", started, failure.code, attempts)
                raise
            except ScannerUnavailable as failure:
                error = failure
            except OSError as failure:
                if removed_by_host(failure):
                    self._observe("rejected", started, "HOST_PROTECTION_BLOCKED", attempts)
                    raise ScanRejected("HOST_PROTECTION_BLOCKED") from None
                error = ScannerUnavailable("SCANNER_UNAVAILABLE")
            except TimeoutError:
                error = ScannerUnavailable("SCANNER_UNAVAILABLE")
            else:
                self._observe("clean", started, None, attempts)
                return receipt
            remaining = self.retry_window - (time.perf_counter() - started)
            if error.code != "SCANNER_UNAVAILABLE" or remaining <= 0:
                self._observe("unavailable", started, error.code, attempts)
                raise error
            self._status = None  # the daemon may have come back with a different database
            await asyncio.sleep(min(2.0, remaining))

    def _observe(self, result: str, started: float, code: str | None, attempts: int = 1):
        if self.observer is not None:
            self.observer({"result": result, "code": code, "attempts": attempts,
                           "duration_ms": round((time.perf_counter() - started) * 1000)})

    async def _scan(self, path: Path) -> ScanReceipt:
        engine, database, built = await self.database()
        if self.clock() - built > self.max_database_age:
            raise ScannerUnavailable("SCANNER_STALE")
        size = path.stat().st_size
        if size > self.max_bytes:
            raise ScanRejected("SCAN_LIMIT_EXCEEDED")
        digest = hashlib.sha256()
        reader, writer = await self._open()
        started = time.perf_counter()
        try:
            writer.write(b"zINSTREAM\0")
            sent = 0
            with path.open("rb") as stream:
                while block := await asyncio.to_thread(stream.read, self.chunk_bytes):
                    sent += len(block)
                    if sent > size:  # the file grew while it was being scanned: the verdict would not cover it
                        raise ScannerUnavailable("SCANNER_ERROR")
                    digest.update(block)
                    writer.write(struct.pack(">I", len(block)) + block)
                    await writer.drain()
            if sent != size:
                raise ScannerUnavailable("SCANNER_ERROR")
            writer.write(struct.pack(">I", 0))
            await writer.drain()
            reply = (await reader.read(4096)).decode("utf-8", errors="replace")
        except OSError as failure:
            if removed_by_host(failure) and not isinstance(failure, ConnectionError):
                raise  # scan() turns this into a rejection
            raise ScannerUnavailable("SCANNER_UNAVAILABLE") from None
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except OSError:
                pass
        signature = parse_reply(reply)
        if signature is not None:
            raise ScanRejected("MALWARE_DETECTED", signature)
        return ScanReceipt(engine="clamav", engine_version=engine, database_version=database,
                           database_built_at=built.isoformat(), sha256=digest.hexdigest(), byte_size=size,
                           duration_ms=round((time.perf_counter() - started) * 1000),
                           scanned_at=self.clock().isoformat())
