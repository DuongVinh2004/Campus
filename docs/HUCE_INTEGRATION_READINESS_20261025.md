# HUCE SSO và API học vụ: kiểm tra hiện trạng ngày 25/10/2026

Chưa kết nối SSO hoặc API học vụ HUCE thật. Kiểm tra các tên cấu hình liên quan
trong môi trường tiến trình, `.env`, `.env.example` và cấu hình frontend đã biết
không thấy issuer/client/API/scopes HUCE. Không xuất giá trị cấu hình hoặc bí mật.
Kết luận này chỉ áp dụng các vị trí đã kiểm trong workspace; không khẳng định
HUCE chưa cấp thông tin ở nơi khác.

Runtime local dùng `LocalOwnerIdentityAdapter` trong tenant `huce-local-public`.
Cổng lịch học hiện có `ScheduleReadPort`, nhưng adapter hiện hành là dữ liệu
tổng hợp. Tài khoản local và nguồn công khai không cấp quyền đọc hồ sơ HUCE.

## Thông tin cần HUCE cung cấp

| Hạng mục | Bằng chứng cần có trước khi nối |
|---|---|
| Danh tính | Giao thức HUCE hỗ trợ, issuer/metadata chính thức, audience, quy tắc ánh xạ subject và vai trò |
| Client | Client đã đăng ký, callback/redirect URI được chấp thuận, cách nhận bí mật qua cấu hình bảo mật |
| Học vụ | Tài liệu API/version, base URL, các route được cấp; không đoán route từ URL cổng sinh viên |
| Quyền | Scopes và quyền đọc dữ liệu cụ thể, môi trường, chủ thể kiểm thử được cho phép và giới hạn sử dụng |
| Vận hành | Timeouts/rate limits, lỗi và thời điểm cập nhật dữ liệu, đầu mối xác nhận thu hồi phiên/quyền |

## Phần kỹ thuật đã chuẩn bị

Đã kiểm tra các điểm nối hiện có: `IdentityProviderPort.extract_identity`,
`IdentityContext`, `ScheduleReadPort.get_student_profile/list_schedule`,
`StudentProfileSnapshot`, `SchedulePage` và composition trong `bootstrap/app.py`.
Chưa chọn OIDC, SAML hoặc giao thức API thay HUCE và chưa viết adapter giả làm
kết nối thật. Khi có tài liệu, adapter phải dùng đúng giao thức và chỉ ánh xạ
quyền từ issuer đã xác minh; vai trò quản trị không được lấy từ dữ liệu tự khai.

Lượt kết nối đầu cần kiểm chứng token/issuer/audience/expiry, ánh xạ subject
được cấp quyền, truy cập `/me` đúng chủ thể, từ chối truy cập chéo người dùng,
thu hồi phiên và lỗi dịch vụ. Chỉ đo kết quả từ môi trường được cấp. Giữ các
kiểm soát auth, preview, confirmation, idempotency, audit và egress hiện hành.
Chưa có kết quả nào trong số này được đánh dấu là tích hợp HUCE thật thành công.

Biên bản kiểm tra đã lưu ở
`infra/local/huce-completion-20261025-02/integration-preflight-01.json`.
Lệnh kiểm lại tạo biên bản mới phải dùng đích mới để giữ bằng chứng cũ; không
chạy lại lệnh ghi vào file 01 đã tồn tại.
