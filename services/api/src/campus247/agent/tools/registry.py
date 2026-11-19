from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Callable, TypeVar, Awaitable

T = TypeVar("T")

class CircuitBreakerTrippedError(Exception):
    pass

class ToolExecutionError(Exception):
    pass



class ToolValidationError(Exception):
    """Raised when tool candidate arguments fail validation or violate invariants."""
    pass


FORBIDDEN_ARGUMENTS = {"actor_id", "user_id", "role", "permissions", "tenant_id", "is_admin"}


@dataclass(frozen=True)
class ToolDefinition:
    tool_id: str
    name: str
    description: str
    is_write: bool
    requires_confirmation: bool
    allowed_arguments: tuple[str, ...] = ()
    timeout_ms: int = 2500
    max_attempts: int = 1
    circuit_breaker_enabled: bool = True


class ToolRegistry:
    """Registry of authorized typed tools and validator for tool candidate arguments."""

    def __init__(self, tools: dict[str, ToolDefinition]) -> None:
        self._tools = dict(tools)
        self._breaker_failures: dict[str, int] = {k: 0 for k in tools}
        self._breaker_tripped: dict[str, bool] = {k: False for k in tools}

    def record_success(self, tool_id: str) -> None:
        if tool_id in self._tools:
            self._breaker_failures[tool_id] = 0
            self._breaker_tripped[tool_id] = False

    def record_failure(self, tool_id: str) -> None:
        tool = self._tools.get(tool_id)
        if tool and tool.circuit_breaker_enabled:
            self._breaker_failures[tool_id] += 1
            if self._breaker_failures[tool_id] >= 3:
                self._breaker_tripped[tool_id] = True

    async def execute_with_policy(self, tool_id: str, fn: Callable[..., Awaitable[T]], *args: Any, **kwargs: Any) -> T:
        tool = self.get_tool(tool_id)
        if tool.circuit_breaker_enabled and self._breaker_tripped.get(tool_id):
            raise CircuitBreakerTrippedError(f"Circuit breaker tripped for tool {tool_id}")

        attempts = 0
        max_attempts = tool.max_attempts
        timeout_seconds = tool.timeout_ms / 1000.0
        last_error = None

        while attempts < max_attempts:
            attempts += 1
            try:
                result = await asyncio.wait_for(fn(*args, **kwargs), timeout=timeout_seconds)
                self.record_success(tool_id)
                return result
            except asyncio.TimeoutError as e:
                last_error = ToolExecutionError(f"Tool {tool_id} timed out after {tool.timeout_ms}ms")
            except Exception as e:
                last_error = ToolExecutionError(f"Tool {tool_id} failed: {e}")
                
        self.record_failure(tool_id)
        if last_error:
            raise last_error
        raise ToolExecutionError(f"Tool {tool_id} failed after {max_attempts} attempts")


    @classmethod
    def default_v1(cls) -> ToolRegistry:
        defs = [
            ToolDefinition(
                tool_id="TOOL-SCHEDULE-001",
                name="student_schedule_get",
                description="Get personal class and exam schedule",
                is_write=False,
                requires_confirmation=False,
                allowed_arguments=("from", "to", "cursor", "limit", "date_from", "date_to", "semester"),
            ),
            ToolDefinition(
                tool_id="TOOL-TICKET-001",
                name="ticket_create",
                description="Create student support ticket",
                is_write=True,
                requires_confirmation=True,
                allowed_arguments=("category", "subject", "description", "contact_preference", "attachment_refs", "title", "priority"),
                timeout_ms=5000,
            ),
            ToolDefinition(
                tool_id="TOOL-TICKET-002",
                name="ticket_get",
                description="Get details of an existing ticket",
                is_write=False,
                requires_confirmation=False,
                allowed_arguments=("ticket_id",),
            ),
            ToolDefinition(
                tool_id="TOOL-DOCUMENT-001",
                name="document_request_create",
                description="Request official student certificate or transcript",
                is_write=True,
                requires_confirmation=True,
                allowed_arguments=("document_type", "purpose", "delivery_method", "copies", "quantity"),
                timeout_ms=5000,
            ),
            ToolDefinition(
                tool_id="TOOL-ROOM-001",
                name="room_availability_search",
                description="Search available rooms and lecture halls",
                is_write=False,
                requires_confirmation=False,
                allowed_arguments=("building", "date", "slot"),
            ),
            ToolDefinition(
                tool_id="TOOL-ROOM-002",
                name="room_booking_create",
                description="Reserve room or hall for class/club",
                is_write=True,
                requires_confirmation=True,
                allowed_arguments=("room_id", "starts_at", "ends_at", "purpose", "attendee_count", "start_time", "end_time"),
                timeout_ms=5000,
            ),
            ToolDefinition(
                tool_id="TOOL-HITL-001",
                name="handover_create",
                description="Escalate conversation to human support queue",
                is_write=True,
                requires_confirmation=False,
                allowed_arguments=("category", "summary", "urgency", "reason"),
                timeout_ms=3000,
            ),
        ]
        return cls(tools={t.tool_id: t for t in defs})

    def has_tool(self, tool_id: str) -> bool:
        return tool_id in self._tools

    def get_tool(self, tool_id: str) -> ToolDefinition:
        if tool_id not in self._tools:
            raise ToolValidationError(f"Unknown tool ID: '{tool_id}'")
        return self._tools[tool_id]

    def validate_candidate(self, tool_id: str, arguments: dict[str, Any]) -> dict[str, Any]:
        tool = self.get_tool(tool_id)

        # Check for forbidden arguments (smuggling / privilege injection)
        for forbidden in FORBIDDEN_ARGUMENTS:
            if forbidden in arguments:
                raise ToolValidationError(
                    f"Forbidden argument '{forbidden}' in tool candidate for {tool_id}"
                )

        # Validate arguments against allowed list
        for arg_name in arguments:
            if arg_name not in tool.allowed_arguments:
                raise ToolValidationError(
                    f"Unexpected argument '{arg_name}' for tool {tool_id}. Allowed: {tool.allowed_arguments}"
                )

        return dict(arguments)

    @classmethod
    def specialist_reads(cls):
        return cls({name: ToolDefinition(name, name, "Scoped server read/prepare", False, False)
                    for name in ("search_knowledge", "search_policy_relations", "read_source", "inspect_evidence")})

    def authorize_specialist(self, tool_id, task, binding, current_binding, capabilities):
        tool = self.get_tool(tool_id)
        if (tool.is_write or tool.requires_confirmation or tool_id not in task.tools or
                tool_id not in capabilities or task.binding is None or
                task.binding.scope != binding or current_binding != binding):
            raise ToolValidationError("SPECIALIST_SCOPE_OR_CAPABILITY_CHANGED")
        allowed = {"read_source", "inspect_evidence"}
        if task.role == "research":
            allowed |= {"search_knowledge", "search_policy_relations"}
        if tool_id not in allowed:
            raise ToolValidationError("SPECIALIST_TOOL_DENIED")
