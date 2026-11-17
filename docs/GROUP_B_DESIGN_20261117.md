# Nhóm B — giá trị cho sinh viên: thiết kế chi tiết (17/11/2026)

Trạng thái: thiết kế, chưa triển khai. Nguồn: [FEATURE_PROPOSALS_20261117.md](FEATURE_PROPOSALS_20261117.md).
Danh sách task làm được ngay: [FEATURE_READY_TASKS_20261117.md](FEATURE_READY_TASKS_20261117.md).
Bằng chứng của thiết kế: đọc mã hiện tại (dẫn `đường-dẫn:dòng`); chưa chạy thay đổi nào. Quy ước: ✅ làm được ngay · ⏳ chờ đầu vào.

Ràng buộc chung: dữ liệu lịch và hồ sơ học vụ hiện là tổng hợp (`source_system="SYNTHETIC_SIS"`,
[ports/schedule.py](../services/api/src/campus247/ports/schedule.py)); không giới thiệu tính năng như dữ liệu chính thức của HUCE.
Không đổi RAG, model, index khi chưa hỏi.

---

## B1 — Lịch học và nhắc hạn

### Hiện trạng

- Web gọi `/v1/students/me/schedule` ([campus_ops.py:111](../services/api/src/campus247/presentation/campus_ops.py)); sinh viên thêm/sửa/xóa
  sự kiện riêng (`/v1/students/me/schedule/events`). Thông báo trong ứng dụng qua `store.notify(...)`
  ([sqlite_campus_ops.py:122](../services/api/src/campus247/infrastructure/repositories/sqlite_campus_ops.py)), đọc tại `/v1/notifications`.
- Có các mốc hạn sẵn: `ops_tickets.due_at`; phiếu ra lớp của học liệu có `payload.closes.utc`
  ([0029_learning_exit_tickets.py:31](../services/api/migrations/versions/0029_learning_exit_tickets.py)).
