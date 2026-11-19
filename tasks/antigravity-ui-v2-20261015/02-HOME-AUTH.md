# Đợt 02 — Trang chủ và đăng nhập

Áp dụng MASTER và nền tảng đã chốt ở đợt 01. Đích: vào ứng dụng dễ hiểu, tổng quan có ích và trải nghiệm đăng nhập hoàn chỉnh.

## Đọc
src/app/page.tsx và test liên quan; src/app/login/page.tsx; AuthLayout.tsx; nhánh CertificateLogin trong features/documents/CertificateWorkspace.tsx; contract/props liên quan trong store chỉ khi cần.

## Thiết kế và thực hiện
- Xây lại trang chủ với lời chào/phân cấp dễ đọc; khu vực hỏi trợ lý là điểm nhấn, không hero quảng cáo khổng lồ.
- Lối tắt cho yêu cầu học vụ, giấy xác nhận, lịch học, phòng học; link phải đúng route/mode. Mỗi card nêu việc có thể làm và hành động cụ thể.
- Lịch tiếp theo và hồ sơ cần chú ý chỉ dùng dữ liệu có nguồn đã cấp. Không bịa lịch hoặc nhận diện người dùng để lấp chỗ trống. Nếu chưa có data, thiết kế trạng thái “chưa kết nối/chưa có/đăng nhập” và bước tiếp theo thích hợp.
- Giữ các nhánh user/status/searchParams, degraded/unavailable capabilities, anonymous/private-data boundary và query gửi tới chat. Không bỏ trạng thái lỗi chỉ để trang luôn đẹp.
- Xây lại AuthLayout và form login: layout desktop cân đối, mobile tập trung vào form; nhãn rõ, password reveal, autofill, loading/error, trợ giúp và quay lại ứng dụng.
- Cả login chuẩn và CertificateLogin phải theo cùng thiết kế. Giữ nguyên auth logic; không in credential lên ảnh/báo cáo hoặc thay demo credentials.
- Link privacy/help và mọi CTA phải có đích hoặc tương tác thực, không nút trang trí.
- Dùng component/tokens đã có, không cài framework mới hay thêm font làm chậm tải.

## Phạm vi và kiểm tra
Thay mã UI trong đúng page/component trên, không refactor store/API.
Kiểm default và feature variants hiện có bằng fixture được xác định; không thay global flags đang phục vụ.
Kiểm guest, empty, API error, disabled capability, login invalid/success bằng fixture; giữ drafts khi lỗi.
Nếu một test khớp nguyên tiêu đề/bố cục cũ, cập nhật tối thiểu cho trải nghiệm mới; giữ mọi assertion về privacy, trạng thái, link và behavior.
Typecheck + test home/auth ảnh hưởng. Ảnh / và /login ở desktop/mobile; thêm một empty/error và dark mode.
Báo cáo theo REPORT-TEMPLATE.md. Không tự chấm điểm trải nghiệm hoặc gọi thành công auth nếu chưa thử.
