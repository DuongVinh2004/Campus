# Đợt 01 — Nền tảng, shell và component

Áp dụng 00-MASTER.md. Thực hiện code, không chỉ tư vấn. Đầu ra: shell mới hoàn chỉnh và dùng được, làm nền cho mọi màn hình.

## Đọc có giới hạn
apps/web/DESIGN.md; src/components/AppShell.tsx; src/components/shared/AccessibleDialog.tsx; ThemeToggle.tsx; src/app/layout.tsx; globals.css; src/styles/tokens.css; package.json.
Đối chiếu AppShell trước khi sửa trong snapshot để giữ role filtering, publicKnowledge, SERVICE_DEMO/CERTIFICATE_DEMO destinations và logic session hiện có. Đừng chép lại nguyên layout cũ.

## Công việc
1. Kiểm Git, canonical paths, các thay đổi hiện có. Liệt kê tối đa 8 quyết định triển khai rồi làm luôn.
2. Sửa AppShell: bỏ initialFocusRef sai API ở call site, giữ AccessibleDialog focus trap/inert/Escape/focus return. Chỉ đổi primitive nếu có bug đã chứng minh.
3. Xử lý publicKnowledge đúng ý nghĩa mode hiện có: giữ lối tới nguồn/cổng công khai cần thiết, không biến nó thành màn hình private hoặc sửa quyền để nav chạy được.
4. Implement tokens và CSS campus-* đang thiếu: sidebar desktop 244px, toolbar 76px, content max-width 1320px; dưới 960px dùng menu modal, đóng khi chọn route hoặc Escape. Tránh trùng landmark/ID khi cả desktop/mobile tồn tại.
5. Đặt typography Inter đúng qua --font-inter; chuẩn hóa màu, spacing, radius, elevation, focus, motion, dark mode. Kiểm dependency tokens/utility của component hiện tại trước khi thay.
6. Xây/cải thiện primitive cần dùng: PageHeader, Surface, Empty/Error/Loading, Button/Field/Status nếu giúp các đợt sau nhất quán. Tái sử dụng thứ có thể dùng; không tự xây framework.
7. Loại bỏ visual language Fluent/glow/acrylic ở phần đã làm. Với class cũ còn được component gọi, có thể giữ alias tạm mang thiết kế mới; không tạo lớp override chồng nhiều bản thiết kế.
8. Xác minh shell với role guest/student/staff/admin và mode liên quan. Không gắn số thông báo, tình trạng online hoặc tên người dùng giả.
9. Kiểm auth/public nav; mỗi hành động visible trỏ route có thật hoặc external đúng nguồn. Menu không thay backend authorization.

## Phạm vi
Chủ yếu AppShell, tokens.css, globals.css, layout font wiring, ThemeToggle và shared presentation primitives.
Không redesign nội dung mọi page trong đợt này. Không thay data gateways/feature flags. Navbar/StudentPortal/StaffShell chỉ sửa nếu route đang serve thực sự cần; ghi rõ bằng chứng.

## Xác minh
Từ apps/web: node node_modules/typescript/bin/tsc --noEmit --incremental false.
Chạy các test shell/theme/shared/a11y phù hợp; xác định baseline errors, không làm test giả pass.
Mở đúng runtime từ source apps/web, chưa có runtime thì chạy local ở port rảnh và ghi URL/PID. Không xóa .next/build output có trước để ép chạy.
Ảnh: / ở desktop/mobile cho shell, một dialog/menu mobile, dark mode. Nêu rõ nội dung trang chủ chưa nằm trong phạm vi đợt 01.
Menu mở/đóng, focus return, Tab/Shift+Tab, skip link tới main; không scroll ngang ở 390px.
Báo cáo theo REPORT-TEMPLATE.md và dừng để review đợt 01.
