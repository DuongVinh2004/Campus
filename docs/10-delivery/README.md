---
document_id: "DOC-DEL-000"
version: "1.0.0"
status: "reviewed"
owner: "Delivery and Release Engineering Lead"
approvers: ["Product Owner", "Architecture Lead", "Quality Lead", "Security Lead", "Operations Lead"]
last_updated: "2026-09-22"
---

# Delivery and release package

Kế hoạch triển khai hiện tại: [đồ án tốt nghiệp](../GRADUATION_PROJECT_PLAN_20261013.md). Gói delivery bên dưới được giữ làm tham khảo lịch sử; vị trí của sáu kế hoạch đã chuyển nằm trong [bảng lưu trữ và phục hồi](../../archive/legacy-plans-20261013/README.md). Tài liệu rollback, bảo mật và bằng chứng vận hành được giữ nguyên.

## 1. Mục đích

Gói này quy định cách chuyển executable specification của Campus 24/7 thành các increment có thể kiểm chứng, release candidate bất biến và quyết định promotion fail-closed. Kế hoạch là capability-gated, không hứa ngày. Mọi trạng thái triển khai hiện tại là `planned`; không tài liệu nào tuyên bố hệ thống đã build, deploy hoặc được HUCE phê duyệt.

## 2. Ranh giới delivery

- Một trường, nhãn `HUCE Demo`, không SaaS/multi-tenancy/billing.
- Synthetic-only cho mọi phase hiện được phép; production/real integration bị chặn.
- Next.js web, FastAPI API/worker, PostgreSQL/pgvector, Redis, LangGraph, DeepSeek qua provider-neutral gateway, AWS ECS/Fargate theo ADR.
- Coding agent không có quyền đổi requirement/contract/ADR/security threshold, dùng secret thật, mua service, deploy production, xóa dữ liệu hoặc thực hiện Git/filesystem destructive action.
- Release quality gates trong `docs/08-quality/RELEASE_QUALITY_GATES.md` là điều kiện promotion, không phải checklist tham khảo.

## 3. Tài liệu

| File | Nội dung |
|---|---|
| [DELIVERY_PLAN.md — lưu trữ](../../archive/legacy-plans-20261013/docs/10-delivery/DELIVERY_PLAN.md) | Delivery model, workstream, dependency và execution wave cũ |
| `PHASE_AND_MILESTONE_GATES.md` | Foundation/MVP/Pilot/Production entry-exit gates |
| `DEFINITION_OF_READY_DONE.md` | DoR/DoD cho task, increment, RC và phase |
| `RELEASE_STRATEGY.md` | Artifact, version, environment, rollout và promotion strategy |
| `RISK_REGISTER.md` | Risk, trigger, owner, mitigation, contingency và gate |
| `RACI.md` | Quyền quyết định và trách nhiệm |
| `CHANGE_CONTROL.md` | Phân loại, impact, approval và emergency change |
| `LAUNCH_AND_ROLLBACK_PLAN.md` | Go/no-go, execution, abort/rollback/recovery |
| [POST_LAUNCH_OPERATING_PLAN.md — lưu trữ](../../archive/legacy-plans-20261013/docs/10-delivery/POST_LAUNCH_OPERATING_PLAN.md) | Verification, hypercare, incident/problem và review của kế hoạch cũ |

## 4. Stable IDs

- milestones: `MS-FOUND-*`, `MS-MVP-*`, `MS-PILOT-*`, `MS-PROD-*`;
- release candidates: `RC-<semver>-<sequence>`;
- releases: `REL-<semver>`;
- risks: `RSK-###`; changes: `CR-<year>-###`; decisions: `RELDEC-<candidate>-<sequence>`;
- rollback executions: `RBK-<release>-<sequence>`.

ID is immutable and never reused. Release status: `planned`, `building`, `candidate`, `rejected`, `approved_non_production`, `released`, `rolled_back`, `superseded`. Only authorized human approvers may set production `released`.

## 5. Source-of-truth rules

A release manifest references exact source revision, image digests, infrastructure/config/contract/schema/dataset/prompt/model/index/tool-policy versions and evidence bundle. Environment-specific secrets are never in manifest. A changed byte/version creates a new candidate; evidence is not silently inherited.

## 6. Agent execution behavior

Gemini Flash works only on a `ready` micro-task whose dependencies are `accepted`, write scope is explicit/disjoint and verification command exists. Agent stops on contract conflict, missing fixture, sensitive approval, out-of-scope file, real data/secret or destructive action. Completion output reports changed files, commands/exit codes, test/evidence IDs, deviations and residual risk.

## 7. Current delivery state

`MS-FOUND-001` documentation specification is being prepared; no milestone is declared passed. `MS-PROD-*` remains blocked by `OQ-001`–`OQ-008`, security/privacy launch approvals, official contacts/owners, Entra and real integration contracts.
