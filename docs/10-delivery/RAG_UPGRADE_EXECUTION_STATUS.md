# RAG upgrade execution snapshot

Ngày theo client: 2026-10-03 (Asia/Bangkok). Đây là evidence/report không normative,
không thay approval, contract hoặc trạng thái accepted trong catalog.

Nguồn backlog: [RAG_PRODUCTION_UPGRADE_PLAN.md](../05-ai/RAG_PRODUCTION_UPGRADE_PLAN.md).
Đã đối chiếu đủ **71 task IDs**, gồm 20 data shards; không có
`tasks/items/TASK-RAGUP-*.yaml` được materialize ở snapshot này. Plan vẫn có
frontmatter draft; direct human approval backlog và yêu cầu triển khai task
không giao nhau được áp dụng, nhưng không suy ra approval production/live
provider, dependency mới hoặc thay đổi contract.

## Scope và ownership

Người dùng xác nhận chat kia vẫn chạy và giữ lease fake embedding, vector adapter
và ingestion script. Chat này không sửa các path đó, shared fixtures, bootstrap,
settings, profile, reranker contract, gold schema/validator/datasets hoặc dependency.
Không spawn subagent hoặc gửi message sang chat khác.

Lượt triển khai CONTEXT-001 chỉ sửa:

- `services/api/src/campus247/domain/retrieval.py`
- `tests/unit/retrieval/test_retrieval_types.py`

File report này được tạo riêng tại `docs/10-delivery/RAG_UPGRADE_EXECUTION_STATUS.md`.
Không thay migration hoặc DB trong lượt này; source head tiếp tục là `0011`.
Git HEAD snapshot: `c18e2d1741361e7852511a2200fb2595bc6e47b9`; working tree có
thay đổi chưa commit, vì vậy Git HEAD riêng lẻ không định danh toàn bộ artifact.
Đối chiếu baseline 45 file sau patch domain/tests: 43 file khác giữ nguyên;
không có thay đổi ngoài hai write paths của CONTEXT-001.

## Cập nhật quyết định legacy scope ngày 2026-10-03

Người dùng yêu cầu tiếp tục theo đề xuất tốt nhất sau câu hỏi cụ thể về legacy
NULL + fail closed. Đã ghi ngoại lệ này trong DOC-DATA-002 v1.2.0 trước mọi
implementation FILTER-001. Đây là approval riêng cho storage transition, không
phải approval model runtime, dependency mới, production hoặc destructive action.

Lượt chuẩn bị contract chỉ sửa DATA_DICTIONARY.md và report này. Baseline gồm
47 files: hai targets thay đổi, 45 files khác giữ nguyên; không tạo file mới.
Source migration chain vẫn 0011; mười hash lịch sử và hash manifest 0011 giữ
nguyên. Docker Engine preflight vẫn fail; chưa tạo/apply migration FILTER-001,
chưa sửa guard để chấp nhận source mới hoặc sửa expected head.

| AC cho bước chuẩn bị contract | Status | Evidence |
|---|---|---|
| Ngoại lệ được ghi riêng, version/header/approval trace rõ ràng | passed | DOC-DATA-002 v1.2.0, direct human instruction 2026-10-03 |
| Scope legacy chỉ được all-NULL; nguồn mới/reviewed bắt buộc đủ tuple | passed | Quy tắc contract; chưa phải DB constraint evidence |
| Legacy bị loại trước ranking/LIMIT; không backfill quyền | passed | Contract giữ fail-closed semantics và cấm default quyền |
| Migration apply, constraints và SQL leakage trên fixture thật | not_verified | B-DB-ENGINE; dừng trước migration mutation |
| Model inference và production retrieval quality | not_verified | B-MODEL-RUNTIME và các upstream gates |

