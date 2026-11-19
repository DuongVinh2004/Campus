# Campus 24/7 — Kết quả triển khai kho tri thức, 23/10/2026

Luồng quản trị mới đang chạy tại <http://127.0.0.1:8015/knowledge/sources>. Upload, job nền, BGE thật, duyệt bằng tài khoản độc lập, preview/xác nhận, release và chatbot đã đi hết luồng với tài liệu kiểm thử Sao Mai. Đây là bằng chứng chức năng local với nội dung synthetic; chưa phải nghiệm thu chất lượng tri thức HUCE hoặc hoàn thành toàn bộ spec.

120 phiên bản HUCE và 2.826 vector đã được nhập vào PostgreSQL ở trạng thái chờ duyệt. Không tự chuyển nhãn duyệt lịch sử thành phê duyệt mới, không kích hoạt hàng loạt. Bốn child chunks thuộc ba parent chưa chứng minh được ánh xạ bản gốc được giữ ngoài đợt import. Kho đầu vào, lịch sử, các bản build và bằng chứng lỗi được giữ nguyên.

## 1. Binding và phạm vi đang chạy

```text
UI /knowledge/sources và catalog /knowledge
    → API loopback :8015
    → PostgreSQL :55437 / campus247_knowledge_local_20261023
    → release membership + immutable artifacts + review bindings
    → PostgreSQL FTS / exact pgvector → RRF → BGE reranker
    → graph chat hiện hữu → citation kiểm quyền hiện tại

Upload → durable job → một worker nặng → parser con → BGE dùng chung
Desired pointer → runtime prepare/load → ack đúng boot/generation, TTL 20 giây
```

- Tenant local: `huce-local-public`, campus HUCE. Form upload lát đầu cố định FIT / PUBLIC, sinh viên và quản trị; không đại diện đầy đủ mọi chương trình/quyền trong trường.
- PostgreSQL portable 17.11; pgvector 0.8.7; migrations mới `0015`, `0016`, `0017` nằm sau head cũ `0014`. Không downgrade hoặc viết lại dữ liệu lịch sử để kiểm thử.
- BGE-M3 revision `5617a9f61b028005a4858fdac845db406aefb181`, vector 1024 chiều chuẩn hóa L2; reranker v2-m3 revision `953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e`.
- Model services dùng guard hiện hữu, CPU 4 core / job 5 GiB, batch embedding 1; giữ toàn bộ bộ đếm và ngân sách kế thừa. Không tăng cap hoặc reset accounting. Namespace đang chạy: `infra/local/rag-advanced-models-20261013-18`.
- SQLite bền vững riêng cho hội thoại, trạng thái actor/consent và action idempotency. Nếu marker actor tồn tại nhưng DB mất thì khởi động thất bại, không âm thầm dùng kho thu hồi rỗng.
- UI phục vụ từ snapshot `frontend-knowledge-v4`, backend proxy cùng origin trên 8015. Không dùng trực tiếp 3015 cho luồng có API.
- Release synthetic đang phục vụ khi kiểm chứng: `01a166de-4fbc-7988-9cc5-c6448b35e0bb`, generation 5; version `01a166dd-fc48-76bf-a6ba-7fcca0ae5714`.

Kiểm tra bàn giao cuối `handoff-20261023T073400269210.json` xác nhận serving đang hoạt động, projection có 118 nguồn / 124 version (bao gồm các fixture), 27 file Python parse được và contract có 16 paths. Bộ đếm native kế thừa: HTTP 16.099 / 20.000, inference 9.962 / 10.000, tokens 2.162.029 / 5.000.000; còn 38 lượt inference tại thời điểm ghi nhận, không phải một ngân sách mới.

Đây là launcher phát triển: KA01 tạo tài liệu, KA02 duyệt/xác nhận, SV01 kiểm quyền sinh viên. Các tài khoản synthetic dùng vai trò thật trong ứng dụng local; không phải SSO production. Listener chỉ loopback. Không dùng launcher này để công bố dịch vụ ra mạng.

## 2. Phần code đã có

| Phần | Kết quả |
|---|---|
| Intake/storage | Multipart stream trực tiếp vào SSD, giới hạn 50 MiB, kiểm MIME/prefix/UTF-8, hash, canonical path và reparse; file ghi độc quyền. Trả 202 và job/version thật; scoped idempotency. |
| Queue | PostgreSQL `SKIP LOCKED`, lease/heartbeat/fencing, checkpoint theo input/config/output hash, retry/cancel, admission một job nặng trên cùng DB qua các tenant. Không giữ transaction khi parse/gọi model. |
| Parser | TXT UTF-8 và PDF có chữ bằng pypdf; process con không mạng, giới hạn trang/ký tự/deadline; thiếu chữ/scan/mã hóa thành ngoại lệ. Giữ page/block locator, không bịa trang TXT. |
| Index | Lưu riêng evidence và toàn input embedding/hash; model/profile cố định. FTS và exact pgvector lọc quyền/tenant/release/hiệu lực trước LIMIT; RRF rồi rerank tối đa 6 ứng viên. Parent trả về đủ đoạn trong hạn mức context. |
| Review/release | Review độc lập gắn rendition + metadata + processor hash. Membership cố định và seal; build giữ thành viên cũ. Preview/token, expected generation/CAS, explicit confirmation, audit/outbox. |
| Runtime | Snapshot cố định theo lượt; desired/serving riêng; ack chỉ sau prepare thành công. Kiểm lại quyền/thu hồi trước lưu/truyền kết quả và khi đọc nguồn; rollback không xóa revocation. |
| Metadata version | Bổ sung căn cứ/ngày hiệu lực tạo version bất biến mới, tái dùng vector đã kiểm, giữ bản cũ và buộc duyệt lại. Không sửa âm thầm nội dung đã duyệt. |
| UI | Upload, tiến độ/lỗi thật, thư viện có lọc tên không dấu, original/rendition, duyệt, search-preview, preview/xác nhận activate/rollback/revoke, trạng thái ack. Trang `/knowledge` chỉ báo published khi có bản thực sự được serving. |
| Contract | Annex `contracts/openapi/knowledge-platform.openapi.json` xuất từ API đang chạy: 16 paths; ghi rõ multipart JSON, idempotency và auth. Không ghi đè OpenAPI tổng đang có thay đổi trước tác vụ. |

