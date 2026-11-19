# Campus 24/7 — checkpoint triển khai tự động hóa tài liệu, 26/10/2026

**Chưa hoàn tất P00–P16.** Đây là checkpoint kỹ thuật và bằng chứng để tiếp tục, không phải biên bản nghiệm thu hoặc quyền bỏ kiểm duyệt.

## Kết quả đã kiểm

- Intake file không cần metadata, intake URL qua hàng đợi thật, idempotency và outbox PostgreSQL; trở lại trang vẫn thấy hồ sơ. Không lấy ngày upload làm ngày hiệu lực.
- Định danh riêng edition/observation/rendition; scope UNKNOWN khác ALL. Ngày nghiệp vụ mặc định Asia/Bangkok, không đổi day thành timestamp giả.
- Parser giữ kiểm soát chỉ đọc/không socket/không subprocess. PDFMiner nhận diện native/table/graphics/raster, Poppler tạo ảnh đối chiếu riêng. Header native không che mất phần ảnh.
- Evidence giữ occurrence, text/hash, vị trí ký tự/ô/vùng, liên kết ngữ cảnh và trạng thái chưa xác minh. Không suy tín chỉ, đơn vị hay chiều mũi tên. API/UI xem theo phần, kiểm lại tenant và hash.
- OCR dùng tesseract.js 7.0.0 và `vie.traineddata` đã cài. Pin executable, engine/core closure, ngôn ngữ, adapter và guard. Child không được mở mạng hoặc spawn executable; cache/temp/output ở namespace mới trong workspace. Mỗi trang có checkpoint riêng. OCR chưa được coi là bằng chứng ngữ nghĩa đã xác minh.
- Bản trùng bytes chỉ đề xuất dùng lại bằng chứng hiện còn đủ điều kiện. Chủ nguồn/phạm vi cần đối chiếu rõ. Hồ sơ STEM trên UI đã liên kết, chỉ có `DUPLICATE_CANDIDATES` và `LINK_EXISTING`, không parse/render/OCR/embed lại, không tạo review/version/release mới. Xuất xứ khác giữ riêng.
- Revision quyết định edition/quan hệ được lưu append-only trong schema 0021. Xác minh chặn tự duyệt, yêu cầu xác nhận căn cứ và đoạn nguồn khớp locator/hash. Preview đọc quyết định theo `known_at`, không chọn bản upload gần nhất. Quan hệ bị bác bỏ vẫn còn lịch sử. Chu trình chỉ chặn phần liên quan.
- Schema 0022 và API/UI đề xuất sửa văn xuôi: đúng người tạo bản nháp đề xuất; người khác đối chiếu độc lập. Tạo rendition/version mới của cùng edition, giữ original, ngày và bản cũ; chưa tự tạo review xuất bản hoặc release. Chặn dùng sửa chữ để xóa lỗi bảng/quan hệ. Kiểm lại intake bằng nút UI dùng checkpoint hợp lệ, giữ attempts/fencing và chặn sau 3 lần.
- Bộ chọn nhiều văn bản giữ hợp các nguồn được hỏi. Metadata prefilter trên 114 thành viên giảm 337 SELECT xuống 3, vẫn đọc/hash cùng 222 artifact, 5.054.987 byte. Lần đo cuối: 1,016 s → 0,816 s; đây chỉ là prefilter, chưa phải latency câu trả lời/tải.
- Scorer phát hiện chi tiết vật chất thừa sai trong phạm vi đóng, tách answered/abstained/clarification. Counterexample môn/tín chỉ bịa bị phát hiện. 65 cờ trên replay cũ không đồng nghĩa 65 câu đã được chứng minh sai. Đã xem 7 ảnh trang liên quan và đóng băng gold v2 trước baseline 11 câu mới; không tái diễn giải số cũ 223/224 thành nghiệm thu mới.

## Phục hồi và ranh giới runtime

Runtime gốc **8015/3015, schema 0018, release `01a172fe-1822-7679-a515-335e063dd1fa`, generation 27, policy 3** giữ nguyên. Raw catalog 120 nguồn; manifest ưu tiên vẫn 117 = 24 CNTT + 22 dùng chung + 71 để sau. 114 thành viên phục vụ. HEAD và danh sách 133 trạng thái tracked sẵn giữ nguyên; không commit/push/deploy/reset/clean/xóa dữ liệu.

Prototype **8016/3016** dùng bản phục hồi riêng `campus247_automation_20261026_008daf8c925a`, schema 0020, frontend snapshot `frontend-knowledge-automation-20261026-07`. Không bật generation. Quyết định 0021 và sửa rendition 0022 đã có code/kiểm thử nhưng bản DB 0020 này không tự migrate; UI sửa rendition chỉ hiện khi schema hỗ trợ.

Bundle phục hồi riêng `campus247_automation_20261026_fc5c770d07fc` lên 0021 đã kiểm:

