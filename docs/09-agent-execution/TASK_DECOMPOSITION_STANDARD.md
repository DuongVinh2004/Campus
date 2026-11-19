---
document_id: "DOC-AGENT-003"
version: "1.1.0"
status: "reviewed"
owner: "Agentic Delivery Architecture"
approvers: ["Architecture Owner", "Quality Owner"]
last_updated: "2026-10-07"
---

# Task decomposition standard

## Atomicity rules

A task has one observable objective, one primary layer and one bounded context. It normally changes 1–3 product files or one coherent test slice, adds no more than about 150 lines, and takes 15–45 minutes for an implementation agent with repository context.

Separate tasks are required for contract/schema, migration, domain behavior, adapter, API route, UI, tests, telemetry and infrastructure. A vertical slice is delivered by a dependency chain, never by a task named “build the whole module”.

## Good boundaries

- create one typed port;
- add one additive migration;
- implement one domain transition;
- expose one endpoint using an existing use case;
- render one screen state family;
- add one adapter error mapping;
- implement one evaluator or security test family.

## Split triggers

Split when work spans layers, bounded contexts, more than three product files, unrelated acceptance criteria, multiple migrations, a contract plus implementation, or both happy path and a large independent failure matrix.

## Dependency rules

- Depend only on stable task IDs.
- A task may start only after all dependencies are accepted.
- Contract and migration precede implementations that consume them.
- Domain precedes adapters/routes; backend contract precedes UI integration.
- Tests may be authored with implementation when narrow, but cross-cutting suites are separate.
- Phase gates are explicit nodes, not implied dates.

## Approval classification

`human_approval_required` and `approval_reasons` retain their historical/schema classification. For assigned local/synthetic work, [DEC-023](../00-governance/LOCAL_EXECUTION_AUTHORITY_DECISION_20261007.md) satisfies the execution-authority requirement without a per-task human checkpoint. Preserve existing task files and flags; record DEC-023 in the execution evidence. Do not turn classification alone into a new permission request.

## Recovery

Recovery must be non-destructive: revert only the task's clean patch through reviewed reverse patch, disable via existing feature flag, stop before promotion, restore previous pointer/image, or leave additive artifacts unused. Never prescribe data deletion, hard reset or broad cleanup.

