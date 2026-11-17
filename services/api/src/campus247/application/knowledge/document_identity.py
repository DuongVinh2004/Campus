"""Business identity and time are independent of intake and technical versions."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from campus247.application.knowledge.platform_models import IntakeMetadata


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class ScopeAxis(StrictModel):
    kind: Literal["UNKNOWN", "ALL", "VALUES"] = "UNKNOWN"
    values: tuple[str, ...] = ()

    @model_validator(mode="after")
    def check_values(self):
        if (self.kind == "VALUES") != bool(self.values) or any(not v for v in self.values):
            raise ValueError("VALUES requires explicit members; UNKNOWN and ALL have no members")
        if len(set(self.values)) != len(self.values):
            raise ValueError("Scope members must be unique")
        return self


class ApplicabilityScope(StrictModel):
    programmes: ScopeAxis = Field(default_factory=ScopeAxis)
    cohorts: ScopeAxis = Field(default_factory=ScopeAxis)
    academic_years: ScopeAxis = Field(default_factory=ScopeAxis)


class SourceWitness(StrictModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=False)
    artifact_id: UUID
    artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    locator: dict = Field(min_length=1)
    verbatim: str = Field(min_length=1)
    text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def verify_text(self):
        from campus247.application.knowledge.platform_models import digest
        if digest(self.verbatim.encode()) != self.text_sha256:
            raise ValueError("Witness text hash mismatch")
        return self


class EffectiveInterval(StrictModel):
    # Day precision is retained; no invented midnight/UTC timestamp.
    from_day: date | None = None
    until_day: date | None = None
    # Preserve previously stored explicit zones; new decisions use the plan's
    # business zone, without converting day precision to an invented timestamp.
    timezone: Literal["Asia/Bangkok", "Asia/Ho_Chi_Minh"] = "Asia/Bangkok"
    basis: SourceWitness | None = None
    end_kind: Literal["UNKNOWN", "OPEN", "KNOWN"] = "UNKNOWN"

    @field_validator("from_day", "until_day", mode="before")
    @classmethod
    def exact_day(cls, value):
        import re
        if value is not None and not (type(value) is date or isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)):
            raise ValueError("Day precision must be explicit; timestamps/months are not silently converted")
        return value

    @model_validator(mode="after")
    def check_interval(self):
        if self.until_day and (not self.from_day or self.until_day <= self.from_day):
            raise ValueError("Effective interval must be nonempty and ordered")
        if bool(self.from_day) != bool(self.basis):
            raise ValueError("Effective date requires a source witness; absence remains unknown")
        if (self.end_kind == "KNOWN") != bool(self.until_day):
            raise ValueError("Known end requires its exact date; unknown is distinct from open")
        if self.end_kind == "OPEN" and not self.from_day:
            raise ValueError("Open interval requires a source-based start")
        return self


class EditionIdentity(StrictModel):
    tenant_id: str = Field(min_length=1)
    family_id: UUID  # Existing knowledge_source, not a second source catalog.
    issuer: str = Field(min_length=2)
    document_number: str | None = None
    issued_on: date | None = None
    scope: ApplicabilityScope = Field(default_factory=ApplicabilityScope)
    effective: EffectiveInterval = Field(default_factory=EffectiveInterval)
    verification: Literal["CANDIDATE", "VERIFIED"] = "CANDIDATE"
    identity_basis: SourceWitness | None = None

    @field_validator("issued_on", mode="before")
    @classmethod
    def issued_day(cls, value):
        return EffectiveInterval.exact_day(value)

    @model_validator(mode="after")
    def verified_identity(self):
        if self.verification == "VERIFIED" and not self.identity_basis:
            raise ValueError("Verified business identity needs a source witness")
        return self


class ObservationIdentity(StrictModel):
    tenant_id: str = Field(min_length=1)
    artifact_id: UUID
    observed_at: datetime
    source_uri: str | None = None

    @model_validator(mode="after")
    def check_time(self):
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("Observation time needs an explicit timezone")
        return self


class RenditionIdentity(StrictModel):
    edition_id: UUID
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    artifact_id: UUID
    processor_revision: str = Field(min_length=1)
    config_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    schema_revision: str = Field(min_length=1)


class StageBinding(StrictModel):
    tenant_id: str = Field(min_length=1)
    authorization_scope_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    stage: str = Field(min_length=1)
    input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    dependency_sha256: tuple[str, ...] = ()
    processor_revision: str = Field(min_length=1)
    config_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    schema_revision: str = Field(min_length=1)
    validator_revision: str = Field(min_length=1)
    model_identity: str | None = None

    @model_validator(mode="after")
    def check_dependencies(self):
        import re
        if any(not re.fullmatch(r"[0-9a-f]{64}", value) for value in self.dependency_sha256):
            raise ValueError("Full dependency hashes required")
        if self.stage == "EMBED" and not self.model_identity:
            raise ValueError("Embedding cache requires the full model/profile identity")
        return self

    def cache_key(self):
        from campus247.application.knowledge.platform_models import digest
        return digest(self.model_dump(mode="json"))


class DraftIntakeInput(StrictModel):
    # Hints never supply authority, source verification, or legal effect.
    title_hint: str | None = Field(default=None, min_length=3, max_length=300)
    source_uri: str | None = Field(default=None, max_length=1000, pattern=r"^https://[^\s]+$")


class ResolveIntakeInput(StrictModel):
    expected_revision: int = Field(ge=1)
    metadata: IntakeMetadata


class UrlIntakeInput(StrictModel):
    url: str = Field(min_length=10, max_length=1000)
    title_hint: str | None = Field(default=None, min_length=3, max_length=300)


class LinkExistingInput(StrictModel):
    expected_revision: int = Field(ge=1)
    expected_generation: int = Field(ge=0)
    expected_policy_generation: int = Field(ge=0)
    version_id: UUID
    source_uri: str = Field(min_length=10, max_length=1000)
    basis: str = Field(min_length=10, max_length=2000)
    confirmed_same_source: Literal[True]


class SeparateIntakeInput(StrictModel):
    expected_revision: int = Field(ge=1)
    reason: str = Field(min_length=10, max_length=2000)


class RecheckIntakeInput(StrictModel):
    expected_revision: int = Field(ge=1)
    expected_original_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class RefreshUrlInput(StrictModel):
    expected_original_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
