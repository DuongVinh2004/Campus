# TASK-RAGUP-FILTER-003 — execution and acceptance

2026-10-03, Asia/Bangkok. Direct human delegation cho reviewer/orchestrator trong
chat duy nhất; đây là execution evidence, không thay normative contracts.

Objective: lexical primary và OR fallback áp cùng compiled authorized predicate
trong PostgreSQL trước rank/LIMIT. Dependency FILTER-002 accepted trong
RAG_DELEGATED_DECISIONS_20261003.md; fixture head 0012 được reverify trước và sau.

## Preflight và scope

Canonical workspace `C:\Users\Duong Vinh\Vinh`; canonical/reparse checks trước
mutation, git status/diff và baseline 1.176 source files được giữ riêng. Ownership
đã được người dùng xác nhận chỉ còn agent này. Đọc existing files trước patch.
Không thêm dependency, migration, model/profile/threshold hoặc đổi dữ liệu retained.

Product files:

- `services/api/src/campus247/infrastructure/retrieval/lexical.py` — scoped edit.
- `tests/integration/retrieval/test_lexical.py` — scoped edit: explicit test profile
  cho legacy SQLite fixture; giữ assertions cũ, thêm negative environment cases.
- `tests/integration/retrieval/test_lexical_authorization.py` — new tests.

Supporting evidence: `delegated_verify.py`, exclusive JSON files và docs này.
FILTER-002 compiler/helpers/test files thuộc objective đã nghiệm thu trước.
Final scope manifest đối chiếu mọi baseline file; không dùng Git HEAD để khôi
phục dirty bytes hoặc suy ra missing historical FILTER-001 initial hashes.

## Behavior

Adapter nhận compiler có trusted institution binding và typed RetrievalContext;
validate trước mọi DB operation. Query limit phải là integer 1..profile.lexical_k.
Không có compiler/context/explicit database binding thì fail closed. Mọi input
values được bind; aliases/predicate là static SQL. Cả AND primary và OR fallback
INNER JOIN source/version, dùng cùng predicate trước ORDER BY/LIMIT. Fallback
SQL failures propagate để downstream ghi failure/degradation, không giấu thành
thành công rỗng. Legacy SQLite helper chỉ chạy trong explicit test environment.

Bootstrap hiện còn legacy callback thiếu compiler/context và vector bị disabled.
FAQ runtime vì vậy abstain an toàn; việc này không được gọi là canonical pipeline
đã triển khai. Không activate production branch hoặc manifest trong objective này.

## Acceptance mapping

| AC | Status | Observable evidence |
|---|---|---|
| Predicate trước rank/LIMIT ở mọi query/fallback | passed | Actual adapter statements có identical compiled predicate/binds trước ORDER BY/LIMIT; primary 1 call và OR fallback 2 calls |
| Query plan dùng index phù hợp | passed, eligibility only | Actual statements EXPLAIN dùng ix_document_retrieval_effective; separate lexical-predicate EXPLAIN dùng ix_knowledge_chunk_tsv; SET LOCAL enable_seqscan=off chỉ trong rollback probe |
| Unauthorized/expired rows không xuất hiện candidate/diagnostic | passed | Unauthorized chunk có rank cao hơn positive control vẫn bị loại tại LIMIT 1; scope, date, simulation, state, approval negatives ở cả hai branches; output chỉ mapped eligible hits, không có raw-query diagnostics |
| Missing authorization/config fail closed | passed | Untyped/missing context, missing compiler/binding và invalid limit bị chặn trước database fetch |
| Fixture và pre-existing source state preserved | passed in scoped coverage | All synthetic mutations savepoint rollback; independent read-only final snapshot head 0012/fingerprints/counts unchanged; final scope manifest riêng |

Test states DRAFT/SUPERSEDED/ARCHIVED đều excluded. Historical schema không cho
WITHDRAWN; không sửa lifecycle để tạo fixture. Compiler chỉ cho PUBLISHED nên
unknown/unsupported state không thể eligible; không claim inserted WITHDRAWN test.

