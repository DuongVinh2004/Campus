# W7 — web chat: L-13 (lịch sử), L-10 (token), L-15 (ngăn trích dẫn), L-16 (chồng nút mobile)

Đọc `W0-common.md` (quy tắc chung và lệnh test web). Mã phiên W7.

Sở hữu: `apps/web/src/app/chat/page.tsx`, `apps/web/src/components/AppShell.tsx`, `apps/web/src/features/chat/CitationDrawer.tsx`, `apps/web/src/features/chat/CitationSource.tsx`, `apps/web/src/features/chat/local-session.ts`, `apps/web/src/features/assistance/AssistanceContextPanel.tsx`, `apps/web/src/features/privacy/PrivacyCenter.tsx`, và tệp mới trong `apps/web/src/features/chat/` (component lịch sử và test). Có thể sửa test của các tệp này (`*.test.tsx`), nhưng không sửa test không liên quan; phiên W8 sẽ xử lý các test web đỏ khác sau. Không sửa `sse.ts`/`history.ts` trừ khi bắt buộc (vừa sửa xong L-01).

## Việc
1. **L-13: danh sách lịch sử hội thoại.** Cột trái của `/chat` chỉ có "Chủ đề thường hỏi", và mục đầu luôn được tô như đang chọn. Sau khi tải lại, người dùng không còn cách mở hội thoại cũ.
   - Thêm mục "Lịch sử" trong cột trái, lấy từ `GET /v1/assistant/conversations?limit=20` (phiên W6 đang gắn route này). Dạng phản hồi: `{items:[{id,title,updated_at,created_at,mode,can_continue,retention_state,…}], page:{next_cursor,has_more,limit}}`.
   - Bấm một mục → điều hướng `/chat?conversation_id=<id>` (luồng khôi phục sẵn có). Mục đang mở được tô; "Chủ đề thường hỏi" không còn tô như đang chọn.
   - Route trả 401/404/lỗi → ẩn danh sách hoặc hiện thông báo ngắn, không phá trang chat.
   - Sau khi gửi câu đầu của hội thoại mới, danh sách cập nhật.
   - Có nhãn truy cập và hoạt động bằng bàn phím.
2. **L-10: không lưu token trong `localStorage`.** Bỏ mọi chỗ ghi `campus247_token` (`AppShell.tsx` khoảng dòng 184, `chat/page.tsx` khoảng dòng 291) và mọi chỗ gửi `Authorization: Bearer` lấy từ `localStorage` (`chat/page.tsx`, `CitationSource.tsx`, `AssistanceContextPanel.tsx`, `local-session.ts`). Dựa hoàn toàn vào cookie HttpOnly (`credentials: "include"`). Phiên W6 bỏ `token` khỏi JSON đăng nhập.
   - Khi gặp 401, hiển thị trạng thái "phiên đã hết hạn, đăng nhập lại", có liên kết `/login?redirect=…`. Không tự gia hạn bằng token cũ.
   - Xóa `campus247_token` còn sót trong `localStorage` khi tải trang (dọn dữ liệu cũ).
   - Cập nhật test liên quan (`local-session.test.ts`, `page.history.test.tsx`…) theo hành vi mới; không nới kiểm khác.
3. **L-15: ngăn trích dẫn.** Ảnh `evals/results/audit-opus-20261101/ui/03-citation-drawer.png`: tiêu đề nguồn bị ép thành cột hẹp, nhãn "Nguồn trong câu trả lời — mở để kiểm tra lại" bị cắt, có thanh cuộn ngang. Sửa bố cục: tiêu đề chiếm hết chiều ngang, nhãn xuống dòng, không cuộn ngang ở 1280 px và 375 px. Không đổi nội dung.
4. **L-16: chồng nút mobile.** Ảnh `ui/10-mobile-chat.png`: ở 375 px, nút ☰ (AppShell) chồng lên khung báo lỗi đầu trang chat. Sửa để không chồng.
5. **Trang Quyền riêng tư.** Liên kết "Lịch sử hội thoại" giờ có đích thật (danh sách ở `/chat`); đảm bảo nó mở đúng chỗ.
6. **Test và kiểm:** test cho danh sách lịch sử (hiển thị, bấm, lỗi 401/404, mục đang chọn) và cho việc không còn đọc/ghi `localStorage` token. Chạy `npx.cmd --no-install vitest run src/features/chat src/app/chat src/components` và `npx.cmd --no-install tsc --noEmit --incremental false` từ `apps/web`, báo trước/sau.
