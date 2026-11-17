"""Internal staff evidence: declarations, rule checks and review stay distinct."""
from typing import Literal, Any
from pydantic import Field
from campus247.application.assistance.contracts import StrictDTO, ResourceRef

Hash = str
EvidenceState = Literal["unchecked", "checked", "missing_source", "error", "conflicting"]


class StaffSource(StrictDTO):
    id: str
    kind: Literal["record", "workflow"]
    version: str
    locator: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    classification: Literal["synthetic", "public_snapshot"]


class StaffFinding(StrictDTO):
    id: str
    label: str
    layer: Literal["deterministic", "officer_review"]
    state: EvidenceState
    reason: str
    dependency_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_ids: list[str]
    reviewed_by: str | None = None
    reviewed_at: str | None = None
    note: str | None = None


class StaffRead(StrictDTO):
    resource: ResourceRef


class StaffReview(StaffRead):
    criterion_id: str = Field(min_length=1, max_length=100)
    binding_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    dependency_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    verdict: Literal["checked", "missing_source", "conflicting"]
    note: str = Field(min_length=1, max_length=1000)
    client_id: str = Field(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")


class StaffSourceRead(StaffRead):
    binding_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_id: str = Field(min_length=1, max_length=100)


class StaffDossier(StrictDTO):
    schema_version: Literal["staff-workspace.v1"] = "staff-workspace.v1"
    resource: ResourceRef
    student_id: str
    tenant: str
    queue: str
    assigned_actor: str | None
    classification: Literal["synthetic"] = "synthetic"
    purpose: str | None
    facts: list[dict[str, Any]]
    timeline: list[dict[str, Any]]
    documents: list[dict[str, Any]]
    sources: list[StaffSource]
    findings: list[StaffFinding]
    ai_proposals: list[dict[str, Any]] = Field(default_factory=list)
    ai_state: Literal["unavailable"] = "unavailable"
    readiness: Literal["ready", "needs_verification", "missing", "waiting", "blocked"]
    reasons: list[str]
    next_action: str
    binding_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    workflow_version: str
    criteria_version: Literal["staff-criteria.v1"] = "staff-criteria.v1"
    delta: dict[str, Any]
    capabilities: dict[str, str]
    action_authority: Literal["none"] = "none"
