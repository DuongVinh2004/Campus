"""Actor/resource/source-bound read grants, with atomic use/revoke and replay.

These grants constrain existing ACLs. They never authorize a business write.
Only trusted read/prepare consumers run under the actor-store transaction lock.
"""
from datetime import datetime, timedelta, timezone

from campus247.application.assistance.contracts import AssistanceRequest, ResourceRef
from campus247.application.assistance.durable_services import ConfirmedStateService
from campus247.application.assistance.feature_contracts import ActiveGrant, GrantSpec, GrantUse
from campus247.application.assistance.preferences import AssistantPreferenceService
from campus247.application.assistance.state_storage import StorageConflict, digest
from campus247.application.document_request.certificates import CertificateError


class AssistantGrantService(ConfirmedStateService):
    namespaces = frozenset({"active_grant"})

    def __init__(self, *args, context, **kwargs):
        super().__init__(*args, **kwargs)
        self.context = context

    def observe(self, actor, resource):
        self.scope(actor)
        resource = ResourceRef.model_validate(resource)
        request = AssistanceRequest(resource=resource,
            surface="service" if resource.kind == "service_request" else "certificate")
        value = self.context.resolve(actor, request)
        if value.status != "observed":
            raise CertificateError(409, "SOURCE_CHANGED", "Cần đối chiếu nguồn trước khi cấp/dùng quyền")
        return value

    def prepare(self, actor, spec):
        spec = GrantSpec.model_validate(spec)
        scope = self.scope(actor)
        old = self.store.get(scope, "active_grant", spec.client_id)
        if old is not None:
            original = self.store.history(scope, "active_grant", spec.client_id, limit=1)[0]
            value = ActiveGrant.model_validate(original.payload)
            if value.spec != spec:
                raise StorageConflict("STATE_IDEMPOTENCY_CONFLICT")
            self.check(actor, ActiveGrant.model_validate(old.payload), capability=spec.capability)
        else:
            observation = self.observe(actor, spec.resource)
            if spec.capability == "read_own_resource" and observation.resource.view != "student":
                raise CertificateError(403, "OWN_RESOURCE_REQUIRED", "Quyền này chỉ đọc hồ sơ của sinh viên hiện tại")
            if spec.capability == "prepare_draft" and (observation.resource.view != "student" or observation.resource.status != "DRAFT"):
                raise CertificateError(403, "PREPARE_SCOPE_INVALID", "Chỉ chuẩn bị nháp của sinh viên")
            now = datetime.now(timezone.utc)
            end = min(now+timedelta(seconds=spec.lifetime_seconds), actor.expires_at)
            value = ActiveGrant(spec=spec, audience=observation.resource.view,
                roles=sorted(str(r) for r in actor.roles), units=sorted(actor.unit_ids), session_id=actor.session_id,
                evidence=observation.evidence, created_at=now.isoformat(), expires_at=end.isoformat())
        return self.preview(actor, "active_grant", spec.client_id, 0, value.model_dump(mode="json"), spec.client_id)

    def check(self, actor, value, *, capability=None, resource=None, operation=None):
        self.scope(actor)
        if (value.state == "revoked" or datetime.now(timezone.utc) >= datetime.fromisoformat(value.expires_at)
                or value.roles != sorted(str(r) for r in actor.roles) or value.units != sorted(actor.unit_ids)
                or value.audience != AssistantPreferenceService.audience(actor)
                or value.spec.lifetime == "session" and value.session_id != actor.session_id
                or capability is not None and capability != value.spec.capability
                or resource is not None and ResourceRef.model_validate(resource) != value.spec.resource):
            raise CertificateError(403, "GRANT_NOT_ACTIVE", "Quyền không còn hiệu lực hoặc không đúng phạm vi")
        used = next((use for use in value.uses if operation and use.operation_id == operation.operation_id), None)
        if used is not None and used != operation:
            raise StorageConflict("GRANT_OPERATION_CHANGED")
        if value.state == "consumed" and used is None:
            raise CertificateError(403, "GRANT_CONSUMED", "Quyền một lần đã được dùng")
        current = self.observe(actor, value.spec.resource)
        if current.evidence != value.evidence or current.resource.view != value.audience:
            raise CertificateError(409, "GRANT_SOURCE_CHANGED", "Nguồn hoặc phạm vi quyền đã thay đổi")
        if value.spec.capability == "prepare_draft" and current.resource.status != "DRAFT":
            raise CertificateError(409, "GRANT_RESOURCE_CHANGED", "Hồ sơ không còn là nháp")
        if value.spec.capability == "read_own_resource" and current.resource.view != "student":
            raise CertificateError(403, "OWN_RESOURCE_REQUIRED", "Quyền này chỉ đọc hồ sơ của sinh viên hiện tại")
        return current

    def read(self, actor, grant_id):
        record = self.store.get(self.scope(actor), "active_grant", grant_id)
        if record is None:
            raise CertificateError(404, "RESOURCE_NOT_FOUND", "Không tìm thấy quyền")
        value = ActiveGrant.model_validate(record.payload)
        # Owner may inspect/revoke even after losing resource access. Do not
        # return source locators or business fields on this management path.
        locked_reason = None
        try:
            self.check(actor, value, capability=value.spec.capability)
        except (CertificateError, StorageConflict) as failure:
            locked_reason = getattr(failure, "code", "GRANT_CHANGED")
        last_used = None
        if value.uses:
            previous_count = 0
            for revision in self.store.history(self.scope(actor), "active_grant", grant_id, after_version=max(0,record.version-100), limit=100):
                count = len(ActiveGrant.model_validate(revision.payload).uses)
                if count > previous_count:
                    last_used = revision.committed_at
                previous_count = count
        return {"id": grant_id, "version": record.version, "capability": value.spec.capability,
                "lifetime": value.spec.lifetime, "expires_at": value.expires_at,
                "state": "expired" if value.state == "active" and datetime.now(timezone.utc) >= datetime.fromisoformat(value.expires_at) else value.state,
                "use_count": len(value.uses), "action_authority": value.action_authority,
                "resource": value.spec.resource.model_dump(mode="json"), "purpose": value.spec.purpose,
                "last_used_at": last_used, "locked_reason": locked_reason}

    def page(self, actor, *, cursor="", limit=20):
        if type(limit) is not int or not 1 <= limit <= 99:
            raise ValueError("bounded grant page required")
        if cursor and self.store.get(self.scope(actor), "active_grant", cursor) is None:
            raise CertificateError(422, "CURSOR_INVALID", "Cursor không thuộc quyền của actor")
        rows = self.store.list_current(self.scope(actor), "active_grant", after_key=cursor, limit=limit+1)
        items = [self.read(actor, row.key) for row in rows[:limit]]
        return {"items": items, "page": {"has_more": len(rows) > limit,
            "next_cursor": items[-1]["id"] if len(rows) > limit else None}}

    def prepare_revoke(self, actor, grant_id, expected_version, client_id):
        scope = self.scope(actor)
        prior_receipt = self.store.receipt(scope, client_id)
        if prior_receipt is not None:
            if prior_receipt.namespace != "active_grant" or prior_receipt.key != grant_id:
                raise StorageConflict("STATE_IDEMPOTENCY_CONFLICT")
            record = self.store.history(scope, "active_grant", grant_id, after_version=prior_receipt.version-1, limit=1)[0]
            value = ActiveGrant.model_validate(record.payload)
            if value.state != "revoked" or expected_version != prior_receipt.version-1:
                raise StorageConflict("STATE_IDEMPOTENCY_CONFLICT")
        else:
            record = self.store.get(scope, "active_grant", grant_id)
            if record is None:
                raise CertificateError(404, "RESOURCE_NOT_FOUND", "Không tìm thấy quyền")
            if record.version != expected_version:
                raise StorageConflict("STATE_STALE_VERSION")
            value = ActiveGrant.model_validate(record.payload).model_copy(update={"state": "revoked"})
        return self.preview(actor, "active_grant", grant_id, expected_version, value.model_dump(mode="json"), client_id)

    def revalidate(self, actor, namespace, key, payload):
        value = ActiveGrant.model_validate(payload)
        if key != value.spec.client_id:
            raise CertificateError(409, "GRANT_BINDING_INVALID", "Sai ràng buộc quyền")
        original = self.store.history(self.scope(actor), namespace, key, limit=1)
        if value.state == "revoked":
            if not original or ActiveGrant.model_validate(original[0].payload).model_copy(update={"state": "revoked", "uses": value.uses}) != value:
                raise CertificateError(409, "GRANT_BINDING_INVALID", "Rút quyền không được thay nội dung")
        else:
            if value.uses or value.state != "active":
                raise CertificateError(409, "GRANT_BINDING_INVALID", "Consumer mới được ghi nhận lượt dùng")
            self.check(actor, value)

    def commit_guard(self, actor, namespace, key, payload):
        def guard(connection):
            scope = self.scope(actor)
            row = connection.execute("SELECT version,record FROM unified_actor_state WHERE tenant=? AND owner=? AND namespace=? AND key=?",
                (scope.tenant, scope.owner, namespace, key)).fetchone()
            current = self.store._decode(row, scope, namespace, key)
            if current is not None:
                self.store._verify_revision(connection, scope, namespace, key, current)
                previous = ActiveGrant.model_validate(current.payload)
                if payload["state"] == "revoked":
                    if previous.model_copy(update={"state": "revoked"}).model_dump(mode="json") != payload:
                        raise StorageConflict("STATE_STALE_VERSION")
                else:
                    self.check(actor, previous)
            elif payload["state"] == "revoked":
                raise CertificateError(404, "RESOURCE_NOT_FOUND", "Không tìm thấy quyền")
            if payload["state"] != "revoked":
                self.check(actor, ActiveGrant.model_validate(payload))
        return guard

    def use(self, actor, grant_id, *, operation_id, capability, resource, intent, consume):
        """Only server-owned read/prepare callbacks; never a business executor."""
        scope = self.scope(actor)
        operation = GrantUse(operation_id=operation_id, capability=capability, intent_sha256=digest(intent))
        record = self.store.get(scope, "active_grant", grant_id)
        if record is None:
            raise CertificateError(404, "RESOURCE_NOT_FOUND", "Không tìm thấy quyền")
        value = ActiveGrant.model_validate(record.payload)
        self.check(actor, value, capability=capability, resource=resource, operation=operation)
        receipt = self.store.receipt(scope, operation_id)
        if receipt is not None:
            if receipt.namespace != "active_grant" or receipt.key != grant_id:
                raise StorageConflict("STATE_IDEMPOTENCY_CONFLICT")
            committed = self.store.history(scope, "active_grant", grant_id, after_version=receipt.version-1, limit=1)[0]
            payload, expected = committed.payload, receipt.version-1
            if operation not in ActiveGrant.model_validate(payload).uses:
                raise StorageConflict("GRANT_OPERATION_CHANGED")
        else:
            if len(value.uses) >= 100:
                raise CertificateError(409, "GRANT_USE_LIMIT", "Cần tạo quyền mới sau giới hạn lượt dùng")
            payload = value.model_copy(update={"uses": [*value.uses, operation],
                "state": "consumed" if value.spec.lifetime == "once" else "active"}).model_dump(mode="json")
            expected = record.version
        result = []
        def guard(connection):
            self.scope(actor)
            row = connection.execute("SELECT version,record FROM unified_actor_state WHERE tenant=? AND owner=? AND namespace='active_grant' AND key=?",
                                     (scope.tenant, scope.owner, grant_id)).fetchone()
            current = self.store._decode(row, scope, "active_grant", grant_id)
            if current is None:
                raise CertificateError(403, "GRANT_NOT_ACTIVE", "Quyền không còn hiệu lực")
            self.store._verify_revision(connection, scope, "active_grant", grant_id, current)
            observation = self.check(actor, ActiveGrant.model_validate(current.payload), capability=capability,
                                     resource=resource, operation=operation)
            result.append(consume(observation))
        committed = self.store.commit(scope, "active_grant", grant_id, expected, payload, operation_id, guard=guard)
        return {"result": result[0], "receipt": committed}
