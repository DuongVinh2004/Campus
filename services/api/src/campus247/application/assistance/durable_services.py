"""Confirmed internal state services; no model, resource mutation or grant activation.

Services receive an identity freshly resolved by server middleware. Every call
reauthorizes that identity; resource readers recheck owner/queue and versions.
Receipts acknowledge only the actor-state transaction. Business state remains
in its own store and must be revalidated when a consumer uses a saved proposal.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import hashlib

from campus247.application.assistance.contracts import ResourceRef
from campus247.application.assistance.state_storage import (
    StateScope, PreferencesSnapshot, GrantRequestSnapshot, ProposalBundle, payload_for,
)
from campus247.application.assistance.unified_contracts import GrantRequest, DraftProposal
from campus247.application.assistance.workflow import WorkflowResolveRequest
from campus247.application.document_request.certificates import CertificateError
from campus247.domain.action.preview import create_action_preview
from campus247.domain.shared.values import is_valid_uuid7
from campus247.ports.identity import IdentityContext


@dataclass(frozen=True)
class ConfirmedPreview:
    preview: object
    confirmation_token: str


class ConfirmedStateService:
    namespaces = frozenset()

    def __init__(self, store, *, tenant, authorize, tokens, resources=None, workflow=None):
        self.store, self.tenant, self.authorize, self.tokens = store, tenant, authorize, tokens
        self.resources, self.workflow = resources, workflow

    def scope(self, actor):
        if not isinstance(actor, IdentityContext):
            raise CertificateError(403, "IDENTITY_REQUIRED", "Cần danh tính từ server")
        if actor.tenant_id != self.tenant:
            raise CertificateError(403, "TENANT_REQUIRED", "Phiên không thuộc tenant đã cấu hình")
        if not actor.is_active or not actor.is_synthetic or not actor.session_id or actor.expires_at <= datetime.now(timezone.utc):
            raise CertificateError(403, "IDENTITY_NOT_ACTIVE", "Cần phiên đang hoạt động")
        self.authorize(actor)
        return StateScope(self.tenant, actor.subject_id)

    def resource(self, actor, target):
        self.scope(actor)
        target = ResourceRef.model_validate(target)
        service = self.resources[target.kind]
        from campus247.ports.identity import IdentityRole
        record = service.read(actor, target.id, staff=actor.has_role(IdentityRole.SUPPORT_OFFICER))
        if record["version"] != target.expected_version:
            raise CertificateError(409, "STALE_VERSION", "Hồ sơ đã thay đổi; cần đọc lại phiên bản")
        return record

    def preview(self, actor, namespace, key, expected_version, payload, client_id):
        scope = self.scope(actor)
        if namespace not in self.namespaces or not is_valid_uuid7(client_id):
            raise ValueError("supported service namespace and stable client UUIDv7 required")
        if type(expected_version) is not int or expected_version < 0:
            raise ValueError("explicit nonnegative version required")
        value = payload_for(namespace, payload)
        preview = create_action_preview(actor.subject_id, "assistant.state." + namespace,
            {"tenant": scope.tenant, "owner": scope.owner, "namespace": namespace, "key": key,
             "expected_version": expected_version, "payload": value, "client_id": client_id},
            session_id=actor.session_id, conversation_id=scope.tenant, tool_version="state-service.v1",
            policy_version="internal-state-only.v1", preview_id=client_id)
        return ConfirmedPreview(preview, self.tokens.mint_token(preview))

    def confirm(self, actor, prepared, *, confirmed):
        scope = self.scope(actor)
        if confirmed is not True or not isinstance(prepared, ConfirmedPreview):
            raise CertificateError(422, "EXPLICIT_CONFIRMATION_REQUIRED", "Cần xác nhận nội dung preview")
        preview = prepared.preview
        try:
            body = json.loads(preview.normalized_payload)
            namespace = body["namespace"]
            if namespace not in self.namespaces:
                raise ValueError("service namespace mismatch")
            result = self.tokens.validate_token(prepared.confirmation_token, body["client_id"], scope.owner,
                actor.session_id, scope.tenant, "assistant.state." + namespace, "state-service.v1",
                "internal-state-only.v1", "sha256:" + hashlib.sha256(preview.normalized_payload.encode()).hexdigest())
            if not result.is_valid or (body["tenant"], body["owner"]) != (scope.tenant, scope.owner):
                raise ValueError("confirmation binding invalid")
            payload = payload_for(namespace, body["payload"])
        except (ValueError, TypeError, KeyError, AttributeError):
            raise CertificateError(409, "CONFIRMATION_INVALID", "Preview không khớp phiên hoặc nội dung") from None
        self.revalidate(actor, namespace, body["key"], payload)
        guard = self.commit_guard(actor, namespace, body["key"], payload)
        options = {"guard": guard} if guard is not None else {}
        return self.store.commit(scope, namespace, body["key"], body["expected_version"], payload, body["client_id"], **options)

    def commit_guard(self, actor, namespace, key, payload):
        return None

    def revalidate(self, actor, namespace, key, payload):
        pass


class ActorSettingsService(ConfirmedStateService):
    namespaces = frozenset({"preferences"})

    def read(self, actor):
        record = self.store.get(self.scope(actor), "preferences", "account")
        return {"version": record.version if record else 0, "saved": record is not None,
                "preferences": record.payload if record else PreferencesSnapshot().model_dump(mode="json"),
                "consumer_enabled": False}

    def prepare(self, actor, preferences, expected_version, client_id):
        return self.preview(actor, "preferences", "account", expected_version, preferences, client_id)

    def revalidate(self, actor, namespace, key, payload):
        if key != "account":
            raise CertificateError(409, "SETTINGS_BINDING_INVALID", "Settings phải thuộc tài khoản hiện tại")


class GrantRequestService(ConfirmedStateService):
    namespaces = frozenset({"grant_lifecycle"})

    def prepare(self, actor, request):
        request = GrantRequest.model_validate(request)
        record = self.resource(actor, request.resource)
        if request.capability == "read_own_resource" and record["student_user_id"] != actor.subject_id:
            raise CertificateError(404, "RESOURCE_NOT_FOUND", "Tài nguyên không thuộc tài khoản này")
        if request.purpose != "source_assistance":
            raise CertificateError(409, "CONSUMER_NOT_CONFIGURED", "Consumer của lựa chọn này chưa có semantics")
        history = self.store.history(self.scope(actor), "grant_lifecycle", request.client_id, limit=1)
        if history:
            original = GrantRequestSnapshot.model_validate(history[0].payload)
            if original.request != request:
                raise CertificateError(409, "IDEMPOTENCY_CONFLICT", "Mã yêu cầu đã dùng cho nội dung khác")
            return self.preview(actor, "grant_lifecycle", request.client_id, 0, original.model_dump(mode="json"), request.client_id)
        now = datetime.now(timezone.utc)
        payload = GrantRequestSnapshot(request=request, requested_at=now.isoformat(),
            expires_at=(now + timedelta(seconds=request.requested_lifetime_seconds)).isoformat())
        return self.preview(actor, "grant_lifecycle", request.client_id, 0, payload.model_dump(mode="json"), request.client_id)

    def read(self, actor, request_id):
        record = self.store.get(self.scope(actor), "grant_lifecycle", request_id)
        if record is None:
            raise CertificateError(404, "RESOURCE_NOT_FOUND", "Không tìm thấy yêu cầu")
        value = GrantRequestSnapshot.model_validate(record.payload)
        self.resource(actor, value.request.resource)
        state = "revoked" if value.state == "revoked" else "expired" if datetime.now(timezone.utc) >= datetime.fromisoformat(value.expires_at) else "requested"
        return {"record": record, "state": state, "active": False, "action_authority": "none"}

    def prepare_revoke(self, actor, request_id, expected_version, client_id):
        record = self.store.get(self.scope(actor), "grant_lifecycle", request_id)
        if record is None:
            raise CertificateError(404, "RESOURCE_NOT_FOUND", "Không tìm thấy yêu cầu")
        if record.version != expected_version:
            raise CertificateError(409, "STALE_VERSION", "Yêu cầu đã thay đổi")
        value = GrantRequestSnapshot.model_validate(record.payload)
        if value.state == "revoked":
            raise CertificateError(409, "ALREADY_REVOKED", "Yêu cầu đã được rút lại")
        payload = value.model_copy(update={"state": "revoked", "revoked_at": datetime.now(timezone.utc).isoformat()})
        # Revocation remains possible after resource access was lost; it only
        # revokes this actor's request and never reads business data.
        return self.preview(actor, "grant_lifecycle", request_id, expected_version, payload.model_dump(mode="json"), client_id)

    def revalidate(self, actor, namespace, key, payload):
        value = GrantRequestSnapshot.model_validate(payload)
        if key != value.request.client_id:
            raise CertificateError(409, "REQUEST_BINDING_INVALID", "Yêu cầu không khớp record")
        if value.state == "requested":
            if value.request.purpose != "source_assistance":
                raise CertificateError(409, "CONSUMER_NOT_CONFIGURED", "Consumer chưa được cấu hình")
            self.resource(actor, value.request.resource)
            if datetime.now(timezone.utc) >= datetime.fromisoformat(value.expires_at):
                raise CertificateError(409, "REQUEST_EXPIRED", "Yêu cầu đã hết hạn")
        else:
            history = self.store.history(self.scope(actor), namespace, key, limit=1)
            if not history:
                raise CertificateError(404, "RESOURCE_NOT_FOUND", "Không tìm thấy yêu cầu cần rút lại")
            original = GrantRequestSnapshot.model_validate(history[0].payload)
            if (value.request, value.requested_at, value.expires_at) != (original.request, original.requested_at, original.expires_at):
                raise CertificateError(409, "REQUEST_BINDING_INVALID", "Không thể thay nội dung yêu cầu khi rút lại")


class ProposalStorageService(ConfirmedStateService):
    namespaces = frozenset({"proposal_bundle"})

    def bundle(self, actor, proposal):
        proposal = DraftProposal.model_validate(proposal)
        record = self.resource(actor, proposal.target)
        if (proposal.operation != "revise_draft" or proposal.audience != "student"
                or record["student_user_id"] != actor.subject_id or record["status"] != "DRAFT"):
            raise CertificateError(409, "PROPOSAL_CONSUMER_NOT_CONFIGURED", "Chỉ lưu candidate cho nháp riêng; staff outcome cần consumer riêng")
        for change in proposal.changes:
            actual = record["payload"].get(change.field)
            if type(actual) is not type(change.before) or actual != change.before:
                raise CertificateError(409, "PROPOSAL_BEFORE_MISMATCH", "Giá trị trước thay đổi phải khớp hồ sơ đã đọc")
        evidence = self.workflow.resolve(actor, WorkflowResolveRequest(resource=proposal.target))
        bundle = ProposalBundle(proposal=proposal, evidence=evidence)
        for change in proposal.changes:
            if change.origin != "source_reference":
                continue
            # A candidate is not a fact just because a model attached a source
            # ID. Admit only a literal span from the validated applied source;
            # paraphrases/derived numbers need a separate verified consumer.
            if proposal.target.kind != "service_request" or change.evidence.classification != "synthetic":
                raise CertificateError(409, "CANDIDATE_SOURCE_UNAVAILABLE", "Chưa có reader kiểm chứng thay đổi này")
            service = self.resources[proposal.target.kind]
            with service.repository.transaction() as tx:
                source = service.knowledge._version(tx, change.evidence.version_id)
            if type(change.candidate) is not str or len(change.candidate) < 8 or change.candidate not in source["text"]:
                raise CertificateError(409, "CANDIDATE_CLAIM_UNSUPPORTED", "Thay đổi chưa được nguồn nguyên gốc hỗ trợ")
        if self.resource(actor, proposal.target) != record or self.workflow.resolve(actor, WorkflowResolveRequest(resource=proposal.target)) != evidence:
            raise CertificateError(409, "PROPOSAL_EVIDENCE_CHANGED", "Hồ sơ, nguồn, quy tắc hoặc mẫu đã thay đổi")
        return bundle

    def prepare(self, actor, proposal, expected_version):
        if type(expected_version) is not int or expected_version != 0:
            raise ValueError("proposal snapshots are immutable; create a new candidate client ID")
        value = self.bundle(actor, proposal)
        return self.preview(actor, "proposal_bundle", value.proposal.client_id, expected_version,
                            value.model_dump(mode="json"), value.proposal.client_id)

    def revalidate(self, actor, namespace, key, payload):
        value = ProposalBundle.model_validate(payload)
        if key != value.proposal.client_id or self.bundle(actor, value.proposal) != value:
            raise CertificateError(409, "EVIDENCE_CHANGED", "Evidence đã thay đổi; cần chuẩn bị lại")

    def read(self, actor, proposal_id):
        record = self.store.get(self.scope(actor), "proposal_bundle", proposal_id)
        if record is None:
            raise CertificateError(404, "RESOURCE_NOT_FOUND", "Không tìm thấy dự thảo")
        self.revalidate(actor, "proposal_bundle", proposal_id, record.payload)
        return record
