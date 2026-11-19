---
document_id: "DOC-AGENT-009"
version: "1.1.0"
status: "approved"
owner: "Architecture and Security Governance"
approvers: ["Architecture Lead", "Security Lead", "Product Owner"]
last_updated: "2026-10-07"
---

# Approved Dependency and Runtime Allowlist

Tài liệu này ghi baseline ngôn ngữ, runtime và thư viện của Campus 24/7 (V1 — HUCE Demo) theo `TASK-DOC-STACK-001`. [DEC-023](../00-governance/LOCAL_EXECUTION_AUTHORITY_DECISION_20261007.md) ủy quyền executor tự review và thêm dependency/tool/runtime cần thiết cho công việc local/synthetic đã giao, không cần xin ADR/approval mới chỉ để cài gói ngoài baseline. Trước sử dụng, ghi purpose, exact version/source/hash, license/security/compatibility và transitive closure; cập nhật allowlist/lockfile hoặc manifest môi trường cô lập. Lockfiles hiện có và historical receipts giữ nguyên cho tới scoped dependency change có evidence.

## 1. Runtimes & Package Managers

| Thành phần | Phiên bản chuẩn | Giấy phép | Ghi chú |
|---|---|---|---|
| **Python** | `>= 3.12, < 3.14` | PSF | Runtime chính cho `services/api` và `services/worker` |
| **uv** | `>= 0.4.0` | Apache-2.0 / MIT | Quản lý gói và môi trường ảo Python |
| **Node.js** | `>= 20.x LTS` | MIT | Runtime thực thi cho `apps/web` |
| **pnpm** | `>= 9.x` | MIT | Quản lý gói và workspace cho Next.js web |

## 2. Python Backend & Worker Allowlist

| Thư viện | Mục đích sử dụng | Giấy phép | Bounded context |
|---|---|---|---|
| `fastapi` | Web framework REST & SSE | MIT | Presentation API |
| `uvicorn` | ASGI server | BSD-3-Clause | API Server bootstrap |
| `pydantic` | Data validation & settings | MIT | Domain & Schema validation |
| `pydantic-settings` | Quản lý cấu hình môi trường | MIT | Bootstrap / Settings |
| `sqlalchemy` | SQL toolkit & Object relational mapping | MIT | Infrastructure / Postgres |
| `asyncpg` | Async PostgreSQL driver | Apache-2.0 | Infrastructure / Database |
| `alembic` | Database schema migrations | MIT | Data migrations |
| `pgvector` | Hỗ trợ vector embeddings trong Postgres | PostgreSQL | Vector search & RAG |
| `redis` | Async Redis client cho cache và state | MIT | Infrastructure / Cache |
| `langgraph` | Máy trạng thái điều khiển Agent workflow | MIT | AI Agent Orchestrator |
| `httpx` | Async HTTP client (LLM gateway, mock SIS) | BSD-3-Clause | Ports & Adapters |
| `pytest` | Test runner cho unit và regression | MIT | Test suite |
| `pytest-asyncio` | Hỗ trợ async tests | Apache-2.0 | Test suite |
| `jsonschema` | Xác thực JSON Schema Draft 2020-12 | MIT | Contracts & Test validation |
| `pyyaml` | Xử lý cấu hình và spec YAML | MIT | Platform & Catalog tools |

## 3. Web Frontend Allowlist

| Thư viện | Mục đích sử dụng | Giấy phép | Bounded context |
|---|---|---|---|
| `next` | React framework (App Router) | MIT | Web UI & SSR |
| `react`, `react-dom` | Thư viện UI component | MIT | Web UI |
| `typescript` | Type checking tĩnh | Apache-2.0 | Web development |
| `tailwindcss` | Utility-first CSS styling | MIT | Styling & Responsive |
| `@axe-core/react` | Kiểm tra khả năng tiếp cận WCAG cục bộ | MPL-2.0 | Accessibility testing |

## 4. Nguyên tắc an toàn chuỗi cung ứng (Supply Chain Policy)

- Cấm thư viện sử dụng giấy phép copyleft nghiêm ngặt (GPLv3, AGPL) trong mã nguồn phân phối thương mại.
- Mọi gói cài đặt bắt buộc phải có hash kiểm tra toàn vẹn trong lockfile.
- Không tải trực tiếp thư viện từ URL mạng công cộng khi build CI không qua lockfile.
