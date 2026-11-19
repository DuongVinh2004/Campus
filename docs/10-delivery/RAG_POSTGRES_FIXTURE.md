# Fixture PostgreSQL/pgvector biệt lập cho RAG

Trạng thái ngày 2026-10-03: **fixture sẵn sàng, đã kiểm chứng runtime thật**.
Database/container/volume mới được tạo riêng sau kiểm tra collision, port và
ownership. TASK-RAGUP-EMBED-004 đã apply migration additive `0011`, descendant
của `0010`, trên đúng fixture. Guard đã review và khóa đúng hash source `0011`;
seed, nearest-neighbor, dimension rejection, repeat seed và stop/start đều pass
tại head `0011`. Fixture này không chứng minh chất lượng embedding hoặc
production RAG.

Dependency scope được người dùng mở riêng. Approval
`DIRECT-HUMAN-2026-10-02-DEP-001` chỉ áp dụng candidate SHA-256
`f7727721cc9d433f506b53f2d644230cca9534f9dcd845565c474554888ca55e`
và đúng 53 package/version bổ sung. Lock có 68 registry packages; môi trường
Windows Python 3.12.14 cài 66, hai package được loại bởi platform marker
(`uvloop`, `httpx2-jsfetch`). Mọi version đã cài khớp lock; nguồn/hash/drift gate
vẫn hoạt động. Verifier Python 3.12 exit 0; Python 3.14 vẫn bị chặn exit 1.

Evidence hiện tại không chứa credential:
[verification-0011-evidence.json](../../infra/local/rag-fixture/verification-0011-evidence.json).
Baseline trước migration vẫn giữ nguyên tại
[verification-evidence.json](../../infra/local/rag-fixture/verification-evidence.json),
head `0010`; không thay baseline bằng fingerprint schema mới.
Review approval: [DEPENDENCY_REVIEW.md](../../tests/unit/dependency_resolution/DEPENDENCY_REVIEW.md).
Lần bàn giao tại `0011` chỉ chạy tests mục tiêu đã đọc: **49 passed, không skip**
(fixture guard, manifest compatibility và lịch sử migration). Không chạy suite
rộng có thể tự kết nối database mặc định trong bước cập nhật fixture này.

## Phạm vi và target dự kiến

| Target | Giá trị |
|---|---|
| Compose riêng | `infra/local/rag-fixture/compose.yaml` |
| Compose project | `campus247-rag-fixture` |
| Database | `campus247_rag_fixture` |
| Business schema | `public` |
| Marker schema/table | `rag_fixture_control.identity` |
| Container | `campus247-rag-fixture` |
| Volume | `campus247_rag_fixture_pgdata` |
| Network | `campus247-rag-fixture_default` |
| Host binding | `127.0.0.1:15433` |
| DSN environment variable | `RAG_FIXTURE_DATABASE_URL` |
| Image | `pgvector/pgvector:pg16` |

Image pin theo PostgreSQL major 16, tương tự Compose chính. Tag này có thể thay
đổi. Runtime đã xác minh PostgreSQL `16.15 (Debian 16.15-1.pgdg12+2)` và pgvector
`0.8.6`; image ID và repo digest thực tế được lưu trong evidence, không tự thay
cấu hình sang một digest chưa được giao.
Không dùng `campus247_local`, port 5433, Compose chính, `.env` hay `DATABASE_URL`.

## Lịch sử inspection trước khi mở scope dependency

Các blocker và exit code trong phần này là baseline trước approval. Kết quả
sau xử lý nằm ở đầu tài liệu và bảng verification cuối tài liệu.

- `py --list-paths`: chỉ đăng ký Python 3.14; `python -B` báo 3.14.7.
  Đã tìm thấy Python 3.12.14 trong runtime bundle hiện có của Codex tại
  `C:\Users\Duong Vinh\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`.
  Runtime này hợp lệ nhưng thiếu `sqlalchemy`, `asyncpg`, `alembic`, `pgvector`
  và `pytest`; không cài thêm package.
- Không tìm thấy `uv` qua command discovery. Không cài runtime hoặc dependency.
- `python -B scripts/verify_dependencies.py`: exit 1, báo `langchain-core` và
  `langgraph` ngoài allowlist trong verifier, đồng thời thiếu hai package này
  trong `uv.lock`. Không sửa allowlist, verifier hoặc lockfile để bỏ qua lỗi.
