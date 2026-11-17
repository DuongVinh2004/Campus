"""Typed persistence inputs. Stored proposals/consents never grant authority.

This internal port is for server services; no browser-supplied owner or tenant
is accepted by an HTTP endpoint. Product permissions remain separate.
"""
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import re
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator, model_serializer

from campus247.application.assistance.contracts import StrictDTO
from campus247.application.assistance.unified_contracts import DraftProposal, GrantRequest, UUID
from campus247.application.assistance.workflow import WorkflowResolveResponse
from campus247.domain.shared.values import is_valid_uuid7
from campus247.application.assistance.feature_contracts import (
    AssistantPreferences, ChatPreferences, LegacyImportSnapshot, ActiveGrant,
)

Namespace = Literal["preferences", "consent", "grant_request", "draft", "evidence", "grant_lifecycle", "proposal_bundle", "feedback", "privacy_request", "revocation", "staff_draft", "assistant_preferences", "chat_preferences", "legacy_import", "active_grant", "conversation_metadata"]


class ConversationMetadata(StrictDTO):
    conversation_id: UUID
    audience: Literal["student"] = "student"
    title: str = Field(min_length=1, max_length=120)
    pinned: bool = False
    archived: bool = False

    @field_validator("title")
    @classmethod
    def bounded_title(cls, value):
        if value != value.strip() or any(ord(char) < 32 for char in value):
            raise ValueError("plain bounded title required")
        return value


class StorageConflict(ValueError):
    pass


class StorageUnavailable(RuntimeError):
    pass


class StorageCorrupt(RuntimeError):
    pass


@dataclass(frozen=True)
class StateScope:
    tenant: str
    owner: str

    def __post_init__(self):
        if not isinstance(self.tenant, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,99}", self.tenant):
            raise ValueError("bounded tenant required")
        if not isinstance(self.owner, str) or not is_valid_uuid7(self.owner):
            raise ValueError("owner UUIDv7 required")


class PreferencesSnapshot(StrictDTO):
    locale: Literal["vi", "en"] = "vi"
    reply_style: Literal["concise", "steps", "detailed"] = "concise"
    format: Literal["text", "markdown"] = "markdown"
    custom_instructions: str = Field(default="", max_length=2000)

    @field_validator("custom_instructions")
    @classmethod
    def no_null(cls, value):
        if "\x00" in value:
            raise ValueError("invalid custom instructions")
        return value


class ConsentSnapshot(StrictDTO):
    purpose: Literal["QUALITY_FEEDBACK", "OPTIONAL_PERSONALIZATION", "DATA_PORTABILITY", "ACCOUNT_CLOSURE", "SERVICE_DELIVERY", "CONVERSATION_HISTORY"]
    decision: Literal["GRANTED", "WITHDRAWN"]
    notice_version: str = Field(min_length=1, max_length=100)
    # A declaration is not a resource grant, memory permission or action token.
    classification: Literal["user_declaration"] = "user_declaration"


class GrantRequestSnapshot(StrictDTO):
    schema_version: Literal["grant-request-state.v1"] = "grant-request-state.v1"
    request: GrantRequest
    requested_at: str
    expires_at: str
    revoked_at: str | None = None
    state: Literal["requested", "revoked"] = "requested"
    action_authority: Literal["none"] = "none"

    @model_validator(mode="after")
    def interval(self):
        start, end = datetime.fromisoformat(self.requested_at), datetime.fromisoformat(self.expires_at)
        revoked = datetime.fromisoformat(self.revoked_at) if self.revoked_at else None
        if (start.utcoffset() is None or end.utcoffset() is None
                or (end - start).total_seconds() != self.request.requested_lifetime_seconds
                or (self.state == "revoked") != (revoked is not None)
                or revoked is not None and (revoked.utcoffset() is None or revoked < start)):
            raise ValueError("grant request interval invalid")
        return self


class ProposalBundle(StrictDTO):
    schema_version: Literal["proposal-bundle.v1"] = "proposal-bundle.v1"
    proposal: DraftProposal
    evidence: WorkflowResolveResponse
    action_authority: Literal["none"] = "none"

    @model_validator(mode="after")
    def resource_binding(self):
        target, resource = self.proposal.target, self.evidence.resource
        binding = self.evidence.binding
        proposed = self.proposal.workflow_binding
        if (target.kind, target.id, target.expected_version) != (resource.kind, resource.id, resource.version):
            raise ValueError("proposal/evidence resource mismatch")
        if (binding is None or self.evidence.binding_status != "bound"
                or proposed.workflow != resource.workflow or proposed.version != binding.workflow_version):
            raise ValueError("bound workflow evidence required")
        source = binding.source
        if (proposed.source.source_id, proposed.source.version_id, proposed.source.sha256,
                proposed.source.locator, proposed.source.classification) != (
                source.source_id, source.version_id, source.rendition_sha256, source.locator, source.classification):
            raise ValueError("proposal/evidence source mismatch")
        if (proposed.effective_from, proposed.effective_until) != (source.effective_from, source.effective_until):
            raise ValueError("proposal cannot invent source effective dates")
        if (self.proposal.audience == "staff_internal") != (resource.view == "staff"):
            raise ValueError("proposal/evidence audience mismatch")
        allowed_sources = [source, *binding.supporting_sources]
        for change in self.proposal.changes:
            if change.origin == "source_reference" and not any(
                (change.evidence.source_id, change.evidence.version_id, change.evidence.sha256,
                 change.evidence.locator, change.evidence.classification) ==
                (row.source_id, row.version_id, row.rendition_sha256, row.locator, row.classification)
                for row in allowed_sources):
                raise ValueError("field evidence must belong to the applied workflow package")
        return self


