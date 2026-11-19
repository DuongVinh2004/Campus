---
document_id: "DOC-GOV-NAV-001"
version: "1.2.0"
status: "reviewed"
owner: "Delivery Navigator"
last_updated: "2026-10-07"
navigation_status: "COMPLETED"
---

# Campus 24/7 — Tài liệu Điều hướng Thực thi (Execution Navigator)

Quy tắc thực thi hiện hành: [DEC-023](LOCAL_EXECUTION_AUTHORITY_DECISION_20261007.md) bỏ checkpoint xin phê duyệt bổ sung cho công việc local/synthetic đã giao. Các bảng, gate và approval entries từ ngày 2026-09-22 bên dưới là hồ sơ tại thời điểm đó; không dùng chúng để yêu cầu task-specific/package-specific approval lại. Source/dependency readiness và technical acceptance vẫn phải có evidence hiện tại.

Tài liệu này là bản đồ điều hướng thực thi và kiểm soát tiến độ thống nhất dành cho Orchestrator và các AI coding agent trong dự án Campus 24/7 (phiên bản V1 — HUCE Demo). 

Tài liệu hoạt động dưới sự chỉ đạo của `AGENTS.md`, tuân thủ nghiêm ngặt thứ tự quyền lực chuẩn (`Authority Order`), không tự tiện thay đổi requirement, contract hay trạng thái phê duyệt của bất kỳ thực thể nào.

---

## 1. Executive Status (Tổng quan Trạng thái Điều hành)

| Chỉ số | Giá trị | Ghi chú kỹ thuật |
|---|---|---|
| **Tổng số Task** | **176** | Phân bổ từ `P00` đến `P09`. 176 task đã hoàn thành (`accepted`/`completed`), 0 task đang chờ. |
| **Tiến độ Thực thi** | **176 / 176 (100.0%)** | P00: 10/10 (100%), P01: 12/12 (100%), P02: 16/16 (100%), P03: 16/16 (100%), P04: 29/29 (100%), P05: 30/30 (100%), P06: 17/17 (100%), P07: 16/16 (100%), P08: 18/18 (100%), P09: 12/12 (100%). |
| **Tổng số Phase** | **10** | Phân bổ từ `P00` đến `P09` theo đồ thị tuần tự DAG. 10/10 Phase đã hoàn thành. |
| **Tổng số Requirement** | **125** | 77 Functional Requirements (FR) + 48 Non-Functional Requirements (NFR). Trạng thái: `approved` cho synthetic. |
| **Tổng số Acceptance Criteria (AC)** | **125** | 100% requirement có tối thiểu 1 AC ràng buộc trực tiếp trong `tasks/requirement-acceptance-bindings.yaml`. |
| **Task yêu cầu Human Approval** | **73** | Đã được Product Owner cấp quyền phê duyệt cho toàn bộ môi trường mô phỏng HUCE Demo. |
| **Task không yêu cầu Human Approval** | **103** | Task kỹ thuật trong phạm vi synthetic nội bộ, thực thi theo DAG khi upstream đã hoàn tất. |
| **Số task sẵn sàng thực thi tiếp theo (NOW)** | **100% HOÀN TẤT** | Toàn bộ 176 task đã hoàn thành nghiệm thu. Sẵn sàng phát hành Release Candidate 1 (1.0.0-rc1). |

### Phân bổ Task theo Phase

| Phase | Tên Phase | Số Task | Trạng thái | Đã hoàn thành |
|---|---|---:|---|---:|
| **P00** | Normative readiness and repository bootstrap | 10 | **COMPLETED** | 10 / 10 |
| **P01** | Runnable local foundation and CI | 12 | **COMPLETED** | 12 / 12 |
| **P02** | Data model, migrations and synthetic fixtures | 16 | **COMPLETED** | 16 / 16 |
| **P03** | Identity, authorization, action control, audit and outbox | 16 | **COMPLETED** | 16 / 16 |
| **P04** | RAG, LLM gateway, controlled agent, memory and guardrails | 29 | **COMPLETED** | 29 / 29 |
| **P05** | Backend vertical service slices | 30 | **COMPLETED** | 30 / 30 |
| **P06** | Responsive accessible web experiences | 17 | **COMPLETED** | 17 / 17 |
| **P07** | Quality, evaluation and security hardening | 16 | **COMPLETED** | 16 / 16 |
| **P08** | AWS platform, observability, performance and recovery | 18 | **COMPLETED** | 18 / 18 |
| **P09** | Pilot, release and launch | 12 | **COMPLETED** | 12 / 12 |
| **Tổng** | **10 Phases** | **176** | **10 PHASES COMPLETED (100.0%)** | **176 / 176** |

### Các Rào cản Toàn cục (Global Blockers)

1. **Rào cản Vòng đời Task (Task Lifecycle Gate)**:
   Toàn bộ 176 task đều đang có trạng thái `draft`. Theo khế ước `AGENTS.md` (mục *Before any mutation* số 4) và `DOC-AGENT-001` (`EXECUTOR_CONTRACT.md`), coding agent tuyệt đối không được nhận hoặc thực thi task nếu task chưa có `status: ready` và toàn bộ dependency chưa đạt `accepted`.
2. **Quyền thực thi hiện hành (DEC-023)**:
   Phân loại approval của 73/176 task là metadata lịch sử. Công việc local/synthetic đã giao sử dụng standing human authority DEC-023, không cần xin approval mới theo task ID. Chỉ đưa task vào thực thi khi dependency và technical readiness được kiểm chứng.
3. **Rào cản Trạng thái Tài liệu Nguồn (Upstream Artifact Status)**:
   Tài liệu requirement trung tâm `DOC-PROD-012` (`docs/01-product/requirements.yaml`) hiện ở trạng thái `reviewed`, chưa phải `approved`. Các tài liệu kiến trúc (`docs/04-architecture/**`), bảo mật (`docs/06-security/**`), hạ tầng platform (`docs/07-platform/**`), thiết kế dịch vụ (`docs/02-service-design/**`) và UX (`docs/03-ux/**`) hiện là `draft` hoặc `reviewed`.
4. **Rào cản Câu hỏi Mở (OQ-001 đến OQ-008)**:
   Theo `docs/00-governance/ASSUMPTIONS_AND_OPEN_QUESTIONS.md`, 8 câu hỏi mở cốt lõi đang mở (`open`). Các câu hỏi này chặn toàn bộ việc tiếp cận dữ liệu thật, tích hợp thật với HUCE, tài khoản Entra ID trường học, kết nối mạng trực tiếp tới LLM bên thứ 3 và triển khai production.
5. **Rào cản Dữ liệu Thực tế và Môi trường Ngoài (Real-Data & Environment Restrictions)**:
   Hệ thống V1 được đóng khung là mô phỏng nội bộ (`HUCE Demo`) chỉ dùng dữ liệu tổng hợp (`synthetic-only`). Cấm đưa dữ liệu sinh viên/giảng viên thật, cấm gọi API live có tính phí (DeepSeek production, AWS live resources), cấm lưu trữ secret thật vào mã nguồn.

---

## 2. Thứ tự Triển khai Chuẩn (Standard Deployment Sequence: P00 — P09)

Mỗi phase là một cổng kiểm soát chất lượng và kiến trúc (quality gate), không phải ước tính lịch trình thời gian.

```text
[P00: Normative & Repo Bootstrap]
               |
               v
[P01: Local Foundation & CI]
               |
               v
[P02: Data Model, Migrations & Fixtures]
               |
               v
[P03: Identity, Authz, Action Control & Outbox]
               |
               v
[P04: RAG, LLM Gateway, Controlled Agent & Guardrails]
               |
               v
[P05: Backend Vertical Service Slices]
               |
               v
[P06: Responsive Accessible Web Experiences]
               |
               v
[P07: Quality, Evaluation & Security Hardening]
               |
               v
[P08: AWS Platform, Observability, Perf & Recovery]
               |
               v
[P09: Pilot, Release & Launch Gates]
```

### Phase P00: Normative Readiness and Repository Bootstrap (10 tasks)

- **Mục tiêu**: Thiết lập tính hợp pháp của tài liệu chuẩn, phê duyệt danh mục requirement/contract/kiến trúc cho triển khai synthetic, phê duyệt allowlist thư viện và dựng khung xương thư mục dự án sạch.
- **Entry criteria**: Toàn bộ quyết định quản trị (DEC-001..DEC-021) đã được chấp thuận; danh mục task và DAG đã được kiểm tra tính hợp lệ về cấu trúc (`validate_catalog.py` pass).
- **Task theo Topo Order**:
  1. `TASK-DOC-GOV-001` (Approve product requirement baseline for synthetic implementation) [Approval Req]
  2. `TASK-DOC-ARCH-001` (Approve architecture and ADR baseline) [Approval Req]
  3. `TASK-DOC-CONTRACT-001` (Approve API data event and tool contracts) [Approval Req]
  4. `TASK-DOC-AI-001` (Approve AI RAG agent and evaluation baseline) [Approval Req]
  5. `TASK-DOC-SEC-001` (Approve security privacy and threat baseline) [Approval Req]
  6. `TASK-DOC-STACK-001` (Approve pinned dependency and runtime allowlist) [Approval Req] — phụ thuộc `ARCH-001`, `SEC-001`.
  7. `TASK-REPO-SCAFFOLD-001` (Create top-level implementation directory skeleton) — phụ thuộc `GOV-001`, `ARCH-001`, `CONTRACT-001`, `AI-001`, `SEC-001`.
  8. `TASK-REPO-CONFIG-001` (Add safe repository ignore and editor defaults) — phụ thuộc `SCAFFOLD-001`.
  9. `TASK-TEST-CATALOG-001` (Wire task catalog validation into preflight) — phụ thuộc `SCAFFOLD-001`.
  10. `TASK-DOC-DEV-001` (Document local bootstrap without secrets) — phụ thuộc `STACK-001`, `CONFIG-001`.
- **Cụm task song song hợp lệ**:
  - Nhóm 1: `TASK-DOC-GOV-001`, `TASK-DOC-ARCH-001`, `TASK-DOC-CONTRACT-001`, `TASK-DOC-AI-001`, `TASK-DOC-SEC-001` (5 root tasks có write scope và conflict keys hoàn toàn tách biệt; có thể chạy tối đa 4 task cùng lúc theo quy định max concurrency = 4).
  - Nhóm 2 (sau khi SCAFFOLD-001 hoàn thành): `TASK-REPO-CONFIG-001` và `TASK-TEST-CATALOG-001` (khác file, khác conflict key: `root-config` vs `delivery-tests`).
- **Exit criteria**: Toàn bộ 6 task tài liệu đã có văn bản phê duyệt; khung xương repository được tạo lập không chứa mã kinh doanh; preflight kiểm tra catalog tích hợp thành công.
- **Evidence bắt buộc**: Báo cáo phê duyệt human approval có chữ ký vai trò; log chạy `python tasks/tools/validate_catalog.py` (exit code 0); git status xác nhận chỉ các file trong allowed_paths bị tác động.
- **Giải thích phụ thuộc then chốt (Dependency Rationale)**:
  - Cấm viết bất kỳ file code/cấu hình nào trước khi 5 tài liệu baseline P00 được phê duyệt.
  - `TASK-DOC-STACK-001` phải làm sau `ARCH-001` và `SEC-001` vì danh mục thư viện (FastAPI, Next.js, pgvector, LangGraph, v.v.) phải phản ánh đúng quyết định kiến trúc và đáp ứng rà soát lỗ hổng bảo mật/giấy phép nguồn mở.
  - `TASK-REPO-SCAFFOLD-001` phải đứng sau cả 5 root tasks để đảm bảo khung cây thư mục `apps/`, `services/`, `packages/` được hình thành trên nền tảng quản trị đã được xác nhận.

---

### Phase P01: Runnable Local Foundation and CI (12 tasks)

- **Mục tiêu**: Thiết lập môi trường thực thi cục bộ (local runtime), khoá phiên bản phụ thuộc (lockfiles), khởi tạo ứng dụng rỗng (app factories), docker-compose cho hạ tầng phụ trợ (Postgres/Redis) và đường ống CI offline.
- **Entry criteria**: Toàn bộ task P00 đạt trạng thái `accepted`; file allowlist `docs/09-agent-execution/DEPENDENCY_ALLOWLIST.md` đã được duyệt.
- **Task theo Topo Order**:
  1. `TASK-REPO-PYTHON-001` (Create pinned Python workspace manifest: `pyproject.toml`, `uv.lock`)
  2. `TASK-REPO-WEB-001` (Create pinned web workspace manifest: `package.json`, `pnpm-lock.yaml`, `pnpm-workspace.yaml`)
  3. `TASK-API-BOOT-001` (Create FastAPI application factory) — phụ thuộc `PYTHON-001`.
  4. `TASK-WORKER-BOOT-001` (Create worker process bootstrap) — phụ thuộc `PYTHON-001`.
  5. `TASK-WEB-BOOT-001` (Create Next.js application shell) — phụ thuộc `WEB-001`.
  6. `TASK-REPO-ENV-001` (Define validated non-secret environment settings) — phụ thuộc `API-BOOT-001`.
  7. `TASK-INFRA-LOCAL-001` (Add local PostgreSQL pgvector compose service) — phụ thuộc `CONFIG-001`.
  8. `TASK-INFRA-LOCAL-002` (Add local Redis compose service) — phụ thuộc `INFRA-LOCAL-001`.
  9. `TASK-API-HEALTH-001` (Implement liveness endpoint) — phụ thuộc `API-BOOT-001`.
  10. `TASK-API-HEALTH-002` (Implement bounded readiness endpoint) — phụ thuộc `API-HEALTH-001`, `REPO-ENV-001`.
  11. `TASK-TEST-CI-001` (Create offline lint type and unit CI job) — phụ thuộc `PYTHON-001`, `WEB-001`, `TEST-CATALOG-001`.
  12. `TASK-TEST-BOUNDARY-001` (Add architecture import-boundary test) — phụ thuộc `API-BOOT-001`, `WORKER-BOOT-001`.
- **Cụm task song song hợp lệ**:
  - `TASK-REPO-PYTHON-001` (conflict: `python-lock`) và `TASK-REPO-WEB-001` (conflict: `web-lock`) chạy song song hoàn hảo vì write scope không giao nhau.
  - Sau khi `PYTHON-001` xong: `TASK-API-BOOT-001` (`services/api/`) và `TASK-WORKER-BOOT-001` (`services/worker/`) chạy song song.
  - `TASK-INFRA-LOCAL-001` có thể chạy song song với `PYTHON-001`/`WEB-001`.
- **Exit criteria**: FastAPI liveness/readiness phản hồi 200 OK; Next.js hiển thị trang chào mừng kèm disclaimer mô phỏng; CI chạy pass toàn bộ unit tests và kiểm tra biên kiến trúc (`test_import_boundaries.py`).
- **Evidence bắt buộc**: Log terminal chạy test `test_app_boot.py`, `test_worker_boot.py`, `test_health_live.py`, `test_health_ready.py`, `test_import_boundaries.py` đạt exit code 0.
- **Giải thích phụ thuộc then chốt (Dependency Rationale)**:
  - Khóa phiên bản (`uv.lock`, `pnpm-lock.yaml`) bắt buộc hoàn thành trước khi viết mã nguồn API/Web nhằm ngăn chặn trôi dạt phiên bản thư viện (dependency drift).
  - Liveness endpoint (`API-HEALTH-001`) phải xong trước Readiness endpoint (`API-HEALTH-002`) vì readiness phụ thuộc vào cấu hình nạp từ `REPO-ENV-001` và kiểm tra kết nối tài nguyên nền.

---

### Phase P02: Data Model, Migrations and Synthetic Fixtures (16 tasks)

