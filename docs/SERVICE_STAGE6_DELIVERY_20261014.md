# Chặng 6 — kết quả local/development ngày 14/10/2026

Chặng 6 đã có luồng phúc khảo và hỗ trợ chung xuyên frontend/API/SQLite, cùng quản trị snapshot/rendition/review/build/publish. Runtime tại **http://localhost:8004/login**, frontend3005/build02; API8003 vẫn là paid writer duy nhất. [Cách chạy và demo](SERVICE_STAGE6_RUNBOOK_20261014.md).

## Nghiệp vụ và quyền

Phúc khảo dùng course records mô phỏng có immutable fixture/checksum: thi viết đủ dữ liệu, thi vấn đáp không đủ điều kiện demo, đã quá hạn và thiếu eligibility/deadline. Hạn demo31/10/2026 là cấu hình fixture, không phải hạn thực tế của một sinh viên. Backend xác minh owner/profile/course/source hiện hành tại draft, preview, resume và confirm. Thay source generation, payload, phiên, version hoặc hết hạn xác nhận đều bị chặn trước effect. Draft revisions và supplements giữ nội dung trước/sau.

Sinh viên chọn dữ liệu → đọc hướng dẫn → draft → preview → explicit confirmation → queue persisted → cán bộ claim/request-information/respond/resolve → student đọc outcome. Hỗ trợ chỉ chia sẻ question/unresolved/reason được user chọn; không tự chuyển transcript. Cán bộ có claim/assign/transfer/respond/request-information/resolve/reject, queue policy, expected version, reason/history và idempotency. LLM không chấm/sửa điểm trường, giả chữ ký hoặc quyết định eligibility.

Các loại mới dùng `service_request`/`service_request_audit` additive trong **cùng business DB chặng1**, tái sử dụng transaction port, domain state, confirmation/replay. Bảng riêng giữ API8003 đang chạy code cũ khỏi đọc/xử lý nhầm loại mới. Hồ sơ giấy xác nhận chỉ có một nguồn sự thật ở bảng cũ; không sao chép hồ sơ sang bảng mới. Replay chung có fingerprint và actor binding.

Attachment chỉ nhận tối đa3tệp UTF-8 `.txt`,16KB/tệp; tên không có path, media type cố định, owner/queue/hash kiểm khi tải. Kết quả mới lưu HTML bất biến trong transaction cùng checksum và `service-outcome-demo-v1`, có nhãn mô phỏng. Không có side effect email/file/payment ngoài transaction; EMAIL chỉ là lựa chọn mô phỏng và được ghi rõ chưa gửi email thật.

## Tri thức

Original UTF-8 bytes/base64, SHA256 và locator giữ bất biến. Rendition/version mới có mapping, hiệu lực, audience/campus cố định HUCE_DEMO/STUDENT; candidate contextual text tách khỏi evidence. Reviewer và publisher khác tác giả. Build manifest có hash/compatibility; build lỗi không đổi active pointer. Publish/withdraw cần preview/token/session/revision/active generation và xác nhận. Current reads/search đọc lại pointer/hash/hiệu lực; không có process cache giữ nguồn withdrawn/superseded. Original/version/audit cũ vẫn đọc được theo quyền admin.

Browser đã upload sourcev2, KA001 tạo version, KA002 review/build/preview/confirm publish. Active phúc khảo `01a13814-d959-7342-abd2-45217216e3dc`, generation2; bản cũ superseded và không còn current search. Đây là **Codex development review với hai tài khoản synthetic**, không phải independent human/institutional approval. Graph review giữ UI/proxy chặng5 và active graph cũ; candidate demo mới không tự trở thành graph publication.

## Kiểm chứng và bằng chứng

Namespace mới: `infra/local/service-stage6-20261014-01/`. Manifest mới nhất `verification-manifest-02.json` gắn hashes code/report; manifest01 được giữ. `data-retention-readback-01.json`, `process-restart-01.json`, `browser-verification-01.json`, `live-source-review-02.json`, `runtime-active-01.json` và screenshots giữ kết quả trực tiếp.

