"""Typed durable auxiliary ports sharing state/revision/receipt transactions."""
import hashlib
import re
from dataclasses import asdict
from datetime import UTC, datetime

from campus247.application.assistance.state_storage import (
    StateScope,
    StorageConflict,
    StorageCorrupt,
    StorageUnavailable,
    digest,
)
from campus247.application.conversations.feedback import (
    AnswerFeedbackReceipt,
    AnswerFeedbackReference,
    FeedbackRating,
    FeedbackStorageError,
)
from campus247.application.identity.session_service import RevocationStoreError
from campus247.application.privacy.consent import ServiceUnavailableError
from campus247.application.privacy.requests import PrivacyRequestRecord
from campus247.domain.shared.values import generate_uuid7, is_valid_uuid7
from campus247.infrastructure.repositories.sqlite_actor_state import (
    SQLiteActorStateStore,
)
from campus247.ports.identity import IdentityContext

SYSTEM_REVOCATION_OWNER = "019a0000-0000-7000-8000-000000000007"
FAILURES = (StorageUnavailable, StorageCorrupt, StorageConflict)


class ActorRepository:
    def __init__(self, store, *, tenant):
        if not isinstance(store, SQLiteActorStateStore):
            raise TypeError("typed durable actor store required")
        StateScope(tenant, SYSTEM_REVOCATION_OWNER)
        self.store, self.tenant = store, tenant

    def scope(self, actor):
        if (not isinstance(actor, IdentityContext) or not actor.is_synthetic or not actor.is_active
                or actor.tenant_id != self.tenant or not actor.session_id or actor.expires_at <= datetime.now(UTC)):
            raise PermissionError("active server identity in configured tenant required")
        return StateScope(self.tenant, actor.subject_id)


class SQLitePrivacyRequestRepository(ActorRepository):
    def create(self, actor, request_type, correction_summary, requester_note, client_id):
        scope = self.scope(actor)
        identifier = client_id if client_id is not None else generate_uuid7()
        if not is_valid_uuid7(identifier):
            raise ValueError("stable request UUIDv7 required")
        payload = {"request_id": identifier, "request_type": request_type,
                   "correction_summary": correction_summary, "requester_note": requester_note}
        try:
            self.store.commit(scope, "privacy_request", identifier, 0, payload, identifier)
            return self.read(actor, identifier)
        except StorageConflict:
            raise
        except FAILURES:
            raise ServiceUnavailableError("PRIVACY_STORAGE_UNAVAILABLE") from None

    def read(self, actor, identifier):
        try:
            state = self.store.get(self.scope(actor), "privacy_request", identifier)
            if state is None:
                return None
            value = state.payload
            if value["request_id"] != identifier:
                raise StorageCorrupt("PRIVACY_REQUEST_BINDING_INVALID")
            timestamp = datetime.fromisoformat(state.committed_at)
            return PrivacyRequestRecord(id=identifier, requester_user_id=actor.subject_id,
                request_type=value["request_type"], status=value["status"],
                tracking_reference="PRIV-" + hashlib.sha256(identifier.encode()).hexdigest()[:12].upper(),
                received_at=timestamp, updated_at=timestamp, correction_summary=value["correction_summary"],
                requester_note=value["requester_note"], next_action="Yêu cầu đang chờ cán bộ phụ trách quyền riêng tư xác minh thông tin.")
        except FAILURES:
            raise ServiceUnavailableError("PRIVACY_STORAGE_UNAVAILABLE") from None


class SQLiteFeedbackRepository(ActorRepository):
    def record(self, owner, conversation_id, message, rating, comment, client_id):
        identifier = client_id if client_id is not None else generate_uuid7()
        if not is_valid_uuid7(identifier):
            raise ValueError("stable feedback UUIDv7 required")
        versions = sorted({str(c.to_dict()["citation"]["document_version_id"]) for c in message.citations})
        payload = {"conversation_id": conversation_id, "message_id": message.id, "rating": FeedbackRating(rating).value,
            "comment": comment.strip() if comment and comment.strip() else None,
            "message_sha256": digest(asdict(message) | {"created_at": message.created_at.isoformat(),
                "redacted_at": message.redacted_at.isoformat() if message.redacted_at else None}),
            "source_document_version_ids": versions}
        # asdict includes nested frozen citation metadata, never raw model input.
        try:
            scope = StateScope(self.tenant, owner)
            self.store.commit(scope, "feedback", identifier, 0, payload, identifier)
            return self.read(owner, conversation_id, message.id, identifier)
        except StorageConflict:
            raise
        except FAILURES:
            raise FeedbackStorageError("FEEDBACK_STORAGE_UNAVAILABLE") from None

    def read(self, owner, conversation_id, message_id, identifier):
        try:
            value = self.store.get(StateScope(self.tenant, owner), "feedback", identifier)
            if value is None or (value.payload["conversation_id"], value.payload["message_id"]) != (conversation_id, message_id):
                raise KeyError("Feedback not found")
            payload = value.payload
            return AnswerFeedbackReceipt(id=identifier, conversation_id=conversation_id, rating=FeedbackRating(payload["rating"]),
                comment_recorded=bool(payload["comment"]), answer_reference=AnswerFeedbackReference(answer_id=message_id,
                    source_document_version_ids=payload["source_document_version_ids"], model_version=payload["model_version"],
                    prompt_version=payload["prompt_version"]), recorded_at=datetime.fromisoformat(value.committed_at))
        except FAILURES:
            raise FeedbackStorageError("FEEDBACK_STORAGE_UNAVAILABLE") from None


class SQLiteRevocationStore(ActorRepository):
    def record_revocation(self, key, *, reason="logout", actor_id=None):
        if not re.fullmatch(r"[0-9a-f]{64}", key):
            raise ValueError("only token SHA256 may be persisted")
        try:
            return self.store.commit(StateScope(self.tenant, SYSTEM_REVOCATION_OWNER), "revocation", key, 0,
                {"token_sha256": key, "reason": reason, "revoked_by": actor_id}, "revoke:" + key)
        except FAILURES:
            raise RevocationStoreError("REVOCATION_STORAGE_UNAVAILABLE") from None

    def revoke(self, key):
        self.record_revocation(key)

    def is_revoked(self, key):
        if not re.fullmatch(r"[0-9a-f]{64}", key):
            return False
        try:
            value = self.store.get(StateScope(self.tenant, SYSTEM_REVOCATION_OWNER), "revocation", key)
            if value is not None and value.payload["token_sha256"] != key:
                raise StorageCorrupt("REVOCATION_BINDING_INVALID")
            return value is not None
        except FAILURES:
            raise RevocationStoreError("REVOCATION_STORAGE_UNAVAILABLE") from None