Worker chạy bằng entrypoint mới `scripts/knowledge_platform.py worker`. `services/worker/src/campus247_worker/main.py` cũ vẫn là stub; chưa đổi entrypoint triển khai chung. Parser/chunker và graph hiện hữu được tái sử dụng khi phù hợp; các adapter platform mới tách khỏi kho JSON cũ.

## 3. Kiểm chứng và bằng chứng

Các đường dẫn dưới đây tính từ workspace. Thư mục `infra/local/knowledge-platform-20261023` được ignore để không đưa credentials, upload, hội thoại và DB runtime vào Git; bằng chứng vẫn còn trên đĩa.

| Kiểm chứng | Kết quả / bằng chứng |
|---|---|
| Inventory trước triển khai | 8.703 file / 924.731.801 byte; `inventory-20261023T032641114754.json`. Khi bắt đầu không có API/frontend cũ đang lắng nghe; không có baseline chat live để so tốc độ. |
| HTTP end-to-end thật | `smoke-20261023T033822779604.json`: 10 kiểm tra đạt; upload replay, student 403, worker/BGE thật, original hash/locator, cấm self-review, pgvector/RRF/rerank, CAS, ack, chat/citation, revoke và rollback. |
| Kiểm chứng qua browser | KA01 upload → KA02 duyệt/preview/xác nhận → SV01 hỏi và mở nguồn. `ui-release-20261023.png`, `ui-citation-20261023.png`, `ui-chat-20261023.png`. Nội dung Sao Mai có nhãn kiểm thử, không phải quy định trường. |
| UI v4 sau nạp lại | Lọc `so tay sinh vien` tìm đúng tên có dấu; hiện original hash, locator, CHƯA XÁC MINH và ngoại lệ còn mở; release synthetic có ack. `ui-library-v4-20261023.png`. Không phê duyệt tài liệu HUCE trong lần này. |
| Regression backend | 114 passed / 6,58 giây; `tests-regression-03.xml`. Bao gồm API chat/citation/knowledge, stream result, ingestion và test PostgreSQL/BGE mới. |
| Admission qua tenant | 1 passed; `test-global-admission.xml`: tenant B không nhận job nặng khi lease tenant A còn sống, nhận được sau A kết thúc. Tổng các kiểm thử backend đã chạy ở lần cuối: 114 + 1, không phải một suite 115 duy nhất. |
| Frontend | 3 test `KnowledgePlatform.test.tsx` passed; `tsc --noEmit --incremental false` exit 0; build v4 exit 0, 17 routes. Build receipt: `frontend-knowledge-v4-build.json`. |
| Auth sau restart | `runtime-revocation-20261023T072518439181-verified.json`: student bị từ chối, Origin sai bị chặn, logout giữ hiệu lực sau restart API, release/generation không đổi. Receipt gốc có token đã thu hồi, chỉ nằm trong runtime riêng, không đưa vào báo cáo/contract. |
| Backup/restore | `logical-backup-20261023072751626073/verification.json`: passed, metadata khớp hash sau restore DB mới, 241 artifacts của tenant chính khớp checksum; SQLite hội thoại, actor/consent, idempotency được backup và quick-check/hash. Snapshot từng store nhất quán riêng, chưa phải transaction phân tán xuyên PostgreSQL/SQLite. |

Lệnh backend đã chạy:

```powershell
$env:KNOWLEDGE_PLATFORM_LIVE_TESTS='1'
& 'infra/local/rag-fixture/.venv/Scripts/python.exe' -B -m pytest tests/knowledge_platform tests/api/test_chat_sse.py tests/api/test_citation_source.py tests/api/test_knowledge_admin.py tests/unit/conversation/test_stream_result.py tests/unit/ingestion --basetemp=infra/local/knowledge-platform-20261023/pytest-regression-03 -o tmp_path_retention_count=100000 -o tmp_path_retention_policy=all -q -p no:cacheprovider --junitxml=infra/local/knowledge-platform-20261023/tests-regression-03.xml
```

Khi chạy lại phải chọn tên basetemp/XML mới; không tái dùng hay dọn thư mục kết quả cũ. Test ghi tenant mới trong DB local, không reset/drop/truncate. Test BGE dùng ngân sách thật còn lại; không lặp không cần thiết.

Một smoke đầu đã phát hiện citation TXT trả 503 do locator chứa khóa trang `None`; đã sửa thống nhất locator và smoke sau đạt. Bằng chứng lỗi `smoke-20261023T033611214750.json` được giữ. Bản frontend v1 lỗi cũng được giữ.

