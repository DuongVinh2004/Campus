from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Literal

from pydantic import Field, StrictStr, model_validator

from campus247.application.assistance.contracts import ResourceRef

from campus247.application.single_agent.contracts import (
    CoverageFinding, CoverageItem, StrictRecord, Support, digest,
)


class CoordinationBinding(StrictRecord):
    actor_id: StrictStr = Field(min_length=1, max_length=100)
    tenant_id: StrictStr = Field(min_length=1, max_length=100)
    conversation_id: StrictStr = Field(min_length=1, max_length=100)
    scope_sha256: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")
    session_sha256: StrictStr | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    roles: list[StrictStr] = Field(min_length=1, max_length=8)
    audiences: list[StrictStr] = Field(min_length=1, max_length=8)
    resource: ResourceRef | None = None
    goal_sha256: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")
    purpose_sha256: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")
    authority: Literal["read_prepare_only"] = "read_prepare_only"


class TaskBinding(StrictRecord):
    scope: CoordinationBinding
    coverage_sha256: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")
    budget_sha256: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")
    output_contract: Literal["task-result.v1"] = "task-result.v1"


class TaskSpec(StrictRecord):
    id: StrictStr = Field(pattern=r"^T[1-8]$")
    role: Literal["research", "verifier", "document"]
    goal: StrictStr = Field(min_length=1, max_length=700)
    coverage_ids: list[StrictStr] = Field(min_length=1, max_length=4)
    dependencies: list[StrictStr] = Field(default_factory=list, max_length=7)
    tools: list[Literal["search_knowledge", "search_policy_relations", "read_source", "inspect_evidence", "read_document"]] = Field(min_length=1, max_length=4)
    binding: TaskBinding | None = None  # Server-bound after validating model proposal.


class TaskAssignment(StrictRecord):
    """Compact model proposal; role permissions are bound by server."""
    id: StrictStr = Field(pattern=r"^T[1-8]$")
    role: Literal["research", "verifier"]
    goal: StrictStr = Field(min_length=1, max_length=100)
    coverage_ids: list[StrictStr] = Field(min_length=1, max_length=4)
    dependencies: list[StrictStr] = Field(default_factory=list, max_length=7)

    def to_spec(self):
        tools = ["read_source", "inspect_evidence"]
        if self.role == "research":
            tools.insert(0, "search_knowledge")
        return TaskSpec(**self.model_dump(), tools=tools)


class EvidenceRecord(StrictRecord):
    evidence_id: StrictStr
    source_id: StrictStr
    document_version_id: StrictStr
    chunk_id: StrictStr
    parent_id: StrictStr
    excerpt: StrictStr = Field(min_length=1, max_length=15000)
    locator: dict
    content_sha256: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")
    publication: Literal["CURRENT", "SYNTHETIC"]
    effective_from: StrictStr
    effective_until: StrictStr | None
    access_reason: Literal["current_server_scope_reader_verified"]


class ToolResult(StrictRecord):
    tool: Literal["search_knowledge", "search_policy_relations", "read_source", "inspect_evidence", "prepare_service_draft"]
    status: Literal["succeeded", "partial", "denied", "unavailable", "invalid_output"]
    evidence_ids: list[StrictStr] = Field(default_factory=list, max_length=12)
    error_code: StrictStr | None = None
    usage: dict = Field(default_factory=dict)


@dataclass(frozen=True)
class RunContext:
    run_id: str
    conversation_id: str
    actor_id: str
    authorized_scope_ref: str
    as_of: datetime
    snapshot: dict
    configuration_fingerprint: str
    deadline: str


class TaskPlan(StrictRecord):
    items: list[CoverageItem] = Field(min_length=1, max_length=4)
    tasks: list[TaskSpec] = Field(max_length=8)
    clarification: StrictStr | None = Field(default=None, min_length=1, max_length=500)


class TaskPlanProposal(StrictRecord):
    items: list[CoverageItem] = Field(min_length=1, max_length=4)
    tasks: list[TaskAssignment] = Field(max_length=8)
    clarification: StrictStr | None = Field(default=None, min_length=1, max_length=500)

    def to_plan(self):
        return TaskPlan(items=self.items, tasks=[task.to_spec() for task in self.tasks], clarification=self.clarification)


class ResearchQuery(StrictRecord):
    query: StrictStr = Field(min_length=1, max_length=700)


