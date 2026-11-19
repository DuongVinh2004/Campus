# RAG runtime — triage bổ sung và hồ sơ reviewer độc lập

Ngày 2026-10-04, Asia/Bangkok. Direct objective: tiếp tục runtime review frontier
trong backlog được duyệt. Đây là execution evidence, không sửa requirement,
security policy, dependency pins, catalog hoặc acceptance. Không phải VEX đã ký.

**Phần chuẩn bị inspection/triage đã thực hiện; B-RUNTIME-SECURITY vẫn mở.**
EMBED-002/RERANK-002 chưa được mở. Acquisition đã hoàn tất và không cần approval
lại. Chưa có security clearance hoặc exact live approval để chạy model.

## Preflight và preservation

SHA-256 của acquisition final scope khớp
`fc28bc2ea49555a734cff37cfad63d3df75b623b7641a5e30c68202d97e635bd`;
đã đọc và rehash **1.332 entries**, không mismatch. Baseline mới exclusive-create:
`infra/local/rag-fixture/review-frontier-20261004-01-baseline.json`, **1.333 files**,
bao gồm acquisition final scope. Coverage là Git cached/nonignored untracked;
ignored runtime/credentials và self-hash được loại. Không dùng baseline để phục hồi
hoặc overwrite bytes hiện tại.

Canonical root/ancestors/write targets được kiểm tra qua `continuation_audit.checked`;
fresh files chưa tồn tại. Chỉ dùng fixture Python **3.12.14**, `-B`; 66 installed
packages khớp lock, chỉ uvloop/httpx2-jsfetch được loại bởi platform. uv.lock vẫn có
SHA-256 `f7727721cc9d433f506b53f2d644230cca9534f9dcd845565c474554888ca55e`.
Dependency verifier, catalog validator và git diff --check preflight đều exit 0.

Write scope: một script review mới, tests parser mới, report này và fresh evidence
trong fixture. Không sửa existing product/source/evidence của baseline. Scope cuối
và commands/exit codes được ghi tại
`infra/local/rag-fixture/review-frontier-20261004-01-final-scope.json`.
Không đọc .env/credentials/Docker config/container environment; không truy cập DB.
Không claim snapshot DB lịch sử là live verification hiện tại.

## Source/image/model binding và discovery

Image giữ đúng:
`ghcr.io/huggingface/text-embeddings-inference@sha256:8419f533857b503ebf6ec292a95d4f1cf9c0464ac8b8abeef39518cf110e5726`.
Source commit `e80ef225ed0e6cb1717ce632a6a84b6cf211bb67`.
Bundle embedding/reranker giữ nguyên checksums đã verify:
`27494beaa7a3dfc6bdff315254232b6a53fca3b39d37dadecdc92bc264981e9a` và
`b0b73b8047e52a0fb3670a3b4789cfa07fe52fe1d910e48dcfd9dd0f79aaa732`.

Evidence mới ở `infra/local/rag-fixture/runtime-acquisition-20261004/review/frontier-01/`:

- Exact commit tree không truncated; các workflows, Cargo manifests, Cargo.lock,
  Dockerfile, logging và HTTP server source đều đối chiếu Git blob identity/size,
  đồng thời ghi SHA-256. Git SHA-1 chỉ là object binding, không thay trust proof.
- Public release v1.9.4 không có release assets. Exact tree chỉ tìm thấy LICENSE
  trong nhóm tên SBOM/VEX/notice/signature; không thấy reviewed packet ở phạm vi đó.
- Workflow build có `id-token: write` và comment Fulcio, nhưng không có signing
  step, SBOM step hoặc independent review evidence được quan sát trong workflow.
  Permissions/comment không chứng minh một chữ ký đã được tạo.
- Public GitHub attestation endpoint cho exact image digest trả 404. Các registry
  probes 404 trước đó vẫn giữ nguyên. Discovery này không chứng minh mọi nơi đều
  thiếu chữ ký hoặc cho phép truy cập private registry.
