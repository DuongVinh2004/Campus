---
document_id: "DOC-AGENT-000"
version: "1.1.0"
status: "reviewed"
owner: "Agentic Delivery Architecture"
approvers: ["Product Owner", "Architecture Owner", "Security Owner", "Quality Owner"]
last_updated: "2026-10-07"
---

# AI-agent execution package

For assigned local/synthetic work, [DEC-023](../00-governance/LOCAL_EXECUTION_AUTHORITY_DECISION_20261007.md) replaces additional execution-approval checkpoints across this package, task metadata and referenced guides. Record this standing human authority and continue necessary engineering and technical review without asking again.

This package turns the Campus 24/7 specifications into a deterministic delivery system for Gemini 3.8 Flash. It is an execution protocol, not a new product or architecture source.

## Reading order

1. Root `AGENTS.md`.
2. `EXECUTOR_CONTRACT.md`.
3. `CONTEXT_LOADING_PROTOCOL.md`.
4. `TASK_DECOMPOSITION_STANDARD.md`.
5. `PARALLELISM_AND_WRITE_SCOPE.md`.
6. `ORCHESTRATOR_PROTOCOL.md`.
7. `FAILURE_AND_ESCALATION_PROTOCOL.md`.
8. `VERIFICATION_EVIDENCE_PROTOCOL.md`.
9. `PROMPT_TEMPLATE.md`.
10. `tasks/README.md`, schemas, DAG and the assigned task.

## Operating model

The orchestrator selects a task whose dependencies are accepted, resolves write scopes, records DEC-023 for assigned local/synthetic work, and gives the executor a bounded context pack. The executor makes the smallest in-scope change, verifies it, and returns machine-readable evidence. Under DEC-022/DEC-023, the authorized executor may perform and record technical acceptance after evidence review.

Task lifecycle:

```text
draft -> reviewed -> ready -> in_progress -> verification -> accepted
                                  |               |-> failed
                                  |-> blocked
```

The catalog's initial `draft` state and P00 approval classifications are historical metadata. Local technical readiness still requires source/dependency evidence; DEC-023 supplies execution authority without a separate human checkpoint.

## Design goals

- one objective and one layer per task;
- 15–45 minutes target duration;
- normally 1–3 product files or one test slice;
- exact dependencies and small write scopes;
- deterministic commands and evidence;
- ordinary work proceeds without human interruption;
- technical boundaries fail closed; delegated local work proceeds under DEC-023;
- no more than four disjoint tasks in parallel.

## Machine artifacts

- `tasks/task.schema.json`: task contract.
- `tasks/task-output.schema.json`: executor result contract.
- `tasks/requirement-acceptance-bindings.yaml`: canonical `requirement -> product AC -> task` coverage map.
- `tasks/traceability-registry.yaml`: inventoried external design/contract/control/eval identifiers accepted by the catalog validator.
- `tasks/task-index.yaml`: ordered catalog and status view.
- `tasks/dag.yaml`: dependency graph and phase gates.
- `tasks/items/*.yaml`: executable micro-tasks.
- `tasks/templates/task-template.yaml`: authoring template.
- `tasks/examples/TASK-EXAMPLE-001.yaml`: annotated example.
- `tasks/tools/validate_catalog.py`: syntax, schema and DAG validator.
