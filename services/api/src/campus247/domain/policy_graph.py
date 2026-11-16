"""Source-backed discovery relations. These records never approve eligibility."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def fingerprint(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), default=str).encode()).hexdigest()


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class GraphScope(Record):
    tenant_id: str = Field(min_length=1, max_length=100)
    campus_id: str = Field(min_length=1, max_length=100)
    audiences: tuple[str, ...] = Field(min_length=1, max_length=20)
    faculties: tuple[str, ...] = Field(min_length=1, max_length=20)
    programs: tuple[str, ...] = Field(min_length=1, max_length=20)

    @field_validator("audiences", "faculties", "programs")
    @classmethod
    def nonempty(cls, values):
        if any(not x.strip() for x in values) or len(set(values)) != len(values):
            raise ValueError("nonempty unique scope required")
        return tuple(sorted(values))

    def permits(self, context):
        from campus247.domain.retrieval import RetrievalContext
        if not isinstance(context, RetrievalContext):
            return False
        scope = context.authorized_scope
        # PUBLIC is the established public corpus classification, never a
        # wildcard for another faculty/program or restricted source.
        return (scope.tenant_id == self.tenant_id and scope.campus_id == self.campus_id
            and bool(set(self.audiences) & scope.audiences)
            and bool(set(self.faculties) & scope.faculty_codes)
            and bool(set(self.programs) & scope.program_codes))


class SourceRef(Record):
    source_id: str = Field(min_length=1, max_length=100)
    document_version_id: str = Field(min_length=1, max_length=100)
    chunk_id: str = Field(min_length=1, max_length=100)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    locator: dict = Field(min_length=1)
    quote: str = Field(min_length=8, max_length=8000)


class EffectiveInterval(Record):
    """Half-open [start,end). Unknown legal dates remain explicitly unknown."""
    start: datetime | None = None
    end: datetime | None = None
    basis: SourceRef | None = None
    status: Literal["unknown", "reviewed"] = "unknown"

    @model_validator(mode="after")
    def dates(self):
        for value in (self.start, self.end):
            if value is not None and (value.tzinfo is None or value.utcoffset() is None):
                raise ValueError("aware effective date required")
        if self.end is not None and (self.start is None or self.end <= self.start):
            raise ValueError("invalid half-open interval")
        if self.status == "unknown" and (self.start or self.end or self.basis):
            raise ValueError("unknown interval cannot assert dates")
        if self.status == "reviewed" and (self.start is None or self.basis is None):
            raise ValueError("reviewed interval requires source basis")
        return self

    def contains(self, at):
        return ((self.start is None or self.start <= at)
            and (self.end is None or at < self.end))


NodeKind = Literal["PolicyDocument", "Clause", "Procedure", "Form", "OrganizationUnit",
    "Audience", "ConditionGroup", "Condition", "Exception", "EffectiveInterval"]
Relation = Literal["requires", "applies_to", "handled_by", "defined_by", "has_exception", "supersedes"]


class ConditionPredicate(Record):
    comparator: Literal[">", ">=", "<", "<=", "="]
    value: str = Field(min_length=1, max_length=40)
    unit: str = Field(min_length=1, max_length=60)


class PolicyNode(Record):
    id: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,100}$")
    kind: NodeKind
    label: str = Field(min_length=1, max_length=300)
    aliases: tuple[str, ...] = Field(default=(), max_length=20)
    scope: GraphScope
    source: SourceRef
    operator: Literal["ALL", "ANY"] | None = None
    members: tuple[str, ...] = Field(default=(), max_length=30)
    # Preserve comparators/units/qualifiers as source strings, never executable rules.
    qualifiers: tuple[str, ...] = Field(default=(), max_length=20)
    predicate: ConditionPredicate | None = None

    @model_validator(mode="after")
    def group(self):
        if self.kind == "ConditionGroup":
            if self.operator is None or not self.members or len(set(self.members)) != len(self.members):
                raise ValueError("condition group needs operator and unique members")
        elif self.operator is not None or self.members:
            raise ValueError("operator/members belong to condition group")
        if self.predicate is not None and self.kind != "Condition":
            raise ValueError("predicate belongs to condition")
        if any(not a.strip() for a in self.aliases):
            raise ValueError("empty alias")
        return self


class PolicyEdge(Record):
    id: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,100}$")
    from_id: str = Field(min_length=1, max_length=100)
    to_id: str = Field(min_length=1, max_length=100)
    relation: Relation
    source: SourceRef
    scope: GraphScope
    interval: EffectiveInterval = Field(default_factory=EffectiveInterval)
    supersession_extent: Literal["clause", "audience"] | None = None
    conflict_key: str | None = Field(default=None, max_length=150)

    @model_validator(mode="after")
    def supersession(self):
        if (self.relation == "supersedes") != (self.supersession_extent is not None):
            raise ValueError("supersedes requires explicit limited extent")
        return self


class GraphProposal(Record):
    schema_version: Literal[1] = 1
    id: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,100}$")
    author: str = Field(min_length=1, max_length=100)
    origin: Literal["llm_candidate", "manual_candidate"]
    index_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    acquired_at: datetime
    nodes: tuple[PolicyNode, ...] = Field(min_length=1, max_length=2000)
    edges: tuple[PolicyEdge, ...] = Field(min_length=1, max_length=5000)

    @field_validator("acquired_at")
    @classmethod
    def acquired(cls, value):
        if value.tzinfo is None:
            raise ValueError("aware acquisition date required")
        return value


class ReviewVerdict(Record):
    target: str = Field(min_length=1, max_length=100)
    verdict: Literal["approved", "rejected", "needs_source", "conflicting"]
    reviewer: str = Field(min_length=1, max_length=100)
    note: str = Field(min_length=8, max_length=2000)
    at: datetime


class TraversalBounds(Record):
    depth: int = Field(default=2, ge=0, le=4)
    nodes: int = Field(default=24, ge=1, le=64)
    edges: int = Field(default=32, ge=1, le=96)
    source_reads: int = Field(default=32, ge=1, le=96)


def source_fingerprint(rows):
    return fingerprint(sorted((r["source_id"], r["document_version_id"], r["chunk_id"],
        r["quote_span_hash"].removeprefix("sha256:")) for r in rows))
