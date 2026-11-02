from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import math
import re
from collections.abc import Mapping, Sequence
from typing import Any


from campus247.ports.llm import EgressViolationError  # noqa: E402 -- re-exported for existing callers


class DataSensitivityClassification(StrEnum):
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    CONFIDENTIAL = "CONFIDENTIAL"
    RESTRICTED = "RESTRICTED"


@dataclass(frozen=True)
class EgressFieldClassification:
    purpose: str
    sensitivity: DataSensitivityClassification
    provider: str
    region: str
    retention: str
    necessary: bool


SECRET_PATTERNS = (
    re.compile(r"(?i)\b(bearer\s+[a-zA-Z0-9_\-\.]{16,})\b"),
    re.compile(r"\b(sk-[a-zA-Z0-9_\-]{16,}|ghp_[a-zA-Z0-9]{20,}|eyJ[a-zA-Z0-9_\-]{20,})\b"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)
from campus247.domain.contact_values import (  # noqa: E402  (shared with evidence minimization)
    EMAIL_PATTERN,
    IP_PATTERN,
    PHONE_PATTERN,
    STUDENT_ID_PATTERN,
)

APPROVED_PURPOSES = frozenset({"FAQ_ANSWERING", "SUMMARIZATION", "EMBEDDING"})
ALLOWED_EGRESS_FIELDS = frozenset(
    {
        "messages",
        "input",
        "temperature",
        "max_tokens",
        "model",
        "top_p",
        "dimensions",
        "encoding_format",
        "thinking",
        "response_format",
    }
)
PURPOSE_FIELDS = {
    "FAQ_ANSWERING": frozenset({"messages", "temperature", "max_tokens", "model", "top_p", "thinking", "response_format"}),
    "SUMMARIZATION": frozenset({"messages", "temperature", "max_tokens", "model", "top_p"}),
    "EMBEDDING": frozenset({"input", "model", "dimensions", "encoding_format"}),
}

MAX_MESSAGES = 32
MAX_MESSAGE_CHARS = 12_000
MAX_INPUT_ITEMS = 128
MAX_INPUT_CHARS = 12_000
MAX_PAYLOAD_CHARS = 100_000

SECRET_KEYS = frozenset(
    {
        "api_key",
        "apikey",
        "authorization",
        "cookie",
        "credential",
        "password",
        "private_key",
        "secret",
        "token",
    }
)
DIRECT_IDENTIFIER_KEYS = frozenset(
    {
        "actor_id",
        "address",
        "dob",
        "email",
        "full_name",
        "name",
        "phone",
        "student_id",
        "ticket_id",
        "user_id",
    }
)
REDACTED_IDENTIFIER_KEYS = frozenset(
    {
        "conversation_id",
        "internal_user_id",
        "ip_address",
        "request_id",
        "session_id",
        "turn_id",
    }
)

REASON_INVALID = "Data policy violation: outbound payload is invalid or incomplete"
REASON_PURPOSE = "Data policy violation: transmission purpose is not approved"
REASON_SECRET = "Data policy violation: sensitive credentials or secrets are prohibited"
REASON_PERSONAL = "Data policy violation: direct personal data is prohibited"
REASON_CONTENT = "Data policy violation: content is not approved for external transmission"


class EgressPolicy:
    """Classify, minimize, redact, and authorize external provider payloads."""

    def __init__(self, approved_purposes: set[str] | None = None) -> None:
        self._approved_purposes = frozenset(
            APPROVED_PURPOSES if approved_purposes is None else approved_purposes
        )

    def classify_field(self, purpose: str, field_name: str) -> EgressFieldClassification:
        """Return the non-secret metadata used by the deterministic field gate."""
        normalized = self._normalize_key(field_name)
        necessary = normalized in PURPOSE_FIELDS.get(purpose, frozenset())
        if normalized in SECRET_KEYS or normalized in DIRECT_IDENTIFIER_KEYS:
            sensitivity = DataSensitivityClassification.RESTRICTED
        elif normalized in REDACTED_IDENTIFIER_KEYS or normalized not in ALLOWED_EGRESS_FIELDS:
            sensitivity = DataSensitivityClassification.CONFIDENTIAL
        elif normalized in {"messages", "input"}:
            sensitivity = DataSensitivityClassification.INTERNAL
        else:
            sensitivity = DataSensitivityClassification.PUBLIC
        return EgressFieldClassification(
            purpose=purpose,
            sensitivity=sensitivity,
            provider="server-configured-approved-provider",
            region="server-configured-region",
            retention="provider-default-disabled",
            necessary=necessary,
        )

    @staticmethod
    def _normalize_key(value: Any) -> str:
        return str(value).strip().lower().replace("-", "_")

    @staticmethod
    def _deny(reason: str) -> None:
        raise EgressViolationError(reason)

    @staticmethod
    def _contains_personal_text(value: str) -> bool:
        email_match = EMAIL_PATTERN.search(value)
        if email_match:
            domain = email_match.group(0).rsplit("@", 1)[-1].lower()
            if not domain.endswith((".example", ".invalid", ".test")):
                return True
        return bool(
            PHONE_PATTERN.search(value)
            or IP_PATTERN.search(value)
            or STUDENT_ID_PATTERN.search(value)
        )

    def _scan_for_prohibited_data(self, value: Any, field_name: str | None = None) -> None:
        if isinstance(value, str):
            if any(pattern.search(value) for pattern in SECRET_PATTERNS):
                self._deny(REASON_SECRET)
            if field_name not in REDACTED_IDENTIFIER_KEYS and self._contains_personal_text(value):
                self._deny(REASON_PERSONAL)
            return
        if isinstance(value, Mapping):
            for key, nested in value.items():
                normalized = self._normalize_key(key)
                if normalized in SECRET_KEYS:
                    self._deny(REASON_SECRET)
                if normalized in DIRECT_IDENTIFIER_KEYS:
                    self._deny(REASON_PERSONAL)
                self._scan_for_prohibited_data(nested, normalized)
            return
        if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
            for item in value:
                self._scan_for_prohibited_data(item, field_name)
            return
        if isinstance(value, set):
            for item in sorted(value, key=repr):
                self._scan_for_prohibited_data(item, field_name)

    def _sanitize_text(self, value: Any, *, max_chars: int) -> str:
        if not isinstance(value, str) or not value.strip() or len(value) > max_chars:
            self._deny(REASON_CONTENT)
        self._scan_for_prohibited_data(value)
        return value

    def _sanitize_message_content(self, value: Any) -> str | list[dict[str, str]]:
        if isinstance(value, str):
            return self._sanitize_text(value, max_chars=MAX_MESSAGE_CHARS)
        if isinstance(value, list):
            text_parts: list[dict[str, str]] = []
            for part in value:
                if not isinstance(part, Mapping) or part.get("type") != "text":
                    continue
                text = part.get("text")
                if isinstance(text, str):
                    text_parts.append(
                        {"type": "text", "text": self._sanitize_text(text, max_chars=MAX_MESSAGE_CHARS)}
                    )
            if text_parts:
                return text_parts
        self._deny(REASON_CONTENT)

    def _sanitize_messages(self, value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list) or not value or len(value) > MAX_MESSAGES:
            self._deny(REASON_INVALID)
        messages: list[dict[str, Any]] = []
        for message in value:
            if not isinstance(message, Mapping):
                self._deny(REASON_INVALID)
            role = message.get("role")
            if role not in {"system", "developer", "user", "assistant", "tool"}:
                self._deny(REASON_INVALID)
            if "content" not in message:
                self._deny(REASON_INVALID)
            messages.append(
                {"role": role, "content": self._sanitize_message_content(message["content"])}
            )
        return messages

    def _sanitize_embedding_input(self, value: Any) -> str | list[str]:
        if isinstance(value, str):
            return self._sanitize_text(value, max_chars=MAX_INPUT_CHARS)
        if isinstance(value, list) and value and len(value) <= MAX_INPUT_ITEMS:
            return [self._sanitize_text(item, max_chars=MAX_INPUT_CHARS) for item in value]
        self._deny(REASON_INVALID)

    def _sanitize_scalar(self, field_name: str, value: Any) -> Any:
        if field_name == "model":
            if not isinstance(value, str) or not value or len(value) > 128:
                self._deny(REASON_INVALID)
            return value
        if field_name == "encoding_format":
            if value not in {"float", "base64"}:
                self._deny(REASON_INVALID)
            return value
        if field_name in {"temperature", "top_p"}:
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                self._deny(REASON_INVALID)
            maximum = 2 if field_name == "temperature" else 1
            if not 0 <= value <= maximum:
                self._deny(REASON_INVALID)
            return value
        if field_name in {"max_tokens", "dimensions"}:
            if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 8192:
                self._deny(REASON_INVALID)
            return value
        self._deny(REASON_INVALID)

    def validate_and_minimize(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            self._deny(REASON_INVALID)
        purpose = payload.get("purpose")
        if not isinstance(purpose, str) or purpose not in self._approved_purposes or purpose not in PURPOSE_FIELDS:
            self._deny(REASON_PURPOSE)
        self._scan_for_prohibited_data(payload)
        if len(repr(payload)) > MAX_PAYLOAD_CHARS:
            self._deny(REASON_INVALID)

        allowed = PURPOSE_FIELDS[purpose]
        minimized: dict[str, Any] = {}
        for field_name in (
            "messages",
            "input",
            "model",
            "temperature",
            "max_tokens",
            "top_p",
            "dimensions",
            "encoding_format",
            "thinking",
            "response_format",
        ):
            if field_name not in payload or field_name not in allowed:
                continue
            self.classify_field(purpose, field_name)
            value = payload[field_name]
            if field_name == "messages":
                minimized[field_name] = self._sanitize_messages(value)
            elif field_name == "input":
                minimized[field_name] = self._sanitize_embedding_input(value)
            elif field_name == "thinking":
                if payload.get("model") != "deepseek-flash" or not isinstance(value, dict) or value != {"type": "disabled"}:
                    self._deny(REASON_INVALID)
                minimized[field_name] = {"type": "disabled"}
            elif field_name == "response_format":
                if payload.get("model") != "deepseek-flash" or not isinstance(value, dict) or value != {"type": "json_object"}:
                    self._deny(REASON_INVALID)
                minimized[field_name] = {"type": "json_object"}
            else:
                minimized[field_name] = self._sanitize_scalar(field_name, value)

        required_field = "input" if purpose == "EMBEDDING" else "messages"
        if required_field not in minimized:
            self._deny(REASON_INVALID)
        return minimized