- Docker CLI có mặt; `docker compose version` trả Compose v5.5.0.
- Trong sandbox, Docker không đọc được config và không tìm thấy pipe mặc định.
  Kiểm tra chỉ đọc ngoài sandbox xác minh context `desktop-linux`, Engine
  `29.7.2` đang chạy. Không đổi quyền hoặc sửa config của người dùng.
- Container/volume/network inventory ngoài sandbox không có các tên fixture
  đề xuất. Image `pgvector/pgvector:pg16` đã cache, short image ID
  `ccc6e83d6e35`; chưa xác minh registry digest hoặc extension version.
  Port inspection không trả listener 15433; guard bind phải kiểm tra lại ngay
  trước startup. Không suy ra ownership hay disposable từ các kết quả này.
- Source migration ancestry là `0001 -> ... -> 0009 -> 0010`. Migration 0009
  khai báo `embedding vector(1536)`, HNSW cosine và GIN `content_tsv`.
  Đây là inspection source, không phải schema của database đã chạy.
- Upgrade chain đã đọc: tạo bảng/index và thêm cột; 0010 SELECT để kiểm tra
  booking overlap trước khi thêm cột/index. Downgrade có thao tác phá hủy và
  tuyệt đối không được gọi. Công cụ khóa hash source đã review, tự tìm head
  bằng Alembic và dừng nếu migration source mới/thay đổi chưa được review.
- Compose validation `config --quiet` với env synthetic tạm: exit 0, không
  tạo resource hoặc đọc `.env` của project. Dùng `--env-file NUL` riêng.
- Offline guard tests bằng Python 3.12.14: exit 0, tám tests passed, một live
  test skipped vì thiếu fixture DSN. Không có live DB evidence.
- `fixture.py preflight` bằng Python 3.12.14: exit 1 vì dependency verifier;
  bằng Python 3.14.7: exit 1 vì runtime. Cả hai dừng trước mutation.
- Git scope inspection: chỉ tạo sáu files trong ba scope được giao; hash của
  23 dirty/untracked files có sẵn được đối chiếu và không đổi. Không sửa file
  của chat khác. `.fixture-state.json` chưa tồn tại; không có resource mới.

| Command/inspection | Exit code | Evidence |
|---|---:|---|
| `docker context ls` và `docker version --format` ngoài sandbox | 0 | `desktop-linux`; Engine 29.7.2 |
| `docker compose --env-file NUL -f infra/local/rag-fixture/compose.yaml config --quiet` | 0 | Cấu hình hợp lệ; chỉ dùng env synthetic tạm |
| `python -B scripts/verify_dependencies.py` | 1 | Allowlist mismatch và lock drift có sẵn |
| Python bundle 3.12.14 chạy `-B tests/integration/rag_fixture/test_guard.py` | 0 | 8 passed, 1 live skipped |
| Python bundle 3.12.14 chạy `-B infra/local/rag-fixture/fixture.py preflight` | 1 | Dependency verifier chặn trước mutation |
| Python 3.14.7 chạy `-B infra/local/rag-fixture/fixture.py preflight` | 1 | Runtime guard chặn trước mutation |
| `git diff --check`, scope/status/untracked inspection | 0 | Không thay đổi tracked file; chỉ thêm files trong lease |

Không chạy `start`, `prepare`, `seed`, `verify` hay `persistence` vì preflight
chưa đạt. Không chạy test suite rộng hoặc kết nối database hiện có.

## Quy trình sử dụng fixture đã xác minh

Dùng interpreter riêng bên dưới. Các bước prepare/seed/verify/persistence đã
chạy thành công trên đúng fixture. Không tự chạy suite rộng. Không dùng Python
3.14 hoặc sửa policy để vượt gate. Docker cần quyền truy cập context
`desktop-linux`; không sửa config/ACL của người dùng.

```powershell
# Tại workspace; interpreter riêng, không thay Python hệ thống.
$fixturePython = 'C:\Users\Duong Vinh\Vinh\infra\local\rag-fixture\.venv\Scripts\python.exe'
$fixtureTool = '.\infra\local\rag-fixture\fixture.py'
& $fixturePython -B $fixtureTool preflight
# Fixture đã tồn tại: dùng resume. start chỉ dành cho setup mới chưa có target.
& $fixturePython -B $fixtureTool resume
```

