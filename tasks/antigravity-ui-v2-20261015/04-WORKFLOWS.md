# Đợt 04 — Hoàn thiện toàn bộ màn hình nghiệp vụ

Áp dụng MASTER và hệ thiết kế đã chốt. Đây là đợt phủ các route còn lại, không chỉ phủ CSS lên nội dung cũ.

## Thực hiện lần lượt, đọc đúng tệp khi đến nhóm đó
A. Hồ sơ sinh viên: /tickets, /services; app/tickets/page.tsx, TicketList, DocumentRequestForm, CertificateWorkspace, ServiceWorkspace.
B. Cán bộ: /staff và các panel staff được route thực dùng; StaffTicketQueue và nhánh CertificateWorkspace staff.
C. Lịch/phòng: /schedule, /rooms; ScheduleView, RoomBooking, UnavailableStudentSurface.
D. Tri thức/quản trị: /knowledge, /knowledge/sources, /knowledge/policy-graph, /admin; KnowledgeReview, SourceOperations, PolicyGraphReview, admin layout/page.
E. Cá nhân: /privacy, /memory, /notifications; PrivacyCenter, AssistantSettingsCenter, MemoryCenter, NotificationCenter.
Không tạo route mới chỉ để dùng component cũ. Ghi ma trận route → implementation/variant → trạng thái hoàn tất trong báo cáo ngắn.

## Hướng UX cho từng nhóm
- Sinh viên: phân biệt hồ sơ mới, nháp, đã gửi, cần bổ sung và có kết quả. Danh sách dễ quét, tìm/lọc có ích; detail rõ thông tin, tài liệu và bước tiếp theo.
- Form: nhãn/mô tả/error cùng trường; chia nhóm theo ý nghĩa; bước review/confirm rõ “chưa gửi/đã gửi”; lưu nháp và readback giữ nguyên.
- Cán bộ: hàng đợi gọn, priority và assignment rõ; detail tập trung vào quyết định; không lộ ghi chú nội bộ sang nội dung sinh viên. Quyền, mandatory review, phiên bản và preview vẫn bắt buộc.
- Lịch/phòng: calendar/list responsive và trạng thái freshness/conflict; thiếu tích hợp thì unavailable state có giải thích và lối hỗ trợ. Không bịa lịch/phòng trống.
- Tri thức: nguồn, phiên bản, bằng chứng và thao tác review/publish phân cấp rõ; graph không được tràn layout. Mọi write vẫn đúng quyền/xác nhận.
- Cá nhân: nhãn người dùng hiểu; scope consent/history/memory/notification riêng biệt, trạng thái đã lưu đúng readback. Không đánh đồng “quên” với xóa vật lý hay thông báo ứng dụng với email/SMS đã gửi.
- Với mọi nhóm: PageHeader/Surface/Field/Status dùng thống nhất; bỏ dấu vết layout/thẩm mỹ cũ ở phần reachable. Đảm bảo cả loading/empty/error/dialog và dark mode, không chỉ happy path.

## Phạm vi và kết quả
Sửa UI của cây component tương ứng trong apps/web/src; không thay src/lib, gateways, backend/contracts hoặc test thresholds để vượt lỗi.
Không thay hàng loạt bằng find/replace xuyên repo. Sau mỗi nhóm kiểm routes và behavior liên quan, rồi tiếp tục nhóm kế tiếp mà không hỏi quyền lại.
Không xóa component chưa dùng, dữ liệu, evidence hay snapshot.
Typecheck và test affected. Chọn khoảng 6 ảnh đại diện: form + preview, student list/detail, staff queue/detail, knowledge/admin, mobile, dark. Toàn bộ route còn lại ghi trạng thái và evidence URL, tránh hàng chục ảnh lặp.
Nếu API không chạy, vẫn hoàn thiện error/unavailable presentation; phần chức năng chưa xác minh ghi NOT_VERIFIED, không fake success.
Báo cáo theo REPORT-TEMPLATE.md và dừng đợt 04.
