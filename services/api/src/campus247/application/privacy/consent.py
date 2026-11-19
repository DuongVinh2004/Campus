from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from typing import Any

from campus247.application.audit.writer import AuditWriter
from campus247.domain.shared.values import generate_uuid7
from campus247.ports.identity import IdentityContext, IdentityRole


class ServiceUnavailableError(Exception):
    pass


class ConsentRequiredError(Exception):
    pass


class CrossSubjectUnauthorizedError(Exception):
    pass


class LegalHoldConflictError(Exception):
    pass


class DuplicateOperationError(Exception):
    pass


@dataclass(frozen=True)
class PrivacyNoticeConfig:
    notice_id: str
    version: str
    effective_at: datetime
    status: str
    disclaimer: dict[str, Any]
    data_categories: list[str]
    purposes: list[str]
    retention_summary: list[dict[str, Any]]


@dataclass(frozen=True)
class ConsentRecord:
    id: str
    user_id: str
    purpose: str
    decision: str
    notice_version: str
    recorded_at: datetime


@dataclass(frozen=True)
class LegalHoldRecord:
    id: str
    user_id: str
    reason: str
    hold_reference: str
    created_at: datetime


@dataclass
class PrivacyOperationRecord:
    id: str
    operation_type: str
    target_subject_id: str
    requester_id: str
    purpose: str
    scope: list[str]
    status: str
    tracking_reference: str
    created_at: datetime
    requester_note: str | None = None


VALID_PURPOSES = {"QUALITY_FEEDBACK", "OPTIONAL_PERSONALIZATION", "DATA_PORTABILITY", "ACCOUNT_CLOSURE", "SERVICE_DELIVERY", "CONVERSATION_HISTORY"}
VALID_DECISIONS = {"GRANTED", "WITHDRAWN"}
VALID_OPERATIONS = {"EXPORT", "CORRECTION", "ERASURE"}
ALLOWED_SCOPES = {"ACCOUNT_CONTEXT", "CONVERSATION_CONTENT", "REQUEST_METADATA", "AUDIT_METADATA", "TICKETS", "BOOKINGS"}
CONSENT_REQUISITE_PURPOSES = {"OPTIONAL_PERSONALIZATION", "QUALITY_FEEDBACK"}


class LegalHoldRegistry:
    def __init__(self) -> None:
        self._holds: dict[str, list[LegalHoldRecord]] = {}

    def is_under_hold(self, user_id: str) -> bool:
        return bool(self._holds.get(user_id))

    def add_hold(self, user_id: str, reason: str, hold_reference: str) -> LegalHoldRecord:
        rec = LegalHoldRecord(
            id=generate_uuid7(),
            user_id=user_id,
            reason=reason,
            hold_reference=hold_reference,
            created_at=datetime.now(timezone.utc),
        )
        self._holds.setdefault(user_id, []).append(rec)
        return rec


class PrivacyConsentService:
    def __init__(
        self,
        active_notice: PrivacyNoticeConfig | None = None,
        audit_writer: AuditWriter | None = None,
        repository=None,
    ) -> None:
        self._active_notice = active_notice
        self._audit_writer = audit_writer or AuditWriter()
        self._consents: list[ConsentRecord] = []
        self._repository = repository

    def get_active_notice(self) -> PrivacyNoticeConfig:
        if not self._active_notice:
            raise ServiceUnavailableError("Active privacy notice is unavailable")
        return self._active_notice

    def list_user_consents(self, user_id: str) -> list[ConsentRecord]:
        if self._repository is not None:
            return self._repository.list_user_consents(user_id)
        return [c for c in self._consents if c.user_id == user_id]

    def has_active_consent(self, user_id: str, purpose: str) -> bool:
        if self._repository is not None:
            return self._repository.has_active_consent(user_id,purpose)
        matching = [c for c in self._consents if c.user_id == user_id and c.purpose == purpose]
        if not matching:
            return False
        # Last record determines current state
        return matching[-1].decision == "GRANTED"

    def record_consent(
        self,
        actor: IdentityContext,
        purpose: str,
        decision: str,
        notice_version: str,
    ) -> ConsentRecord:
        notice = self.get_active_notice()
        if notice_version != notice.version:
            raise ValueError(f"Notice version mismatch: expected active '{notice.version}', got '{notice_version}'")

        if purpose not in VALID_PURPOSES:
            raise ValueError(f"Unknown consent purpose: {purpose}")

        if decision not in VALID_DECISIONS:
            raise ValueError(f"Unknown consent decision: {decision}")

        if self._repository is not None:
            # The durable repository writes state, revision/audit and receipt
            # atomically; avoid a second process-local success audit afterward.
            return self._repository.record_consent(actor,purpose,decision,notice_version)

        now = datetime.now(timezone.utc)
        record = ConsentRecord(
            id=generate_uuid7(),
            user_id=actor.subject_id,
            purpose=purpose,
            decision=decision,
            notice_version=notice_version,
            recorded_at=now,
        )
        self._consents.append(record)

        self._audit_writer.record_event(
            actor_type=actor.roles[0].value if actor.roles else "STUDENT",
            actor_id=actor.subject_id,
            action_code=f"privacy.consent_{decision.lower()}",
            resource_type="consent",
            resource_id=record.id,
            outcome="SUCCESS",
            metadata={"purpose": purpose, "notice_version": notice_version},
        )

        return record