`start` từ chối mọi target container/volume/network hoặc receipt đã có sẵn;
kiểm tra port trước khi tạo. Không reuse resource có ownership mơ hồ. Nó tạo
password local synthetic riêng và owner token ngẫu nhiên, lưu bằng exclusive
create vào `.fixture-state.json` trong scope fixture; file này được gitignore.
Không in credential hoặc DSN. Không đưa receipt vào Git, log hay evidence.
Nếu startup lỗi, giữ receipt và resources để inspection; không cleanup/retry
bằng cách xóa receipt hoặc volume.

Nạp DSN riêng vào bộ nhớ PowerShell, không in biến ra output:

```powershell
$fixtureReceipt = Get-Content -LiteralPath '.\infra\local\rag-fixture\.fixture-state.json' | ConvertFrom-Json
$env:RAG_FIXTURE_DATABASE_URL = 'postgresql+asyncpg://rag_fixture:' + $fixtureReceipt.password + '@127.0.0.1:15433/campus247_rag_fixture'
& $fixturePython -B $fixtureTool prepare
& $fixturePython -B $fixtureTool seed
& $fixturePython -B $fixtureTool verify
& $fixturePython -B $fixtureTool seed
& $fixturePython -B $fixtureTool verify
& $fixturePython -B $fixtureTool persistence
& $fixturePython -B tests/integration/rag_fixture/test_guard.py
```

`prepare` chỉ upgrade một DB mới có marker và không có business table/dữ liệu.
Nếu đã có Alembic version, chỉ cho phép no-op khi current bằng source head;
không tự nâng cấp database đang có dữ liệu. Nó dùng Alembic upgrade traversal
trên cùng connection/transaction đã guard, không import migration `env.py`
vì file đó luôn khởi tạo app settings và có thể đọc `.env`. Không dùng downgrade.

Trước mỗi write transaction, guard kiểm tra receipt, container/volume labels,
binding, endpoint, current database/user/schema, marker, extension, relation
inventory và dữ liệu synthetic. Table ngoài source được review hoặc dữ liệu
ngoài seed đều làm dừng trước ghi. Không có fallback DSN. Seed chỉ INSERT ID
mới; bản ghi đã có phải khớp provenance và vector, không UPDATE/overwrite.
Advisory lock serialize các lệnh prepare/seed của fixture.

Seed gồm một synthetic source, một document version và ba chunks với hash,
URI `synthetic://`, locator và vector theo dimension của schema thực tế.
Vector `(1,0)`, `(0.6,0.8)`, `(0,1)` được pad zero; cosine nearest-neighbor
phải theo thứ tự này. Sai dimension được thử bằng SELECT cast trong savepoint,
không ghi dữ liệu lỗi. Seed này chỉ kiểm tra lưu trữ/toán tử/dimension, không
đại diện model BGE-M3, semantic quality, authorization hay production publish.

`verify` yêu cầu current=head, đọc lại toàn bộ seed/provenance/vector, kiểm tra
thứ tự và dimension rejection. Nó tính SHA-256 cho toàn bộ cột seed (bao gồm
timestamps) và định nghĩa mọi public index. `persistence` đối chiếu các fingerprint
trước/sau exact owned container stop/start. Chỉ gọi fixture sẵn sàng khi các kiểm
tra thật pass.
Live test thiếu DSN sẽ skip; skip không được tính là pass/readiness evidence.

## Stop và bàn giao cho task tiếp theo

```powershell
& $fixturePython -B $fixtureTool stop
# Chỉ resume container/volume đã có receipt và labels khớp.
& $fixturePython -B $fixtureTool resume
& $fixturePython -B $fixtureTool verify
```

Không dùng down, down -v, reset, DROP, TRUNCATE, DELETE hoặc cleanup volume.
Không bỏ qua receipt/guard khi target bị collision hoặc ownership không rõ.

