"""Where write-action previews, their metadata and the "already used" marks live.

By default this is process memory (tests, one process). With several API processes the preview made in one
process must be recognised, and used at most once, by all of them: `SqlitePreviewStore` keeps the same three
things in a SQLite file shared by every process. The signing key for confirmation tokens is shared the same way
(see `configure_shared_state`). Nothing here weakens a check: an unknown preview or a bad signature is still refused.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def canonical(fingerprint: tuple[Any, ...]) -> str:
    """Stable text form of a preview fingerprint (ids, payload hash, datetimes) for storing and comparing."""
    def text(item):
        if isinstance(item, datetime):  # the same instant is the same text whatever offset it was built with
            return (item.astimezone(timezone.utc) if item.tzinfo else item).isoformat()
        return item
    return json.dumps([text(item) for item in fingerprint],
                      sort_keys=True, separators=(",", ":"), default=str)


class InMemoryPreviewStore:
    def __init__(self) -> None:
        self._bindings: dict[str, str] = {}
        self._metadata: dict[str, dict[str, str]] = {}
        self._consumed: set[str] = set()
        self._lock = threading.Lock()

    def put_binding(self, preview_id: str, canonical_fingerprint: str) -> None:
        self._bindings[preview_id] = canonical_fingerprint

    def get_binding(self, preview_id: str) -> str | None:
        return self._bindings.get(preview_id)

    def put_metadata(self, preview_id: str, metadata: dict[str, str]) -> None:
        self._metadata[preview_id] = metadata

    def get_metadata(self, preview_id: str) -> dict[str, str] | None:
        return self._metadata.get(preview_id)

    def is_consumed(self, preview_id: str) -> bool:
        return preview_id in self._consumed

    def consume(self, preview_id: str) -> bool:
        """Mark used; True only for the first caller."""
        with self._lock:
            if preview_id in self._consumed:
                return False
            self._consumed.add(preview_id)
            return True


class SqlitePreviewStore:
    """The same contract on a SQLite file in WAL mode, safe for several processes (one writer at a time)."""

    def __init__(self, path: str | Path) -> None:
        self._path = str(path)
        with self._connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS preview_binding(id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS preview_metadata(id TEXT PRIMARY KEY, metadata TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS preview_consumed(id TEXT PRIMARY KEY)")

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self._path, timeout=30, isolation_level=None)
        db.execute("PRAGMA busy_timeout = 30000")
        deadline = time.monotonic() + 30
        while str(db.execute("PRAGMA journal_mode").fetchone()[0]).lower() != "wal":
            try:
                db.execute("PRAGMA journal_mode = WAL")
            except sqlite3.OperationalError as error:  # several processes starting on a fresh file
                if "locked" not in str(error).lower() or time.monotonic() >= deadline:
                    raise
                time.sleep(0.05)
        db.execute("PRAGMA synchronous = FULL")
        return db

    def _run(self, sql: str, params: tuple = ()):
        db = self._connect()
        try:
            return db.execute(sql, params)
        finally:
            db.close()

    def put_binding(self, preview_id: str, canonical_fingerprint: str) -> None:
        self._run("INSERT OR REPLACE INTO preview_binding VALUES(?,?)", (preview_id, canonical_fingerprint))

    def get_binding(self, preview_id: str) -> str | None:
        db = self._connect()
        try:
            row = db.execute("SELECT fingerprint FROM preview_binding WHERE id=?", (preview_id,)).fetchone()
        finally:
            db.close()
        return row[0] if row else None

    def put_metadata(self, preview_id: str, metadata: dict[str, str]) -> None:
        self._run("INSERT OR REPLACE INTO preview_metadata VALUES(?,?)", (preview_id, json.dumps(metadata, sort_keys=True)))

    def get_metadata(self, preview_id: str) -> dict[str, str] | None:
        db = self._connect()
        try:
            row = db.execute("SELECT metadata FROM preview_metadata WHERE id=?", (preview_id,)).fetchone()
        finally:
            db.close()
        return json.loads(row[0]) if row else None

    def is_consumed(self, preview_id: str) -> bool:
        db = self._connect()
        try:
            return db.execute("SELECT 1 FROM preview_consumed WHERE id=?", (preview_id,)).fetchone() is not None
        finally:
            db.close()

    def consume(self, preview_id: str) -> bool:
        db = self._connect()
        try:
            return db.execute("INSERT OR IGNORE INTO preview_consumed VALUES(?)", (preview_id,)).rowcount == 1
        finally:
            db.close()
