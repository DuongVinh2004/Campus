"""Switch a SQLite connection to WAL without failing when other processes start at the same moment.

`PRAGMA journal_mode = WAL` needs a lock on the database file and SQLite does not run the busy handler for it, so
several API processes starting together against a fresh file fail with "database is locked" on one of them.
The mode is stored in the file: once WAL, later calls only read it. Others copy this helper where the layer rules
forbid importing infrastructure (application/action/idempotency.py keeps its own private copy).
"""
from __future__ import annotations

import sqlite3
import time


def enable_wal(connection: sqlite3.Connection, *, wait_s: float = 30.0) -> None:
    deadline = time.monotonic() + wait_s
    while str(connection.execute("PRAGMA journal_mode").fetchone()[0]).lower() != "wal":
        try:
            connection.execute("PRAGMA journal_mode = WAL")
        except sqlite3.OperationalError as error:
            if "locked" not in str(error).lower() or time.monotonic() >= deadline:
                raise
            time.sleep(0.05)
