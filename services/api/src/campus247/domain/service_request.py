"""Validated demo inputs and transition rules, independent of HTTP and models."""
from __future__ import annotations

from datetime import datetime
from pathlib import PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from campus247.domain.service_workflow import WORKFLOWS, TEMPLATE_VERSION, staff_transition

KINDS = {definition.kind for definition in WORKFLOWS}
QUEUES = {definition.queue for definition in WORKFLOWS}
DISCLAIMER = "DỮ LIỆU MÔ PHỎNG — KHÔNG CÓ GIÁ TRỊ PHÁP LÝ — KHÔNG GỬI ĐẾN HUCE"


class StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TextAttachment(StrictInput):
    name: str = Field(min_length=5, max_length=120)
    media_type: Literal["text/plain"] = "text/plain"
    content: str = Field(min_length=1, max_length=16000)

    @model_validator(mode="after")
    def bounded(self):
        if (PurePosixPath(self.name).name != self.name or any(c in self.name for c in '\\/:\x00')
                or not self.name.lower().endswith(".txt") or self.name in {".", ".."}
                or not self.content.strip() or "\x00" in self.content
                or len(self.content.encode("utf-8")) > 16000):
            raise ValueError("Tệp phải là .txt UTF-8 tối đa 16 KB, tên không chứa đường dẫn")
        return self


class ServiceForm(StrictInput):
    kind: Literal["GRADE_APPEAL", "GENERAL_SUPPORT"]
    course_record_id: str | None = Field(default=None, max_length=100)
    reason: str = Field(min_length=1, max_length=2000)
    contact_preference: Literal["PORTAL", "EMAIL"] = "PORTAL"
    attachments: tuple[TextAttachment, ...] = Field(default=(), max_length=3)
    # Only selected text, never an implicit raw conversation transcript.
    question: str = Field(default="", max_length=2000)
    unresolved: str = Field(default="", max_length=1000)
    evidence_refs: tuple[str, ...] = Field(default=(), max_length=6)

    @field_validator("reason", "question", "unresolved")
    @classmethod
    def text(cls, value):
        if "\x00" in value:
            raise ValueError("Nội dung không hợp lệ")
        return value.strip()

    @model_validator(mode="after")
    def appropriate(self):
        definition = next(value for value in WORKFLOWS if value.kind == self.kind)
        if any(not getattr(self, field) for field in definition.required_form_fields):
            raise ValueError("Cần lý do và học phần khi phúc khảo")
        if self.kind == "GENERAL_SUPPORT" and self.course_record_id:
            raise ValueError("Hỗ trợ chung không nhận course record")
        return self


class SourceInput(StrictInput):
    title: str = Field(min_length=1, max_length=200)
    filename: str = Field(min_length=5, max_length=120)
    content: str = Field(min_length=1, max_length=16000)
    locator: str = Field(min_length=1, max_length=500)
    campus: Literal["HUCE_DEMO"] = "HUCE_DEMO"
    audience: Literal["STUDENT"] = "STUDENT"

    @model_validator(mode="after")
    def safe(self):
        TextAttachment(name=self.filename, content=self.content)
        if not self.title.strip() or not self.locator.strip() or "\x00" in self.locator:
            raise ValueError("Thiếu metadata nguồn")
        return self


class VersionInput(StrictInput):
    source_id: str
    procedure: Literal["GRADE_APPEAL", "GENERAL_SUPPORT"]
    text: str = Field(min_length=1, max_length=16000)
    mapping: str = Field(min_length=1, max_length=1000)
    effective_from: datetime
    effective_until: datetime | None = None
    candidate_text: str = Field(default="", max_length=4000)

    @model_validator(mode="after")
    def interval(self):
        if (not self.text.strip() or not self.effective_from.tzinfo
                or self.effective_until and (not self.effective_until.tzinfo or self.effective_until <= self.effective_from)):
            raise ValueError("Rendition và khoảng hiệu lực không hợp lệ")
        return self
