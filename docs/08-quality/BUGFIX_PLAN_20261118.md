# Kế hoạch sửa triệt để lỗi web Campus 24/7 — 2026-11-18

Nguồn: lượt QA thao tác thật trên runtime 8015 ngày 2026-11-18 (báo cáo `infra/local/qa-20261118/BAO_CAO_LOI.md`, ảnh cùng thư mục, script trong `infra/local/qa-20261118/scripts/`). Tài liệu này viết để một phiên sau thực thi từ đầu đến cuối, không cần hỏi lại, trừ đúng một điểm quyết định ghi ở mục 5.

## 0. Định nghĩa "không còn lỗi" (cổng nghiệm thu)

Không thể chứng minh phần mềm không còn lỗi nào; "xong" ở đây nghĩa là **mọi lỗi trong danh sách dưới đây đã sửa có test chặn tái phát, và cổng nghiệm thu ở WP12 chạy xanh trên runtime 8015 thật**:

1. `pnpm --dir apps/web exec tsc --noEmit` và `pnpm --dir apps/web exec vitest run`: 0 lỗi.
2. `evals/runners/run_full_regression.py` (Python): không thêm lỗi nào so với trước khi bắt đầu (ghi số trước/sau).
3. `node scripts/qa/web_acceptance.mjs` (tạo ở WP12) trên 8015, 3 vai × desktop 1360 + mobile 390: mọi trang trả 200 và có `h1`; 0 lỗi console ngoài danh sách cho phép rỗng; 0 phản hồi 4xx/5xx ngoài các ca kiểm lỗi có chủ đích; trang đạt network idle trong 10 s; không tràn ngang trên mobile; mọi luồng ở mục 4 chạy hết bước.
4. RAG (WP9): bộ `evals/runners/rag_natural_eval.py` không giảm so với số đã lưu, và 2 câu hỏi lỗi trả lời có trích dẫn.

Ghi rõ phần chưa đo được: người dùng thật; ClamAV và tải tệp nếu máy không đủ RAM (WP11).

## 1. Bối cảnh kỹ thuật cần biết trước khi sửa

- Runtime 8015 = API (`scripts/knowledge_platform.py serve`) **đứng trước** web snapshot ở 3015 và tự proxy trang. Web snapshot build với `NEXT_PUBLIC_KNOWLEDGE_PLATFORM=true` (`scripts/knowledge_platform_frontend.py:74`), tức là một nhánh code khác bản dev: `app/layout.tsx:42` **không bọc `StoreProvider`**, `app/login/page.tsx:296` dùng `OwnerLogin`.
- Có **ba danh sách cho phép viết tay** quyết định cái gì tới được người dùng, và chúng lệch nhau. Đây là gốc của nhóm lỗi lớn nhất:
  1. Trang được chép vào snapshot: `scripts/knowledge_platform_frontend.py:28-31`.
  2. Đường dẫn trang API proxy sang 3015: `scripts/knowledge_platform.py:767-768`.
  3. Đường `/v1/*` API cho qua: middleware `operational_boundary`, `scripts/knowledge_platform.py:744-752`.
- Xem thay đổi web trên 8015: build snapshot mới rồi đổi frontend 3015 (memory `ui-rebuild-restart`). Đổi mã API: dừng tiến trình `knowledge_platform.py serve` (cả worker con) rồi chạy lại launcher. Khởi động nguội: model server 18081/18082 trước (memory `runtime-8015-startup-gotchas`). Máy 16 GB chỉ đủ khi đóng bớt ứng dụng; nếu thiếu RAM thì dùng `CAMPUS_SCANNER_ENABLED=false` **chỉ khi chủ hệ thống đồng ý trong phiên đó**.
- Tài khoản thử: `student-local`, `staff-local`, chủ hệ thống; mật khẩu đọc từ `infra/local/knowledge-platform-20261023/*-credentials.json` bằng script, không in ra.

## 2. Đã sửa trong phiên QA

| Mã | Lỗi | Trạng thái |
|---|---|---|
| A1 | API sập khi khởi động trên Python runtime không có `tzdata` (`ZoneInfo("Asia/Ho_Chi_Minh")` lúc import ở `reminders.py`, `freshness_reminders.py`, `observability/alerts.py`) | Đã sửa (fallback UTC+7), commit `579e6b7`, 34 test đạt. Thêm ở WP1: test giả lập thiếu tzdata. |

