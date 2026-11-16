"""Explicit tracking contracts; only local in-app delivery is configured."""
from datetime import datetime
from typing import Literal
from pydantic import Field, model_validator

from campus247.application.assistance.contracts import StrictDTO, ResourceRef
from campus247.application.assistance.unified_contracts import UUID


class SubscriptionSpec(StrictDTO):
    resource: ResourceRef
    trigger: Literal['feedback', 'supplement', 'status', 'deadline']
    channel: Literal['in_app'] = 'in_app'
    expires_at: str
    permission_id: UUID
    permission_version: int = Field(ge=1)
    quiet_start_hour: int = Field(default=22, ge=0, le=23)
    quiet_end_hour: int = Field(default=7, ge=0, le=23)
    utc_offset_minutes: int = Field(default=420, ge=-720, le=840)
    purpose: Literal['selected_resource_tracking'] = 'selected_resource_tracking'

    @model_validator(mode='after')
    def aware_expiry(self):
        if datetime.fromisoformat(self.expires_at).utcoffset() is None:
            raise ValueError('timezone required')
        return self


class TrackingChange(StrictDTO):
    operation: Literal['subscribe', 'stop']
    client_id: UUID
    subscription_id: UUID
    expected_version: int = Field(ge=0)
    spec: SubscriptionSpec | None = None

    @model_validator(mode='after')
    def shape(self):
        if (self.operation == 'subscribe') != (self.spec is not None):
            raise ValueError('subscribe requires spec; stop has no replacement spec')
        if self.operation == 'stop' and self.expected_version < 1:
            raise ValueError('stop requires existing version')
        return self


class BusinessTrackingEvent(StrictDTO):
    event_id: UUID
    tenant: str = Field(min_length=1, max_length=100)
    recipient_id: UUID
    audience: Literal['student', 'staff']
    resource: ResourceRef
    trigger: Literal['feedback', 'supplement', 'status', 'deadline']
    source_id: str = Field(min_length=1, max_length=200)
    source_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    changed_at: str
    # This is metadata only. Private business payloads remain at their source.
    classification: Literal['public_student', 'internal_staff']

    @model_validator(mode='after')
    def scope(self):
        if datetime.fromisoformat(self.changed_at).utcoffset() is None:
            raise ValueError('timezone required')
        if (self.audience == 'student') != (self.classification == 'public_student'):
            raise ValueError('audience/classification mismatch')
        return self


class NotificationProjection(StrictDTO):
    recipient_id: UUID
    audience: Literal['student', 'staff']
    resource: ResourceRef
    reason: str = Field(min_length=1, max_length=240)
    source_id: str = Field(min_length=1, max_length=200)
    source_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    updated_at: str
    next_action: Literal['open_resource', 'review_supplement', 'read_feedback', 'review_status']
    classification: Literal['public_student', 'internal_staff']
    action_authority: Literal['none'] = 'none'

    @model_validator(mode='after')
    def audience_binding(self):
        if (self.audience == 'student') != (self.classification == 'public_student'):
            raise ValueError('privacy mismatch')
        if datetime.fromisoformat(self.updated_at).utcoffset() is None:
            raise ValueError('timezone required')
        if any(ord(char) < 32 for char in self.reason):
            raise ValueError('plain reason required')
        return self
