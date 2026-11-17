"""Validated intake and immutable processing identity for the local platform."""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

PROCESSOR = "text-pdf-pages-v1:paragraph-1800-overlap-180:bge-m3"
EMBED_MODEL = "BAAI/bge-m3"
EMBED_REVISION = "5617a9f61b028005a4858fdac845db406aefb181"
RERANK_MODEL = "BAAI/bge-reranker-v2-m3"
RERANK_REVISION = "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e"
EMBED_ARTIFACT = "1eebfb28493f67bba03ce0ef64bfdc7fc5a3bd9d7493f818bb1d78cd798416b4"
MAX_UPLOAD = 50 * 1024 * 1024


def json_value(value):
    return json.loads(value) if isinstance(value, str) else value


def digest(value) -> str:
    raw = value if isinstance(value, bytes) else json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(raw).hexdigest()


class PlatformError(Exception):
    def __init__(self, status: int, code: str, detail: str):
        self.status, self.code, self.detail = status, code, detail
        super().__init__(code)


class IntakeMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(min_length=3, max_length=300)
    owner_unit: str = Field(min_length=2, max_length=160)
    canonical_uri: str = Field(min_length=3, max_length=1000)
    campus: Literal["HUCE"] = "HUCE"
    faculties: list[Literal["FIT"]] = Field(default_factory=lambda: ["FIT"], min_length=1)
    programs: list[str] = Field(min_length=1, max_length=30)
    audiences: list[Literal["STUDENT", "SUPPORT_OFFICER", "KNOWLEDGE_ADMIN", "SYSTEM_ADMIN"]] = Field(min_length=1)
    effective_from: datetime | None = None
    effective_until: datetime | None = None
    authority_level: int = Field(default=50, ge=1, le=100)
    source_id: str | None = Field(default=None, pattern=r"^[0-9a-f-]{36}$")

    @model_validator(mode="after")
    def validate_metadata(self):
        for value in (self.effective_from, self.effective_until):
            if value is not None and (value.tzinfo is None or value.utcoffset() is None):
                raise ValueError("Effective dates require a timezone")
        if self.effective_until and (not self.effective_from or self.effective_until <= self.effective_from):
            raise ValueError("Invalid effective date range")
        if any(not p.strip() or len(p) > 64 for p in self.programs):
            raise ValueError("Explicit program scope is required")
        if not self.canonical_uri.startswith(("https://", "urn:")):
            raise ValueError("Use an HTTPS source URI or an explicit urn locator")
        self.faculties = sorted(set(self.faculties))
        self.programs = sorted(set(self.programs))
        self.audiences = sorted(set(self.audiences))
        if self.effective_from:
            self.effective_from = self.effective_from.astimezone(UTC)
        if self.effective_until:
            self.effective_until = self.effective_until.astimezone(UTC)
        return self


class ReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1)
    verdict: Literal["APPROVED", "REJECTED"]
    note: str = Field(min_length=5, max_length=2000)


class PreviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operation: Literal["activate", "revoke", "rollback"]
    target_id: str = Field(pattern=r"^[0-9a-f-]{36}$")
    expected_generation: int = Field(ge=0)


class ConfirmInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    preview_id: str = Field(pattern=r"^[0-9a-f-]{36}$")
    confirmation_token: str = Field(min_length=20, max_length=4096)
    confirmed: Literal[True]


class ApplicabilityInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1)
    effective_from: datetime
    effective_until: datetime | None = None
    basis: str = Field(min_length=10,max_length=2000)

    @model_validator(mode="after")
    def validate_dates(self):
        for value in (self.effective_from,self.effective_until):
            if value and (value.tzinfo is None or value.utcoffset() is None):
                raise ValueError("Explicit timezone required")
        if self.effective_until and self.effective_until <= self.effective_from:
            raise ValueError("Invalid applicability range")
        if len(self.basis.strip()) < 10:
            raise ValueError("Source-based applicability decision required")
        return self


def review_binding(row) -> str:
    return digest({"rendition": row["rendition_sha256"], "metadata": row["metadata_sha256"],
                   "processor": row["processor_profile"]})


def metadata_binding(row) -> str:
    value = IntakeMetadata(title=row["title"], owner_unit=row["owner_unit"],
        canonical_uri=row["canonical_uri"], campus=row["campus_scope"], faculties=row["faculty_scope"],
        programs=row["program_scope"], audiences=row["audiences"], authority_level=row["authority_level"],
        effective_from=row["effective_from"], effective_until=row["effective_until"])
    return digest(value.model_dump(mode="json", exclude={"source_id"}))
