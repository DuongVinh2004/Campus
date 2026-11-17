W7 đã thực hiện phần sửa trong phạm vi tệp được giao; chưa triển khai lên runtime 8015.

1. **Đã sửa và nguyên nhân gốc**

- L-13: thêm “Lịch sử” từ `GET /v1/assistant/conversations?limit=20`; mở đúng URL hội thoại, tô mục đang mở, bỏ chọn khi tạo chat mới và cập nhật sau lượt đầu. Lỗi danh sách không chặn chat. Trước đây cột trái chỉ có gợi ý với mục đầu luôn được tô.
- L-10: các luồng W7 chỉ gửi cookie qua `credentials: "include"`; bỏ đọc/ghi token và tự xin lại phiên. Khi tải trang, xóa khóa token cũ; gặp 401 có thông báo hết hạn và liên kết `/login?redirect=…`.
- L-15: tách tiêu đề và nhãn nguồn thành hai hàng, cho nhãn và định danh dài xuống dòng. Nguyên nhân là hàng flex chia ngang và nhãn `nowrap`.
- L-16: nút menu mobile tham gia luồng bố cục trước nội dung, thay vị trí absolute/fixed gây chồng khung lỗi.
- Liên kết “Lịch sử hội thoại” ở Quyền riêng tư vốn trỏ `/chat`; đã kiểm tra đích này hiển thị danh sách mới, không cần sửa trang quyền riêng tư.

2. **Tệp đã đổi và test**

Các đường dẫn dưới đây tính từ `apps/web/src/`:

- Mã: `app/chat/page.tsx`, `components/AppShell.tsx`, `features/chat/CitationDrawer.tsx`, `features/chat/CitationSource.tsx`, `features/chat/local-session.ts`, `features/assistance/AssistanceContextPanel.tsx`; thêm `features/chat/ConversationHistory.tsx`.
- Test cập nhật: `app/chat/page.test.tsx`, `app/chat/page.history.test.tsx`, `app/chat/page.resume.test.tsx`, `components/AppShell.test.tsx`, `features/chat/CitationSource.test.tsx`, `features/chat/local-session.test.ts`.
- Thêm `features/chat/W7-chat-history.test.tsx` (9 ca): `shows server conversation history, native keyboard links and only the current selection`; `opens the real chat history destination from the privacy page link`; `keeps chat usable when the list fails with %s` (401/404/503/network); `uses cookies without reading or writing a legacy token and refreshes after the first turn`; `offers login with the current redirect after %s returns 401 without renewal` (restore/send).
- Thêm `features/chat/W7-layout.test.tsx`: `gives source titles their own row and wraps the full validity label and long identifiers`; `places the mobile chat menu in document flow before the chat alert`.
- Thêm `features/chat/W7-assistance-session.test.tsx`: `resolves assistance with cookies and returns to the same resource after login`.
- Thêm vào AppShell: `removes the legacy credential on load without reading or writing a token`; CitationSource: `uses only cookies for a v2 source and offers login on 401 without reading a token`.

3. **Lệnh và kết quả trước/sau**

Chạy từ `apps/web`, dùng `npx.cmd --no-install`:

- `vitest run src/features/chat src/app/chat src/components`: trước **183 đạt / 6 đỏ**; sau **199 đạt / 3 đỏ** (202 ca), exit 1.
- Nhóm 4 tệp tái hiện (`W7-chat-history`, `W7-layout`, `local-session`, `CitationSource`): mã cũ **15 đạt / 15 đỏ**; sau sửa **30 đạt / 0 đỏ**. Các ca bổ sung sau đó cũng đạt trong lệnh gộp.
- `vitest run src/features/chat`: sau **133 đạt / 3 đỏ**, exit 1; không có ca đỏ mới của W7.
- `tsc --noEmit --incremental false`: trước và sau **0 lỗi**, exit 0. `git diff --check` trên tệp tracked W7 sạch.
- Ba ca đỏ cũ giữ nguyên: ChatPanel — `shows public knowledge without a fabricated account or conversation history and links real HUCE services`; `renders actionable procedural shortcuts for relevant AI answers`; history — `does not promote legacy assistant text to a verified answer`.
- Chrome ngoại tuyến, HTML từ component và CSS hiện tại, primitive dialog giả lập: 1280/375 px đều không tràn ngang; tiêu đề trên nhãn. 375 px: đáy menu 52 px, đầu khung lỗi 72 px, không chồng.
- Chrome với ConversationHistory thật và API giả: Tab tới liên kết, Enter mở đúng `/chat?conversation_id=…`, `aria-current="page"`; mọi yêu cầu được chặn hoặc trả giả lập.

4. **Thiết kế và giới hạn bằng chứng**

- Dùng liên kết HTML để điều hướng và chạy lại luồng khôi phục khi tải trang; dùng khe `historyContent` sẵn có. CSS chỉ trung hòa trạng thái gợi ý trong cột lịch sử, tránh sửa ChatPanel ngoài quyền sở hữu.
- Giữ chữ ký helper `renewExpiredLocalToken` cho caller ngoài phạm vi, nhưng helper chỉ bỏ token cũ và trả null; không gọi mạng hay cấp lại token.
- Không sửa `sse.ts`/`history.ts`; các kiểm binding, hash, `unit_id`, nguồn và phiên bản vẫn giữ.
- Bằng chứng là test tổng hợp theo hình dạng phản hồi máy chủ, fixture trích dẫn v2 với hash kiểm bằng mã, cùng kiểm Chrome ngoại tuyến; mức dùng được với người dùng thật chưa đo.

5. **Cần phối hợp / rủi ro**

- L-10 toàn web chưa khép kín ngoài quyền W7: `features/knowledge/OwnerLogin.tsx` vẫn ghi `result.token` và chưa xử lý `redirect`; sau W6 bỏ token JSON, nơi này có thể ghi chuỗi `undefined`. Cần sửa trước khi coi luồng đăng nhập/quay lại hội thoại hoàn tất.
- `lib/api/client.ts`, `lib/unified-assistant-runtime.tsx`, gateway dịch vụ/chứng nhận và một số component knowledge/assistance khác vẫn tham chiếu khóa token. Đã giữ nguyên theo giới hạn sở hữu; cần phiên phụ trách chuyển chúng sang cookie.
- Ba test đỏ cũ cần W8 xử lý. Cần triển khai đồng bộ web và API danh sách của W6 rồi kiểm tích hợp thực tế khi được giao; phiên này không gọi mạng/dịch vụ trả phí, không khởi động/build 8015, không commit/push/reset/clean/xóa tệp.

Báo cáo: [W7-report.md](<C:/Users/Duong Vinh/Vinh/evals/results/audit-opus-20261101/impl/W7-report.md>).
