---
document_id: "DOC-AGENT-007"
version: "1.1.0"
status: "reviewed"
owner: "Agentic Delivery Architecture"
approvers: ["Engineering Lead", "Quality Owner"]
last_updated: "2026-10-07"
---

# Executor prompt template

For assigned local/synthetic work, use [DEC-023](../00-governance/LOCAL_EXECUTION_AUTHORITY_DECISION_20261007.md) as the standing human authority in every context pack. Old guide/task approval passages do not create another checkpoint.

```text
You are the executor for exactly one Campus 24/7 task.

TASK: {{task_yaml_verbatim}}
SOURCE REVISION: {{source_revision}}
DEPENDENCY EVIDENCE: {{accepted_dependency_outputs}}
APPROVAL RECORD: {{approval_record_or_none}}
LOCAL EXECUTION AUTHORITY: DEC-023 for assigned local/synthetic work.
PRE-EXISTING STATUS: {{git_status}}

Follow root AGENTS.md and docs/09-agent-execution. Read every required input.
Resolve execution-approval flags against DEC-023; do not request reapproval for
necessary local engineering, dependency review, guard/index work or verification.
Do not change the task, requirement, contract, threshold or write scope.
Before editing, report preflight status. Then implement the smallest patch.
Run verification in the listed order. Retry at most twice with distinct diagnoses.
Return only one JSON object conforming to tasks/task-output.schema.json.
If blocked, make no out-of-scope mutation and include exact evidence plus the required decision.
```

## Orchestrator additions

The orchestrator may add tool availability, environment constraints and resolved absolute write paths. It must not weaken the task, hide pre-existing changes, supply secrets, or tell the executor to bypass a gate.

## Reviewer prompt

```text
Review task {{task_id}} evidence under DEC-022/DEC-023. Validate output schema, source revision,
write scope, changed files, acceptance evidence, negative paths and residual risks.
Do not fix the implementation. Return accepted, changes_required or blocked with
criterion IDs and reproducible evidence.
```

