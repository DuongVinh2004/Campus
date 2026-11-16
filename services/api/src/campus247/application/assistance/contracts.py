from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class ResourceRef(StrictDTO):
    kind: Literal["service_request", "certificate_request"]
    id: str = Field(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
    expected_version: int = Field(ge=1)


class AssistanceRequest(StrictDTO):
    schema_version: Literal["unified-assistance.v1"] = "unified-assistance.v1"
    surface: Literal["service", "certificate"]
    resource: ResourceRef
    field: Literal["reason", "course_record_id", "contact_preference", "purpose", "recipient", "quantity", "delivery_method"] | None = None

    @model_validator(mode="after")
    def consistent_context(self):
        expected = "service_request" if self.surface == "service" else "certificate_request"
        fields = {"reason", "course_record_id", "contact_preference"} if self.surface == "service" else {"purpose", "recipient", "quantity", "delivery_method"}
        if self.resource.kind != expected or self.field is not None and self.field not in fields:
            raise ValueError("surface/resource/field mismatch")
        return self


class EvidenceRef(StrictDTO):
    source_id: str = Field(min_length=1, max_length=100)
    version_id: str = Field(min_length=1, max_length=100)
    locator: str = Field(min_length=1, max_length=1000)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    classification: Literal["synthetic", "public_snapshot"]


class ResourceState(StrictDTO):
    kind: Literal["service_request", "certificate_request"]
    id: str
    version: int = Field(ge=1)
    status: Literal["DRAFT", "PENDING_CONFIRMATION", "SUBMITTED", "VALIDATING", "PROCESSING", "WAITING_STUDENT", "READY", "REJECTED", "FULFILLED", "CANCELLED"]
    workflow: Literal["GRADE_APPEAL", "GENERAL_SUPPORT", "STUDENT_CERTIFICATE"]
    view: Literal["student", "staff"]


class AssistanceResponse(StrictDTO):
    schema_version: Literal["unified-assistance.v1"] = "unified-assistance.v1"
    status: Literal["observed", "source_changed", "missing_source"]
    resource: ResourceState
    evidence: list[EvidenceRef] = Field(default_factory=list, max_length=6)
    guidance: str = Field(max_length=20000)
    limitations: list[str] = Field(max_length=8)
    # Fixed read-only navigation, not executable model output or approval.
    open_path: str = Field(pattern=r"^/(services|tickets)\?request=[0-9a-f-]{36}$")
    action_authority: Literal["none"] = "none"
