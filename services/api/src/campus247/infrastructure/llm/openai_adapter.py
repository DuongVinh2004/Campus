from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
import json
import logging
import time
from typing import Any
import httpx

from campus247.ports.llm import (
    FinishReason,
    LlmEvent,
    LlmEventType,
    LlmGateway,
    LlmRequest,
    LlmResponse,
    LlmResponseStatus,
    ModelCapabilities,
    TokenUsage,
    ToolCandidate,
)

logger = logging.getLogger(__name__)


class OpenAICompatibleAdapter(LlmGateway):
    """Universal adapter for OpenAI-compatible LLM endpoints (Gemini, DeepSeek, OpenAI, Groq)."""

    def __init__(
        self,
        provider_id: str,
        base_url: str,
        api_key: str | None,
        model_name: str,
        is_free: bool = False,
        default_timeout_sec: float = 15.0,
        *,
        disable_thinking: bool = False,
        json_mode: bool = False,
    ) -> None:
        if type(disable_thinking) is not bool:
            raise ValueError("disable_thinking must be boolean")
        if type(json_mode) is not bool:
            raise ValueError("json_mode must be boolean")
        if (disable_thinking or json_mode) and (
            provider_id != "deepseek" or model_name != "deepseek-flash"
            or base_url.rstrip("/") not in {"https://api.deepseek.com", "https://api.deepseek.com/v1"}
        ):
            raise ValueError("Non-thinking option requires the approved DeepSeek endpoint/model")
        self._disable_thinking = disable_thinking
        self._json_mode = json_mode
        self._provider_id = provider_id
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key or ""
        self._model_name = model_name
        self._is_free = is_free
        self._default_timeout = default_timeout_sec

    @property
    def provider_id(self) -> str:
        return self._provider_id

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def is_free(self) -> bool:
        return self._is_free

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key and self._api_key.strip())

    def _build_payload(self, request: LlmRequest) -> dict[str, Any]:
        messages: list[dict[str, str]] = []
        if request.system_instructions:
            messages.append({"role": "system", "content": request.system_instructions})

        for item in request.input_items:
            messages.append({
                "role": str(item.get("role", "user")),
                "content": str(item.get("content", "")),
            })

        payload: dict[str, Any] = {
            "model": self._model_name,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_output_tokens,
        }
        if self._disable_thinking:
            payload["thinking"] = {"type": "disabled"}
        if self._json_mode:
            payload["response_format"] = {"type": "json_object"}
        return payload

    def _normalize_response(self, raw_data: dict[str, Any], latency_ms: int = 0) -> LlmResponse:
        choices = raw_data.get("choices", [])
        output_text: str | None = None
        finish_reason = FinishReason.STOP
        tool_candidates: list[ToolCandidate] = []

        if choices:
            choice = choices[0]
            msg = choice.get("message", {})
            output_text = msg.get("content")

            finish_str = str(choice.get("finish_reason", "stop")).lower()
            if finish_str == "tool_calls":
                finish_reason = FinishReason.TOOL_CALL
                for tc in msg.get("tool_calls", []):
                    fn = tc.get("function", {})
                    raw_args = fn.get("arguments", "{}")
                    parsed_args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                    tool_candidates.append(
                        ToolCandidate(
                            call_id=tc.get("id", ""),
                            name=fn.get("name", ""),
                            arguments=parsed_args,
                        )
                    )
            elif finish_str == "length":
                finish_reason = FinishReason.LENGTH
            elif finish_str == "content_filter":
                finish_reason = FinishReason.CONTENT_FILTER
            else:
                finish_reason = FinishReason.STOP

        usage_raw = raw_data.get("usage", {})
        usage = TokenUsage(
            input_tokens=usage_raw.get("prompt_tokens", 0),
            cached_input_tokens=usage_raw.get("prompt_tokens_details", {}).get("cached_tokens", 0),
            output_tokens=usage_raw.get("completion_tokens", 0),
            reasoning_tokens=usage_raw.get("completion_tokens_details", {}).get("reasoning_tokens", 0),
        )

        return LlmResponse(
            status=LlmResponseStatus.COMPLETED,
            provider_id=self._provider_id,
            model_id=self._model_name,
            provider_request_id=raw_data.get("id"),
            output_text=output_text,
            structured_output=None,
            tool_candidates=tuple(tool_candidates),
            finish_reason=finish_reason,
            usage=usage,
            latency_ms=latency_ms,
            attempt=1,
        )

    async def generate(self, request: LlmRequest) -> LlmResponse:
        if not self.is_configured:
            raise ValueError(f"Provider {self._provider_id} has no valid API key configured")

        url = f"{self._base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = self._build_payload(request)
        timeout_sec = min(request.deadline_ms / 1000.0, self._default_timeout)

        start_time = time.monotonic()
        async with asyncio.timeout(request.deadline_ms / 1000.0), httpx.AsyncClient(timeout=timeout_sec) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            raw_data = resp.json()

        latency_ms = int((time.monotonic() - start_time) * 1000)
        return self._normalize_response(raw_data, latency_ms=latency_ms)

    async def stream(self, request: LlmRequest) -> AsyncIterator[LlmEvent]:
        if not self.is_configured:
            raise ValueError(f"Provider {self._provider_id} has no valid API key configured")

        url = f"{self._base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = self._build_payload(request)
        payload["stream"] = True
        timeout_sec = min(request.deadline_ms / 1000.0, self._default_timeout)

        yield LlmEvent(event_type=LlmEventType.RESPONSE_STARTED)

        async with asyncio.timeout(request.deadline_ms / 1000.0), httpx.AsyncClient(timeout=timeout_sec) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as stream_resp:
                stream_resp.raise_for_status()
                async for line in stream_resp.aiter_lines():
                    trimmed = line.strip()
                    if not trimmed or not trimmed.startswith("data:"):
                        continue
                    data_str = trimmed[5:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        choices = chunk.get("choices", [])
                        if choices:
                            delta_content = choices[0].get("delta", {}).get("content")
                            if delta_content:
                                yield LlmEvent(
                                    event_type=LlmEventType.TEXT_DELTA,
                                    delta=delta_content,
                                )
                    except json.JSONDecodeError:
                        continue

        yield LlmEvent(
            event_type=LlmEventType.RESPONSE_COMPLETED,
            status=LlmResponseStatus.COMPLETED,
        )

    def capabilities(self, provider_id: str, model_id: str) -> ModelCapabilities:
        return ModelCapabilities(
            provider_id=self._provider_id,
            model_id=self._model_name,
            supports_structured_output=True,
            supports_function_tools=True,
            supports_streaming=True,
            supports_images=False,
            supports_stateless_requests=True,
            context_tokens=65536,
            max_output_tokens=8192,
        )