- PostgreSQL snapshot export/pg_dump/pg_restore vào DB mới; counts, vector, artifact metadata và membership fingerprints khớp.
- 649 artifact của tenant HUCE, tổng 100.083.724 byte, được sao lưu rồi khôi phục sang hai namespace file mới; hash kiểm lại. 74 artifact row của tenant kiểm thử khác được giữ trong dump; kho vật lý riêng của chúng ngoài phạm vi sao lưu artifact HUCE. Lần thử đầu tìm chúng trong kho HUCE đã dừng và được giữ nguyên.
- Ba SQLite actor/consent/revocation, action-idempotency và conversations được backup/restore. Schema/row fingerprints khớp; integrity check OK, không vi phạm foreign key. Read transaction SQLite bao trùm snapshot PostgreSQL; `data_version` không đổi trong khoảng đó. Đây là một lần capture được kiểm trong phạm vi trên, không phải tuyên bố mọi backup riêng lẻ đều nguyên tử.
- Runtime bundle khởi động riêng tại 8017, đọc được original và citation lịch sử của đúng chủ, hash/locator khớp. Anonymous admin read bị chặn; phiên mới tạo riêng cho kiểm thử bị chặn sau logout. Có boot/ack mới, không kế thừa ack cũ để báo phục vụ. Process 8017 đã dừng sau kiểm; DB/file/receipt giữ nguyên.

## Kiểm chứng tái hiện

| Kiểm tra | Kết quả / evidence |
|---|---|
| Knowledge platform mới nhất, gồm rehearsal 0020/0021/0022 và restore | **324 passed, 7 skipped**, `infra/local/knowledge-automation-20261026/verify-20261026T135251027454/` |
| Local OCR thật và network guard | **2 ca đã chạy qua** trong `verify-20261026T131424477172/`; lượt mới không gọi lại OCR smoke |
| UI intake/platform/correction | **11 passed**, receipt mới nhất |
| TypeScript `--noEmit --incremental false` | Exit 0, cùng receipt |
| Frontend snapshot 07 | Exit 0, `infra/local/knowledge-platform-20261023/frontend-knowledge-automation-20261026-07-build.json` |
| Migration mới 0021, replay no-op | `infra/local/knowledge-automation-20261026/schema-rehearsal-20261026T124825291097.json` |
| Migration 0022, replay no-op | `infra/local/knowledge-automation-20261026/schema-rehearsal-20261026T133349385686.json` |
| Bundle PG/artifact/SQLite | `infra/local/knowledge-automation-20261026/schema-rehearsal-bundle-20261026T125636532306.json` |
| Runtime/citation/quyền sau restore | `infra/local/knowledge-automation-20261026/restore-runtime-20261026T130034144065.json` |
| Đo SELECT/hash tương đương | `infra/local/knowledge-automation-20261026/snapshot-reads-20261026T124308885829.json` |
| UI public STEM dùng lại bằng chứng | `infra/local/knowledge-automation-20261026/ui-intake-reuse-01.png` |
| UI OCR PDF tổng hợp | `infra/local/knowledge-automation-20261026/ui-local-ocr-01.png` |

Lệnh kiểm được ghi đầy đủ cùng cwd, giờ và exit code trong receipt. Runner `scripts/knowledge_automation_verify.py --local-ocr` dùng các manifest rehearsal cố định, tắt live-tests trên DB gốc và BGE smoke mặc định. Khi tái hiện, không để worker prototype tranh cùng queue thử. Lượt mới có 7 skipped: 5 live-test opt-in và 2 local OCR smoke không gọi lại; không tính skipped là passed. OCR smoke trước đã chạy thật và kiểm cache không gọi lại engine; không dùng vector giả thay BGE.

Đã giữ cả các lần thất bại: import parser bị guard chặn; URL thật không xác minh được TLS; BGE response/lease wait trước smoke thành công; fixture tranh job cũ; kiểm resume phải xét thêm stage EVIDENCE; ánh xạ artifact sai tenant ở lần bundle đầu; anchor Node và Windows preload path ở OCR. Không xóa evidence thất bại, giảm ngưỡng hoặc bỏ guard để chạy xanh.

## Trạng thái P00–P16

