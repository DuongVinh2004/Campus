# Campus 24/7 — kết quả phiên hoàn thiện 15/10/2026

Phần kỹ thuật được thực hiện tuần tự trên source hiện tại và fixture mới `infra/local/unified-ai-completion-20261015-01`. Backend gate cuối đạt **877/877 ca duy nhất, exit 0**, source không đổi trong lượt kiểm. Production build và TypeScript của candidate04 đạt. Đây là bằng chứng local/synthetic; kế hoạch chưa được coi là hoàn tất nghiệm thu người dùng hoặc production.

## Thay đổi đã kiểm

- UNI-040: conversation mode được server lưu, đọc lại và ràng buộc owner/tenant. Chat tạm thời không đọc/ghi personal memory, không xuất hiện trong catalog chat thường; vẫn có lưu trữ vận hành 30 ngày theo disclosure. Legacy không rõ mode không được tự nhận là persistent hoặc gắn owner mới.
- Chat persistent chỉ nhận memory qua consent, opt-in, relevance và nguồn passive có giới hạn. Consent/revoke/correction/forget được kiểm lại trước final. Forgotten memory bị chặn cả đường tự tái sử dụng history, kể cả khi memory đã tắt; chat gốc vẫn giữ và có thể mở riêng. Không tự trích xuất hoặc lưu memory từ chat.
- Native chat được gắn vào unified candidate bằng repository tenant-bound và actor/memory stores dùng chung rõ ràng. Held-history proxy không được coi là consumer hỗ trợ temporary. Schema JSON create-conversation được cập nhật thêm mode, các assertion schema vẫn giữ nghiêm ngặt.
- Các process probe cũ được bổ sung đúng namespace fixture mới có marker xác minh; ngoài scope vẫn bị từ chối. Guard build gốc không sửa. Lỗi deadline trước dispatch được sửa ở bộ đếm: call chưa gửi không bị tính thành call không rõ kết quả; reservation chi phí vẫn bảo thủ. Budget và threshold 50ms gốc không đổi.
- UI sửa React keys trùng giữa các panel projection/context/supplement/dossier/draft/workflow ở hai workspace. Trước sửa, claim có thể tạo nhiều panel/editor; sau sửa, E2E kiểm đúng một bộ hồ sơ/editor.

## Bằng chứng chính

Các đường dưới đây tính từ repository root. Báo cáo máy tại `infra/local/unified-ai-completion-20261015-01/coverage.json` nối đủ **26 REQ / 50 AT / 50 UNI / 43 source mappings**; có test IDs và giới hạn riêng, không biến mọi hàng thành acceptance pass.

| Kiểm tra | Kết quả / bằng chứng |
| --- | --- |
| Backend cuối | `checks/backend-08/command.json`, `backend.xml`, `backend.log`: 877 passed, 0 failed/skipped/xfail; 273,60 giây pytest. Không cộng các lần chạy lại thành coverage mới. |
| Frontend cuối | `checks/frontend-04/frontend-build-04.json`, `typescript.json`: exit 0; BUILD_ID `I0Xq0uJY2BXxvGQBOUo-i`. Guard nguyên bản SHA-256 `8f0886295da2214205cf257dd9e1d9476993ed1a7fb0ac67434909fa4af2eae6`. |
| UI hai vai trò | `checks/ui-flow-09/` rồi `ui-flow-10/report.json`, cùng case `01a13f91-9d64-7f7a-915d-5db43cfb0407`: goal/draft, manual edit, reload, preview/confirm, staff claim/source/autosave/reload, mandatory reviews, typed supplement, student correction, delta review, result/receipt/readback. Lượt09 timeout ở harness khi queue đang tải; lượt10 tiếp tục case đã commit, không gửi lại action. Không gọi đây là một lượt đơn không gián đoạn. |
| UI bổ sung | `ui-memory-01`, `ui-chat-02`, `ui-notifications-01`: consent, opt-in, lưu/sửa/quên/export/tắt; Settings keyboard/Escape/focus restore; temporary reload; notification mở đúng resource. Notification setup dùng API thật của fixture, không phải toàn bộ thao tác qua UI. Hai worker process lần lượt delivery1 rồi0. |
| Mobile/a11y giới hạn | `ui-mobile-07/report.json`: 390px, services/chat/memory/notifications/privacy và staff case detail; không horizontal overflow, inputs có label, skip-link nhận Tab. Settings focus được kiểm riêng. Dark mode chờ chuyển màu hoàn tất; 4 tiêu đề h1/h2 đo contrast 14,89–15,95:1. Chưa phải audit WCAG đầy đủ, screen reader hoặc mọi viewport. Ảnh cũ chụp giữa transition được giữ, không tính là lỗi CSS đã sửa. |
| Feature-off | `checks/ui-fallback-01/report.json` và `tests/unified_completion/test_rehearsal.py`: bản build mới tắt unified assistant vẫn cho student manual draft/save/reload/confirm, staff claim và receipt; history/draft có đường đọc lại. Không đổi feature của bản đang phục vụ cũ. |
| So sánh matched | `fixtures/matched-comparison-01/report.json`: cùng 3 điều kiện nguồn hiện hành/thiếu/sai số, single và selected-multi chạy graph thật với model scripted, material gates đạt. Không chứng minh model quality, usefulness hoặc ý kiến chuyên gia. |
| Load | `fixtures/concurrent-load-01/report.json`: 24 restore/prepare/receipt-read triplets, concurrency4, 18,01 triplets/s; p95 tương ứng136,56 /168,34 /110,06ms. Recipient sai403; checks không bị bỏ qua. |
| Cache/queue/first commit | `fixtures/extended-measure-01/report.json`: 23 warm hits revalidate nguồn, p95650,22ms; 24 queue queries trên8 case chưa review, concurrency4, p95501,19ms, mandatory reviews vẫn chặn; 24 fixture độc lập confirm→public/staff receipt-read p9537,81ms. Không gồm khởi tạo/chờ người/review; không phải cold-process hoặc production SLO. |

