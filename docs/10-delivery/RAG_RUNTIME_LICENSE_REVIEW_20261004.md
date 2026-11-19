# RAG runtime — exact MKL license evidence supplement, 2026-10-04

## Objective và kết quả

Direct objective: tiếp tục runtime review frontier của RAG production upgrade,
bổ sung package-specific license/notices và byte binding cho MKL. Technical
inspection hoàn thành trong scope này; **runtime security gate và toàn bộ
production upgrade vẫn blocked**, không có dependency nào được đổi thành accepted.

Human đã cho phép tiếp tục xử lý và trực tiếp xác nhận **chưa có** independent
reviewer/signed packet, trusted institution/issuer/resolver và reviewed corpus.
Đây là missing external inputs đã xác nhận, không phải một câu hỏi approval chung
đang chờ trả lời. Quyền thực hiện kỹ thuật không tạo ra danh tính reviewer, signed
acceptance, institution facts hoặc knowledge-owner review.

Image được đối chiếu vẫn là
`ghcr.io/huggingface/text-embeddings-inference@sha256:8419f533857b503ebf6ec292a95d4f1cf9c0464ac8b8abeef39518cf110e5726`,
source `e80ef225ed0e6cb1717ce632a6a84b6cf211bb67`.

## Acquisition và binding cụ thể

Đọc hai Intel public Packages.gz indexes qua HTTPS, lưu nguyên bytes/checksums.
Parser xử lý cả stanza có Filename trước Package; không dựa vào field order.
Chỉ đọc/archive inspection; không cài Debian packages, chạy maintainer scripts,
deserialize model, load Docker image, launch/infer hoặc access database.

| Package | Exact version | Archive bytes | SHA-256 |
|---|---|---:|---|
| intel-oneapi-mkl-common-2024.0 | 2024.0.0-49656 | 21,890 | ec2b67813739fa4a2895f63479a41acba2174afe2d0cb8a0c1c9119d1317d8ef |
| intel-oneapi-mkl-common-devel-2024.0 | 2024.0.0-49656 | 4,590,304 | adbf0ea946f63946d29b7f9c750c38a42ea7a65d8c81655b268aa2c7bb908192 |
| intel-oneapi-common-licensing-2024.0 | 2024.0.0-49406 | 30,746 | 9f9c8a12fc0bc82ab5b71e118e66745eff23f42224eba304068225b366cd74b6 |
| intel-oneapi-mkl-2024.0 | 2024.0.0-49656 | 164,130,774 | 10a86e24051d6ef4a80fd839c570e629190638a3c0ac9bcca99ab855f534b959 |