- **118 distinct backend tests passed**, gồm34ca chặng6 cùng certificate/multi-agent/graph bootstrap (117ởreport06+1focused report07); **9 UI tests passed**. Scoped TypeScript/Ruff/diffcheck và fresh production build02 qua. Concurrency kiểm hai phiên của một cán bộ qua HTTP và hai identity khác nhau qua trusted same-queue fixture contexts ở application service; không đổi directory/token/grants của ứng dụng.
- Restart thật4worker mới trên fixture8005: pending preview/phiên gốc sống qua restart, confirm retry không duplicate, hai outcome/hash sống qua restart. Worker chỉ đóng bằng unique in-memory lifecycle nonce; không dừng runtime cũ.
- Browser phúc khảo `01a1380c-cd67-7544-800d-7e7413d817c2` READYv8/8audit; hỗ trợ `01a13812-0104-7008-a9e1-2b11a0c32d38` READYv5/5audit. Student owner đọc được, nonowner bị404; source/checksum/history được đọc lại qua HTTP.
- Mọi prior business row khớp backup.4certificate requests/17audit cũ giữ nguyên. READY `01a1350b-8854-718f-8a37-47c544049501` thuộcSV024 vẫn5audit/HTML SHA256 `e88565283b6cd21700449b49d5ef881c36cfc7232f0fc87b8e74407e142577f3` qua8003và8004. Không confirm lại hồ sơ đó.
- Mobile360px: document/body354px; iframe viewport247px/document232px. Không quan sát tràn ngang trong view đã kiểm. Có loading/error/permission/stale/unknown-effect tests; không suy ra accessibility certification từ mẫu này.
-3fresh guidance questions:2grounded+1safe refusal,0system errors,3history khớp/2citation hash khớp. p50=12474ms/p95=13814ms cho3ca này. Browser chat mới thêm1partial có citation/hash/history, chuyển tới form phúc khảo với effect NONE; không tự tạo queue.

Runner ban đầu so cả danh sách nghiệp vụ trong lúc browser/cán bộ đang thay đổi hồ sơ nên aggregate exit1.3raw cases được giữ, không resend. Attribution của phép so đó là **not verified do concurrency**; runner đã sửa để lưu hai snapshot và báo inconclusive, chưa replay code sửa. Các test sandbox bị treo socketpair, lượt test05 sai tên thư mục và readback đầu nhầm owner cũng được ghi trong manifest; không che thành pass.

Tổng quan sát chặng6: **41provider calls/0,0257856USD bảo thủ**. Ledger cuối**12146/12192calls**, charged**4,5173922/10USD**, còn46calls/5,4826078USD;14unknown reservations giữ nguyên. Native**8064HTTP/4707inference/807061tokens**, caps giữ nguyên. Invoice thực tế và tổng active/external-wait/calendar effort của các chặng vẫn unknown. Không tăng cap, refund/reset hoặc mở Gateway thứ hai.

## Giới hạn thực tế

Service intent/field collection dùng deterministic demo adapter và form; live multi-agent RAG cung cấp hướng dẫn từ corpus cũ. Model không có executor xác nhận hay staff/grade tools. Nguồn quản trị mới hỗ trợ bounded UTF-8 text snapshot và manual rendition có review; chưa bổ sung automatic PDF/OCR ingestion. Demo lexical candidate ảnh hưởng guidance/eligibility snapshot của dịch vụ; official hybrid index/chặng5graph vẫn riêng và được giữ nguyên.

Ca hỏi mức phí có refusal chung, thiếu lời giải thích trực tiếp rằng mức tiền chưa có nguồn. Chat chuẩn bị demo trả partial vì corpus chính thức không chứa form demo; form có hướng dẫn mô phỏng riêng. Chưa xác minh phí/mẫu/eligibility thực tế, chưa nối hệ thống trường, chưa gửi notification thật, chưa có independent human evaluation hoặc production readiness. Chặng7 đánh giá cuối vẫn riêng.

Full-project TypeScript còn4lỗi `ByRoleOptions.exact` có sẵn ở AppShell tests; không sửa để lấy trạng thái sạch. Whole-workspace diffcheck còn blank EOF có sẵn trong globals.css; scoped checks qua. Giữ toàn bộ dirty/untracked/deleted/ignored state, reports/builds/data cũ; không commit/push/deploy/delete/reset/cleanup.
