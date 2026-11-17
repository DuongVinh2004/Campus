"""Durable metadata outbox mirror, bounded jobs and idempotent local inbox."""
import json
from datetime import datetime, timezone

from campus247.application.assistance.state_storage import digest, StorageConflict, StorageCorrupt
from campus247.infrastructure.repositories.sqlite_assistant_memory import SQLiteAssistantMemory


class SQLiteAssistantTracking(SQLiteAssistantMemory):
    def __init__(self, path, *, initialize=False):
        super().__init__(path, initialize=initialize)
        if initialize:
            with self.transaction() as connection:
                connection.execute('CREATE TABLE tracking_event(event_id TEXT PRIMARY KEY,body TEXT NOT NULL,sha256 TEXT NOT NULL)')
                connection.execute('CREATE TABLE tracking_job(subscription_id TEXT,event_id TEXT,tenant TEXT,owner TEXT,state TEXT NOT NULL,attempts INTEGER NOT NULL DEFAULT 0,next_at TEXT NOT NULL,last_code TEXT,PRIMARY KEY(subscription_id,event_id))')
                connection.execute('CREATE TABLE tracking_inbox(tenant TEXT,owner TEXT,notification_id TEXT,subscription_id TEXT,event_id TEXT,content_sha256 TEXT,body TEXT,sha256 TEXT,PRIMARY KEY(tenant,owner,notification_id))')
                connection.execute('CREATE INDEX tracking_inbox_dedup ON tracking_inbox(tenant,owner,subscription_id,content_sha256)')

    def ingest(self, event):
        body = event.model_dump(mode='json')
        with self.transaction() as connection:
            row = connection.execute('SELECT body,sha256 FROM tracking_event WHERE event_id=?', (event.event_id,)).fetchone()
            if row:
                if digest(json.loads(row[0])) != row[1] or row[1] != digest(body):
                    raise StorageConflict('TRACKING_EVENT_ID_CONFLICT')
                return False
            connection.execute('INSERT INTO tracking_event VALUES(?,?,?)', (event.event_id, json.dumps(body), digest(body)))
            return True

    def events(self, *, limit=20):
        with self.transaction() as connection:
            rows = connection.execute('SELECT body,sha256 FROM tracking_event ORDER BY event_id LIMIT ?', (limit,)).fetchall()
            result = []
            for body, checksum in rows:
                value = json.loads(body)
                if digest(value) != checksum:
                    raise StorageCorrupt('TRACKING_EVENT_CORRUPT')
                result.append(value)
            return result

    def subscriptions_for(self, event, *, limit=51):
        from campus247.application.assistance.state_storage import StateScope
        return self.page(StateScope(event.tenant, event.recipient_id), 'tracking', limit=limit)

    def schedule(self, scope, subscription_id, event):
        with self.transaction() as connection:
            connection.execute('INSERT OR IGNORE INTO tracking_job(subscription_id,event_id,tenant,owner,state,next_at) VALUES(?,?,?,?,?,?)',
                (subscription_id, event.event_id, scope.tenant, scope.owner, 'pending', datetime.fromisoformat(event.changed_at).astimezone(timezone.utc).isoformat()))

    def jobs(self, now, *, limit=20):
        with self.transaction() as connection:
            connection.row_factory = __import__('sqlite3').Row
            return [dict(row) for row in connection.execute("SELECT * FROM tracking_job WHERE state IN ('pending','retry','quiet') AND next_at<=? ORDER BY event_id,subscription_id LIMIT ?", (now.astimezone(timezone.utc).isoformat(), limit))]

    def event(self, event_id, connection):
        row = connection.execute('SELECT body,sha256 FROM tracking_event WHERE event_id=?', (event_id,)).fetchone()
        if row is None or digest(json.loads(row[0])) != row[1]:
            raise StorageCorrupt('TRACKING_EVENT_CORRUPT')
        return json.loads(row[0])

    def finish(self, connection, job, state, *, code=None, next_at=None, attempt=False):
        connection.execute('UPDATE tracking_job SET state=?,last_code=?,next_at=?,attempts=attempts+? WHERE subscription_id=? AND event_id=?',
            (state, code, (next_at or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat(), int(attempt), job['subscription_id'], job['event_id']))

    def inbox(self, scope, *, after='', limit=20):
        if not 1 <= limit <= 50:
            raise ValueError('bounded inbox required')
        with self.transaction() as connection:
            rows = connection.execute('SELECT body,sha256 FROM tracking_inbox WHERE tenant=? AND owner=? AND notification_id>? ORDER BY notification_id LIMIT ?', (scope.tenant, scope.owner, after, limit)).fetchall()
            items = []
            for body, checksum in rows:
                value = json.loads(body)
                if digest(value) != checksum or (value['tenant'], value['owner']) != (scope.tenant, scope.owner):
                    raise StorageCorrupt('TRACKING_INBOX_CORRUPT')
                items.append(value)
            return items
