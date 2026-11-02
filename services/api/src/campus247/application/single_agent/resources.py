"""Reserve before dispatch, join cancellation, never refund uncertain calls."""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import replace

from campus247.ports.llm import LlmResponse


class AgentStop(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class RunResources:
    def __init__(self, policy, *, usage=None, persist=lambda: None, cancelled=lambda: False):
        self.policy, self.persist, self.cancelled = policy, persist, cancelled
        self.started = time.monotonic()
        self.expires = self.started + policy.deadline_seconds
        self.usage = {"model_calls": 0, "reserved_tokens": 0, "input_tokens": 0,
                      "output_tokens": 0, "tool_calls": 0, "searches": 0,
                      "steps": 0, "cost_usd": None, "usage_complete": True}
        self.usage["elapsed_ms"] = 0
        if usage:
            if set(usage) != set(self.usage):
                raise ValueError("checkpoint usage schema")
            self.usage.update(usage)
            for key in ("model_calls", "reserved_tokens", "input_tokens", "output_tokens",
                        "tool_calls", "searches", "steps", "elapsed_ms"):
                if type(self.usage[key]) is not int or self.usage[key] < 0:
                    raise ValueError("checkpoint usage bounds")
        self.elapsed_before = self.usage["elapsed_ms"]
        self.expires = self.started + max(0, policy.deadline_seconds-self.elapsed_before/1000)

    def elapsed_ms(self):
        return self.elapsed_before + round((time.monotonic()-self.started)*1000)

    def check(self):
        if self.cancelled():
            raise AgentStop("CANCELLED")
        if time.monotonic() >= self.expires:
            raise AgentStop("DEADLINE_EXCEEDED")

    def timeout_ms(self, cap):
        self.check()
        return max(1, min(cap, int((self.expires - time.monotonic()) * 1000)))

    def reserve_tool(self, *, search=False):
        self.check()
        if (self.usage["tool_calls"] >= self.policy.max_tool_calls or
                search and self.usage["searches"] >= self.policy.max_searches):
            raise AgentStop("TOOL_BUDGET_EXHAUSTED")
        self.usage["tool_calls"] += 1
        self.usage["searches"] += int(search)
        self.persist()


class BoundedGateway:
    def __init__(self, gateway, resources, *, event=lambda *_: None, pending=lambda *_: None, validate=lambda: None):
        self.gateway, self.resources, self.event, self.pending = gateway, resources, event, pending
        self.stop_code = None
        self.validate = validate

    def capabilities(self, *args):
        return self.gateway.capabilities(*args)

    async def generate(self, request):
        resources = self.resources
        resources.check()
        self.validate()
        # UTF-8 bytes are an explicitly conservative token upper bound. Include
        # schema/tools, not just message text; global gateway performs egress too.
        size = len(json.dumps({"system": request.system_instructions, "input": request.input_items,
                              "schema": request.output_schema, "tools": request.allowed_tools},
                             ensure_ascii=False).encode()) + 512
        reservation = size + request.max_output_tokens
        usage = resources.usage
        # Conservative reserved cost is derived from durable token reservations;
        # it includes uncertain calls and is never refunded on a lost response.
        rate = getattr(resources.policy, "reserved_cost_per_token_usd", None)
        cost_cap = getattr(resources.policy, "max_reserved_cost_usd", None)
        if rate is not None and (usage["reserved_tokens"] + reservation) * rate > cost_cap:
            raise AgentStop("COST_BUDGET_EXHAUSTED")
        if (usage["model_calls"] >= resources.policy.max_model_calls or
                usage["reserved_tokens"] + reservation > resources.policy.max_reserved_tokens):
            self.stop_code = "MODEL_BUDGET_EXHAUSTED"
            raise AgentStop("MODEL_BUDGET_EXHAUSTED")
        usage["model_calls"] += 1
        usage["reserved_tokens"] += reservation
        resources.persist()
        self.pending("model")
        started = time.monotonic()
        dispatched = False
        try:
            request = replace(request, deadline_ms=resources.timeout_ms(min(
                request.deadline_ms, resources.policy.model_timeout_ms)))
            async with asyncio.timeout(request.deadline_ms / 1000):
                dispatched = True
                response = await self.gateway.generate(request)
            if not isinstance(response, LlmResponse):
                raise AgentStop("MODEL_INVALID_OUTPUT")
            self.validate()
            token_usage = response.usage
            if (any(type(value) is not int or value < 0 for value in
                    (token_usage.input_tokens, token_usage.output_tokens, token_usage.reasoning_tokens))
                    or token_usage.input_tokens > size or token_usage.output_tokens > request.max_output_tokens):
                raise AgentStop("MODEL_INVALID_USAGE")
            usage["input_tokens"] += token_usage.input_tokens
            usage["output_tokens"] += token_usage.output_tokens
            self.event("model", "completed", round((time.monotonic()-started)*1000),
                       {"route": request.route_id, "model": response.model_id,
                        "input_tokens": token_usage.input_tokens, "output_tokens": token_usage.output_tokens})
            self.pending(None)
            resources.persist()
            return response
        except BaseException as failure:
            if not dispatched and isinstance(failure, AgentStop):
                # Durable reservation may consume the remaining deadline. A
                # reservation is not a dispatched call; no provider ran here.
                usage['model_calls'] -= 1
                self.pending(None)
                resources.persist()
                self.stop_code = failure.code
                raise
            from campus247.ports.llm import EgressViolationError
            rejected = isinstance(failure, EgressViolationError) or (
                isinstance(failure, ValueError) and str(failure) == "provider operation bound")
            self.stop_code = failure.code if isinstance(failure, AgentStop) else (
                "MODEL_REQUEST_REJECTED" if rejected else
                "MODEL_TIMEOUT" if isinstance(failure, TimeoutError) else "MODEL_FAILURE")
            usage["usage_complete"] = usage["usage_complete"] and rejected
            self.event("model", "rejected" if rejected else "uncertain", round((time.monotonic()-started)*1000),
                       {"route": request.route_id, "error_type": type(failure).__name__, "code": self.stop_code})
            if rejected:
                self.pending(None)
            # Keep pending=model in durable state if the process crashes here.
            resources.persist()
            if rejected:
                raise AgentStop("MODEL_REQUEST_REJECTED") from None
            if isinstance(failure, TimeoutError):
                raise AgentStop("DEADLINE_EXCEEDED" if time.monotonic() >= resources.expires else "MODEL_TIMEOUT") from None
            raise
