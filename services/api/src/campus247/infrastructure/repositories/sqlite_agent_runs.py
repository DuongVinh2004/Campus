"""Additive run store with compare-and-swap leases and append-only events.

This is an application orchestration store, not a LangGraph checkpointer.
Checkpoint JSON never contains identity grants, credentials or raw model output.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from time import time
from campus247.infrastructure.repositories.sqlite_certificates import workspace_path


from campus247.ports.agent_runs import RunConflict  # noqa: E402 -- re-exported for existing callers


class RunStorageUnavailable(sqlite3.OperationalError):
    pass


class RunStorageCorrupt(RunStorageUnavailable):
    pass


class SQLiteAgentRunStore:
    def __init__(self, path: Path, *, tenant=None):
        root = Path(__file__).resolve().parents[6]
        path = Path(path).absolute()
        if not path.resolve().is_relative_to(root) or path.resolve() == root or path.suffix != ".sqlite3":
            raise ValueError("run database outside workspace")
        for parent in (path, *path.parents):
            if parent.exists() and (parent.is_symlink() or parent.is_junction()
                                    or getattr(parent.stat(), "st_file_attributes", 0) & 0x400):
                raise ValueError("reparse database path denied")
            if parent == root:
                break
        self.path = path.resolve()
        self.tenant = tenant
        with self.connect(initialize=True) as conn:
            conn.execute("BEGIN IMMEDIATE")
            if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='agent_schema'").fetchone():
                if list(conn.execute("SELECT version FROM agent_schema")) != [(1,)]:
                    raise ValueError("unsupported agent schema")
            conn.execute("CREATE TABLE IF NOT EXISTS agent_run (id TEXT PRIMARY KEY, owner TEXT NOT NULL, conversation TEXT NOT NULL, version INTEGER NOT NULL, status TEXT NOT NULL, lease_until REAL NOT NULL, cancel_requested INTEGER NOT NULL DEFAULT 0, record TEXT NOT NULL)")
            conn.execute("CREATE TABLE IF NOT EXISTS agent_event (run_id TEXT NOT NULL REFERENCES agent_run(id), seq INTEGER NOT NULL, record TEXT NOT NULL, PRIMARY KEY(run_id,seq))")
            conn.execute("CREATE TABLE IF NOT EXISTS agent_task (run_id TEXT NOT NULL REFERENCES agent_run(id), id TEXT NOT NULL, version INTEGER NOT NULL, status TEXT NOT NULL, attempt INTEGER NOT NULL, lease_until REAL NOT NULL, record TEXT NOT NULL, PRIMARY KEY(run_id,id))")
            conn.execute("CREATE TABLE IF NOT EXISTS agent_cache (key TEXT PRIMARY KEY, record TEXT NOT NULL)")
            conn.execute("CREATE TABLE IF NOT EXISTS agent_transition_receipt (id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES agent_run(id), version INTEGER NOT NULL, record TEXT NOT NULL)")
            conn.execute("CREATE INDEX IF NOT EXISTS agent_owner_conversation ON agent_run(owner,conversation,id)")
            conn.execute("CREATE TABLE IF NOT EXISTS agent_schema(version INTEGER PRIMARY KEY)")
            conn.execute("INSERT OR IGNORE INTO agent_schema VALUES(1)")
            if tenant is not None:
                from campus247.application.assistance.state_storage import StateScope
                StateScope(tenant,"019a0000-0000-7000-8000-000000000007")
                exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='agent_tenant'").fetchone()
                if not exists and conn.execute("SELECT COUNT(*) FROM agent_run").fetchone()[0]:
                    raise RunStorageCorrupt("LEGACY_RUN_TENANT_UNBOUND")
                conn.execute("CREATE TABLE IF NOT EXISTS agent_tenant(tenant TEXT PRIMARY KEY)")
                bindings = conn.execute("SELECT tenant FROM agent_tenant").fetchall()
                if bindings and bindings != [(tenant,)]:
                    raise RunStorageCorrupt("RUN_TENANT_MISMATCH")
                conn.execute("INSERT OR IGNORE INTO agent_tenant VALUES(?)",(tenant,))
            elif conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='agent_tenant'").fetchone():
                bindings = conn.execute("SELECT tenant FROM agent_tenant").fetchall()
                if len(bindings) != 1:
                    raise RunStorageCorrupt("RUN_TENANT_MISMATCH")
                from campus247.application.assistance.state_storage import StateScope
                StateScope(bindings[0][0],"019a0000-0000-7000-8000-000000000007")
                self.tenant = bindings[0][0]

    @contextmanager
    def connect(self, *, initialize=False):
        workspace_path(self.path)
        conn = None
        try:
            conn = sqlite3.connect(self.path.as_uri()+"?mode="+("rwc" if initialize else "rw"), uri=True, timeout=2)
            conn.execute("PRAGMA foreign_keys=ON")
            if not initialize:
                if conn.execute("SELECT version FROM agent_schema").fetchall() != [(1,)]:
                    raise RunStorageCorrupt("RUN_SCHEMA_UNSUPPORTED")
                if self.tenant is not None and conn.execute("SELECT tenant FROM agent_tenant").fetchall() != [(self.tenant,)]:
                    raise RunStorageCorrupt("RUN_TENANT_MISMATCH")
            with conn:
                yield conn
        except RunStorageCorrupt:
            raise
        except sqlite3.OperationalError:
            raise RunStorageUnavailable("RUN_STORAGE_UNAVAILABLE") from None
        finally:
            if conn is not None:
                conn.close()

    @staticmethod
    def _object(encoded):
        try:
            value = json.loads(encoded)
            if not isinstance(value,dict):
                raise TypeError("object required")
            return value
        except (ValueError,TypeError):
            raise RunStorageCorrupt("RUN_RECORD_INVALID") from None

    @staticmethod
    def _decode(row):
        if row is None:
            return None
        try:
            record = SQLiteAgentRunStore._object(row[6])
            if not isinstance(record,dict) or any(k in record and record[k] != v for k,v in
                {"id":row[0],"owner":row[1],"conversation_id":row[2]}.items()):
                raise ValueError("run binding invalid")
        except (ValueError,TypeError):
            raise RunStorageCorrupt("RUN_RECORD_INVALID") from None
        return {**record, "id": row[0], "owner": row[1], "conversation_id": row[2],
                "version": row[3], "status": row[4], "lease_until": row[5]}

    def get(self, run_id, owner, conversation_id):
        with self.connect() as conn:
            row = conn.execute("SELECT id,owner,conversation,version,status,lease_until,record FROM agent_run WHERE id=? AND owner=? AND conversation=?", (run_id, owner, conversation_id)).fetchone()
            value = self._decode(row)
            if value:
                events = []
                for sequence,encoded in conn.execute("SELECT seq,record FROM agent_event WHERE run_id=? ORDER BY seq",(run_id,)):
                    try:
                        event = json.loads(encoded)
                        if not isinstance(event,dict) or event.get("seq") != sequence:
                            raise ValueError("event sequence invalid")
                        events.append(event)
                    except (ValueError,TypeError):
                        raise RunStorageCorrupt("RUN_EVENT_BINDING_INVALID") from None
                value["events"] = events
            return value

    def owned_resource_run(self, run_id, owner):
        with self.connect() as conn:
            row = conn.execute("SELECT conversation FROM agent_run WHERE id=? AND owner=?", (run_id, owner)).fetchone()
        value = self.get(run_id, owner, row[0]) if row else None
        return value if value and value.get("binding", {}).get("resource") and value.get("request") else None

    def create(self, run_id, owner, conversation_id, record, lease_seconds, *, max_active=None):
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if max_active is not None and conn.execute("SELECT COUNT(*) FROM agent_run WHERE status='running' AND lease_until>?", (time(),)).fetchone()[0] >= max_active:
                raise RunConflict("RUN_CAPACITY_EXHAUSTED")
            try:
                conn.execute("INSERT INTO agent_run (id,owner,conversation,version,status,lease_until,record) VALUES (?,?,?,1,'running',?,?)",
                             (run_id, owner, conversation_id, time()+lease_seconds,
                              json.dumps(record, ensure_ascii=False)))
            except sqlite3.IntegrityError:
                raise RunConflict("run already exists") from None
        return 1

    def save(self, run_id, owner, conversation_id, version, status, record, event=None, receipt=None):
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            updated = conn.execute("UPDATE agent_run SET version=version+1,status=?,record=? WHERE id=? AND owner=? AND conversation=? AND version=?",
                                   (status, json.dumps(record, ensure_ascii=False), run_id, owner, conversation_id, version))
            if updated.rowcount != 1:
                raise RunConflict("stale run version")
            if receipt is not None:
                if receipt["run_id"] != run_id or receipt["version"] != version + 1 or receipt["state"] != status:
                    raise ValueError("receipt transition binding invalid")
                conn.execute("INSERT INTO agent_transition_receipt VALUES(?,?,?,?)",
                             (receipt["id"], run_id, version + 1, json.dumps(receipt)))
            if event:
                seq = conn.execute("SELECT COALESCE(MAX(seq),0)+1 FROM agent_event WHERE run_id=?", (run_id,)).fetchone()[0]
                conn.execute("INSERT INTO agent_event VALUES (?,?,?)", (run_id, seq, json.dumps({**event, "seq": seq}, ensure_ascii=False)))
        return version + 1

    def claim_resume(self, run_id, owner, conversation_id, version, lease_seconds, *, max_active=None):
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if max_active is not None and conn.execute("SELECT COUNT(*) FROM agent_run WHERE status='running' AND lease_until>? AND id!=?", (time(), run_id)).fetchone()[0] >= max_active:
                raise RunConflict("RUN_CAPACITY_EXHAUSTED")
            changed = conn.execute("UPDATE agent_run SET version=version+1,status='running',lease_until=? WHERE id=? AND owner=? AND conversation=? AND version=? AND cancel_requested=0 AND (status='waiting_user' OR (status='running' AND lease_until<?))",
                                   (time()+lease_seconds, run_id, owner, conversation_id, version, time()))
            if changed.rowcount != 1:
                raise RunConflict("run cannot resume")
        return version + 1

    def transition_receipt(self, run_id, owner, conversation_id, receipt_id):
        with self.connect() as conn:
            row = conn.execute("SELECT r.record FROM agent_transition_receipt r JOIN agent_run a ON a.id=r.run_id WHERE r.id=? AND r.run_id=? AND a.owner=? AND a.conversation=?",
                               (receipt_id, run_id, owner, conversation_id)).fetchone()
            return self._object(row[0]) if row else None

    def cancelled(self, run_id):
        with self.connect() as conn:
            row = conn.execute("SELECT cancel_requested FROM agent_run WHERE id=?", (run_id,)).fetchone()
            return bool(row and row[0])

    def cancel(self, run_id, owner, conversation_id, version):
        with self.connect() as conn:
            changed = conn.execute("UPDATE agent_run SET cancel_requested=1 WHERE id=? AND owner=? AND conversation=? AND version=? AND status IN ('running','waiting_user')",
                                   (run_id, owner, conversation_id, version))
            if changed.rowcount != 1:
                raise RunConflict("run cannot cancel")
        return version

    def tasks(self, run_id):
        with self.connect() as conn:
            return [{**self._task_record(row[5],row[0]), "id": row[0], "version": row[1], "status": row[2],
                     "attempt": row[3], "lease_until": row[4]} for row in conn.execute(
                         "SELECT id,version,status,attempt,lease_until,record FROM agent_task WHERE run_id=? ORDER BY id", (run_id,))]

    @classmethod
    def _task_record(cls, encoded, task_id):
        value = cls._object(encoded)
        for field,key in (("spec","id"),("result","task_id")):
            if field in value and (not isinstance(value[field],dict) or value[field].get(key) != task_id):
                raise RunStorageCorrupt("RUN_TASK_BINDING_INVALID")
        return value

    def add_tasks(self, run_id, tasks):
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            for task in tasks:
                try:
                    conn.execute("INSERT INTO agent_task VALUES (?,?,1,'pending',0,0,?)",
                                 (run_id, task.id, json.dumps({"spec": task.model_dump()}, ensure_ascii=False)))
                except sqlite3.IntegrityError:
                    raise RunConflict("task already exists") from None

    def claim_task(self, run_id, task_id, version, *, lease_seconds, max_attempts):
        with self.connect() as conn:
            changed = conn.execute("UPDATE agent_task SET version=version+1,status='running',attempt=attempt+1,lease_until=? WHERE run_id=? AND id=? AND version=? AND attempt<? AND (status='pending' OR (status='running' AND lease_until<?))",
                                   (time()+lease_seconds, run_id, task_id, version, max_attempts, time()))
            if changed.rowcount != 1:
                raise RunConflict("task lease unavailable")
        return version + 1

    def finish_task(self, run_id, task_id, version, result):
        with self.connect() as conn:
            row = conn.execute("SELECT record FROM agent_task WHERE run_id=? AND id=? AND version=? AND status='running'",
                               (run_id, task_id, version)).fetchone()
            if not row:
                raise RunConflict("stale task result")
            if result.task_id != task_id:
                raise ValueError("result must match the claimed task")
            record = {**self._task_record(row[0],task_id), "result": result.model_dump()}
            changed = conn.execute("UPDATE agent_task SET version=version+1,status=?,record=? WHERE run_id=? AND id=? AND version=? AND status='running'",
                                   (result.status, json.dumps(record, ensure_ascii=False), run_id, task_id, version))
            if changed.rowcount != 1:
                raise RunConflict("stale task result")
        return version + 1

    def cache_get(self, key):
        with self.connect() as conn:
            row = conn.execute("SELECT record FROM agent_cache WHERE key=?", (key,)).fetchone()
            return self._object(row[0]) if row else None

    def cache_put(self, key, result):
        with self.connect() as conn:
            conn.execute("INSERT OR IGNORE INTO agent_cache VALUES (?,?)", (key, json.dumps(result, ensure_ascii=False)))

    def close_pending_tasks(self, run_id, reason):
        from campus247.application.multi_agent.contracts import TaskResult
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            rows = conn.execute("SELECT id,version,record FROM agent_task WHERE run_id=? AND status='pending'", (run_id,)).fetchall()
            for task_id, version, encoded in rows:
                result = TaskResult(task_id=task_id, status="cancelled", error_code=reason)
                record = {**self._task_record(encoded,task_id), "result": result.model_dump()}
                conn.execute("UPDATE agent_task SET version=version+1,status='cancelled',record=? WHERE run_id=? AND id=? AND version=? AND status='pending'",
                             (json.dumps(record, ensure_ascii=False), run_id, task_id, version))
