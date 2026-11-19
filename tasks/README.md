# Campus 24/7 implementation task catalog

Kế hoạch triển khai hiện tại: [đồ án tốt nghiệp Campus 24/7](../docs/GRADUATION_PROJECT_PLAN_20261013.md). Catalog, DAG, trạng thái và task outputs trong thư mục này được giữ nguyên để tham khảo và bảo toàn bằng chứng; chúng chưa phải backlog được phân rã cho kế hoạch đồ án mới.

Sáu kế hoạch cũ được lưu tại [archive/legacy-plans-20261013](../archive/legacy-plans-20261013/README.md). Quy trình lịch sử bên dưới không thay thế yêu cầu trực tiếp hiện tại hoặc hướng dẫn thực thi trong `AGENTS.md`; các kiểm soát bảo vệ dữ liệu và bảo mật vẫn áp dụng.

[DEC-023](../docs/00-governance/LOCAL_EXECUTION_AUTHORITY_DECISION_20261007.md) supplies standing human authority for assigned local/synthetic work. Preserve task approval classifications and historical outputs, but do not require a new approval by task ID or package. Technical dependencies, scope and verification remain necessary.

This directory is the machine-readable delivery plan from an empty implementation repository to a production-ready single-institution product.

## Files

- `task.schema.json` validates every `items/*.yaml` task.
- `task-output.schema.json` validates executor results.
- `task-index.yaml` is the ordered catalog.
- `dag.yaml` is the dependency graph and phase-gate view.
- `items/` contains one immutable file per micro-task.
- `templates/` and `examples/` support task authors.
- `tools/validate_catalog.py` validates YAML/JSON, schemas, references and cycles.
- `tools/generate_catalog.py` is the deterministic source used to materialize the initial catalog. It refuses to overwrite files.

## Workflow

1. Run `python tasks/tools/validate_catalog.py`.
2. Select a `ready` task whose dependencies are `accepted`.
3. Resolve and lease its write scope.
4. Dispatch it with the prompt in `docs/09-agent-execution/PROMPT_TEMPLATE.md`.
5. Validate the returned JSON against `task-output.schema.json`.
6. Review evidence and record technical acceptance; authorized executor review is permitted under DEC-022/DEC-023 for delegated local/synthetic work.

Initial task/source status is historical metadata. Establish current technical readiness from source/dependency evidence under DEC-023; an older human-approval flag alone does not block assigned local execution.

## Phase map

| Phase | Outcome |
|---|---|
| P00 | normative readiness, dependency allowlist and repository skeleton |
| P01 | runnable local foundation and CI |
| P02 | data model, additive migrations and deterministic fixtures |
| P03 | identity, authorization, action control, audit and outbox |
| P04 | RAG, LLM gateway, controlled graph, memory and guardrails |
| P05 | backend vertical slices and APIs |
| P06 | accessible responsive web experiences |
| P07 | eval, security, integration and end-to-end quality gates |
| P08 | AWS IaC, observability, performance and recovery hardening |
| P09 | pilot, release candidate and human-gated production launch |

## Authoring rules

Copy the template; assign a never-reused ID; keep one objective; list exact dependencies; limit writes to three paths; provide positive and failure-path acceptance; use non-destructive recovery; and run the catalog validator. A changed task is a new reviewed version, not an undocumented edit after execution began.

