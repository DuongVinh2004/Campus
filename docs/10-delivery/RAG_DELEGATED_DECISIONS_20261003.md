# RAG upgrade — delegated orchestration decisions

Ngày 2026-10-03, Asia/Bangkok. Direct human instruction: “không còn chat song
song, chỉ có bạn làm, tôi ủy quyền cho bạn quyết định, lên kế hoạch và thực hiện
chuẩn chỉ chính xác đi”. Quyền được giao cho reviewer/orchestrator trong chat
này; không thay hoặc nới Global Agent Safety Policy, DOCUMENT_CONTROL, model,
revision, thresholds, dependency allowlist hoặc deployment/live-provider gates.

## Ownership và evidence được review

Lease trước đó của vector.py, embed_fake.py, run_ingestion.py và bootstrap/settings
đã kết thúc theo direct human instruction. Tiếp nhận bytes hiện tại, giữ mọi
dirty/untracked state; không coi handoff này là nghiệm thu implementation.
Baseline mới `infra/local/rag-fixture/delegated-20261003-baseline.json` ghi trực
tiếp 1.176 source files bằng exclusive-create. 1.175 entries của final manifest
lượt trước đều khớp. Snapshot không bao phủ credential/ignored-runtime bytes.

Review căn cứ: approved ADR-005/RAG_PIPELINE/DATA_DICTIONARY; plan đã được người
dùng duyệt; source và tests đã đọc; evidence 561 deterministic + 51 PostgreSQL
tests pass không skip; read-only head 0012 và fingerprints preserved. Evidence
lượt trước ở RAG_CONTINUATION_20261003_REVIEW.md và continuation JSON files.

## Quyết định reviewer

| Task/objective | Decision | Phạm vi nghiệm thu |
|---|---|---|
| CONTEXT-001 | accepted | Typed immutable context/scope, required fields, serialization/negative contracts; end-to-end propagation riêng ở CONTEXT-003 |
| CONTEXT-002 | accepted | Trusted factory/resolver input, spoofing/missing/inactive/expired/cross-tenant rejection, audit-safe trace; không nghiệm thu production resolver wiring |
| RERANK-001 | accepted | Port/request/output contract và strict ordered-ID/model/finite-score/latency validator; adapter/model quality riêng |
| EVAL-001 | accepted | Gold schema và offline integrity validator, duplicate/paraphrase/split/context/version/citation checks; không accept dataset shards hoặc real retrieval quality |
| EMBED-001 | accepted | Shared vendor-neutral port, API/worker imports và model/dimension/input/batch errors; không accept inference |
| EMBED-004 | accepted | Additive manifest/storage, synthetic compatibility/schema/pointer rollback evidence tại 0012; active production index/model còn riêng |
| FILTER-001 storage milestone | accepted as dependency milestone | Additive fields/checks/indexes, new source rejection, legacy preservation và fail-closed predicate probes |
| FILTER-001 toàn bộ runtime AC | pending | Production SQL exclusion phải được kiểm chứng ở FILTER-003/004/005; historical initial-hash gap giữ nguyên |
| RETRIEVE-001 | verification, not accepted | Profile/schema/loader tests đạt; production hard-coded constants/wiring còn gap |
| EMBED-003 | accepted | Fresh-import/profile/use guards và production import graph đã reverify; vector/ingestion bị chặn trước DB/provider/config access |
| FILTER-002 | accepted | Compiler và PostgreSQL parameterized-predicate probes; legacy helper được bảo toàn |
| FILTER-003 | accepted | Lexical primary/fallback SQL, authorization trước rank/LIMIT và rollback-only PostgreSQL leakage/EXPLAIN evidence |
| CONTEXT-003 | blocked at runtime binding; not accepted | Chưa có deployment institution binding/trusted scope resolver; graph/bootstrap/reranker/citation propagation chưa triển khai đầy đủ |

FILTER-001 gate được phân định theo layer/objective của plan: storage milestone
mở compiler FILTER-002; full production-filter AC giữ tại downstream integration.
Đây là quyết định orchestration cụ thể trong quyền người dùng vừa giao sau khi
điểm nghẽn đã được giải thích. Không ghi toàn task FILTER-001 completed, không
thay source contract và không coi SQL probe là production runtime evidence.
Release và FILTER-005 vẫn đòi tất cả runtime AC pass; missing/unknown metadata
luôn excluded. Không có waiver cho authorization hoặc source leakage.

## Thứ tự thực hiện

1. FILTER-002: compiler + unit/property predicates; verify rồi reviewer nghiệm thu.
2. FILTER-003: lexical primary/fallback trước rank/LIMIT; PostgreSQL positive,
   negative/leakage tests và EXPLAIN; verify và nghiệm thu riêng.
3. Audit CONTEXT-003/EMBED-003/RETRIEVE-001 sau hai objectives trên, thực hiện
   chỉ khi dependencies/scope đủ. Không khai báo full propagation trước canonical
   retriever, real model và citation paths sẵn sàng.
4. EMBED-002/RERANK-002: chuẩn bị runtime decision/bundle requirements theo exact
   approved revisions; không invent API protocol, tải model, cài package hoặc
   gọi live provider trước khi có runtime artifacts/scope đủ và exact approval.
5. Các downstream giữ dependency gates; không fake gold quality, không đọc sealed
   text, không commit/push/deploy hoặc thực hiện destructive operations.

