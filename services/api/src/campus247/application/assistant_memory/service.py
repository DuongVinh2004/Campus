"""Explicit memory opt-in, CAS correction, permanent logical suppression and fresh use."""
from datetime import datetime, timezone, timedelta
import hashlib
import json
from contextlib import nullcontext, contextmanager
from contextvars import ContextVar

from campus247.application.assistance.durable_services import ConfirmedStateService
from campus247.application.assistance.feature_contracts import ActiveGrant
from campus247.application.assistance.preferences import AssistantPreferenceService
from campus247.application.assistance.state_storage import digest
from campus247.application.document_request.certificates import CertificateError
from campus247.domain.action.preview import create_action_preview
from campus247.domain.assistant_memory import MemoryChange, MemoryQuery, MemoryValue

DISCLOSURE = 'memory.v1: Chỉ ghi khai báo đã xác nhận cho cá nhân hóa. Quên là suppression/tombstone có phiên bản; dữ liệu cũ, history, index và backup không bị xóa vật lý. Tắt memory không xóa history. Export chỉ gồm kho memory của actor, không phải toàn bộ dữ liệu tài khoản. Không tự import history/legacy. Chat tạm thời không đọc/ghi memory.'
_request_revalidator = ContextVar('personal_request_revalidator', default=None)


class PersonalConfirmedService(ConfirmedStateService):
    feature = 'memory'

    @contextmanager
    def request_guard(self, revalidate):
        if not callable(revalidate):
            raise CertificateError(503, 'PERSONAL_SESSION_READER_UNAVAILABLE', 'Chưa có reader phiên hiện hành')
        token = _request_revalidator.set(revalidate)
        try:
            yield
        finally:
            _request_revalidator.reset(token)

    def scope(self, actor):
        revalidate = _request_revalidator.get()
        if revalidate is not None:
            try:
                fresh = revalidate()
            except ValueError:
                raise CertificateError(403, 'PERSONAL_SESSION_REVOKED', 'Phiên đã hết hạn hoặc bị thu hồi') from None
            if (fresh.subject_id, fresh.tenant_id, fresh.session_id, fresh.roles, fresh.unit_ids) != (actor.subject_id, actor.tenant_id, actor.session_id, actor.roles, actor.unit_ids):
                raise CertificateError(403, 'PERSONAL_SESSION_CHANGED', 'Actor/vai trò/phạm vi phiên đã thay đổi')
            actor = fresh
        return super().scope(actor)

    def preview_body(self, actor, body):
        scope = self.scope(actor)
        preview = create_action_preview(scope.owner, 'assistant.personal.' + self.feature,
            {'tenant': scope.tenant, 'owner': scope.owner, 'feature': self.feature, **body},
            session_id=actor.session_id, conversation_id=scope.tenant, tool_version='personal.v1',
            policy_version='personal-confirmed.v1', preview_id=body['client_id'], ttl_seconds=120)
        return {'normalized_payload': preview.normalized_payload, 'confirmation_token': self.tokens.mint_token(preview),
                'expires_at': preview.expires_at.isoformat(), 'effect': 'personal_state_only'}

    def confirm(self, actor, normalized_payload, confirmation_token, *, confirmed):
        scope = self.scope(actor)
        if confirmed is not True:
            raise CertificateError(422, 'EXPLICIT_CONFIRMATION_REQUIRED', 'Cần xác nhận preview')
        try:
            body = json.loads(normalized_payload)
            validation = self.tokens.validate_token(confirmation_token, body['client_id'], scope.owner,
                actor.session_id, scope.tenant, 'assistant.personal.' + self.feature, 'personal.v1',
                'personal-confirmed.v1', 'sha256:' + hashlib.sha256(normalized_payload.encode()).hexdigest())
            if not validation.is_valid or (body['tenant'], body['owner'], body['feature']) != (scope.tenant, scope.owner, self.feature):
                raise ValueError('binding')
        except (ValueError, TypeError, KeyError):
            raise CertificateError(409, 'PERSONAL_CONFIRMATION_INVALID', 'Preview không khớp phiên/nội dung') from None
        return self.commit_body(actor, body)

    def receipt(self, actor, client_id):
        value = self.store.receipt(self.scope(actor), client_id)
        if value is None:
            raise CertificateError(404, 'RECEIPT_NOT_FOUND', 'Chưa có commit; giữ bản soạn')
        return value


