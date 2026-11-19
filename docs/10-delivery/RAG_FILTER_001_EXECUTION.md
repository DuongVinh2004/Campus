# RAG upgrade — FILTER-001 và upstream acceptance audit

Ngày 2026-10-03, Asia/Bangkok. Report là evidence, không thay contract hoặc
human acceptance. Git HEAD `c18e2d1741361e7852511a2200fb2595bc6e47b9` không
định danh toàn bộ working tree đang dirty. Backlog được người dùng duyệt trực
tiếp; catalog hiện có 241 tasks hợp lệ, chưa materialize TASK-RAGUP YAML.

## Objective 1 — dependency/runtime và fixture 0011

**Kết quả: verified hiện tại.** Python 3.12.14 trong fixture venv; 66 installed
packages khớp exact reviewed lock. Hai platform exclusions là uvloop và
httpx2-jsfetch. Candidate SHA-256 và 53 additions vẫn đúng approval đã giao.
Không thay package/runtime/lock/verifier hoặc cài dependency.

Docker context desktop-linux, Engine 29.7.2. Preflight trong sandbox bị chặn
truy cập Docker; cùng preflight ngoài sandbox pass. Receipt, owner labels,
container/volume/network, binding 127.0.0.1:15433, image ID và hai mounts khớp.
Container có sẵn được resume; không recreate. Image đã kiểm chứng:
`sha256:ccc6e83d6e35e931dc7c5def2022729d5a6c370318d099181995567ff1fb4d6b`.
DSN được derive trong memory qua guard; không log credential/DSN.

Head 0011, synthetic marker, provenance, 1 source/1 document/3 chunks,
vector(1536), nearest-neighbor và dimension rejection được reverify. Row/index
fingerprints khớp hoàn toàn verification-0011-evidence.json trước migration.
Đọc toàn bộ schema trước DDL: 324 columns, 46 indexes, 167 constraints.

## Objective 2 — TASK-RAGUP-FILTER-001

**Kết quả: storage và migration apply verified; toàn task chưa completed/accepted.**
Dependency GOV-001 có approval trực tiếp trong ADR-005/RAG_PIPELINE/DATA_DICTIONARY;
ngoại lệ legacy scope áp dụng DATA_DICTIONARY v1.2.0. Production SQL wiring vẫn
thuộc FILTER-002/003/004 và chưa verified. Full initial source hash audit cũng
chưa verified vì transport snapshot bị cắt, như phần scope dưới đây.

Migration additive 0012, descendant 0011, đã commit trên đúng fixture được
guard. Migration 0001..0011 giữ nguyên bytes. Source SHA-256 0012:
`b13ece1987ae63fcbf0481fe54144902dc89bbda7881a8cbc6afd81077595e1d`.

Thêm campus_scope, faculty_scope, program_scope, audiences và
applicability_reviewed_at; không default/backfill quyền. CHECK kiểm tra tuple
all-NULL hoặc toàn bộ hợp lệ; trigger giới hạn all-NULL ở legacy chưa review,
chặn INSERT mới thiếu scope, reviewed-to-NULL và clone legacy qua đổi PK.
Faculty V1 FIT và bốn role DEC-006 được kiểm tra; không invent thêm cohort.
Program rỗng hợp lệ ở storage nhưng không authorize program trong SQL.
Thêm effective-range CHECK, một state index, ba GIN scope indexes và một
document effective index. Không thay lifecycle, constraint lịch sử, vector
dimension hoặc active pointer. Downgrade chỉ báo forward-only.