class SpanSupport(StrictRecord):
    requirement_id: StrictStr = Field(pattern=r"^R[1-9][0-9]?$")
    evidence_id: StrictStr = Field(min_length=1, max_length=64)
    span_id: StrictStr = Field(pattern=r"^S[0-9]{3}$")


class CoverageSelection(StrictRecord):
    item_id: StrictStr = Field(pattern=r"^Q[1-4]$")
    status: Literal["supported", "missing_user_fact", "missing_source", "conflicting", "out_of_scope"]
    supports: list[SpanSupport | Support] = Field(max_length=16)


class ResearchReport(StrictRecord):
    coverage: list[CoverageSelection] = Field(min_length=1, max_length=4)


class CoordinatorDecision(StrictRecord):
    action: Literal["research", "synthesize", "clarify", "stop"]
    tasks: list[TaskSpec] = Field(default_factory=list, max_length=8)
    clarification: StrictStr | None = Field(default=None, min_length=1, max_length=500)


class CoordinatorDecisionProposal(StrictRecord):
    action: Literal["research", "synthesize", "clarify", "stop"]
    tasks: list[TaskAssignment] = Field(default_factory=list, max_length=8)
    clarification: StrictStr | None = Field(default=None, min_length=1, max_length=500)

    def to_decision(self):
        return CoordinatorDecision(action=self.action, tasks=[task.to_spec() for task in self.tasks], clarification=self.clarification)


class ClaimRecord(StrictRecord):
    claim_id: StrictStr = Field(pattern=r"^CLM-[0-9]{3}$")
    text: StrictStr = Field(min_length=1, max_length=2000)
    evidence_ids: list[StrictStr] = Field(min_length=1, max_length=6)
    verdict: Literal["supported", "insufficient", "contradicted", "invalid"]


class TaskResult(StrictRecord):
    task_id: StrictStr = Field(pattern=r"^T[1-8]$")
    status: Literal["succeeded", "partial", "failed", "cancelled"]
    evidence_refs: list[dict[str, StrictStr]] = Field(default_factory=list, max_length=6)
    coverage: list[CoverageFinding] = Field(default_factory=list, max_length=4)
    error_code: StrictStr | None = Field(default=None, max_length=64)

    @model_validator(mode="after")
    def truthful_status(self):
        if self.status == "succeeded" and (not self.coverage or any(r.status != "supported" for r in self.coverage)):
            raise ValueError("successful task requires supported coverage")
        if self.status in {"failed", "cancelled"} and not self.error_code:
            raise ValueError("failed task requires reason")
        return self


class ContinuationCheckpoint(StrictRecord):
    schema_version: Literal["coordination-checkpoint.v1"] = "coordination-checkpoint.v1"
    binding: CoordinationBinding
    state: Literal["pending", "interrupted", "uncertain", "waiting_user", "partial", "completed", "cancelled", "failed"]
    blockers: list[StrictStr] = Field(default_factory=list, max_length=16)
    next_action: Literal["wait", "clarify", "read_receipt", "read_sources", "new_run", "none"]
    receipt_id: StrictStr | None = None
    # References describe work; they never supply action/confirmation authority.
    draft: ResourceRef | None = None
    case: ResourceRef | None = None
    task_versions: dict[StrictStr, int] = Field(default_factory=dict)

    @model_validator(mode="after")
    def receipt_required(self):
        if self.state == "completed" and (not self.receipt_id or self.blockers or self.next_action != "none"):
            raise ValueError("completion requires committed receipt and no blockers")
        return self


class ControllerCoverage(CoverageFinding):
    verification: Literal["quoted_source_checked_pending_claim_verification"] | None = None


class ControllerCheckpoint(StrictRecord):
    items: list[CoverageItem] = Field(default_factory=list, max_length=4)
    coverage: list[ControllerCoverage] = Field(default_factory=list, max_length=4)
    queries: list[StrictStr] = Field(default_factory=list, max_length=8)
    no_progress: int = Field(default=0, ge=0, le=8)
    evidence_refs: list[dict[StrictStr, StrictStr]] = Field(default_factory=list, max_length=6)

    @model_validator(mode="after")
    def references_only(self):
        import re
        fields = {"source_id", "document_version_id", "chunk_id", "quote_span_hash", "locator_sha256",
                  "effective_from", "effective_until", "source_status"}
        for ref in self.evidence_refs:
            if not set(ref) <= fields or not {"source_id", "document_version_id", "chunk_id", "quote_span_hash"} <= set(ref):
                raise ValueError("checkpoint must contain source references only")
        if any(re.fullmatch(r"[0-9a-f]{64}", value) is None for value in self.queries):
            raise ValueError("checkpoint query fingerprints required")
        return self