- **Mục tiêu**: Xây dựng mô hình dữ liệu quan hệ, các migration tuần tự thêm mới (additive migrations), hạt giống dữ liệu tổng hợp (deterministic synthetic fixtures), và kiểm thử khế ước schema (JSON Schema, OpenAPI, AsyncAPI).
- **Entry criteria**: P01 accepted; Docker Compose Postgres/pgvector cục bộ khởi động thành công và vượt qua health check.
- **Task theo Topo Order**:
  1. `TASK-TEST-SCHEMA-001` (Validate JSON Schema contracts against models)
  2. `TASK-TEST-OPENAPI-001` (OpenAPI contract validator) & `TASK-TEST-ASYNCAPI-001` (AsyncAPI contract validator) — phụ thuộc `TEST-SCHEMA-001`.
  3. `TASK-DATA-KERNEL-001` (Domain kernel data types and identifiers) — phụ thuộc `TEST-SCHEMA-001`, `REPO-PYTHON-001`.
  4. `TASK-DB-BASE-001` (Alembic migration foundation) — phụ thuộc `REPO-ENV-001`, `INFRA-LOCAL-001`.
  5. Chuỗi Migration tuần tự:
     `TASK-DB-MIG-001` -> `TASK-DB-IDENTITY-001` -> `TASK-DB-KNOWLEDGE-001` -> `TASK-DB-CONVERSATION-001` -> `TASK-DB-ACTION-001` -> `TASK-DB-TICKET-001` -> `TASK-DB-DOCREQ-001` -> `TASK-DB-BOOKING-001` -> `TASK-DB-OUTBOX-001`.
  6. `TASK-DATA-SEED-001` (Deterministic synthetic identity and academic seed data) — phụ thuộc `DB-IDENTITY-001`.
  7. `TASK-DATA-SEED-002` (Deterministic synthetic ticket booking and outbox seed data) — phụ thuộc `DATA-SEED-001`, `DB-OUTBOX-001`.
- **Cụm task song song hợp lệ**:
  - Nhóm Contract/Validation: `TASK-TEST-OPENAPI-001`, `TASK-TEST-ASYNCAPI-001`, `TASK-DATA-KERNEL-001` chạy song song sau khi `TEST-SCHEMA-001` accepted.
  - Tuyệt đối cấm song song: Toàn bộ chuỗi 9 migration từ `DB-MIG-001` đến `DB-OUTBOX-001` cùng giữ conflict key `db-migration-head`, bắt buộc chạy tuần tự từng migration một.
- **Exit criteria**: Toàn bộ migration áp dụng sạch sẽ vào database cục bộ không có lỗi; seed data nạp thành công 100% dữ liệu synthetic với hash cố định (deterministic); không có PII/dữ liệu thực.
- **Evidence bắt buộc**: Log alembic upgrade head; kết quả chạy `pytest tests/data/` và `pytest tests/contracts/` exit code 0.
- **Giải thích phụ thuộc then chốt (Dependency Rationale)**:
  - Khế ước schema (`TEST-SCHEMA-001`) phải đi trước code thực thể để bảo đảm data dictionary thống nhất.
  - Các migration phải xếp theo trật tự phụ thuộc khoá ngoại: Identity (User) -> Knowledge -> Conversation -> Action -> Ticket -> DocReq -> Booking -> Outbox.
  - Outbox table nằm cuối cùng vì nó ghi nhận sự kiện của tất cả các thực thể nghiệp vụ trước đó.

---

### Phase P03: Identity, Authorization, Action Control, Audit and Outbox (16 tasks)

- **Mục tiêu**: Xây dựng phân hệ danh tính mô phỏng (synthetic identity), phân quyền mặc định từ chối (default-deny RBAC/ABAC), kiểm soát hành động nhạy cảm (preview/confirm/idempotency token), ghi log kiểm toán bất biến và tiến trình quét transactional outbox.
- **Entry criteria**: P02 accepted; seed data người dùng và bảng kiểm toán outbox đã sẵn sàng.
- **Task theo Topo Order**:
  1. `TASK-API-IDENTITY-001` (Synthetic actor context extraction) [Approval Req]
  2. `TASK-API-IDENTITY-002` (Demo login and token exchange) [Approval Req] -> `TASK-API-IDENTITY-003` (Session derivation middleware) [Approval Req] -> `TASK-API-IDENTITY-004` (Demo role switching) [Approval Req] -> `TASK-API-IDENTITY-005` (Internal claims mapping) [Approval Req].
  3. `TASK-API-POLICY-001` (Default-deny authorization engine) [Approval Req] -> `TASK-API-POLICY-002` (Student scoped policies) [Approval Req] / `TASK-API-POLICY-003` (Staff/Admin scoped policies) [Approval Req].
  4. `TASK-API-ACTION-001` (Action preview generator) [Approval Req] -> `TASK-API-ACTION-002` (Confirmation token binder) [Approval Req] -> `TASK-API-ACTION-003` (Idempotent action execution adapter) [Approval Req].
  5. `TASK-API-AUDIT-001` (Structured immutable audit logger) [Approval Req].
  6. `TASK-WORKER-OUTBOX-001` (Transactional outbox polling worker) & `TASK-WORKER-EVENT-001` (Internal event dispatcher).
  7. `TASK-TEST-AUTHZ-001` (Comprehensive RBAC/ABAC security test suite) & `TASK-TEST-ACTION-001` (Action preview/confirm idempotency test suite).
- **Cụm task song song hợp lệ**:
  - `TASK-WORKER-OUTBOX-001` và `TASK-WORKER-EVENT-001` (trong worker, không đụng presentation API).
  - `TASK-API-POLICY-002` và `TASK-API-POLICY-003` (sau khi `POLICY-001` accepted).
  - `TASK-TEST-AUTHZ-001` và `TASK-TEST-ACTION-001` (chạy song song ở tầng test).
- **Exit criteria**: Đăng nhập synthetic thành công với 4 role (student, officer, know_admin, sys_admin); mọi request không có token bị từ chối 401/403; hành động ghi đòi hỏi preview/confirm hợp lệ; outbox worker chuyển giao sự kiện đáng tin cậy.
- **Evidence bắt buộc**: Báo cáo test ma trận phân quyền 100% pass; log kiểm toán ghi nhận mọi đột biến; test idempotency xác nhận không bị ghi đúp khi gọi lặp.
- **Giải thích phụ thuộc then chốt (Dependency Rationale)**:
  - Identity Context (`IDENTITY-001`) phải hoàn thành trước Authorization Policy (`POLICY-001`) vì policy cần actor claims đáng tin cậy.
  - Khung Preview/Confirm/Idempotency (`ACTION-001..003`) phải hoàn thành trước các API nghiệp vụ P05 nhằm ngăn chặn model tự ý kích hoạt side-effects trực tiếp.

---

### Phase P04: RAG, LLM Gateway, Controlled Agent, Memory and Guardrails (29 tasks)

- **Mục tiêu**: Xây dựng cổng LLM trung lập (LLM gateway với fake provider cho test), chuỗi trích xuất tri thức RAG lai (hybrid lexical + vector search), bộ reranker, bộ trích xuất citation, máy trạng thái LangGraph có kiểm soát, bộ nhớ hội thoại và hàng rào an toàn (guardrails/handover).
- **Entry criteria**: P03 accepted; bảng knowledge và conversation đã sẵn sàng; fake LLM adapter đã cấu hình.
- **Task theo Topo Order**:
  1. `TASK-AGENT-LLM-001` (Provider-neutral LLM gateway interface) -> `LLM-002` (Deterministic fake provider for testing) -> `LLM-003` (Structured output parser) -> `PROMPT-001` (System prompts & templates) -> `LLM-004` (Token & cost tracker) -> `LLM-005` (DeepSeek production adapter draft behind gateway) [Approval Req].
  2. Tri thức & Ingestion: `TASK-DATA-CORPUS-001` (Synthetic HUCE corpus) -> `WORKER-INGEST-001..003` (Document parser, chunker, metadata extractor) -> `WORKER-EMBED-001` (Embedding worker) -> `WORKER-INDEX-001` (Hybrid indexer in pgvector).
  3. Retrieval & Citations: `API-RAG-001..004` (Lexical, vector, hybrid merger, query rewriter) -> `AGENT-RERANK-001` (Cross-encoder reranker) -> `API-CITATION-001` (Citation formatter) -> `API-EVIDENCE-001` (Grounding validator).
  4. Agent Graph & Safety: `AGENT-STATE-001` (Agent state definition) -> `AGENT-SAFETY-001` (Sensitive intent & emergency detector) [Approval Req] -> `AGENT-ROUTE-001` (Intent router) -> `AGENT-RAG-001` (RAG subgraph node) -> `AGENT-COMPOSE-001` (Response synthesizer) -> `AGENT-TOOL-001..002` (Authorized typed tools) [Approval Req] -> `AGENT-GRAPH-001` (Compiled LangGraph workflow) [Approval Req] -> `AGENT-CHECKPOINT-001` (Postgres checkpointer) -> `AGENT-MEMORY-001` (Summary memory manager) [Approval Req].
- **Cụm task song song hợp lệ**:
  - Nhánh LLM Gateway (`AGENT-LLM-001..003`) và nhánh Ingestion (`DATA-CORPUS-001`, `WORKER-INGEST-001`) chạy song song hoàn toàn độc lập.
  - `API-RAG-002` (Vector search) và `API-RAG-003` (Lexical search) có thể chạy song song sau khi `API-RAG-001` hoàn thành.
- **Exit criteria**: Fake provider vượt qua kiểm thử; pipeline RAG trả về câu trả lời có trích dẫn nguồn (citations) đạt ngưỡng grounding; LangGraph định tuyến chính xác các ca khẩn cấp sang handover; không phát sinh cuộc gọi mạng ngoài chưa duyệt.
- **Evidence bắt buộc**: Báo cáo đánh giá grounding trên tập fixture tổng hợp; kết quả chạy `test_agent_safety.py` và `test_graph_execution.py`.
- **Giải thích phụ thuộc then chốt (Dependency Rationale)**:
  - Gateway trung lập và fake provider bắt buộc đi trước Graph và Node để toàn bộ kiểm thử AI hoàn toàn offline và tiền định (deterministic).
  - Ingestion và Indexing phải hoàn thành trước RAG Retrieval; RAG Retrieval và Reranker phải đi trước Citation/Evidence Validation.
  - Node an toàn (`AGENT-SAFETY-001`) phải nằm ngay sau State và trước Intent Router để mọi ca khủng hoảng/nhạy cảm được tách luồng lập tức trước khi gọi LLM tạo câu trả lời.

---

### Phase P05: Backend Vertical Service Slices (30 tasks) — COMPLETED

- **Trạng thái**: **COMPLETED (30/30 tasks accepted)**
- **Mục tiêu**: Hiện thực hoá đầy đủ các API dịch vụ nghiệp vụ theo lát cắt dọc (vertical slices): Lịch học, Chat streaming, Yêu cầu giấy tờ (DocReq), Đặt phòng học (Room Booking), Bàn giao nhân sự (HITL Handover), Hàng đợi hỗ trợ (Staff Queue), Quản trị tri thức (Knowledge Admin), Quyền riêng tư (Privacy) và Giám sát vận hành (Operations).
- **Entry criteria**: P03 (Action/Policy/Identity) và P04 (Agent Graph/RAG) accepted.
- **Task theo Topo Order**:
  - Lịch học (Schedule): `TASK-API-SCHEDULE-001` -> `002` -> `003` [Approval Req].
  - Chat SSE: `TASK-API-CHAT-001` (Conversation management) -> `002` (SSE streaming chat) -> `003` (Chat feedback & rating).
  - Yêu cầu giấy tờ (DocReq): `TASK-API-DOCREQ-001` (Catalog) -> `002` (Submission via action confirmation) [Approval Req].
  - Đặt phòng (Room Booking): `TASK-API-ROOM-001` (Availability search) -> `002` (Booking reservation) [Approval Req] -> `003` (Cancellation & management) [Approval Req].
  - Ticket: `TASK-API-TICKET-001` -> `002` [Approval Req] -> `003` [Approval Req] -> `004` [Approval Req] -> `005` [Approval Req] -> `006` [Approval Req].
  - HITL Handover: `TASK-API-HITL-001` -> `002` [Approval Req] -> `003` [Approval Req].
  - Hàng đợi cán bộ (Staff Queue): `TASK-API-STAFF-001` -> `002` [Approval Req] -> `003` [Approval Req].
  - Quản trị tri thức: `TASK-API-KNOW-001` [Approval Req] -> `002` [Approval Req].
  - Quyền riêng tư: `TASK-API-PRIV-001` -> `002` [Approval Req].
  - Vận hành: `TASK-API-OPS-001` (Operational metrics and safe-mode switch).
- **Cụm task song song hợp lệ**:
  - Các lát cắt dọc độc lập có thể triển khai song song: Lát cắt Schedule (`TASK-API-SCHEDULE-001`), DocReq (`TASK-API-DOCREQ-001`), Room Booking (`TASK-API-ROOM-001`), Operations (`TASK-API-OPS-001`).
- **Exit criteria**: Toàn bộ endpoint OpenAPI v1 hoạt động đúng khế ước; luồng ghi (DocReq, Room, Ticket) thực hiện đầy đủ chu trình preview -> confirm token -> audit; SSE streaming hoạt động ổn định.
- **Evidence bắt buộc**: Kết quả test API integration và contract testing cho từng module với exit code 0.
- **Giải thích phụ thuộc then chốt (Dependency Rationale)**:
  - Mọi thao tác ghi của sinh viên đều phải tái sử dụng module Action Control của P03 để đảm bảo tính nhất quán (không bao giờ cho phép bypass preview/confirm).
  - Ticket là nền tảng trừu tượng của DocReq, do đó Ticket core đi trước DocReq.

---

### Phase P06: Responsive Accessible Web Experiences (17 tasks) — COMPLETED

- **Trạng thái**: **COMPLETED (17/17 tasks accepted)**
- **Mục tiêu**: Xây dựng giao diện web responsive, chuẩn accessibility (WCAG 2.2 AA), bao gồm: Chat surface với citation panel, Dashboard sinh viên, Form xác nhận preview/confirm, Giao diện cán bộ hỗ trợ (Staff Console), Quản trị viên tri thức (Knowledge Console) và Ops Dashboard.
- **Entry criteria**: P05 API cơ bản accepted; OpenAPI spec đồng bộ; Next.js app shell sẵn sàng.
- **Task theo Topo Order**:
  1. `TASK-WEB-DESIGN-001` (Design system tokens & accessible base components) -> `WEB-SHELL-001` (Responsive app shell with persistent disclaimer) -> `WEB-STATE-001` (Client session state store).
  2. `TASK-WEB-API-001` (Typed API client from OpenAPI contracts).
  3. Giao diện người dùng:
     - `TASK-WEB-CHAT-001` (Streaming chat interface) -> `002` (Chat history drawer) & `TASK-WEB-CITE-001` (Citation slide-out drawer).
     - `TASK-WEB-SCHEDULE-001` (Schedule view component).
     - `TASK-WEB-TICKET-001` (Student ticket portal) & `TASK-WEB-CONFIRM-001` (Modal preview/confirm dialog) [Approval Req].
     - `TASK-WEB-DOCREQ-001` & `TASK-WEB-ROOM-001` (Form đăng ký & đặt phòng).
     - `TASK-WEB-HITL-001` (Handover banner & emergency modal) [Approval Req].
     - `TASK-WEB-STAFF-001` (Staff inbox and ticket resolution queue) [Approval Req].
     - `TASK-WEB-KNOW-001` (Knowledge document lifecycle manager) [Approval Req].
     - `TASK-WEB-PRIV-001` (Privacy center & synthetic data notice).
     - `TASK-WEB-OPS-001` (System health, metric and safe-mode controls).
  4. `TASK-WEB-A11Y-001` (WCAG AA keyboard, aria & screen reader audit) & `TASK-WEB-RESPONSIVE-001` (Mobile/desktop reflow & responsive verification).
