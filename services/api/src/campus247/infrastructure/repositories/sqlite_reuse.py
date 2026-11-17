"""Per-thread reuse of SQLite connections for the hot read/write paths.

Opening a SQLite file costs a workspace path check (resolve plus a reparse-point test of every parent), the open itself,
two pragmas and a schema check. A chat turn opens the conversation and actor-state stores a dozen times, which was about a
fifth of the API's CPU under load. A connection is reused for at most `ttl_s` seconds, then closed and reopened through
the full path (path check, schema and tenant checks), so those guards still run every `ttl_s` seconds and on every error.

Safety: a connection is handed out to one user at a time. A nested or interleaved `connect()` on the same thread gets its
own fresh connection (the old behaviour), so one use can never commit or roll back another's transaction. Each use still
ends with `with connection:` (commit, or rollback on error), so an idle cached connection holds no transaction and no lock.
`invalidate()` retires every cached connection (for example after the tenant binding changes).
"""
from __future__ import annotations

import threading
import time
from collections.abc import Callable


class ReusableConnections:
    def __init__(self, ttl_s: float = 2.0) -> None:
        self.ttl_s = ttl_s
        self._local = threading.local()
        self._generation = 0

    def invalidate(self) -> None:
        self._generation += 1

    def checkout(self, open_connection: Callable[[], object]):
        """(connection, temporary). A temporary connection must be closed by the caller; a cached one is given back with release()."""
        slot = getattr(self._local, "slot", None)
        now = time.monotonic()
        if slot is not None and (now - slot["at"] > self.ttl_s or slot["generation"] != self._generation):
            if not slot["busy"]:
                self._close(slot)
                slot = None
        if slot is None:
            slot = self._local.slot = {"conn": open_connection(), "at": now, "busy": False, "generation": self._generation}
        if slot["busy"]:
            return open_connection(), True
        slot["busy"] = True
        return slot["conn"], False

    def close_current_thread(self) -> None:
        """Close this thread's cached connection (tests and shutdown; a cached one is also closed after ttl_s)."""
        slot = getattr(self._local, "slot", None)
        if slot is not None and not slot["busy"]:
            self._close(slot)
            self._local.slot = None

    def release(self, connection, temporary: bool, failed: bool) -> None:
        if temporary:
            self._safe_close(connection)
            return
        slot = self._local.slot
        slot["busy"] = False
        if failed:
            self._close(slot)
            self._local.slot = None

    @staticmethod
    def _safe_close(connection) -> None:
        try:
            connection.close()
        except Exception:  # noqa: BLE001 -- closing must never mask the real error
            pass

    def _close(self, slot) -> None:
        self._safe_close(slot["conn"])
