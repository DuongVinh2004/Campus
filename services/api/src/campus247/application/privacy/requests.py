from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib

from campus247.application.audit.writer import AuditWriter
from campus247.domain.shared.values import generate_uuid7, is_valid_uuid7
from campus247.ports.identity import IdentityContext

VALID_REQUEST_TYPES = {"EXPORT", "CORRECTION", "DELETION"}


@dataclass
class PrivacyRequestRecord:
    id: str
    requester_user_id: str
    request_type: str
    status: str
    tracking_reference: str
    received_at: datetime
    updated_at: datetime
    correction_summary: str | None = None
    requester_note: str | None = None
    internal_notes: str | None = None
    next_action: str | None = None


@dataclass(frozen=True)
class PrivacyRequestReceipt:
    request_id: str
    request_type: str
    status: str
    received_at: str
    tracking_reference: str


@dataclass(frozen=True)
class PrivacyRequestStatusView:
    request_id: str
    request_type: str
    status: str
    received_at: str
    updated_at: str
    next_action: str | None = None


class PrivacyRequestService:
    def __init__(self, audit_writer: AuditWriter | None = None, repository=None) -> None:
        self._audit_writer = audit_writer or AuditWriter()
        self._requests: dict[str, PrivacyRequestRecord] = {}
        self._repository = repository

    def get_raw_record(self, request_id: str) -> PrivacyRequestRecord | None:
        if self._repository is not None:
            raise ValueError("durable privacy records require an authenticated owner")
        return self._requests.get(request_id)

    def create_request(
        self,
        actor: IdentityContext,
        request_type: str,
        correction_summary: str | None = None,
        requester_note: str | None = None,
        client_id: str | None = None,
    ) -> tuple[PrivacyRequestRecord, PrivacyRequestReceipt]:
        if request_type not in VALID_REQUEST_TYPES:
            raise ValueError(f"Invalid request_type: {request_type}")

        if request_type == "CORRECTION" and not (correction_summary and correction_summary.strip()):
            raise ValueError("correction_summary is required for CORRECTION requests")

        if self._repository is not None:
            record = self._repository.create(actor,request_type,
                correction_summary.strip() if correction_summary else None,
                requester_note.strip() if requester_note else None,client_id)
            return record, PrivacyRequestReceipt(record.id,record.request_type,record.status,
                record.received_at.isoformat(),record.tracking_reference)

        now = datetime.now(timezone.utc)
        req_id = generate_uuid7()
        hash_suffix = hashlib.sha256(f"{req_id}:{now.isoformat()}".encode("utf-8")).hexdigest()[:12].upper()
        tracking_ref = f"PRIV-{hash_suffix}"

        record = PrivacyRequestRecord(
            id=req_id,
            requester_user_id=actor.subject_id,
            request_type=request_type,
            status="RECEIVED",
            tracking_reference=tracking_ref,
            received_at=now,
            updated_at=now,
            correction_summary=correction_summary.strip() if correction_summary else None,
            requester_note=requester_note.strip() if requester_note else None,
            next_action="Yêu cầu đang chờ cán bộ phụ trách quyền riêng tư xác minh thông tin.",
        )
        self._requests[req_id] = record

        self._audit_writer.record_event(
            actor_type=actor.roles[0].value if actor.roles else "STUDENT",
            actor_id=actor.subject_id,
            action_code=f"privacy.request_{request_type.lower()}",
            resource_type="privacy_request",
            resource_id=req_id,
            outcome="SUCCESS",
            metadata={"tracking_reference": tracking_ref},
        )

        receipt = PrivacyRequestReceipt(
            request_id=record.id,
            request_type=record.request_type,
            status="RECEIVED",
            received_at=record.received_at.isoformat(),
            tracking_reference=record.tracking_reference,
        )
        return record, receipt

    def get_my_request_status(
        self,
        actor: IdentityContext,
        request_id: str,
    ) -> PrivacyRequestStatusView | None:
        if not is_valid_uuid7(request_id):
            return None
        rec = self._repository.read(actor,request_id) if self._repository is not None else self._requests.get(request_id)
        if not rec or rec.requester_user_id != actor.subject_id:
            return None

        return PrivacyRequestStatusView(
            request_id=rec.id,
            request_type=rec.request_type,
            status=rec.status,
            received_at=rec.received_at.isoformat(),
            updated_at=rec.updated_at.isoformat(),
            next_action=rec.next_action,
        )
