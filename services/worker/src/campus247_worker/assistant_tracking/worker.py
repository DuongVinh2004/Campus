"""Bounded durable local inbox consumer; all effects are under a DB transaction."""
from datetime import datetime, timezone, timedelta
import json

from campus247.application.assistance.state_storage import StateScope, digest
from campus247.application.document_request.certificates import CertificateError
from campus247.domain.assistant_tracking import BusinessTrackingEvent, SubscriptionSpec


class AssistantTrackingWorker:
    def __init__(self, service):
        self.service, self.store = service, service.store

    @staticmethod
    def quiet_until(spec, now):
        if spec.quiet_start_hour == spec.quiet_end_hour:
            return None
        local = now + timedelta(minutes=spec.utc_offset_minutes)
        start, end, hour = spec.quiet_start_hour, spec.quiet_end_hour, local.hour
        quiet = start <= hour < end if start < end else hour >= start or hour < end
        if not quiet:
            return None
        target = local.replace(hour=end, minute=0, second=0, microsecond=0)
        if target <= local:
            target += timedelta(days=1)
        return target - timedelta(minutes=spec.utc_offset_minutes)

    def tick(self, *, now=None):
        self.service.available()
        now = now or datetime.now(timezone.utc)
        counters = {'ingested': 0, 'delivered': 0, 'suppressed': 0, 'retry': 0, 'quiet': 0}
        events = self.service.source.read_batch(limit=20)
        if len(events) > 20:
            raise ValueError('source violated batch bound')
        for raw in events:
            event = BusinessTrackingEvent.model_validate(raw)
            counters['ingested'] += int(self.store.ingest(event))
            self.schedule(event)
            # Ack follows both durable ingest and scheduling. A crash anywhere
            # before ack replays the source row and repairs missing jobs.
            self.service.source.ack(event.event_id)
        for job in self.store.jobs(now, limit=20):
            with self.store.transaction() as connection:
                # Claim and commit share the same transaction; concurrent workers
                # recheck terminal state after obtaining SQLite's write lock.
                actual = connection.execute('SELECT state FROM tracking_job WHERE subscription_id=? AND event_id=?', (job['subscription_id'], job['event_id'])).fetchone()
                if actual[0] not in {'pending', 'retry', 'quiet'}:
                    continue
                event = BusinessTrackingEvent.model_validate(self.store.event(job['event_id'], connection))
                scope = StateScope(job['tenant'], job['owner'])
                subscription = self.store.get(scope, 'tracking', job['subscription_id'], connection)
                try:
                    if subscription is None:
                        raise CertificateError(403, 'SUBSCRIPTION_MISSING', 'Đăng ký không còn hiệu lực')
                    payload = subscription['payload']
                    actor = self.service.resolve_recipient(scope.tenant, scope.owner, payload['session_id'])
                    value = self.service.projection(actor, subscription, event)
                    quiet = self.quiet_until(SubscriptionSpec.model_validate(payload['spec']), now)
                    if quiet:
                        self.store.finish(connection, job, 'quiet', code='QUIET_HOURS', next_at=quiet)
                        counters['quiet'] += 1
                        continue
                    # Source content/version is part of dedup. Repeated event IDs
                    # and different IDs with no business change cannot spam.
                    content_hash = digest({'resource': value.resource.model_dump(), 'source': value.source_sha256, 'trigger': event.trigger})
                    old = connection.execute('SELECT 1 FROM tracking_inbox WHERE tenant=? AND owner=? AND subscription_id=? AND content_sha256=?', (scope.tenant, scope.owner, subscription['key'], content_hash)).fetchone()
                    if old:
                        self.store.finish(connection, job, 'no_change', code='NO_CHANGE')
                        counters['suppressed'] += 1
                        continue
                    # Final check occurs immediately before local insert.
                    actor = self.service.resolve_recipient(scope.tenant, scope.owner, payload['session_id'])
                    value = self.service.projection(actor, subscription, event)
                    notification_id = event.event_id + ':' + subscription['key']
                    body = {'tenant': scope.tenant, 'owner': scope.owner, 'notification_id': notification_id,
                        'subscription_id': subscription['key'], 'event': event.model_dump(mode='json'), 'projection': value.model_dump(mode='json')}
                    connection.execute('INSERT INTO tracking_inbox VALUES(?,?,?,?,?,?,?,?)', (scope.tenant, scope.owner, notification_id, subscription['key'], event.event_id, content_hash, json.dumps(body), digest(body)))
                    self.store.finish(connection, job, 'delivered')
                    counters['delivered'] += 1
                except CertificateError as exc:
                    if exc.status < 500:
                        self.store.finish(connection, job, 'suppressed', code=exc.code)
                        counters['suppressed'] += 1
                    else:
                        self.failure(connection, job, now, counters)
                except (TimeoutError, ConnectionError):
                    self.failure(connection, job, now, counters)
        return counters

    def schedule(self, event):
        rows = self.store.subscriptions_for(event)
        if len(rows) > 50:
            raise ValueError('recipient subscription bound exceeded')
        for row in rows:
            payload = row['payload']
            spec = SubscriptionSpec.model_validate(payload['spec'])
            if (payload['state'] == 'active' and datetime.fromisoformat(event.changed_at) >= datetime.fromisoformat(row['updated_at'])
                    and (spec.resource.kind, spec.resource.id, spec.trigger) == (event.resource.kind, event.resource.id, event.trigger)):
                self.store.schedule(StateScope(event.tenant, event.recipient_id), row['key'], event)

    def failure(self, connection, job, now, counters):
        terminal = job['attempts'] + 1 >= 3
        self.store.finish(connection, job, 'failed' if terminal else 'retry', code='SOURCE_UNAVAILABLE',
            next_at=now+timedelta(seconds=2 ** (job['attempts']+1)), attempt=True)
        counters['retry'] += 1
