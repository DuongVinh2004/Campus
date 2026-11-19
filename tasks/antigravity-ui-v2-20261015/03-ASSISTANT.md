# Đợt 03 — Trợ lý học vụ, nguồn và hội thoại

Áp dụng MASTER. Đích: giao diện AI gọn, đáng tin, đọc tốt và thao tác dễ trên điện thoại.

## Đọc
app/chat/page.tsx; features/chat/ChatPanel.tsx, CitationDrawer.tsx, CitationSource.tsx, ClaimEvidence.tsx, AnswerFeedback.tsx; features/assistance/UnifiedAssistantWorkspace.tsx.
Chỉ đọc các settings/history/preparation panel được cây component này dùng. Không đọc lại toàn bộ backend/AI docs.

## Thực hiện
- Thiết kế lại khung chat, welcome, gợi ý câu hỏi và composer. Người dùng hiểu hỏi gì và tìm nguồn ở đâu.
- Tránh hai sidebar luôn mở làm nội dung hẹp: điều hướng toàn ứng dụng và lịch sử chat có phân cấp khác nhau. Dùng drawer/panel khi cần; bảo đảm lịch sử và thao tác hội thoại vẫn truy cập được.
- Tin người dùng, trả lời AI, trạng thái xử lý, lỗi và nguồn có hierarchy rõ; nội dung nhiều đoạn/bảng/code/URL dài vẫn đọc và cuộn được.
- Composer dễ thấy, tự giãn hợp lý, không bị bàn phím/mobile safe area che. Giữ Enter gửi, Shift+Enter xuống dòng, IME, streaming stop, disabled, retry hợp lệ.
- Không hiển thị “đã kiểm chứng”, “trực tuyến”, confidence hoặc thành công mà runtime không cung cấp.
- Giữ đầy đủ history restore, saved/temporary mode, partial/abstained/unknown/stopped states, citation binding, feedback và handover.
- Citation drawer có tiêu đề, locator, tình trạng nguồn và mở nguồn; layout dễ đọc, đóng và trả focus đúng.
- Sắp xếp panel settings/preparation/workflow bằng progressive disclosure nếu thích hợp, nhưng không giấu cảnh báo bắt buộc, trạng thái chưa rõ hoặc bước xác nhận.
- Làm mới cả nhánh ExistingChatPage và UnifiedAssistantWorkspace; không chỉ nhánh đang dễ render.
- Không sửa stream parser, API service, confirmation rules hay fetch lifecycle để hợp layout.

## Xác minh
Kiểm bằng fixture/read-only phù hợp: gửi một câu, streaming, stop, lỗi mạng, khôi phục lịch sử, mở citation rồi Escape, chuyển mobile, tin dài và bảng.
Phân biệt fixture với nguồn thật trong báo cáo; không gọi fake model là đánh giá chất lượng trả lời.
Typecheck + test chat/citation/feedback và flow bị ảnh hưởng. Lỗi localStorage phải được xác định môi trường, không tắt test để qua.
Ảnh desktop/mobile chat rỗng và có nội dung, citation drawer, dark mode. Không chụp dữ liệu riêng hoặc token.
Báo cáo REPORT-TEMPLATE.md rồi dừng đợt.