- **Cụm task song song hợp lệ**:
  - Sau khi `WEB-SHELL-001` và `WEB-API-001` hoàn thành: Các trang chức năng độc lập như `TASK-WEB-SCHEDULE-001`, `TASK-WEB-STAFF-001`, `TASK-WEB-KNOW-001`, `TASK-WEB-OPS-001` có thể chạy song song (tối đa 4 task).
- **Exit criteria**: Disclaimer "Campus 24/7 — HUCE Demo" và nhãn "Dữ liệu mô phỏng" hiển thị rõ ràng trên mọi màn hình; chat streaming hiển thị citation chính xác; form preview/confirm hiển thị cảnh báo hành động; kiểm tra a11y không có vi phạm WCAG mức nghiêm trọng.
- **Evidence bắt buộc**: Báo cáo kiểm tra a11y tự động (axe-core); ảnh chụp màn hình headless browser xác nhận luồng thao tác người dùng.
- **Giải thích phụ thuộc then chốt (Dependency Rationale)**:
  - Design tokens và App Shell phải đi trước các trang con để đảm bảo tính đồng bộ giao diện và disclaimer luôn hiện diện.
  - Typed API Client (`WEB-API-001`) phải hoàn thành trước khi gắn dữ liệu vào các component UI.

---

### Phase P07: Quality, Evaluation and Security Hardening (16 tasks)

- **Mục tiêu**: Đóng băng chất lượng bằng bộ kiểm thử toàn diện: AI evaluation gates (Faithfulness, Answer Relevance, Context Precision), Red-teaming chống prompt injection, Kiểm thử khế ước (Contract tests), E2E flows, Quét lỗ hổng bảo mật và Kiểm thử chuỗi cung ứng (Supply chain).
- **Entry criteria**: P05 (Backend) và P06 (Frontend) hoàn thành; bộ dữ liệu đánh giá tổng hợp sẵn sàng.
- **Task theo Topo Order**:
  1. `TASK-EVAL-SCHEMA-001` -> `TASK-EVAL-RAG-001` / `TASK-EVAL-SAFE-001` [Approval Req] / `TASK-EVAL-RED-001` -> `TASK-EVAL-RUNNER-001` -> `TASK-EVAL-GATE-001` (Cổng chặn chất lượng AI) [Approval Req].
  2. `TASK-TEST-CONTRACT-001` (Full contract verification across all boundaries).
  3. `TASK-TEST-E2E-001` (End-to-end grounded FAQ & citation flow).
  4. `TASK-TEST-E2E-002` (End-to-end ticket & room confirmation flow).
  5. `TASK-TEST-E2E-003` (End-to-end sensitive case emergency handover flow) [Approval Req].
  6. `TASK-TEST-SEC-001` (OWASP LLM Top 10 & prompt injection penetration suite).
  7. `TASK-TEST-SEC-002` (Broken object level authorization BOLA & tenant leak tests).
  8. `TASK-TEST-SEC-003` (Document upload security and path traversal tests).
  9. `TASK-TEST-SEC-004` (CSRF, XSS, CSP & session fixation web security tests).
  10. `TASK-TEST-SUPPLY-001` (Dependency vulnerability CVE audit & SBOM generation) [Approval Req].
  11. `TASK-TEST-LOAD-001` (Local simulated peak load benchmark: 200 concurrent users).
- **Cụm task song song hợp lệ**:
  - Các bài kiểm thử bảo mật `SEC-001`, `SEC-002`, `SEC-003`, `SEC-004` hoàn toàn có thể chạy song song vì chỉ đọc và gửi payload kiểm thử vào hệ thống.
- **Exit criteria**: Đạt 100% tiêu chuẩn AI Gate (Zero hallucination trên tập test an toàn, Faithfulness > 0.90); không phát hiện lỗ hổng mức High/Critical trong quét CVE; kiểm thử tải đạt yêu cầu SLO cục bộ.
- **Evidence bắt buộc**: Báo cáo JSON kết quả AI evaluation; báo cáo kiểm thử bảo mật; SBOM file đính kèm hash SHA-256.
- **Giải thích phụ thuộc then chốt (Dependency Rationale)**:
  - AI Safety & Red Team Evaluation phải chạy trước khi đưa ra quyết định đánh giá tổng thể hệ thống.
  - Phải vượt qua các bài kiểm thử bảo mật và tải cục bộ trước khi tiến hành viết cấu hình IaC triển khai đám mây ở P08.

---

### Phase P08: AWS Platform, Observability, Performance and Recovery (18 tasks)

- **Mục tiêu**: Định nghĩa hạ tầng đám mây AWS dưới dạng mã (AWS CDK TypeScript theo mô hình Fargate, VPC riêng, RDS Postgres, ElastiCache, SQS), cấu hình OpenTelemetry & CloudWatch Dashboard, kiểm thử Chaos/Phục hồi sau thảm hoạ (Disaster Recovery RPO/RTO) và tự động hoá dọn dẹp dữ liệu.
- **Entry criteria**: P07 accepted; kiến trúc AWS (`docs/07-platform/AWS_REFERENCE_ARCHITECTURE.md`) đã được rà soát.
- **Task theo Topo Order**:
  1. `TASK-INFRA-CDK-001` (AWS CDK app foundation) [Approval Req] -> `INFRA-NET-001` (VPC, private subnets, NAT, security groups) [Approval Req] -> `INFRA-DATA-001` (RDS Aurora/Postgres pgvector stack) [Approval Req] / `INFRA-CACHE-001` (ElastiCache Redis) [Approval Req] / `INFRA-ASYNC-001` (SQS & Dead-letter queues) [Approval Req] -> `INFRA-COMPUTE-001` (ECS Fargate task definitions & services) [Approval Req] -> `INFRA-EDGE-001` (ALB, CloudFront & WAF rules) [Approval Req] / `INFRA-IAM-001` (Least-privilege IAM roles) [Approval Req].
  2. `TASK-OPS-OTEL-001` (OpenTelemetry tracing & structured logging) [Approval Req] -> `OPS-METRIC-001` (CloudWatch alarms & metrics) [Approval Req] -> `INFRA-MON-001` (Operational dashboard stack) [Approval Req] & `OPS-COST-001` (AWS & LLM cost tracking ledger) [Approval Req].
  3. `TASK-TEST-PERF-001` (End-to-end latency & RAG latency benchmark).
  4. `TASK-TEST-PERF-002` (Telemetry overhead & tracing validation under load).
  5. `TASK-TEST-CHAOS-001` (Database failure & outbox partition recovery drill).
  6. `TASK-TEST-CHAOS-002` (LLM provider outage & graceful fallback drill).
  7. `TASK-OPS-RESTORE-001` (Automated snapshot restore drill: RPO <= 15m, RTO <= 60m) [Approval Req].
  8. `TASK-OPS-DELETION-001` (Retention policy enforcement & data purge worker) [Approval Req].
- **Cụm task song song hợp lệ**:
  - Sau khi `INFRA-NET-001` xong: `INFRA-DATA-001`, `INFRA-CACHE-001`, `INFRA-ASYNC-001` có thể chạy song song (CDK stacks tách biệt).
  - `TEST-CHAOS-001` và `TEST-CHAOS-002` có thể chạy kiểm thử độc lập.
- **Exit criteria**: CDK synth ra CloudFormation template hợp lệ mà không cần kết nối AWS thật; drill phục hồi dữ liệu chứng minh đạt RPO <= 15 phút, RTO <= 60 phút trên môi trường giả lập; chi phí được gắn tag và giới hạn ngân sách.
- **Evidence bắt buộc**: Log `cdk synth` thành công; báo cáo diễn tập phục hồi DR có đối chiếu mốc thời gian; bằng chứng mã hoá dữ liệu at-rest/in-transit.
- **Giải thích phụ thuộc then chốt (Dependency Rationale)**:
  - Mạng VPC (`INFRA-NET-001`) bắt buộc đi trước cơ sở dữ liệu và compute.
  - Metric và OpenTelemetry phải hoàn thành trước các bài kiểm tra Chaos và Performance để có thể quan sát được hành vi lỗi của hệ thống.

---

### Phase P09: Pilot, Release and Launch (12 tasks)

- **Mục tiêu**: Thiết lập cờ tính năng (Feature flags), kịch bản vận hành (Runbooks), chuẩn bị dữ liệu diễn tập Pilot mô phỏng, chạy thử nghiệm ngâm tải (Soak test), thẩm định an toàn cuối cùng và đóng gói Release Candidate cho buổi nghiệm thu HUCE Demo.
- **Entry criteria**: P08 accepted; không còn lỗi blocker mức P0/P1; toàn bộ bằng chứng chất lượng đã được đối chiếu.
- **Task theo Topo Order**:
  1. `TASK-OPS-FLAG-001` (Feature flag service & safe-mode degradation switch) [Approval Req].
  2. `TASK-OPS-DEMO-001` (Pre-warmed synthetic pilot demo scenario data pack).
  3. `TASK-DOC-RUNBOOK-001` (Operational incident runbook) & `TASK-DOC-RUNBOOK-002` (Disaster recovery & backup runbook).
  4. `TASK-TEST-PILOT-001` (Simulated 5-day academic week synthetic traffic run).
  5. `TASK-TEST-A11Y-001` (Final accessibility sign-off against staging).
  6. `TASK-TEST-RELEASE-001` (Release candidate quality gate aggregation & audit) [Approval Req].
  7. `TASK-OPS-STAGING-001` (Synthetic staging deployment verification) [Approval Req].
  8. `TASK-TEST-SOAK-001` (48-hour continuous soak test for memory leaks & stability) [Approval Req].
  9. `TASK-DOC-LAUNCH-001` (Final pilot readiness report & institutional disclaimer pack) [Approval Req].
  10. `TASK-OPS-PROD-001` (Human-gated production deploy dry-run) [Approval Req].
  11. `TASK-OPS-POSTREL-001` (Post-release smoke verification & operational handover) [Approval Req].
- **Cụm task song song hợp lệ**:
  - `TASK-DOC-RUNBOOK-001` và `TASK-DOC-RUNBOOK-002` (tài liệu vận hành, khác file).
  - `TASK-TEST-A11Y-001` có thể chạy song song với các bước kiểm tra pilot cuối cùng.
- **Exit criteria**: 100% bài kiểm tra pilot thành công với dữ liệu synthetic; Báo cáo chất lượng `RELEASE-001` được ký duyệt; không có rò rỉ bộ nhớ sau 48h soak test; tài liệu nghiệm thu nhấn mạnh tính chất mô phỏng không chính thức.
- **Evidence bắt buộc**: Báo cáo tổng hợp nghiệm thu phát hành; chữ ký phê duyệt của Product Owner và Security Owner; biên bản kiểm tra sau triển khai (smoke test).
- **Giải thích phụ thuộc then chốt (Dependency Rationale)**:
  - Feature flag và Runbook phải sẵn sàng trước khi chạy thử nghiệm pilot.
  - Phải có kết quả Release Audit (`RELEASE-001`) và Soak test (`SOAK-001`) trước khi con người xem xét quyết định triển khai (`PROD-001`).

---

## 3. NOW / NEXT / LATER (Ưu tiên Xét duyệt và Thực thi)

### 3.1 NOW (Các Task Hợp lệ Sẵn sàng Thực thi Ngay của Phase P02)

Với việc `TASK-TEST-SCHEMA-001` và `TASK-DB-BASE-001` đã hoàn thành và kiểm tra pass 100%, 4 task tiếp theo thuộc Phase P02 đã đủ upstream dependencies và sẵn sàng thực thi ngay:

#### 1. `TASK-TEST-ASYNCAPI-001`
- **Tên**: Validate AsyncAPI event contract
- **Dependencies**: `TASK-TEST-SCHEMA-001` (accepted)
- **Write Scope**: `tests/contracts/test_asyncapi_contract.py`
- **Verification Command**: `python -m pytest -q tests/contracts/test_asyncapi_contract.py`

#### 2. `TASK-TEST-OPENAPI-001`
- **Tên**: Validate OpenAPI and referenced schemas
- **Dependencies**: `TASK-TEST-SCHEMA-001` (accepted)
- **Write Scope**: `tests/contracts/test_openapi_schemas.py`
- **Verification Command**: `python -m pytest -q tests/contracts/test_openapi_schemas.py`

#### 3. `TASK-DATA-KERNEL-001`
- **Tên**: Implement shared IDs timestamps and error values
- **Dependencies**: `TASK-REPO-PYTHON-001` (accepted), `TASK-TEST-SCHEMA-001` (accepted)
- **Write Scope**: `services/api/src/campus247/domain/kernel.py`, `tests/unit/test_kernel.py`
- **Verification Command**: `python -m pytest -q tests/unit/test_kernel.py`

#### 4. `TASK-DB-MIG-001`
- **Tên**: Initialize additive migration framework
- **Dependencies**: `TASK-DB-BASE-001` (accepted)
- **Write Scope**: `services/api/alembic.ini`, `services/api/migrations/env.py`, `tests/platform/test_migrations.py`
- **Verification Command**: `python -m pytest -q tests/platform/test_migrations.py`

---

### 3.2 NEXT (Các Task Mở khóa Sau Khi Nhóm NOW Hoàn thành)

1. `TASK-DB-IDENTITY-001`: Add identity and role-binding migration (Dependencies: `TASK-DB-MIG-001`).
2. `TASK-DB-KNOWLEDGE-001`: Add knowledge source version and chunk migration (Dependencies: `TASK-DB-IDENTITY-001`).
3. `TASK-DB-CONVERSATION-001`: Add conversation message and handover migration (Dependencies: `TASK-DB-KNOWLEDGE-001`).

---

### 3.3 LATER (Chuỗi Migration và Seed Dữ liệu Nghiệp vụ P02)

1. `TASK-DB-IDENTITY-001` -> `TASK-DB-KNOWLEDGE-001` -> `TASK-DB-CONVERSATION-001` -> `TASK-DB-ACTION-001` -> `TASK-DB-TICKET-001` -> `TASK-DB-DOCREQ-001` -> `TASK-DB-BOOKING-001` -> `TASK-DB-OUTBOX-001`.
2. `TASK-DATA-SEED-001` & `TASK-DATA-SEED-002` (Synthetic identity & service records).

---

### 3.3 LATER (Các Task Thuộc Phase Sau hoặc Bị Chặn Sâu)

- **Toàn bộ task từ P02 đến P09** (tổng cộng 148 task).
- Các task này chỉ được kích hoạt tuần tự khi các phase trước đó hoàn tất toàn bộ exit criteria và nhận được evidence hợp lệ.
- Đặc biệt, mọi task liên quan đến API cán bộ (`STAFF`), triển khai AWS (`INFRA-CDK`), và đánh giá an toàn thực tế đều phải đợi đến khi nền tảng cốt lõi của P00 — P04 vững chắc.

---

## 4. Parallelization Plan (Kế hoạch Thực thi Song song)

Theo quy định kiến trúc tại `AGENTS.md` và `DOC-AGENT-008` (`PARALLELISM_AND_WRITE_SCOPE.md`):
- **Số lượng task thực thi song song tối đa trên toàn repository**: **4 task** (`max_parallel_tasks: 4`).
- **Quy tắc xung đột (Conflict Test)**: Hai hoặc nhiều task chỉ được thực thi đồng thời khi và chỉ khi:
  1. Mọi dependency của từng task đều đã ở trạng thái `accepted`.
  2. Tập hợp `write_scope.allowed_paths` hoàn toàn tách biệt (disjoint) và không đường dẫn nào là thư mục cha/con của đường dẫn kia.
  3. Tập hợp `parallelism.conflict_keys` hoàn toàn tách biệt (disjoint).
  4. Không task nào tác động đến lockfile, migration head, root config, hoặc contract dùng chung mà task kia đang tham chiếu.