| Command bước chuẩn bị contract | Exit code | Result |
|---|---:|---|
| Fixture Python: `python -B scripts/verify_dependencies.py` | 0 | Runtime/pins/closure/source/hash gate pass |
| `docker version --format '{{.Server.Version}}'` | 1 | Docker Desktop Linux Engine pipe vắng |
| Read-only YAML/header, contract clauses, relative links và source hash/ancestry inspection | 0 | Version 1.2.0 hợp lệ, links tồn tại, source head vẫn 0011 |
| Baseline hash/scope/untracked inspection | 0 | Chỉ hai documentation targets; 45 files khác giữ nguyên |
| `git diff --check`, `git diff --name-only`, `git status --short` | 0 | Không có whitespace/scope violation |

Không chạy lại suite 561 tests chỉ vì thay đổi documentation; kết quả ở phần
CONTEXT-001 dưới đây là evidence của lượt implementation trước. Không chạy DB
test hoặc coi live skip là pass khi engine chưa sẵn sàng.

## Verification CONTEXT-001

Probe trước patch xác minh constructor chấp nhận `dict` ở `authorized_scope`.
Patch thực thi typed contract có sẵn: scope phải là `AuthorizedScope`,
simulation policy là enum, timestamps timezone-aware, scope collections là
immutable frozenset và identifiers là tuple. Serialization không ép số thành
actor/locale, không chấp nhận roles dạng string hoặc field lạ. Lỗi malformed
serialization trả constant message, không echo input.

`from_dict` chỉ round-trip trusted context; nó không xác thực identity hoặc cấp
quyền cho claims của client. Production vẫn phải dùng trusted context factory.
Không thay role mapping, authorization policy, model, dimension, timeout,
threshold hoặc production wiring.

| AC | Status | Evidence |
|---|---|---|
| Context chứa tenant/campus, actor, roles, faculty/program, audience, locale, effective time, simulation policy và trace ID | passed | Existing context factory/types tests và serialization round-trip |
| Typed boundary reject arbitrary dict, malformed scalars/collections và missing/empty scope | passed | 45 regression cases bổ sung trong test_retrieval_types.py |
| Context/scope immutable và serialization giữ nguyên giá trị | passed | FrozenInstanceError, immutable collection và equality assertions |
| API/domain boundary và downstream unit regression | passed | 101 targeted; 561 broad tests; không external connection |
| End-to-end propagation qua lexical/vector/reranker/citation | not_verified | Thuộc CONTEXT-003; chưa gọi là hoàn tất wiring |
| Human catalog acceptance | not_verified | Không tự đặt ready/accepted |

| Command | Exit code | Result |
|---|---:|---|
| Fixture Python 3.12.14: `python -B scripts/verify_dependencies.py` | 0 | Exact pins, closure, sources, artifact hashes và candidate approval pass |
| `python -B -m pytest tests/unit/retrieval/test_retrieval_types.py tests/unit/retrieval/test_retrieval_context_factory.py tests/unit/retrieval/test_reranker_contract.py tests/architecture -q -p no:cacheprovider` | 0 | 101 passed |
| `python -B -m pytest tests/unit tests/architecture tests/evals tests/api/test_app_boot.py -q -p no:cacheprovider` | 0 | 561 passed; executed through runpy with outbound socket audit guard |
| `python -B -m pytest tests/integration/rag_fixture/test_guard.py tests/integration/test_embedding_index_manifest.py tests/integration/test_migration_0009.py -q -p no:cacheprovider` | 0 | 47 passed, 2 live cases skipped vì thiếu explicit fixture DSN; không dùng skip làm DB evidence |
| Baseline hash/scope inspection | 0 | Hai files mục tiêu thay đổi, 43 files khác không đổi |
| Audit inventory extraction lần đầu | 1 | Host cp1252 không encode Vietnamese output; chưa ghi file |
| Audit inventory extraction dùng JSON ASCII | 0 | Đủ 71 unique IDs; không sửa repo để xử lý encoding |
| Read-only fixture preflight/inspection | 1 | Docker API pipe vắng; dừng trước connection/mutation |
| `docker version --format '{{.Server.Version}}'` | 1 | `dockerDesktopLinuxEngine` pipe không tồn tại |
| `docker compose version` | 0 | Compose v5.5.0 có mặt; không chứng minh engine readiness |
| `git diff --check`, `git diff --name-only`, `git status --short`, untracked inspection | 0 | Hai source/test targets và report mới đúng scope; không sửa lease chat kia |