class PrivacyOperationAuthorizationService:
    def __init__(
        self,
        consent_service: PrivacyConsentService,
        legal_hold_registry: LegalHoldRegistry | None = None,
        audit_writer: AuditWriter | None = None,
    ) -> None:
        self._consent_service = consent_service
        self._legal_holds = legal_hold_registry or LegalHoldRegistry()
        self._audit_writer = audit_writer or AuditWriter()
        self._operations: dict[str, PrivacyOperationRecord] = {}

    def authorize_and_queue(
        self,
        actor: IdentityContext,
        operation_type: str,
        target_subject_id: str,
        purpose: str,
        scope: list[str],
        requester_note: str | None = None,
    ) -> PrivacyOperationRecord:
        if operation_type not in VALID_OPERATIONS:
            raise ValueError(f"Unsupported operation type: {operation_type}")

        if purpose not in VALID_PURPOSES:
            raise ValueError(f"Invalid or unapproved purpose: {purpose}")

        if not scope or not all(s in ALLOWED_SCOPES for s in scope):
            raise ValueError(f"Scope contains unapproved or overbroad data categories: {scope}")

        # Authorization: subject themselves or staff role
        is_owner = actor.subject_id == target_subject_id
        is_staff = any(r in (IdentityRole.SUPPORT_OFFICER, IdentityRole.SYSTEM_ADMIN) for r in actor.roles)
        if not is_owner and not is_staff:
            raise CrossSubjectUnauthorizedError("Caller not authorized to act on behalf of target subject")

        # Consent prerequisite check: no implicit approval
        if purpose in CONSENT_REQUISITE_PURPOSES:
            if not self._consent_service.has_active_consent(target_subject_id, purpose):
                raise ConsentRequiredError(f"No active affirmative consent granted for purpose '{purpose}'")

        # Legal hold conflict check: legal holds block erasure/deletion
        if operation_type == "ERASURE" and self._legal_holds.is_under_hold(target_subject_id):
            raise LegalHoldConflictError("Erasure cannot proceed due to active statutory or legal hold")

        # Duplicate pending operation check
        for op in self._operations.values():
            if (
                op.target_subject_id == target_subject_id
                and op.operation_type == operation_type
                and op.status in ("ACCEPTED", "PENDING")
            ):
                raise DuplicateOperationError(f"Duplicate {operation_type} operation is already in-flight")

        now = datetime.now(timezone.utc)
        op_id = generate_uuid7()
        hash_suffix = hashlib.sha256(f"{op_id}:{now.isoformat()}".encode("utf-8")).hexdigest()[:12].upper()
        tracking_ref = f"PRIV-OP-{hash_suffix}"

        record = PrivacyOperationRecord(
            id=op_id,
            operation_type=operation_type,
            target_subject_id=target_subject_id,
            requester_id=actor.subject_id,
            purpose=purpose,
            scope=scope,
            status="ACCEPTED",
            tracking_reference=tracking_ref,
            created_at=now,
            requester_note=requester_note,
        )
        self._operations[op_id] = record

        self._audit_writer.record_event(
            actor_type=actor.roles[0].value if actor.roles else "STUDENT",
            actor_id=actor.subject_id,
            action_code=f"privacy.operation_{operation_type.lower()}",
            resource_type="privacy_operation",
            resource_id=op_id,
            outcome="SUCCESS",
            metadata={
                "operation_type": operation_type,
                "purpose": purpose,
                "tracking_reference": tracking_ref,
            },
        )
        return record