Mọi evidence trên nằm trong namespace mới. Browser tương tác trong app và Node REPL không khởi tạo được kernel (`os error 3`); E2E dùng Playwright/Chromium đã cài, headless, profile/temp/downloads riêng trong workspace, chỉ mở loopback candidate. Không liên hệ người khác. Các lần harness lỗi, source lỗi, 429 do giới hạn120/60, screenshot trước hydration/giữa transition và các log cũ đều được giữ; `ui-readback-01` xác nhận trạng thái sau429 mà không replay action.

## Runtime có thể xem

- Candidate04: `http://localhost:3019/login`, API `http://localhost:8019`; `GET /candidate-manifest` gắn đúng BUILD_ID, provider `deterministic_fake`, paid calls0. Các tài khoản SV001/SV024 và OF002 ở đây là fixture tổng hợp.
- Feature-off candidate: `http://localhost:3020/login`, API8020, dữ liệu tổng hợp riêng.
- Candidate01–03 và các snapshot cũ được giữ. Không chuyển entry của runtime cũ, không deploy/commit/push và không dừng runtime cũ.

## Phần chưa có bằng chứng để đóng

UNI-045 cần qualified expert/blind review và so sánh model thật cùng điều kiện. Snapshot budget read-only tại `checks/provider-admission-01.json`: 12.158/12.192 calls, còn34; 3 selected-multi runs cần reserve36 ở giới hạn12 calls/run hiện hành, chưa tính single baseline. Vì vậy full campaign không được admitted. Không tăng quota, đổi policy, mua access hoặc phát paid call. Model USD, active time, student wait và unit wait không quan sát được được giữ **null**, không ghi0.

UNI-047 / AT-49 chưa chạy người thật. Ủy quyền tự động của người dùng cho phép hoàn tất kỹ thuật nhưng không tạo ra participants, chuyên gia, session thật hay institutional authority. Protocol cũ `docs/UNIFIED_AI_PILOT_C_20261015_01.md` được giữ làm thiết kế; `pilot-session-template.json` trong namespace mới có records rỗng. Các mục tiêu40% giảm nhập tay,30% giảm thời gian và90% hoàn tất supported chưa được đo.

Official fees/deadlines/templates/rules của trường, real legacy ownership, external channels, toàn bộ route/admin coverage, thiết bị/người dùng thật và distributed cross-store crash atomicity vẫn chưa được xác minh. Load local không được suy thành năng lực production. UNI-044/046/048/049/050 hoàn tất phần local được mô tả nhưng full acceptance còn pending; UNI-040 có đủ implementation và kiểm local, vẫn giữ `implemented` vì còn acceptance legacy/triển khai rộng. UNI-043 được `verified` trong phạm vi bộ contract/security/fault synthetic cuối.

## Bảo toàn và bàn giao

Preflight giữ1.070 source preimages và schema/all-table/row digest của4 DB serving/retained qua kết nối read-only. `preservation-01.json` đã xác nhận nguyên trạng; audit cuối và `checks/final-source-binding.json` chốt sau tài liệu. AGENTS, web AGENTS, package/lockfiles và guard được đối chiếu hash. Không xóa/reset/cleanup, không sửa dữ liệu cũ hoặc bảo vệ an toàn. Chênh lệch với gate cuối chỉ được phép là metadata backlog; implementation/build source phải khớp.

Runbook hiện hành của phiên: [UNIFIED_AI_COMPLETION_RUNBOOK_20261015_01.md](UNIFIED_AI_COMPLETION_RUNBOOK_20261015_01.md). Bước kế tiếp thực tế là cung cấp điều kiện cho review/model evaluation và pilot người thật; không chạy lại các action đã có receipt để lấy ảnh đẹp hơn.