Seed có NULL content_tsv; test populate tsv và create higher-rank denied row chỉ
trong savepoint. Positive control dùng real PostgreSQL FTS, không fake candidates.

## Commands and retained evidence

Interpreter cho mọi command: `infra/local/rag-fixture/.venv/Scripts/python.exe`,
Python 3.12.14, `-B`; cwd workspace. Runner chặn outbound DNS/network trong tests;
live tests chỉ kết nối đúng 127.0.0.1:15433 sau receipt/marker/image/mount/network
checks. No default DSN; credential chỉ giữ trong memory. Fresh canonical basetemp,
retention_policy=all và deletion guard; giữ tất cả failed/pass run artifacts.

| Exact runner invocation after python -B | Exit | Evidence/result |
|---|---:|---|
| infra/local/rag-fixture/delegated_verify.py filter003-offline-01 tests/integration/retrieval/test_lexical.py tests/unit/retrieval tests/architecture tests/api/test_app_boot.py | 0 | delegated-filter003-offline-01.json; 350 passed, no skips |
| infra/local/rag-fixture/delegated_verify.py live-filter003-final-03 tests/integration/retrieval/test_lexical_authorization.py tests/integration/retrieval/test_authorized_filters.py tests/integration/test_retrieval_scope_migration.py tests/integration/test_embedding_index_manifest.py tests/integration/rag_fixture/test_guard.py tests/integration/test_migration_0009.py | 0 | delegated-live-filter003-final-03.json; 57 passed, no skips |
| infra/local/rag-fixture/delegated_verify.py broad-final-01 tests/unit tests/architecture tests/evals tests/api/test_app_boot.py tests/integration/retrieval/test_lexical.py | 0 | delegated-broad-final-01.json; 648 passed, no skips |
| infra/local/rag-fixture/delegated_verify.py snapshot-final-filter003 | 0 | delegated-snapshot-final-filter003.json; independent read-only verification |

EXPLAIN artifact:
`infra/local/rag-fixture/.venv/delegated-live-filter003-final-03-outputs/lexical-filter-explain.json`.

Two repair attempts được giữ minh bạch:

1. Initial live run: 56 passed, 1 setup error — pytest tmp_path alias cleanup
   bị deletion guard chặn. Chuyển test output sang exclusive canonical directory;
   giữ guard. Seed tsv positive control được populate trong savepoint.
2. Second live run: 56 passed, 1 failure — new oracle đòi exact GIN plan cho
   mỗi tiny-fixture query. Approved AC chỉ đòi appropriate index. Independent
   rollback EXPLAIN inspection xác nhận planner chọn document effective index
   và chunk ordinal index. Final oracle kiểm tra actual predicate index và kiểm
   tra GIN eligibility riêng; không đổi production SQL/settings, thresholds hoặc
   existing expected results. Final third run đạt 57/57, không sửa tiếp.

Failed evidence: delegated-live-filter003-01.json, delegated-live-filter003-02.json.
Diagnostic evidence: delegated-filter003-plan-inspection.json. Không overwrite
hoặc xóa evidence để che failure. Không dùng EXPLAIN này làm latency benchmark.

## Preservation and limitations

Final snapshot: head 0012; 1 source/1 document/3 chunks; retained vector dimension
1536; 329 columns/51 indexes/169 constraints; active pointer 0.
Rows SHA-256 `00a182aedfa2abaa918c64404673621dda9e15199cb1aa920812828e81dbc0c2`;
indexes SHA-256 `aa812b4615ba831bf8ce8956ddda436068e01a6f12bd291b37244b4a7ddc7304`.

Reviewer decision: FILTER-003 completed/accepted trong lexical adapter scope.
FILTER-001 full runtime AC, FILTER-004/005, CONTEXT-003, RETRIEVE-001/canonical
retriever, real model/index and quality remain not_verified/not accepted.
Small synthetic corpus và index eligibility không chứng minh release SLO/recall.
Historical FILTER-001 initial hash coverage gap không được phục hồi hoặc che đi.
Next dependency frontier ghi trong RAG_RUNTIME_INTAKE_20261003.md.