class FeedbackSnapshot(StrictDTO):
    conversation_id: UUID
    message_id: UUID
    rating: Literal["HELPFUL", "NOT_HELPFUL"]
    comment: str | None = Field(default=None, max_length=2000)
    message_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_document_version_ids: list[str] = Field(default_factory=list, max_length=20)
    model_version: Literal["unknown"] = "unknown"
    prompt_version: Literal["unknown"] = "unknown"
    training_authority: Literal["none"] = "none"


class PrivacyRequestSnapshot(StrictDTO):
    request_id: UUID
    request_type: Literal["EXPORT", "CORRECTION", "DELETION"]
    correction_summary: str | None = Field(default=None, max_length=1000)
    requester_note: str | None = Field(default=None, max_length=1000)
    status: Literal["RECEIVED"] = "RECEIVED"
    effect: Literal["queued_request_only"] = "queued_request_only"

    @model_validator(mode="after")
    def correction_present(self):
        if self.request_type == "CORRECTION" and not (self.correction_summary and self.correction_summary.strip()):
            raise ValueError("correction summary required")
        return self


class RevocationSnapshot(StrictDTO):
    token_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    reason: str = Field(min_length=1, max_length=100)
    revoked_by: UUID | None = None
    state: Literal["revoked"] = "revoked"


class StaffDraftSnapshot(StrictDTO):
    resource: WorkflowResolveResponse
    assigned_actor: UUID
    queue: str = Field(min_length=1, max_length=100)
    text: str = Field(max_length=8000)
    input_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    audience: Literal["staff_internal"] = "staff_internal"
    action_authority: Literal["none"] = "none"

    @model_serializer(mode="wrap")
    def preserve_legacy_bytes(self, serialize):
        value = serialize(self)
        if self.input_sha256 is None:
            value.pop("input_sha256", None)
        return value

    @model_validator(mode="after")
    def staff_scope(self):
        if self.resource.resource.view != "staff" or "\x00" in self.text:
            raise ValueError("staff-only bounded draft required")
        return self


PAYLOAD_MODELS = {"preferences": PreferencesSnapshot, "consent": ConsentSnapshot,
                  "grant_request": GrantRequest, "draft": DraftProposal, "evidence": WorkflowResolveResponse,
                  "grant_lifecycle": GrantRequestSnapshot, "proposal_bundle": ProposalBundle,
                  "feedback": FeedbackSnapshot, "privacy_request": PrivacyRequestSnapshot,
                  "revocation": RevocationSnapshot, "staff_draft": StaffDraftSnapshot,
                  "assistant_preferences": AssistantPreferences, "chat_preferences": ChatPreferences,
                  "legacy_import": LegacyImportSnapshot, "active_grant": ActiveGrant,
                  "conversation_metadata": ConversationMetadata}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def payload_for(namespace, value):
    if namespace not in PAYLOAD_MODELS:
        raise ValueError("unknown state namespace")
    payload = PAYLOAD_MODELS[namespace].model_validate(value).model_dump(mode="json")
    if len(json.dumps(payload, ensure_ascii=False).encode()) > 65536:
        raise ValueError("state payload exceeds storage bound")
    return payload


def identity_key(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_:.\-]{0,99}", value):
        raise ValueError("bounded explicit state key required")
    return value


class StoredState(StrictDTO):
    schema_version: Literal["unified-state.v1"] = "unified-state.v1"
    tenant: str
    owner: UUID
    namespace: Namespace
    key: str
    version: int = Field(ge=1)
    payload: dict[str, Any]
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    committed_at: str

    @model_validator(mode="after")
    def integrity(self):
        StateScope(self.tenant, self.owner)
        identity_key(self.key)
        at = datetime.fromisoformat(self.committed_at)
        if at.utcoffset() is None or payload_for(self.namespace, self.payload) != self.payload or digest(self.payload) != self.sha256:
            raise ValueError("state binding invalid")
        payload = self.payload
        bindings = {"privacy_request":lambda:payload["request_id"], "grant_lifecycle":lambda:payload["request"]["client_id"],
                    "proposal_bundle":lambda:payload["proposal"]["client_id"], "revocation":lambda:payload["token_sha256"],
                    "staff_draft":lambda:payload["resource"]["resource"]["id"],
                    "chat_preferences":lambda:payload["conversation_id"],
                    "conversation_metadata":lambda:payload["conversation_id"],
                    "legacy_import":lambda:payload["logical_sha256"],
                    "active_grant":lambda:payload["spec"]["client_id"]}
        if self.namespace in bindings and bindings[self.namespace]() != self.key:
            raise ValueError("state resource/key mismatch")
        if self.namespace == "assistant_preferences" and self.key != "account":
            raise ValueError("account preferences key required")
        if self.namespace == "staff_draft" and payload["assigned_actor"] != self.owner:
            raise ValueError("draft owner mismatch")
        return self


class StateReceipt(StrictDTO):
    schema_version: Literal["unified-state-receipt.v1"] = "unified-state-receipt.v1"
    receipt_id: UUID
    tenant: str
    owner: UUID
    client_id: str = Field(min_length=8, max_length=100)
    namespace: Namespace
    key: str
    version: int = Field(ge=1)
    payload_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    committed_at: str
    state: Literal["committed"] = "committed"
    is_replay: bool = False

    @model_validator(mode="after")
    def binding(self):
        StateScope(self.tenant, self.owner)
        identity_key(self.key)
        identity_key(self.client_id)
        if datetime.fromisoformat(self.committed_at).utcoffset() is None:
            raise ValueError("receipt timestamp requires timezone")
        return self