Suite rộng dùng Python 3.12.14 trong fixture venv. Outbound DNS/socket connection
bị chặn; chỉ cho phép socketpair IPC do chính stdlib event loop tạo. Fresh
basetemp nằm dưới venv workspace, retention_policy=all; giữ mọi artifacts,
không cleanup/reset dữ liệu có sẵn. Child fake import tests đã đọc source trước
và chỉ dùng deterministic test profile.

## Quyết định chuyển tiếp và blockers còn thiếu

### B-FILTER-LEGACY-NULL — quyết định contract đã ghi nhận

[DATA_DICTIONARY.md](../04-architecture/contracts/DATA_DICTIONARY.md) DATA-DIC-030
version 1.2.0 giữ yêu cầu NOT NULL cho nguồn mới/reviewed và ghi rõ ngoại lệ
tuple NULL cho legacy. §8 vẫn cấm tự đổi nullability ngoài ngoại lệ đã duyệt.
Legacy migration 0002 chưa có bốn field này; baseline fixture có một source.
Không có approved metadata mapping để điền scope. Không tự mặc định quyền
`FIT`/`STUDENT`/`ALL`, backfill metadata hoặc sửa source đang có.

Ngày 2026-10-03 người dùng chỉ dẫn “tiếp tục theo đề xuất tốt nhất, phù hợp nhất”.
Phương án legacy NULL + fail closed đã được ghi nhận trong approved contract:
chỉ source legacy chưa review được giữ cả bốn scope mới NULL; source mới/reviewed
phải đủ tuple hợp lệ, không cho phép partial NULL. Production SQL loại legacy
trước rank/LIMIT. Không tự backfill quyền hoặc đổi dữ liệu cũ; program_scope rỗng
vẫn không authorize program nào. Quyết định contract đã xử lý B-FILTER-LEGACY-NULL.
Implementation/migration apply vẫn not_verified và bị B-DB-ENGINE chặn trước
mutation; chưa tạo migration 0012, chưa sửa fixture guard hoặc expected head.

### B-MODEL-RUNTIME

ADR-005 chốt inference qua internal/private endpoint và exact artifact checksum.
Approved model vẫn là:

- `BAAI/bge-m3@5617a9f61b028005a4858fdac845db406aefb181`, dimension 1024, L2/cosine.
- `BAAI/bge-reranker-v2-m3@953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e`.

Private runtime location, API spec, artifact checksum và approved live environment
chưa được cung cấp ở lượt này. Không tự bịa wire protocol, tải weights, thêm
inference dependency hoặc coi deterministic fake là model thật.
Candidate approval 53 package/version không tự phê duyệt runtime/model packaging
mới, SCA/release hoặc paid provider.

### B-DB-ENGINE

Docker Desktop Linux Engine hiện không có pipe
`//./pipe/dockerDesktopLinuxEngine`. Compose CLI tồn tại, dependency verifier
pass; read-only fixture preflight dừng trước DB connection. Runtime/schema/health
hiện tại là not_verified, không suy ra resource đã bị xóa hoặc dữ liệu mất.
Baseline đã verified trước đó vẫn giữ nguyên tại:

- [verification-evidence.json](../../infra/local/rag-fixture/verification-evidence.json): 0010.
- [verification-0011-evidence.json](../../infra/local/rag-fixture/verification-0011-evidence.json): 0011,
  41 index/116 constraints lịch sử giữ nguyên, legacy vector 1536 và pointer rỗng.