Hai test cũ của `SourceOperations.test.tsx` thất bại vì mock tạo `new URL(relativePath)` trong khi API client hiện hữu dùng URL tương đối; không sửa phần thay đổi có sẵn để làm xanh test. Không kết luận toàn bộ frontend suite đã đạt.

## 4. Quan sát tài nguyên

`resource-observation-20261023T072624033417.json`: cửa sổ 11,89 giây, lấy mẫu 200 ms, hai lượt chat tuần tự trong lúc một job TXT synthetic chạy nền. Job SUCCEEDED; một câu answered/grounded_answer, một câu abstained/safe_refusal.

| Đại lượng | Thực đo |
|---|---:|
| Thời gian HTTP hoàn tất lượt chat thứ nhất | 5.609 ms |
| Thời gian HTTP hoàn tất lượt chat thứ hai | 4.032 ms |
| RAM khả dụng thấp nhất toàn máy | 3.504.431.104 byte, khoảng 3,26 GiB |
| Model process tree peak working set trong mẫu | 3.116.961.792 byte |
| API tree | 137.973.760 byte |
| PostgreSQL tree | 288.313.344 byte |
| Worker tree | 87.207.936 byte |
| Frontend tree | 86.904.832 byte |

Working set giữa process có thể chứa trang chia sẻ, không cộng thành physical RAM duy nhất. Không quan sát OOM/mất job trong cửa sổ này. Hai câu hỏi không đủ để công bố p50/p95, SLA, ổn định dài hạn hoặc khẳng định AC-10 đã đạt trên mọi máy 16 GB. Parser peak/resource telemetry dài hạn và queue-age dashboard chưa hoàn chỉnh.

## 5. Import HUCE

Corpus fingerprint `5d0cc896e688d54210154d1c0a83787740ae19ad8a174457eda4e83dc6d12093`; index nguồn SHA256 `14c6851a7de3a509e1dc71ac78af50961fa3154003e0c234bccc25f53c757526`.

- Loader cũ kiểm manifest/input/model/profile và ready/withdrawn trước khi import. 1.009 parent, 2.830 child trong corpus; 1.006 parent chứng minh được original mapping bằng hash.
- Adapter legacy giữ nguyên input embedding, parent context, provenance và locator. Không giả rằng output của chunker mới tương thích chỉ vì cùng 1024 chiều.
- 120 version / 2.826 vector được stage, không gọi thêm model, không tạo phê duyệt con người, không activation. Ngày hiệu lực chưa chứng minh được giữ UNKNOWN.
- Lần chạy lại trả cả 120 `REUSED_EXISTING`; không thêm version/vector/call. Bằng chứng: `huce-import-preflight-20261023T040549782553.json` và `huce-import-preflight-20261023T041525565523.json`.
- Chưa nhập bốn child từ ba parent: hai parent về Quyết định 924 học phí 2026–2027 dựa trên hai ảnh scan; một parent khung chương trình kỹ sư CNTT FIT. Manifest supplemental chưa ánh xạ một original artifact/hash đủ rõ trong inventory ban đầu. Không chọn một file gần giống để ép import. Cần adapter bundle/receipt đúng nguồn trước khi nhập.
- Tài liệu đã nhập vẫn cần xác minh hiệu lực/phạm vi, xử lý issue và duyệt độc lập trước khi đưa vào release. Có tài liệu mang khác biệt giữa sổ tay và quy chế gốc; không tự hòa trộn hoặc phê duyệt để mở cutover.

## 6. Runbook local

Chạy từ workspace `C:\Users\Duong Vinh\Vinh`. Trước khi khởi động, kiểm listener/process; không start trùng, không dừng PID chưa xác minh. Các lệnh dưới là entrypoint, không phải lệnh reset môi trường.

```powershell
# API (cần PostgreSQL và BGE đang sẵn sàng)
& 'infra/local/rag-fixture/.venv/Scripts/python.exe' -B -u scripts/knowledge_platform.py serve --port 8015 --frontend-port 3015 --generation

# Worker, một instance cho tenant local
& 'infra/local/rag-fixture/.venv/Scripts/python.exe' -B -u scripts/knowledge_platform.py worker

# Phục vụ snapshot đã build, nếu port 3015 chưa có listener
& 'infra/local/rag-fixture/.venv/Scripts/python.exe' -B -u scripts/knowledge_platform_frontend.py serve --name frontend-knowledge-v4 --port 3015

# Kiểm kê import chỉ đọc; --stage chỉ dùng khi thật sự muốn bổ sung version chờ duyệt
& 'infra/local/rag-fixture/.venv/Scripts/python.exe' -B scripts/knowledge_platform_import.py

# Backup mới và restore kiểm chứng vào tên DB mới, giữ toàn bộ đích
& 'infra/local/rag-fixture/.venv/Scripts/python.exe' -B -u scripts/knowledge_platform_logical_backup.py
```

Cluster đang có nằm ở `.tooling/knowledge-postgres-20261023/cluster`; không gọi `bootstrap-local`/initdb lại. Connection record riêng `infra/local/knowledge-platform-20261023/local-connection.json` chỉ nhận đúng host/port/database/user đã tạo. Không in password/DSN hoặc sao chép vào mã nguồn. Native `pg_ctl` có thể start lại cluster hiện có nếu PostgreSQL đã dừng và port 55437 trống; không tạo service hệ thống.

