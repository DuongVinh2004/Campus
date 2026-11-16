"""Additive types in the same DB/transaction port; old runtime cannot read them."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager

from campus247.infrastructure.repositories.sqlite_certificates import (
    SQLiteCertificateRepository,
    SQLiteCertificateTransaction,
    encode,
    workspace_path,
)


class OperationsTransaction(SQLiteCertificateTransaction):
    def get(self, document_id):
        row = self.connection.execute("SELECT record FROM service_request WHERE id=?", (document_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def list(self, owner):
        if owner is None:
            rows = self.connection.execute("SELECT record FROM service_request ORDER BY created_at DESC,id DESC")
        else:
            rows = self.connection.execute("SELECT record FROM service_request WHERE owner=? ORDER BY created_at DESC,id DESC", (owner,))
        return [json.loads(row[0]) for row in rows]

    def save(self, record):
        self.connection.execute("INSERT INTO service_request(id,owner,created_at,record) VALUES(?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET record=excluded.record",
            (record["id"], record["student_user_id"], record["created_at"], encode(record)))

    def audit(self, event):
        self.connection.execute("INSERT INTO service_request_audit VALUES(?,?,?)", (event["id"], event["document_id"], encode(event)))

    def item(self, kind, identifier):
        row = self.connection.execute("SELECT record FROM service_operations_record WHERE kind=? AND id=?", (kind, identifier)).fetchone()
        return json.loads(row[0]) if row else None

    def items(self, kind):
        return [json.loads(r[0]) for r in self.connection.execute(
            "SELECT record FROM service_operations_record WHERE kind=? ORDER BY id", (kind,))]

    def insert(self, kind, value):
        self.connection.execute("INSERT INTO service_operations_record VALUES(?,?,?)", (kind, value["id"], encode(value)))

    def update(self, kind, value):
        result = self.connection.execute("UPDATE service_operations_record SET record=? WHERE kind=? AND id=?",
                                         (encode(value), kind, value["id"]))
        if result.rowcount != 1:
            raise ValueError("missing operations record")

    def operation_audit(self, event):
        self.insert("audit", event)


class SQLiteServiceOperationsRepository(SQLiteCertificateRepository):
    def __init__(self, path):
        super().__init__(path)
        with self.transaction() as tx:
            tx.connection.execute("CREATE TABLE IF NOT EXISTS service_operations_record(kind TEXT NOT NULL,id TEXT NOT NULL,record TEXT NOT NULL,PRIMARY KEY(kind,id))")
            tx.connection.execute("CREATE TABLE IF NOT EXISTS service_request(id TEXT PRIMARY KEY,owner TEXT NOT NULL,created_at TEXT NOT NULL,record TEXT NOT NULL)")
            tx.connection.execute("CREATE INDEX IF NOT EXISTS service_request_owner ON service_request(owner,created_at,id)")
            tx.connection.execute("CREATE TABLE IF NOT EXISTS service_request_audit(id TEXT PRIMARY KEY,document_id TEXT NOT NULL REFERENCES service_request(id),event TEXT NOT NULL)")
            tx.connection.execute("INSERT OR IGNORE INTO certificate_schema VALUES(2)")

    @contextmanager
    def transaction(self):
        workspace_path(self.path)
        connection = sqlite3.connect(self.path, timeout=5)
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            with connection:
                connection.execute("BEGIN IMMEDIATE")
                yield OperationsTransaction(connection)
        finally:
            connection.close()
