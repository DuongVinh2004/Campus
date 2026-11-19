---
document_id: "DOC-AGENT-005"
version: "1.1.0"
status: "reviewed"
owner: "Agentic Delivery Architecture"
approvers: ["Engineering Lead", "Security Owner"]
last_updated: "2026-10-07"
---

# Failure and escalation protocol

[DEC-023](../00-governance/LOCAL_EXECUTION_AUTHORITY_DECISION_20261007.md) removes additional human execution-approval checkpoints for assigned local/synthetic work. `APPROVAL_REQUIRED` and `UNAPPROVED_DEPENDENCY` remain historical schema codes; do not raise them solely because an older task/package asks for reapproval within this delegation. Resolve dependencies with technical review and pinned records.

## Stop codes

Use one stable code: `SOURCE_NOT_APPROVED`, `SOURCE_CHANGED`, `MISSING_DEPENDENCY`, `MISSING_ARTIFACT`, `CONTRACT_MISMATCH`, `SCOPE_VIOLATION`, `WRITE_CONFLICT`, `APPROVAL_REQUIRED`, `UNAPPROVED_DEPENDENCY`, `SECURITY_DECISION_REQUIRED`, `DESTRUCTIVE_ACTION_REQUIRED`, `REAL_DATA_OR_SECRET_REQUIRED`, `PAID_SERVICE_REQUIRED`, `PRODUCTION_ACCESS_REQUIRED`, `VERIFICATION_UNAVAILABLE`, or `ACCEPTANCE_FAILED`.

## Escalation payload

Return the task-output schema with:

- exact blocker code and one-sentence summary;
- source IDs and path/line evidence;
- work safely completed before the blocker;
- changed files, if any;
- safe state of the repository/system;
- one to three bounded options;
- the exact missing information or external authority required; do not ask again for local execution authority already supplied by DEC-023.

Do not ask broad questions such as “what should I do?”. Never invent an answer to continue.

## Failure budget

Run a failing command once, diagnose from evidence, and attempt at most two distinct in-scope fixes. Repeating the same command without a state change does not count as progress. Infrastructure/network/transient failures may be retried only within the task's explicit policy.

## Delegated local execution

Record the exact target, effect, technical checks and preservation method before mutation, then execute local/synthetic work under DEC-023. A newly identified target required by the same objective updates the execution record; it does not trigger another human approval request. Escalate missing technical information or a genuinely external/destructive boundary with concrete evidence.