Model launcher `scripts/serve_rag_models.py` giữ resource authorization và predecessor receipts. Nếu model dừng, cần chọn namespace mới nối predecessor hiện tại qua launcher, trong cap hiện có; không dùng lại state để xóa/reset counters. Không khởi động model thứ hai trong khi model hiện tại còn chạy. Native inference cap kế thừa là 10.000; sau lần đo còn khoảng vài chục lần gọi, không đủ rebuild toàn bộ corpus 2.830 chunks. Khi guard báo hết ngân sách, dừng model work và báo đúng lý do.

Thao tác trên UI:

1. Mở `Phiên phát triển local`, đăng nhập KA01, upload PDF có chữ hoặc TXT UTF-8 được phép. Thấy version/job và đợi trạng thái thực. SUCCEEDED ở bước xử lý không có nghĩa đã phục vụ.
2. Chọn tài liệu, tải original và đối chiếu rendition/locator. Nếu chưa rõ hiệu lực, bổ sung ngày và căn cứ bằng version mới; bản mới buộc duyệt lại. Scan/issue chưa hỗ trợ phải giữ chờ xử lý.
3. Dùng KA02 để ghi nhận đối chiếu và duyệt. Tạo release; search-preview chạy BGE thật trên ứng viên. Chỉ dùng các tài khoản thử cho nội dung kiểm thử, không coi thao tác tự động là quyết định phê duyệt chính sách trường.
4. Xem trước xuất bản, đọc diff/generation và xác nhận. Chờ runtime ack hiện tại; ack mất/hết hạn không báo đang phục vụ. Mở chat, hỏi và mở nguồn để kiểm version/locator.
5. Thu hồi tài liệu qua preview/xác nhận; rollback qua release cũ. Hai thao tác có audit, không xóa artifact và không gỡ trạng thái thu hồi. Retry/cancel giữ original/checkpoint.

Backup native bằng `pg_dump.exe` bị Windows Application Control chặn với WinError 4551. Không đổi tên executable hoặc sửa/bỏ chính sách. Phương án SQL/API ở trên đã restore thành công qua migrations và constraints/triggers bình thường, không disable protection. Python `.venv` gốc cũng bị policy chặn; interpreter fixture hiện hữu được phép đã dùng. Đây là hạn chế môi trường được giữ nguyên.

Restore kiểm chứng gần nhất tạo DB riêng `campus247_knowledge_logical_20261023072751626073`. Không có lệnh tự chuyển app sang DB restore hoặc ghi đè kho hiện tại. Backup artifacts chỉ bao phủ tenant vận hành local; artifacts test riêng ở namespace test vẫn được giữ nguyên tại chỗ. Cần thiết kế phục hồi đồng bộ đa store trước production.

## 7. Trạng thái nghiệm thu còn lại

| AC | Bằng chứng hiện có và giới hạn |
|---|---|
| 01 | Upload TXT từ UI đạt; parser/intake PDF có chữ có test. Chưa chạy một PDF HUCE mới qua toàn bộ browser flow để nghiệm thu định dạng. |
| 02 | Checkpoint/retry và khởi động lại worker giữ dữ liệu; chưa có chiến dịch kill/restart giữa từng ranh giới artifact/DB commit. Chưa tuyên bố đạt đầy đủ. |
| 03 | PostgreSQL test lease hết hạn, fencing owner cũ, cancel/retry và checkpoint reuse đạt; admission qua tenant đạt. |
| 04 | TXT/PDF text; scan/mã hóa/missing text fail closed. Chưa có Docling/Tesseract, DOCX hoặc UI sửa OCR/bảng. Chưa đạt. |
| 05 | Kiểm quyền trước parse/search/citation, student original 403, scope lọc cả FTS/vector/parent, kiểm lại khi stream. Chưa phải ma trận toàn bộ quyền thực tế của trường. |
| 06 | Hash-bound independent review và metadata version mới buộc duyệt lại có test đạt. |
| 07 | CAS/idempotency, desired/serving và ack thật đạt trong smoke/UI; chưa phủ đủ fault injection mọi giai đoạn activation. |
| 08 | Revoke chặn citation, rollback không phục hồi tài liệu đã thu hồi đạt trong smoke HTTP. Browser có điều khiển thao tác; chưa thực hiện chiến dịch browser riêng cho mọi nhánh revoke. |
| 09 | Có smoke BGE thật, câu có đáp án/không đủ bằng chứng. Chưa có bộ holdout HUCE với đáp án/locator kiểm chứng và đánh giá lỗi số liệu/hiệu lực toàn diện. Chưa đạt. |
| 10 | Quan sát đồng thời nhỏ ở mục 4; chưa có p50/p95/tải dài hạn hay thử OOM/crash toàn process tree. Chưa đạt đầy đủ. |
| 11 | Import mới có ánh xạ/checksum/cache reuse, idempotent, giữ dữ liệu cũ. Bốn child chưa ánh xạ bị giữ ngoài và có báo cáo; cutover HUCE chưa làm. |
| 12 | HTTP sync/Crawl4AI/scheduler và chính sách auto-publish chưa triển khai; chưa đạt. |
| 13 | Upload/duyệt/release/chat/citation synthetic qua UI đạt; catalog cùng DB runtime và phân biệt serving. Chưa nghiệm thu toàn bộ với dữ liệu HUCE đã duyệt. |