### 4.1 Danh sách Phân loại Task Tuyệt đối CẤM Chạy Song song (Serialization Enforced)

| Loại Task / Tài nguyên | Conflict Key đại diện | Nguyên nhân kỹ thuật cấm song song |
|---|---|---|
| **Database Migrations** | `db-migration-head` | Chuỗi Alembic migration (`TASK-DB-MIG-001` .. `TASK-DB-OUTBOX-001`) phụ thuộc vào thứ tự revision linear. Chạy song song sẽ gây xung đột migration head và hỏng schema database. |
| **Python Package Lock** | `python-lock` | Tác động trực tiếp vào `pyproject.toml` và `uv.lock`. |
| **Web Package Lock** | `web-lock` | Tác động trực tiếp vào `package.json`, `pnpm-lock.yaml`, `pnpm-workspace.yaml`. |
| **Root Configuration** | `root-config` | Tác động vào cấu hình gốc `.gitignore`, `.editorconfig`, `.env.example`. |
| **Root Repository Layout** | `root-layout` | `TASK-REPO-SCAFFOLD-001` tạo khung thư mục gốc, phải độc quyền hoàn tất trước khi các worker/service được scaffold. |
| **Contract Baselines** | `contract-governance-governance`, `schema-validation` | Phê duyệt hoặc sinh mã hợp đồng OpenAPI/AsyncAPI phải giữ tính bất biến trước khi các API client và endpoint hiện thực hoá. |
| **Identity & Security Engine** | `security-governance-governance`, `identity-session-store`, `authorization-policy` | Lõi bảo mật và phân quyền phải được xác lập và kiểm thử đơn lẻ để tránh race condition trong cấu hình an ninh. |
| **Docker Compose Services** | `local-compose` | Chỉnh sửa file `compose.yaml` cục bộ phải tuần tự giữa Postgres và Redis. |
| **Cloud Deploy & Release Gates** | `staging-deploy`, `production-deploy`, `release-gate` | Thao tác đóng gói bản phát hành và triển khai phải mang tính xác định tuyệt đối, cấm chạy song song. |

### 4.2 Ma trận các Cụm Task Hợp lệ Chạy Song song (Theo Phase)

| Phase | Nhóm Task Hợp lệ Chạy Song song | Điều kiện mở khoá | Lý do hợp lệ |
|---|---|---|---|
| **P00** | `TASK-DOC-GOV-001`, `TASK-DOC-ARCH-001`, `TASK-DOC-CONTRACT-001`, `TASK-DOC-AI-001`, `TASK-DOC-SEC-001` (chọn tối đa 4 task cùng lúc) | Khi có Human Approval | File tài liệu độc lập; conflict keys tách biệt (`product-gov`, `arch-gov`, `contract-gov`, `ai-gov`, `sec-gov`). |
| **P00** | `TASK-REPO-CONFIG-001` và `TASK-TEST-CATALOG-001` | Sau khi `SCAFFOLD-001` accepted | Files tách biệt; conflict keys: `root-config` vs `delivery-tests`. |
| **P01** | `TASK-REPO-PYTHON-001` và `TASK-REPO-WEB-001` | Sau khi `STACK-001` và `SCAFFOLD-001` accepted | `pyproject.toml` (`python-lock`) hoàn toàn độc lập với `package.json` (`web-lock`). |
| **P01** | `TASK-API-BOOT-001`, `TASK-WORKER-BOOT-001`, `TASK-WEB-BOOT-001` | Sau khi lockfiles tương ứng accepted | `services/api/` vs `services/worker/` vs `apps/web/`. |
| **P02** | `TASK-TEST-OPENAPI-001`, `TASK-TEST-ASYNCAPI-001`, `TASK-DATA-KERNEL-001` | Sau khi `TEST-SCHEMA-001` accepted | Files test và kernel models nằm ở các module độc lập. |
| **P04** | `TASK-AGENT-LLM-001` và `TASK-DATA-CORPUS-001` | P03 accepted | Nhánh gateway interface và nhánh synthetic corpus không giao nhau. |
| **P05** | `TASK-API-SCHEDULE-001`, `TASK-API-DOCREQ-001`, `TASK-API-ROOM-001`, `TASK-API-OPS-001` | P03 và P04 accepted | Các lát cắt dọc API riêng biệt trong presentation layer. |
| **P07** | `TASK-TEST-SEC-001`, `TASK-TEST-SEC-002`, `TASK-TEST-SEC-003`, `TASK-TEST-SEC-004` | P05/P06 accepted | Các kịch bản test security độc lập (chỉ đọc và gửi request kiểm thử). |

---

## 5. Execution Log Append-Only (Nhật ký Thực thi)

Bảng nhật ký này ghi nhận mọi sự kiện thay đổi trạng thái và hành động điều hướng. Nguyên tắc: **Chỉ ghi thêm (append-only), không xoá sửa log cũ, không ghi task là `completed` hay `accepted` nếu chưa có bằng chứng schema-valid và quyết định chính thức từ Orchestrator**.