| Bước | Trạng thái và phần còn thiếu |
|---|---|
| P00 | Baseline và binding gốc đã kiểm; receipt mới để đối chiếu cuối checkpoint. |
| P01 | Partial: scorer/replay/counterexample; 7 ảnh đã xem, 11 câu live baseline có đủ quan sát. Còn hai false abstentions và một giải thích thiếu kết nối API cá nhân; không phải nghiệm thu code candidate. |
| P02 | Partial: typed identity/time/scope/rendition/evidence/relation; mapping hiện hữu và hợp đồng đầy đủ chưa xong. |
| P03 | Migrations 0019–0022 đã rehearsal/replay; chưa migrate runtime gốc hoặc chuyển 46 nguồn. |
| P04 | Partial: file/URL durable, MIME/size/DNS/TLS/redirect; batch và attachment HTML chưa hoàn chỉnh. URL HUCE mới thử bị TLS từ chối, không bypass. |
| P05 | Partial: lease/fencing, immutable stage/cache, BGE/OCR reuse; telemetry CPU và mọi tình huống crash chưa đủ. |
| P06 | Partial: native layout/render/local OCR; chưa cache theo vùng xuyên rendition, merged tables và quality real scans chưa đủ. |
| P07 | Partial: occurrence/context candidates; graph ngữ nghĩa được xác minh, OCR evidence units, điều kiện nối trang và mũi tên chưa hoàn chỉnh. |
| P08 | Partial: resolver + append-only source-bound decision history; chưa tích hợp toàn tuyến vào serving/citation hoặc UI quyết định nghiệp vụ. |
| P09 | Partial: metadata, duplicate reconciliation, evidence/ảnh/OCR, recheck có cap, API/UI sửa văn xuôi theo revision; còn live UI schema0022 và sửa bảng/quan hệ/dependency chi tiết. |
| P10 | Partial: batch metadata/hash equivalence, full embedding input checks; chưa index gia tăng theo unit/page/dependency hoàn chỉnh. |
| P11 | Chưa tự phát hành: review độc lập, eligibility, preview/confirmation, generation và ack giữ nguyên. Chưa có policy automation được ủy quyền; chưa thay bảo vệ. |
| P12 | Partial: multi-source selector và variants; baseline 11 câu mới phát hiện 3 vấn đề cần sửa; multi-turn và edition resolver serving chưa đủ. Không giả SSO/điểm/lịch cá nhân. |
| P13 | Chưa triển khai lịch đồng bộ/đến ngày hiệu lực. Không tạo Codex automation/sub-agent. Chat nối tiếp sẽ được tạo theo yêu cầu trực tiếp mới của người dùng để chuyển context. |
| P14 | Partial: scoped bundle/runtime/citation/permission restore đã kiểm; chưa đo tải/burst/cancel/long-job đầy đủ. Resource wait thật dưới 2 GiB đã quan sát; không giảm floor. |
| P15 | Chưa đủ ba pilot tài liệu thật đến ack/answer và tài liệu hoàn toàn mới không recipe; chưa shadow-map toàn bộ 46 nguồn. |
| P16 | Chưa rollout/acceptance/bàn giao đầy đủ. 71 nguồn để sau và membership gốc giữ nguyên. |

## Tài nguyên và giới hạn kết luận

Baseline mới có 12 quan sát cho 11 câu: một lần đầu thiếu final, một lần chẩn đoán câu đầu thành công, rồi 10 câu còn lại. Giữ tất cả attempt, chọn quan sát sau cùng theo thứ tự thời gian, không chọn câu đạt điểm cao nhất. Disposition đúng ở lần đầu 8/11, quan sát cuối 9/11. Diagnostic từ v2: 7 câu answered qua kiểm material/source và 1 abstention giải thích đúng; ba cờ là hai câu trả lời được nhưng bị từ chối và câu lịch cá nhân nói thiếu tài liệu thay vì thiếu kết nối API. Không phải chứng minh mọi ngữ nghĩa đều đúng.

Evidence: `independent-text-baseline-01.json`, `independent-text-diagnostic-01.json` trong namespace ngày 26/10. Chỉ endpoint gốc 8015 chạy baseline; gateway diễn tập bị khóa writer nên không khởi động, không phá khóa/khởi động writer thứ hai. Không nghiệm thu code candidate bằng kết quả này. Delta ledger paid dùng chung trong khoảng: 42 calls, 51.856 input token, 1.888 output token, conservative USD 0,0178224. Không quy toàn bộ delta cho agent hoặc coi là hóa đơn chính xác. Các conversation/session kiểm thử mới được thêm; source/schema/review/release gốc không đổi.

Token/cost dùng ledger hiện hữu, không reset/cấp cap mới. Các bước OCR có invocation, wall time, pixel và output-character thật; CPU chưa đo không ghi số giả. Snapshot account quota chỉ là usage dùng chung, không có baseline đầu task nên không suy delta riêng cho agent.

OCR mẫu tổng hợp đã đọc sai đuôi một từ; việc pipeline chạy được không chứng minh tính dùng được trên văn bản HUCE thật. Không phát hành phần chữ/cell khi điều kiện hoặc phụ thuộc chưa xác minh. Phần việc kế tiếp là nối OCR evidence/correction và resolver vào luồng ngoại lệ có revision, rồi làm admission/answer pilot trong quyền hiện có; quyền tự xác nhận hoặc giả người duyệt không được suy từ yêu cầu triển khai.
