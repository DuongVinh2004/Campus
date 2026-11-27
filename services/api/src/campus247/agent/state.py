from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from campus247.application.conversation.history import HistoryContext


class Route(StrEnum):
    GROUNDED_FAQ = "grounded_faq"
    PERSONAL_SCHEDULE = "personal_schedule"
    TICKET_CREATE = "ticket_create"
    DOCUMENT_REQUEST = "document_request"
    ROOM_BOOKING = "room_booking"
    HUMAN_HANDOVER = "human_handover"
    SENSITIVE_CASE = "sensitive_case"
    UNSUPPORTED = "unsupported"


class Terminal(StrEnum):
    ANSWERED = "answered"
    ABSTAINED = "abstained"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    HANDED_OVER = "handed_over"
    SAFE_FAILURE = "safe_failure"


class ToolPhase(StrEnum):
    NONE = "none"
    CANDIDATE = "candidate"
    VALIDATED = "validated"
    AUTHORIZED = "authorized"
    PREVIEWED = "previewed"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    CONFIRMED = "confirmed"
    EXECUTING = "executing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    UNCERTAIN = "uncertain"


class SafetySeverity(StrEnum):
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class NormalizedTurn:
    session_id: str
    turn_id: str
    user_id: str
    query: str
    locale: str = "vi-VN"
    history: HistoryContext | None = None
    # Server callbacks only; never serialized as an executable model tool.
    presentation: Any = None
    context_guard: Any = None
    coordination_guard: Any = None  # Server identity/session callback, never model data.
    personal_memory: Any = None  # Fresh actor-bound passive data callback; never a writer/tool.


@dataclass(frozen=True)
class SafetyDecision:
    severity: SafetySeverity = SafetySeverity.NORMAL
    is_crisis: bool = False
    reason: str | None = None
    labels: tuple[str, ...] = ()
    confidence: float = 0.0
    immediacy: str = "unknown"
    target: str = "unknown"
    handover_recommended: bool = False
    reason_codes: tuple[str, ...] = ()


@dataclass(frozen=True)
class RetrievalState:
    candidate_ids: tuple[str, ...] = ()
    citation_bundle_ref: str | None = None


@dataclass(frozen=True)
class DraftResponse:
    text: str
    claim_count: int = 0
    is_grounded: bool = False
    gate_decision: str = "abstain"
    gate_reasons: tuple[str, ...] = ()
    grounded_claims: tuple[Any, ...] = ()
    partial_note: str | None = None  # Fixed server text; never model-authored.
    preface: str | None = None       # Fixed server text shown before the answer (scope caveat).
    guidance: tuple[str, ...] = ()   # Server-derived next-step suggestions shown after the answer.
    # Layout only: grounded claims grouped by the part of the question they answer (user's words, claim indexes).
    claim_groups: tuple[tuple[str, tuple[int, ...]], ...] = ()


@dataclass(frozen=True)
class ConfirmationContext:
    """Immutable, serializable binding carried by a pending write action."""

    preview_id: str
    tool_id: str
    canonical_arguments: str
    payload_hash: str
    actor_id: str
    authorization_scope: str
    contract_version: str
    policy_version: str
    expires_at: str
    risk_level: str


@dataclass(frozen=True)
class ExecutionContext:
    """Safe terminal evidence for a reserved tool execution."""

    idempotency_key: str
    action_name: str
    payload_hash: str
    correlation_id: str
    outcome: str
    permitted_next_action: str


@dataclass(frozen=True)
class ToolCandidate:
    tool_id: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolFlowState:
    validated_arguments: dict[str, Any] | None = None
    preview: Any | None = None
    interrupt: dict[str, Any] | None = None
    result_data: Any | None = None
    candidates: list[Any] | None = None
    classifier_safety: Any | None = None
    coordinator_status: str | None = None
    idempotency_key: str | None = None
    correlation_id: str | None = None
    search_question: str | None = None  # Validated accent restoration; never source facts or scope.
    # The router's restatement of a messy question (typos, slang, filler removed). Accepted only after the code check
    # that every number, code, name and negation of the original survived; never source facts or scope.
    clean_question: str | None = None


@dataclass(frozen=True)
class AgentState:
    """Canonical typed agent state contract for controlled LangGraph execution."""

    request: NormalizedTurn
    schema_version: str = "1.0"
    trusted_context_ref: str | None = None
    route: Route | None = None
    safety: SafetyDecision = field(default_factory=SafetyDecision)
    retrieval: RetrievalState | None = None
    draft: DraftResponse | None = None
    tool_candidate: ToolCandidate | None = None
    tool_flow: ToolFlowState | None = None
    tool_phase: ToolPhase = ToolPhase.NONE
    terminal: Terminal | None = None
    state_version: int = 1
    interrupt_id: str | None = None
    errors: tuple[str, ...] = ()
    step_count: int = 0
    confirmation_context: ConfirmationContext | None = None
    execution_context: ExecutionContext | None = None
    agent_run_id: str | None = None
    knowledge_snapshot: dict[str, Any] | None = None  # Server-bound release/generations; no executable data.

    def __post_init__(self) -> None:
        if self.schema_version != "1.0":
            raise ValueError(f"Invalid state schema version '{self.schema_version}'. Expected '1.0'")