| Acceptance | Status | Evidence |
|---|---|---|
| Legacy không backfill, giữ tuple all-NULL và toàn bộ giá trị cũ | passed | So sánh từng hàng/cột/vector với filter-001-baseline.json |
| INSERT mới thiếu tuple, partial NULL, sai campus/faculty/audience, null array elements bị chặn | passed | PostgreSQL CHECK/trigger negative probes |
| Legacy non-scope update được phép; reviewed scope không revert NULL | passed | Savepoint probes; tất cả rollback |
| Empty program không allow-all; unknown scope excluded trước LIMIT | passed, SQL probe | Empty intersection và isolated unknown-scope probe với dates hợp lệ |
| Temporal/applicability/state/simulation predicates | passed, SQL probe | Positive control 3 chunks; wrong/empty scope, date boundaries, missing applicability, DRAFT/SUPERSEDED/ARCHIVED và simulation=false trả 0 |
| Historical schema/data/index/constraints preserved | passed | 324 columns, 46 indexes, 167 constraints giữ nguyên; 5 columns, 5 indexes, 2 constraints mới |
| Index phù hợp predicate | passed, eligibility only | EXPLAIN cho cả 5 indexes với SET LOCAL enable_seqscan=off; không phải performance benchmark |
| Manifest/model/revision/dimension/profile/index mismatch rejection và pointer rollback | passed, synthetic compatibility | EMBED-004 live regression tại head 0012; pointer rỗng sau rollback |
| Production lexical/vector SQL dùng các predicates | not_verified | Chưa nối FILTER-002/003/004; hiện lexical vẫn chỉ lọc PUBLISHED |
| WITHDRAWN lifecycle implementation | not_verified | Không đổi historical status CHECK; cần lifecycle contract rõ ràng ở task liên quan |
| Complete initial working-tree hash preservation | not_verified | Snapshot tool transport bị cắt; không suy diễn phần mất |
| Human acceptance / model inference / production quality | not_verified | Không tự accept task; chưa có private model runtime hoặc real evaluation |

Từng probe UPDATE/INSERT synthetic rollback trong savepoint. Schema upgrade
commit, sau đó connection read-only độc lập xác minh head 0012 và dữ liệu cũ.
Seed regression là no-op và fingerprint không đổi. Final DB có 329 columns,
51 indexes, 169 constraints; không có active manifest được tự activate.

## Files và ownership

Existing files sửa bằng scoped patch:

- infra/local/rag-fixture/fixture.py: thêm đúng reviewed source/hash 0012;
  unknown-source/hash-drift và existing-data implicit-upgrade gates giữ nguyên.
- tests/integration/rag_fixture/test_guard.py: explicit descendant 0012.
- tests/integration/test_migration_0009.py: giữ toàn ancestry 0001..0010,
  kiểm tra 0011/0012 descendants kèm live preservation evidence.
- tests/integration/test_embedding_index_manifest.py: chạy compatibility ở head
  mới; projection lịch sử có evidence FILTER-001 độc lập kiểm tra mọi field mới.

New files:

- services/api/migrations/versions/0012_retrieval_scope.py
- tests/integration/test_retrieval_scope_migration.py
- infra/local/rag-fixture/filter-001-baseline.json
- infra/local/rag-fixture/filter-001-scope-baseline.json
- infra/local/rag-fixture/filter-001-final-scope.json
- infra/local/rag-fixture/verification-0012-evidence.json
- docs/10-delivery/RAG_FILTER_001_EXECUTION.md

Lease chat song song vẫn giữ nguyên. Không có source-write call đến vector.py,
embed_fake.py, run_ingestion.py, bootstrap/settings hoặc các candidate contracts.
Không spawn subagent, tạo chat hoặc gửi message; không suy ra handoff.
Baseline 0010 và evidence 0011 giữ nguyên; evidence 0012 là artifact mới.
Không sửa docs normative, dependency, shared fixtures hoặc task acceptance.

Snapshot toàn repo truyền qua tool bị truncation và tạo một invalid path entry.
Giữ bản snapshot này như evidence sự cố; **không dùng làm baseline đầy đủ**.
593 entries hợp lệ có thể đối chiếu: 590 không đổi và ba integration test paths
thay đổi đúng scope. Initial hashes của fixture.py và lease files không có trong
phần payload còn lại, nên hash-based preservation cho chúng là not_verified.
Tool mutation provenance giới hạn đúng các paths liệt kê trên. Full final
manifest 1,164 files được ghi trực tiếp bằng exclusive-create để tránh transport
truncation; có thể dùng làm baseline cho objective tiếp theo. Basetemp mới trong
workspace, retention_policy=all; artifacts giữ nguyên, không cleanup.

