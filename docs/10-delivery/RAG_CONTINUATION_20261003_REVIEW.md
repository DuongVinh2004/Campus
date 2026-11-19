# Campus 24/7 — continuation preflight và acceptance review

Ngày 2026-10-03, Asia/Bangkok. Đây là evidence mới, không normative và không
tự đặt task ready/accepted. Objective của lượt này: kiểm chứng lại runtime,
fixture và acceptance DAG trước khi chọn objective implementation tiếp theo.

## Kết quả hiện tại

**Preflight/fixture/regression verified; triển khai downstream blocked bởi
acceptance và quyết định phạm vi AC.** Không triển khai FILTER-002/003 khi gate
chưa được reviewer giải quyết. Không sửa candidate, lease, dependency, contract,
migration hoặc catalog có sẵn. Git HEAD vẫn là
`c18e2d1741361e7852511a2200fb2595bc6e47b9`; working tree dirty được định danh
bằng manifest bytes riêng, không dùng HEAD để đại diện toàn bộ artifacts.

| AC của objective kiểm chứng | Status | Evidence hiện tại |
|---|---|---|
| Canonical workspace, reparse/junction checks và snapshot trực tiếp | passed | baseline 1.166 files; exclusive-create, không truyền manifest qua stdout |
| Reconcile manifest cuối của lượt trước | passed | 1.164 hashes đều khớp; hai files mới là report FILTER-001 và chính manifest cuối |
| Runtime/dependency chính xác | passed | Python 3.12.14; 66 installed packages khớp reviewed lock; exclusions uvloop/httpx2-jsfetch |
| Dependency verifier/catalog | passed | Hai commands exit 0; VALID tasks=241, phases=10 |
| Docker ownership/image/binding/mount/network/health | passed | desktop-linux; Engine 29.7.2; exact image ID, receipt/labels và hai mounts khớp |
| Independent read-only fixture trước/sau live regression | passed | Head 0012; 1 source/1 document/3 chunks; vector(1536); schema 329/51/169; pointer 0 |
| Rows/index fingerprints bảo toàn | passed | Cả hai read-only snapshots khớp retained evidence 0012 |
| Deterministic regression, network blocked và artifacts retained | passed | Offline-retained: 561 passed, không skip; socket/DNS + Python -c child guard; deletion denied |
| Live synthetic regression | passed | 51 passed, không skip; scope migration/guard/history/manifest tests; probes rollback |
| Source preservation của lượt này | passed | Đối chiếu toàn bộ 1.166 pre-existing files không đổi sau tests |
| Full initial hashes của lượt FILTER-001 trước | not_verified | Không thể phục hồi entries mất từ transport snapshot cũ; không che bằng baseline mới |
| Production filtering/model inference/quality/acceptance | not_verified | Implementation/upstream/reviewer/runtime gates dưới đây |

Manifest bao phủ toàn bộ git cached và nonignored untracked files tại preflight,
không bao phủ bytes của ignored venv/cache/test artifacts hoặc credential receipt.
Không claim preservation hash của toàn bộ 67.067 ignored paths. Mọi test temp
được bổ sung ở lượt giữ-artifact dùng tên mới trong workspace; không cleanup
paths có sẵn. Receipt và DSN chỉ đi qua guard trong memory, không ghi evidence.

Read-only transactions kiểm tra marker `rag-synthetic-v1`, current database/user/
schema, reviewed source chain và synthetic seed. Không resume/recreate container,
upgrade migration hoặc activate index trong lượt này. Historical migration
hashes và reviewed 0011/0012 được guard và integration tests đối chiếu lại.

Fingerprint rows:
`00a182aedfa2abaa918c64404673621dda9e15199cb1aa920812828e81dbc0c2`.
Fingerprint indexes:
`aa812b4615ba831bf8ce8956ddda436068e01a6f12bd291b37244b4a7ddc7304`.

## Artifacts và commands tái lập

Runner mới: [continuation_audit.py](../../infra/local/rag-fixture/continuation_audit.py).
Mọi Python command dùng `infra/local/rag-fixture/.venv/Scripts/python.exe -B`.
Runner không overwrite evidence; mỗi run mới phải có mode/output/temp name mới.

