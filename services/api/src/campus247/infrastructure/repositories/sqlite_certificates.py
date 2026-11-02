"""Additive local demo migration. Atomic business state, replay and audit."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[6]


def workspace_path(path: Path) -> Path:
    path = path.absolute()
    resolved = path.resolve()
    if resolved == ROOT or not resolved.is_relative_to(ROOT):
        raise ValueError("certificate storage must stay inside workspace")
    for part in (path, *path.parents):
        if part.exists() and (part.is_symlink() or part.is_junction()
                              or getattr(part.stat(), "st_file_attributes", 0) & 0x400):
            raise ValueError("reparse storage path denied")
        if part == ROOT:
            break
    return resolved


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class SQLiteCertificateTransaction:
    def __init__(self, connection):
        self.connection = connection

    def get(self, document_id):
        row = self.connection.execute("SELECT record FROM certificate_request WHERE id=?", (document_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def list(self, owner):
        if owner is None:
            rows = self.connection.execute("SELECT record FROM certificate_request ORDER BY created_at DESC,id DESC")
        else:
            rows = self.connection.execute("SELECT record FROM certificate_request WHERE owner=? ORDER BY created_at DESC,id DESC", (owner,))
        return [json.loads(row[0]) for row in rows]

    def save(self, record):
        self.connection.execute(
            "INSERT INTO certificate_request(id,owner,created_at,record) VALUES(?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET record=excluded.record",
            (record["id"], record["student_user_id"], record["created_at"], encode(record)),
        )

    def replay(self, actor, key):
        row = self.connection.execute("SELECT fingerprint,result FROM certificate_replay WHERE actor=? AND key=?", (actor, key)).fetchone()
        return {"fingerprint": row[0], "result": json.loads(row[1])} if row else None

    def complete(self, actor, key, fingerprint, result):
        self.connection.execute("INSERT INTO certificate_replay VALUES(?,?,?,?)", (actor, key, fingerprint, encode(result)))

    def audit(self, event):
        self.connection.execute("INSERT INTO certificate_audit(id,document_id,event) VALUES(?,?,?)", (event["id"], event["document_id"], encode(event)))


class SQLiteCertificateRepository:
    # Read by presentation instead of an isinstance check on this adapter.
    shares_session_database = True

    def __init__(self, path: Path):
        self.path = workspace_path(path)
        if not self.path.parent.is_dir():
            raise ValueError("create an explicitly owned demo directory first")
        with self.transaction() as tx:
            tx.connection.execute("CREATE TABLE IF NOT EXISTS certificate_schema(version INTEGER PRIMARY KEY)")
            tx.connection.execute("INSERT OR IGNORE INTO certificate_schema VALUES(1)")
            tx.connection.execute("CREATE TABLE IF NOT EXISTS certificate_request(id TEXT PRIMARY KEY,owner TEXT NOT NULL,created_at TEXT NOT NULL,record TEXT NOT NULL)")
            tx.connection.execute("CREATE INDEX IF NOT EXISTS certificate_owner ON certificate_request(owner,created_at,id)")
            tx.connection.execute("CREATE TABLE IF NOT EXISTS certificate_replay(actor TEXT NOT NULL,key TEXT NOT NULL,fingerprint TEXT NOT NULL,result TEXT NOT NULL,PRIMARY KEY(actor,key))")
            tx.connection.execute("CREATE TABLE IF NOT EXISTS certificate_audit(id TEXT PRIMARY KEY,document_id TEXT NOT NULL REFERENCES certificate_request(id),event TEXT NOT NULL)")
            tx.connection.execute("CREATE TABLE IF NOT EXISTS certificate_revocation(key TEXT PRIMARY KEY)")

    @contextmanager
    def transaction(self):
        # Check the destination again before every SQLite open (including journals).
        workspace_path(self.path)
        conn = sqlite3.connect(self.path, timeout=5)
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            with conn:
                conn.execute("BEGIN IMMEDIATE")
                yield SQLiteCertificateTransaction(conn)
        finally:
            conn.close()

    def revoke(self, key):
        with self.transaction() as tx:
            tx.connection.execute("INSERT OR IGNORE INTO certificate_revocation VALUES(?)", (key,))

    def is_revoked(self, key):
        with self.transaction() as tx:
            return tx.connection.execute("SELECT 1 FROM certificate_revocation WHERE key=?", (key,)).fetchone() is not None