Task RAGUP chưa materialize catalog YAML, nên kết quả các objectives được ghi
trong execution evidence/AC tables theo direct human request. Không đổi catalog
accepted bằng cách sửa task index hoặc expected results.

## Objective TASK-RAGUP-FILTER-002 — accepted

Dependencies: CONTEXT-002 accepted; FILTER-001 storage milestone accepted theo
quyết định trên. Không có dependency/package/runtime/source contract change.
Product scope: application/retrieval/filters.py; test_retrieval_filters.py;
tests/integration/retrieval/test_authorized_filters.py.
Correction: filters.py là tracked clean file đã có; compiler được bổ sung, còn
legacy _parse_dt/RetrievalFilter được bảo toàn. Hai test files là mới. Scope check
phát hiện initial Add File operation đã thay helper; baseline hash khớp HEAD
chứng minh recovery bytes, nên đã đưa nguyên helper body trở lại bằng scoped
patch, giữ implementation mới. Evidence initial runs không bị overwrite. Chỉ
nghiệm thu final bytes sau regression cả helper cũ và compiler mới.

| AC | Result | Evidence |
|---|---|---|
| Parameterized SQL, không interpolate context values | passed | Static identifiers/operators; named/asyncpg binds; injection-like program value là dữ liệu |
| Lexical/vector dùng cùng eligibility semantics | passed | Cùng static predicate; asyncpg render chỉ đổi placeholders, không đổi điều kiện |
| Empty/missing scope không allow-all | passed | Typed/context round-trip guard và bypass-constructor negative cases |
| Date/role/audience/faculty/tenant negative cases | passed | 15 role combinations × 4 audiences trong unit suite; actual PostgreSQL crossing/date/state/approval/scope negatives |
| Simulation cần profile + trusted context | passed | Four-way boolean unit matrix và PostgreSQL positive/negative controls |
| Legacy unknown excluded; effective_until NULL cần applicability review | passed | PostgreSQL compiled-predicate probes, không phải copied handwritten predicate |
| Preservation và ownership | passed | Mọi probe rollback; f.verify khớp head 0012/fingerprints; 1.175 baseline files không đổi, chỉ filters.py thay đổi đúng scope, helper AST khớp bản gốc |

Commands dùng fixture Python -B delegated_verify.py:

- filter002-unit-01: compiler/context/reranker/architecture tests; exit 0,
  **180 passed**, no skips; delegated-filter002-unit-01.json.
- snapshot-pre-filter003: independent read-only fixture; exit 0,
  delegated-snapshot-pre-filter003.json.
- live-filter002-01: actual compiled predicate trên PostgreSQL; exit 0,
  **1 passed**, no skips; delegated-live-filter002-01.json.
- filter002-final-02: toàn unit retrieval, architecture và legacy helper
  regression; exit 0, **342 passed**, no skips; delegated-filter002-final-02.json.
  Performance test dùng fake chỉ là helper regression, không là benchmark/quality.
- delegated-filter002-scope.json: exit 0; helper AST preservation, source hash
  scope và git diff check. Final broad suite ở FILTER-003 cũng kiểm tra compiler.

Reviewer decision: FILTER-002 completed/accepted trong scope compiler. Compiler
không authenticate client claims, không activate index và chưa là integration
của lexical/vector branches. Production-query wiring thuộc objective tiếp theo.

## Objective TASK-RAGUP-FILTER-003 — accepted

AC mapping, exact commands, failed-run history, EXPLAIN và preservation được ghi
riêng trong RAG_FILTER_003_EXECUTION.md. Final evidence: **57 PostgreSQL tests**
và **648 deterministic tests** pass, không skip. Independent read-only snapshot
sau tests xác nhận head 0012, rows/index fingerprints và empty active pointer.
Chỉ nghiệm thu lexical adapter; bootstrap/canonical retriever chưa được bật.

## Objective TASK-RAGUP-EMBED-003 — accepted after audit

Không sửa bytes candidate được bàn giao. Đọc fake adapter, vector guard,
ingestion guard và profile/import graph tests; tests chạy lại trong final 342/648
suites. Dependency EMBED-001 đã accepted. Mapping:

| AC | Result | Evidence |
|---|---|---|
| Chỉ import fake trong explicit test profile | passed | Fresh Python subprocess từng environment; guard không dựa pytest/module cache |
| dev/staging/production fail closed khi chọn fake | passed | Constructor/use guards cả cached module sau environment change; vector/ingestion reject trước DB/provider/config |
| Không production import từ embed_fake.py | passed | AST import graph services/scripts, kể cả literal dynamic-import references |
| Fake không là model-quality evidence | passed | Fake profile test-only, runtime query/ingestion disabled; in-memory fixture chỉ test và không kết nối database |

Source-preservation sẽ được đối chiếu trong delegated-20261003-final-scope.json.
Đây là nghiệm thu isolation, không nghiệm thu EMBED-002/005/006 hoặc startup
với model thật. Không có fake output thay cho live inference.

## Frontier còn lại

RAG_RUNTIME_INTAKE_20261003.md ghi các đầu vào thiếu, phương án runtime và
thứ tự mở downstream. CONTEXT-003/RETRIEVE-001 vẫn có implementation gaps;
không coi chúng đã hoàn thành chỉ vì profile/type tests pass. Gold shards không
được tạo bằng ba synthetic legacy chunks: chưa có trusted active 1024 index và
corpus được review. Không đọc sealed test text để chỉnh implementation.
