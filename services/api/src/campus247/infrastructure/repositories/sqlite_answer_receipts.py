"""Durable answer receipts (F4.2): which release and source versions an answer rested on, and how each statement was checked.

No question, answer text or name is stored, only hashes, source ids and check results. A receipt lives as long as its conversation.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path

from campus247.infrastructure.sqlite_wal import enable_wal

SCHEMA = """
CREATE TABLE IF NOT EXISTS answer_receipts(
  receipt_id TEXT PRIMARY KEY, owner_subject_id TEXT NOT NULL, conversation_id TEXT NOT NULL, message_id TEXT NOT NULL,
  release_id TEXT NOT NULL, binding_sha256 TEXT NOT NULL, outcome_kind TEXT NOT NULL, statements_sha256 TEXT NOT NULL,
  sources TEXT NOT NULL, checks TEXT NOT NULL, rejected_counts TEXT NOT NULL, created_at TEXT NOT NULL, expires_at TEXT NOT NULL,
  UNIQUE(conversation_id, message_id))
"""


class AnswerReceiptStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        with closing(self._connect()) as db:
            enable_wal(db)
            db.execute(SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        db.row_factory = sqlite3.Row
        return db

    def save(self, row: dict) -> None:
        with closing(self._connect()) as db:
            db.execute("INSERT OR IGNORE INTO answer_receipts VALUES(:receipt_id,:owner_subject_id,:conversation_id,:message_id,:release_id,:binding_sha256,"
                       ":outcome_kind,:statements_sha256,:sources,:checks,:rejected_counts,:created_at,:expires_at)",
                       {**row, "sources": json.dumps(row["sources"]), "checks": json.dumps(row["checks"]), "rejected_counts": json.dumps(row["rejected_counts"])})

    def get(self, receipt_id: str) -> dict | None:
        with closing(self._connect()) as db:
            r = db.execute("SELECT * FROM answer_receipts WHERE receipt_id=?", (receipt_id,)).fetchone()
        if r is None:
            return None
        return {**dict(r), "sources": json.loads(r["sources"]), "checks": json.loads(r["checks"]), "rejected_counts": json.loads(r["rejected_counts"])}

    def for_message(self, conversation_id: str, message_id: str) -> dict | None:
        with closing(self._connect()) as db:
            r = db.execute("SELECT receipt_id FROM answer_receipts WHERE conversation_id=? AND message_id=?", (conversation_id, message_id)).fetchone()
        return self.get(r["receipt_id"]) if r else None

    def delete_conversation(self, conversation_id: str) -> int:
        """The only deletion: when the conversation is deleted or expires (privacy request), its receipts go with it."""
        with closing(self._connect()) as db:
            return db.execute("DELETE FROM answer_receipts WHERE conversation_id=?", (conversation_id,)).rowcount

    def purge_expired(self, now_iso: str) -> int:
        with closing(self._connect()) as db:
            return db.execute("DELETE FROM answer_receipts WHERE expires_at<=?", (now_iso,)).rowcount