- **Ba lỗi đã thấy trong mã:**
  1. File `.ics` xuất ra ([ScheduleView.tsx:62](../apps/web/src/features/schedule/ScheduleView.tsx)) không có `DTSTART`, `DTEND`, `UID`, `DTSTAMP`,
     dùng LF thay CRLF, không escape `,` `;` `\` và xuống dòng. Theo RFC 5545, `UID` và `DTSTAMP` là bắt buộc; thiếu `DTSTART`
     thì Google/Apple Calendar không nhập được sự kiện. Nguyên nhân gốc: trang map `starts_at`/`ends_at` thành chuỗi `time` hiển thị
     rồi bỏ ngày giờ gốc ([schedule/page.tsx:92](../apps/web/src/app/schedule/page.tsx)).
  2. Thứ trong tuần lấy bằng `start.getDay()`, theo múi giờ trình duyệt chứ không theo `Asia/Ho_Chi_Minh`. Máy đặt múi giờ khác thì
     buổi 07:00 sáng thứ Hai có thể hiện thành Chủ nhật.
  3. Lịch thi nhận theo `course_name.toLowerCase().includes("thi")`. Môn "Thiết kế…" bị xếp nhầm thành lịch thi.

### Thiết kế

- **Sửa trên web (không đổi API):**
  - `ScheduleEntry` thêm `startsAt`/`endsAt` (ISO); `time` và `dayOfWeek` tính bằng `Intl.DateTimeFormat` với `timeZone: "Asia/Ho_Chi_Minh"`.
  - Loại "thi": dùng trường của nguồn nếu có. Port hiện chưa có trường loại, nên tạm dùng regex có ranh giới từ:
    `/(^|\s|—|-)(thi|kiểm tra)(\s|$)/i` trên tiêu đề đã chuẩn hóa Unicode NFC. Ghi rõ đây là tạm thời cho tới khi nguồn có trường loại.
  - `lib/ics.ts`: hàm thuần `buildIcs(events, {now, prodId})`. CRLF; `UID: <id>@campus247.local`; `DTSTAMP` UTC; `DTSTART`/`DTEND` dạng UTC `Z`
    (tránh phải nhúng `VTIMEZONE`); escape theo RFC 5545 §3.3.11; gập dòng > 75 octet theo §3.1, tính byte UTF-8; mô tả ghi
    "Dữ liệu tổng hợp, không phải lịch chính thức" khi `is_synthetic`.
- **Feed `.ics` phía server (B1-S):** `GET /v1/students/me/schedule.ics?from&to` dùng cookie phiên hiện có, `Content-Disposition: attachment`,
  `Cache-Control: no-store`, tối đa 6 tháng. Cùng hàm dựng `.ics` viết bằng Python (`application/schedule/ics.py`), cùng bộ ca kiểm với bản TS.
- **Đăng ký lịch (webcal) — cần quyết định:** ứng dụng lịch không gửi cookie, nên phải dùng URL có token bí mật dài hạn
  (`/v1/calendar/<token>.ics`). Lộ URL là lộ lịch cá nhân. Nếu làm: token 256 bit, lưu hash, xoay và thu hồi được, chỉ chứa lịch
  (không chứa hồ sơ), log truy cập. Chờ chủ dự án quyết định.
- **Nhắc hạn trong ứng dụng:**
  - Nguồn mốc: (a) lịch thi; (b) `ops_tickets.due_at` của hồ sơ sinh viên đang mở; (c) phiếu ra lớp sắp đóng mà sinh viên chưa nộp;
    (d) sự kiện riêng sinh viên bật nhắc.
  - Job `reminder_tick` trong leader, chu kỳ 5 phút: tìm mốc trong `[now, now + 25h]`, nhắc ở T−24h và T−2h. Khóa idempotency
    `(subject_id, source, item_id, offset)` trong bảng `ops_reminders_sent` (store SQLite campus_ops, thêm bảng không qua Alembic).
    Gửi bằng `store.notify(kind="REMINDER", link=...)`.
  - Cài đặt: `reminders: {exams: true, tickets: true, exit_tickets: true, offsets: ["24h", "2h"]}` trong actor-state, chỉnh ở trang
    Thông báo. Tắt thì job bỏ qua.
  - Kênh ngoài (email/push) để sau B2 và quyết định kênh.
- **Dữ liệu thật:** sau A1 và khi HUCE cấp API lịch, viết adapter `ScheduleReadPort` thật; giao diện không đổi.

### Task

| ID | Việc | Kiểm chứng | |
|---|---|---|---|
| B1.1 | Sửa ba lỗi: giữ `startsAt`/`endsAt`, thứ theo `Asia/Ho_Chi_Minh`, nhận lịch thi có ranh giới từ | Vitest: "Thiết kế hệ thống" không là thi, "Thi giữa kỳ" là thi; giả lập TZ `America/New_York` vẫn ra đúng thứ | ✅ |
| B1.2 | `lib/ics.ts` đúng RFC 5545 + dùng trong nút xuất | Vitest: có đủ `UID`/`DTSTAMP`/`DTSTART`/`DTEND`, CRLF, escape, gập dòng UTF-8; parse lại bằng parser tự viết trong test | ✅ |
| B1.3 | Feed `GET /v1/students/me/schedule.ics` (Python, cùng bộ ca) | pytest: 401 khi chưa đăng nhập, chỉ lịch của chính mình, giới hạn 6 tháng | ✅ |
| B1.4 | Bảng `ops_reminders_sent` + job `reminder_tick` trong leader | pytest đồng hồ giả: nhắc đúng T−24h/T−2h, không trùng khi chạy lại, không nhắc mốc đã qua hoặc hồ sơ đã đóng | ✅ |
| B1.5 | Nhắc phiếu ra lớp sắp đóng (đọc từ learning service, chỉ đọc) | pytest với dữ liệu học liệu tổng hợp | ✅ |
| B1.6 | Cài đặt nhắc trong actor-state + UI ở trang Thông báo | pytest + vitest | ✅ |
| B1.7 | URL đăng ký lịch (webcal) có token | — | ⏳ quyết định riêng tư B-D1 |
| B1.8 | Adapter lịch thật | — | ⏳ A1 + API lịch của HUCE |

---

## B2 — PWA và web push

### Hiện trạng

Không có `manifest`, service worker hay icon ứng dụng (`apps/web/public` chỉ có `fonts`, `images`; `layout.tsx` không khai báo manifest).
`<html lang="vi">` có sẵn.

### Thiết kế

- **Manifest:** `apps/web/src/app/manifest.ts` (cơ chế có sẵn của Next): `name: "Campus 24/7"`, `short_name: "Campus 24/7"`, `lang: "vi"`,
  `start_url: "/?source=pwa"`, `display: "standalone"`, màu lấy từ token CSS hiện có, icon 192/512 và maskable. Icon dùng biểu tượng
  riêng của ứng dụng, **không dùng logo HUCE** (sản phẩm không phải dịch vụ chính thức).
- **Service worker** (`public/sw.js`, viết tay, không thêm thư viện):
  - Precache: trang `/offline` và các asset tĩnh có hash của bản build hiện tại (danh sách sinh lúc build).
  - Runtime: `/_next/static/*` cache-first; điều hướng thì network-first, mất mạng thì trả `/offline`.
  - **Không bao giờ cache** `/v1/*`, `/api/*`, phản hồi có `Set-Cookie`, hoặc phản hồi `Cache-Control: no-store`. Đăng xuất gửi
    `postMessage` để SW xóa cache trang.
  - Phiên bản cache theo build id; `activate` xóa cache cũ.
  - Đăng ký SW chỉ khi `window.isSecureContext` (HTTPS hoặc localhost).
- **Cài đặt:** nút "Cài ứng dụng" dùng `beforeinstallprompt` (Android/desktop); iOS hiện hướng dẫn "Chia sẻ → Thêm vào MH chính".
- **Web push — cần quyết định:**
  - Cần khóa VAPID (tự sinh, lưu như bí mật) và gửi tới dịch vụ push của trình duyệt (Google FCM, Mozilla, Apple), tức dữ liệu ra
    bên thứ ba. Payload được mã hóa đầu-cuối (RFC 8291), nhưng metadata (thời điểm, endpoint) vẫn đi qua họ.
  - Hai cách: thêm thư viện `pywebpush` (dependency mới, cần duyệt) hoặc tự cài RFC 8291 bằng `cryptography` (tránh dependency, nhiều rủi ro hơn).
  - Nội dung push tối thiểu ("Bạn có 1 nhắc hạn mới"), chi tiết chỉ hiện khi mở ứng dụng.
  - iOS chỉ nhận push khi PWA đã được cài.

### Task

| ID | Việc | Kiểm chứng | |
|---|---|---|---|
| B2.1 | `manifest.ts` + icon riêng (SVG nguồn + PNG 192/512/maskable) | Lighthouse "installable" trên localhost; vitest kiểm manifest | ✅ |
| B2.2 | `sw.js` + trang `/offline` + đăng ký SW | Playwright: offline hiện `/offline`; `/v1/*` không bao giờ vào cache (kiểm `caches.keys()`/`match`); đăng xuất xóa cache | ✅ |
| B2.3 | Nút cài đặt + hướng dẫn iOS | vitest | ✅ |
| B2.4 | Web push | — | ⏳ B-D2 (dịch vụ push bên thứ ba, cách cài RFC 8291 hoặc dependency mới) |

---

## B3 — Ôn tập từ học liệu

### Hiện trạng

Module học liệu đã có tải lên, phiên bản, phiếu ra lớp, thẻ ý tưởng, báo vướng theo trang, bản chữ hỗ trợ (OCR) và giải thích AI.
Giải thích AI trả 503 `LEARNING_AI_UNAVAILABLE` khi không có gateway/verifier
([explanation.py:37](../services/api/src/campus247/application/learning/explanation.py)), tức mặc định tắt vì cần provider trả phí.
Lưu trữ học liệu dùng Postgres qua Alembic (0023–0031); guard migration cần chủ dự án duyệt hash cho mỗi migration mới.

### Thiết kế

- **Đối tượng:**
  - `practice_set` (thuộc một `version_id` cụ thể, trạng thái `DRAFT → PUBLISHED → RETIRED`, tác giả, revision).
  - `practice_item` có `kind` (`single_choice` | `multi_choice` | `short_answer`), `prompt`, `options`, `answer`, `explanation`,
    `citations[{page_no, quote}]`, `origin` (`lecturer` | `ai_draft`), `review_state`.
  - `practice_attempt` (sinh viên, item, đúng/sai, thời điểm).
  - `practice_schedule` (sinh viên, item, `ease`, `interval_days`, `due_at`): lặp lại ngắt quãng kiểu SM-2 rút gọn
    (đúng: `interval = max(1, round(interval × ease))`, `ease += 0.1`; sai: `interval = 1`, `ease = max(1.3, ease − 0.2)`).
- **Kiểm nguồn bằng mã:** mỗi `citations.quote` phải xuất hiện nguyên văn (sau chuẩn hóa khoảng trắng và NFC) trong chữ của đúng trang
  của đúng phiên bản (lớp chữ PDF hoặc bản chữ hỗ trợ đã duyệt). Không khớp thì item không công bố được. Áp dụng cho cả câu giảng viên viết và câu AI nháp.
- **Luồng giảng viên:** tạo bộ cho một phiên bản → viết câu (hoặc nhận nháp AI) → xem trước như sinh viên → công bố. Phiên bản mới của
  tài liệu không tự chuyển bộ câu hỏi; giảng viên được báo các câu có trích dẫn không còn khớp ở phiên bản mới.
- **Luồng sinh viên:** "Ôn tập" trong trang học liệu: phiên 10 câu ưu tiên câu đến hạn, chấm ngay, giải thích kèm nút mở đúng trang
  được trích. Câu trả lời ngắn chấm bằng so khớp sau chuẩn hóa (không dùng AI chấm).
- **Thống kê cho giảng viên:** tỉ lệ đúng từng câu, câu sai nhiều nhất, trang được mở lại nhiều nhất. Chỉ số gộp; không hiện tên từng
  sinh viên nếu lớp dưới 5 người.
- **Sinh nháp bằng AI (sau):** cùng cổng gateway/verifier của giải thích AI; chỉ giảng viên bấm; trần số câu mỗi lần; nháp luôn qua
  kiểm nguồn và duyệt của giảng viên trước khi sinh viên thấy.
- **Quyền:** dùng đúng kiểm quyền lớp/phiên bản hiện có của module học liệu, kiểm lại trong transaction (bài học từ AUD-001).

### Task

| ID | Việc | Kiểm chứng | |
|---|---|---|---|
| B3.1 | Domain + bộ kiểm nguồn trích dẫn (hàm thuần) | Unit test: khớp, lệch dấu, khác trang, khác phiên bản | ✅ |
| B3.2 | Thuật toán lặp lại ngắt quãng (hàm thuần) | Unit test các chuỗi đúng/sai | ✅ |
| B3.3 | Migration 0032 + repository Postgres | Chạy trên DB tạm; test repository | ✅ viết và kiểm trên DB tạm · ⏳ B-D3 duyệt hash trước khi áp vào DB chính |
| B3.4 | API giảng viên/sinh viên | Test quyền: sinh viên lớp khác 403, phiên bị thu hồi giữa transaction bị từ chối | ✅ (theo B3.3) |
| B3.5 | UI giảng viên (soạn, xem trước, công bố, báo trích dẫn lệch) + UI sinh viên (phiên ôn tập) | vitest + `learning-features.mjs` mở rộng trên bản diễn tập | ✅ (theo B3.3) |
| B3.6 | Thống kê gộp cho giảng viên | Test ngưỡng 5 người | ✅ (theo B3.3) |
| B3.7 | Sinh nháp bằng AI | — | ⏳ B-D4 ngân sách gọi provider |

---

## B4 — Hỗ trợ tiếng Anh

### Hiện trạng

Giao diện viết thẳng tiếng Việt trong component, không có lớp i18n; `<html lang="vi">`. Embedding `bge-m3` là đa ngôn ngữ, nhưng truy hồi
chéo ngôn ngữ (hỏi tiếng Anh, tìm nguồn tiếng Việt) chưa được đo.

### Thiết kế

- **Bước 1 — đo trước (không đổi RAG):** dịch bộ ca dev của `rag_v2_retrieval_probe.py` sang tiếng Anh. Bản dịch do mô hình viết, vẫn
  giữ nguyên chunk gold. Chạy probe (chỉ truy hồi, không gọi model sinh câu trả lời, dùng embedding/reranker local), so recall@k với bản
  tiếng Việt. Nếu tụt nhiều thì B4 dừng ở giao diện tiếng Anh, câu trả lời vẫn tiếng Việt.
- **Bước 2 — giao diện:**
  - `lib/i18n/`: từ điển `vi.ts` (nguồn) và `en.ts`, hàm `t(key, params)`, kiểm kiểu bằng TypeScript để thiếu khóa thì lỗi biên dịch.
  - Ngôn ngữ lấy theo cookie `lang` (mặc định `vi`), đặt `<html lang>` tương ứng; không dùng đường dẫn `/en/...` để không đổi route.
  - Chuyển chuỗi theo từng màn hình (shell, đăng nhập, chat, lịch trước); phần còn lại làm hàng loạt sau.
- **Bước 3 — câu trả lời tiếng Anh (cần quyết định, vì đổi cách sinh câu trả lời):** câu trả lời tiếng Anh nhưng trích dẫn giữ nguyên
  văn tiếng Việt kèm dịch tham khảo đánh dấu rõ "bản dịch máy". Phải chạy gate chất lượng trước khi bật.

### Task

| ID | Việc | Kiểm chứng | |
|---|---|---|---|
| B4.1 | Bộ ca dev tiếng Anh (bản dịch do mô hình viết, giữ gold) + chạy probe truy hồi | So recall@k vi/en, lưu `evals/results/` | ✅ khi model server 18081/18082 chạy; dịch bằng chính Claude, không gọi provider trả phí |
| B4.2 | Hạ tầng `t()` + cookie `lang` + `<html lang>` | vitest; `tsc` báo thiếu khóa | ✅ |
| B4.3 | Chuyển shell, đăng nhập, chat, lịch | vitest + ảnh chụp hai ngôn ngữ | ✅ |
| B4.4 | Chuyển các màn hình còn lại | — | ✅ (khối lượng lớn; có thể giao worker nếu bật 9router) |
| B4.5 | Câu trả lời tiếng Anh | — | ⏳ B-D5: quyết định phạm vi + chi phí gate |

---

## Quyết định cần chủ dự án (nhóm B)

| # | Quyết định | Chặn | Đề xuất |
|---|---|---|---|
| B-D1 | Cho phép URL đăng ký lịch có token dài hạn | B1.7 | Chưa làm trước khi có dữ liệu lịch thật |
| B-D2 | Web push qua dịch vụ push của trình duyệt; `pywebpush` hay tự cài | B2.4 | Đồng ý, dùng `pywebpush` sau khi đọc mã và ghim |
| B-D3 | Duyệt hash migration 0032 cho bảng ôn tập | B3.3 khi áp vào DB chính | Duyệt sau khi xem migration |
| B-D4 | Ngân sách sinh nháp câu hỏi bằng AI | B3.7 | Trần theo lần bấm, chỉ giảng viên |
| B-D5 | Có cần câu trả lời tiếng Anh không | B4.5 | Quyết định sau khi có số đo B4.1 |
