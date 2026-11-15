from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
import os
from pathlib import Path
import sqlite3
import tempfile
import time

from campus247.domain.shared.values import generate_uuid7


class IdempotencyState(StrEnum):
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED_RETRYABLE = "FAILED_RETRYABLE"
    FAILED_FINAL = "FAILED_FINAL"


class ReservationStatus(StrEnum):
    ACQUIRED = "ACQUIRED"
    REPLAY = "REPLAY"
    CONFLICT_REUSED = "CONFLICT_REUSED"
    CONFLICT_IN_PROGRESS = "CONFLICT_IN_PROGRESS"


@dataclass
class IdempotencyRecord:
    id: str
    actor_user_id: str
    operation_id: str
    idempotency_key: str
    request_fingerprint: str
    state: IdempotencyState
    http_status: int | None = None
    response_reference: str | None = None
    expires_at: datetime | None = None


@dataclass(frozen=True)
class ReservationResult:
    status: ReservationStatus
    record: IdempotencyRecord | None = None
    error_code: str | None = None


def _enable_wal(connection: sqlite3.Connection, wait_s: float = 30.0) -> None:
    """WAL needs a file lock that SQLite's busy handler does not wait for, so processes starting together on a fresh
    file would fail with "database is locked". Retry, and skip once the file is already WAL (the mode is stored in it).
    A copy of infrastructure/sqlite_wal.py: this layer may not import infrastructure."""
    deadline = time.monotonic() + wait_s
    while str(connection.execute("PRAGMA journal_mode").fetchone()[0]).lower() != "wal":
        try:
            connection.execute("PRAGMA journal_mode = WAL")
        except sqlite3.OperationalError as error:
            if "locked" not in str(error).lower() or time.monotonic() >= deadline:
                raise
            time.sleep(0.05)


