from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import hashlib
import json
import threading
from typing import Any, Callable

from campus247.agent.state import ExecutionContext, ToolPhase
from campus247.domain.shared.values import generate_uuid7


class BlindRetryBlockedError(Exception):
    pass


class IdempotencyConflictError(Exception):
    pass


class ExecutionInProgressError(Exception):
    pass


class ScopedSpecialistExecutor:
    """Server-selected read/prepare adapter with strict input/output and guards.

    It receives no action coordinator, confirmation token or business dispatcher.
    Revalidation runs on every call and again before returning a result.
    """
    def __init__(self, registry, *, authorize):
        self.registry, self.authorize = registry, authorize

    def execute(self, tool_id, candidate, input_contract, output_contract, handler):
        tool = self.registry.get_tool(tool_id)
        if tool.is_write or tool.requires_confirmation:
            raise PermissionError("SPECIALIST_WRITE_TOOL_DENIED")
        value = input_contract.model_validate(candidate)
        self.authorize(tool_id, value)
        output = output_contract.model_validate(handler(value))
        self.authorize(tool_id, value)
        return output


class ExecutionOutcomeStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED_NO_EFFECT = "failed_no_effect"
    RESULT_UNKNOWN = "result_unknown"


@dataclass(frozen=True)
class ToolExecutionResult:
    idempotency_key: str
    action_name: str
    status: ExecutionOutcomeStatus
    tool_phase: ToolPhase
    correlation_id: str
    data: Any | None = None
    error: str | None = None
    permitted_next_action: str = "Tác vụ hoàn tất."

    def to_state_context(self, payload_hash: str) -> ExecutionContext:
        return ExecutionContext(
            idempotency_key=self.idempotency_key,
            action_name=self.action_name,
            payload_hash=payload_hash,
            correlation_id=self.correlation_id,
            outcome=self.status.value,
            permitted_next_action=self.permitted_next_action,
        )


@dataclass
class _ExecutionRecord:
    action_name: str
    payload_hash: str
    correlation_id: str
    result: ToolExecutionResult | None = None


class IdempotentToolExecutionCoordinator:
    """Coordinates deterministic tool execution, idempotency reservation, and outcome categorization."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._ledger: dict[str, _ExecutionRecord] = {}

    @staticmethod
    def _payload_hash(action_name: str, payload: dict[str, Any]) -> str:
        try:
            canonical = json.dumps(
                {"action": action_name, "payload": payload},
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            )
        except (TypeError, ValueError):
            raise ValueError("Execution payload must be JSON serializable") from None
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _success(
        idempotency_key: str,
        action_name: str,
        correlation_id: str,
        output: Any,
    ) -> ToolExecutionResult:
        return ToolExecutionResult(
            idempotency_key=idempotency_key,
            action_name=action_name,
            status=ExecutionOutcomeStatus.SUCCEEDED,
            tool_phase=ToolPhase.SUCCEEDED,
            correlation_id=correlation_id,
            data=output,
            permitted_next_action="Tác vụ đã được thực hiện thành công.",
        )

    @staticmethod
    def _failed_no_effect(idempotency_key: str, action_name: str, correlation_id: str) -> ToolExecutionResult:
        return ToolExecutionResult(
            idempotency_key=idempotency_key,
            action_name=action_name,
            status=ExecutionOutcomeStatus.FAILED_NO_EFFECT,
            tool_phase=ToolPhase.FAILED,
            correlation_id=correlation_id,
            error="EXECUTION_FAILED_NO_EFFECT",
            permitted_next_action="Kiểm tra lại dữ liệu đầu vào và tạo một yêu cầu mới.",
        )

    @staticmethod
    def _unknown(idempotency_key: str, action_name: str, correlation_id: str) -> ToolExecutionResult:
        return ToolExecutionResult(
            idempotency_key=idempotency_key,
            action_name=action_name,
            status=ExecutionOutcomeStatus.RESULT_UNKNOWN,
            tool_phase=ToolPhase.UNCERTAIN,
            correlation_id=correlation_id,
            error="EXECUTION_RESULT_UNKNOWN",
            permitted_next_action="Chờ reconciliation xác thực trạng thái; không retry mù.",
        )

    def execute_idempotent(
        self,
        idempotency_key: str,
        action_name: str,
        payload: dict[str, Any],
        dispatch_fn: Callable[[], Any],
    ) -> ToolExecutionResult:
        payload_hash = self._payload_hash(action_name, payload)
        correlation_id = generate_uuid7()
        with self._lock:
            existing = self._ledger.get(idempotency_key)
            if existing is not None:
                if existing.action_name != action_name or existing.payload_hash != payload_hash:
                    raise IdempotencyConflictError("IDEMPOTENCY_KEY_REUSED")
                if existing.result is None:
                    raise ExecutionInProgressError("EXECUTION_IN_PROGRESS")
                if existing.result.status == ExecutionOutcomeStatus.RESULT_UNKNOWN:
                    raise BlindRetryBlockedError("EXECUTION_RESULT_UNKNOWN_REQUIRES_RECONCILIATION")
                return existing.result
            # Reserve before dispatch. A second caller sees the reservation and cannot dispatch.
            self._ledger[idempotency_key] = _ExecutionRecord(
                action_name=action_name,
                payload_hash=payload_hash,
                correlation_id=correlation_id,
            )

        try:
            output = dispatch_fn()
            result = self._success(idempotency_key, action_name, correlation_id, output)
        except (TimeoutError, ConnectionError, BrokenPipeError):
            result = self._unknown(idempotency_key, action_name, correlation_id)
        except Exception:
            result = self._failed_no_effect(idempotency_key, action_name, correlation_id)

        with self._lock:
            self._ledger[idempotency_key].result = result

        return result

    def reconcile(
        self,
        idempotency_key: str,
        resolved_status: ExecutionOutcomeStatus,
        data: Any = None,
        error: str | None = None,
    ) -> ToolExecutionResult:
        with self._lock:
            existing = self._ledger.get(idempotency_key)
            if existing is None or existing.result is None:
                raise ValueError("EXECUTION_RESERVATION_NOT_FOUND")
            if existing.result.status != ExecutionOutcomeStatus.RESULT_UNKNOWN:
                return existing.result
            if resolved_status == ExecutionOutcomeStatus.RESULT_UNKNOWN:
                raise ValueError("RECONCILIATION_MUST_RESOLVE_OUTCOME")
            if resolved_status == ExecutionOutcomeStatus.SUCCEEDED:
                updated = self._success(
                    idempotency_key,
                    existing.action_name,
                    existing.correlation_id,
                    data,
                )
            elif resolved_status == ExecutionOutcomeStatus.FAILED_NO_EFFECT:
                updated = self._failed_no_effect(
                    idempotency_key,
                    existing.action_name,
                    existing.correlation_id,
                )
            else:
                raise ValueError("Unsupported reconciliation outcome")
            existing.result = updated
            return updated