Task RAG tiếp theo phải nhận database/schema/DSN variable và live evidence ở
trên, kiểm chứng lại source head và snapshot dữ liệu/index trước khi apply
migration của task đó. Fixture tool hiện chỉ sở hữu bootstrap/seed và từ chối
source migration mới chưa review. Không tự sửa manifest/profile/adapter hoặc
chuyển dimension 1536 thành 1024. Existing fixture data vẫn phải được bảo toàn.

Review bổ sung `0011_embedding_index_manifest.py` khóa SHA-256
`bad24bab87a36fc54bfd6e807f1bc199a1f05f1ed606075dbce55e4850da1d7e`
trong `REVIEWED_ADDITIONS`; `REVIEWED` giữ nguyên mười source lịch sử tới `0010`.
Guard đối chiếu chính xác toàn bộ tập source với hai map này. Sửa hash hoặc thêm
migration chưa review vẫn dừng trước DB mutation. `prepare` trên DB đã có dữ
liệu chỉ no-op tại `0011`; nếu revision khác head, nó tiếp tục từ chối implicit
upgrade. Không chạy lại migration đã apply.

Schema hiện có 46 public indexes và 167 constraints. Đối chiếu baseline xác minh
41 index và 116 constraint lịch sử không đổi, toàn bộ cột dữ liệu cũ giữ nguyên;
cột trace mới `document_version.index_version` là NULL ở document có sẵn.
Ba bảng `retrieval_profile`, `embedding_index_manifest` và
`embedding_index_active_pointer` đều rỗng sau rollback metadata synthetic trong
live compatibility test. Không có index được tự kích hoạt.

Fingerprint đầy đủ tại `0011` bao gồm cột trace và index mới nên khác fingerprint
baseline. Evidence lưu riêng projection các cột/index lịch sử và xác minh chúng
khớp `0010`; đồng thời kiểm tra fingerprint đầy đủ `0011` không đổi qua prepare,
seed lặp, negative guards và stop/start. Không bỏ qua cột/index mới khi kiểm tra
persistence.

Dependency/runtime blocker đã xử lý trong scope được người dùng mở và candidate
được duyệt. uv 0.12.22 chỉ provision trong workspace với artifact hash được ghi
tại `tests/unit/dependency_resolution/resolver-toolchain.lock.json`; không cần
uv global/PATH. Package installation dùng frozen hashed export, `--require-hashes`,
`--no-deps`, `--no-build` vào `.venv` mới; không sync/prune môi trường có sẵn.

Giới hạn còn lại: review advisory/license metadata không thay thế SCA hoặc release
approval; certifi/orjson có MPL-2.0. Image tag chưa pin immutable. Fixture dùng
deterministic vectors dimension 1536 theo schema; chưa tải weights BGE-M3 hoặc
kiểm chứng semantic quality. Model/revision/dimension/profile/index mismatch đã
được kiểm chứng bằng contract tests và constraint tests trên PostgreSQL thật;
việc này không chứng minh model inference hay quality threshold. Query/ingestion
adapter vẫn chờ dependencies EMBED-002/005/006. Bước cập nhật fixture này không
thêm/sửa migration nghiệp vụ, head test, adapter, profile hoặc governance.

| Gate trên PostgreSQL thật | Kết quả hiện tại |
|---|---|
| Healthy và đúng database | passed; `campus247_rag_fixture`, `public` |
| Extension vector và version thực tế | passed; pgvector 0.8.6, PostgreSQL 16.15 |
| Alembic current = source head | passed; 0011 là descendant của 0010; ancestry lịch sử giữ nguyên |
| Seed lưu/đọc đúng | passed; 1 source, 1 document, 3 chunks, vector(1536) |
| Nearest-neighbor theo thứ tự dự kiến | passed; exact axis, diagonal, orthogonal axis |
| Database reject sai dimension | passed; SELECT cast trong savepoint, SQLSTATE 22000 |
| Guard reject sai DB/thiếu DSN trước write | passed; hai CLI calls exit 1 như dự kiến, không fallback/kết nối target sai |
| Repeat seed không duplicate | passed; toàn bộ stored-row và index fingerprints không đổi |
| Stop/start bảo toàn dữ liệu | passed; stored-row và public-index fingerprints khớp trước/sau |
| Source review và drift rejection | passed; exact hash 0011, source thay đổi hoặc migration mới bị chặn |
| Model/index compatibility và pointer | passed; mismatch bị reject, metadata synthetic rollback, pointer còn rỗng |