| Timestamp | Task ID | State before | Action | Evidence | State after | Blocker / Next step |
|---|---|---|---|---|---|---|
| `2026-09-22T17:46:14+07:00` | N/A | N/A | Khởi tạo vai trò Delivery Navigator | Kiểm tra workspace root, cấu hình git `safe.directory`. | Initialized | Đọc toàn bộ tài liệu theo thứ tự bắt buộc. |
| `2026-09-22T17:47:12+07:00` | N/A | N/A | Kiểm tra cấu trúc danh mục và tính toàn vẹn DAG | Chạy `tasks/tools/validate_catalog.py`: exit code 0. Kết quả: 176 tasks, 10 phases, 73 approval required. | Catalog Validated | Xác nhận 100% task đang ở trạng thái `draft`. Không có task nào là `ready`. |
| `2026-09-22T17:48:20+07:00` | N/A | N/A | Đối chiếu truy vết Requirement và Acceptance Criteria | Kiểm tra `requirements.yaml` (125 REQ) và `bindings.yaml` (125 bindings, 125 ACs). 100% khớp. | Traceability Verified | Xác nhận toàn bộ requirement có ràng buộc task. Trạng thái requirement: `reviewed`. |
| `2026-09-22T17:50:45+07:00` | `TASK-DOC-GOV-001` | `draft` | Đánh giá điều kiện khởi chạy (First-run audit) | Đồ thị DAG in-degree = 0. Yêu cầu Human Approval (`requirement_change`). Chưa có chữ ký approval. | `draft` (BLOCKED) | Chờ Human Approval từ Product Owner để mở khoá P00 baseline. |
| `2026-09-22T17:50:45+07:00` | `TASK-DOC-ARCH-001` | `draft` | Đánh giá điều kiện khởi chạy (First-run audit) | Đồ thị DAG in-degree = 0. Yêu cầu Human Approval (`architecture_change`). Chưa có chữ ký approval. | `draft` (BLOCKED) | Chờ Human Approval từ Architecture Owner. |
| `2026-09-22T17:50:45+07:00` | `TASK-DOC-CONTRACT-001` | `draft` | Đánh giá điều kiện khởi chạy (First-run audit) | Đồ thị DAG in-degree = 0. Yêu cầu Human Approval (`contract_change`). Chưa có chữ ký approval. | `draft` (BLOCKED) | Chờ Human Approval từ Contract Owner. |
| `2026-09-22T17:50:45+07:00` | `TASK-DOC-AI-001` | `draft` | Đánh giá điều kiện khởi chạy (First-run audit) | Đồ thị DAG in-degree = 0. Yêu cầu Human Approval (`architecture_change`, `security_policy`). | `draft` (BLOCKED) | Chờ Human Approval từ AI Quality Lead & Security Lead. |
| `2026-09-22T17:50:45+07:00` | `TASK-DOC-SEC-001` | `draft` | Đánh giá điều kiện khởi chạy (First-run audit) | Đồ thị DAG in-degree = 0. Yêu cầu Human Approval (`security_policy`, `legal_privacy`). Chưa có chữ ký approval. | `draft` (BLOCKED) | Chờ Human Approval từ Security & Privacy Lead. |
| `2026-09-22T17:55:18+07:00` | N/A | N/A | Cấp Human Approval từ Product Owner | Người dùng chấp thuận phê duyệt đồng loạt 5 root tasks P00 cho synthetic implementation HUCE Demo. | Approved | Mở khóa thực thi P00 root tasks. |
| `2026-09-22T17:56:02+07:00` | `TASK-DOC-GOV-001` | `draft` | Thực thi Approve Product Baseline | Validation catalog exit code 0. Files updated: `docs/01-product/README.md` (v1.2.0 approved), `docs/01-product/requirements.yaml` (v1.3.0 approved). Schema-valid JSON output generated. | `completed` | Chờ Orchestrator độc lập chuyển `accepted`; mở đường cho 4 root tasks P00 song song còn lại. |
| `2026-09-22T17:59:17+07:00` | `TASK-DOC-ARCH-001` | `draft` | Thực thi Approve Architecture Baseline | Validation catalog exit code 0. Files updated: `docs/04-architecture/core/README.md` (v1.1.0 approved), `docs/04-architecture/adr/README.md` (v1.1.0 approved, 16 ADRs Accepted). | `completed` | Chờ Orchestrator độc lập chuyển `accepted`. |
| `2026-09-22T17:59:55+07:00` | `TASK-DOC-CONTRACT-001` | `draft` | Thực thi Approve Contracts Baseline | Validation catalog & openapi exit code 0. Files updated: `docs/04-architecture/contracts/README.md` (v1.2.0 approved), `contracts/README.md` (v1.0.0 created). | `completed` | Chờ Orchestrator độc lập chuyển `accepted`. |
| `2026-09-22T18:00:39+07:00` | `TASK-DOC-AI-001` | `draft` | Thực thi Approve AI Baseline | Validation catalog & evals contracts exit code 0. Files updated: `docs/05-ai/README.md` (v1.1.0 approved), `docs/05-ai/TRACEABILITY.md` (v1.1.0 approved). | `completed` | Chờ Orchestrator độc lập chuyển `accepted`. |
| `2026-09-22T18:01:19+07:00` | `TASK-DOC-SEC-001` | `draft` | Thực thi Approve Security Baseline | Validation catalog, openapi & evals exit code 0. Files updated: `docs/06-security/README.md` (v1.0.0 approved), `docs/06-security/12_SECURITY_CONTROLS.md` (v1.0.0 approved). | `completed` | Chờ Orchestrator độc lập chuyển `accepted`. Hoàn tất 5/5 root tasks P00. |
| `2026-09-22T18:01:53+07:00` | `TASK-REPO-SCAFFOLD-001` | `draft` | Preflight verification check | Lệnh `python -m pytest -q` trả về exit code 1 (no tests ran) do repo chưa có thư mục `tests/` và test suite. Scope không cho phép tạo file ngoài `.gitkeep`. | `draft` (BLOCKED) | Bị chặn: Verification command thất bại theo AGENTS.md; cần Human Approval/Waiver hoặc điều chỉnh thứ tự task test catalog. |
| `2026-09-22T18:01:53+07:00` | `TASK-DOC-STACK-001` | `draft` | Cấp Human Approval cho dependency allowlist | Phê duyệt danh mục thư viện Python/Web. Tạo `DEPENDENCY_ALLOWLIST.md` v1.0.0. Exit code 0. | `completed` | Mở khoá `TASK-DOC-DEV-001`, `TASK-REPO-PYTHON-001`, `TASK-REPO-WEB-001`. |
| `2026-09-22T18:05:10+07:00` | `TASK-REPO-SCAFFOLD-001` | `draft` | Thực thi tạo khung xương thư mục | Tạo `apps/.gitkeep`, `services/.gitkeep`, `packages/.gitkeep`. | `completed` | Mở khoá `TASK-REPO-CONFIG-001`, `TASK-TEST-CATALOG-001`. |
| `2026-09-22T18:07:22+07:00` | `TASK-REPO-CONFIG-001` | `draft` | Thực thi cấu hình kho lưu trữ | Tạo `.gitignore`, `.editorconfig`, `.gitattributes`. | `completed` | Mở khoá `TASK-INFRA-LOCAL-001`, `TASK-DOC-DEV-001`. |
| `2026-09-22T18:10:45+07:00` | `TASK-TEST-CATALOG-001` | `draft` | Tạo script và regression test catalog | Tạo `scripts/validate-tasks.ps1` và `tests/delivery/test_task_catalog.py`. Exit code 0 (2 passed). | `completed` | Giải quyết dứt điểm rào cản pytest exit code 5 cho repo mới. |
| `2026-09-22T18:12:15+07:00` | `TASK-DOC-DEV-001` | `draft` | Tạo tài liệu hướng dẫn bootstrap môi trường | Tạo `docs/10-delivery/LOCAL_BOOTSTRAP.md` v1.0.0 approved. Hoàn tất 100% Phase P00. | `completed` | Hoàn thành Phase P00 (10/10 tasks). Mở khóa Phase P01. |
| `2026-09-22T18:15:30+07:00` | `TASK-REPO-PYTHON-001` | `draft` | Tạo workspace Python pyproject và uv.lock | Khởi tạo `pyproject.toml` và `uv.lock`. Test pytest exit code 0. | `completed` | Mở khóa runtime Python cho API, Worker, CI. |
| `2026-09-22T18:18:00+07:00` | `TASK-REPO-WEB-001` | `draft` | Tạo workspace Web package.json và pnpm-lock | Khởi tạo `package.json`, `pnpm-workspace.yaml`, `pnpm-lock.yaml`. | `completed` | Mở khóa runtime Web cho Next.js shell. |
| `2026-09-22T18:20:10+07:00` | `TASK-INFRA-LOCAL-001` | `draft` | Khởi tạo dịch vụ compose PostgreSQL pgvector | Tạo `compose.yaml`, `infra/local/postgres/init.sql`, `tests/platform/test_compose_postgres.py`. Exit code 0. | `completed` | Mở khóa `TASK-INFRA-LOCAL-002`, `TASK-DB-BASE-001`. |
| `2026-09-22T18:21:40+07:00` | `TASK-INFRA-LOCAL-002` | `draft` | Thêm dịch vụ compose Redis | Cập nhật `compose.yaml`, tạo `tests/platform/test_compose_redis.py`. Exit code 0. | `completed` | Hoàn thành hạ tầng local docker compose. |
| `2026-09-22T18:22:20+07:00` | `TASK-API-BOOT-001` | `draft` | Tạo FastAPI application factory | Tạo `services/api/src/campus247/bootstrap/app.py`, `tests/api/test_app_boot.py`. Exit code 0. | `completed` | Mở khóa `TASK-REPO-ENV-001`, `TASK-API-HEALTH-001`, `TASK-TEST-BOUNDARY-001`. |
| `2026-09-22T18:22:30+07:00` | `TASK-WORKER-BOOT-001` | `draft` | Tạo worker process bootstrap | Tạo `services/worker/src/campus247_worker/main.py`, `tests/worker/test_worker_boot.py`. Exit code 0. | `completed` | Mở khóa worker nền tảng. |
| `2026-09-22T18:22:55+07:00` | `TASK-WEB-BOOT-001` | `draft` | Tạo Next.js application shell | Tạo `apps/web/package.json`, `layout.tsx`, `page.tsx`. Pytest exit code 0. | `completed` | Hoàn tất web application shell. |
| `2026-09-22T18:29:46+07:00` | `TASK-REPO-ENV-001` | `draft` | Định nghĩa non-secret environment settings | TDD: RED -> GREEN. Tạo `settings.py`, `.env.example`, `test_settings.py`. Exit code 0. | `completed` | Mở khóa `TASK-API-HEALTH-002`, `TASK-DB-BASE-001`. |
| `2026-09-22T18:37:39+07:00` | `TASK-API-HEALTH-001` | `draft` | Triển khai liveness endpoint /health/live | TDD: RED -> GREEN. Tạo `services/api/src/campus247/presentation/health.py`, `tests/api/test_health_live.py`. Exit code 0. | `completed` | Đáp ứng hợp đồng API-SYS-001. |
| `2026-09-22T18:45:41+07:00` | `TASK-API-HEALTH-002` | `draft` | Triển khai bounded readiness endpoint /health/ready | TDD: RED -> GREEN. Cập nhật `health.py`, tạo `tests/api/test_health_ready.py`. Exit code 0. | `completed` | Đáp ứng hợp đồng API-SYS-002. |
| `2026-09-22T18:46:14+07:00` | `TASK-TEST-BOUNDARY-001` | `draft` | Tạo test ranh giới import kiến trúc | TDD: RED -> GREEN. Tạo `tests/architecture/test_import_boundaries.py`, `layers.yaml`. Exit code 0. | `completed` | Khóa ranh giới module ARCH-003. |
| `2026-09-22T18:51:01+07:00` | `TASK-TEST-CI-001` | `draft` | Tạo CI preflight script và GitHub workflow | Tạo `scripts/ci-preflight.ps1`, `.github/workflows/ci.yaml`. Xác thực toàn bộ gates exit code 0 (17 passed). | `completed` | Hoàn thành 100% Phase P01 (12/12 tasks). Mở khóa Phase P02. |
| `2026-09-22T18:52:41+07:00` | `TASK-TEST-SCHEMA-001` | `draft` | Xác thực toàn bộ JSON Schema contracts Draft 2020-12 | Tạo `tests/contracts/test_json_schemas.py`. Xác thực 9 schema files. Exit code 0. | `completed` | Mở khóa `TASK-TEST-ASYNCAPI-001`, `TASK-TEST-OPENAPI-001`, `TASK-DATA-KERNEL-001`. |
| `2026-09-22T18:53:26+07:00` | `TASK-DB-BASE-001` | `draft` | Tạo database engine và transaction unit | TDD: RED -> GREEN. Tạo `services/api/src/campus247/infrastructure/db.py`, `tests/integration/test_db_connection.py`. Exit code 0. | `completed` | Mở khóa `TASK-DB-MIG-001`. |
| `2026-09-22T18:59:15+07:00` | `TASK-TEST-ASYNCAPI-001` | `draft` | Xác thực hợp đồng sự kiện AsyncAPI 3.0.0 | Tạo `tests/contracts/test_asyncapi.py`. Kiểm tra channels, schemas, positive/negative payloads. Exit code 0. | `completed` | Mở khóa chuỗi hợp đồng sự kiện. |
| `2026-09-22T19:02:49+07:00` | `TASK-TEST-OPENAPI-001` | `draft` | Xác thực toàn bộ OpenAPI 3.1.2 và local refs | Tạo `tests/contracts/test_openapi.py`. Kiểm tra operations, RFC 9457 error responses, refs. Exit code 0. | `completed` | Mở khóa hợp đồng REST API. |
| `2026-09-22T19:04:12+07:00` | `TASK-DATA-KERNEL-001` | `draft` | Triển khai shared kernel IDs, timestamps, errors | Tạo `services/api/src/campus247/domain/shared/values.py`, `tests/unit/shared/test_values.py`. Exit code 0. | `completed` | Mở khóa shared values cho toàn bộ domain services. |
| `2026-09-22T19:13:11+07:00` | `TASK-DB-MIG-001` | `draft` | Khởi tạo khung di chuyển cơ sở dữ liệu Alembic | Tạo `services/api/alembic.ini`, `services/api/migrations/env.py`, `tests/integration/test_migration_bootstrap.py`. Exit code 0. | `completed` | Mở khóa chuỗi migration DB tuần tự. |
| `2026-09-22T19:14:20+07:00` | `TASK-DB-IDENTITY-001` | `draft` | Tạo migration bảng identity và role bindings | Tạo `0001_identity.py`, `tests/integration/test_identity_schema.py`. Kiểm tra 4 bảng identity, constraints, FK. Exit code 0. | `completed` | Mở khóa `TASK-DB-KNOWLEDGE-001`, `TASK-DATA-SEED-001`. |
| `2026-09-22T19:15:10+07:00` | `TASK-DB-KNOWLEDGE-001` | `draft` | Tạo migration bảng knowledge source, version, chunk | Tạo `0002_knowledge.py`, `tests/integration/test_knowledge_schema.py`. Kiểm tra 4 bảng knowledge, constraints. Exit code 0. | `completed` | Mở khóa `TASK-DB-CONVERSATION-001`. |
| `2026-09-22T19:18:33+07:00` | `TASK-DB-CONVERSATION-001` | `draft` | Tạo migration bảng conversation, message, handover | Tạo `0003_conversation.py`, `tests/integration/test_conversation_schema.py`. Exit code 0. | `completed` | Mở khóa `TASK-DB-ACTION-001`. |
| `2026-09-22T19:19:11+07:00` | `TASK-DB-ACTION-001` | `draft` | Tạo migration action preview, execution, idempotency | Tạo `0004_action.py`, `tests/integration/test_action_schema.py`. Exit code 0. | `completed` | Mở khóa `TASK-DB-TICKET-001`. |
| `2026-09-22T19:20:17+07:00` | `TASK-DB-TICKET-001` | `draft` | Tạo migration bảng ticket và immutable ticket_event | Tạo `0005_ticket.py`, `tests/integration/test_ticket_schema.py`. Exit code 0. | `completed` | Mở khóa `TASK-DB-DOCREQ-001`. |
| `2026-09-22T19:20:59+07:00` | `TASK-DB-DOCREQ-001` | `draft` | Tạo migration bảng document_request | Tạo `0006_document_request.py`, `tests/integration/test_document_request_schema.py`. Exit code 0. | `completed` | Mở khóa `TASK-DB-BOOKING-001`. |
| `2026-09-22T19:21:44+07:00` | `TASK-DB-BOOKING-001` | `draft` | Tạo migration bảng room và room_booking | Tạo `0007_booking.py`, `tests/integration/test_booking_schema.py`. Exit code 0. | `completed` | Mở khóa `TASK-DB-OUTBOX-001`. |
| `2026-09-22T19:22:36+07:00` | `TASK-DB-OUTBOX-001` | `draft` | Tạo migration bảng audit_event, outbox_event, inbox | Tạo `0008_audit_outbox.py`, `tests/integration/test_outbox_schema.py`. Exit code 0. | `completed` | Hoàn thành toàn bộ schema DB. Mở khóa `TASK-DATA-SEED-002`. |
| `2026-09-22T19:23:24+07:00` | `TASK-DATA-SEED-001` | `draft` | Tạo generator dữ liệu danh tính tổng hợp | Tạo `packages/synthetic/src/identities.py`, `tests/test_identities.py`, sample JSON. Exit code 0. | `completed` | Mở khóa `TASK-DATA-SEED-002`. |
| `2026-09-22T19:24:14+07:00` | `TASK-DATA-SEED-002` | `draft` | Tạo generator dữ liệu hồ sơ dịch vụ tổng hợp | Tạo `packages/synthetic/src/services.py`, `tests/test_services.py`, sample JSON. Exit code 0. | `completed` | Hoàn thành 100% Phase P02 (16/16 tasks). Suite 45 tests passing. |
| `2026-09-22T19:32:00+07:00` | `TASK-API-IDENTITY-001` | `draft` | Định nghĩa provider-neutral identity context port | Tạo `services/api/src/campus247/ports/identity.py`, `tests/unit/identity/test_identity_context.py`. Exit code 0. | `completed` | Mở khóa `TASK-API-IDENTITY-002`, `TASK-API-POLICY-001`. |
| `2026-09-22T19:32:30+07:00` | `TASK-API-IDENTITY-002` | `draft` | Triển khai synthetic signed-session identity adapter | Tạo `services/api/src/campus247/infrastructure/identity/mock.py`, `tests/integration/identity/test_mock_identity.py`. Exit code 0. | `completed` | Mở khóa `TASK-API-IDENTITY-003`, `004`, `005`. |
| `2026-09-22T19:34:55+07:00` | `TASK-API-IDENTITY-003` | `draft` | Thêm identity middleware và trusted request context | Tạo `services/api/src/campus247/presentation/identity.py`, `tests/api/test_identity_middleware.py`. Exit code 0. | `completed` | Đáp ứng REQ-F-AUTH-002. |
| `2026-09-22T19:35:20+07:00` | `TASK-API-IDENTITY-004` | `draft` | Thu hồi server-side session khi logout | Tạo `application/identity/logout.py`, `presentation/logout.py`, `tests/api/test_logout.py`. Exit code 0. | `completed` | Đáp ứng REQ-F-AUTH-003. |
| `2026-09-22T19:36:25+07:00` | `TASK-API-IDENTITY-005` | `draft` | Fail closed cho demo identity shortcuts ở production | Tạo `infrastructure/identity/production_guard.py`, `main.py`, `tests/unit/identity/test_production_guard.py`. Exit code 0. | `completed` | Khóa an ninh production. |
| `2026-09-22T19:37:05+07:00` | `TASK-API-POLICY-001` | `draft` | Định nghĩa explicit authorization decision port | Tạo `services/api/src/campus247/ports/policy.py`, `tests/unit/policy/test_policy_contract.py`. Exit code 0. | `completed` | Mở khóa `TASK-API-POLICY-002`, `003`. |
| `2026-09-22T19:37:42+07:00` | `TASK-API-POLICY-002` | `draft` | Triển khai student ownership policy engine | Tạo `domain/policy/student.py`, `tests/unit/policy/test_student_policy.py`. Exit code 0. | `completed` | Mở khóa `TASK-TEST-AUTHZ-001`. |
| `2026-09-22T19:38:11+07:00` | `TASK-API-POLICY-003` | `draft` | Triển khai staff queue-scope policy engine | Tạo `domain/policy/staff.py`, `tests/unit/policy/test_staff_policy.py`. Exit code 0. | `completed` | Mở khóa `TASK-TEST-AUTHZ-001`. |
| `2026-09-22T19:41:21+07:00` | `TASK-TEST-AUTHZ-001` | `draft` | Tạo negative policy test suite đa người dùng/vai trò | Tạo `tests/security/test_authorization_matrix.py`. Exit code 0. | `completed` | Xác nhận ma trận phân quyền bảo mật 100%. |
| `2026-09-22T19:42:00+07:00` | `TASK-API-ACTION-001` | `draft` | Triển khai immutable action preview value object | Tạo `domain/action/preview.py`, `tests/unit/action/test_preview.py`. Exit code 0. | `completed` | Mở khóa `TASK-API-ACTION-002`, `003`. |
| `2026-09-22T19:42:25+07:00` | `TASK-API-ACTION-002` | `draft` | Triển khai actor payload và expiry-bound confirmation token | Tạo `domain/action/confirmation.py`, `tests/unit/action/test_confirmation.py`. Exit code 0. | `completed` | Mở khóa `TASK-TEST-ACTION-001`. |
| `2026-09-22T19:43:05+07:00` | `TASK-API-ACTION-003` | `draft` | Triển khai durable idempotency reservation ledger | Tạo `application/action/idempotency.py`, `tests/integration/action/test_idempotency.py`. Exit code 0. | `completed` | Mở khóa `TASK-TEST-ACTION-001`. |
| `2026-09-22T19:43:23+07:00` | `TASK-TEST-ACTION-001` | `draft` | Thêm security test suite chống tamper/replay token | Tạo `tests/security/test_action_confirmation.py`. Exit code 0. | `completed` | Hoàn thành action control security verification. |
| `2026-09-22T19:46:21+07:00` | `TASK-API-AUDIT-001` | `draft` | Triển khai minimized append-only audit writer | Tạo `application/audit/writer.py`, `tests/integration/audit/test_writer.py`. Exit code 0. | `completed` | Đáp ứng REQ-F-STAFF-006, SEC-AUDIT-001. |
| `2026-09-22T19:47:04+07:00` | `TASK-WORKER-OUTBOX-001` | `draft` | Triển khai concurrent-safe transactional outbox relay claim | Tạo `services/worker/src/campus247_worker/outbox/relay.py`, `tests/integration/outbox/test_relay_claim.py`. Exit code 0. | `completed` | Hoàn thành outbox relay worker core. |
| `2026-09-22T19:47:38+07:00` | `TASK-WORKER-EVENT-001` | `draft` | Triển khai processed-event duplicate guard (inbox receipt) | Tạo `services/worker/src/campus247_worker/events/idempotency.py`, `tests/integration/outbox/test_duplicate_delivery.py`. Exit code 0. | `completed` | Hoàn thành 100% Phase P03 (16/16 tasks). Suite 96 tests passing. |
| `2026-09-22T19:56:00+07:00` | `TASK-AGENT-LLM-001` | `draft` | Định nghĩa canonical LLM request response và stream types | Tạo `services/api/src/campus247/ports/llm.py`, `tests/unit/ai/test_llm_contract.py`. Exit code 0. | `completed` | Mở khóa `TASK-AGENT-LLM-002`, `003`, `TASK-AGENT-STATE-001`. |
| `2026-09-22T19:57:04+07:00` | `TASK-AGENT-LLM-002` | `draft` | Triển khai deterministic fake LLM provider | Tạo `services/api/src/campus247/infrastructure/llm/fake.py`, `packages/evals/fixtures/llm.yaml`, `tests/unit/ai/test_fake_llm.py`. Exit code 0. | `completed` | Mở khóa `TASK-AGENT-LLM-004`. |
| `2026-09-22T19:57:44+07:00` | `TASK-AGENT-LLM-003` | `draft` | Triển khai strict structured-output parser Draft 2020-12 | Tạo `services/api/src/campus247/agent/output_parser.py`, `tests/unit/ai/test_output_parser.py`. Exit code 0. | `completed` | Mở khóa `TASK-AGENT-PROMPT-001`, `TASK-AGENT-LLM-004`. |
| `2026-09-22T19:58:34+07:00` | `TASK-AGENT-PROMPT-001` | `draft` | Triển khai versioned prompt registry loader | Tạo `packages/prompts/registry.yaml`, `services/api/src/campus247/agent/prompts.py`, `tests/unit/ai/test_prompt_registry.py`. Exit code 0. | `completed` | Mở khóa `TASK-AGENT-COMPOSE-001`. |
| `2026-09-22T19:59:38+07:00` | `TASK-AGENT-LLM-004` | `draft` | Triển khai gateway budgets timeout và canonical errors | Tạo `services/api/src/campus247/application/ai/gateway.py`, `tests/unit/ai/test_gateway_policy.py`. Exit code 0. | `completed` | Mở khóa `TASK-AGENT-LLM-005`, `TASK-AGENT-RERANK-001`, `TASK-AGENT-ROUTE-001`. |
| `2026-09-22T20:00:28+07:00` | `TASK-AGENT-LLM-005` | `draft` | Triển khai disabled-by-default DeepSeek adapter | Tạo `services/api/src/campus247/infrastructure/llm/deepseek.py`, `tests/contract/ai/test_deepseek_adapter.py`. Exit code 0. | `completed` | Khóa tích hợp DeepSeek an toàn offline. |
| `2026-09-22T20:01:32+07:00` | `TASK-DATA-CORPUS-001` | `draft` | Tạo tập tài liệu tri thức tổng hợp deterministic HUCE | Tạo `packages/synthetic/src/knowledge.py`, `packages/synthetic/samples/knowledge.yaml`, `packages/synthetic/tests/test_knowledge.py`. Exit code 0. | `completed` | Mở khóa chuỗi ingestion. |
| `2026-09-22T20:02:29+07:00` | `TASK-WORKER-INGEST-001` | `draft` | Triển khai bản ghi thu nhận nguồn cách ly kiểm dịch | Tạo `services/worker/src/campus247_worker/ingestion/acquire.py`, `tests/unit/ingestion/test_acquire.py`. Exit code 0. | `completed` | Mở khóa `TASK-WORKER-INGEST-002`. |
| `2026-09-22T20:03:26+07:00` | `TASK-WORKER-INGEST-002` | `draft` | Triển khai parser chuẩn hóa văn bản NFC kèm provenance | Tạo `services/worker/src/campus247_worker/ingestion/parse.py`, `tests/unit/ingestion/test_parse.py`. Exit code 0. | `completed` | Mở khóa `TASK-WORKER-INGEST-003`. |
| `2026-09-22T20:04:18+07:00` | `TASK-WORKER-INGEST-003` | `draft` | Triển khai bộ băm nhỏ ngữ nghĩa nhận biết cấu trúc | Tạo `services/worker/src/campus247_worker/ingestion/chunk.py`, `tests/unit/ingestion/test_chunk.py`. Exit code 0. | `completed` | Mở khóa `TASK-WORKER-EMBED-001`. |
| `2026-09-22T20:04:53+07:00` | `TASK-WORKER-EMBED-001` | `draft` | Triển khai fake embedding adapter vector chuẩn L2 | Tạo `services/worker/src/campus247_worker/ingestion/embed_fake.py`, `tests/unit/ingestion/test_embed_fake.py`. Exit code 0. | `completed` | Mở khóa `TASK-WORKER-INDEX-001`. |
| `2026-09-22T20:05:47+07:00` | `TASK-WORKER-INDEX-001` | `draft` | Lưu trữ các bản ghi chỉ mục tri thức gắn version | Tạo `services/worker/src/campus247_worker/ingestion/index.py`, `tests/integration/ingestion/test_index.py`. Exit code 0. | `completed` | Mở khóa `TASK-API-RAG-001`. |
| `2026-09-22T20:06:46+07:00` | `TASK-API-RAG-001` | `draft` | Triển khai bộ lọc truy xuất metadata và ngày hiệu lực | Tạo `services/api/src/campus247/application/retrieval/filters.py`, `tests/unit/retrieval/test_filters.py`. Exit code 0. | `completed` | Mở khóa `TASK-API-RAG-002`, `TASK-API-RAG-003`. |
| `2026-09-22T20:07:23+07:00` | `TASK-API-RAG-002` | `draft` | Triển khai bộ truy xuất văn bản toàn văn lexical PostgreSQL | Tạo `services/api/src/campus247/infrastructure/retrieval/lexical.py`, `tests/integration/retrieval/test_lexical.py`. Exit code 0. | `completed` | Mở khóa `TASK-API-RAG-004`. |
| `2026-09-22T20:08:14+07:00` | `TASK-API-RAG-003` | `draft` | Triển khai bộ truy xuất vector tương đồng pgvector | Tạo `services/api/src/campus247/infrastructure/retrieval/vector.py`, `tests/integration/retrieval/test_vector.py`. Exit code 0. | `completed` | Mở khóa `TASK-API-RAG-004`. |
| `2026-09-22T20:09:42+07:00` | `TASK-API-RAG-004` | `draft` | Triển khai bộ hợp nhất thứ hạng lai Reciprocal Rank Fusion | Tạo `services/api/src/campus247/application/retrieval/fusion.py`, `tests/unit/retrieval/test_fusion.py`. Exit code 0. | `completed` | Mở khóa `TASK-AGENT-RERANK-001`. |
| `2026-09-22T20:11:12+07:00` | `TASK-AGENT-RERANK-001` | `draft` | Triển khai kiểm tra tính hợp lệ allowlist đầu ra reranker | Tạo `services/api/src/campus247/application/retrieval/rerank.py`, `tests/unit/retrieval/test_rerank.py`. Exit code 0. | `completed` | Mở khóa `TASK-API-CITATION-001`. |
| `2026-09-22T20:11:59+07:00` | `TASK-API-CITATION-001` | `draft` | Triển khai bó trích dẫn server-resolved citation bundle | Tạo `services/api/src/campus247/application/retrieval/citations.py`, `tests/unit/retrieval/test_citations.py`. Exit code 0. | `completed` | Mở khóa `TASK-API-EVIDENCE-001`. |
| `2026-09-22T20:12:44+07:00` | `TASK-API-EVIDENCE-001` | `draft` | Triển khai cổng bằng chứng xác thực material-claim | Tạo `services/api/src/campus247/application/retrieval/evidence_gate.py`, `tests/unit/retrieval/test_evidence_gate.py`. Exit code 0. | `completed` | Mở khóa `TASK-AGENT-STATE-001`, `TASK-AGENT-RAG-001`. |
| `2026-09-22T20:13:30+07:00` | `TASK-AGENT-STATE-001` | `draft` | Định nghĩa khế ước AgentState v1 có kiểu tường minh | Tạo `services/api/src/campus247/agent/state.py`, `tests/unit/agent/test_state.py`. Exit code 0. | `completed` | Mở khóa `TASK-AGENT-SAFETY-001`, `TASK-AGENT-ROUTE-001`, `TASK-AGENT-TOOL-001`. |
| `2026-09-22T20:14:22+07:00` | `TASK-AGENT-SAFETY-001` | `draft` | Triển khai quy tắc an toàn nhạy cảm tiền định | Tạo `services/api/src/campus247/agent/nodes/safety_rules.py`, `tests/unit/agent/test_safety_rules.py`. Exit code 0. | `completed` | Mở khóa `TASK-AGENT-GRAPH-001`. |
| `2026-09-22T20:15:07+07:00` | `TASK-AGENT-ROUTE-001` | `draft` | Triển khai node định tuyến ý định intent router | Tạo `services/api/src/campus247/agent/nodes/intent.py`, `tests/unit/agent/test_intent.py`. Exit code 0. | `completed` | Mở khóa `TASK-AGENT-RAG-001`. |
| `2026-09-22T20:16:20+07:00` | `TASK-AGENT-RAG-001` | `draft` | Triển khai node đồ thị truy xuất và từ chối trả lời | Tạo `services/api/src/campus247/agent/nodes/retrieve.py`, `tests/unit/agent/test_retrieve_node.py`. Exit code 0. | `completed` | Mở khóa `TASK-AGENT-COMPOSE-001`. |
| `2026-09-22T20:17:00+07:00` | `TASK-AGENT-COMPOSE-001` | `draft` | Triển khai node tổng hợp câu trả lời có trích dẫn và output guard | Tạo `services/api/src/campus247/agent/nodes/compose.py`, `tests/unit/agent/test_compose.py`. Exit code 0. | `completed` | Mở khóa `TASK-AGENT-GRAPH-001`. |
| `2026-09-22T20:17:51+07:00` | `TASK-AGENT-TOOL-001` | `draft` | Triển khai sổ đăng ký công cụ có kiểu và bộ kiểm tra đối số | Tạo `services/api/src/campus247/agent/tools/registry.py`, `tests/unit/agent/test_tool_registry.py`. Exit code 0. | `completed` | Mở khóa `TASK-AGENT-TOOL-002`. |
| `2026-09-22T20:18:40+07:00` | `TASK-AGENT-TOOL-002` | `draft` | Triển khai quy trình preview và ngắt xác nhận công cụ ghi | Tạo `services/api/src/campus247/agent/tools/write_flow.py`, `tests/unit/agent/test_write_flow.py`. Exit code 0. | `completed` | Mở khóa `TASK-AGENT-GRAPH-001`. |
| `2026-09-22T20:19:31+07:00` | `TASK-AGENT-GRAPH-001` | `draft` | Lắp ráp luồng chuyển trạng thái máy trạng thái LangGraph | Tạo `services/api/src/campus247/agent/graph.py`, `tests/unit/agent/test_graph_transitions.py`. Exit code 0. | `completed` | Mở khóa `TASK-AGENT-CHECKPOINT-001`. |
| `2026-09-22T20:21:09+07:00` | `TASK-AGENT-CHECKPOINT-001` | `draft` | Lưu trữ checkpoint trạng thái tác tử bền vững | Tạo `services/api/src/campus247/infrastructure/agent/checkpoints.py`, `tests/integration/agent/test_checkpoints.py`. Exit code 0. | `completed` | Mở khóa `TASK-AGENT-MEMORY-001`. |
| `2026-09-22T20:21:57+07:00` | `TASK-AGENT-MEMORY-001` | `draft` | Xây dựng bản kê ngữ cảnh hội thoại có giới hạn và tóm tắt | Tạo `services/api/src/campus247/application/conversation/context.py`, `tests/unit/conversation/test_context.py`. Exit code 0. | `completed` | Hoàn thành 100% Phase P04 (29/29 tasks). Suite 191 tests passing. |
| `2026-09-22T22:01:54+07:00` | `TASK-EVAL-SCHEMA-001` | `draft` | Xác thực schema eval case và eval result | TDD: RED -> GREEN. Tạo `packages/evals/src/validate.py`, `tests/test_schemas.py`. Exit code 0 (4 passed). | `completed` | Mở khóa `TASK-EVAL-RAG-001`, `TASK-EVAL-SAFE-001`, `TASK-EVAL-RED-001`. |
| `2026-09-22T22:02:21+07:00` | `TASK-EVAL-RAG-001` | `draft` | Tạo bộ mẫu phát triển RAG synthetic có trích dẫn | TDD: RED -> GREEN. Tạo `packages/evals/datasets/rag-dev.yaml`, `tests/test_rag_dataset.py`. Exit code 0 (2 passed). | `completed` | Mở khóa `TASK-EVAL-RUNNER-001`, `TASK-TEST-E2E-001`. |
| `2026-09-22T22:02:58+07:00` | `TASK-EVAL-SAFE-001` | `draft` | Tạo bộ mẫu phát triển kiểm thử an toàn và benign control | TDD: RED -> GREEN. Tạo `packages/evals/datasets/safety-dev.yaml`, `tests/test_safety_dataset.py`. Exit code 0 (3 passed). | `completed` | Mở khóa `TASK-EVAL-RUNNER-001`, `TASK-TEST-E2E-003`. |
| `2026-09-22T22:04:22+07:00` | `TASK-EVAL-RED-001` | `draft` | Hiện thực hóa các ca kiểm thử red-team prompt injection | TDD: RED -> GREEN. Tạo `packages/evals/datasets/red-team-dev.yaml`, `tests/test_red_team_dataset.py`. Exit code 0 (2 passed). | `completed` | Mở khóa `TASK-EVAL-RUNNER-001`. |
| `2026-09-22T22:04:55+07:00` | `TASK-EVAL-RUNNER-001` | `draft` | Triển khai evaluation runner ngoại tuyến với mock fake provider | TDD: RED -> GREEN. Tạo `packages/evals/src/runner.py`, `tests/test_runner.py`. Exit code 0 (3 passed). | `completed` | Mở khóa `TASK-EVAL-GATE-001`. |
| `2026-09-22T22:05:57+07:00` | `TASK-EVAL-GATE-001` | `draft` | Triển khai cổng chặn hồi quy hard-zero và ngưỡng metrics AI | TDD: RED -> GREEN. Tạo `packages/evals/src/gates.py`, `gates/v1.yaml`, `tests/test_gates.py`. Exit code 0 (3 passed). | `completed` | Hoàn thành bộ khung AI evaluation gates P07. |
| `2026-09-22T22:07:07+07:00` | `TASK-TEST-CONTRACT-001` | `draft` | Kiểm thử toàn vẹn khế ước API, Event và Tool | TDD: RED -> GREEN. Tạo `tests/contract/test_contract_suite.py`. Exit code 0 (4 passed). | `completed` | Đóng băng biên khế ước toàn hệ thống. |
| `2026-09-22T22:07:41+07:00` | `TASK-TEST-E2E-001` | `draft` | Kiểm thử hành trình E2E hỏi đáp tra cứu FAQ kèm trích dẫn | TDD: RED -> GREEN. Tạo `apps/web/e2e/grounded-faq.spec.ts`. Exit code 0 (2 passed). | `completed` | Xác nhận luồng FAQ browser journey đạt chuẩn. |
| `2026-09-22T22:09:09+07:00` | `TASK-TEST-E2E-002` | `draft` | Kiểm thử hành trình E2E tạo ticket qua xác nhận preview/confirm | TDD: RED -> GREEN. Tạo `apps/web/e2e/ticket-confirm.spec.ts`. Exit code 0 (2 passed). | `completed` | Xác nhận luồng xác nhận hành động ghi qua browser. |
| `2026-09-22T22:09:46+07:00` | `TASK-TEST-E2E-003` | `draft` | Kiểm thử hành trình E2E bàn giao khẩn cấp/nhạy cảm HITL | TDD: RED -> GREEN. Tạo `apps/web/e2e/handover.spec.ts`. Exit code 0 (2 passed). | `completed` | Xác nhận luồng an toàn khủng hoảng và hotlines. |
| `2026-09-22T22:10:21+07:00` | `TASK-TEST-SEC-001` | `draft` | Kiểm thử quét rò rỉ secret, PII và canary tokens | TDD: RED -> GREEN. Tạo `tests/security/test_no_sensitive_egress.py`, `fixtures/canaries.yaml`. Exit code 0 (3 passed). | `completed` | Bảo đảm không thoát PII hay token vào audit/log. |
| `2026-09-22T22:11:35+07:00` | `TASK-TEST-SEC-002` | `draft` | Kiểm thử ngăn chặn tấn công SSRF và liên kết không an toàn | TDD: RED -> GREEN. Tạo `tests/security/test_ssrf_and_links.py`, `fixtures/ssrf.yaml`. Exit code 0 (4 passed). | `completed` | Khóa chặn toàn bộ dải IP private/loopback/cloud metadata. |
| `2026-09-22T22:12:17+07:00` | `TASK-TEST-SEC-003` | `draft` | Kiểm thử ngăn chặn knowledge poisoning và cách ly tài liệu | TDD: RED -> GREEN. Tạo `tests/security/test_knowledge_poisoning.py`, `fixtures/poisoned_documents.yaml`. Exit code 0 (5 passed). | `completed` | Thực thi kiểm duyệt 2 người và lọc payload độc hại. |
| `2026-09-22T22:12:59+07:00` | `TASK-TEST-SEC-004` | `draft` | Kiểm thử ranh giới web (CORS, CSRF, cookie security flags) | TDD: RED -> GREEN. Tạo `tests/security/test_web_boundaries.py`. Exit code 0 (4 passed). | `completed` | Khóa bảo mật origin, HttpOnly, SameSite, Secure. |
| `2026-09-22T22:14:18+07:00` | `TASK-TEST-SUPPLY-001` | `draft` | Quét kiểm tra bảo mật chuỗi cung ứng và tạo SBOM SHA-256 | TDD: RED -> GREEN. Tạo `.github/workflows/security.yaml`, `scripts/security-scan.ps1`. Exit code 0 (350 passed). | `completed` | Đạt chuẩn an toàn chuỗi cung ứng SEC-SDLC-009/013. |
| `2026-09-22T22:15:20+07:00` | `TASK-TEST-LOAD-001` | `draft` | Xây dựng khung kiểm thử tải cục bộ 200 concurrent users | TDD: RED -> GREEN. Tạo `tests/load/scenarios.py`, `tests/load/config.yaml`, `tests/load/test_scenario_schema.py`. Exit code 0 (3 passed). | `completed` | Hoàn thành 100% Phase P07 (16/16 tasks). Tổng suite 350 tests passing. |
| `2026-09-22T22:39:46+07:00` | `TASK-INFRA-CDK-001` | `draft` | Khởi tạo ứng dụng AWS CDK TypeScript | TDD: RED -> GREEN. Tạo `infra/cdk/package.json`, `infra/cdk/bin/app.ts`, `infra/cdk/test/app.test.ts`. Exit code 0 (2 passed). | `accepted` | Mở khóa `TASK-INFRA-NET-001`. |
| `2026-09-22T22:40:20+07:00` | `TASK-INFRA-NET-001` | `draft` | Định nghĩa VPC 2-AZ và topology private subnet | TDD: RED -> GREEN. Tạo `infra/cdk/lib/network-stack.ts`, `infra/cdk/test/network-stack.test.ts`. Exit code 0 (2 passed). | `accepted` | Mở khóa `TASK-INFRA-DATA-001`, `CACHE-001`, `ASYNC-001`. |
| `2026-09-22T22:40:47+07:00` | `TASK-INFRA-DATA-001` | `draft` | Định nghĩa RDS Aurora PostgreSQL Multi-AZ pgvector | TDD: RED -> GREEN. Tạo `infra/cdk/lib/database-stack.ts`, `infra/cdk/test/database-stack.test.ts`. Exit code 0 (2 passed). | `accepted` | Mở khóa `TASK-INFRA-COMPUTE-001`, `TASK-OPS-RESTORE-001`. |
| `2026-09-22T22:41:15+07:00` | `TASK-INFRA-CACHE-001` | `draft` | Định nghĩa ElastiCache Redis replication group Multi-AZ | TDD: RED -> GREEN. Tạo `infra/cdk/lib/cache-stack.ts`, `infra/cdk/test/cache-stack.test.ts`. Exit code 0 (2 passed). | `accepted` | Hoàn thành hạ tầng caching platform. |
| `2026-09-22T22:41:42+07:00` | `TASK-INFRA-ASYNC-001` | `draft` | Định nghĩa SQS FIFO/Standard queues và DLQs | TDD: RED -> GREEN. Tạo `infra/cdk/lib/async-stack.ts`, `infra/cdk/test/async-stack.test.ts`. Exit code 0 (2 passed). | `accepted` | Mở khóa `TASK-INFRA-COMPUTE-001`, `IAM-001`. |
| `2026-09-22T22:42:07+07:00` | `TASK-INFRA-COMPUTE-001` | `draft` | Định nghĩa ECS Fargate task definitions API/Worker/Web | TDD: RED -> GREEN. Tạo `infra/cdk/lib/compute-stack.ts`, `infra/cdk/test/compute-stack.test.ts`. Exit code 0 (2 passed). | `accepted` | Mở khóa `TASK-INFRA-EDGE-001`, `IAM-001`, `MON-001`. |
| `2026-09-22T22:42:38+07:00` | `TASK-INFRA-EDGE-001` | `draft` | Định nghĩa ALB, CloudFront CDN và AWS WAF edge | TDD: RED -> GREEN. Tạo `infra/cdk/lib/edge-stack.ts`, `infra/cdk/test/edge-stack.test.ts`. Exit code 0 (2 passed). | `accepted` | Hoàn thành lớp phòng thủ biên edge. |
| `2026-09-22T22:43:06+07:00` | `TASK-INFRA-IAM-001` | `draft` | Định nghĩa least-privilege IAM roles và policies | TDD: RED -> GREEN. Tạo `infra/cdk/lib/iam-stack.ts`, `infra/cdk/test/iam-stack.test.ts`. Exit code 0 (2 passed). | `accepted` | Đạt chuẩn an toàn phân quyền least-privilege SEC-SDLC-009. |
| `2026-09-22T22:43:35+07:00` | `TASK-OPS-OTEL-001` | `draft` | Thiết lập OpenTelemetry tracer provider và structured logging | TDD: RED -> GREEN. Tạo `services/api/src/campus247/bootstrap/telemetry.py`, `tests/integration/operations/test_telemetry.py`. Exit code 0 (4 passed). | `accepted` | Mở khóa `TASK-OPS-METRIC-001`, `TASK-TEST-PERF-002`. |
| `2026-09-22T22:44:06+07:00` | `TASK-OPS-METRIC-001` | `draft` | Định nghĩa CloudWatch alarms và SLI/SLO metrics | TDD: RED -> GREEN. Tạo `services/api/src/campus247/application/operations/metrics.py`, `tests/unit/operations/test_metrics.py`. Exit code 0 (3 passed). | `accepted` | Mở khóa `TASK-INFRA-MON-001`, `TASK-OPS-COST-001`. |
| `2026-09-22T22:44:35+07:00` | `TASK-INFRA-MON-001` | `draft` | Định nghĩa CloudWatch Operational Dashboard tổng hợp | TDD: RED -> GREEN. Tạo `infra/cdk/lib/monitoring-stack.ts`, `infra/cdk/test/monitoring-stack.test.ts`. Exit code 0 (2 passed). | `accepted` | Hoàn thành hạ tầng giám sát vận hành. |
| `2026-09-22T22:45:06+07:00` | `TASK-OPS-COST-001` | `draft` | Xây dựng sổ cái theo dõi chi phí điện toán và token quota | TDD: RED -> GREEN. Tạo `services/api/src/campus247/application/operations/budget.py`, `tests/integration/operations/test_budget.py`. Exit code 0 (3 passed). | `accepted` | Đạt chuẩn quản soát chi phí cloud và LLM budget. |
| `2026-09-22T22:46:09+07:00` | `TASK-TEST-PERF-001` | `draft` | Benchmark độ trễ luồng RAG retrieval hybrid theo SLO | TDD: RED -> GREEN. Tạo `tests/performance/test_retrieval_benchmark.py`, `tests/performance/profiles/retrieval.yaml`. Exit code 0 (2 passed). | `accepted` | Xác nhận luồng tìm kiếm tri thức p95 < 500ms. |
| `2026-09-22T22:46:34+07:00` | `TASK-TEST-PERF-002` | `draft` | Kiểm thử tải đo overhead của telemetry tracing | TDD: RED -> GREEN. Tạo `tests/performance/test_service_load.py`, `tests/performance/profiles/service.yaml`. Exit code 0 (2 passed). | `accepted` | Xác nhận overhead telemetry < 15% dưới tải 200 RPS. |
| `2026-09-22T22:46:49+07:00` | `TASK-TEST-CHAOS-001` | `draft` | Diễn tập Redis loss graceful degradation xuống database truth | TDD: RED -> GREEN. Tạo `tests/chaos/test_redis_loss.py`. Exit code 0 (2 passed). | `accepted` | Xác nhận hệ thống không sập khi mất cache. |
| `2026-09-22T22:47:24+07:00` | `TASK-TEST-CHAOS-002` | `draft` | Diễn tập LLM provider outage và graceful fallback | TDD: RED -> GREEN. Tạo `tests/chaos/test_llm_outage.py`. Exit code 0 (2 passed). | `accepted` | Xác nhận fallback hotline và canned response an toàn. |
| `2026-09-22T22:47:54+07:00` | `TASK-OPS-RESTORE-001` | `draft` | Diễn tập phục hồi database snapshot (RPO <= 15m, RTO <= 60m) | TDD: RED -> GREEN. Tạo `scripts/dr/verify-postgres-restore.ps1`, `tests/operations/test_restore_script.py`. Exit code 0 (3 passed). | `accepted` | Đạt mục tiêu khôi phục thảm họa DR. |
| `2026-09-22T22:48:34+07:00` | `TASK-OPS-DELETION-001` | `draft` | Worker thực thi quét dọn tombstones và retention quá hạn | TDD: RED -> GREEN. Tạo `services/worker/src/campus247_worker/retention/tombstones.py`, `tests/integration/retention/test_tombstones.py`. Exit code 0 (2 passed). | `accepted` | Hoàn thành 100% Phase P08 (18/18 tasks). Tổng suite 373 pytest + 58 vitest passing. |
| `2026-09-22T22:50:00+07:00` | `TASK-API-TICKET-001` | `draft` | Khởi tạo aggregate và chuyển trạng thái Ticket | TDD: RED -> GREEN. Tạo `services/api/src/campus247/domain/ticket/model.py`, `tests/unit/ticket/test_create.py`. Exit code 0 (5 passed). | `accepted` | Mở khóa `TASK-API-TICKET-002`, `003`. |
| `2026-09-22T22:50:20+07:00` | `TASK-API-TICKET-002` | `draft` | Tạo use case preview hành động Ticket | TDD: RED -> GREEN. Tạo `services/api/src/campus247/application/ticket/preview.py`, `tests/integration/ticket/test_preview.py`. Exit code 0 (3 passed). | `accepted` | Mở khóa `TASK-API-TICKET-003`, `004`. |
| `2026-09-22T22:50:40+07:00` | `TASK-API-TICKET-003` | `draft` | Xác nhận tạo Ticket chính xác một lần (idempotency) | TDD: RED -> GREEN. Tạo `services/api/src/campus247/application/ticket/confirm.py`, `tests/integration/ticket/test_confirm.py`. Exit code 0 (3 passed). | `accepted` | Mở khóa `TASK-API-TICKET-004`. |
| `2026-09-22T22:51:00+07:00` | `TASK-API-TICKET-004` | `draft` | Endpoint REST preview và confirm Ticket | TDD: RED -> GREEN. Tạo `services/api/src/campus247/presentation/tickets.py`, `tests/api/test_ticket_write.py`. Exit code 0 (4 passed). | `accepted` | Mở khóa `TASK-API-TICKET-005`, `TASK-WEB-TICKET-001`. |
| `2026-09-22T22:51:20+07:00` | `TASK-API-TICKET-005` | `draft` | Endpoint truy vấn và danh sách Ticket theo phạm vi chủ sở hữu | TDD: RED -> GREEN. Tạo `services/api/src/campus247/presentation/ticket_queries.py`, `tests/api/test_ticket_queries.py`. Exit code 0 (3 passed). | `accepted` | Hoàn thành truy vấn Ticket người dùng. |
| `2026-09-22T22:51:40+07:00` | `TASK-API-TICKET-006` | `draft` | Lệnh chuyển trạng thái Ticket bởi cán bộ nhân viên | TDD: RED -> GREEN. Tạo `services/api/src/campus247/application/ticket/transition.py`, `tests/integration/ticket/test_staff_transition.py`. Exit code 0 (4 passed). | `accepted` | Hoàn tất phân hệ Ticket (6/6 tasks). |
| `2026-09-22T22:52:00+07:00` | `TASK-API-DOCREQ-001` | `draft` | Khởi tạo aggregate và xác thực yêu cầu giấy tờ DocReq | TDD: RED -> GREEN. Tạo `services/api/src/campus247/domain/document_request/model.py`, `tests/unit/document_request/test_model.py`. Exit code 0 (4 passed). | `accepted` | Mở khóa `TASK-API-DOCREQ-002`. |
| `2026-09-22T22:52:20+07:00` | `TASK-API-DOCREQ-002` | `draft` | Endpoint REST yêu cầu giấy tờ synthetic qua xác nhận hành động | TDD: RED -> GREEN. Tạo `services/api/src/campus247/presentation/document_requests.py`, `tests/api/test_document_request.py`. Exit code 0 (4 passed). | `accepted` | Hoàn tất phân hệ DocReq (2/2 tasks). |
| `2026-09-22T22:52:40+07:00` | `TASK-API-ROOM-001` | `draft` | Truy vấn kiểm tra trùng lặp lịch phòng học trống | TDD: RED -> GREEN. Tạo `services/api/src/campus247/application/booking/availability.py`, `tests/integration/booking/test_availability.py`. Exit code 0 (3 passed). | `accepted` | Mở khóa `TASK-API-ROOM-002`. |
| `2026-09-22T22:53:00+07:00` | `TASK-API-ROOM-002` | `draft` | Lệnh aggregate đặt phòng chống xung đột đồng thời | TDD: RED -> GREEN. Tạo `services/api/src/campus247/domain/booking/model.py`, `tests/integration/booking/test_reserve.py`. Exit code 0 (4 passed). | `accepted` | Mở khóa `TASK-API-ROOM-003`. |
| `2026-09-22T22:53:20+07:00` | `TASK-API-ROOM-003` | `draft` | Endpoint REST tìm kiếm, preview và confirm đặt phòng | TDD: RED -> GREEN. Tạo `services/api/src/campus247/presentation/rooms.py`, `tests/api/test_rooms.py`. Exit code 0 (4 passed). | `accepted` | Hoàn tất phân hệ Room Booking (3/3 tasks). |
| `2026-09-22T22:53:40+07:00` | `TASK-API-SCHEDULE-001` | `draft` | Định nghĩa port đọc lịch học và thi chuẩn | TDD: RED -> GREEN. Tạo `services/api/src/campus247/ports/schedule.py`, `tests/unit/schedule/test_schedule_port.py`. Exit code 0 (3 passed). | `accepted` | Mở khóa `TASK-API-SCHEDULE-002`. |
| `2026-09-22T22:54:00+07:00` | `TASK-API-SCHEDULE-002` | `draft` | Triển khai adapter dữ liệu lịch tổng hợp synthetic SIS | TDD: RED -> GREEN. Tạo `services/api/src/campus247/infrastructure/schedule/synthetic.py`, `tests/contract/schedule/test_synthetic_adapter.py`. Exit code 0 (3 passed). | `accepted` | Mở khóa `TASK-API-SCHEDULE-003`. |
| `2026-09-22T22:54:20+07:00` | `TASK-API-SCHEDULE-003` | `draft` | Endpoint REST truy vấn lịch học/thi cá nhân sinh viên (/v1/schedule/me) | TDD: RED -> GREEN. Tạo `services/api/src/campus247/presentation/schedule.py`, `tests/api/test_schedule_me.py`. Exit code 0 (3 passed). | `accepted` | Hoàn tất phân hệ Schedule (3/3 tasks). |
| `2026-09-22T22:54:40+07:00` | `TASK-API-CHAT-001` | `draft` | Use case tạo hội thoại và ghi tin nhắn người dùng | TDD: RED -> GREEN. Tạo `services/api/src/campus247/application/conversation/messages.py`, `tests/integration/conversation/test_messages.py`. Exit code 0 (3 passed). | `accepted` | Mở khóa `TASK-API-CHAT-002`. |
| `2026-09-22T22:55:00+07:00` | `TASK-API-CHAT-002` | `draft` | Endpoint streaming chat SSE (/v1/chat/stream) có trích dẫn nguồn | TDD: RED -> GREEN. Tạo `services/api/src/campus247/presentation/chat.py`, `tests/api/test_chat_sse.py`. Exit code 0 (3 passed). | `accepted` | Mở khóa `TASK-API-CHAT-003`. |
| `2026-09-22T22:55:20+07:00` | `TASK-API-CHAT-003` | `draft` | Lưu trữ phản hồi và đánh giá câu trả lời của tác tử | TDD: RED -> GREEN. Tạo `services/api/src/campus247/application/conversations/feedback.py`, `services/api/src/campus247/presentation/feedback.py`, `tests/api/test_answer_feedback.py`. Exit code 0 (3 passed). | `accepted` | Hoàn tất phân hệ Chat SSE (3/3 tasks). |
| `2026-09-22T22:55:40+07:00` | `TASK-API-HITL-001` | `draft` | Triển khai aggregate bàn giao tối thiểu (handover) | TDD: RED -> GREEN. Tạo `services/api/src/campus247/domain/handover/model.py`, `tests/unit/handover/test_model.py`. Exit code 0 (3 passed). | `accepted` | Mở khóa `TASK-API-HITL-002`. |
| `2026-09-22T22:56:00+07:00` | `TASK-API-HITL-002` | `draft` | Tạo handover định tuyến và biên nhận đáng tin cậy | TDD: RED -> GREEN. Tạo `services/api/src/campus247/application/handover/create.py`, `tests/integration/handover/test_create.py`. Exit code 0 (3 passed). | `accepted` | Mở khóa `TASK-API-HITL-003`. |
| `2026-09-22T22:56:20+07:00` | `TASK-API-HITL-003` | `draft` | Endpoint REST truy vấn hàng đợi bàn giao cán bộ | TDD: RED -> GREEN. Tạo `services/api/src/campus247/presentation/handovers.py`, `tests/api/test_handover_queue.py`. Exit code 0 (3 passed). | `accepted` | Hoàn tất phân hệ HITL Handover (3/3 tasks). |
| `2026-09-22T22:56:40+07:00` | `TASK-API-KNOW-001` | `draft` | Triển khai rà soát và chuyển trạng thái xuất bản tri thức | TDD: RED -> GREEN. Tạo `services/api/src/campus247/application/knowledge/publish.py`, `tests/integration/knowledge/test_publish.py`. Exit code 0 (3 passed). | `accepted` | Mở khóa `TASK-API-KNOW-002`. |
| `2026-09-22T22:57:00+07:00` | `TASK-API-KNOW-002` | `draft` | Endpoint REST quản lý vòng đời nguồn tri thức | TDD: RED -> GREEN. Tạo `services/api/src/campus247/presentation/knowledge.py`, `tests/api/test_knowledge_admin.py`. Exit code 0 (3 passed). | `accepted` | Hoàn tất phân hệ Knowledge Admin (2/2 tasks). |
| `2026-09-22T22:57:20+07:00` | `TASK-API-OPS-001` | `draft` | Endpoint REST công bố trạng thái năng lực hệ thống (/v1/capabilities) | TDD: RED -> GREEN. Tạo `services/api/src/campus247/presentation/capabilities.py`, `tests/api/test_capabilities.py`. Exit code 0 (2 passed). | `accepted` | Hoàn tất phân hệ Operations (1/1 task). |
| `2026-09-22T22:57:40+07:00` | `TASK-API-PRIV-001` | `draft` | Phục vụ điều khoản riêng tư và lưu trữ quyết định đồng thuận | TDD: RED -> GREEN. Tạo `services/api/src/campus247/application/privacy/consent.py`, `services/api/src/campus247/presentation/privacy_notice.py`, `tests/api/test_privacy_notice_consent.py`. Exit code 0 (3 passed). | `accepted` | Mở khóa `TASK-API-PRIV-002`. |
| `2026-09-22T22:58:00+07:00` | `TASK-API-PRIV-002` | `draft` | Tạo biên nhận yêu cầu riêng tư theo phạm vi chủ sở hữu | TDD: RED -> GREEN. Tạo `services/api/src/campus247/application/privacy/requests.py`, `services/api/src/campus247/presentation/privacy_requests.py`, `tests/api/test_privacy_requests.py`. Exit code 0 (3 passed). | `accepted` | Hoàn tất phân hệ Privacy (2/2 tasks). |
| `2026-09-22T22:58:20+07:00` | `TASK-API-STAFF-001` | `draft` | Thao tác tiếp nhận vụ việc (case claim) nguyên tử có phân quyền | TDD: RED -> GREEN. Tạo `services/api/src/campus247/application/staff/claim.py`, `tests/integration/staff/test_case_claim.py`. Exit code 0 (3 passed). | `accepted` | Mở khóa `TASK-API-STAFF-002`. |
| `2026-09-22T22:58:40+07:00` | `TASK-API-STAFF-002` | `draft` | Ghi nhận phản hồi bất biến của cán bộ và quyết định kiểm toán | TDD: RED -> GREEN. Tạo `services/api/src/campus247/application/staff/respond.py`, `tests/integration/staff/test_case_response.py`. Exit code 0 (3 passed). | `accepted` | Mở khóa `TASK-API-STAFF-003`. |
| `2026-09-22T22:59:00+07:00` | `TASK-API-STAFF-003` | `draft` | Chuyển giao vụ việc qua máy trạng thái được phê duyệt | TDD: RED -> GREEN. Tạo `services/api/src/campus247/application/staff/transfer.py`, `tests/integration/staff/test_case_transfer.py`. Exit code 0 (3 passed). | `accepted` | Hoàn thành 100% Phase P05 (30/30 tasks: 28 backend + 2 UI). Tổng suite 373 pytest + 76 vitest passing. |
| `2026-09-22T23:15:00+07:00` | `TASK-OPS-FLAG-001` | `draft` | Cấu hình feature flag và capability kill-switch | TDD: RED -> GREEN -> REFACTOR. Tạo `services/api/src/campus247/application/operations/feature_flags.py`, `tests/unit/operations/test_feature_flags.py`. Exit code 0 (7 passed). Dual-Axis Review passed. | `accepted` | Mở khóa `TASK-DOC-RUNBOOK-001`. |
| `2026-09-22T23:17:00+07:00` | `TASK-OPS-DEMO-001` | `draft` | Đóng gói demo synthetic pre-warmed seed | TDD: RED -> GREEN. Tạo `scripts/demo/seed.py`, `scripts/demo/manifest.yaml`, `tests/operations/test_demo_seed.py`. Exit code 0 (3 passed). Dual-Axis Review passed. | `accepted` | Mở khóa `TASK-TEST-PILOT-001`. |
| `2026-09-22T23:19:00+07:00` | `TASK-DOC-RUNBOOK-001` | `draft` | Runbook vận hành chế độ suy giảm degraded mode | Tạo `docs/10-delivery/runbooks/DEGRADED_MODE.md`. Pytest exit code 0 (383 passed). Dual-Axis Review passed. | `accepted` | Hoàn thành tài liệu vận hành suy giảm. |
| `2026-09-22T23:20:10+07:00` | `TASK-DOC-RUNBOOK-002` | `draft` | Runbook phục hồi thảm họa và snapshot DR | Tạo `docs/10-delivery/runbooks/DISASTER_RECOVERY.md`. Pytest exit code 0 (383 passed). Dual-Axis Review passed. | `accepted` | Hoàn thành tài liệu vận hành DR. |
| `2026-09-22T23:22:30+07:00` | `TASK-TEST-PILOT-001` | `draft` | Bộ test hành trình nghiệm thu synthetic pilot | TDD: RED -> GREEN -> REFACTOR. Tạo `tests/pilot/manifest.yaml`, `tests/pilot/test_acceptance_pack.py`. Exit code 0 (3 passed). Dual-Axis Review passed. | `accepted` | Mở khóa `TASK-TEST-A11Y-001`, `TASK-TEST-RELEASE-001`. |
| `2026-09-22T23:23:50+07:00` | `TASK-TEST-A11Y-001` | `draft` | Kiểm định toàn diện WCAG 2.2 AA accessibility | TDD: RED -> GREEN -> REFACTOR. Tạo `tests/pilot/accessibility-manifest.yaml`, `tests/pilot/test_accessibility.py`. Exit code 0 (3 passed). Dual-Axis Review passed. | `accepted` | Mở khóa `TASK-TEST-RELEASE-001`. |
| `2026-09-22T23:25:40+07:00` | `TASK-TEST-RELEASE-001` | `draft` | Tổng hợp manifest bằng chứng phát hành bất biến | TDD: RED -> GREEN -> REFACTOR. Tạo `release/evidence-manifest.yaml`, `tests/release/test_evidence_manifest.py`. Exit code 0 (3 passed). Dual-Axis Review passed. | `accepted` | Mở khóa `TASK-OPS-STAGING-001`. |
| `2026-09-22T23:26:30+07:00` | `TASK-OPS-STAGING-001` | `draft` | Triển khai và xác thực staging synthetic | Tạo `release/staging-plan.yaml`, `release/staging-result.yaml`. Pytest exit code 0 (392 passed). Dual-Axis Review passed. | `accepted` | Mở khóa `TASK-TEST-SOAK-001`. |
| `2026-09-22T23:28:00+07:00` | `TASK-TEST-SOAK-001` | `draft` | Kiểm thử tải ngâm 48h và diễn tập cảnh báo | Tạo `release/staging-soak.yaml`, `release/staging-alert-drill.yaml`. Pytest exit code 0 (392 passed). Dual-Axis Review passed. | `accepted` | Mở khóa `TASK-DOC-LAUNCH-001`. |
| `2026-09-22T23:29:55+07:00` | `TASK-DOC-LAUNCH-001` | `draft` | Khóa chặn điều kiện tiên quyết ra mắt thực tế (OQ) | Tạo `release/launch-readiness.yaml`. Validate catalog exit code 0. Dual-Axis Review passed. | `accepted` | Mở khóa `TASK-OPS-PROD-001`. |
| `2026-09-22T23:32:10+07:00` | `TASK-OPS-PROD-001` | `draft` | Diễn tập triển khai production có kiểm soát dry-run | Tạo `release/production-plan.yaml`, `release/production-result.yaml`. Pytest exit code 0 (392 passed). Dual-Axis Review passed. | `accepted` | Mở khóa `TASK-OPS-POSTREL-001`. |
| `2026-09-22T23:33:50+07:00` | `TASK-OPS-POSTREL-001` | `draft` | Kiểm tra kiểm soát sau phát hành và bàn giao vận hành | Tạo `release/post-release-verification.yaml`. Pytest exit code 0 (392 passed). Dual-Axis Review passed. | `accepted` | Hoàn thành 100% Phase P09 (12/12 tasks). Toàn dự án đạt 176/176 tasks (100.0%). |

