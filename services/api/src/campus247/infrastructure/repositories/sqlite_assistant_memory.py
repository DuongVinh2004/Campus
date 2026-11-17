"""Separate append-only personal state. Never opens legacy/retained stores implicitly."""
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3

from campus247.application.assistance.state_storage import digest, StorageConflict, StorageCorrupt
from campus247.infrastructure.repositories.sqlite_certificates import workspace_path


class SQLiteAssistantMemory:
    def __init__(self, path, *, initialize=False):
        self.path = workspace_path(Path(path))
        if initialize:
            # Composition must explicitly choose a new fixture/store. No auto migration.
            with self.path.open('xb'):
                pass
            with self.transaction() as connection:
                connection.execute('CREATE TABLE personal_revision(tenant TEXT,owner TEXT,namespace TEXT,key TEXT,version INTEGER,body TEXT,sha256 TEXT,PRIMARY KEY(tenant,owner,namespace,key,version))')
                connection.execute('CREATE TABLE personal_receipt(tenant TEXT,owner TEXT,client_id TEXT,body TEXT,sha256 TEXT,PRIMARY KEY(tenant,owner,client_id))')

    @contextmanager
    def transaction(self):
        workspace_path(self.path)
        connection = sqlite3.connect(self.path.as_uri() + '?mode=rw', uri=True, timeout=2)
        try:
            connection.execute('BEGIN IMMEDIATE')
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def decode(row, scope, namespace, key):
        if row is None:
            return None
        version, body, checksum = row
        try:
            value = json.loads(body)
            if digest(value) != checksum or value['version'] != version or (value['tenant'], value['owner'], value['namespace'], value['key']) != (scope.tenant, scope.owner, namespace, key):
                raise ValueError('binding')
            return value
        except (ValueError, KeyError, TypeError):
            raise StorageCorrupt('PERSONAL_STATE_CORRUPT') from None

    def get(self, scope, namespace, key, connection=None):
        if connection is None:
            with self.transaction() as connection:
                return self.get(scope, namespace, key, connection)
        row = connection.execute('SELECT version,body,sha256 FROM personal_revision WHERE tenant=? AND owner=? AND namespace=? AND key=? ORDER BY version DESC LIMIT 1', (scope.tenant, scope.owner, namespace, key)).fetchone()
        return self.decode(row, scope, namespace, key)

    def page(self, scope, namespace, *, after='', limit=100, connection=None):
        if not 1 <= limit <= 101:
            raise ValueError('bounded page required')
        if connection is None:
            with self.transaction() as connection:
                return self.page(scope, namespace, after=after, limit=limit, connection=connection)
        keys = connection.execute('SELECT DISTINCT key FROM personal_revision WHERE tenant=? AND owner=? AND namespace=? AND key>? ORDER BY key LIMIT ?', (scope.tenant, scope.owner, namespace, after, limit)).fetchall()
        return [self.get(scope, namespace, row[0], connection) for row in keys]

    def receipt(self, scope, client_id, connection=None):
        if connection is None:
            with self.transaction() as connection:
                return self.receipt(scope, client_id, connection)
        row = connection.execute('SELECT body,sha256 FROM personal_receipt WHERE tenant=? AND owner=? AND client_id=?', (scope.tenant, scope.owner, client_id)).fetchone()
        if row is None:
            return None
        value = json.loads(row[0])
        if digest(value) != row[1] or (value['tenant'], value['owner'], value['client_id']) != (scope.tenant, scope.owner, client_id):
            raise StorageCorrupt('PERSONAL_RECEIPT_CORRUPT')
        return value

    def commit(self, scope, namespace, key, expected, payload, client_id, *, guard):
        with self.transaction() as connection:
            current = self.get(scope, namespace, key, connection)
            # Reauthorization also runs on an idempotent replay.
            guard(connection, current)
            intent = digest({'namespace': namespace, 'key': key, 'expected': expected, 'payload': payload})
            old = self.receipt(scope, client_id, connection)
            if old:
                if old['intent'] != intent:
                    raise StorageConflict('PERSONAL_IDEMPOTENCY_CONFLICT')
                return {**old, 'is_replay': True}
            version = current['version'] if current else 0
            if version != expected:
                raise StorageConflict('PERSONAL_STALE_VERSION')
            now = datetime.now(timezone.utc).isoformat()
            body = {'tenant': scope.tenant, 'owner': scope.owner, 'namespace': namespace, 'key': key,
                    'version': version + 1, 'updated_at': now, 'payload': payload}
            connection.execute('INSERT INTO personal_revision VALUES(?,?,?,?,?,?,?)', (scope.tenant, scope.owner, namespace, key, version+1, json.dumps(body, ensure_ascii=False), digest(body)))
            receipt = {'tenant': scope.tenant, 'owner': scope.owner, 'namespace': namespace, 'key': key,
                       'version': version+1, 'client_id': client_id, 'intent': intent, 'committed_at': now, 'state': 'committed', 'is_replay': False}
            connection.execute('INSERT INTO personal_receipt VALUES(?,?,?,?,?)', (scope.tenant, scope.owner, client_id, json.dumps(receipt), digest(receipt)))
            return receipt