class AssistantMemoryService(PersonalConfirmedService):
    def __init__(self, *args, preferences, grants=None, conversation_mode=None, minimize=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.preferences, self.grants = preferences, grants
        self.conversation_mode, self.minimize = conversation_mode, minimize

    def mode(self, actor, conversation_id):
        self.scope(actor)
        if self.conversation_mode is None:
            raise CertificateError(503, 'MEMORY_MODE_CONSUMER_UNAVAILABLE', 'Chưa nối reader mode/ownership; dùng settings hiện có')
        value = self.conversation_mode(actor, conversation_id)
        if value not in {'persistent', 'settings', 'temporary'} or conversation_id is not None and value == 'settings':
            raise CertificateError(403, 'CHAT_MODE_UNVERIFIED', 'Không xác nhận được ownership/mode')
        return value

    def active(self, actor, conversation_id, connection=None):
        mode = self.mode(actor, conversation_id)
        control = self.store.get(self.scope(actor), 'memory_control', 'account', connection)
        enabled = bool(control and control['payload']['enabled'] and control['payload']['disclosure'] == DISCLOSURE)
        if mode == 'temporary' or not enabled or not self.preferences.consented(actor, 'OPTIONAL_PERSONALIZATION'):
            raise CertificateError(403, 'MEMORY_DISABLED', 'Memory tắt, chat tạm thời hoặc thiếu consent hiện hành')

    @staticmethod
    def key(value, audience):
        resource = {'kind': value.resource.kind, 'id': value.resource.id} if value.resource else None
        return digest({'audience': audience, 'topic': value.topic.casefold(), 'resource': resource})

    def check_value(self, actor, value):
        self.scope(actor)
        now = datetime.now(timezone.utc)
        if not now < datetime.fromisoformat(value.valid_until) <= now + timedelta(days=366):
            raise CertificateError(409, 'MEMORY_VALIDITY_INVALID', 'Cần thời hạn còn hiệu lực, tối đa 366 ngày')
        if value.resource:
            if AssistantPreferenceService.audience(actor) == 'staff':
                raise CertificateError(403, 'STAFF_CASE_MEMORY_PROHIBITED', 'Không tái dùng hồ sơ sinh viên làm personal memory cán bộ')
            if self.grants is None:
                raise CertificateError(503, 'MEMORY_GRANT_UNAVAILABLE', 'Chưa có grant consumer')
            row = self.grants.store.get(self.scope(actor), 'active_grant', value.grant_id)
            if row is None:
                raise CertificateError(403, 'GRANT_NOT_ACTIVE', 'Quyền không còn hiệu lực')
            grant = ActiveGrant.model_validate(row.payload)
            if grant.spec.lifetime == 'once':
                raise CertificateError(403, 'MEMORY_REUSABLE_GRANT_REQUIRED', 'Memory cần quyền có thể recheck, không dùng quyền một lần')
            self.grants.check(actor, grant, capability='read_source', resource=value.resource)

    def prepare(self, actor, change):
        change = MemoryChange.model_validate(change)
        scope = self.scope(actor)
        self.mode(actor, change.conversation_id)
        if change.operation == 'control':
            if self.mode(actor, change.conversation_id) == 'temporary':
                raise CertificateError(403, 'TEMPORARY_MEMORY_DISABLED', 'Không thay đổi personal memory trong chat tạm thời')
            if change.enabled and not self.preferences.consented(actor, 'OPTIONAL_PERSONALIZATION'):
                raise CertificateError(403, 'MEMORY_CONSENT_REQUIRED', 'Cần consent cá nhân hóa hiện hành trước')
            namespace, key = 'memory_control', 'account'
            payload = {'enabled': change.enabled, 'disclosure': DISCLOSURE}
        elif change.operation == 'forget':
            if self.mode(actor, change.conversation_id) == 'temporary':
                raise CertificateError(403, 'TEMPORARY_MEMORY_DISABLED', 'Mở memory settings để quản lý')
            namespace, key = 'memory', change.key
            old = self.store.get(scope, namespace, key)
            if old is None:
                raise CertificateError(404, 'MEMORY_NOT_FOUND', 'Không tìm thấy memory')
            payload = {**old['payload'], 'state': 'suppressed', 'suppression': 'logical_only_no_physical_deletion'}
        else:
            self.active(actor, change.conversation_id)
            self.check_value(actor, change.value)
            namespace, key = 'memory', self.key(change.value, AssistantPreferenceService.audience(actor))
            payload = {'state': 'active', 'value': change.value.model_dump(mode='json'),
                'source': {'type': 'explicit_actor_declaration', 'actor': actor.subject_id, 'session': actor.session_id},
                'disclosure': DISCLOSURE, 'audience': AssistantPreferenceService.audience(actor)}
        return self.preview_body(actor, {'client_id': change.client_id, 'expected_version': change.expected_version,
            'namespace': namespace, 'key': key, 'payload': payload, 'conversation_id': change.conversation_id})

    def commit_body(self, actor, body):
        scope = self.scope(actor)
        def guard(connection, current):
            mode = self.mode(actor, body['conversation_id'])
            if mode == 'temporary':
                raise CertificateError(403, 'TEMPORARY_MEMORY_DISABLED', 'Chat tạm thời không ghi memory')
            payload = body['payload']
            if body['namespace'] == 'memory_control':
                if payload['enabled'] and not self.preferences.consented(actor, 'OPTIONAL_PERSONALIZATION'):
                    raise CertificateError(403, 'MEMORY_CONSENT_REQUIRED', 'Consent đã thay đổi')
            elif payload['state'] == 'active':
                self.active(actor, body['conversation_id'], connection)
                self.check_value(actor, MemoryValue.model_validate(payload['value']))
                if current and current['payload']['state'] == 'suppressed':
                    raise CertificateError(409, 'MEMORY_SUPPRESSED', 'Topic đã quên; không được tái tạo từ history/candidate')
                if current is None and len(self.store.page(scope, 'memory', limit=101, connection=connection)) >= 100:
                    raise CertificateError(409, 'MEMORY_CAPACITY_BOUND', 'Kho memory đạt giới hạn 100 topic, gồm tombstone')
            elif current is None:
                raise CertificateError(404, 'MEMORY_NOT_FOUND', 'Không tìm thấy memory')
        return self.store.commit(scope, body['namespace'], body['key'], body['expected_version'], body['payload'], body['client_id'], guard=guard)

    def history_suppression_stamp(self, actor, conversation_id):
        # Suppression metadata is checked even with memory off. Old history
        # remains readable, but cannot silently reconstruct forgotten topics.
        if self.mode(actor, conversation_id) == 'temporary':
            return ()  # Never inspect personal memory in temporary chats.
        rows = self.store.page(self.scope(actor), 'memory', limit=101)
        if len(rows) > 100:
            raise CertificateError(409, 'MEMORY_RETRIEVAL_BOUND', 'Kho memory vượt giới hạn kiểm suppression')
        return tuple(sorted((row['key'], row['version']) for row in rows if row['payload']['state'] == 'suppressed'))

    def management(self, actor, *, cursor='', limit=20):
        scope = self.scope(actor)
        if not 1 <= limit <= 50:
            raise ValueError('bounded page required')
        rows = self.store.page(scope, 'memory', after=cursor, limit=limit+1)
        # Suppressed text is deliberately absent from the management projection.
        items = []
        for row in rows[:limit]:
            payload = row['payload']
            item = {key: row[key] for key in ('key', 'version', 'updated_at')}
            item['state'] = payload['state']
            if payload['state'] == 'active':
                try:
                    if not self.preferences.consented(actor, 'OPTIONAL_PERSONALIZATION'):
                        raise CertificateError(403, 'MEMORY_CONSENT_REQUIRED', 'Consent đã bị rút lại')
                    if payload['audience'] != AssistantPreferenceService.audience(actor):
                        raise CertificateError(403, 'MEMORY_ROLE_CHANGED', 'Memory thuộc ngữ cảnh vai trò khác')
                    self.check_value(actor, MemoryValue.model_validate(payload['value']))
                    item['value'], item['source'] = payload['value'], payload['source']
                except CertificateError as exc:
                    item['locked_reason'] = exc.code
            items.append(item)
        control = self.store.get(scope, 'memory_control', 'account')
        return {'items': items, 'control': control, 'next_cursor': rows[limit-1]['key'] if len(rows) > limit else None,
            'disclosure': DISCLOSURE, 'export_scope': 'current authorized personal memory only', 'physical_erasure': 'not_performed'}

    def retrieve(self, actor, query, *, _connection=None):
        query = MemoryQuery.model_validate(query)
        scope = self.scope(actor)
        if self.mode(actor, query.conversation_id) == 'temporary':
            return {'items': [], 'action_authority': 'none', 'reason': 'temporary_chat'}
        self.active(actor, query.conversation_id, _connection)
        if self.minimize is None:
            raise CertificateError(503, 'MEMORY_MINIMIZER_UNAVAILABLE', 'Chưa có minimization consumer')
        with (self.store.transaction() if _connection is None else nullcontext(_connection)) as connection:
            rows = self.store.page(scope, 'memory', limit=101, connection=connection)
            if len(rows) > 100:
                raise CertificateError(409, 'MEMORY_RETRIEVAL_BOUND', 'Thu hẹp memory; không quét vô hạn')
            items = []
            for row in rows:
                payload = row['payload']
                if payload['state'] != 'active' or payload['audience'] != AssistantPreferenceService.audience(actor):
                    continue
                value = MemoryValue.model_validate(payload['value'])
                if value.resource != query.resource and value.scope == 'resource':
                    continue
                try:
                    self.check_value(actor, value)
                except CertificateError:
                    continue
                if not any(term in (value.topic + ' ' + value.text).casefold() for term in query.terms):
                    continue
                text = self.minimize(value.text)
                if not isinstance(text, str) or not text or len(text.encode()) > 1200:
                    continue
                items.append({'key': row['key'], 'version': row['version'], 'kind': value.kind, 'text': text,
                    'source': {'type': payload['source']['type'], 'actor': payload['source']['actor']}, 'confirmed_at': row['updated_at'], 'valid_until': value.valid_until,
                    'scope': value.scope, 'purpose': value.purpose, 'classification': 'untrusted_personal_declaration'})
                if len(items) == query.limit:
                    break
            self.active(actor, query.conversation_id, connection)
            result = {'items': items, 'action_authority': 'none', 'freshness': 'recompose_every_use',
                'constraint': 'Never replace current sources or business rules with memory.'}
            return {**result, 'sha256': digest(result)}

    def use(self, actor, query, expected_sha256, consume):
        # Consumer receives only a fresh projection; callers must not cache raw blocks.
        with self.store.transaction() as connection:
            value = self.retrieve(actor, query, _connection=connection)
            if value.get('sha256') != expected_sha256:
                raise CertificateError(409, 'MEMORY_CONTEXT_CHANGED', 'Memory đã sửa/quên; cần compose lại')
            self.active(actor, MemoryQuery.model_validate(query).conversation_id, connection)
            return consume(value)
