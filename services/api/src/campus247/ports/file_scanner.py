"""A malware scanner boundary shared by every flow that accepts files.

A scanner either returns a receipt for a clean file or raises. It never returns "unknown": a scanner that cannot decide
raises ScannerUnavailable, so callers fail closed.
"""
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class ScanReceipt:
    """What was scanned and with which signatures. A clean result means "no known signature matched at this time"."""
    engine: str
    engine_version: str
    database_version: str
    database_built_at: str
    sha256: str
    byte_size: int
    duration_ms: int
    scanned_at: str
    result: str = "CLEAN"

    def as_dict(self) -> dict:
        return asdict(self)


class ScanRejected(Exception):
    """The file matched a signature or exceeds a scan limit. `signature` is for logs and audit only, never for users."""

    def __init__(self, code: str, signature: str | None = None):
        super().__init__(code)
        self.code, self.signature = code, signature


class ScannerUnavailable(Exception):
    """The scanner could not give a verdict (down, stale database, timeout, error)."""

    def __init__(self, code: str = "SCANNER_UNAVAILABLE"):
        super().__init__(code)
        self.code = code


class FileScanner(Protocol):
    name: str

    async def scan(self, path: Path) -> ScanReceipt: ...