Các việc tiếp theo: hoàn thiện OCR/DOCX và đối chiếu phiên bản; reconciliation orphan chỉ báo cáo; pagination phía server thay giới hạn projection 200/50; import bundle ba parent còn thiếu; bộ đánh giá HUCE và xác minh applicability; sync có SSRF/allowlist/cursor/scheduler; fault injection và vận hành dài hạn. Chỉ kích hoạt HUCE sau review sản phẩm đúng quyền và kiểm chứng chất lượng ứng viên. Không gọi toàn bộ M2–M5 hoàn thành.

Workspace có nhiều thay đổi trước tác vụ; không thể gán toàn bộ diff so với HEAD cho lần triển khai này. Không commit, push, deploy production, reset/clean, xóa file/DB hoặc sửa các guard hiện hữu. Hai `.gitignore` mới chỉ giữ dữ liệu runtime ngoài Git; không xóa hoặc di chuyển dữ liệu trên đĩa.

## 8. Tiếp tục xử lý dữ liệu thật ngày 23/10/2026 — trạng thái có giới hạn

Phần này thay thế các nhận định hiện trạng serving/demo phía trên; các smoke cũ được giữ làm lịch sử, không phải bằng chứng kho HUCE đã sẵn sàng. **Chưa hoàn tất toàn bộ yêu cầu vận hành thật.**

### Kho đang phục vụ và dữ liệu mẫu

- API vẫn ở `127.0.0.1:8015`, PostgreSQL `55437`, DB `campus247_knowledge_local_20261023`, tenant `huce-local-public`. Không tạo lại/reset/overwrite DB.
- Release hiện tại `01a167ef-474f-7b88-9578-195d47e123a4`, generation **11**, policy generation **3**. Runtime đã ack lại sau restart; citation học phí đã lưu đọc lại được (200), phiên đã logout vẫn bị từ chối sau restart (401), principal khác chủ chat bị chặn đọc citation (404).
- Phục vụ hai nguồn: QĐ **924/QĐ-ĐHXDHN** về học phí 2026–2027, version `01a167c6-b6ca-77b2-a2a6-cefd66345d5d`; QĐ **2114/QĐ-ĐHXDHN** về an toàn thông tin, version `01a167eb-e62e-71d9-91ea-a9aedc888f0d`. Đây là phạm vi đã đối chiếu, không phải toàn bộ kho hay toàn bộ chính sách HUCE hiện hành.
- Cả ba version Sao Mai `01a166d4-998e-7439-9c89-4869678e41c9`, `01a166d6-9b6b-739b-8494-b20299f86cd3`, `01a166dd-fc48-76bf-a6ba-7fcca0ae5714` đều đã thu hồi. Thao tác mới dùng preview/confirmation của ứng dụng. Không xóa original, rendition, row, audit hoặc release lịch sử. Runtime vận hành chặn xuất bản/rollback nguồn fixture URI không phải HTTPS; catalog vận hành không trình bày chúng.
- Catalog thực tế có **117 nguồn / 125 phiên bản**, **122 phiên bản chờ duyệt** (bao gồm các bản trước của nguồn đã có successor). Không được hiểu số lượng nhập là số lượng đang phục vụ.

### Danh tính và phê duyệt

Người dùng trực tiếp xác nhận: “tạo 1 tài khoản chịu trách nhiệm này, tôi xác nhận”. Đã tạo `knowledge-owner`, issuer riêng `urn:campus247:issuer:local-owner`, cùng principal agent kỹ thuật tách biệt. Đăng nhập bằng mật khẩu, chữ ký phiên gắn issuer/tenant/subject/expiry, giới hạn thử sai; dùng lại durable session revocation. Thông tin đăng nhập ở `infra/local/knowledge-platform-20261023/owner-credentials.json`, ngoài Git, không in vào log/báo cáo.

Review mới ghi rõ **tự động do agent thực hiện theo ủy quyền chủ hệ thống, không phải xác nhận của cán bộ HUCE**. UI hiển thị ghi nhận review; không chuyển nhãn review lịch sử thành phê duyệt con người. Tài khoản local không phải SSO HUCE, không xác minh tư cách sinh viên hay cán bộ trường. Chủ hệ thống trực tiếp xác nhận ngày 23/10/2026 hiện chưa có SSO/OIDC và API học vụ được cấp quyền. Giữ phạm vi quản trị local và tra cứu nguồn HUCE công khai; không hỏi lại cho đến khi người dùng báo có kết nối.

`KA01/KA02/SV01`, `/v1/auth/demo-session` và `/local-session` không còn dùng được trên API vận hành (404). UI không tự tạo/đổi phiên demo, không nạp StoreProvider/catalog demo trong composition này, chỉ điều hướng chat/nguồn/đăng nhập đã nối thật. Chat quản trị có policy role/tenant riêng, không giả tài khoản sinh viên; citation vẫn kiểm owner và quyền nguồn hiện tại. Các dịch vụ assistant chỉ hỗ trợ synthetic không được ghép vào luồng chat này; nhánh lịch cá nhân/hồ sơ/đặt phòng/handover chưa có kết nối thật báo chưa thực hiện, không trả lịch hoặc receipt giả. Worker `main.py` đã nối vòng poll/lease/checkpoint thật thay cho CLI chỉ start rồi thoát.

### Original, metadata, vector và retrieval

