---
document_id: "DOC-AGENT-001"
version: "1.1.0"
status: "reviewed"
owner: "Agentic Delivery Architecture"
approvers: ["Engineering Lead", "Security Owner", "Quality Owner"]
last_updated: "2026-10-07"
---

# Executor contract

[DEC-023](../00-governance/LOCAL_EXECUTION_AUTHORITY_DECISION_20261007.md) is standing direct human authority for assigned local/synthetic engineering. Older approval flags, roles and guide passages do not require another task/package approval. Record the decision, prepare exact targets and technical evidence, and proceed within the assigned objective.

## Input

The executor receives exactly one task file, the accepted dependency evidence, and a context pack resolved from task inputs and traceability. It must not infer authorization from repository access.

Before reading implementation code, it resolves upstream product obligations in this order:

1. `task.traceability.requirements` plus `task.traceability.acceptance_criteria`, when both are present;
2. the matching task entry in `tasks/requirement-acceptance-bindings.yaml`;
3. the union of both only when `binding_mode: mixed` is explicit.

The resolver must reject an empty result, an unknown requirement/AC, an AC belonging to another requirement, or a direct link that disagrees with the canonical binding. It loads the exact requirement and AC from `docs/01-product/requirements.yaml`, then reads the governing Markdown source named there. A binding supplies traceability only; it never weakens a task's direct product obligation.

## Required preflight

1. Parse and schema-validate the task.
2. Resolve and record every upstream requirement and product AC; verify `status: ready` and dependency states.
3. Record DEC-023 as execution authority for delegated local/synthetic work; verify that the task's actual target, environment and objective fall within it.
4. Inspect Git status and record pre-existing changes.
5. Resolve allowed paths canonically; reject roots, parent traversal, globs that escape the repository and symlink targets outside the workspace.
6. Check no running task has overlapping paths or conflict keys.
7. Read every required input completely.
8. Run preflight commands and stop on non-zero unless the task explicitly expects it.

## Execution invariants

- The task objective is immutable.
- Only paths allowed by the task may change.
- The executor must preserve unrelated dirty, untracked and staged state.
- Acceptance criteria are assertions, not suggestions.
- Tests must observe externally meaningful behavior where practical.
- Fakes must simulate error, timeout and conflict paths, not only success.
- Generated output must be reproducible from a checked-in source and command.
- No hidden network call is permitted when `network_access: false`.
- No paid call is permitted when `paid_services: false`.

## Result semantics

- `completed`: implementation and every required check passed.
- `blocked`: work could not safely begin or continue because required technical information, an artifact or an authorized environment boundary is missing. Do not use a historical approval flag as a blocker for DEC-023 work.
- `failed`: in-scope implementation was attempted but acceptance still fails after the repair budget.

The task-output schema retains its result vocabulary. The authorized executor can separately record technical acceptance under DEC-022/DEC-023 after reviewing evidence; independent human review is not an execution prerequisite in this scope.

## Required output trace

Every task output includes `resolved_upstream_traceability`. It records the resolution mode, the binding path when used, and every resolved requirement with its exact product AC IDs. A task with no resolved product trace is `blocked` with `CONTRACT_MISMATCH`; it must not begin implementation.

## Forbidden behavior

No scope expansion, opportunistic cleanup, mass formatting outside scope, weakened test, invented contract, placeholder production behavior, destructive recovery, silent dependency addition, or success claim without exit-code evidence.