## 3. Các gói sửa

Mỗi gói một commit (hoặc vài commit nhỏ) trên cùng nhánh, theo thứ tự ở mục 4. Mỗi lỗi phải có test đỏ trước, xanh sau.

### WP1 — Đường đi runtime: trang, PWA, API vận hành (A2, A3, A4, 404)

**Lỗi**
- A2: khối "Trạng thái hệ thống" ở `/admin` báo "Chức năng này chưa kết nối dữ liệu vận hành". `GET /v1/admin/operations/status` bị `operational_boundary` trả 404 vì thiếu trong allowlist (`knowledge_platform.py:749-751`). Router thật vẫn được đăng ký ở `:526`.
- A3: `/memory`, `/offline`, `/knowledge/freshness`, `/knowledge/policy-graph` trả JSON 404 thô. Chúng thiếu ở cả hai danh sách: snapshot (`knowledge_platform_frontend.py:28,30`) và proxy (`knowledge_platform.py:767`).
- A4: `/sw.js`, `/manifest.webmanifest`, `/icons/*` trả 404 qua 8015 (3015 trả 200). Mỗi trang ghi lỗi console. `sw.js` precache `/offline` và `/icons/*` (`public/sw.js:10`) nên việc cài service worker luôn hỏng.
- Trang không tồn tại trả JSON thô thay vì trang 404 dễ đọc.

**Cách sửa (gốc, không vá từng đường)**
1. Tạo một nguồn sự thật duy nhất `scripts/runtime_routes.py`:
   - `PAGE_ROUTES` sinh tự động bằng cách quét `apps/web/src/app/**/page.tsx`, trừ một danh sách loại trừ có lý do (ví dụ trang demo VinUni hoặc certificate nếu không dùng).
   - `STATIC_PREFIXES = ("_next/", "images/", "fonts/", "icons/")` và `STATIC_FILES = {"sw.js", "manifest.webmanifest", "favicon.ico"}`.