- Đã ánh xạ hết **1.009 parent / 2.830 child** trong corpus legacy bằng inventory và acquisition receipt. Hai ảnh scan QĐ 924 được kiểm trực tiếp, SHA khớp ảnh embedded trong HTML publication gốc; không thay original bằng PDF dựng lại. FIT khớp đoạn HTML đã lưu; trang công bố cũng được đối chiếu. Nhập bổ sung hai version còn thiếu, giữ 120 version có sẵn; không có inference mới từ import.
- Hiệu lực QĐ 924: Điều 2 và ngày ký 10/06/2026 trên ảnh trang 1; bảng có phạm vi năm học 2026–2027, điều kiện khóa/chương trình/ĐVHT và phụ thu ở trang 2. Không tự đặt ngày kết thúc năm học.
- Audit original/rendition bằng hash trên 122 version. So khớp chuỗi toàn parent chỉ khớp hoàn toàn ba version; nhiều bản khác có layout/OCR/cột/bảng, prefix/suffix biên tập hoặc chú thích được thêm trước đây. **Không diễn giải phép so khớp chuỗi thất bại là toàn bộ nguồn giả**, và không duyệt hàng loạt từ kết quả này. Các nguồn đó vẫn cần đối chiếu riêng; ngày hiệu lực chưa có căn cứ vẫn UNKNOWN, gồm cả FIT (ngày đăng bài không bị dùng làm ngày hiệu lực).
- Với QĐ 2114, tạo rendition mới gồm **36 span nguyên bản**, không chứa lời dẫn/ghi chú agent. Bản v2 tái dùng **123 vector** với full input/hash/model/profile giữ nguyên; **15 child chỉ chứa ghi chú** giữ ngoài. Chỉ mục có thể chứa context phục vụ tìm kiếm, nhưng evidence chỉ chứa văn bản gốc. Hiệu lực 31/12/2024 được đối chiếu trang 1, Điều 2. Không tuyên bố đã xác minh mọi căn cứ luật được tài liệu dẫn hoặc mọi thay đổi ngoài snapshot.
- Lần v1 gửi toàn parent vào reranker vượt envelope được phát hiện bằng live canary. Đã rollback qua preview/confirmation về bản học phí trong lúc sửa. V2 map child vào span gốc để rerank, giữ full parent làm evidence. Tokenizer/envelope đã duyệt kiểm offline 123 span, tối đa **294/900 token** với câu hỏi canary. Không bật truncation, đổi model, tăng cap hay khởi động model trùng. Bản processor v1 bị chặn tái xuất bản/rollback (409); lịch sử được giữ.
- Loại logit BGE không dương/nonfinite trước generation; kiểm năm học tường minh không khớp; kho không có ứng viên đủ quyền không gọi model. Câu học phí thiếu khóa/chương trình/năm học trả clarification cụ thể, không chọn một mức tiền.
- Giới hạn rerank **3 ứng viên** trong composition local để giới hạn tài nguyên/cost; không hạ evidence/auth/claim-verification threshold. Đây là lựa chọn có rủi ro recall, chưa có nghiệm thu toàn corpus. Model/revision BGE-M3 `5617a9…b181`, reranker `953dc6…e41e`, ports `18081/18082`, namespace `rag-advanced-models-20261013-18` giữ nguyên.

### Kiểm chứng thực tế và lỗi đã xử lý

