---
document_id: "DOC-DEL-007"
version: "1.1.0"
status: "reviewed"
owner: "Change Management Lead"
approvers: ["Product Owner", "Architecture Lead", "Security Lead", "Release Owner"]
last_updated: "2026-10-07"
---

# Change control

[DEC-023](../00-governance/LOCAL_EXECUTION_AUTHORITY_DECISION_20261007.md) replaces additional role/task/package approvals for assigned local/synthetic engineering. The executor performs the affected technical assessments, records versions/targets/evidence and proceeds. Role approvals below are baseline responsibility metadata, not repeated human execution checkpoints in this scope.

## 1. Principle

Every behavior-affecting change is intentional, traceable, reviewed, tested and reversible/degradable. Implementation never edits upstream requirements/contracts/tests merely to legitimize current output. Silence or successful deployment is not approval.

## 2. Change classes

| Class | Examples | Required approval/gates |
|---|---|---|
| C0 Editorial | typo/layout, no normative/ID/contract meaning | document owner; trace/link check |
| C1 Compatible implementation | internal refactor or optional compatible field with same behavior | ENG + QE; affected deterministic gates |
| C2 Behavioral | new/changed user outcome, workflow, KPI, prompt/model/routing | PO + ARCH + QE; AI/SEC/OPS as affected; full trace/eval |
| C3 Breaking contract/data | required field removal/rename/semantic change, incompatible event/migration | ARCH + consumers + QE + REL; version/migration/rollback |
| C4 Security/privacy/identity | auth, authorization, data class/flow/retention/egress/crypto | SEC/PRIV mandatory; threat/DPIA/control/evidence |
| C5 Platform/cost | datastore, queue, provider, region, public surface, paid dependency | ARCH + OPS + SEC + FIN; ADR/capacity/cost/rollback |
| C6 Emergency containment | disable/safe mode/rollback to stop active harm | authorized incident roles; audit; post-change verify/retrospective |

When uncertain, classify higher and perform every affected technical assessment. Multiple classes do not add human checkpoints for work covered by DEC-023.

## 3. Change request contract

```yaml
change_request:
  change_id: CR-<year>-<sequence>
  title: <short>
  status: proposed|impact_assessed|approved|scheduled|implemented|verified|rejected|rolled_back
  classes: [C2]
  requester_role: <role>
  reason_and_outcome: <text>
  scope_in: []
  scope_out: []
  affected_ids: []
  affected_files_components: []
  data_security_privacy_impact: <text>
  compatibility_migration: <text>
  test_gate_plan: []
  rollout_plan_ref: <ref>
  rollback_plan_ref: <ref>
  cost_capacity_impact: <text>
  risk_ids: []
  owner_role: <role>
  approvals: []
  requested_window: <nonbinding-or-null>
```

Unknown impact is not an empty field; use `unknown` and block approval.

## 4. Workflow

1. Submit problem/outcome and proposed scope; do not begin implementation.
2. Classify and identify authoritative IDs/artifacts.
3. Assess product, architecture, contract/data, security/privacy, AI, operations, cost, test and rollback impacts.
4. Resolve conflicts/create prerequisite requirement/ADR/contract tasks.
5. Record DEC-023 authority and affected technical assessments for delegated local work; use separate external authority only when the operation lies outside that scope.
6. Decompose into disjoint ready micro-tasks and update dependency DAG.
7. Implement and verify against unchanged approved oracle.
8. Assemble candidate, run affected + regression gates, execute authorized rollout.
9. Verify outcome, update evidence/risk/trace and close or rollback.

A rejected/expired request remains in history; its ID is not reused.

## 5. Impact checklist

Every C2–C5 assessment answers:

- Which `OBJ/KPI/REQ/UC` changes and why?
- Which `ARCH/ADR/API/EVT/DATA/TOOL` consumer is affected?
- Does actor, permission, data class/purpose/location/retention or LLM payload change?
- Does source/model/prompt/tool/retrieval/safety behavior change?
- Does SLO, capacity, cost, cache, retry, failure/degraded state or runbook change?
- Is migration backward-compatible and what is rollback/forward recovery?
- Which `TEST/EVAL/GATE` changes and is the oracle independently approved?
- Which docs, training, support copy and communications change?
- Can scope stay single-institution and synthetic-only? If not, it is future/blocking work.

## 6. Protected changes

Necessary local dependency, contract/architecture, synthetic auth/grant, fixture-guard, runtime and index changes proceed under DEC-023 with impact/version/technical evidence. Requirements, threshold/gold oracles are not rewritten to hide failure. Destructive migration/recovery, real data, new external expenditure, production deployment and deletion/reset/force-push remain outside local delegation.

## 7. Emergency change

C6 is for containment, not feature delivery. Allowed actions are pre-approved reversible safe mode, capability disable or rollback within incident role authority. Record actor/time/reason/scope/config before-after/correlation, verify containment and preserve evidence. No emergency path permits invented contact, bypassed audit, destructive database operation or unapproved data transfer. Create retrospective and standard corrective change after stability.

## 8. Threshold/test change rule

A failing test may reveal either code defect or invalid oracle. The implementer MUST NOT decide alone. Oracle/threshold/gold-label change requires upstream evidence, independent QE/domain review, impact on baseline/trends and a separate change ID. Historical reports remain unchanged.

## 9. Close criteria

Change closes only when implemented candidate and affected gates pass, runtime/config matches manifest, outcome metric is observable, rollback remains valid, docs/trace/risk are updated and approvers accept residual risk. Otherwise status is `implemented` or `blocked`, not `verified`.
