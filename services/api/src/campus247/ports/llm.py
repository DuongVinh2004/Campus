from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol


class PrivacyClass(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    PERSONAL_REDACTED = "personal_redacted"


class FinishReason(StrEnum):
    STOP = "stop"
    LENGTH = "length"
    CONTENT_FILTER = "content_filter"
    TOOL_CALL = "tool_call"
    ERROR = "error"


class LlmResponseStatus(StrEnum):
    COMPLETED = "completed"
    INCOMPLETE = "incomplete"
    FAILED = "failed"


class LlmEventType(StrEnum):
    RESPONSE_STARTED = "response_started"
    TEXT_DELTA = "text_delta"
    TOOL_ARGUMENTS_DELTA = "tool_arguments_delta"
    OUTPUT_ITEM_COMPLETED = "output_item_completed"
    USAGE_FINAL = "usage_final"
    RESPONSE_COMPLETED = "response_completed"
    RESPONSE_INCOMPLETE = "response_incomplete"
    RESPONSE_FAILED = "response_failed"


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass(frozen=True)
class ToolCandidate:
    call_id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LlmRequest:
    request_id: str
    route_id: str
    model_profile: str
    system_instructions: str
    input_items: tuple[dict[str, Any], ...]
    output_schema: dict[str, Any] | None = None
    allowed_tools: tuple[dict[str, Any], ...] = ()
    tool_choice: str | None = None
    temperature: float = 0.0
    max_output_tokens: int = 1024
    deadline_ms: int = 10000
    privacy_class: PrivacyClass = PrivacyClass.PUBLIC
    trace_context: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.max_output_tokens <= 0:
            raise ValueError(f"max_output_tokens must be positive, got {self.max_output_tokens}")
        if self.deadline_ms <= 0:
            raise ValueError(f"deadline_ms must be positive, got {self.deadline_ms}")


@dataclass(frozen=True)
class LlmResponse:
    status: LlmResponseStatus
    provider_id: str
    model_id: str
    provider_request_id: str | None = None
    output_text: str | None = None
    structured_output: dict[str, Any] | None = None
    tool_candidates: tuple[ToolCandidate, ...] = ()
    finish_reason: FinishReason = FinishReason.STOP
    usage: TokenUsage = field(default_factory=TokenUsage)
    latency_ms: int = 0
    attempt: int = 1


@dataclass(frozen=True)
class LlmEvent:
    event_type: LlmEventType
    delta: str | None = None
    tool_delta: dict[str, Any] | None = None
    usage: TokenUsage | None = None
    status: LlmResponseStatus | None = None
    error_message: str | None = None


@dataclass(frozen=True)
class ModelCapabilities:
    provider_id: str
    model_id: str
    supports_structured_output: bool = True
    supports_function_tools: bool = True
    supports_streaming: bool = True
    supports_images: bool = False
    supports_stateless_requests: bool = True
    context_tokens: int = 32768
    max_output_tokens: int = 4096


class LlmGateway(Protocol):
    async def generate(self, request: LlmRequest) -> LlmResponse:
        ...

    async def stream(self, request: LlmRequest) -> AsyncIterator[LlmEvent]:
        ...

    def capabilities(self, provider_id: str, model_id: str) -> ModelCapabilities:
        ...


class EgressViolationError(Exception):
    def __init__(self, safe_reason: str, message: str | None = None) -> None:
        self.safe_reason = safe_reason
        # Never use caller-supplied message: it may contain the rejected value.
        super().__init__(safe_reason)