class IdempotencyLedger:
    def __init__(self, database_path: str | Path | None = None, *, environment: str | None = None) -> None:
        configured_path = database_path or os.getenv("CAMPUS247_IDEMPOTENCY_DB")
        runtime_environment = (environment or os.getenv("ENVIRONMENT", "development")).strip().lower()
        if configured_path is None and runtime_environment in {"staging", "production"}:
            raise RuntimeError("Durable idempotency storage is required outside local development and testing")
        if configured_path is None:
            configured_path = Path(tempfile.gettempdir()) / f"campus247-idempotency-{os.getpid()}.sqlite3"
        if str(configured_path) == ":memory:":
            raise ValueError("Idempotency storage must be durable; in-memory databases are not allowed")

        self._database_path = Path(configured_path)
        if not self._database_path.parent.is_dir():
            raise ValueError("Idempotency database parent directory must already exist")
        self._initialize_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database_path, timeout=30, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 30000")
        _enable_wal(connection)
        connection.execute("PRAGMA synchronous = FULL")
        return connection

    @contextmanager
    def _transaction(self):
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize_schema(self) -> None:
        connection = self._connect()
        try:
            connection.execute("CREATE TABLE IF NOT EXISTS idempotency_record (id TEXT PRIMARY KEY, actor_user_id TEXT NOT NULL, operation_id TEXT NOT NULL, idempotency_key TEXT NOT NULL, request_fingerprint TEXT NOT NULL, state TEXT NOT NULL, http_status INTEGER, response_reference TEXT, expires_at TEXT NOT NULL, UNIQUE (actor_user_id, operation_id, idempotency_key))")
        finally:
            connection.close()

    @staticmethod
    def _record_from_row(row: sqlite3.Row) -> IdempotencyRecord:
        return IdempotencyRecord(row["id"], row["actor_user_id"], row["operation_id"], row["idempotency_key"], row["request_fingerprint"], IdempotencyState(row["state"]), row["http_status"], row["response_reference"], datetime.fromisoformat(row["expires_at"]))

    def reserve(
        self,
        actor_user_id: str,
        operation_id: str,
        idempotency_key: str,
        request_fingerprint: str,
        ttl_seconds: int = 86400,
    ) -> ReservationResult:
        if not (16 <= len(idempotency_key) <= 128) or not idempotency_key.isascii() or not idempotency_key.isprintable():
            raise ValueError("Idempotency key must be 16-128 visible ASCII characters")
        if ttl_seconds <= 0:
            raise ValueError("Idempotency TTL must be positive")

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=ttl_seconds)
        with self._transaction() as connection:
            row = connection.execute(
                """
                SELECT id, actor_user_id, operation_id, idempotency_key,
                       request_fingerprint, state, http_status,
                       response_reference, expires_at
                FROM idempotency_record
                WHERE actor_user_id = ? AND operation_id = ? AND idempotency_key = ?
                """,
                (actor_user_id, operation_id, idempotency_key),
            ).fetchone()
            if row is not None:
                existing = self._record_from_row(row)
                if existing.expires_at is not None and now >= existing.expires_at:
                    connection.execute(
                        "DELETE FROM idempotency_record WHERE actor_user_id = ? AND operation_id = ? AND idempotency_key = ?",
                        (actor_user_id, operation_id, idempotency_key),
                    )
                    row = None
                elif existing.request_fingerprint != request_fingerprint:
                    return ReservationResult(ReservationStatus.CONFLICT_REUSED, error_code="IDEMPOTENCY_KEY_REUSED")
                elif existing.state == IdempotencyState.IN_PROGRESS:
                    return ReservationResult(ReservationStatus.CONFLICT_IN_PROGRESS, error_code="IDEMPOTENCY_IN_PROGRESS")
                elif existing.state == IdempotencyState.COMPLETED:
                    return ReservationResult(ReservationStatus.REPLAY, record=existing)

            record = IdempotencyRecord(
                id=generate_uuid7(),
                actor_user_id=actor_user_id,
                operation_id=operation_id,
                idempotency_key=idempotency_key,
                request_fingerprint=request_fingerprint,
                state=IdempotencyState.IN_PROGRESS,
                expires_at=expires_at,
            )
            if row is None:
                connection.execute(
                    """
                    INSERT INTO idempotency_record
                    (id, actor_user_id, operation_id, idempotency_key,
                     request_fingerprint, state, expires_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (record.id, actor_user_id, operation_id, idempotency_key,
                     request_fingerprint, record.state.value, expires_at.isoformat()),
                )
            else:
                connection.execute(
                    """
                    UPDATE idempotency_record
                    SET request_fingerprint = ?, state = ?, http_status = NULL,
                        response_reference = NULL, expires_at = ?
                    WHERE actor_user_id = ? AND operation_id = ? AND idempotency_key = ?
                    """,
                    (request_fingerprint, record.state.value, expires_at.isoformat(),
                     actor_user_id, operation_id, idempotency_key),
                )
            return ReservationResult(ReservationStatus.ACQUIRED, record=record)

    def complete(
        self,
        actor_user_id: str,
        operation_id: str,
        idempotency_key: str,
        http_status: int,
        response_payload: str,
    ) -> None:
        with self._transaction() as connection:
            connection.execute(
                """
                UPDATE idempotency_record
                SET state = ?, http_status = ?, response_reference = ?
                WHERE actor_user_id = ? AND operation_id = ? AND idempotency_key = ?
                """,
                (IdempotencyState.COMPLETED.value, http_status, response_payload,
                 actor_user_id, operation_id, idempotency_key),
            )

    def fail(
        self,
        actor_user_id: str,
        operation_id: str,
        idempotency_key: str,
        retryable: bool = False,
    ) -> None:
        with self._transaction() as connection:
            connection.execute(
                """
                UPDATE idempotency_record
                SET state = ?
                WHERE actor_user_id = ? AND operation_id = ? AND idempotency_key = ?
                """,
                ((IdempotencyState.FAILED_RETRYABLE if retryable else IdempotencyState.FAILED_FINAL).value,
                 actor_user_id, operation_id, idempotency_key),
            )