Cần engine desktop-linux hoạt động trở lại rồi recheck receipt/ownership,
synthetic-only marker, DSN guard, current head, source hashes và fingerprints.
Không recreate/reset/drop/cleanup để làm verification pass.

## Inventory toàn bộ task

Status ở đây là trạng thái evidence của snapshot; candidate_verified không phải
human accepted. implementation_verified không đồng nghĩa production/release ready.
Chưa có dữ liệu đủ để kết luận mọi task còn lại completed.

| Task ID | Objective | Dependencies từ plan | Snapshot status | Evidence / blocker |
|---|---|---|---|---|
| `TASK-RAGUP-GOV-001` | Chốt production retrieval specification | không | source_approved | GOV-001 approval ngày 2026-09-29 trong ba approved docs; không sửa nguồn normative. |
| `TASK-RAGUP-DEPS-001` | Phê duyệt dependency và model allowlist | GOV-001, TASK-REPO-DEP-002 | partial_verified | Candidate 68 packages đã duyệt; verifier pass. SCA/release approval và model runtime packaging chưa xác minh. |
| `TASK-RAGUP-EMBED-001` | Canonical embedding contract | GOV-001 | candidate_verified | Implementation có sẵn; test liên quan pass trong suite 561. Chưa có acceptance record của task; giữ nguyên files có sẵn. |
| `TASK-RAGUP-EMBED-002` | Production embedding adapter | EMBED-001, DEPS-001 | blocked | B-MODEL-RUNTIME: private endpoint/API spec/revision/checksum chưa được cung cấp; dependency acceptance còn thiếu. |
| `TASK-RAGUP-EMBED-003` | Cô lập fake embedding vào test | EMBED-001 | owned_elsewhere | Fake isolation thuộc lease chat kia; test candidate nằm trong suite pass. Không sửa hoặc tự nghiệm thu task của chat kia. |
| `TASK-RAGUP-EMBED-004` | Embedding/index manifest | GOV-001 | implementation_verified | Migration/compatibility đã apply và verify trước đó tại 0011; evidence riêng. DB recheck hiện bị Docker engine chặn. |
| `TASK-RAGUP-EMBED-005` | Ingestion dùng embedding port | EMBED-002, EMBED-004 | blocked | Dependency upstream chưa accepted; path ingestion/vector/bootstrap giao với lease chat kia. |
| `TASK-RAGUP-EMBED-006` | Query embedding cùng active manifest | EMBED-002, EMBED-004 | blocked | Dependency upstream chưa accepted; path ingestion/vector/bootstrap giao với lease chat kia. |
| `TASK-RAGUP-EMBED-007` | Reindex song song và atomic activation | EMBED-005, EMBED-006 | blocked | Dependencies liệt kê chưa có acceptance/evidence đầy đủ; không triển khai downstream vượt DAG. |
| `TASK-RAGUP-CONTEXT-001` | Domain retrieval types | GOV-001 | implementation_verified | Typed scope, immutable collections, strict serialization đã sửa; 101 targeted và 561 broad tests pass. Chưa đặt catalog accepted. |
| `TASK-RAGUP-CONTEXT-002` | Trusted context factory | CONTEXT-001 | candidate_verified | Implementation có sẵn; test liên quan pass trong suite 561. Chưa có acceptance record của task; giữ nguyên files có sẵn. |
| `TASK-RAGUP-CONTEXT-003` | Propagate context xuyên pipeline | CONTEXT-002 | blocked | Dependencies liệt kê chưa có acceptance/evidence đầy đủ; không triển khai downstream vượt DAG. |
| `TASK-RAGUP-FILTER-001` | Storage fields và indexes | GOV-001 | blocked | Ngoại lệ legacy NULL đã duyệt trong DOC-DATA-002 v1.2.0; B-DB-ENGINE chặn preflight/create/apply migration thật. |
| `TASK-RAGUP-FILTER-002` | Authorized filter compiler | CONTEXT-002, FILTER-001 | blocked | Dependencies liệt kê chưa có acceptance/evidence đầy đủ; không triển khai downstream vượt DAG. |
| `TASK-RAGUP-FILTER-003` | Lexical filter trước rank/limit | FILTER-002 | blocked | Dependencies liệt kê chưa có acceptance/evidence đầy đủ; không triển khai downstream vượt DAG. |
| `TASK-RAGUP-FILTER-004` | Vector filter trước ANN limit | FILTER-002, EMBED-006 | blocked | Dependency upstream chưa accepted; path ingestion/vector/bootstrap giao với lease chat kia. |
| `TASK-RAGUP-FILTER-005` | Cross-branch leakage suite | FILTER-003, FILTER-004 | blocked | Dependencies liệt kê chưa có acceptance/evidence đầy đủ; không triển khai downstream vượt DAG. |
| `TASK-RAGUP-RETRIEVE-001` | Versioned retrieval profile | GOV-001 | candidate_verified | Implementation có sẵn; test liên quan pass trong suite 561. Chưa có acceptance record của task; giữ nguyên files có sẵn. |
| `TASK-RAGUP-RETRIEVE-002` | Canonical `HybridRetriever` | FILTER-003, FILTER-004, RETRIEVE-001 | blocked | Dependencies liệt kê chưa có acceptance/evidence đầy đủ; không triển khai downstream vượt DAG. |
| `TASK-RAGUP-RETRIEVE-003` | Exact identifier handling | RETRIEVE-002 | blocked | Dependencies liệt kê chưa có acceptance/evidence đầy đủ; không triển khai downstream vượt DAG. |
| `TASK-RAGUP-RETRIEVE-004` | Context assembler | RETRIEVE-002 | blocked | Dependencies liệt kê chưa có acceptance/evidence đầy đủ; không triển khai downstream vượt DAG. |
| `TASK-RAGUP-RETRIEVE-005` | Wire graph/bootstrap về canonical service | RETRIEVE-003, RETRIEVE-004 | blocked | Dependencies liệt kê chưa có acceptance/evidence đầy đủ; không triển khai downstream vượt DAG. |
| `TASK-RAGUP-RETRIEVE-006` | Failure/degradation policy | RETRIEVE-005 | blocked | Dependencies liệt kê chưa có acceptance/evidence đầy đủ; không triển khai downstream vượt DAG. |
| `TASK-RAGUP-RERANK-001` | Reranker port và validator | CONTEXT-001 | candidate_verified | Implementation có sẵn; test liên quan pass trong suite 561. Chưa có acceptance record của task; giữ nguyên files có sẵn. |
| `TASK-RAGUP-RERANK-002` | Approved reranker adapter | RERANK-001, DEPS-001 | blocked | B-MODEL-RUNTIME: private endpoint/API spec/revision/checksum chưa được cung cấp; dependency acceptance còn thiếu. |
| `TASK-RAGUP-RERANK-003` | Rerank top-20 thành top-8 | RETRIEVE-002, RERANK-002 | blocked | Dependencies liệt kê chưa có acceptance/evidence đầy đủ; không triển khai downstream vượt DAG. |
| `TASK-RAGUP-RERANK-004` | Reranker ablation/quality suite | RERANK-003 | blocked | Dependencies liệt kê chưa có acceptance/evidence đầy đủ; không triển khai downstream vượt DAG. |
| `TASK-RAGUP-EVID-001` | Structured grounded-answer parser | RETRIEVE-004, TASK-AGENT-EVIDENCE-002 | blocked | Dependencies liệt kê chưa có acceptance/evidence đầy đủ; không triển khai downstream vượt DAG. |
| `TASK-RAGUP-EVID-002` | Wire graph vào canonical evidence gate | EVID-001, TASK-AGENT-EVIDENCE-002 | blocked | Dependencies liệt kê chưa có acceptance/evidence đầy đủ; không triển khai downstream vượt DAG. |
| `TASK-RAGUP-EVID-003` | Bounded evidence repair | EVID-002 | blocked | Dependencies liệt kê chưa có acceptance/evidence đầy đủ; không triển khai downstream vượt DAG. |
| `TASK-RAGUP-EVID-004` | Adversarial evidence integration | EVID-003, TASK-AGENT-INJECT-001, TASK-AGENT-STREAM-001 | blocked | Dependencies liệt kê chưa có acceptance/evidence đầy đủ; không triển khai downstream vượt DAG. |
| `TASK-RAGUP-CITE-001` | Complete candidate provenance | FILTER-005, EMBED-004 | blocked | Dependencies liệt kê chưa có acceptance/evidence đầy đủ; không triển khai downstream vượt DAG. |
| `TASK-RAGUP-CITE-002` | Server-side citation resolver | CITE-001 | blocked | Dependencies liệt kê chưa có acceptance/evidence đầy đủ; không triển khai downstream vượt DAG. |
| `TASK-RAGUP-CITE-003` | Public API citation contract | CITE-002 | blocked | Dependencies liệt kê chưa có acceptance/evidence đầy đủ; không triển khai downstream vượt DAG. |
| `TASK-RAGUP-CITE-004` | Verified citation UI states | CITE-003, citation UI task hiện có | blocked | Dependencies liệt kê chưa có acceptance/evidence đầy đủ; không triển khai downstream vượt DAG. |
| `TASK-RAGUP-EVAL-001` | Gold dataset schema và validator | GOV-001 | candidate_verified | Implementation có sẵn; test liên quan pass trong suite 561. Chưa có acceptance record của task; giữ nguyên files có sẵn. |
| `TASK-RAGUP-DATA-001` | Gold data shards | EVAL-001 | blocked | EVAL-001 chưa accepted; trusted corpus/index và reviewer evidence chưa đủ. Không tự tạo 500 gold cases giả hoặc đọc sealed test. |
| `TASK-RAGUP-DATA-002` | Gold data shards | EVAL-001 | blocked | EVAL-001 chưa accepted; trusted corpus/index và reviewer evidence chưa đủ. Không tự tạo 500 gold cases giả hoặc đọc sealed test. |
| `TASK-RAGUP-DATA-003` | Gold data shards | EVAL-001 | blocked | EVAL-001 chưa accepted; trusted corpus/index và reviewer evidence chưa đủ. Không tự tạo 500 gold cases giả hoặc đọc sealed test. |
| `TASK-RAGUP-DATA-004` | Gold data shards | EVAL-001 | blocked | EVAL-001 chưa accepted; trusted corpus/index và reviewer evidence chưa đủ. Không tự tạo 500 gold cases giả hoặc đọc sealed test. |
| `TASK-RAGUP-DATA-005` | Gold data shards | EVAL-001 | blocked | EVAL-001 chưa accepted; trusted corpus/index và reviewer evidence chưa đủ. Không tự tạo 500 gold cases giả hoặc đọc sealed test. |
| `TASK-RAGUP-DATA-006` | Gold data shards | EVAL-001 | blocked | EVAL-001 chưa accepted; trusted corpus/index và reviewer evidence chưa đủ. Không tự tạo 500 gold cases giả hoặc đọc sealed test. |
| `TASK-RAGUP-DATA-007` | Gold data shards | EVAL-001 | blocked | EVAL-001 chưa accepted; trusted corpus/index và reviewer evidence chưa đủ. Không tự tạo 500 gold cases giả hoặc đọc sealed test. |
| `TASK-RAGUP-DATA-008` | Gold data shards | EVAL-001 | blocked | EVAL-001 chưa accepted; trusted corpus/index và reviewer evidence chưa đủ. Không tự tạo 500 gold cases giả hoặc đọc sealed test. |
| `TASK-RAGUP-DATA-009` | Gold data shards | EVAL-001 | blocked | EVAL-001 chưa accepted; trusted corpus/index và reviewer evidence chưa đủ. Không tự tạo 500 gold cases giả hoặc đọc sealed test. |
| `TASK-RAGUP-DATA-010` | Gold data shards | EVAL-001 | blocked | EVAL-001 chưa accepted; trusted corpus/index và reviewer evidence chưa đủ. Không tự tạo 500 gold cases giả hoặc đọc sealed test. |
| `TASK-RAGUP-DATA-011` | Gold data shards | EVAL-001 | blocked | EVAL-001 chưa accepted; trusted corpus/index và reviewer evidence chưa đủ. Không tự tạo 500 gold cases giả hoặc đọc sealed test. |
| `TASK-RAGUP-DATA-012` | Gold data shards | EVAL-001 | blocked | EVAL-001 chưa accepted; trusted corpus/index và reviewer evidence chưa đủ. Không tự tạo 500 gold cases giả hoặc đọc sealed test. |
| `TASK-RAGUP-DATA-013` | Gold data shards | EVAL-001 | blocked | EVAL-001 chưa accepted; trusted corpus/index và reviewer evidence chưa đủ. Không tự tạo 500 gold cases giả hoặc đọc sealed test. |
| `TASK-RAGUP-DATA-014` | Gold data shards | EVAL-001 | blocked | EVAL-001 chưa accepted; trusted corpus/index và reviewer evidence chưa đủ. Không tự tạo 500 gold cases giả hoặc đọc sealed test. |
| `TASK-RAGUP-DATA-015` | Gold data shards | EVAL-001 | blocked | EVAL-001 chưa accepted; trusted corpus/index và reviewer evidence chưa đủ. Không tự tạo 500 gold cases giả hoặc đọc sealed test. |
| `TASK-RAGUP-DATA-016` | Gold data shards | EVAL-001 | blocked | EVAL-001 chưa accepted; trusted corpus/index và reviewer evidence chưa đủ. Không tự tạo 500 gold cases giả hoặc đọc sealed test. |
| `TASK-RAGUP-DATA-017` | Gold data shards | EVAL-001 | blocked | EVAL-001 chưa accepted; trusted corpus/index và reviewer evidence chưa đủ. Không tự tạo 500 gold cases giả hoặc đọc sealed test. |
| `TASK-RAGUP-DATA-018` | Gold data shards | EVAL-001 | blocked | EVAL-001 chưa accepted; trusted corpus/index và reviewer evidence chưa đủ. Không tự tạo 500 gold cases giả hoặc đọc sealed test. |
| `TASK-RAGUP-DATA-019` | Gold data shards | EVAL-001 | blocked | EVAL-001 chưa accepted; trusted corpus/index và reviewer evidence chưa đủ. Không tự tạo 500 gold cases giả hoặc đọc sealed test. |
| `TASK-RAGUP-DATA-020` | Gold data shards | EVAL-001 | blocked | EVAL-001 chưa accepted; trusted corpus/index và reviewer evidence chưa đủ. Không tự tạo 500 gold cases giả hoặc đọc sealed test. |
| `TASK-RAGUP-EVAL-002` | PostgreSQL/pgvector evaluation runner | RETRIEVE-005, EVAL-001 | blocked | Dependencies liệt kê chưa có acceptance/evidence đầy đủ; không triển khai downstream vượt DAG. |
| `TASK-RAGUP-EVAL-003` | Retrieval/grounding metrics | EVAL-002 | blocked | Dependencies liệt kê chưa có acceptance/evidence đầy đủ; không triển khai downstream vượt DAG. |
| `TASK-RAGUP-EVAL-004` | Controlled ablation | EVAL-003, RERANK-004 | blocked | Dependencies liệt kê chưa có acceptance/evidence đầy đủ; không triển khai downstream vượt DAG. |
| `TASK-RAGUP-EVAL-005` | Approved live-model evaluation | EVAL-004, toàn bộ data shards | blocked | Ablation, đủ 20 data shards và approved live environment/cost chưa có evidence. |
| `TASK-RAGUP-EVAL-006` | Production quality gate | EVAL-005 | blocked | Dependencies liệt kê chưa có acceptance/evidence đầy đủ; không triển khai downstream vượt DAG. |
| `TASK-RAGUP-EVAL-007` | CI/release integration | EVAL-006, TASK-EVAL-GATE-001, TASK-OPS-RELEASE-002 | blocked | Dependencies liệt kê chưa có acceptance/evidence đầy đủ; không triển khai downstream vượt DAG. |
| `TASK-RAGUP-OPS-001` | Retrieval observability schema | RETRIEVE-001 | blocked | Dependencies liệt kê chưa có acceptance/evidence đầy đủ; không triển khai downstream vượt DAG. |
| `TASK-RAGUP-OPS-002` | Privacy-safe trace writer | OPS-001, trace task hiện có | blocked | Dependencies liệt kê chưa có acceptance/evidence đầy đủ; không triển khai downstream vượt DAG. |
| `TASK-RAGUP-CACHE-001` | Scope-safe cache key | CONTEXT-002, RETRIEVE-005 | blocked | Dependencies liệt kê chưa có acceptance/evidence đầy đủ; không triển khai downstream vượt DAG. |
| `TASK-RAGUP-CACHE-002` | Invalidation | CACHE-001, EMBED-007 | blocked | Dependencies liệt kê chưa có acceptance/evidence đầy đủ; không triển khai downstream vượt DAG. |
| `TASK-RAGUP-PERF-001` | Real retrieval benchmark | EVAL-002, RERANK-003 | blocked | Dependencies liệt kê chưa có acceptance/evidence đầy đủ; không triển khai downstream vượt DAG. |
| `TASK-RAGUP-PERF-002` | HNSW tuning experiment | PERF-001 | blocked | Dependencies liệt kê chưa có acceptance/evidence đầy đủ; không triển khai downstream vượt DAG. |
| `TASK-RAGUP-PERF-003` | Pool saturation và degradation test | PERF-001 | blocked | Dependencies liệt kê chưa có acceptance/evidence đầy đủ; không triển khai downstream vượt DAG. |
| `TASK-RAGUP-PERF-004` | Infrastructure decision gate | PERF-002, PERF-003 | blocked | Benchmark/tuning upstream chưa có; chưa có cơ sở quyết định kiến trúc. |
| `TASK-RAGUP-RELEASE-001` | Final promotion gate | toàn bộ task bắt buộc ở nhóm 0–9 | blocked | Toàn bộ upstream/eval/benchmark chưa verified và accepted; chưa có promotion approval riêng. |

Tổng: source_approved=1; partial_verified=1; candidate_verified=5; blocked=61; owned_elsewhere=1; implementation_verified=2.

## Thứ tự tiếp tục

1. Giữ nguyên lease của chat kia; nhận acceptance/handoff evidence của những task
   upstream họ sở hữu trước mọi downstream wiring.
2. Quyết định B-FILTER-LEGACY-NULL đã ghi nhận; giải quyết B-DB-ENGINE và reverify
   đúng fixture trước khi tạo/apply FILTER-001.
3. Cung cấp approved private runtime/spec/checksums để unblock embedding/reranker
   adapters; các live calls cần phạm vi môi trường rõ ràng.
4. Sau mỗi micro-task: verify AC, ghi command/exit/evidence và chờ accepted
   dependency trước task kế tiếp; không tự mark catalog accepted.
5. Chỉ làm data/eval/benchmark và promotion khi toàn bộ upstream cùng artifact
   tuple đã verified; gold reviewer, sealed split, SCA/cost/release approval
   vẫn là gate thật. Không sửa threshold/expected result để pass.

