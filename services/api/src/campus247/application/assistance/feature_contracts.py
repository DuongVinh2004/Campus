"""Additive UNI-007–010 payloads; existing state payloads stay byte compatible."""
from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator, model_validator

from campus247.application.assistance.contracts import StrictDTO, ResourceRef, EvidenceRef
from campus247.application.assistance.unified_contracts import UUID


class AssistantPreferences(StrictDTO):
    locale: Literal["vi", "en"] = "vi"
    reply_style: Literal["concise", "steps", "detailed"] = "concise"
    verbosity: Literal["short", "normal", "long"] = "normal"
    format: Literal["text", "markdown"] = "markdown"
    display_name: str = Field(default="", max_length=100)
    address_as: str = Field(default="", max_length=100)
    custom_instructions: str = Field(default="", max_length=2000)

    @field_validator("display_name", "address_as", "custom_instructions")
    @classmethod
    def bounded_text(cls, value):
        if any(ord(char) < 32 and char not in "\n\t" for char in value):
            raise ValueError("invalid preference text")
        return value


class ChatPreferences(StrictDTO):
    conversation_id: UUID
    audience: Literal["student", "staff"]
    preferences: AssistantPreferences
    enabled: bool = True


class LegacyImportSnapshot(StrictDTO):
    schema_version: Literal["legacy-import.v1"] = "legacy-import.v1"
    source_json: str = Field(min_length=1, max_length=48000)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    logical_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    owner_evidence: str = Field(min_length=1, max_length=100)
    classification: Literal["demo", "verified_owner"]
    thread_count: int = Field(ge=1, le=50)
    exchange_count: int = Field(ge=0, le=200)
    execution_authority: Literal["none"] = "none"
    context_eligible: Literal[False] = False


class GrantSpec(StrictDTO):
    client_id: UUID
    resource: ResourceRef
    capability: Literal["read_source", "read_own_resource", "prepare_draft"]
    purpose: Literal["source_assistance"] = "source_assistance"
    lifetime: Literal["once", "session", "timed"]
    lifetime_seconds: int = Field(default=300, ge=1, le=86400)


class GrantUse(StrictDTO):
    operation_id: UUID
    capability: Literal["read_source", "read_own_resource", "prepare_draft"]
    intent_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ActiveGrant(StrictDTO):
    schema_version: Literal["active-grant.v1"] = "active-grant.v1"
    spec: GrantSpec
    audience: Literal["student", "staff"]
    roles: list[str] = Field(min_length=1, max_length=4)
    units: list[str] = Field(max_length=20)
    session_id: str = Field(min_length=1, max_length=200)
    evidence: list[EvidenceRef] = Field(max_length=6)
    created_at: str
    expires_at: str
    state: Literal["active", "consumed", "revoked"] = "active"
    uses: list[GrantUse] = Field(default_factory=list, max_length=100)
    action_authority: Literal["read_or_prepare_only"] = "read_or_prepare_only"

    @model_validator(mode="after")
    def interval(self):
        start, end = datetime.fromisoformat(self.created_at), datetime.fromisoformat(self.expires_at)
        if (start.utcoffset() is None or end.utcoffset() is None or end <= start
                or (end-start).total_seconds() > self.spec.lifetime_seconds
                or len({use.operation_id for use in self.uses}) != len(self.uses)
                or any(use.capability != self.spec.capability for use in self.uses)
                or self.spec.lifetime == "once" and len(self.uses) > 1
                or self.state == "consumed" and (self.spec.lifetime != "once" or len(self.uses) != 1)
                or self.state == "active" and self.spec.lifetime == "once" and self.uses):
            raise ValueError("invalid grant interval or use binding")
        return self
