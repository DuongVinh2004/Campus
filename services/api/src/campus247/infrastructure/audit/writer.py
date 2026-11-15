from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile
import threading
from typing import Any

from campus247.domain.shared.values import generate_uuid7
from campus247.infrastructure.sqlite_wal import enable_wal

SENSITIVE_KEY_PATTERNS = {
    "password",
    "secret",
    "token",
    "access_token",
    "authorization",
    "auth",
    "api_key",
    "credential",
    "prompt",
    "chain_of_thought",
    "cookie",
    "csrf",
    "session",
    "student_id",
    "email",
    "phone",
    "address",
}
SENSITIVE_VALUE_PATTERNS = re.compile(r"(?:bearer\s+|basic\s+|api[_-]?key\s*=|password\s*=|secret\s*=|token\s*=)", re.IGNORECASE)


class AuditPersistenceError(Exception):
    """Raised when audit record cannot be durably persisted."""
    pass


@dataclass(frozen=True)
class AuditRecord:
    event_id: str
    sequence_number: int
    action_type: str
    actor_pseudonym: str
    preview_id: str
    binding_hash: str
    stage: str
    outcome: str
    timestamp: datetime
    metadata_safe: dict[str, Any]
    prev_hash: str
    record_hash: str


def sanitize_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    if not metadata:
        return {}

    def sanitize_value(value: Any) -> Any:
        if isinstance(value, dict):
            return sanitize_metadata(value)
        if isinstance(value, list):
            return [sanitize_value(item) for item in value]
        if isinstance(value, str):
            if SENSITIVE_VALUE_PATTERNS.search(value) or "@" in value:
                return "[REDACTED]"
            return value
        if value is None or isinstance(value, (bool, int, float)):
            return value
        return "[REDACTED]"

    sanitized: dict[str, Any] = {}
    for k, v in metadata.items():
        if not isinstance(k, str) or any(pat in k.lower() for pat in SENSITIVE_KEY_PATTERNS):
            continue
        sanitized[k] = sanitize_value(v)
    return sanitized