| Command bàn giao tại 0011 | Exit code | Kết quả |
|---|---:|---|
| Python fixture chạy `scripts/verify_dependencies.py` | 0 | Runtime 3.12.14; candidate được duyệt, source/hash/drift pass |
| `fixture.py verify`, `prepare`, `seed`, repeat `verify` | 0 | Head 0011; prepare no-op; seed và fingerprints không đổi |
| `fixture.py seed` thiếu DSN / sai database | 1 | Rejection đúng lý do; không fallback/kết nối sai target |
| `fixture.py persistence`, `verify` | 0 | Exact owned stop/start; volume và fingerprints bảo toàn |
| Targeted pytest fixture guard + manifest + migration history | 0 | 49 passed; không skip, gồm live compatibility/preservation |

| Command sau approval dependency, bàn giao ban đầu tại 0010 | Exit code | Kết quả |
|---|---:|---|
| `uv lock --offline` với lock baseline | 2 | Lock cũ không parse; áp dụng exact reviewed candidate bằng patch |
| `uv export --frozen --offline`, `uv venv` | 0 | Hashed export; môi trường mới không seed package |
| `uv pip install --require-hashes --no-deps --no-build --strict` | 0 | 66 packages khớp candidate, không thay Python hệ thống |
| Python fixture chạy `scripts/verify_dependencies.py` | 0 | Pins, graph, registry, artifact hashes, approval checksum pass |
| Python 3.14 chạy verifier | 1 | Runtime guard chặn như dự kiến |
| `fixture.py preflight`, `start`, `prepare`, `seed`, `verify`, `persistence` | 0 | Live checks pass; không downgrade/reset/drop |
| `fixture.py prepare` lần hai | 0 | No-op tại head hiện tại, không implicit upgrade dữ liệu |
| `fixture.py seed` thiếu DSN / sai database | 1 | Hai negative cases bị chặn đúng lý do, fingerprints không đổi |
| Targeted pytest fixture guard + dependency verifier | 0 | 37 passed; không skip |

## Scope và kiểm tra bàn giao ban đầu tại 0010

- Sửa tracked files trong dependency scope: `pyproject.toml`, `uv.lock`,
  `scripts/verify_dependencies.py`; thêm `.gitignore`, review JSON/Markdown,
  toolchain artifact lock và `test_verifier.py` trong
  `tests/unit/dependency_resolution/`.
- Fixture scope: `compose.yaml`, `init.sql`, `.gitignore`, `fixture.py`,
  `verification-evidence.json` trong `infra/local/rag-fixture/`;
  `tests/integration/rag_fixture/test_guard.py` và tài liệu này.
- `.fixture-state.json`, `.venv`, uv tool/cache/candidate được ignore; receipt
  và credential không xuất hiện trong evidence hay tracked files. Không cleanup
  các artifacts này. Container fixture đang healthy; volume được giữ nguyên.
- `git diff --check`, `git diff --name-only`, `git status --short`, untracked và
  ignored-path inspection: exit 0. Đối chiếu 29 baseline hashes: chỉ ba files
  fixture do chat này tạo và sở hữu thay đổi (`fixture.py`, `.gitignore`, tài liệu);
  23 files dirty/untracked từ các task khác không đổi. Không commit/push/deploy,
  reset/clean, thay migration lịch sử hoặc sửa test expected head.
- Schema inspection xác minh HNSW cosine và GIN `content_tsv` vẫn tồn tại;
  41 public indexes và 116 constraints được ghi trong evidence baseline 0010.
  TASK-RAGUP-EMBED-004 sau đó đối chiếu baseline này trước/sau migration additive;
  evidence hiện tại tại 0011 được lưu riêng như mô tả ở đầu tài liệu.

## Scope cập nhật bàn giao tại 0011

Chỉ sửa `infra/local/rag-fixture/fixture.py`,
`tests/integration/rag_fixture/test_guard.py` và tài liệu này; thêm
`infra/local/rag-fixture/verification-0011-evidence.json`. Giữ nguyên baseline
evidence 0010, toàn bộ migration, contract, adapter, dependency và các thay đổi
có sẵn của chat khác. Không commit, push, deploy hoặc cleanup.
