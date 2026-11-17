"""UNI-004 contracts. Proposals/references never grant execution authority.

Identity, permissions, source contents, confirmation tokens and receipts are
resolved/issued by application services, not trusted from these inputs.
"""
from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from campus247.application.assistance.contracts import EvidenceRef, ResourceRef, StrictDTO
from campus247.application.multi_agent.contracts import MultiAgentPolicy, TaskPlanProposal, validate_dag

UUID = Annotated[str, Field(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")]
Hash = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Text = Annotated[str, Field(min_length=1, max_length=2000)]
Scalar = str | int | bool | None
Workflow = Literal["STUDENT_CERTIFICATE", "GRADE_APPEAL", "GENERAL_SUPPORT"]


class WorkflowBinding(StrictDTO):
    workflow: Workflow
    version: str = Field(min_length=1, max_length=100)
    source: EvidenceRef
    effective_from: str
    effective_until: str | None = None

    @model_validator(mode="after")
    def interval(self):
        start = datetime.fromisoformat(self.effective_from)
        end = datetime.fromisoformat(self.effective_until) if self.effective_until else None
        if not start.tzinfo or end and (not end.tzinfo or end <= start):
            raise ValueError("timezone-aware nonempty effective interval required")
        return self


class CandidateFact(StrictDTO):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    value: Scalar
    origin: Literal["user_statement", "profile_reference", "document_candidate", "inference"]
    evidence: EvidenceRef | None = None
    status: Literal["candidate"] = "candidate"

    @field_validator("value")
    @classmethod
    def bounded_value(cls, value):
        if isinstance(value, str) and (len(value) > 2000 or "\x00" in value):
            raise ValueError("candidate value exceeds contract")
        return value


class IntentProposal(StrictDTO):
    schema_version: Literal["unified-intent.v1"] = "unified-intent.v1"
    goal: Text
    workflow: Workflow | None = None
    purpose: Text | None = None
    resource: ResourceRef | None = None
    constraints: list[Text] = Field(default_factory=list, max_length=8)
    facts: list[CandidateFact] = Field(default_factory=list, max_length=24)
    missing_fields: list[str] = Field(default_factory=list, max_length=24)
    clarification: Text | None = None
    status: Literal["candidate", "needs_clarification", "out_of_scope"]
    action_authority: Literal["none"] = "none"

    @model_validator(mode="after")
    def unambiguous(self):
        if not self.goal.strip() or "\x00" in self.goal or any(not value.strip() for value in self.constraints):
            raise ValueError("nonempty goal and constraints required")
        if self.status == "needs_clarification" and not self.clarification:
            raise ValueError("clarification required")
        if self.status == "candidate" and not self.workflow:
            raise ValueError("workflow must be explicit before preparing a candidate")
        keys = [fact.key for fact in self.facts]
        if len(set(keys)) != len(keys) or len(set(self.missing_fields)) != len(self.missing_fields):
            raise ValueError("duplicate facts or missing fields")
        return self


class FieldChange(StrictDTO):
    field: Literal["purpose", "recipient", "quantity", "delivery_method", "reason", "course_record_id",
                   "contact_preference", "public_response", "internal_note"]
    before: Scalar
    candidate: Scalar
    origin: Literal["user_statement", "source_reference", "inference"]
    evidence: EvidenceRef | None = None

    @model_validator(mode="after")
    def bounded(self):
        for value in (self.before, self.candidate):
            if isinstance(value, str) and (len(value) > 2000 or "\x00" in value):
                raise ValueError("field change exceeds contract")
        if self.origin == "source_reference" and not self.evidence:
            raise ValueError("source reference required")
        return self


class DraftProposal(StrictDTO):
    schema_version: Literal["unified-proposal.v1"] = "unified-proposal.v1"
    client_id: UUID
    target: ResourceRef
    workflow_binding: WorkflowBinding
    audience: Literal["student", "staff_internal"]
    operation: Literal["revise_draft", "prepare_response", "prepare_internal_note"]
    changes: list[FieldChange] = Field(min_length=1, max_length=24)
    action_authority: Literal["none"] = "none"

    @model_validator(mode="after")
    def exact_fields(self):
        certificate = {"purpose", "recipient", "quantity", "delivery_method"}
        service = {"reason", "course_record_id", "contact_preference"}
        fields = [change.field for change in self.changes]
        if len(set(fields)) != len(fields):
            raise ValueError("one proposal per field")
        if self.operation == "revise_draft":
            allowed = certificate if self.target.kind == "certificate_request" else service
        elif self.operation == "prepare_response":
            allowed = {"public_response"}
        else:
            allowed = {"internal_note"}
        if not set(fields) <= allowed:
            raise ValueError("operation/target/field mismatch")
        if self.operation != "revise_draft" and self.audience != "staff_internal":
            raise ValueError("staff drafts must remain in staff scope until public confirmation")
        expected = "STUDENT_CERTIFICATE" if self.target.kind == "certificate_request" else None
        if expected and self.workflow_binding.workflow != expected or not expected and self.workflow_binding.workflow == "STUDENT_CERTIFICATE":
            raise ValueError("workflow/target mismatch")
        for change in self.changes:
            if change.field in {"purpose","recipient","reason","course_record_id","public_response","internal_note"}:
                if type(change.candidate) is not str or not change.candidate.strip():
                    raise ValueError("text field requires a nonempty text candidate")
                maximum = {"purpose":500,"recipient":200,"course_record_id":100}.get(change.field,2000)
                if len(change.candidate) > maximum:
                    raise ValueError("candidate exceeds domain field bounds")
            if change.field == "quantity" and (type(change.candidate) is not int or not 1 <= change.candidate <= 3):
                raise ValueError("invalid quantity candidate")
            if change.field == "delivery_method" and change.candidate not in {"DIGITAL", "PICKUP"}:
                raise ValueError("invalid delivery candidate")
            if change.field == "contact_preference" and change.candidate not in {"PORTAL", "EMAIL"}:
                raise ValueError("invalid contact candidate")
        return self


class PreferencesPatch(StrictDTO):
    expected_version: int = Field(ge=1)
    locale: Literal["vi", "en"] | None = None
    reply_style: Literal["concise", "steps", "detailed"] | None = None
    format: Literal["text", "markdown"] | None = None
    custom_instructions: str | None = Field(default=None, max_length=2000)
    # A style patch is deliberately separate from consent, memory or grants.

    @model_validator(mode="after")
    def nonempty_patch(self):
        if all(getattr(self, key) is None for key in ("locale", "reply_style", "format", "custom_instructions")):
            raise ValueError("no preference changes")
        if self.custom_instructions and "\x00" in self.custom_instructions:
            raise ValueError("invalid custom instructions")
        return self


class GrantRequest(StrictDTO):
    client_id: UUID
    purpose: Literal["source_assistance", "personalization", "notifications"]
    capability: Literal["read_source", "read_own_resource", "prepare_draft", "remember_preference", "notify_resource"]
    resource: ResourceRef
    requested_lifetime_seconds: int = Field(ge=1, le=86400)
    state: Literal["requested"] = "requested"

    @model_validator(mode="after")
    def purpose_capability(self):
        allowed = {"source_assistance":{"read_source","read_own_resource","prepare_draft"},
                   "personalization":{"remember_preference"}, "notifications":{"notify_resource"}}
        if self.capability not in allowed[self.purpose]:
            raise ValueError("purpose/capability mismatch")
        return self


class TaskRequest(StrictDTO):
    schema_version: Literal["unified-task.v1"] = "unified-task.v1"
    client_id: UUID
    goal: Text
    resources: list[ResourceRef] = Field(min_length=1, max_length=8)
    plan: TaskPlanProposal
    action_authority: Literal["none"] = "none"

    @model_validator(mode="after")
    def safe_dag(self):
        refs = [(r.kind, r.id) for r in self.resources]
        if len(set(refs)) != len(refs):
            raise ValueError("duplicate resource")
        plan = self.plan.to_plan()
        if plan.tasks:
            validate_dag(plan.tasks, plan.items, MultiAgentPolicy())
        elif not plan.clarification:
            raise ValueError("taskless plan must explain clarification")
        return self


class SupplementItem(StrictDTO):
    id: str = Field(pattern=r"^SUP-[0-9]{3}$")
    criterion_id: str = Field(min_length=1, max_length=100)
    field: Literal["purpose", "recipient", "reason", "course_record_id", "attachment"]
    public_reason: Text
    required_evidence: EvidenceRef


class SupplementProposal(StrictDTO):
    client_id: UUID
    target: ResourceRef
    workflow_binding: WorkflowBinding
    items: list[SupplementItem] = Field(min_length=1, max_length=24)
    state: Literal["draft"] = "draft"
    action_authority: Literal["none"] = "none"

    @model_validator(mode="after")
    def unique_items(self):
        ids = [item.id for item in self.items]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate supplement item")
        certificate = self.target.kind == "certificate_request"
        if certificate != (self.workflow_binding.workflow == "STUDENT_CERTIFICATE"):
            raise ValueError("workflow/target mismatch")
        allowed = {"purpose","recipient","attachment"} if certificate else {"reason","course_record_id","attachment"}
        if any(item.field not in allowed or not item.public_reason.strip() for item in self.items):
            raise ValueError("supplement item does not match target or reason")
        return self


class BatchPreparationRequest(StrictDTO):
    client_id: UUID
    items: list[DraftProposal] = Field(min_length=1, max_length=20)
    mode: Literal["prepare_only"] = "prepare_only"

    @model_validator(mode="after")
    def exact_targets(self):
        targets = [(item.target.kind, item.target.id) for item in self.items]
        ids = [item.client_id for item in self.items]
        if len(set(targets)) != len(targets) or len(set(ids)) != len(ids):
            raise ValueError("batch needs exact unique targets and client IDs")
        return self


class MessagePageRequest(StrictDTO):
    conversation_id: UUID
    cursor: str | None = Field(default=None, min_length=1, max_length=256)
    limit: int = Field(default=50, ge=1, le=100)


class ConversationMetadataPatch(StrictDTO):
    expected_version: int = Field(ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    pinned: bool | None = None
    archived: bool | None = None

    @model_validator(mode="after")
    def nonempty_patch(self):
        if self.title is self.pinned is self.archived is None:
            raise ValueError("no metadata changes")
        if self.title is not None and (not self.title.strip() or "\x00" in self.title):
            raise ValueError("invalid title")
        return self


class CommitAcknowledgement(StrictDTO):
    client_id: UUID
    resource: ResourceRef
    receipt_id: UUID
    state: Literal["committed", "replayed"]
    committed_at: str

    @field_validator("committed_at")
    @classmethod
    def timezone(cls, value):
        if not datetime.fromisoformat(value).tzinfo:
            raise ValueError("commit time must carry timezone")
        return value


class AssistanceProblem(StrictDTO):
    schema_version: Literal["unified-error.v1"] = "unified-error.v1"
    status: int = Field(ge=400, le=599)
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{2,63}$")
    request_id: UUID
    retryable: bool
    detail: str = Field(min_length=1, max_length=500)


CONTRACT_MODELS = {
    model.__name__: model for model in [IntentProposal, DraftProposal, PreferencesPatch, GrantRequest,
        TaskRequest, SupplementProposal, BatchPreparationRequest, MessagePageRequest,
        ConversationMetadataPatch, CommitAcknowledgement, AssistanceProblem]
}