class AppendOnlyAuditWriter:
    """Durable tamper-evident append-only audit log for controlled writes."""

    def __init__(self, database_path: str | Path | None = None, environment: str | None = None) -> None:
        self._lock = threading.Lock()
        configured_path = database_path or os.environ.get("CAMPUS247_AUDIT_DB")
        runtime_environment = (environment or os.environ.get("CAMPUS247_ENV") or "test").lower()
        if configured_path is None:
            if runtime_environment in {"staging", "production"}:
                raise AuditPersistenceError("durable audit storage is required")
            configured_path = Path(tempfile.gettempdir()) / f"campus247-audit-{os.getpid()}.sqlite3"
        if str(configured_path) == ":memory:":
            raise AuditPersistenceError("in-memory audit storage is not allowed")
        self._database_path = Path(configured_path)
        if not self._database_path.parent.exists():
            raise AuditPersistenceError("audit storage directory is unavailable")
        try:
            self._initialize_schema()
        except AuditPersistenceError:
            raise
        except Exception as exc:
            raise AuditPersistenceError("audit storage initialization failed") from exc

    @staticmethod
    def pseudonymize(actor_id: str) -> str:
        """Hash raw actor identifier to create safe pseudonym."""
        if not actor_id:
            return "anonymous"
        return f"act-{hashlib.sha256(actor_id.encode('utf-8')).hexdigest()[:12]}"

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self._database_path), timeout=5, isolation_level=None)
        connection.execute("PRAGMA busy_timeout = 5000")
        enable_wal(connection)
        connection.execute("PRAGMA synchronous = FULL")
        return connection

    def _initialize_schema(self) -> None:
        connection = self._connect()
        try:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS audit_record (
                    sequence_number INTEGER PRIMARY KEY,
                    event_id TEXT NOT NULL UNIQUE,
                    action_type TEXT NOT NULL,
                    actor_pseudonym TEXT NOT NULL,
                    preview_id TEXT NOT NULL,
                    binding_hash TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    prev_hash TEXT NOT NULL,
                    record_hash TEXT NOT NULL
                );
                CREATE TRIGGER IF NOT EXISTS audit_record_no_update
                BEFORE UPDATE ON audit_record
                BEGIN
                    SELECT RAISE(ABORT, 'audit records are append-only');
                END;
                CREATE TRIGGER IF NOT EXISTS audit_record_no_delete
                BEFORE DELETE ON audit_record
                BEGIN
                    SELECT RAISE(ABORT, 'audit records are append-only');
                END;
                """
            )
        finally:
            connection.close()

    @staticmethod
    def _canonical_data(
        event_id: str,
        sequence_number: int,
        action_type: str,
        actor_pseudonym: str,
        preview_id: str,
        binding_hash: str,
        stage: str,
        outcome: str,
        timestamp: datetime,
        metadata_safe: dict[str, Any],
        prev_hash: str,
    ) -> dict[str, Any]:
        return {
            "event_id": event_id,
            "seq": sequence_number,
            "action": action_type,
            "actor": actor_pseudonym,
            "pid": preview_id,
            "phash": binding_hash,
            "stage": stage,
            "outcome": outcome,
            "ts": timestamp.isoformat(),
            "prev_hash": prev_hash,
            "meta": metadata_safe,
        }

    @staticmethod
    def _record_from_row(row: tuple[Any, ...]) -> AuditRecord:
        metadata_safe = json.loads(row[9])
        if not isinstance(metadata_safe, dict):
            raise AuditPersistenceError("audit metadata is invalid")
        return AuditRecord(
            event_id=row[1],
            sequence_number=row[0],
            action_type=row[2],
            actor_pseudonym=row[3],
            preview_id=row[4],
            binding_hash=row[5],
            stage=row[6],
            outcome=row[7],
            timestamp=datetime.fromisoformat(row[8]),
            metadata_safe=metadata_safe,
            prev_hash=row[10],
            record_hash=row[11],
        )

    def append_transition(
        self,
        action_type: str,
        actor_id: str,
        preview_id: str,
        binding_hash: str,
        stage: str,
        outcome: str,
        metadata: dict[str, Any] | None = None,
    ) -> AuditRecord:
        safe_meta = sanitize_metadata(metadata)
        actor_pseudo = self.pseudonymize(actor_id)
        event_id = generate_uuid7()
        now = datetime.now(timezone.utc)
        connection: sqlite3.Connection | None = None
        try:
            with self._lock:
                connection = self._connect()
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT sequence_number, record_hash FROM audit_record ORDER BY sequence_number DESC LIMIT 1"
                ).fetchone()
                sequence_number = (row[0] + 1) if row else 1
                prev_hash = row[1] if row else "GENESIS"
                canonical_data = self._canonical_data(
                    event_id,
                    sequence_number,
                    action_type,
                    actor_pseudo,
                    preview_id,
                    binding_hash,
                    stage,
                    outcome,
                    now,
                    safe_meta,
                    prev_hash,
                )
                record_hash = hashlib.sha256(
                    json.dumps(canonical_data, sort_keys=True, separators=(",", ":")).encode("utf-8")
                ).hexdigest()
                connection.execute(
                    """
                    INSERT INTO audit_record (
                        sequence_number, event_id, action_type, actor_pseudonym, preview_id,
                        binding_hash, stage, outcome, occurred_at, metadata_json, prev_hash, record_hash
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        sequence_number,
                        event_id,
                        action_type,
                        actor_pseudo,
                        preview_id,
                        binding_hash,
                        stage,
                        outcome,
                        now.isoformat(),
                        json.dumps(safe_meta, sort_keys=True, separators=(",", ":")),
                        prev_hash,
                        record_hash,
                    ),
                )
                connection.commit()
                return AuditRecord(
                    event_id=event_id,
                    sequence_number=sequence_number,
                    action_type=action_type,
                    actor_pseudonym=actor_pseudo,
                    preview_id=preview_id,
                    binding_hash=binding_hash,
                    stage=stage,
                    outcome=outcome,
                    timestamp=now,
                    metadata_safe=safe_meta,
                    prev_hash=prev_hash,
                    record_hash=record_hash,
                )
        except Exception as exc:
            if connection is not None:
                connection.rollback()
            if isinstance(exc, AuditPersistenceError):
                raise
            raise AuditPersistenceError("audit record persistence failed") from exc
        finally:
            if connection is not None:
                connection.close()

    def verify_integrity(self) -> bool:
        try:
            with self._lock:
                records = self._load_records()
            expected_prev = "GENESIS"
            for record in records:
                if record.prev_hash != expected_prev:
                    return False
                canonical_data = self._canonical_data(
                    record.event_id,
                    record.sequence_number,
                    record.action_type,
                    record.actor_pseudonym,
                    record.preview_id,
                    record.binding_hash,
                    record.stage,
                    record.outcome,
                    record.timestamp,
                    record.metadata_safe,
                    record.prev_hash,
                )
                expected_hash = hashlib.sha256(
                    json.dumps(canonical_data, sort_keys=True, separators=(",", ":")).encode("utf-8")
                ).hexdigest()
                if record.record_hash != expected_hash:
                    return False
                expected_prev = record.record_hash
            return True
        except Exception as exc:
            if isinstance(exc, AuditPersistenceError):
                raise
            raise AuditPersistenceError("audit integrity verification failed") from exc

    def _load_records(self, preview_id: str | None = None) -> list[AuditRecord]:
        connection = self._connect()
        try:
            if preview_id:
                rows = connection.execute(
                    "SELECT * FROM audit_record WHERE preview_id = ? ORDER BY sequence_number",
                    (preview_id,),
                ).fetchall()
            else:
                rows = connection.execute("SELECT * FROM audit_record ORDER BY sequence_number").fetchall()
            return [self._record_from_row(row) for row in rows]
        finally:
            connection.close()

    def get_records(self, preview_id: str | None = None) -> list[AuditRecord]:
        with self._lock:
            return self._load_records(preview_id)
