# RAG runtime — kết quả acquisition và hồ sơ security review

Ngày 2026-10-04, Asia/Bangkok. Đây là evidence thực thi, không sửa normative
contracts, không phải acceptance của DEPS-001/EMBED-002/RERANK-002 hoặc release.

## Objective, quyền hạn và dependencies

Human đã trả lời **“ok phê duyệt toàn bộ cho bạn làm”** sau proposal cụ thể tại
`RAG_RUNTIME_CANDIDATE_20261004.md`, mục acquisition/inspection only. Đã thực hiện
đầy đủ acquisition đúng image digest và 16 file model được trình bày. Scope này
không chứa launch/inference, production access, đổi dependency pins, hay thay
security controls. Không hỏi lại approval cho acquisition đã được cấp.

Intake được khóa bằng SHA-256
`286f8311c01fe6f0123037456daf441968ab25cf842f39ba1477d15bb73b397e`.
Objective chỉ đọc public distribution/security metadata và ghi artifact mới trong
workspace. Không cài package/tool, Docker pull/load/create/run, gọi model, đọc
credentials/.env/container environment, truy cập DB, publish/commit/push/cleanup.

Preflight: canonical root và tất cả ancestor không có symlink/junction/reparse;
fresh destinations chưa tồn tại; Git dirty/untracked state được giữ nguyên. Rehash
toàn bộ **1.217** entries của scope cuối lượt trước đều khớp. Baseline mới tạo bằng
exclusive-create có **1.218** files, loại ignored runtime/credentials và chính nó:
`infra/local/rag-fixture/acquisition-20261004-baseline.json`.

## Acquired bytes và independent verification

Tất cả artifact ở `infra/local/rag-fixture/runtime-acquisition-20261004/`.
Không ghi vào external Docker cache. File mới dùng exclusive-create; không có
overwrite/truncate/remove. Mọi artifact và partial/negative-test bytes được giữ.

| Artifact | Kết quả |
|---|---|
| TEI cpu-1.9.4 Linux/amd64 | Manifest/config/index raw bytes khớp digest; 13 layer khớp size và SHA-256; tổng compressed payload 239.307.989 bytes |
| BAAI/bge-m3, revision 5617a9f61b028005a4858fdac845db406aefb181 | 10 file, 2.293.315.801 bytes; từng file khớp intake |
| BAAI/bge-reranker-v2-m3, revision 953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e | 6 file, 2.293.242.108 bytes; từng file khớp intake |
| Tổng actual payload | **4.825.865.898 bytes**, 29 file payload được kiểm tra full bytes |
| Independent static pass | Rehash tất cả model/layer; 13 uncompressed layer digest khớp OCI config `rootfs.diff_ids` |

Image:
`ghcr.io/huggingface/text-embeddings-inference@sha256:8419f533857b503ebf6ec292a95d4f1cf9c0464ac8b8abeef39518cf110e5726`.

Weight SHA-256:

- bge-m3 `pytorch_model.bin`:
  `b5e0ce3470abf5ef3831aa1bd5553b486803e83251590ab7ff35a117cf6aad38`.
- reranker `model.safetensors`:
  `d9e3e081faff1eefb84019509b2f5558fd74c1a05a2c7db22f74174fcedb5286`.

Checksum của canonical full-file manifest sau actual-byte verification:

- Embedding bundle: `27494beaa7a3dfc6bdff315254232b6a53fca3b39d37dadecdc92bc264981e9a`.
- Reranker bundle: `b0b73b8047e52a0fb3670a3b4789cfa07fe52fe1d910e48dcfd9dd0f79aaa732`.

Đây là checksum bundle đã tải, không phải active index/corpus checksum hoặc chứng
minh deployed service. Giữ riêng ý nghĩa này với metadata-manifest hash của intake.

Static model inspection: embedding là ZIP PyTorch, 395 members/391 tensor storage
members; chỉ parse pickle opcodes bằng `pickletools`, **không unpickle/load/execute**.
Reranker có 393 tensors F32, offsets/shape/data length hợp lệ; classifier output
weight [1, 1024]. Config cả hai xác nhận XLM-RoBERTa, hidden size 1024, 24 layers.
Load thực tế, output vector/logit, latency và quality vẫn **not_verified**.

## Security/native/license review và giới hạn

Final inventory tái dựng overlay trong memory, không extract hoặc follow archive
links: **5.194 entries**, 117 installed dpkg packages, 83 source/version pairs,
116 copyright files. ELF evidence gồm router, 9 MKL libraries, libfakeintel và
`mklost+found` thuộc OS; file cuối không phải MKL inference dependency.

Lượt static đầu có lỗi parser khi gặp field trống `Conffiles:` trong dpkg status.
Đã sửa một lần, giữ nguyên evidence cũ. Evidence authoritative dùng
`review/static-02/`; parser thứ hai độc lập dùng stdlib email parser từ raw status
xác nhận toàn bộ 117 package records khớp. Không dùng inventory lượt đầu cho SCA.

