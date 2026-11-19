from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import StrEnum
import re

from campus247.domain.shared.values import generate_uuid7, is_valid_uuid7

PATTERN_IDENTIFIER = re.compile(r"^[A-Z][A-Z0-9_]{1,63}$")


class DocumentDeliveryMethod(StrEnum):
    DIGITAL = "DIGITAL"
    PICKUP = "PICKUP"


class DocumentRequestStatus(StrEnum):
    DRAFT = "DRAFT"
    PENDING_CONFIRMATION = "PENDING_CONFIRMATION"
    SUBMITTED = "SUBMITTED"
    VALIDATING = "VALIDATING"
    PROCESSING = "PROCESSING"
    WAITING_STUDENT = "WAITING_STUDENT"
    READY = "READY"
    FULFILLED = "FULFILLED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


TERMINAL_STATES = {
    DocumentRequestStatus.FULFILLED,
    DocumentRequestStatus.REJECTED,
    DocumentRequestStatus.CANCELLED,
}


class InvalidDocumentRequestValidationError(ValueError):
    pass


class InvalidDocumentRequestStateError(Exception):
    pass


@dataclass(frozen=True)
class DocumentRequest:
    id: str
    student_user_id: str
    document_type: str
    purpose_code: str
    delivery_method: DocumentDeliveryMethod
    status: DocumentRequestStatus
    created_at: datetime
    updated_at: datetime
    action_execution_id: str | None = None
    ticket_id: str | None = None
    submitted_at: datetime | None = None
    version: int = 1
    is_synthetic: bool = True
    disclaimer: str = "DỮ LIỆU MÔ PHỎNG — KHÔNG CÓ GIÁ TRỊ"

    def __post_init__(self) -> None:
        if not is_valid_uuid7(self.student_user_id):
            raise InvalidDocumentRequestValidationError(
                f"student_user_id must be a valid UUIDv7 string, got: {self.student_user_id}"
            )
        if not PATTERN_IDENTIFIER.match(self.document_type):
            raise InvalidDocumentRequestValidationError(
                f"document_type must match pattern '^[A-Z][A-Z0-9_]{{1,63}}$', got: {self.document_type}"
            )
        if not PATTERN_IDENTIFIER.match(self.purpose_code):
            raise InvalidDocumentRequestValidationError(
                f"purpose_code must match pattern '^[A-Z][A-Z0-9_]{{1,63}}$', got: {self.purpose_code}"
            )

    @classmethod
    def create_draft(
        cls,
        student_user_id: str,
        document_type: str,
        purpose_code: str,
        delivery_method: DocumentDeliveryMethod | str = DocumentDeliveryMethod.DIGITAL,
    ) -> DocumentRequest:
        now = datetime.now(timezone.utc)
        return cls(
            id=generate_uuid7(),
            student_user_id=student_user_id,
            document_type=document_type,
            purpose_code=purpose_code,
            delivery_method=DocumentDeliveryMethod(delivery_method),
            status=DocumentRequestStatus.DRAFT,
            created_at=now,
            updated_at=now,
            version=1,
        )

    def _transition_to(self, new_status: DocumentRequestStatus, **kwargs) -> DocumentRequest:
        if self.status in TERMINAL_STATES:
            raise InvalidDocumentRequestStateError(
                f"Cannot transition from terminal state {self.status}"
            )
        now = datetime.now(timezone.utc)
        return replace(self, status=new_status, updated_at=now, version=self.version + 1, **kwargs)

    def _check_terminal(self) -> None:
        if self.status in TERMINAL_STATES:
            raise InvalidDocumentRequestStateError(
                f"Cannot transition from terminal state {self.status}"
            )

    def request_confirmation(self) -> DocumentRequest:
        self._check_terminal()
        if self.status != DocumentRequestStatus.DRAFT:
            raise InvalidDocumentRequestStateError(
                f"Cannot request confirmation from state {self.status}"
            )
        return self._transition_to(DocumentRequestStatus.PENDING_CONFIRMATION)

    def revise_draft(self) -> DocumentRequest:
        if self.status not in (DocumentRequestStatus.DRAFT, DocumentRequestStatus.PENDING_CONFIRMATION):
            raise InvalidDocumentRequestStateError(f"Cannot edit draft from state {self.status}")
        return self._transition_to(DocumentRequestStatus.DRAFT)

    def confirm_submit(self, action_execution_id: str, ticket_id: str | None = None) -> DocumentRequest:
        self._check_terminal()
        if self.status != DocumentRequestStatus.PENDING_CONFIRMATION:
            raise InvalidDocumentRequestStateError(
                f"Cannot confirm submit from state {self.status}"
            )
        now = datetime.now(timezone.utc)
        return self._transition_to(
            DocumentRequestStatus.SUBMITTED,
            action_execution_id=action_execution_id,
            ticket_id=ticket_id,
            submitted_at=now,
        )

    def start_validation(self) -> DocumentRequest:
        if self.status != DocumentRequestStatus.SUBMITTED:
            raise InvalidDocumentRequestStateError(
                f"Cannot start validation from state {self.status}"
            )
        return self._transition_to(DocumentRequestStatus.VALIDATING)

    def start_processing(self) -> DocumentRequest:
        if self.status != DocumentRequestStatus.VALIDATING:
            raise InvalidDocumentRequestStateError(
                f"Cannot start processing from state {self.status}"
            )
        return self._transition_to(DocumentRequestStatus.PROCESSING)

    def mark_ready(self) -> DocumentRequest:
        if self.status != DocumentRequestStatus.PROCESSING:
            raise InvalidDocumentRequestStateError(
                f"Cannot mark ready from state {self.status}"
            )
        return self._transition_to(DocumentRequestStatus.READY)

    def request_supplement(self) -> DocumentRequest:
        if self.status not in (DocumentRequestStatus.VALIDATING, DocumentRequestStatus.PROCESSING):
            raise InvalidDocumentRequestStateError(f"Cannot request supplement from state {self.status}")
        return self._transition_to(DocumentRequestStatus.WAITING_STUDENT)

    def submit_supplement(self) -> DocumentRequest:
        if self.status != DocumentRequestStatus.WAITING_STUDENT:
            raise InvalidDocumentRequestStateError(f"Cannot supplement from state {self.status}")
        return self._transition_to(DocumentRequestStatus.SUBMITTED)

    def fulfill(self) -> DocumentRequest:
        if self.status != DocumentRequestStatus.READY:
            raise InvalidDocumentRequestStateError(
                f"Cannot fulfill from state {self.status}"
            )
        return self._transition_to(DocumentRequestStatus.FULFILLED)

    def reject(self, reason_code: str) -> DocumentRequest:
        if self.status not in (DocumentRequestStatus.VALIDATING, DocumentRequestStatus.PROCESSING):
            raise InvalidDocumentRequestStateError(
                f"Cannot reject from state {self.status}"
            )
        return self._transition_to(DocumentRequestStatus.REJECTED)

    def cancel(self) -> DocumentRequest:
        if self.status not in (
            DocumentRequestStatus.DRAFT,
            DocumentRequestStatus.PENDING_CONFIRMATION,
            DocumentRequestStatus.SUBMITTED,
        ):
            raise InvalidDocumentRequestStateError(
                f"Cannot cancel from state {self.status}"
            )
        return self._transition_to(DocumentRequestStatus.CANCELLED)