2. `knowledge_platform_frontend.py` dùng `PAGE_ROUTES` thay cho tập viết tay. Giữ nguyên hai trang redirect `/` và `/knowledge`.
3. Proxy ở `knowledge_platform.py:760-770` dùng `PAGE_ROUTES`, `STATIC_*`, và các trang con động. Giữ chặn `..` và `\`.
4. `operational_boundary`: thêm tiền tố `/v1/admin/operations/`. Viết test liệt kê mọi route `/v1/*` của app: mỗi route phải hoặc được cho qua, hoặc nằm trong `BLOCKED_LEGACY` có ghi lý do (document-requests, service-*, knowledge-operations, handovers, demo-session…). Thêm router mới mà quên khai báo thì test đỏ.
5. Đường không phải `/v1/` mà không khớp trang nào: trả HTML 404 tiếng Việt (link về `/chat`). `/v1/*` vẫn trả JSON problem.
6. `sw.js`: chỉ precache tài nguyên chắc chắn có, và cài đặt không được fail toàn bộ vì một tệp (precache từng tệp, bỏ qua tệp lỗi).

**Test**
- pytest: mọi `page.tsx` ↔ proxy 200; `/sw.js`, `/manifest.webmanifest`, `/icons/icon-192.png` → 200 qua 8015; `/khong-ton-tai` → 404 `text/html`; `/v1/admin/operations/status` với owner → 200, với student → 403.
- pytest A1: patch `ZoneInfo` ném `ZoneInfoNotFoundError` rồi `importlib.reload` ba module. VN offset phải là +7.
- Thủ công trên 8015: mở 4 trang A3 ở 3 vai và kiểm nội dung thật. Đây là lần đầu chúng được kiểm, có thể lộ lỗi mới: ghi thêm vào mục 6 rồi sửa.

**Xong khi** cổng WP12 không còn 404 nào ngoài ca cố ý, và `/admin` hiện khối trạng thái có số liệu model, sao lưu, kiểm tra đêm.

### WP2 — Giao diện tối và các trang lệ thuộc `StoreProvider` (A6)

**Lỗi**: nút "Chuyển sang giao diện tối" không làm gì trên 8015.
**Gốc**: bản runtime không bọc `StoreProvider` (`app/layout.tsx:42`), nên `useStore()` trả context mặc định có `toggleTheme: () => {}` (`lib/store.tsx:759`).

**Cách sửa**
1. Tách theme thành `lib/theme.tsx`: `ThemeProvider` cùng `useTheme()` (đọc/ghi `campus247_theme_v2`, đổi class `dark` trên `<html>`, theo dõi `prefers-color-scheme`). Bọc ở `app/layout.tsx` cho **cả hai** nhánh. `store.tsx` dùng lại hook này thay vì giữ state riêng.
2. `ThemeToggle` dùng `useTheme()`.
3. Kiểm toàn bộ consumer `useStore()` được render ở chế độ knowledge (`NotificationCenter`, `MemoryCenter`, `Navbar`, `login`…). Mỗi consumer hoặc không phụ thuộc store, hoặc nhận dữ liệu thật. Không để giá trị mặc định im lặng thay cho dữ liệu: cho `defaultStoreContext` ghi cảnh báo ở môi trường dev khi bị gọi.
4. Dark mode cho lớp identity: `styles/identity.css` mới có 4 luật `.dark`. Bổ sung token tối cho nền giấy, lưới, rail, thẻ, input, banner và kiểm tương phản AA.
5. Trang `/chat` không có thanh trên (không tìm kiếm, chuông, nút theme). Đưa nút theme và chuông vào header chat để đồng nhất.

**Test**: vitest render `ThemeToggle` không có `StoreProvider`, bấm thì `<html>` có `dark` và localStorage đổi. Thêm một test chụp ảnh dark mode vào WP12 cho 6 trang chính.

### WP3 — Đánh giá câu trả lời trong chat (A5)

**Lỗi**: chat không có nút "Hữu ích / Chưa hữu ích".
**Gốc**: `ChatPanel` chỉ hiện `AnswerFeedback` khi có `onFeedbackSubmit` (`features/chat/ChatPanel.tsx:957`), mà `app/chat/page.tsx` không truyền prop này (qua `RouteDraftChatPanel`). Vì vậy tính năng đếm "nguồn bị đánh giá chưa hữu ích" (commit `37a1403`) không có đầu vào.

**Cách sửa**
1. Kiểm trước: `FeedbackService.record_feedback` tra hội thoại qua `conv_service.get_conversation` (`application/conversations/feedback.py:57`). Xác nhận `conv_service` này đọc đúng kho hội thoại mà chat runtime ghi (`/v1/assistant/...`). Probe: POST feedback cho một `conversation_id`/`message_id` thật lấy từ `/v1/assistant/conversations`. Nếu 404/422 thì sửa adapter để cùng một kho, không tạo kho thứ hai.
2. Truyền `onFeedbackSubmit` từ `app/chat/page.tsx` qua `RouteDraftChatPanel` xuống `ChatPanel`. Gọi `POST /v1/conversations/{cid}/messages/{mid}/feedback` với `client_id` idempotent. Đã gửi thì hiện trạng thái đã đánh giá, lỗi thì hiện thông báo.
3. `message.id` phía client phải là `message_id` của server (xem chỗ nhận `message.started`, `page.tsx:353`).

**Test**: vitest cho chat page có nút và gọi đúng URL. Cổng WP12: bấm "Chưa hữu ích", rồi trang Kho tri thức (owner) thấy số đếm tăng.

### WP4 — Hồ sơ một cửa: trạng thái, nhãn, chữ (A8, A9, B3, B6)

**Lỗi và gốc**
- A8: cán bộ trả lời với "Giữ nguyên" nhưng hồ sơ chuyển SUBMITTED → NEED_INFO. Gốc ở `application/campus_ops/service.py:562`: `status = set_status or ("NEED_INFO" if SUBMITTED ...)`.
- A8b: nút "Nhận xử lý" vẫn hiện khi chính mình đã phụ trách. Gốc: `_allowed` (`service.py:466-468`) luôn trả `claim` khi hồ sơ còn mở.
- A9: phía sinh viên ghi tin cán bộ là "Bạn (Cán bộ…)". Gốc: `features/tickets/SubmittedTickets.tsx:421` so `actor_role === "STAFF"`, nhưng backend ghi `SUPPORT_OFFICER` (`_role_label`).
- A9b: lộ mã thô: "Trạng thái: SUBMITTED → NEED_INFO" (`service.py:567`), "(SUPPORT_OFFICER)" (`StaffTicketsConsole.tsx:721`), khóa biểu mẫu `purpose/recipient/reason` (`StaffTicketsConsole.tsx:555`, `SubmittedTickets.tsx:385`).
- B3: banner "chưa có yêu cầu nào từ trang này được gửi đến trường" (`features/documents/OperationalServiceWorkspace.tsx`) mâu thuẫn với nút "Gửi hồ sơ" và hàng đợi cán bộ.
- B6: thanh xác nhận đóng hồ sơ nằm ngoài màn hình.

**Cách sửa**
1. Backend: phản hồi không chọn trạng thái trên hồ sơ SUBMITTED sẽ chuyển sang **IN_REVIEW** (cán bộ đã bắt đầu xử lý). Chỉ chọn rõ "Cần bổ sung" mới sang NEED_INFO. Đổi nhãn option thành "Giữ nguyên trạng thái hiện tại" và hiện trạng thái đích dự kiến cạnh nút gửi.
2. `_allowed`: bỏ `claim` khi `assignee_subject_id == identity.subject_id`.
3. Thêm `actor_kind` (`student|staff|system`) vào view sự kiện, tính từ vai trò. Frontend dùng `actor_kind` và so `actor_subject_id` với người đang xem để hiện "Bạn". Không so chuỗi vai trò.
4. Nhãn tiếng Việt tính lúc đọc (không sửa dữ liệu cũ):
   - Sự kiện `STATUS_CHANGE` hiển thị "Chuyển trạng thái: Đã gửi → Cần bổ sung thông tin" bằng bảng nhãn dùng chung (đã có ở filter staff, `StaffTicketsConsole.tsx:56-60`). Đưa bảng vào `lib/ticket-labels.ts` cho cả hai phía.
   - Vai trò: SUPPORT_OFFICER → "Cán bộ Một cửa", STUDENT → "Sinh viên".
   - Khóa biểu mẫu lấy nhãn từ định nghĩa dịch vụ (purpose → Mục đích sử dụng, recipient → Đơn vị nhận, reason → Nội dung / lý do). Khóa lạ thì ẩn hàng thô, giữ ở khối "Nội dung yêu cầu".
5. Banner B3: "Hồ sơ được xử lý trong hệ thống Một cửa nội bộ Campus 24/7, chưa kết nối hệ thống tiếp nhận chính thức của HUCE."
6. B6: khi bấm "Gửi phản hồi" kèm trạng thái đóng, thanh xác nhận hiện ngay dưới nút, cuộn vào tầm nhìn và nhận focus.

**Test**: pytest `staff_reply` không truyền trạng thái trên SUBMITTED → IN_REVIEW; `_allowed` không có claim khi đã phụ trách; view sự kiện có `actor_kind`. Vitest timeline sinh viên hiện "Cán bộ" cho tin cán bộ và không chứa chuỗi `SUBMITTED`, `SUPPORT_OFFICER`, `purpose`. Cổng WP12: chạy lại luồng sinh viên gửi → cán bộ nhận → phản hồi → đóng.

### WP5 — Đặt phòng (A10)

**Lỗi**: khung mặc định 09:00–11:00 của hôm nay đã qua giờ, nên lần đặt đầu bị 422 "Không đặt được khung giờ đã qua". Bản xem trước hiện giờ giữ chỗ dạng ISO UTC thô.
**Gốc**: `features/rooms/RoomFinder.tsx:138-139` gán cứng giờ; `:783` in thẳng `preview.expires_at`.

**Cách sửa**
1. Giờ bắt đầu mặc định là mốc 30 phút kế tiếp sau `now + 15'`, dài 2 giờ, kẹp trong 07:00–21:00. Quá 19:00 thì sang 07:00 ngày mai và đổi luôn ô ngày. Dùng giờ Việt Nam.
2. Ô giờ của ngày hôm nay không cho chọn mốc đã qua.
3. `expires_at` hiển thị "Giữ chỗ đến 18:16 (còn 15 phút)" bằng formatter chung.
4. Kiểm "Đặt phòng của tôi" (state `myBookings`, `RoomFinder.tsx:157`): sau khi đặt, danh sách hiện mã BK và cho hủy. QA chưa thấy mã BK trên trang khi ngày lọc khác ngày đặt. Nếu danh sách chỉ lọc theo ngày đang xem thì đổi thành mọi đặt chỗ sắp tới.

**Test**: vitest với giờ giả 17:50 cho mặc định 18:30–20:30; với 20:00 thì sang ngày mai. Cổng WP12: đặt và hủy bằng giá trị mặc định, không chỉnh gì.

### WP6 — Kiểm tra dữ liệu nhập dễ thấy (A7, lịch)

**Hiện tượng**: bấm "Đăng" ở Thêm tài liệu khi chưa có tệp hoặc URI sai, và "Lưu sự kiện" khi thiếu tên, thì không thấy thông báo trong DOM. Nguyên nhân: form dùng kiểm tra gốc của trình duyệt (`required`, `pattern`, `KnowledgeDocuments.tsx:93-97`), chỉ hiện bong bóng của trình duyệt. **Trước khi sửa**: xác nhận bằng Chrome có giao diện xem bong bóng có hiện không. Nếu có thì đây là cải tiến UX, không phải lỗi chặn.

**Cách sửa (thống nhất cho mọi form)**: `noValidate` + kiểm trong `submit()` + lỗi inline cạnh trường (`aria-invalid`, `aria-describedby`, focus trường lỗi đầu tiên). Áp cho Thêm tài liệu, Nguồn tự động, Thêm sự kiện lịch, Đặt phòng, nháp dịch vụ. Ô chọn tệp thay bằng nút có kiểu và tên tệp đã chọn.

**Test**: vitest mỗi form gửi rỗng thì có `role="alert"` hoặc thông báo gắn trường.

### WP7 — Hoàn thiện giao diện (B1, B2, B4, B5, B7 và các mục nhỏ)

1. **B1 Đăng nhập**: `features/knowledge/OwnerLogin.tsx` dùng lớp identity (nền giấy lưới, logo Campus 24/7, tiêu đề serif, nút teal), có nút hiện/ẩn mật khẩu, Enter để gửi, trạng thái đang đăng nhập, lỗi gắn trường.
2. **B2 Thanh trên trong suốt**: `styles/identity.css:60` đặt `.campus-toolbar { background: transparent }` trong khi thanh này sticky. Đổi sang nền giấy (`var(--paper)` hơi trong) + `backdrop-filter: blur(8px)`. Kiểm khi cuộn ở `/staff` và `/tickets`.
3. **B4 Tiêu đề không đồng nhất**: `KnowledgePlatform.tsx:139` và trang Học liệu dùng `campus-page-heading` cùng `data-eyebrow`. Đổi chữ kỹ thuật: "Desired" → "Bản phát hành mong muốn", "generation" → "Thế hệ chỉ mục", bỏ "xử lý nền BGE" (`KnowledgePlatform.tsx:139,158,162`).
4. **B5**: "Tiến độ tài liệu: Chưa có tài liệu nào" → "Chưa có tài liệu nào được thêm qua trang này" (kho vẫn có tài liệu cũ).
5. **Nhật ký thao tác `/admin`**: cột người thực hiện đang hiện mã `01a1d62b`, tài nguyên hiện UUID. Đổi sang tên hiển thị và mã nghiệp vụ (HS-…, BK-…). Bỏ "(Actor)" ở `app/admin/page.tsx:365`.
6. **Hộp thoại**: lớp phủ để hở dải trắng ở đáy (ảnh `flow2/student-rooms-dialog.png`). Lớp phủ phải `position: fixed; inset: 0`.
7. **B7 Mobile chat**: nút menu chiếm riêng một hàng. Gộp vào header chat; gợi ý câu hỏi không bị thanh nhập che (thêm padding đáy bằng chiều cao composer).
8. **PWA**: `app/manifest.ts` có `theme_color #1d4ed8` (xanh dương) lệch nhận diện teal. Đổi theo token. Trang `/offline` dùng lớp identity.
9. **Nút nhỏ**: QA đếm 2–5 phần tử dưới 32 px mỗi trang desktop. Liệt kê bằng script WP12 rồi nâng lên ≥ 44 px vùng chạm.

**Test**: ảnh chụp WP12 trước/sau, desktop + mobile + dark; không tràn ngang.

### WP8 — Truy vấn định kỳ quá dày (B8)

**Lỗi**: không trang nào đạt network idle. `features/knowledge/KnowledgeAvailability.tsx:26` gọi `/v1/knowledge/platform/availability` mỗi 5 giây trên **mọi trang**, kể cả tab ẩn. Với 100 người dùng là ~20 req/s chỉ cho banner. Các panel khác cũng poll 4–15 s không dừng khi ẩn (`KnowledgeIntake.tsx:69`, `KnowledgePlatform.tsx:105`, `AdminOverviewPanel.tsx:132`).

**Cách sửa**: tạo hook `usePolling(fn, { intervalMs, pauseWhenHidden: true, refetchOnFocus: true })` dùng chung. Banner kho: 60 s, chỉ khi tab hiện, tải lại khi tab lấy lại focus. Panel quản trị: giữ 5 s chỉ khi đang có tác vụ chạy, ngược lại 30–60 s.

**Test**: vitest hook dừng khi `document.hidden`. Cổng WP12: mỗi trang đạt network idle (500 ms không request) trong 10 s.

### WP9 — Chất lượng trả lời RAG (A11) — có điểm quyết định

**Lỗi**: "Học phí ngành Công nghệ thông tin K67 là bao nhiêu mỗi tín chỉ?" bị từ chối 3/3 lần. Trace: 1 phát biểu sinh ra, bị loại `SEMANTIC_UNSUPPORTED`, kết quả `refuse`. "Điều kiện xếp loại tốt nghiệp giỏi" cũng bị từ chối. Mọi trace có `rerank_scores: []` (`rag_v2/service.py:264`), tức là không ứng viên nào mang điểm rerank, dù model server 18082 vẫn nhận request.

**Bước 1 — chẩn đoán, không đổi mã (làm ngay)**
1. Chạy lại 2 câu với trace đầy đủ. Ghi lại phát biểu bị loại, các span nguồn được đưa cho bộ chấm ngữ nghĩa, lý do của bộ chấm. Đối chiếu với dòng học phí K67 trong nguồn: sai số, sai đơn vị, hay bảng bị cắt.
2. Tìm vì sao `rerank_score` luôn `None`: rerank bị bỏ qua, lỗi im lặng, hay chỉ trace không ghi. So log `rag_v2_trace` của một câu trả lời đúng.
3. Kiểm lịch sử: cùng câu này trong lịch sử chat đã từng trả lời. Xác định từ commit nào thì bị từ chối (`git log -- services/api/src/campus247/rag_v2`) bằng cách chạy eval đơn câu ở các commit nghi vấn.

**Bước 2 — sửa (chỉ sau điểm quyết định ở mục 5)**: sửa đúng nguyên nhân tìm được. Ví dụ: phát biểu số liệu bảng được chứng minh bằng khớp số và đơn vị xác định trước khi gọi bộ chấm ngữ nghĩa; hoặc span đưa cho bộ chấm phải chứa cả hàng tiêu đề bảng; hoặc sửa đường rerank. Không nâng giới hạn 5 s của provider, không đổi model hay chỉ mục (memory `rag-eval-and-retained-bounds`).

**Test**: thêm 2 câu (và 2–3 cách hỏi khác) vào `evals/datasets/rag-v2/` với gold kiểm bằng span nguồn. Chạy `rag_natural_eval.py` toàn bộ, không giảm so với `evals/results/rag-natural-20261114/`. Chạy `rag_regression_gate.py run --quick` (provider thật, khoảng 600 lượt gọi, client giãn nhịp).

### WP10 — Học liệu theo lớp (A12)

Không kiểm được vì `student-local` chưa được gán lớp nào (trang hiện đúng trạng thái rỗng). Dùng `scripts/learning_local_setup.py` / `learning_local_identity.py` để tạo một lớp tổng hợp có 2 buổi học và 1 tài liệu (đánh dấu dữ liệu mô phỏng) gán cho `student-local`. Sau đó kiểm: chọn lớp, mở buổi, đọc tài liệu, vị trí đọc được nhớ, "Cập nhật học liệu", phản hồi trang (`PageFeedback`), phiếu cuối buổi. Lỗi phát hiện thêm vào mục 6 rồi sửa trong gói này.

### WP11 — Phần chưa kiểm được trong lượt QA

1. Tải tài liệu thật với ClamAV **bật** (cần khoảng 4,2 GB RAM trống). Kiểm tệp TXT sạch, tệp EICAR (phải bị chặn), PDF scan (OCR), tệp > 50 MB.
2. Luồng phát hành: dùng tài liệu tổng hợp có tiêu đề "QA" ở chế độ **Gửi duyệt**, duyệt bằng tài khoản khác, theo dõi tới ACTIVE, hỏi chatbot thấy trích dẫn, rồi **Thu hồi** và xác nhận chỉ mục quay lại. Bước này đổi chỉ mục RAG sống nên chạy khi chủ hệ thống đồng ý.
3. Bốn trang mới vào được sau WP1 (`/memory`, `/offline`, `/knowledge/freshness`, `/knowledge/policy-graph`): kiểm như mọi trang khác.

### WP12 — Cổng nghiệm thu tự động

Chuyển script QA (`infra/local/qa-20261118/scripts/`) thành `scripts/qa/web_acceptance.mjs` có **khẳng định** chứ không chỉ in log:

- Đăng nhập qua form thật cho 3 vai. Đọc mật khẩu từ tệp, không in. Kiểm cả mật khẩu sai.
- Mỗi trang trong `PAGE_ROUTES` (WP1), 2 khung hình, sáng và tối: 200, có `h1`, không tràn ngang, network idle ≤ 10 s, 0 lỗi console, 0 phản hồi ≥ 400 ngoài danh sách ca cố ý, phần tử chạm ≥ 44 px.
- Luồng: chat (câu có nguồn, câu chống injection, câu ngoài phạm vi, đánh giá câu trả lời), đặt phòng mặc định → thông báo → hủy, thêm và xóa sự kiện lịch, nháp → gửi → cán bộ nhận/phản hồi/đóng → sinh viên thấy đúng nhãn, đánh dấu đã đọc, kiểm lỗi các form (WP6), `/admin` có khối trạng thái.
- Dữ liệu tạo ra mang tiền tố `QA-<ngày>` và được dọn bằng chính API của ứng dụng (hủy đặt phòng, xóa sự kiện). Hồ sơ đã đóng thì giữ lại.
- Đầu ra: JSON + ảnh trong `infra/local/qa-<ngày>/`, mã thoát ≠ 0 khi có khẳng định sai.

## 4. Thứ tự thực hiện

1. **WP1** trước: mở đường cho 4 trang và API vận hành, và là nền cho danh sách trang của WP12.
2. WP2, WP4, WP5, WP8 độc lập nhau. Có thể làm song song nếu không chung tệp; cùng chạm `app/layout.tsx` thì làm tuần tự.
3. WP3 sau WP2 (chung `app/chat/page.tsx` và header chat).
4. WP6, WP7.
5. WP9 bước 1 làm sớm (chỉ đọc), bước 2 theo mục 5.
6. WP10, WP11.
7. WP12 viết song song từ đầu (dùng làm test đỏ cho từng gói), chạy toàn bộ ở cuối.
8. Kết thúc: build snapshot mới, khởi động lại 8015, chạy đủ cổng ở mục 0, cập nhật báo cáo với số trước/sau.

Git: làm trên nhánh `fix/qa-20261118-bugs` (đã có commit A1). Mỗi WP một hoặc vài commit, chỉ `git add` tệp của mình. Không push, không merge khi chưa được duyệt.

## 5. Điểm quyết định của chủ hệ thống

- **Sửa mã RAG (WP9 bước 2) và phát hành thử tài liệu (WP11.2)**: memory dự án ghi "không đổi RAG khi chưa hỏi". Yêu cầu ngày 2026-11-18 "sửa triệt để toàn bộ lỗi" bao gồm lỗi này. Khi thực thi, nêu kết quả chẩn đoán bước 1 và cách sửa đề xuất trong một câu hỏi duy nhất, rồi làm tiếp các gói khác trong lúc chờ.
- Phạm vi khác (giai đoạn cloud, VPS, chi phí) không thuộc kế hoạch này.

## 6. Lỗi phát sinh khi thực thi

(Ghi thêm tại đây: mã, hiện tượng, nguyên nhân gốc, gói xử lý, trạng thái.)
