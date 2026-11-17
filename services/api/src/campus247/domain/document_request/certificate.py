"""Demo certificate form rules; no institutional eligibility is inferred."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

DISCLAIMER = "DỮ LIỆU MÔ PHỎNG — KHÔNG CÓ GIÁ TRỊ PHÁP LÝ — KHÔNG PHẢI GIẤY TỜ HUCE"
QUEUE = "HUCE_GENERAL"


class DemoAttachment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    name: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=16000)

    @field_validator("content", mode="before")
    @classmethod
    def raw_byte_limit(cls, value):
        if not isinstance(value, str) or len(value.encode("utf-8")) > 16000:
            raise ValueError("Tệp UTF-8 vượt 16 KB")
        return value

    @model_validator(mode="after")
    def text_file(self):
        if (not self.name.lower().endswith(".txt") or any(c in self.name for c in '\\/:\x00')
                or len(self.content.encode("utf-8")) > 16000):
            raise ValueError("Tệp phải là .txt UTF-8 tối đa 16 KB, tên không chứa đường dẫn")
        return self

    @field_validator("name", "content")
    @classmethod
    def clean_text(cls, value: str) -> str:
        value = value.strip()
        if not value or "\x00" in value:
            raise ValueError("Tệp minh họa phải có tên và nội dung hợp lệ")
        return value


class CertificateForm(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    purpose: str = Field(min_length=1, max_length=500)
    recipient: str = Field(min_length=1, max_length=200)
    quantity: int = Field(default=1, ge=1, le=3, strict=True)
    delivery_method: str = "DIGITAL"
    attachments: tuple[DemoAttachment, ...] = Field(default=(), max_length=3)

    @field_validator("purpose", "recipient")
    @classmethod
    def clean_text(cls, value: str) -> str:
        value = value.strip()
        if not value or "\x00" in value:
            raise ValueError("Cần nhập mục đích và nơi nộp giấy xác nhận")
        return value

    @field_validator("delivery_method")
    @classmethod
    def delivery(cls, value: str) -> str:
        if value not in {"DIGITAL", "PICKUP"}:
            raise ValueError("Phương thức nhận không được hỗ trợ")
        return value
