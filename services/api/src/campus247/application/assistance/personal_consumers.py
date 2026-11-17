"""A-owned adapters for B's registrar: business outbox and current sessions.

Identifiers and safe token hashes are retained; no bearer token is persisted.
Legacy chats without a server mode remain unavailable for memory use.
"""
from datetime import datetime, timezone
import hashlib
from identities import generate_identities
from campus247.application.document_request.certificates import CertificateError
from campus247.application.knowledge.operations import digest
from campus247.ports.identity import AccountState, IdentityContext, IdentityRole

class CaseTrackingSource:
    def __init__(self, cases, grants):
        self.cases, self.grants = cases, grants

    def read_batch(self, *, limit=20):
        if type(limit) is not int or not 1 <= limit <= 20:
            raise ValueError("bounded exact outbox read required")
        with self.cases.resources["service_request"].repository.transaction() as tx:
            rows = tx.connection.execute("SELECT e.id FROM service_operations_record e LEFT JOIN service_operations_record a ON a.kind='case_tracking_ack' AND a.id=e.id WHERE e.kind='case_tracking_event' AND a.id IS NULL ORDER BY e.id LIMIT ?", (limit,)).fetchall()
            return [{k: v for k, v in self.cases.repository.read(tx, "tracking_event", row[0]).items() if k != "id"} for row in rows]

    def ack(self, event_id):
        with self.cases.resources["service_request"].repository.transaction() as tx:
            if self.cases.repository.read(tx, "tracking_event", event_id) is None:
                raise CertificateError(404, "OUTBOX_EVENT_NOT_FOUND", "Không tìm thấy event chính xác")
            if self.cases.repository.read(tx, "tracking_ack", event_id) is None:
                self.cases.repository.insert(tx, "tracking_ack", {"id": event_id, "at": datetime.now(timezone.utc).isoformat()})

    def project(self, actor, spec, event):
        with self.cases.resources[event.resource.kind].repository.transaction() as tx:
            source = self.cases.repository.read(tx, "tracking_event", event.event_id)
            if not source or {k: v for k, v in source.items() if k != "id"} != event.model_dump(mode="json"):
                raise CertificateError(409, "EVENT_SOURCE_CHANGED", "Event không khớp nguồn bền vững")
        value = self.cases.projection(actor, event.resource)
        if value["source_state"] != "bound":
            raise CertificateError(409, "NOTIFICATION_SOURCE_UNRESOLVED", "Nguồn cần đối chiếu; mở hồ sơ thủ công")
        if event.tenant != actor.tenant_id or event.recipient_id != actor.subject_id:
            raise CertificateError(403, "NOTIFICATION_RECIPIENT_MISMATCH", "Sai người nhận")
        if event.audience == "staff" and value.get("assigned_actor") != actor.subject_id:
            raise CertificateError(403, "NOTIFICATION_ASSIGNMENT_CHANGED", "Người phụ trách đã đổi")
        from campus247.application.assistance.contracts import AssistanceRequest
        from campus247.application.assistance.feature_contracts import ActiveGrant
        scope = self.grants.scope(actor)
        permission = self.grants.store.get(scope, "active_grant", spec.permission_id)
        if not permission or permission.version != spec.permission_version:
            raise CertificateError(403, "TRACKING_PERMISSION_CHANGED", "Quyền nguồn đã đổi/rút lại")
        grant = ActiveGrant.model_validate(permission.payload)
        observation = self.grants.context.resolve(actor, AssistanceRequest(resource=event.resource,
            surface="service" if event.resource.kind == "service_request" else "certificate"))
        if (grant.state != "active" or grant.evidence != observation.evidence or observation.status != "observed"
                or grant.audience != observation.resource.view):
            raise CertificateError(403, "TRACKING_SOURCE_PERMISSION_CHANGED", "Nguồn hiện tại khác phạm vi đã cho phép; cần cấp lại quyền sau đối chiếu")
        return {"recipient_id": actor.subject_id, "audience": event.audience, "resource": event.resource.model_dump(),
            "reason": "Hồ sơ có thay đổi đã ghi nhận; mở hồ sơ để đối chiếu trạng thái và phần cần xử lý.",
            "source_id": event.source_id, "source_sha256": event.source_sha256, "updated_at": event.changed_at,
            "next_action": "review_supplement" if event.trigger == "supplement" else "read_feedback" if event.trigger == "feedback" else "review_status",
            "classification": event.classification, "action_authority": "none"}

class CurrentRecipientRegistry:
    def __init__(self, cases):
        self.cases = cases

    def capture(self, actor, token):
        if not token:
            return
        self.cases.resources["service_request"].authorize(actor)
        value = {"id": digest([actor.tenant_id, actor.subject_id, actor.session_id]), "tenant": actor.tenant_id,
            "owner": actor.subject_id, "session": actor.session_id, "token_sha256": hashlib.sha256(token.encode()).hexdigest(),
            "roles": sorted(str(r) for r in actor.roles), "units": sorted(actor.unit_ids),
            "auth_time": actor.auth_time.isoformat(), "expires_at": actor.expires_at.isoformat()}
        with self.cases.resources["service_request"].repository.transaction() as tx:
            prior = self.cases.repository.read(tx, "session", value["id"])
            if prior is None:
                self.cases.repository.insert(tx, "session", value)
            elif prior != value:
                raise CertificateError(409, "SESSION_BINDING_CHANGED", "Phiên đã đổi metadata; cần đăng nhập lại")

    def resolve(self, tenant, owner, session_id):
        if tenant != self.cases.tenant:
            raise CertificateError(403, "RECIPIENT_TENANT_MISMATCH", "Sai tenant")
        with self.cases.resources["service_request"].repository.transaction() as tx:
            value = self.cases.repository.read(tx, "session", digest([tenant, owner, session_id]))
            if not value:
                raise CertificateError(503, "RECIPIENT_SESSION_UNAVAILABLE", "Chưa có phiên đã xác minh của người nhận")
            if tx.connection.execute("SELECT 1 FROM certificate_revocation WHERE key IN (?,?,?)",
                (value["token_sha256"], session_id, hashlib.sha256(session_id.encode()).hexdigest())).fetchone():
                raise CertificateError(403, "RECIPIENT_SESSION_REVOKED", "Phiên người nhận đã bị thu hồi")
        directory = generate_identities()["records"]
        user = next((u for u in directory["user_identity"] if u["id"] == owner), None)
        roles = sorted({r["role"] for r in directory["role_binding"] if r["user_id"] == owner})
        units = sorted({r["scope_key"] for r in directory["role_binding"] if r["user_id"] == owner and r["scope_type"] == "QUEUE"})
        if not user or user["status"] != "ACTIVE" or roles != value["roles"] or units != value["units"]:
            raise CertificateError(403, "RECIPIENT_DIRECTORY_CHANGED", "Quyền/tài khoản người nhận đã đổi")
        profile = next((p for p in directory["student_profile"] if p["user_id"] == owner), None)
        actor = IdentityContext(subject_id=owner, external_subject="syn_" + owner, issuer="urn:campus247:issuer:synthetic",
            roles=tuple(IdentityRole(r) for r in roles), display_name="", auth_time=datetime.fromisoformat(value["auth_time"]),
            expires_at=datetime.fromisoformat(value["expires_at"]), tenant_id=tenant, unit_ids=tuple(units),
            session_id=session_id, account_state=AccountState.ACTIVE, student_code=profile["student_code"] if profile else None)
        self.cases.resources["service_request"].authorize(actor)
        return actor