- GitHub commit API báo `verified=true`, reason `valid`. Đây là assertion của
  GitHub cho **source commit**; chưa tự verify cryptographic signature và không
  phải image signature.
- Retained SLSA statement có matching subject/build GIT_SHA; BuildKit metadata
  ghi `resolvedDependencies=false`. Không dùng nó làm complete compiled SBOM hoặc
  verified signer/provenance.

Sources: [pinned workflow](https://github.com/huggingface/text-embeddings-inference/blob/e80ef225ed0e6cb1717ce632a6a84b6cf211bb67/.github/workflows/build.yaml),
[pinned Dockerfile](https://github.com/huggingface/text-embeddings-inference/blob/e80ef225ed0e6cb1717ce632a6a84b6cf211bb67/Dockerfile).

## Cargo và native triage

`cargo-triage.json` giữ 10 affected package entries/8 advisory IDs và potential
lock paths. Trong 10 entries có **5 maintenance**, **5 vulnerability**; đây không
phải 10 confirmed reachable vulnerabilities. Lock graph bao gồm optional/dev/build
edges; chưa chạy cargo resolution/build, chưa có compiled feature graph.

| Component | Evidence/đề xuất triage | Disposition |
|---|---|---|
| h2 0.3.27 | Marker tồn tại trong router. Lock path ngắn qua optional tonic không đủ loại h2: HTTP build vẫn dùng OTLP/tonic dependencies. Publisher mô tả Low; patched >=0.4.16. Không thay trực tiếp 0.3 bằng 0.4 mà bỏ compatibility review. | pending independent review |
| rustls 0.23.43 | Marker tồn tại; lock có reqwest path. Publisher CVSS 5.3 Medium, fixed >=0.23.45. Native OpenSSL linkage không chứng minh Rustls bị loại. | pending independent review |
| SDK 0.19.0 + opentelemetry_api | Potential path qua optional Python backend/grpc-metadata, không thuộc requested CPU backend features theo source. Chỉ là feature-exclusion candidate, chưa compiled proof. | pending independent review |
| SDK 0.22.1/0.23.0 | Source HTTP có OtelAxumLayer; logging gọi init_propagator khi OTLP init thành công. Versioned init-tracing 0.18.1 source có mặc định tracecontext,baggage. Không kết luận baggage disabled. | pending independent review |
| yaml-rust | Path qua insta trong router dev-dependencies; build/test exclusion candidate. | maintenance review pending |
| paste/proc-macro-error | Tokenizers/utoipa-gen paths; macro build relevance candidate, không tự đóng maintenance review. | maintenance review pending |
| number_prefix | hf-hub/indicatif path; không tự gọi build-only. | maintenance review pending |

Primary advisory sources: [h2](https://rustsec.org/advisories/RUSTSEC-2026-0258.html),
[rustls](https://rustsec.org/advisories/RUSTSEC-2026-0285.html),
[baggage](https://github.com/open-telemetry/opentelemetry-rust/security/advisories/GHSA-w9wp-h8wv-79jx).
Versioned third-party source snapshot là supporting evidence, chưa independently
bound tới compiled binary. Global GitHub advisory API trả 404 cho h2/rustls/xz;
đã giữ discovery records, không coi 404 là absence của primary repository advisory.

Full native pass đọc tất cả regular image entries, nhận diện **752 ELF64
little-endian x86-64**, ghi hashes/DT_NEEDED/SONAME/RPATH/RUNPATH. Không extract,
load hoặc chạy binary. Symlink aliases của image chỉ resolve trong memory.
Router SHA-256 vẫn là
`157abaf15d1cf9ae906108cd5005b7a0590a8ab02355687b5412a6eab1fa5887`.

Router có tám dependency names trong static transitive closure; libiomp5 alias
map tới LLVM libomp.so.5, không có unresolved name. Router **thực sự DT_NEEDED
libssl.so.3 và libcrypto.so.3**. Closure không chứa libpcre2/liblzma, nhưng không
chứng minh absence của dlopen/preload/static code hoặc affected OS utilities.
Đây là native linkage inventory, **không phải full compiled SBOM hay VEX**.

## Debian, severity và license frontier

Giữ toàn bộ **192 pending entries** từ retained tracker: 14 version-lag, 177 open,
1 undetermined; `debian-triage.json` bổ sung điều kiện API/platform từ description.
Không biến urgency `unimportant`/`not yet assigned`, no-dsa hoặc missing severity
thành accepted/clean. Không tự downgrade severity.

| Version-lag subset | Điều kiện cần reviewer kiểm tra |
|---|---|
| OpenSSL 6 entries | DTLS buffer amplification; CMS unwrap; CMP context/PBM; EVP_Cipher empty AEAD; CVE-2026-42767 giữ nguyên description để review. Linkage là thật; cần chứng minh API use/config cho từng finding. Fixed package target trong snapshot: 3.0.22-1~deb12u1. |
| PCRE2 7 entries | CVE-2026-89157/89158 explicitly 32-bit: platform mismatch candidates cho ELF64 image. Các JIT/DFA/invalid-UTF cases còn lại vẫn pending. Fixed target: 10.42-1+deb12u2. |
| xz-utils 1 entry | TEMP-1147318-639065 map tới upstream GHSA-5qpq-xqfv-j9pg **High**. Điều kiện gồm reuse decoder, allocation failure và dictionary matching; .xz/raw decoders không affected. Fixed Debian target: 5.4.1-1+deb12u2. Không tự đóng finding vì router không DT_NEEDED liblzma. |

Sources: [PCRE2 32-bit case 1](https://security-tracker.debian.org/tracker/CVE-2026-89157),
[case 2](https://security-tracker.debian.org/tracker/CVE-2026-89158),
[XZ primary advisory](https://github.com/tukaani-project/xz/security/advisories/GHSA-5qpq-xqfv-j9pg).
High XZ condition phải có independent disposition hoặc đúng policy exception;
không suy ra waiver từ synthetic smoke constraints.

MKL build package là `intel-oneapi-mkl-devel=2024.0.0-49656`; final image có chín
shared libraries và libfakeintel. Website FAQ/current license không đóng controlling
license/redist/notices cho package này hoặc static linkage. Cần publisher/package
evidence và compliance reviewer. Không tải/cài package/scanner/runtime mới.

Candidate remediation gửi reviewer: publisher rebuild với fixed Debian packages
trên, reviewed compatible h2/Rustls/telemetry dependency graph, complete native
notices, compiled SBOM và signed provenance. Đây là **tiêu chí candidate**, chưa
là approved replacement digest; không đổi package pins hoặc build một image mới.

## DAG và đầu vào cụ thể

Đã reconcile **71 RAGUP nodes** và 241 catalog items; không có RAGUP YAML trong
catalog. `dag-frontier.json` ghi từng dependency/state, không sửa acceptance.
Generated task-index ghi DEP-002 draft trong khi actual task item là accepted;
validator đọc items cho dependency acceptance. Giữ discrepancy, không tự đồng bộ.

Không còn new implementation objective độc lập đủ cả dependency và input gate:
DEPS-001 chờ runtime security; DATA-001..020 chờ trusted corpus; CONTEXT-003 và
RETRIEVE-001 còn partial và cần trusted runtime/binding/canonical consumers;
OPS-001 cần RETRIEVE-001 accepted. Các vector/retrieval/rerank/evidence/citation/
eval/cache/performance/release tasks chờ accepted dependencies theo DEC-019.
Không mở downstream bằng partial pass, fake quality hoặc ba legacy chunks.

`independent-review-input.json` đã khóa exact image/model manifests và hashes của
supporting evidence, với reviewer/signature còn null/not_verified. Đầu vào đóng gate:

1. Signed independent review/VEX cho đúng digest/findings; compiled Rust/native/OS
   SBOM; verified signer/issuer/provenance; MKL controlling license/redist/notices.
   Hoặc vetted private runtime/service bundle có equivalent immutable evidence,
   exact models, endpoint/OpenAPI/auth **secret-reference metadata**, synthetic scope.
2. Deployment institution identifier, verified issuer binding và reviewed resolver
   cho role validity/revocation, audience, faculty/program. Không default grants.
3. Reviewed corpus snapshot với source-version/chunk/scope/provenance và
   knowledge-owner review để xây active 1024 index/gold. Không đọc sealed text.

Đã tìm trong infra/specs/bootstrap/delivery/context sources, pinned upstream tree/
workflows/release, public attestation discovery và acquired image inventory.
Không tìm thấy signed independent packet/private bundle/trusted bindings/corpus
review đủ gate trong phạm vi này. Không yêu cầu secret/token trong chat.

Normative requirements: SEC-SDLC-002/004/010/012, SEC-CTRL-019/026/029,
SEC-LAUNCH-012; typed scope/source rules của approved RAG_PIPELINE,
ADR-005/DATA_DICTIONARY; accepted-dependency rule DEC-019. Approval chung không
thay những artifact/config/review bắt buộc này. Sau clearance mới đề xuất separate
exact live approval theo candidate container/network/port/CPU/input envelope.

## Verification, failed evidence và limits

Mọi command dùng fixture python -B; fresh labels/temp outputs, retention all,
outbound/DNS denied cho tests. Public metadata inspection được authorize riêng
trong direct request; không live-provider/model test.

| Command/check | Exit | Evidence |
|---|---:|---|
| Acquisition manifest rehash + new baseline | 0 | 1.332 matches; 1.333 baseline files |
| verify_dependencies.py; validate_catalog.py; git diff --check preflight | 0 each | 66 exact installed packages; catalog 241/10 |
| delegated_verify.py frontier-20261004-parser-01 tests/unit/runtime_review/test_frontier_review.py | 1 | 6 passed/1 failed; synthetic ELF test changed memsz instead of filesz |
| Same targets label parser-02 | 0 | 7 passed; corrected fixture offset, rejection expectation unchanged |
| runtime_frontier_review_20261004.py | 0 | review-final.json; exact source, Cargo triage, initial 17 native ELF |
| native_triage(full=True), first pass | 1 | native-full-01-failure.json; exact LLVM member exceeded initial read bound; no full output created |
| Full native pass after scoped bound adjustment | 0 | native-link-full-02.json; 752 ELF; only exact inspected LLVM path/109967296 bytes additionally admitted |
| supplements(), first pass | 1 | supplement-01-failure.json; OpenTelemetry snapshots retained, public global advisory 404 |
| advisory_and_closure() | 0 | Discovery 404 recorded; router-dynamic-closure.json; no finding suppressed |
| DAG read helper first/second attempts | 1 each | dag-inspection-failures.json; stopped before writes on schema assumption/index-item discrepancy |
| Actual task-item DAG reconciliation | 0 | dag-frontier.json; 71 nodes; zero additional independent preflight candidates |
| delegated_verify.py frontier-20261004-parser-final-03 tests/unit/runtime_review/test_frontier_review.py | 0 | **7 passed**, no skip/warning; final parser version |
| Final dependency/catalog/diff/scope and scoped secret/canary scan | recorded in final scope | Fresh evidence, raw hits never emitted; no broad regression repeated |

AC mapping: immutable acquisition preservation/source binding/static triage/reviewer
packet/DAG inspection verified within stated scope. Compiled SBOM, signer/issuer,
native license closure, independent security acceptance, inference/model quality,
trusted scope/corpus and whole production upgrade remain **not_verified/blocked**.
Static source/ELF review is not comprehensive malware/PII/model-memorization proof.
No commit/push/deploy/reset/clean/delete or resource/history mutation performed.