## Commands và exit codes

Mọi command Python dùng infra/local/rag-fixture/.venv/Scripts/python.exe -B.
Pytest dùng -p no:cacheprovider, fresh --basetemp trong fixture venv workspace
và -o tmp_path_retention_policy=all. Không dùng global Python 3.14 để nghiệm thu.

| Command, theo thứ tự | Exit | Evidence |
|---|---:|---|
| scripts/verify_dependencies.py | 0 | exact pins/closure/registry/artifact hashes/candidate approval |
| fixture.py preflight trong sandbox | 1 | external command access failure; chưa DB mutation |
| docker context show; docker version --format và fixture preflight ngoài sandbox | 0 | desktop-linux, 29.7.2, runtime/dependency pass |
| owned-resource inspect và exact container resume | 0 | receipt/labels/image/port/mount/network match; existing volume giữ nguyên |
| Guarded read-only verify tại 0011 và schema snapshot | 0 | retained 0011 fingerprints match; 46 indexes/167 constraints |
| Installed package/runtime inventory | 0 | 3.12.14; 66 exact versions, 2 platform exclusions |
| tasks/tools/validate_catalog.py | 0 | VALID tasks=241, phases=10 |
| fixture.chain() khi 0012 còn unreviewed | 1, expected | stopped before DB mutation |
| Targeted offline pytest, live cases deselected | 0 | 48 passed, 3 deselected; không tính là live readiness |
| pytest tests/integration/test_retrieval_scope_migration.py -q -s | 0 | 2 passed, no skips; additive apply và postcommit preservation |
| pytest tests/unit tests/architecture tests/evals tests/api/test_app_boot.py -q | 0 | 561 passed, no skips |
| pytest scope migration + fixture guard + migration 0009 history + embedding manifest | 0 | 51 passed, no skips; compatibility, seed no-op, preservation |
| Same targeted suite sau isolated positive/negative predicate probes | 0 | Final predicate version passed; source không đổi sau đó |
| Final independent read-only verify/preserve | 0 | head 0012, row/index hashes khớp verification-0012-evidence.json |
| Initial full scope hash check | 1 | payload truncation phát hiện; không claim pass |
| Partial scope comparison và exclusive final manifest | 0 | 593 valid initial entries; 590 comparable files preserved |
| git diff --check, diff/name/status, source hash audit; dependency verifier lần cuối | 0 | whitespace pass; 0001..0011 bytes unchanged; dependency unchanged |

Deterministic pytest chạy với Python socket/DNS audit hook deny outbound;
chỉ cho stdlib socketpair IPC. Live fixture pytest chỉ cho endpoint
127.0.0.1:15433 cùng IPC; không dùng DATABASE_URL mặc định hoặc .env. Child
fake import tests dùng source deterministic đã đọc. Không chạy live provider.
Đây là guard trong test process, không phải thay đổi firewall hệ thống.

Fingerprint 0012 rows: `00a182aedfa2abaa918c64404673621dda9e15199cb1aa920812828e81dbc0c2`.
Fingerprint 0012 indexes: `aa812b4615ba831bf8ce8956ddda436068e01a6f12bd291b37244b4a7ddc7304`.
Fingerprints đầy đủ đổi vì thêm nullable columns/indexes; từng projection cũ
và definition lịch sử đã đối chiếu, không coi fingerprint mới là mất dữ liệu.

## Objective 3 — audit upstream và DAG

Audit chỉ đọc source và tests; broad suite hiện tại kiểm chứng các candidate
tests. Approval backlog không tự trở thành acceptance cho implementation.
DOCUMENT_CONTROL quy định chỉ orchestrator/human reviewer đặt ready/accepted,
và dependency chưa accepted là gate. Không tự sửa catalog để vượt DAG.