@dataclass(frozen=True)
class MultiAgentPolicy:
    version: str = "multi-agent-v15"
    max_steps: int = 3
    max_tasks: int = 8
    max_concurrency: int = 2
    max_attempts: int = 2
    max_model_calls: int = 12
    max_searches: int = 4
    max_tool_calls: int = 64
    max_candidates: int = 12
    max_evidence: int = 6
    max_context_bytes: int = 15000
    max_reserved_tokens: int = 150000
    max_no_progress: int = 2
    deadline_seconds: float = 30.0
    model_timeout_ms: int = 5000
    tool_timeout_ms: int = 12000
    max_active_runs: int = 4
    max_reserved_cost_usd: float = 1.0
    reserved_cost_per_token_usd: float = 0.000005

    def __post_init__(self):
        ceilings = {"max_steps": 3, "max_tasks": 8, "max_concurrency": 2, "max_attempts": 2,
                    "max_model_calls": 12, "max_searches": 4, "max_tool_calls": 64,
                    "max_candidates": 12, "max_evidence": 6, "max_context_bytes": 15000,
                    "max_reserved_tokens": 150000, "max_no_progress": 2,
                    "model_timeout_ms": 5000, "tool_timeout_ms": 12000, "max_active_runs": 4}
        if self.version != "multi-agent-v15":
            raise ValueError("unsupported multi-agent profile")
        for name, cap in ceilings.items():
            if type(getattr(self, name)) is not int or not 0 <= getattr(self, name) <= cap:
                raise ValueError("multi-agent ceiling exceeded")
        if self.max_concurrency < 1 or type(self.deadline_seconds) not in {int, float} or not 0 < self.deadline_seconds <= 30:
            raise ValueError("invalid concurrency/deadline")
        if (not 1 <= self.max_active_runs <= 4 or
                type(self.max_reserved_cost_usd) not in {int, float} or not 0 <= self.max_reserved_cost_usd <= 1 or
                type(self.reserved_cost_per_token_usd) not in {int, float} or not 0 < self.reserved_cost_per_token_usd <= 0.000005):
            raise ValueError("invalid shared cost/worker budget")

    @property
    def fingerprint(self):
        return digest(asdict(self))


def validate_dag(tasks, items, policy, *, previous=()):
    """Validate the entire proposal before creating or dispatching any task."""
    if len(tasks) + len(previous) > policy.max_tasks:
        raise ValueError("TASK_LIMIT")
    old_ids = {task.id for task in previous}
    ids = [task.id for task in tasks]
    coverage_ids = {item.id for item in items}
    if len(set(ids)) != len(ids) or old_ids.intersection(ids):
        raise ValueError("DUPLICATE_TASK")
    all_tasks = {task.id: task for task in (*previous, *tasks)}
    covered = set()
    for task in tasks:
        if (len(set(task.coverage_ids)) != len(task.coverage_ids) or
                not set(task.coverage_ids) <= coverage_ids or
                len(set(task.dependencies)) != len(task.dependencies) or
                not set(task.dependencies) <= set(all_tasks) or
                len(set(task.tools)) != len(task.tools)):
            raise ValueError("INVALID_TASK_REFERENCE")
        allowed = {"search_knowledge", "search_policy_relations", "read_source", "inspect_evidence"} if task.role == "research" else {"read_document", "inspect_evidence"} if task.role == "document" else {"read_source", "inspect_evidence"}
        required = {"read_document", "inspect_evidence"} if task.role == "document" else {"read_source", "inspect_evidence"}
        if not set(task.tools) <= allowed or not required <= set(task.tools):
            raise ValueError("TASK_TOOL_DENIED")
        if task.role == "research" and "search_knowledge" not in task.tools:
            raise ValueError("TASK_TOOL_DENIED")
        if task.role == "verifier" and not task.dependencies:
            raise ValueError("VERIFIER_DEPENDENCY_REQUIRED")
        covered.update(task.coverage_ids)
    visited, visiting = set(), set()
    def visit(key):
        if key in visiting:
            raise ValueError("TASK_CYCLE")
        if key in visited:
            return
        visiting.add(key)
        for parent in all_tasks[key].dependencies:
            visit(parent)
        visiting.remove(key)
        visited.add(key)
    for key in all_tasks:
        visit(key)
    if not previous and covered != coverage_ids:
        raise ValueError("INCOMPLETE_TASK_COVERAGE")
    for item_id in covered:
        researchers = {task.id for task in tasks if task.role in {"research", "document"} and item_id in task.coverage_ids}
        verifiers = [task for task in tasks if task.role == "verifier" and item_id in task.coverage_ids]
        def ancestors(task_id):
            result = set()
            for parent in all_tasks[task_id].dependencies:
                result.add(parent)
                result.update(ancestors(parent))
            return result
        if not researchers or not any(ancestors(task.id) & researchers for task in verifiers):
            raise ValueError("INCOMPLETE_VERIFICATION_DAG")
    return tasks