- Câu CNTT CN chính quy K71, năm học 2026–2027: trả **592.500 đồng/tín chỉ**, phụ thu Anh/Pháp ngữ K71 **17.000.000 đồng/năm**, citation trang 2, hash/version/release đúng. Đọc source owner 200, anonymous 401.
- QĐ 2114: trả đúng điều khoản thay mật khẩu tối thiểu **01 lần/06 tháng**, citation source 200.
- Câu “học phí ngành công nghệ thông tin”: hỏi rõ khóa, chương trình/hệ và năm học, không gọi BGE. Yêu cầu lịch cá nhân báo chưa kết nối và chưa thực hiện, không có lịch/receipt demo.
- Câu Sao Mai đã trả 0 search hits khi kiểm trên release học phí. Sau cùng, mọi fixture đã thu hồi và rollback release fixture bị chặn 409. Không tiêu thêm BGE để lặp lại ca âm khi ledger gần hết.
- Browser login owner và catalog thật đạt. Browser còn phát hiện parser citation làm rơi `release_id`, `release_generation`, `evidence_sha256`, dẫn tới khôi phục lịch sử thất bại dù API trả đúng. Đã sửa parser giữ/validate các trường, bổ sung regression về reload/tampering và pin hash khi mở citation. Không sửa dữ liệu chat để làm UI qua.
- Browser cuối đã khôi phục câu trả lời CN K71 từ chat `01a167ef-b882-74fd-9340-b8e85b9aa398`, mở toàn bộ bảng nguồn, kiểm hash và hiển thị ngày hiệu lực 10/06/2026 theo UTC+7. Không gọi lại model. Ảnh `ui-huce-real-chat-v10-20261023.png` và `ui-huce-real-citation-v10-20261023.png` được giữ trong runtime; banner ghi hai nguồn, 122 version chờ duyệt và chưa sẵn sàng vận hành liên tục.
- Snapshot vận hành mới chỉ chứa các page chat/đăng nhập/nguồn và redirect trang chủ; các page lịch/phòng/hồ sơ/catalog cũ không đi vào snapshot phục vụ. Không xóa page nguồn hoặc snapshot lịch sử. Điểm vào ứng dụng là API proxy `http://127.0.0.1:8015`; frontend `3015` là dịch vụ nội bộ của proxy.
- Snapshot cuối `frontend-knowledge-v11` đã build/type-check và đang phục vụ port 3015. `/rooms` qua 8015 và `/rooms`, `/services` trực tiếp 3015 đều trả 404; chat 8015 trả 200. Browser v11 reload lại đúng chat/citation đã lưu; ảnh cuối `ui-huce-final-v11-20261023.png`. Ledger vẫn 9.995, không thêm inference khi mở lịch sử/nguồn.
- Kiểm thử cuối: **44 Python unit/API tests**, **3 PostgreSQL tests** về authorization/idempotency/lease/fencing (không gọi BGE), **45 frontend tests** về SSE/citation/history-release/drawer/preview-confirmation đạt. Next production snapshot build có type checking đạt; các snapshot cũ giữ nguyên. Đây không phải performance/holdout/full-corpus campaign.
- Pytest autoload plugin bị treo ở lần đầu; dừng đúng process kiểm thử của tác vụ và chạy với `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, bật rõ `pytest_asyncio.plugin`. Không sửa test/guard hoặc dọn dữ liệu để pass.

Bằng chứng mới (trong runtime ignore, không có mật khẩu/token trong các báo cáo dưới):

- `huce-import-preflight-20261023T075623730156.json`: 122 version, original mapping 1.009/1.009, reuse 2.830 vector, 0 model call.
- `source-audit-20261023T075852232861.json`: audit nguyên bản/rendition và các vấn đề chưa giải quyết.
- `source-2114-v2-release-20261023T084457075387.json`: preview/confirmation release thật, review ghi rõ agent.
- `huce-cn-recovered-20261023T084619597977.json`: kết quả CN canary đã commit được đọc lại sau lỗi console Unicode; không chạy model lại cho ca đó.
- `huce-acceptance-20261023T084629673889.json`: QĐ 2114, clarification, lịch chưa kết nối, logout, source permission.
- `real-final-state-20261023T085455528990.json`: pointer/ack sau restart, revoked session 401, other-owner citation 404, fixture/v1 rollback 409, catalog và ledger.

### Giới hạn ngăn tuyên bố hoàn tất

Ledger hiện **9.995/10.000 native inference**, còn **5 inference**, không phải năm lượt chat. Không reset/tăng cap. Admission mới không bắt đầu retrieval nếu còn dưới bốn inference, tránh dùng nửa batch rồi thất bại; UI công bố ngân sách thấp và chưa sẵn sàng vận hành liên tục. Không chạy thêm canary BGE sau mốc này.

Kho mới có hai nguồn đủ điều kiện phục vụ; 122 version còn chờ xử lý/review hoặc là predecessor chưa được duyệt. Chưa có SSO/đối tượng sinh viên thật, API học vụ cá nhân, OCR/DOCX tổng quát, sync HTTP/scheduler gắn ingestion, đánh giá HUCE đầy đủ, fault injection và tải dài hạn. Hai nguồn được chọn đã có đối chiếu scan/text/metadata cụ thể; điều đó không hoàn thành những phần còn thiếu. API vẫn là composition local có các dependency development lịch sử bị chặn khỏi route/graph vận hành, chưa phải bản production composition đã loại mọi dependency synthetic. Không deploy production, commit/push, xóa dữ liệu, nới/bỏ guard hoặc reset/tăng budget trong lần tiếp tục này.

## 9. Yêu cầu bỏ ngân sách mô hình và mở rộng nguồn (23/10/2026, cập nhật sau mục 8)

Người dùng trực tiếp yêu cầu: **“bỏ ngân sách mô hình đi, dùng bao nhiêu thì dùng, sao lại mới phục vụ 2 tài liệu”**, sau đó yêu cầu tiếp tục. Quyết định này thay thế giới hạn ngân sách tổng mô hình nêu ở mục 8. Không thay đổi xác thực, quyền nguồn, review, preview/confirmation, kiểm hash, giới hạn từng request, deadline, token envelope, memory/CPU hoặc bảo vệ dữ liệu.

### Bỏ hạn mức tổng, giữ nguyên kế toán sử dụng

- Native BGE chạy một instance ở hai cổng cũ 18081/18082, namespace mới `infra/local/rag-advanced-models-20261023-accounting-01`, kế thừa namespace `rag-advanced-models-20261013-18`. Trước khi khởi động đã kiểm tra các listener cũ không còn chạy; không chạy hai bản model đồng thời.
- Snapshot thực tế lúc kế thừa: **9.999 inference / 16.185 HTTP / 2.167.992 token**. Các số này được giữ nguyên. `resource-transition.json` ghi `reset=false`, request trực tiếp của người dùng và cả ba aggregate cap là `null` (không giới hạn). Mọi reservation/result cũ được giữ; bộ đếm tiếp tục tăng, kể cả ordinal từ sáu chữ số trở lên.
- Paid gateway đang dùng `AccountingBudget` đã được ủy quyền trước đó: tổng USD/calls không trần, vẫn giữ chi phí/token, pending và các reservation chưa xác định. Lượt tạo câu trả lời thật sau thay đổi thành công; không đổi provider/model/secret.
- `model-accounting.json` gắn API vào đúng namespace mới. Availability trả `ACCOUNTING_ONLY`, `remaining_inferences=null`, `inference_cap=null`, `answering_available=true`; không còn cảnh báo ngân sách sắp hết. Guard ngân sách hữu hạn vẫn hoạt động khi cấu hình hữu hạn; chế độ hiện tại không chặn tổng lượt.
- Canary đầu tiên đi từ **9.999 lên 10.003**, vượt trần 10.000 cũ, trả đúng học phí và citation; không reset bộ đếm. Bằng chứng cuối hiện ghi **10.057 inference**, tiếp tục tăng khi có truy vấn.
- API 8015, frontend snapshot v11 cổng 3015, PostgreSQL cụm cũ cổng 55437 và durable worker đã được khôi phục. Không tạo database mới hoặc xóa dữ liệu. PostgreSQL tự recovery WAL của lần dừng trước; sau đó khởi động lại đúng cổng đã cấu hình bằng smart restart.

### Vì sao trước đó chỉ có hai tài liệu và phần đã xử lý thêm

Hai là số nguồn đã hoàn tất đối chiếu và activation, không phải giới hạn của model hay tổng số tài liệu đã nhập. Kho gồm tài liệu dạng scan/OCR, bảng/chương trình theo khóa, trang hướng dẫn không có ngày hiệu lực pháp lý, nội dung có prefix/suffix biên tập và nhiều predecessor. Không thể chuyển số lượng nhập thành số lượng phục vụ bằng duyệt hàng loạt hoặc gán ngày hiệu lực từ ngày đăng bài.

Đã đối chiếu toàn bộ hai ảnh gốc của **Nội quy Phòng thực hành máy tính Trung tâm CNTT&CSDL**, original SHA256 `8a0bc59b2cc844d7f606204f8b4c3cbf6c99e023033493057f923929221810c7`. Ngày ký 09/04/2024, Điều 2: hiệu lực kể từ ngày ký. Bản mới chỉ dùng 12 khoản trang 2; trang 1 và số quyết định viết tay chưa xác minh được giữ ngoài evidence. Hash original, PNG, OCR và transcript được kiểm lại; không ghi nhận đây là phê duyệt của cán bộ HUCE.

- Version mới `01a168c6-d1c7-7ddb-9590-f7a141f31698`; tái sử dụng **15 vector** với input/hash/revision giữ nguyên, giữ ngoài **17 child** thuộc phần không được chọn hoặc chỉ có ngữ cảnh biên tập. Không gọi embedding để tạo bản này. Evidence chỉ chứa lời nguồn, mapping rerank có kiểm hash; canary pair dài nhất 270 token, dưới envelope 900 không đổi.
- Review, build release, kiểm thành viên preview và confirmation chạy qua ứng dụng. Release đang phục vụ **`01a168c6-dce3-7b72-bcbd-b5797b9452b8`, generation 12, policy generation 3**, gồm QĐ 924, QĐ 2114 và Nội quy phòng máy.
- Câu hỏi thật về đi muộn trả **sau 15 phút**, câu hỏi USB trả **phải được cán bộ phòng máy đồng ý**. Cả hai đều answered, source HTTP200, original/version đúng hash, locator trang 2, content hash khớp evidence hash; anonymous source vẫn 401.
- Catalog hiện **117 nguồn / 126 phiên bản**, **3 tài liệu đang phục vụ / 122 phiên bản chờ**. Số pending không giảm vì sửa bằng version mới; version nhập cũ vẫn được giữ. Không đồng nhất số pending với số tài liệu độc lập chưa phục vụ.

### Kiểm chứng và bằng chứng

- 30 unit tests về intake, danh tính, knowledge-only, relevance, accounting không trần và 47 API tests về quản trị nguồn/SSE/citation đạt; 4 PostgreSQL integration tests đạt (bao gồm contract dùng BGE thật trong namespace test tách biệt).
- Bảy ca HUCE ban đầu sau gỡ trần đạt, receipt `huce-acceptance-20261023T123708485402.json`. Sau mở rộng, bảy ca cũ tiếp tục đạt trong `huce-acceptance-20261023T124209509065.json`; hai ca mới trả lời đúng nhưng assertion của runner dùng trường `source_sha256` không tồn tại nên báo false. Đã sửa runner kiểm original hash từ version binding, locator và evidence hash đúng contract; chạy lại riêng hai ca mới đạt trong `huce-acceptance-20261023T124253315615.json`. Giữ cả bằng chứng assertion cũ, không đổi câu trả lời/kỳ vọng để che lỗi.
- `lab-real-release-20261023T124025605880.json`: review note tự động, candidate, đúng preview ba thành viên và confirmation. `accounting-final-state-20261023T124356789012.json`: desired/serving/availability và model identity/counter/cap. Các receipt ở `infra/local/knowledge-platform-20261023/`.

Bỏ ngân sách đã thực hiện và kiểm tra bằng inference thật vượt mốc cũ. Việc mở rộng toàn bộ kho vẫn chưa hoàn tất: 122 version còn cần phân loại predecessor, hiệu lực/phạm vi khóa, đối chiếu OCR/bảng/đoạn nguồn phù hợp. Không có SSO hoặc API học vụ, theo xác nhận trực tiếp của chủ hệ thống. Chưa tuyên bố toàn bộ kho đủ chất lượng hoặc hệ thống sẵn sàng production.