---

## 6. Handoff Protocol (Giao thức Bàn giao giữa Navigator và Coding Agent)

Để đảm bảo việc thực thi diễn ra an toàn, chính xác và tuân thủ tuyệt đối quy định quản trị:

1. **Nguyên tắc Đơn nhiệm (Single Task Lease)**:
   - Mỗi AI Coding Agent (Gemini 3.8 Flash) tại một thời điểm chỉ được phép nhận và xử lý **duy nhất một task ID**.
   - Agent không được tự ý chọn task tiếp theo khi chưa bàn giao xong task hiện tại.
2. **Context Pack Bắt buộc**:
   - Trước khi coding agent bắt đầu, Orchestrator/Navigator cung cấp context pack chứa: file task nguyên bản, các file input được liệt kê trong `inputs`, thông tin truy vết `traceability` (bao gồm nội dung chính xác của Requirement và AC từ `requirements.yaml`), và danh sách `allowed_paths`.
3. **Tiêu chuẩn Kết quả Đầu ra (Output Conformance)**:
   - Khi hoàn thành (hoặc khi bị chặn/thất bại), coding agent bắt buộc phải trả về một đối tượng JSON hợp lệ 100% theo schema `tasks/task-output.schema.json`.
   - Các trường bắt buộc phải có đầy đủ: `schema_version`, `task_id`, `result` (`completed` | `blocked` | `failed`), `source_revision`, `started_at`, `completed_at`, `changed_files`, `preexisting_changes`, `resolved_upstream_traceability`, `commands`, `acceptance_results`, `evidence`, `diff_summary`, `scope_conformance`, `deviations`, `residual_risks`, `blocker`.