Các checksums/size khớp Intel index. Public origins:
[amd64 index](https://apt.repos.intel.com/oneapi/dists/all/main/binary-amd64/Packages.gz),
[all index](https://apt.repos.intel.com/oneapi/dists/all/main/binary-all/Packages.gz).
Full URLs của từng archive và metadata/dependency edges nằm trong evidence JSON.
Đây là content binding qua public HTTPS, **chưa phải** verified package/repository
signature. Các `_gpgorigin` members được giữ trong archive và hash riêng;
không có GPG/scanner mới được cài hoặc dùng.

Acquired tám license/notice documents: MKL license.txt, sáu third-party-programs
files (benchmarks, IPP, oneMKL Interfaces, OpenMP, safestring, general), generic
oneAPI license.htm; thêm một toolkit filelist, tổng chín selected text files.
Original bytes được giữ nguyên. OpenMP notice có encoding Latin-1 được chấp nhận
chỉ với exact path/hash; generic HTML khai báo windows-1252 và cũng được khóa
exact path/hash. Không dùng unrestricted encoding fallback. Common-devel có
2,177 entries nhưng không có selected licensing/redist filename; không suy ra
toàn bộ static redistribution inventory đã đầy đủ.

Runtime archive được stream trong memory: 38 regular files, tổng declared member
payload 1,303,994,426 bytes; không ghi expanded members vào filesystem.
**9/9 MKL shared objects có SHA-256 khớp image inventory**:
libmkl_intel_lp64, libmkl_intel_thread, libmkl_core, libmkl_vml_def, libmkl_def,
libmkl_vml_avx2, libmkl_vml_avx512, libmkl_avx2, libmkl_avx512 (đều `.so.2`).
Từng package path, image path, size và hai hashes được giữ trong binding JSON.

SHA-256 của `license-evidence.json`:
`0717587bf4636354b222dc7031f57254febaf96d8f38533c100c970a507b5b72`.
SHA-256 của `runtime-library-binding.json`:
`7f745be39c8562ad7a7307bd7bed5ccc7c4ce07679ecd470399eeff23fa6a6f0`.
SHA-256 của `review-addendum.json`:
`8163f9ac9b9e5b72f3190c0667eaef7490d45c4f57c193771f46ec3f13cc762e`.

## Những điểm reviewer cần giải quyết

Package MKL license.txt là Intel Simplified Software License October 2022.
Nội dung yêu cầu giữ copyright/terms khi redistribution và có điều khoản hạn chế
modification/alteration, bao gồm operation during execution; third-party terms
cần được xét riêng. Đối chiếu publisher:
[Intel license](https://cdrdv2-public.intel.com/749362/intel-simplified-license-software-october-2022.pdf),
[oneMKL 2024.0 notices](https://www.intel.com/content/www/us/en/docs/onemkl/developer-reference-dpcpp/2024-0/notices-and-disclaimers.html).

Pinned Dockerfile tạo libfakeintel.so, đặt LD_PRELOAD và override
mkl_serv_intel_cpu_true. Vì vậy reviewer cần disposition cụ thể cho hành vi này
so với controlling license; byte match của shared objects không giải quyết câu
hỏi operation override. Đây là review question, không phải kết luận pháp lý hay
security exception do implementer tự chấp nhận.

Builder pin tên/version MKL, không pin archived Debian digest. Generic licensing
dependency version lấy từ retained public repository, chưa có historical build
attestation chứng minh chính bản đó được resolver dùng. Chín shared objects đã
bound; static components/router compiled graph chưa có full SBOM. Final image
chưa chứng minh đã đóng gói đủ notices. Verified signer/issuer/provenance,
compiled Rust/native SBOM, independent license/risk disposition và production
notices packaging vẫn thiếu.

Giữ nguyên 10 affected Cargo entries/8 advisory IDs và 192 Debian pending entries
từ frontier trước; không coi thư viện khớp publisher bytes là vulnerability clean.
Review packet cũ được supplement bằng `review/license-04/review-addendum.json` và
`handoff-readiness.json`; reviewer/signature vẫn null, exceptions/acceptance
changes vẫn rỗng.

## DAG và blocker cuối

Không có thay đổi acceptance của 71 RAGUP nodes. DEPS-001 chưa được accepted;
EMBED-002/RERANK-002 và downstream vẫn cần accepted dependencies theo DEC-019.
Trusted context/retrieval thiếu institution/issuer binding và reviewed resolver.
DATA shards/gold/active 1024 index thiếu reviewed corpus snapshot và owner review.
Những input này đã được human xác nhận chưa có.

Normative clauses: SEC-SDLC-002/004, SEC-CTRL-019/029, SEC-LAUNCH-012, approved
scope/source contracts và DEC-019. `docs/10-delivery/RACI.md` separation of duties
và one-person adaptation quy định agent không tự approve security exception hoặc
production gate; institutional/legal/security roles không được AI mô phỏng.
Vì vậy chưa mở live runtime hoặc production acceptance từ quyền kỹ thuật chung.

Đã tìm trong governance/specs/bootstrap/delivery/typed-context sources, pinned
upstream tree/workflows/releases, public signature discovery, acquired image,
Intel package metadata và exact package bytes. Việc còn cần người/đơn vị bên ngoài:
signed independent security/license disposition với compiled SBOM/provenance,
institution/issuer/resolver metadata đã review và reviewed corpus. Equivalent
vetted private runtime bundle vẫn là alternative được mô tả trong packet trước.

## Verification và preservation

Chỉ dùng Python fixture 3.12.14 với `-B`. Canonical/reparse/write-scope checks,
Git status/diff và mới tạo exclusive baseline trước mutation. Rehash 1,386 entries
của previous frontier final scope pass. New baseline gồm 1,387 pre-existing files,
bao gồm chính previous final-scope; SHA-256:
`b3c59b092549428cdaf8b9dfee8638afceceb0c983f677f2b93f34df44b19faa`.

| Command/check | Exit | Evidence/result |
|---|---:|---|
| verify_dependencies.py preflight | 0 | Exact reviewed dependency pins/closure/hashes |
| tasks/validate_catalog.py, initial wrong path | 2 | Read-only invocation failure; correction retained in handoff-readiness.json |
| tasks/tools/validate_catalog.py | 0 | 241 tasks, 10 phases; no catalog mutation |
| git diff --check preflight | 0 | Existing CRLF warnings retained; no pre-existing file rewritten |
| delegated_verify.py license-20261004-parser-01 | 0 | 9 passed; no skip/warning; outbound/DNS denied |
| runtime_license_review_20261004.py, license-02 | 1 | Exact OpenMP notice not UTF-8; inspection-failure.json + bytes retained |
| Parser tests label parser-02 | 0 | 9 passed after exact OpenMP encoding allowance |
| Inspection, license-03 | 1 | Generic HTML windows-1252; bytes/failure retained |
| Parser tests label parser-final-03 | 0 | 10 passed; added rejection check for unknown non-UTF8 document |
| Inspection, license-04 | 0 | Three documentation archives, nine selected files; two scoped encoding repairs |
| bind_runtime(), first attempt | 1 | Exact package exceeds initial resource bound; runtime-binding-failure.json retained |
| Metadata-only package inventory | 0 | Exact rehash; 38 files, payload 1,303,994,426; max member 182,190,512 |
| bind_runtime(reuse_verified_archive=True) | 0 | Exact rehash + scoped measured bounds; 9/9 image library matches; no archive overwrite |
| Final dependency/catalog/diff/scope/scan | Final scope records actual exits | Fresh retained final evidence; no broad regression repeated |

Reproduction: script main uses fresh output and intentionally refuses existing
license-04. Do not run it blindly. Binding command imports the module and calls
`bind_runtime(reuse_verified_archive=True)` only when archive exists and binding
output does not; it rehashes the exact archive first. Existing evidence is never
overwritten. Parser test target is
`tests/unit/runtime_review/test_license_review.py` through delegated_verify.py
with a fresh label and retained temp outputs.

Changed scope: new inspection script, parser tests, this delivery report, fresh
baseline/test/scan/final-scope files and retained license-02/03/04 evidence only.
All pre-existing dirty/untracked state is preserved; exact preservation hashes,
new-file paths, final command exits and scan counts are recorded in
`infra/local/rag-fixture/license-review-20261004-02-final-scope.json`.
Static canary/secret-pattern scan is not malware, comprehensive PII or license
certification. No commit/push/deploy/reset/clean/delete, environment/security
control changes, runtime installs or live provider/model tests performed.
