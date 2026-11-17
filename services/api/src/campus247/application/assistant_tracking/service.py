"""Explicit subscription confirmation and fresh inbox authorization."""
from datetime import datetime, timezone, timedelta

from campus247.application.assistant_memory.service import PersonalConfirmedService
from campus247.application.assistance.feature_contracts import ActiveGrant
from campus247.application.assistance.preferences import AssistantPreferenceService
from campus247.application.document_request.certificates import CertificateError
from campus247.domain.assistant_tracking import TrackingChange, SubscriptionSpec, BusinessTrackingEvent, NotificationProjection


class AssistantTrackingService(PersonalConfirmedService):
    feature = 'tracking'

    def __init__(self, *args, grants, source=None, resolve_recipient=None, project_notification=None, minimize=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.grants, self.source, self.resolve_recipient = grants, source, resolve_recipient
        self.project_notification, self.minimize = project_notification, minimize

    @property
    def configured(self):
        return bool(self.grants and self.source and callable(getattr(self.source, 'read_batch', None))
            and callable(getattr(self.source, 'ack', None)) and self.resolve_recipient and self.project_notification and self.minimize)

    def available(self):
        if not self.configured:
            raise CertificateError(503, 'TRACKING_CONSUMER_UNAVAILABLE', 'Chưa nối outbox/recipient/source consumer; mở hồ sơ để kiểm tra thủ công')

    def check(self, actor, spec, *, event=None):
        scope = self.scope(actor)
        self.available()
        if spec.trigger == 'deadline' and getattr(self.source, 'supports_deadline', False) is not True:
            raise CertificateError(503, 'TRACKING_DEADLINE_UNAVAILABLE', 'Chưa có deadline được nguồn xác minh; không hứa thời hạn')
        now = datetime.now(timezone.utc)
        if not now < datetime.fromisoformat(spec.expires_at) <= min(now+timedelta(days=30), actor.expires_at):
            raise CertificateError(403, 'SUBSCRIPTION_EXPIRED', 'Hết thời hạn theo dõi/phiên')
        row = self.grants.store.get(scope, 'active_grant', spec.permission_id)
        if row is None or row.version != spec.permission_version:
            raise CertificateError(403, 'TRACKING_PERMISSION_CHANGED', 'Quyền đã thay đổi/rút lại')
        grant = ActiveGrant.model_validate(row.payload)
        if grant.spec.lifetime == 'once' or datetime.fromisoformat(spec.expires_at) > datetime.fromisoformat(grant.expires_at):
            raise CertificateError(403, 'TRACKING_PERMISSION_LIFETIME', 'Theo dõi cần quyền còn hiệu lực trong toàn thời hạn')
        # Original source version remains the permission binding. The business
        # projection separately checks a new event's exact version/assignment.
        if event is None:
            self.grants.check(actor, grant, capability='read_source', resource=spec.resource)
        elif (grant.state != 'active' or datetime.fromisoformat(grant.expires_at) <= now
                or grant.roles != sorted(str(role) for role in actor.roles) or grant.units != sorted(actor.unit_ids)
                or grant.spec.capability != 'read_source' or grant.spec.resource != spec.resource
                or grant.audience != AssistantPreferenceService.audience(actor)
                or grant.spec.lifetime == 'session' and grant.session_id != actor.session_id):
            raise CertificateError(403, 'TRACKING_PERMISSION_INACTIVE', 'Quyền không còn đúng actor/phiên/phạm vi')
        if event:
            if (event.tenant, event.recipient_id, event.audience) != (scope.tenant, scope.owner, AssistantPreferenceService.audience(actor)):
                raise CertificateError(403, 'TRACKING_RECIPIENT_MISMATCH', 'Sai actor/tenant/audience')
            if (event.resource.kind, event.resource.id, event.trigger) != (spec.resource.kind, spec.resource.id, spec.trigger):
                raise CertificateError(403, 'TRACKING_RESOURCE_MISMATCH', 'Sai tài nguyên/trigger')
            if not callable(getattr(self.grants, 'observe', None)):
                raise CertificateError(503, 'TRACKING_SOURCE_GRANT_RECHECK_UNAVAILABLE', 'Chưa có consumer đối chiếu nguồn quyền ở phiên bản mới')
            observation = self.grants.observe(actor, event.resource)
            if observation.evidence != grant.evidence or observation.resource.view != grant.audience:
                raise CertificateError(403, 'TRACKING_SOURCE_GRANT_CHANGED', 'Nguồn/phạm vi hiện tại khác quyền đã xác nhận')
        return scope

    def prepare(self, actor, change):
        change = TrackingChange.model_validate(change)
        scope = self.scope(actor)
        audience = AssistantPreferenceService.audience(actor)
        if change.operation == 'subscribe':
            self.check(actor, change.spec)
            payload = {'state': 'active', 'spec': change.spec.model_dump(mode='json'), 'session_id': actor.session_id,
                'audience': audience, 'roles': sorted(str(r) for r in actor.roles), 'units': sorted(actor.unit_ids)}
        else:
            old = self.store.get(scope, 'tracking', change.subscription_id)
            if old is None:
                raise CertificateError(404, 'SUBSCRIPTION_NOT_FOUND', 'Không tìm thấy đăng ký')
            payload = {**old['payload'], 'state': 'stopped'}
        return self.preview_body(actor, {'client_id': change.client_id, 'namespace': 'tracking', 'key': change.subscription_id,
            'expected_version': change.expected_version, 'payload': payload})

    def commit_body(self, actor, body):
        scope = self.scope(actor)
        def guard(connection, current):
            self.scope(actor)
            if body['payload']['state'] == 'active':
                self.check(actor, SubscriptionSpec.model_validate(body['payload']['spec']))
                if body['payload']['session_id'] != actor.session_id:
                    raise CertificateError(403, 'TRACKING_SESSION_CHANGED', 'Phiên đã thay đổi')
                if current is None and len(self.store.page(scope, 'tracking', limit=51, connection=connection)) >= 50:
                    raise CertificateError(409, 'TRACKING_CAPACITY_BOUND', 'Đạt giới hạn 50 đăng ký của tài khoản')
            elif current is None or {**current['payload'], 'state': 'stopped'} != body['payload']:
                raise CertificateError(409, 'TRACKING_STOP_CHANGED', 'Chỉ được dừng đúng đăng ký')
        return self.store.commit(scope, 'tracking', body['key'], body['expected_version'], body['payload'], body['client_id'], guard=guard)

    def subscriptions(self, actor):
        return {'items': self.store.page(self.scope(actor), 'tracking', limit=50), 'channel': 'in_app',
            'configured': self.configured, 'remote_channels': 'unavailable',
            'supported_triggers': ['feedback', 'supplement', 'status'] + (['deadline'] if getattr(self.source, 'supports_deadline', False) is True else [])}

    def projection(self, actor, subscription, event):
        payload = subscription['payload']
        if payload['state'] != 'active' or payload['session_id'] != actor.session_id or payload['roles'] != sorted(str(r) for r in actor.roles) or payload['units'] != sorted(actor.unit_ids):
            raise CertificateError(403, 'SUBSCRIPTION_INACTIVE', 'Đăng ký/phiên/vai trò đã thay đổi')
        spec = SubscriptionSpec.model_validate(payload['spec'])
        self.check(actor, spec, event=event)
        value = NotificationProjection.model_validate(self.project_notification(actor, spec, event))
        if (value.recipient_id, value.audience, value.resource, value.source_id, value.source_sha256, value.classification) != (actor.subject_id, payload['audience'], event.resource, event.source_id, event.source_sha256, event.classification):
            raise CertificateError(403, 'NOTIFICATION_SOURCE_MISMATCH', 'Projection không khớp recipient/nguồn/phiên bản')
        reason = self.minimize(value.reason)
        if not isinstance(reason, str) or not reason:
            raise CertificateError(403, 'NOTIFICATION_MINIMIZATION_FAILED', 'Không có preview an toàn')
        return NotificationProjection.model_validate({**value.model_dump(mode='json'), 'reason': reason})

    def notifications(self, actor, *, cursor=''):
        scope = self.scope(actor)
        self.available()
        rows = self.store.inbox(scope, after=cursor, limit=20)
        items = []
        for row in rows:
            subscription = self.store.get(scope, 'tracking', row['subscription_id'])
            try:
                if subscription is None:
                    continue
                event = BusinessTrackingEvent.model_validate(row['event'])
                fresh = self.projection(actor, subscription, event)
            except CertificateError:
                continue
            items.append({'id': row['notification_id'], 'event_id': event.event_id, 'subscription_id': row['subscription_id'],
                'subscription_version': subscription['version'], **fresh.model_dump(mode='json')})
        return {'items': items, 'next_cursor': rows[-1]['notification_id'] if len(rows) == 20 else None,
                'channel': 'in_app', 'delivery': 'local_inbox_only', 'remote_channels': 'unavailable'}
