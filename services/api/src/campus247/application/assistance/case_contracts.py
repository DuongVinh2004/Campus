"""Explicit human proposals; every reference is rebound by the application."""
from typing import Literal
from pydantic import Field, model_validator, field_validator
from campus247.application.assistance.contracts import StrictDTO, ResourceRef

UUID = r"^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"

class SupplementItem(StrictDTO):
    id: str = Field(pattern=r"^[a-z0-9_-]{1,80}$")
    criterion_id: str = Field(min_length=1, max_length=100)
    source_ids: list[str] = Field(min_length=1, max_length=6)
    field: Literal["reason", "purpose", "recipient", "attachments", "course_record_id", "quantity", "delivery_method", "contact_preference"]
    public_reason: str = Field(min_length=1, max_length=500)
    accepted_format: Literal["text", "text/plain", "course_reference", "integer", "delivery_method", "contact_preference"]

class HandoverSummary(StrictDTO):
    done: list[str] = Field(max_length=10)
    open: list[str] = Field(min_length=1, max_length=10)
    evidence_ids: list[str] = Field(max_length=10)
    next_action: str = Field(min_length=1, max_length=500)
    visibility: Literal["internal", "public"]
    target_queue: str = Field(min_length=1, max_length=100)
    target_actor: str = Field(pattern=UUID)

class CaseDraftPrepare(StrictDTO):
    resource: ResourceRef
    client_id: str = Field(pattern=UUID)
    expected_draft_version: int = Field(ge=0)
    student_id: str = Field(pattern=UUID)
    recipient_id: str = Field(pattern=UUID)
    operation: Literal["respond", "resolve", "reject", "approve", "request_supplement", "transfer"]
    outcome: str = Field(min_length=1, max_length=100)
    fact_source_ids: list[str] = Field(min_length=1, max_length=10)
    public_reasons: list[str] = Field(min_length=1, max_length=5)
    internal_note: str = Field(default="", max_length=2000)
    workflow_version: str = Field(min_length=1, max_length=100)
    template_version: str = Field(min_length=1, max_length=100)
    binding_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    supplement_items: list[SupplementItem] = Field(default_factory=list, max_length=12)
    handover: HandoverSummary | None = None

    @model_validator(mode="after")
    def shape(self):
        if any(not r.strip() or len(r) > 500 for r in self.public_reasons) or len("\n".join(self.public_reasons)) > 1000:
            raise ValueError("bounded non-empty public reasons required")
        if len(set(self.fact_source_ids)) != len(self.fact_source_ids):
            raise ValueError("unique source selection required")
        if (self.operation == "request_supplement") != bool(self.supplement_items):
            raise ValueError("supplement action requires exact items")
        if len({i.id for i in self.supplement_items}) != len(self.supplement_items):
            raise ValueError("unique supplement item IDs required")
        scalar_fields = [i.field for i in self.supplement_items if i.field != "attachments"]
        if len(set(scalar_fields)) != len(scalar_fields):
            raise ValueError("group requests for the same field in one item")
        if (self.operation == "transfer") != (self.handover is not None):
            raise ValueError("transfer requires an explicit selected summary")
        return self

class CaseDraftRead(StrictDTO):
    resource: ResourceRef

class CaseDraftPreview(CaseDraftRead):
    draft_version: int = Field(ge=1)
    client_id: str = Field(pattern=UUID)

class CaseConfirm(StrictDTO):
    preview_id: str = Field(pattern=UUID)
    confirmation_token: str = Field(min_length=1, max_length=4000)
    client_id: str = Field(pattern=UUID)
    confirmed: Literal[True]

    @field_validator("confirmed", mode="before")
    @classmethod
    def exact_confirmation(cls, value):
        if value is not True:
            raise ValueError("explicit JSON boolean true required")
        return value

class ReceiptRead(StrictDTO):
    client_id: str = Field(pattern=UUID)

class ItemResponse(StrictDTO):
    item_id: str = Field(min_length=1, max_length=80)
    field: str = Field(min_length=1, max_length=100)
    value: str | int

class SupplementResponse(StrictDTO):
    resource: ResourceRef
    request_id: str = Field(pattern=UUID)
    request_version: int = Field(ge=1)
    client_id: str = Field(pattern=UUID)
    responses: list[ItemResponse] = Field(min_length=1, max_length=12)
    note: str = Field(min_length=1, max_length=1000)

class StaffIntent(StrictDTO):
    resources: list[ResourceRef] = Field(max_length=20)
    surface: Literal["queue", "detail", "checklist", "editor", "error", "handover", "admin"]
    intent: Literal["read", "review", "prepare", "retry", "route", "publish"]

class BatchPrepare(StrictDTO):
    client_id: str = Field(pattern=UUID)
    items: list[CaseDraftPreview] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def exact_targets(self):
        targets = [(i.resource.kind, i.resource.id) for i in self.items]
        if len(set(targets)) != len(targets):
            raise ValueError("duplicate batch targets forbidden")
        if len({i.client_id for i in self.items}) != len(self.items):
            raise ValueError("individual stable operation IDs required")
        return self

class BatchConfirm(StrictDTO):
    batch_id: str = Field(pattern=UUID)
    target_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    confirmed: Literal[True]

    @field_validator("confirmed", mode="before")
    @classmethod
    def exact_confirmation(cls, value):
        if value is not True:
            raise ValueError("explicit JSON boolean true required")
        return value

class QueueRead(StrictDTO):
    kind: Literal["service_request", "certificate_request"]
    limit: int = Field(default=100, ge=1, le=100)

class NotificationOpen(StrictDTO):
    event_id: str = Field(pattern=UUID)
