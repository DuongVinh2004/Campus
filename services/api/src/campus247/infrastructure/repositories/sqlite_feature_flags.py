"""Durable feature-flag overrides (F0.3): one SQLite file in the state folder (WAL), several API processes may share it.

Rows of `ff_audit` are never deleted; removing an override is itself an audit row.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from campus247.infrastructure.sqlite_wal import enable_wal

SCHEMA = """
CREATE TABLE IF NOT EXISTS ff_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ff_overrides(
  key TEXT PRIMARY KEY, value TEXT NOT NULL, audience TEXT NOT NULL DEFAULT '{}', expires_at TEXT, reason TEXT NOT NULL,
  actor_subject_id TEXT NOT NULL, updated_at TEXT NOT NULL, revision INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS ff_previews(
  id TEXT PRIMARY KEY, actor_subject_id TEXT NOT NULL, payload TEXT NOT NULL, payload_hash TEXT NOT NULL,
  expected_version INTEGER NOT NULL, expires_at TEXT NOT NULL, used_at TEXT);
CREATE TABLE IF NOT EXISTS ff_audit(
  id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, actor_subject_id TEXT NOT NULL, key TEXT NOT NULL,
  before TEXT NOT NULL, after TEXT NOT NULL, reason TEXT NOT NULL, idempotency_key TEXT NOT NULL,
  UNIQUE(actor_subject_id, idempotency_key));
"""


class FeatureStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            enable_wal(db)
            db.executescript(SCHEMA)
            db.execute("INSERT OR IGNORE INTO ff_meta(key,value) VALUES('version','0')")

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        db.row_factory = sqlite3.Row
        return db

    @contextmanager
    def _tx(self):
        db = self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.execute("COMMIT")
        except BaseException:
            try:
                db.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise
        finally:
            db.close()

    def version(self) -> int:
        with self._connect() as db:
            return int(db.execute("SELECT value FROM ff_meta WHERE key='version'").fetchone()[0])

    def overrides(self) -> tuple[int, dict[str, dict]]:
        db = self._connect()
        try:
            version = int(db.execute("SELECT value FROM ff_meta WHERE key='version'").fetchone()[0])
            rows = db.execute("SELECT * FROM ff_overrides").fetchall()
        finally:
            db.close()
        out = {}
        for r in rows:
            out[r["key"]] = {"value": r["value"], "audience": json.loads(r["audience"]), "expires_at": r["expires_at"], "reason": r["reason"],
                             "by": r["actor_subject_id"], "at": r["updated_at"], "revision": r["revision"]}
        return version, out

    def save_preview(self, preview_id: str, actor: str, payload: dict, payload_hash: str, expected_version: int, expires_at: str) -> None:
        with self._tx() as db:
            db.execute("INSERT INTO ff_previews VALUES(?,?,?,?,?,?,NULL)",
                       (preview_id, actor, json.dumps(payload, sort_keys=True), payload_hash, expected_version, expires_at))

    def apply(self, *, preview_id: str, actor: str, idempotency_key: str, now: str, token_check) -> dict:
        """Consume a preview and write the change in one transaction. Returns the receipt, or a prior receipt for a repeated key.

        Raises KeyError('PREVIEW_EXPIRED'), ValueError('VERSION_CONFLICT:<n>') or PermissionError('CONFIRMATION_REQUIRED').
        """
        with self._tx() as db:
            prior = db.execute("SELECT * FROM ff_audit WHERE actor_subject_id=? AND idempotency_key=?", (actor, idempotency_key)).fetchone()
            if prior:
                return {"receipt_id": str(prior["id"]), "key": prior["key"], "after": json.loads(prior["after"]), "replayed": True,
                        "version": int(db.execute("SELECT value FROM ff_meta WHERE key='version'").fetchone()[0]), "applied_at": prior["at"]}
            row = db.execute("SELECT * FROM ff_previews WHERE id=? AND actor_subject_id=?", (preview_id, actor)).fetchone()
            if row is None or row["used_at"] or row["expires_at"] <= now:
                raise KeyError("PREVIEW_EXPIRED")
            if not token_check(row["payload_hash"]):
                raise PermissionError("CONFIRMATION_REQUIRED")
            version = int(db.execute("SELECT value FROM ff_meta WHERE key='version'").fetchone()[0])
            if version != row["expected_version"]:
                raise ValueError(f"VERSION_CONFLICT:{version}")
            payload = json.loads(row["payload"])
            key = payload["key"]
            old = db.execute("SELECT * FROM ff_overrides WHERE key=?", (key,)).fetchone()
            before = {"value": old["value"], "audience": json.loads(old["audience"]), "expires_at": old["expires_at"]} if old else None
            if payload.get("remove"):
                db.execute("DELETE FROM ff_overrides WHERE key=?", (key,))
                after = {"removed": True}
            else:
                revision = (old["revision"] + 1) if old else 1
                db.execute("INSERT OR REPLACE INTO ff_overrides VALUES(?,?,?,?,?,?,?,?)",
                           (key, payload["value"], json.dumps(payload["audience"], sort_keys=True), payload["expires_at"], payload["reason"], actor, now, revision))
                after = {"value": payload["value"], "audience": payload["audience"], "expires_at": payload["expires_at"]}
            cursor = db.execute("INSERT INTO ff_audit(at,actor_subject_id,key,before,after,reason,idempotency_key) VALUES(?,?,?,?,?,?,?)",
                                (now, actor, key, json.dumps(before), json.dumps(after), payload["reason"], idempotency_key))
            db.execute("UPDATE ff_previews SET used_at=? WHERE id=?", (now, preview_id))
            db.execute("UPDATE ff_meta SET value=? WHERE key='version'", (str(version + 1),))
            return {"receipt_id": str(cursor.lastrowid), "key": key, "after": after, "replayed": False, "version": version + 1, "applied_at": now}

    def audit(self, key: str | None, before_id: int | None, limit: int) -> list[dict]:
        sql, args = "SELECT * FROM ff_audit WHERE 1=1", []
        if key:
            sql += " AND key=?"
            args.append(key)
        if before_id:
            sql += " AND id<?"
            args.append(before_id)
        sql += " ORDER BY id DESC LIMIT ?"
        args.append(limit)
        db = self._connect()
        try:
            rows = db.execute(sql, args).fetchall()
        finally:
            db.close()
        return [{"id": r["id"], "at": r["at"], "by": r["actor_subject_id"], "key": r["key"], "before": json.loads(r["before"]),
                 "after": json.loads(r["after"]), "reason": r["reason"]} for r in rows]