def fit_initial_plan(plan, policy, remaining_calls):
    """Group only validated independent goals when their proposed DAG is costly.

    Coverage requirements, tool rights and ceilings stay identical. Dependency
    graphs that cannot be flattened safely still require a model repair.
    """
    if plan.clarification:
        return plan
    validate_dag(plan.tasks, plan.items, policy)
    needed = sum(2 if task.role == "research" else 1 for task in plan.tasks)
    if needed+2 <= remaining_calls:
        return plan
    researchers = [task for task in plan.tasks if task.role == "research"]
    verifiers = [task for task in plan.tasks if task.role == "verifier"]
    research_ids = {task.id for task in researchers}
    if (remaining_calls < 5 or not researchers or not verifiers
            or any(task.dependencies for task in researchers)
            or any(not set(task.dependencies) <= research_ids for task in verifiers)):
        raise ValueError("TASK_PLAN_BUDGET_NOT_FEASIBLE")
    coverage_ids = [item.id for item in plan.items]
    def grouped(tasks, dependencies):
        return TaskSpec(**{**tasks[0].model_dump(), "goal": "; ".join(task.goal for task in tasks),
            "coverage_ids": coverage_ids, "dependencies": dependencies})
    research = grouped(researchers, [])
    verifier = grouped(verifiers, [research.id])
    result = TaskPlan(items=plan.items, tasks=[research, verifier])
    validate_dag(result.tasks, result.items, policy)
    return result


def fit_supplemental_tasks(tasks, items, policy, previous, missing, remaining_calls):
    """Narrow validated supplemental work to uncovered goals, within budget."""
    validate_dag(tasks, items, policy, previous=previous)
    research_ids = {task.id for task in (*previous, *tasks) if task.role == "research"}
    independent = (all(not task.dependencies for task in tasks if task.role == "research")
        and all(set(task.dependencies) <= research_ids for task in tasks if task.role == "verifier"))
    if any(not set(task.coverage_ids) <= missing for task in tasks):
        if not independent:
            raise ValueError("UNNECESSARY_TASK")
        removed = {task.id for task in tasks if not set(task.coverage_ids) & missing}
        tasks = [TaskSpec(**{**task.model_dump(),
            "coverage_ids": [key for key in task.coverage_ids if key in missing],
            "dependencies": [key for key in task.dependencies if key not in removed]})
            for task in tasks if task.id not in removed]
        if not tasks:
            raise ValueError("UNNECESSARY_TASK")
        validate_dag(tasks, items, policy, previous=previous)
    needed = sum(2 if task.role == "research" else 1 for task in tasks)
    if needed+2 <= remaining_calls:
        return tasks
    if not independent or remaining_calls < 5:
        raise ValueError("TASK_PLAN_BUDGET_NOT_FEASIBLE")
    researchers = [task for task in tasks if task.role == "research"]
    verifiers = [task for task in tasks if task.role == "verifier"]
    covered = {key for task in tasks for key in task.coverage_ids}
    targets = [item.id for item in items if item.id in covered]
    research = TaskSpec(**{**researchers[0].model_dump(),
        "goal": "; ".join(task.goal for task in researchers), "coverage_ids": targets, "dependencies": []})
    verifier = TaskSpec(**{**verifiers[0].model_dump(),
        "goal": "; ".join(task.goal for task in verifiers), "coverage_ids": targets, "dependencies": [research.id]})
    validate_dag([research, verifier], items, policy, previous=previous)
    return [research, verifier]