| Command, theo thứ tự | Exit | Evidence |
|---|---:|---|
| scripts/verify_dependencies.py | 0 | Exact pins/closure/sources/hashes; command được ghi lại trong dag-review JSON |
| tasks/tools/validate_catalog.py | 0 | VALID tasks=241 phases=10; command được ghi lại trong dag-review JSON |
| fixture.py preflight trong sandbox | 1 | External command access failure, chưa DB mutation |
| docker context show/version và fixture.py preflight ngoài sandbox | 0 | desktop-linux, 29.7.2, dependency/runtime/Docker passed |
| continuation_audit.py before | 0 | Independent read-only snapshot và installed inventory |
| continuation_audit.py offline | 0 | 561 passed; retention limitation bên dưới |
| continuation_audit.py live | 0 | 51 passed, no skips; exact fixture endpoint và ownership guard |
| continuation_audit.py after | 0 | Independent read-only snapshot sau live probes, fingerprints không đổi |
| continuation_audit.py offline-retained | 0 | 561 passed, no skips; retained stdlib temps và network-guarded Python children |
| Source/DAG audit, verifier/catalog rerun | 0 | 71 IDs; không có RAGUP catalog YAML/output acceptance; 1.166 source hashes preserved |

Các pytest runs dùng `-q -p no:cacheprovider`, fresh `--basetemp` trong fixture
venv workspace và `-o tmp_path_retention_policy=all`. Live connect chỉ tới
127.0.0.1:15433; deterministic runs chỉ cho stdlib socketpair IPC. Không dùng
DATABASE_URL, .env hoặc live model provider. Python subprocess import tests đã
được đọc; lượt offline-retained thêm socket/DNS guard vào chính child interpreter.

**Giới hạn evidence lần offline đầu:** bốn test cũ dùng TemporaryDirectory với
cleanup mặc định, ngoài cơ chế retention của pytest. Lần đầu đạt tests nhưng
không chứng minh giữ toàn bộ artifacts; default cleanup có thể đã loại các temp
do chính tests tạo. Giữ nguyên evidence đó. Runner được sửa trong đúng file mới
để cấp stdlib temp trong workspace với delete=False và chặn os.remove/rmdir/
shutil.rmtree. Lần offline-retained đạt lại toàn suite. Không tìm/xóa temp cũ,
không sửa tests hoặc giả lập recovery artifacts đã mất. Đây là correction của
test harness; không phải thay expected result hoặc production behavior.

Evidence mới trong `infra/local/rag-fixture/`:

- `continuation-20261003-baseline.json`: source hashes/status và prior coverage.
- `continuation-20261003-before.json`, `continuation-20261003-after.json`:
  runtime/inventory và read-only fixture evidence.
- `continuation-20261003-offline.json`: retained initial-run evidence/limitation.
- `continuation-20261003-offline-retained.json`: final deterministic test evidence.
- `continuation-20261003-live.json`: live PostgreSQL regression.
- `continuation-20261003-dag-review.json`: 71 nodes, acceptance discovery và commands.
- `continuation-20261003-final-scope.json`: final source scope/hashes và diff checks;
  self-hash excluded, sẽ được đối chiếu ở objective tiếp theo.

## Hồ sơ cụ thể để reviewer quyết định

Broad suite đã chạy các tests liệt kê; pass được dùng cho contract evidence,
không chuyển thành inference, end-to-end wiring hoặc production quality.

| Task | Artifact review | AC/evidence đủ review | Gate còn lại |
|---|---|---|---|
| CONTEXT-001 | domain/retrieval.py; test_retrieval_types.py | Context/scope immutable, đủ tenant/campus/actor/roles/faculty/program/audience/locale/effective/simulation/trace; strict serialization round-trip/negative cases | Human acceptance; propagation thuộc CONTEXT-003 |
| CONTEXT-002 | application/retrieval/context.py; test_retrieval_context_factory.py | Trusted identity/resolver; spoofing/tenant crossing/missing/inactive/expired identity rejected; server clock và audit-safe trace tests | CONTEXT-001 acceptance và human acceptance |
| RERANK-001 | ports/reranker.py; application/retrieval/rerank.py; test_reranker_contract.py | Typed immutable request, limits, foreign/duplicate IDs, finite scores, model/revision/latency rejection | CONTEXT-001 acceptance và human acceptance; approved adapter thuộc RERANK-002 |
| EVAL-001 | evals/schemas/rag-gold.schema.yaml; evals/runners/rag_gold.py; test_rag_gold.py | Duplicate/paraphrase/split/context/version/citation validator positive/negative cases | Human acceptance; trusted corpus/index/gold reviewers vẫn chưa đủ cho data shards |
| EMBED-001 | shared embedding port và test_embedding_contract.py | API/worker import và typed model/dimension/input/batch contract tests pass | Candidate acceptance; adapter/private runtime chưa có |
| EMBED-004 | domain/embedding_index.py; migration 0011; test_embedding_index_manifest.py | Synthetic compatibility/manifest constraints/document-profile trace/pointer rollback verified tại 0012 | Candidate acceptance; không có real inference hoặc active production manifest |
| FILTER-001 | migration 0012; test_retrieval_scope_migration.py; RAG_FILTER_001_EXECUTION.md | Storage/apply/schema/data/vector/index preservation; fail-closed SQL probes; index eligibility | AC scope ambiguity; production SQL chưa wired, historical initial hash gap còn nguyên |
| RETRIEVE-001 | application/retrieval/profile.py; test_retrieval_profile.py | Exact immutable rag-prod-v1.0.0 và runtime-binding mismatch tests pass | Production magic constants/wiring chưa fully replaced; không đề nghị accept toàn task |