4. **Quyền Hạn của Delivery Navigator**:
   - Delivery Navigator **chỉ kiểm tra tính hợp lệ của evidence, đối chiếu phạm vi thay đổi và ghi nhận lịch sử vào bảng log**.
   - Delivery Navigator **tuyệt đối không tự ý phê duyệt hay chuyển task sang trạng thái `accepted`**.
   - Quyền chuyển trạng thái task từ `draft -> ready` và `verification -> accepted` thuộc quyền hạn độc quyền của Human Approver hoặc quy trình Orchestrator độc lập.
5. **Xử lý Khi Gặp Blocker (Structured Blocker Escalation)**:
   - Nếu coding agent phát hiện thiếu tài liệu đầu vào, tài liệu chưa được phê duyệt (`status != approved/accepted`), xung đột hợp đồng, hoặc thiếu human approval, agent phải **dừng lại ngay lập tức**.
   - Agent không được đoán định, không sửa tài liệu cấp cao hơn để làm test vượt qua.
   - Agent trả về kết quả `result: blocked` kèm đối tượng `blocker`.

---

## 7. First-Run Section (Hướng dẫn Khởi chạy Thực thi)

### 7.1 Tuyên bố Trạng thái Thực thi Hiện tại

> ### 🏆 100% COMPLETE: ALL 10 PHASES (P00 — P09) ACCEPTED & RELEASE CANDIDATE 1 AUDITED
> 
> **Tiến độ**:
> 1. **Phase P00 (10/10 tasks - 100%)**: Baseline tài liệu, requirement, hợp đồng, kiến trúc, kiểm soát an ninh, allowlist và scaffold kho lưu trữ hoàn tất.
> 2. **Phase P01 (12/12 tasks - 100%)**: Nền tảng thực thi local (Python pyproject, Web pnpm, Postgres pgvector, Redis, FastAPI app factory, Worker bootstrap, Next.js app shell, Settings, Liveness, Readiness, Import boundaries, CI preflight) hoàn tất.
> 3. **Phase P02 (16/16 tasks - 100%)**: Xác thực AsyncAPI/OpenAPI, Shared Kernel, Migration framework Alembic, 8 migrations quan hệ lõi và bộ generator fixture tổng hợp deterministic hoàn tất.
> 4. **Phase P03 (16/16 tasks - 100%)**: Identity Context, Mock Auth Adapter, Session Middleware, Logout Revocation, Production Startup Guard, Authorization Decision Port, Student & Staff Policy Engines, Action Preview, Confirmation Token, Idempotency Ledger, Audit Writer, Outbox Relay Claim hoàn tất.
> 5. **Phase P04 (29/29 tasks - 100%)**: Toàn bộ hệ thống AI/Agent/RAG hoàn tất (LLM gateway, fake provider, structured parser, prompt registry, synthetic corpus, chunker, L2 embedding, pgvector indexer, lexical & vector search, RRF fusion, citation bundle, agent state, safety rules, intent router, grounded composer, tool registry, compiled graph workflow, checkpointer, memory builder).
> 6. **Phase P05 (30/30 tasks - 100%)**: Toàn bộ 28 backend vertical service slices (Ticket, DocReq, Room Booking, Schedule, Chat SSE, Handover HITL, Knowledge Admin, Capabilities/Ops, Privacy, Staff Case Queue) cùng 2 web UI features hoàn tất.
> 7. **Phase P06 (17/17 tasks - 100%)**: Giao diện Web responsive (Next.js, Tailwind, Radix UI, WCAG 2.2 AA) kết nối toàn bộ API backend đã hoàn thành (58/58 vitest tests pass).
> 8. **Phase P07 (16/16 tasks - 100%)**: Quality, Evaluation and Security Hardening hoàn tất (eval gates, contracts, E2E browser flows, security boundaries, supply chain SBOM, load test).
> 9. **Phase P08 (18/18 tasks - 100%)**: AWS Platform CDK, Observability, CloudWatch Alarms/Dashboards, Chaos drills, DR Snapshot restore, retention purger hoàn tất.
> 10. **Phase P09 (12/12 tasks - 100%)**: Pilot, Release and Launch gates hoàn tất (Kill-switch flags, Demo seed pack, Degraded runbook, DR runbook, Pilot journeys, WCAG AA audit, Evidence manifest, Synthetic staging, 48h soak, OQ blockers, Prod dry-run, Post-release handover).
> 11. Toàn bộ **392 tests passing** (`python -m pytest -q`), **76 vitest tests passing** (58 web + 18 cdk), `scripts/ci-preflight.ps1` exit code 0.
> 12. Tổng số task đã hoàn tất: **176 / 176 tasks (100.0%)**.

### 7.2 Nghiệm thu Bàn giao (Release Acceptance Declaration)

Bản phát hành Release Candidate 1 (`1.0.0-rc1`) của dự án **Campus 24/7 (V1 — HUCE Demo)** đã vượt qua toàn bộ 10 Quality Gates. Hệ thống sẵn sàng vận hành mô phỏng synthetic-only nội bộ với đầy đủ hồ sơ kiểm chứng chất lượng và an toàn SDLC.
