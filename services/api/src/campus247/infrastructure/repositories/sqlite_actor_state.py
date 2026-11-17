"""Additive actor state, immutable revisions and receipts in one transaction.

No delete API, in-memory fallback, grants activation or product execution.
Each open rechecks the canonical workspace path. Normal opens require the
existing database, so a missing file cannot silently become an empty store.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import sqlite3

from campus247.application.assistance.state_storage import (
    StateScope, StoredState, StateReceipt, StorageConflict, StorageUnavailable, StorageCorrupt,
    digest, identity_key, payload_for, PAYLOAD_MODELS,
)
from campus247.domain.shared.values import generate_uuid7
from campus247.infrastructure.repositories.sqlite_certificates import workspace_path, encode
from campus247.infrastructure.repositories.sqlite_reuse import ReusableConnections


class SQLiteActorStateStore:
    schema_version = 1

    def __init__(self, path):
        self._connections = ReusableConnections()
        self.path = workspace_path(path)
        if self.path.suffix != ".sqlite3" or not self.path.parent.is_dir():
            raise ValueError("explicit existing workspace directory and SQLite filename required")
        with self.connect(initialize=True) as connection:
            connection.execute("BEGIN IMMEDIATE")
            if connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='unified_state_schema'").fetchone():
                versions = [r[0] for r in connection.execute("SELECT version FROM unified_state_schema")]
                if versions != [self.schema_version]:
                    raise StorageCorrupt("STATE_SCHEMA_UNSUPPORTED")
            connection.execute("CREATE TABLE IF NOT EXISTS unified_state_schema(version INTEGER PRIMARY KEY)")
            connection.execute("CREATE TABLE IF NOT EXISTS unified_actor_state(tenant TEXT NOT NULL,owner TEXT NOT NULL,namespace TEXT NOT NULL,key TEXT NOT NULL,version INTEGER NOT NULL CHECK(version>=1),record TEXT NOT NULL,PRIMARY KEY(tenant,owner,namespace,key))")
            connection.execute("CREATE TABLE IF NOT EXISTS unified_state_revision(tenant TEXT NOT NULL,owner TEXT NOT NULL,namespace TEXT NOT NULL,key TEXT NOT NULL,version INTEGER NOT NULL,event_id TEXT NOT NULL UNIQUE,record TEXT NOT NULL,PRIMARY KEY(tenant,owner,namespace,key,version),FOREIGN KEY(tenant,owner,namespace,key) REFERENCES unified_actor_state(tenant,owner,namespace,key))")
            connection.execute("CREATE TABLE IF NOT EXISTS unified_state_receipt(tenant TEXT NOT NULL,owner TEXT NOT NULL,client_id TEXT NOT NULL,fingerprint TEXT NOT NULL,record TEXT NOT NULL,PRIMARY KEY(tenant,owner,client_id))")
            connection.execute("INSERT OR IGNORE INTO unified_state_schema VALUES(?)", (self.schema_version,))

    def _open(self, initialize):
        """A checked connection: workspace path guard, pragmas and (unless initializing) the schema check."""
        workspace_path(self.path)
        connection = sqlite3.connect(self.path.as_uri()+"?mode="+("rwc" if initialize else "rw"), uri=True, timeout=2)
        try:
            connection.execute("PRAGMA foreign_keys=ON")
            if not initialize and connection.execute("SELECT version FROM unified_state_schema").fetchall() != [(self.schema_version,)]:
                raise StorageCorrupt("STATE_SCHEMA_UNSUPPORTED")
        except BaseException:
            connection.close()
            raise
        return connection

    @contextmanager
    def connect(self, *, initialize=False):
        connection, temporary, sql_failed = None, True, False
        try:
            if initialize:
                connection = self._open(True)
            else:
                connection, temporary = self._connections.checkout(lambda: self._open(False))
            with connection:
                yield connection
        except sqlite3.Error:
            sql_failed = True
            raise StorageUnavailable("STATE_STORAGE_UNAVAILABLE") from None
        finally:
            if connection is not None:
                if initialize:
                    connection.close()
                else:
                    self._connections.release(connection, temporary, sql_failed)

    @staticmethod
    def _scope(scope):
        if not isinstance(scope, StateScope):
            raise ValueError("server-bound scope required")
        return scope.tenant, scope.owner

    @staticmethod
    def _decode(row, scope, namespace, key):
        if row is None:
            return None
        try:
            value = StoredState.model_validate_json(row[1])
            if (value.tenant, value.owner, value.namespace, value.key, value.version) != (scope.tenant, scope.owner, namespace, key, row[0]):
                raise ValueError("state column binding mismatch")
            return value
        except (ValueError, TypeError):
            raise StorageCorrupt("STATE_BINDING_INVALID") from None

    def get(self, scope, namespace, key):
        tenant, owner = self._scope(scope)
        payload_for_namespace = namespace in PAYLOAD_MODELS
        if not payload_for_namespace:
            raise ValueError("unknown state namespace")
        identity_key(key)
        with self.connect() as connection:
            row = connection.execute("SELECT version,record FROM unified_actor_state WHERE tenant=? AND owner=? AND namespace=? AND key=?",
                                     (tenant,owner,namespace,key)).fetchone()
            value = self._decode(row,scope,namespace,key)
            if value is not None:
                self._verify_revision(connection, scope, namespace, key, value)
            return value

    def _verify_revision(self, connection, scope, namespace, key, value):
        revision = connection.execute("SELECT version,record,event_id FROM unified_state_revision WHERE tenant=? AND owner=? AND namespace=? AND key=? AND version=?",
            (scope.tenant,scope.owner,namespace,key,value.version)).fetchone()
        if revision is None or self._decode(revision[:2],scope,namespace,key) != value:
            raise StorageCorrupt("STATE_CURRENT_REVISION_MISMATCH")
        rows = connection.execute("SELECT client_id,fingerprint,record FROM unified_state_receipt WHERE tenant=? AND owner=? AND json_extract(record,'$.receipt_id')=?",
            (scope.tenant,scope.owner,revision[2])).fetchall()
        try:
            if len(rows) != 1:
                raise ValueError("one matching commit receipt required")
            client_id, fingerprint, encoded = rows[0]
            receipt = StateReceipt.model_validate_json(encoded)
            expected = digest({"tenant":scope.tenant,"owner":scope.owner,"namespace":namespace,"key":key,
                "expected_version":value.version-1,"payload_sha256":value.sha256})
            if (receipt.tenant,receipt.owner,receipt.namespace,receipt.key,receipt.version,
                    receipt.receipt_id,receipt.client_id,receipt.fingerprint,receipt.payload_sha256,receipt.committed_at) != (
                    scope.tenant,scope.owner,namespace,key,value.version,revision[2],client_id,expected,value.sha256,value.committed_at
                    ) or fingerprint != expected or receipt.is_replay:
                raise ValueError("commit receipt binding invalid")
        except (ValueError, TypeError):
            raise StorageCorrupt("STATE_REVISION_RECEIPT_MISMATCH") from None

    def check_available(self):
        with self.connect() as connection:
            if connection.execute("SELECT version FROM unified_state_schema").fetchall() != [(self.schema_version,)]:
                raise StorageCorrupt("STATE_SCHEMA_UNSUPPORTED")
            for table in ("unified_actor_state","unified_state_revision","unified_state_receipt"):
                connection.execute("SELECT 1 FROM "+table+" LIMIT 1").fetchone()

    def commit(self, scope, namespace, key, expected_version, payload, client_id, *, guard=None):
        tenant, owner = self._scope(scope)
        identity_key(key); identity_key(client_id)
        if len(client_id) < 8 or type(expected_version) is not int or expected_version < 0:
            raise ValueError("stable client ID and explicit nonnegative version required")
        value = payload_for(namespace,payload)
        sha = digest(value)
        fingerprint = digest({"tenant":tenant,"owner":owner,"namespace":namespace,"key":key,
                              "expected_version":expected_version,"payload_sha256":sha})
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if guard is not None:
                # Runs under the same write lock for first commit and replay.
                # Consumers can recheck revocation/use state without a CAS gap.
                guard(connection)
            old_receipt = connection.execute("SELECT fingerprint,record FROM unified_state_receipt WHERE tenant=? AND owner=? AND client_id=?",
                                             (tenant,owner,client_id)).fetchone()
            if old_receipt:
                try:
                    receipt = StateReceipt.model_validate_json(old_receipt[1])
                    if (receipt.tenant,receipt.owner,receipt.client_id,receipt.fingerprint) != (tenant,owner,client_id,old_receipt[0]):
                        raise ValueError("receipt column binding mismatch")
                    if receipt.is_replay:
                        raise ValueError("stored receipt is not original")
                    if old_receipt[0] != fingerprint:
                        raise StorageConflict("STATE_IDEMPOTENCY_CONFLICT")
                    if (receipt.namespace,receipt.key,receipt.version,receipt.payload_sha256) != (namespace,key,expected_version+1,sha):
                        raise ValueError("receipt target mismatch")
                    revision = connection.execute("SELECT version,record,event_id FROM unified_state_revision WHERE tenant=? AND owner=? AND namespace=? AND key=? AND version=?",
                        (tenant,owner,namespace,key,receipt.version)).fetchone()
                    if not revision or revision[2] != receipt.receipt_id:
                        raise ValueError("receipt audit revision missing")
                    committed = self._decode(revision[:2],scope,namespace,key)
                    if committed.sha256 != sha or committed.committed_at != receipt.committed_at:
                        raise ValueError("receipt audit binding mismatch")
                    return receipt.model_copy(update={"is_replay":True})
                except StorageConflict:
                    raise
                except (ValueError,TypeError):
                    raise StorageCorrupt("STATE_RECEIPT_INVALID") from None
            row = connection.execute("SELECT version,record FROM unified_actor_state WHERE tenant=? AND owner=? AND namespace=? AND key=?",
                                     (tenant,owner,namespace,key)).fetchone()
            previous = self._decode(row,scope,namespace,key)
            if previous is not None:
                self._verify_revision(connection,scope,namespace,key,previous)
            if (previous.version if previous else 0) != expected_version:
                raise StorageConflict("STATE_STALE_VERSION")
            at = datetime.now(timezone.utc).isoformat()
            record = StoredState(tenant=tenant,owner=owner,namespace=namespace,key=key,version=expected_version+1,
                                 payload=value,sha256=sha,committed_at=at)
            receipt = StateReceipt(receipt_id=generate_uuid7(),tenant=tenant,owner=owner,client_id=client_id,
                namespace=namespace,key=key,version=record.version,payload_sha256=sha,fingerprint=fingerprint,committed_at=at)
            encoded = encode(record.model_dump(mode="json"))
            if previous:
                changed = connection.execute("UPDATE unified_actor_state SET version=?,record=? WHERE tenant=? AND owner=? AND namespace=? AND key=? AND version=?",
                    (record.version,encoded,tenant,owner,namespace,key,expected_version))
                if changed.rowcount != 1:
                    raise StorageConflict("STATE_STALE_VERSION")
            else:
                connection.execute("INSERT INTO unified_actor_state VALUES(?,?,?,?,?,?)",(tenant,owner,namespace,key,record.version,encoded))
            connection.execute("INSERT INTO unified_state_revision VALUES(?,?,?,?,?,?,?)",
                (tenant,owner,namespace,key,record.version,receipt.receipt_id,encoded))
            connection.execute("INSERT INTO unified_state_receipt VALUES(?,?,?,?,?)",
                (tenant,owner,client_id,fingerprint,encode(receipt.model_dump(mode="json"))))
        return receipt

    def receipt(self, scope, client_id):
        tenant, owner = self._scope(scope)
        identity_key(client_id)
        with self.connect() as connection:
            row = connection.execute("SELECT record FROM unified_state_receipt WHERE tenant=? AND owner=? AND client_id=?",
                                     (tenant, owner, client_id)).fetchone()
            if row is None:
                return None
            try:
                receipt = StateReceipt.model_validate_json(row[0])
                if (receipt.tenant, receipt.owner, receipt.client_id, receipt.is_replay) != (tenant, owner, client_id, False):
                    raise ValueError("receipt scope invalid")
                revision = connection.execute("SELECT version,record,event_id FROM unified_state_revision WHERE tenant=? AND owner=? AND namespace=? AND key=? AND version=?",
                    (tenant, owner, receipt.namespace, receipt.key, receipt.version)).fetchone()
                value = self._decode(revision[:2], scope, receipt.namespace, receipt.key) if revision else None
                if value is None:
                    raise ValueError("missing receipt revision")
                if (receipt.receipt_id, receipt.payload_sha256, receipt.committed_at) != (revision[2], value.sha256, value.committed_at):
                    raise ValueError("receipt revision binding invalid")
                self._verify_revision(connection, scope, receipt.namespace, receipt.key, value)
                return receipt
            except (ValueError, TypeError):
                raise StorageCorrupt("STATE_RECEIPT_INVALID") from None

    def list_current(self, scope, namespace, *, after_key="", limit=50):
        """Bounded actor-owned management page, including immutable integrity."""
        if type(limit) is not int or not 1 <= limit <= 100 or namespace not in PAYLOAD_MODELS:
            raise ValueError("bounded known namespace required")
        if after_key:
            identity_key(after_key)
        with self.connect() as conn:
            rows = conn.execute("SELECT key,version,record FROM unified_actor_state WHERE tenant=? AND owner=? AND namespace=? AND key>? ORDER BY key LIMIT ?",
                                (scope.tenant, scope.owner, namespace, after_key, limit)).fetchall()
            result = []
            for key, version, record in rows:
                value = self._decode((version, record), scope, namespace, key)
                self._verify_revision(conn, scope, namespace, key, value)
                result.append(value)
            return result

    def history(self, scope, namespace, key, *, after_version=0, limit=50):
        tenant, owner = self._scope(scope)
        identity_key(key)
        if namespace not in PAYLOAD_MODELS:
            raise ValueError("unknown state namespace")
        if type(after_version) is not int or after_version < 0 or type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("bounded revision page required")
        with self.connect() as connection:
            rows = connection.execute("SELECT version,record FROM unified_state_revision WHERE tenant=? AND owner=? AND namespace=? AND key=? AND version>? ORDER BY version LIMIT ?",
                                      (tenant,owner,namespace,key,after_version,limit)).fetchall()
            result = [self._decode(row,scope,namespace,key) for row in rows]
            for value in result:
                self._verify_revision(connection,scope,namespace,key,value)
            return result
