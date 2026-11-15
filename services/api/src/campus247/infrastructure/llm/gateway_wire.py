"""JSON form of LlmRequest / LlmResponse for the loopback hop between an API process and the gateway sidecar.

Strict on the way in: the sidecar rebuilds a request from untrusted JSON (even on loopback), so every field is
type-checked and enums are parsed, never trusted. Nothing here logs or stores content.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from campus247.ports.llm import (
    FinishReason, LlmRequest, LlmResponse, LlmResponseStatus, PrivacyClass, TokenUsage, ToolCandidate)

MAX_BODY_BYTES = 256_000  # far above the 28,000-byte provider bound; refuses absurd bodies before parsing


class WireError(ValueError):
    pass


def _check(value, kind, name):
    if not isinstance(value, kind) or isinstance(value, bool) and kind is not bool:
        raise WireError(f"invalid {name}")
    return value


def request_to_json(request: LlmRequest) -> dict[str, Any]:
    data = asdict(request)
    data["privacy_class"] = request.privacy_class.value
    data["input_items"] = list(request.input_items)
    data["allowed_tools"] = list(request.allowed_tools)
    return data


def request_from_json(data: Any) -> LlmRequest:
    if not isinstance(data, dict):
        raise WireError("request must be an object")
    unknown = set(data) - {"request_id", "route_id", "model_profile", "system_instructions", "input_items", "output_schema",
                           "allowed_tools", "tool_choice", "temperature", "max_output_tokens", "deadline_ms",
                           "privacy_class", "trace_context"}
    if unknown:
        raise WireError("unknown request field")
    try:
        items = _check(data.get("input_items", []), list, "input_items")
        tools = _check(data.get("allowed_tools", []), list, "allowed_tools")
        schema = data.get("output_schema")
        if schema is not None:
            _check(schema, dict, "output_schema")
        choice = data.get("tool_choice")
        if choice is not None:
            _check(choice, str, "tool_choice")
        context = _check(data.get("trace_context", {}), dict, "trace_context")
        temperature = data.get("temperature", 0.0)
        if not isinstance(temperature, (int, float)) or isinstance(temperature, bool):
            raise WireError("invalid temperature")
        return LlmRequest(
            request_id=_check(data["request_id"], str, "request_id"), route_id=_check(data["route_id"], str, "route_id"),
            model_profile=_check(data["model_profile"], str, "model_profile"),
            system_instructions=_check(data["system_instructions"], str, "system_instructions"),
            input_items=tuple(_check(item, dict, "input item") for item in items), output_schema=schema,
            allowed_tools=tuple(_check(tool, dict, "tool") for tool in tools), tool_choice=choice,
            temperature=float(temperature),
            max_output_tokens=_check(data["max_output_tokens"], int, "max_output_tokens"),
            deadline_ms=_check(data["deadline_ms"], int, "deadline_ms"),
            privacy_class=PrivacyClass(data.get("privacy_class", PrivacyClass.PUBLIC.value)), trace_context=context)
    except KeyError as error:
        raise WireError(f"missing {error.args[0]}") from None
    except ValueError as error:  # includes bad enum values and the dataclass bounds
        raise WireError(str(error)) from None


def response_to_json(response: LlmResponse) -> dict[str, Any]:
    data = asdict(response)
    data["status"] = response.status.value
    data["finish_reason"] = response.finish_reason.value
    data["tool_candidates"] = [asdict(candidate) for candidate in response.tool_candidates]
    return data


def response_from_json(data: Any) -> LlmResponse:
    if not isinstance(data, dict):
        raise WireError("response must be an object")
    try:
        usage = data.get("usage", {})
        return LlmResponse(
            status=LlmResponseStatus(data["status"]), provider_id=_check(data["provider_id"], str, "provider_id"),
            model_id=_check(data["model_id"], str, "model_id"), provider_request_id=data.get("provider_request_id"),
            output_text=data.get("output_text"), structured_output=data.get("structured_output"),
            tool_candidates=tuple(ToolCandidate(**item) for item in data.get("tool_candidates", [])),
            finish_reason=FinishReason(data.get("finish_reason", FinishReason.STOP.value)),
            usage=TokenUsage(**{key: _check(usage.get(key, 0), int, key) for key in
                                ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_tokens")}),
            latency_ms=_check(data.get("latency_ms", 0), int, "latency_ms"), attempt=_check(data.get("attempt", 1), int, "attempt"))
    except (KeyError, TypeError, ValueError) as error:
        raise WireError("malformed gateway response") from None
