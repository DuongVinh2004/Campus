"""One process owns the retained paid ledger; no counters are reset. Windows (msvcrt) and Linux (flock)."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = b"CAMPUS247_PAID_LEDGER_WRITER_V1\n"


class PaidLedgerWriterLease:
    def __init__(self, path: Path):
        path = path.absolute()
        if path.resolve() == ROOT or not path.resolve().is_relative_to(ROOT):
            raise ValueError("ledger lease outside workspace")
        for parent in (path, *path.parents):
            if parent.exists() and (parent.is_symlink() or parent.is_junction()
                                    or getattr(parent.stat(), "st_file_attributes", 0) & 0x400):
                raise ValueError("reparse ledger lease denied")
            if parent == ROOT:
                break
        try:
            handle = path.open("x+b")
        except FileExistsError:
            handle = path.open("r+b")
        else:
            handle.write(MARKER)
            handle.flush()
        try:
            handle.seek(0)
            if handle.read() != MARKER:
                raise ValueError("unrecognized ledger lease file")
            handle.seek(0)
            _lock(handle)
        except BaseException:
            handle.close()
            raise
        self._handle = handle

    def close(self):
        if not self._handle.closed:
            try:
                self._handle.seek(0)
                _unlock(self._handle)
            finally:
                self._handle.close()


def _lock(handle) -> None:
    """Exclusive, non-blocking lock on the lease file; raises OSError when another process holds it."""
    if os.name == "nt":
        import msvcrt
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise PermissionError(*error.args) from None  # same exception as the Windows byte-range lock


def _unlock(handle) -> None:
    if os.name == "nt":
        import msvcrt
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
