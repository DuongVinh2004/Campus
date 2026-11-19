# Bộ prompt điều phối Antigravity 3.8 Flash — Campus UI V2

Ngày: 15/10/2026. Workspace: C:\Users\Duong Vinh\Vinh.

## Cách sử dụng
1. Mở đúng workspace trong Antigravity.
2. Dán prompt khởi động bên dưới. Antigravity đọc 00-MASTER và thực hiện đợt 01.
3. Gửi báo cáo và ảnh thật của đợt đó về cuộc chat chỉ đạo này. Tôi rà soát rồi viết prompt sửa có đúng file, lỗi và tiêu chí.
4. Khi đợt đạt yêu cầu, dùng prompt chuyển đợt. Có 5 đợt, không yêu cầu duyệt từng component.
5. Giữ cùng một chat Antigravity trong khả năng cho phép. Khi đổi chat, cung cấp MASTER, báo cáo gần nhất và đúng prompt đợt đang làm; không nạp lại toàn bộ lịch sử.

## Prompt khởi động — sao chép nguyên khối
Bạn là Antigravity 3.8 Flash, thực thi việc xây lại toàn bộ UX/UI Campus 24/7 ngay trong frontend hiện tại.
Workspace: C:\Users\Duong Vinh\Vinh.
Đọc tasks/antigravity-ui-v2-20261015/00-MASTER.md và tasks/antigravity-ui-v2-20261015/01-FOUNDATION.md, rồi thực hiện đợt 01.
Tôi giao quyền quyết định chi tiết giao diện trong phạm vi đó. Không dừng ở lập kế hoạch; sửa code, chạy kiểm tra và xem trên browser.
Đọc mã hiện tại để giữ chức năng và dữ liệu; không dùng giao diện hiện tại làm mẫu thẩm mỹ.
Kết thúc bằng báo cáo theo tasks/antigravity-ui-v2-20261015/REPORT-TEMPLATE.md, kèm ảnh thật desktop/mobile. Chỉ thực hiện đợt 01 ở lượt này.

## Prompt chuyển đợt — thay NN-TEN-DOT bằng tên tệp thật
Tiếp tục thiết kế lại Campus UI V2 theo 00-MASTER.md đã nạp.
Đọc tasks/antigravity-ui-v2-20261015/NN-TEN-DOT.md và báo cáo đợt trước, rồi thực hiện đúng đợt này.
Giữ các quyết định thiết kế đã chốt và các thay đổi đang có. Không tự mở rộng sang backend hoặc dựng ứng dụng thay thế.
Sửa code, chạy kiểm tra phù hợp, xem trên browser và báo cáo ngắn theo REPORT-TEMPLATE.md.
Nếu phát hiện lỗi trong phần nền tảng ảnh hưởng đợt này, sửa đúng phần dùng chung cần thiết, ghi rõ lý do; không dừng để xin phép việc UI đã được giao.

## Thứ tự
- 01-FOUNDATION.md: hoàn thiện nền tảng và shell.
- 02-HOME-AUTH.md: trang chủ, đăng nhập, vào ứng dụng.
- 03-ASSISTANT.md: chat, nguồn, lịch sử và các panel trợ lý.
- 04-WORKFLOWS.md: toàn bộ màn hình nghiệp vụ còn lại.
- 05-VERIFICATION.md: kiểm tra tích hợp và sửa đến khi đạt.

## Tiết kiệm quota
- Một lần thực thi một đợt; không nhiều agent; không tái lập kế hoạch tổng thể.
- Đọc tệp đích và dependencies trực tiếp, dùng tìm kiếm có giới hạn; không quét infra/local, archive, node_modules hoặc mọi tài liệu.
- Chỉ đọc tài liệu Next đã cài tương ứng API sử dụng, không đọc toàn bộ bộ docs.
- Không cài đồng thời nhiều skill/framework UI. UI UX Pro Max hỗ trợ ra quyết định, DESIGN.md giữ thiết kế nhất quán; không cần thêm Figma/v0/Stitch cho đợt này.
- Báo cáo tối đa khoảng 450 từ, khoảng 6 ảnh có ích mỗi đợt. Các trang còn lại dùng ma trận trạng thái.
- Chạy typecheck và test ảnh hưởng theo đợt; full suite và production build tập trung ở đợt 05, trừ khi cần sớm để giải quyết lỗi.
- Không gọi một test lỗi là pre-existing nếu chưa có bằng chứng so sánh.

## Trạng thái bàn giao cần biết
Đã lưu 190 tệp frontend hiện tại vào .tooling/campus-ui-v2-20261015-01/frontend-before.zip, kèm manifest SHA256 và trạng thái Git.
Sau snapshot, đã tạo apps/web/DESIGN.md và thay apps/web/src/components/AppShell.tsx bằng bản nháp shell mới.
Bản nháp này chưa có CSS campus-*, có prop initialFocusRef không thuộc API AccessibleDialog, và chưa xử lý publicKnowledge. Không coi là sản phẩm hoàn chỉnh.
Chưa có ảnh browser xác minh hoặc build thành công cho shell mới. Không có thao tác rollback, xóa file hoặc commit.