| Task | Evidence hiện tại | Gate còn lại |
|---|---|---|
| GOV-001 | Approved ADR-005/RAG_PIPELINE/DATA_DICTIONARY và human approval trace | Không cần hỏi lại approval chung |
| DEPS-001 | Approved exact candidate/runtime/pins/closure/source/hash verified; TASK-REPO-DEP-002 accepted | Model packaging và SCA/release vẫn riêng; không claim full DEPS acceptance |
| EMBED-001 | Vendor-neutral API/worker port; mismatch/NaN/Infinity/empty/batch tests pass | Human candidate acceptance; fake output không phải model evidence |
| EMBED-003 | Candidate fake-isolation tests nằm trong suite pass | Owned elsewhere; chờ handoff/acceptance rõ ràng |
| EMBED-004 | Live schema/model/index compatibility reverified tại 0012 | Human acceptance; chưa inference hoặc active production index |
| CONTEXT-001 | Typed immutable boundary/serialization tests pass | Human acceptance |
| CONTEXT-002 | Trusted identity/scope factory, spoofing/missing/expired identity tests pass | CONTEXT-001 acceptance và candidate review/acceptance |
| FILTER-001 | Storage/apply/preservation/predicate probes verified | Production wiring, full initial hash limitation và task acceptance như trên |
| RETRIEVE-001 | Profile/loader/runtime-binding constants và mismatch tests pass | Runtime magic constants chưa fully wired; không claim toàn AC complete |
| RERANK-001 | Typed port, finite scores, immutable candidates, foreign/duplicate ID/model rejection tests pass | CONTEXT-001 acceptance; approved adapter riêng ở RERANK-002 |
| EVAL-001 | Gold validator tests pass: duplicates/paraphrase/split/version/context/citation checks | Human acceptance; trusted gold corpus/reviewer/index chưa đủ để tạo shards |

Các task còn lại trong 71-ID plan vẫn đi theo DAG; không bỏ task hoặc coi tests
fake là production acceptance. FILTER-002/003 có thể tiến sau acceptance phù hợp
cho context/storage. CONTEXT-003 và EMBED-005/006 không được chạm leased wiring
trước handoff. EMBED-002/RERANK-002 cần private runtime bundle. OPS-001 cần
RETRIEVE-001 acceptance; DATA-001..020 cần EVAL-001 acceptance, trusted corpus/index
và reviewer evidence. Retrieval/evidence/citation/cache/eval/performance/release
downstream chờ upstream gates; không tạo 500 gold cases hoặc đọc sealed text.

## Blockers thực sự và bước tiếp theo

1. **B-UPSTREAM-ACCEPTANCE:** cần human/orchestrator review acceptance cụ thể cho
   candidate contracts/storage đã có evidence; không phải backlog approval mới.
   Production wiring và full-task AC chưa verified phải giữ riêng trong review.
2. **B-MODEL-RUNTIME:** repo chưa có approved private endpoint location/API spec,
   artifact SHA-256 của hai exact BGE revisions và approved live environment.
   Đã hỏi một lần bundle này, không hỏi credential hoặc tự tải weights/package.
3. **B-OWNERSHIP-HANDOFF:** lease fake/vector/ingestion còn hiệu lực; chưa có
   handoff/acceptance upstream của chat song song. Không gửi message để tự lấy.
4. **B-SOURCE-HASH-COVERAGE:** initial snapshot transport không đủ full hash audit;
   giữ evidence sự cố, mutation provenance và final direct-written manifest.
   Không thể phục hồi missing initial hashes từ current bytes hoặc Git HEAD dirty.

Không có failed implementation/repair attempt: migration và tests pass ở lần
apply đầu. SQL production vẫn thiếu filters hiện tại, nên đây chưa phải production
readiness hoặc completed toàn FILTER-001. Không commit/push/deploy, không xóa/reset,
không đổi requirement/contract/model/revision/dimension/quality threshold.

Sau khi acceptance và ownership gates được giải quyết, dùng full final manifest
làm preflight baseline mới và tiếp tục objective kế tiếp theo DAG. Private model
bundle có thể được cung cấp độc lập; không dùng fake để nghiệm thu inference.