Pinned router ELF SHA-256:
`157abaf15d1cf9ae906108cd5005b7a0590a8ab02355687b5412a6eab1fa5887`.
Binary chứa static markers `h2-0.3.27`, `rustls-0.23.43`, `opentelemetry`.
Điều này ngăn việc tự loại findings như build-only; strings không đủ chứng minh
compiled SBOM, vulnerable-code reachability hoặc severity. Cargo OSV evidence
cũ (576 registry crates, 10 affected entries/8 advisory IDs) vẫn được giữ nguyên;
limitation “image chưa acquired” của report đó là trạng thái lịch sử, đã được
bổ sung bởi evidence mới, không sửa report cũ.

Debian security tracker snapshot 79.808.822 bytes, SHA-256
`dfa790b02499ee4761ff4e6ee3d5155cad78f13c8e338c1052a330ae4ba3de5f`.
Đối chiếu source version theo [Debian version policy](https://www.debian.org/doc/debian-policy/ch-controlfields.html#version):

| Disposition của tracker/version | Số entries |
|---|---:|
| Installed source version bằng hoặc sau fixed version | 1.404 |
| Tracker ghi không affected | 218 |
| Installed source version thấp hơn fixed version | **14** |
| Open, chưa có fixed version | 177 |
| Undetermined | 1 |

14 version-lag entries gồm OpenSSL 6, PCRE2 7 và xz-utils 1. Đây là version matching,
không kết luận 192 findings đều reachable/exploitable hoặc cùng severity.
Các điều kiện platform/API/JIT/CMP/DTLS và open/no-dsa cần triage độc lập.
Ví dụ primary sources: [OpenSSL](https://security-tracker.debian.org/tracker/CVE-2026-63072),
[PCRE2](https://security-tracker.debian.org/tracker/CVE-2026-103111),
[xz advisory](https://github.com/tukaani-project/xz/security/advisories/GHSA-5qpq-xqfv-j9pg).

Registry referrers và legacy Cosign signature tag probes đều trả 404. Không suy ra
không có signature ở mọi hệ thống; **signer/issuer cryptographic verification vẫn
not_verified**. SLSA raw statement tải đúng digest và source files đúng pinned
checksums không thay thế verified signature/independent review.

License: model cards đúng revision và source LICENSE được rehash; embedding MIT,
reranker/TEI Apache-2.0. [Intel FAQ](https://www.intel.com/content/www/us/en/developer/articles/tool/onemkl-license-faq.html)
cho biết oneMKL dùng ISSL và cho phép redistribution theo terms. Tuy nhiên final
image inventory không có controlling MKL license/redist/third-party notices.
[Intel EULA index](https://www.intel.com/content/www/us/en/developer/articles/license/end-user-license-agreement.html)
nêu controlling agreement là bản bundled với software; không lấy website hiện tại
thay cho package-specific closure. OS copyright collection cũng không phải license
closure của toàn compiled Rust/native image. Không publish/distribute artifact.
[INTEL-SA-01155](https://www.intel.com/content/www/us/en/security-center/advisory/intel-sa-01155.html)
là finding Windows, không tự áp thành Linux finding; native scan không được gọi clean.

Dockerfile có MKL AVX512_E4 default và libfakeintel CPU patch. Static inspection
không xác nhận CPU instruction compatibility. [Intel reference](https://www.intel.com/content/www/us/en/docs/onemkl/developer-reference-c/2024-0/mkl-enable-instructions.html)
cho biết có AVX2 setting; chưa đổi setting hoặc chạy binary để thử.
Public publisher latest release hiện vẫn [v1.9.4](https://github.com/huggingface/text-embeddings-inference/releases/tag/v1.9.4);
không tự thay bằng floating tag hoặc một image chưa review để tránh findings.

## Verification và acceptance mapping

Tất cả Python commands dùng `infra/local/rag-fixture/.venv/Scripts/python.exe -B`
(Python 3.12.14), không cài dependency. Full command/evidence được giữ trong final
scope artifact; report dưới đây dùng relative paths trong workspace.

| Command/check | Exit | Evidence / ý nghĩa |
|---|---:|---|
| runtime_acquire_20261004.py | 0 | review/acquisition-final.json; 29 full-byte payload checks |
| runtime_inspect_20261004.py, final corrected pass | 0 | review/static-02/static-inspection-final.json; độc lập full rehash, diff_ids, static formats |
| runtime_security_review_20261004.py | 0 | review/security-01/security-review-final.json; review có findings, **không phải gate pass** |
| Offline acquisition boundary checks | 0 | review/guard-01/checks.json; 10 checks: URL/redirect denial, auth strip, no overwrite, mismatch/short/oversized bytes rejected and retained |
| delegated_verify.py acquisition-20261004-security-regression-01, 4 existing security test files | 0 | delegated-acquisition-20261004-security-regression-01.json; **16 passed**, outbound/DNS denied; không chứng minh model quality/security closure |
| runtime_acquisition_scan_20261004.py | 0 | acquisition-20261004-static-scan.json; 112 new files/4.912.616.889 bytes; 0 rule hits |
| verify_dependencies.py, validate_catalog.py, git diff --check | 0 | Exact app pins unchanged; catalog 241 tasks/10 phases; source preservation checked again in final scope |

Static scan là known canary/secret-pattern scan; compressed OCI được scan như
stored bytes, không mọi expanded member. Không chứng minh absence của mọi PII,
malware hoặc training-data memorization. Ignored runtime/credentials không đọc.
Report này và final evidence payload được scan bổ sung trước final scope write.

| AC / gate | Status |
|---|---|
| Exact acquisition scope, revisions, sizes, full bytes/checksums | passed |
| Independent actual-byte and uncompressed image digest verification | passed |
| Static model/config/header/offset checks, safe archive handling | passed |
| Dependency install/lock/config/corpus/pointer safety boundaries | passed trong scope đã thực hiện |
| Full compiled SBOM, vulnerability reachability/severity review, native license closure, verified signer | **not_verified** |
| Model load/inference/production adapter acceptance | **not_verified; chưa thực hiện** |
| Whole RAG production upgrade | **blocked**, chưa nghiệm thu |

## Exact blockers và bước tiếp theo

**B-RUNTIME-ACQUISITION đã giải quyết** cho đúng immutable artifacts này.
**B-RUNTIME-SECURITY** còn thực sự mở. Cần Engineering Security Lead / independent
reviewer disposition gắn với exact image digest, Cargo findings và Debian snapshot;
compiled SBOM/provenance verification và MKL notices/terms phù hợp version.
Không tự downgrade findings hoặc ký acceptance thay người review độc lập.

Authority: `SEC-SDLC-002` yêu cầu license/transitive-risk review và SBOM update;
`SEC-SDLC-004` cấm unresolved Critical/High nếu không có valid exception;
`SEC-CTRL-019` yêu cầu pin/scan/sign/provenance; `SEC-CTRL-029` không cho control owner
là sole verifier cho high-risk control. `SEC-LAUNCH-012` yêu cầu independent review
và vulnerability triage. Nếu reviewer chọn bounded exception, `SEC-CTRL-026` bắt
buộc control/scope/reason/compensating controls/residual risk/owner/expiry ≤90 ngày;
approval chung không tự sinh các dữ kiện hoặc thay đổi policy đó.

Đầu vào cụ thể có thể là: (a) signed review/VEX + compiled SBOM và license evidence
cho đúng digest này; hoặc (b) vetted private service/runtime bundle đã review, có
immutable digest, exact model-file manifests, endpoint/OpenAPI/auth secret-reference
metadata và allowed synthetic scope. Không gửi secret/token vào chat.

Sau security disposition, chuẩn bị exact live approval cho isolated smoke đã mô tả
ở candidate: một model/lần, 4 CPUs/5 GiB, synthetic ≤128 tokens/item, localhost
18081/18082, riêng network/container names, model mount read-only, no DB egress,
validated CPU instruction setting. Chưa áp dụng settings hay chạy scope này.
Production deadline/quality/8192-token envelope không thể nghiệm thu bằng smoke.

EMBED-002/RERANK-002 phụ thuộc DEPS-001 runtime gate; không mở objective đó hoặc
downstream trước accepted dependency (`DEC-019`). Những phần độc lập CONTEXT-003 /
RETRIEVE-001 đã triển khai ở lượt trước, final 679-pass evidence giữ nguyên;
không kể historical pass như một live-model test hiện tại.

Hai external inputs trước đó vẫn thiếu: reviewed institution/issuer binding và
trusted resolver cho role/revocation/audience/faculty/program; reviewed corpus
snapshot/source-version/chunk/scope/provenance và owner review để xây active 1024
index/gold. Không cấp default grants hoặc dùng ba legacy chunks để nghiệm thu gold.
Không đọc sealed test text. Không đổi requirements/thresholds để bypass DAG.

## Preservation

Không sửa existing file của baseline lượt này. Final scope:
`infra/local/rag-fixture/acquisition-20261004-final-scope.json` ghi exact new file list,
mọi hash và command/exit/evidence; self hash excluded, ignored runtime/credentials
excluded. Pre-existing staged/dirty/untracked/deleted state được giữ. SQL/corpus,
fixture rows/indexes/active pointer không bị truy cập hoặc mutation trong lượt này.
Pipeline tiếp tục abstain an toàn; không claim production-ready.