### B-UPSTREAM-ACCEPTANCE

[DOCUMENT_CONTROL.md](../00-governance/DOCUMENT_CONTROL.md) quy định “Only the
orchestrator or a human reviewer may set ready or accepted” và dependency chưa
accepted là stop condition. [DEC-019](../00-governance/DECISION_REGISTER.md) yêu
cầu mọi dependency accepted trước khi bắt đầu task. Discovery không thấy RAGUP
catalog YAML/output hoặc acceptance record mới cho các candidates. Backlog
approval vẫn có hiệu lực; nó không tự là implementation acceptance.

Quyết định cần: reviewer ghi rõ accepted hoặc yêu cầu sửa cho CONTEXT-001,
CONTEXT-002, RERANK-001 và EVAL-001 theo artifacts/AC ở bảng trên. Không tự cập
nhật DOCUMENT_CONTROL, catalog, requirement hoặc acceptance binding.

### B-FILTER001-AC-SCOPE

Plan §9 đặt FILTER-001 AC: “metadata uncertainty loại source khỏi production
retrieval”; cùng §9 đặt FILTER-002 phụ thuộc FILTER-001 và FILTER-003/004 mới
wire predicate. Storage/probes đã đạt, nhưng query production hiện chưa có đủ
filter. Nếu hiểu AC là runtime wiring, chưa thể accept FILTER-001 để mở task
compiler tiếp theo. Không tự coi SQL probes là production filtering.

Giải pháp nhỏ nhất đề nghị reviewer: xác nhận storage/schema/probe milestone
của FILTER-001 đủ làm dependency gate cho FILTER-002; giữ production-filter AC
để nghiệm thu tại FILTER-003/004/005 và giữ toàn upgrade chưa completed. Đây là
**đề nghị quyết định phạm vi**, chưa được áp dụng, không phải tự accept task
hoặc tự đổi contract. Nếu reviewer không xác nhận, FILTER-002 tiếp tục blocked.

### B-MODEL-RUNTIME và B-OWNERSHIP-HANDOFF

Approved repository artifacts chưa cung cấp đủ bundle cho hai exact BGE
revisions trong ADR-005: private endpoint locations; request/response/auth
specification (không cần credential); artifact SHA-256; approved live environment/
test scope; runtime packaging decision nếu cần thêm runtime. Không dùng fake
hoặc tự invent protocol để triển khai EMBED-002/RERANK-002.

Lease vector.py, embed_fake.py, run_ingestion.py và wiring bootstrap/settings
vẫn được giữ. Hashes của chúng và mọi candidate có sẵn khớp baseline mới.
Không suy ra handoff từ file tồn tại hoặc tests pass; không tạo/gửi message chat
khác, không spawn subagent. CONTEXT-003/EMBED-005/006 tiếp tục chờ lease rõ ràng.

## Bước tiếp theo sau quyết định

Nếu acceptance context và FILTER-001 milestone gate được reviewer xác nhận,
triển khai đúng một objective FILTER-002 ở compiler/predicate tests có write
scope mới, không giao lease. Sau verification và acceptance riêng mới chọn
FILTER-003. Nếu chưa có quyết định, trạng thái implementation là blocked; mọi
real model/index/eval/cache/benchmark/release gates giữ nguyên.
