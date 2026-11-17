# Đăng nhập bằng tài khoản trường (OpenID Connect): cấu hình và kiểm tra

Trạng thái 17/11/2026: mã đã có và đã kiểm thử với nhà cung cấp giả; **chưa nối với hệ thống đăng nhập của HUCE** vì chưa có thông tin
từ trường (xem `HUCE_INTEGRATION_READINESS_20261025.md`). Đây không phải tích hợp đã hoạt động.

## Cần HUCE cung cấp

| Thông tin | Dùng làm gì | Ghi chú |
|---|---|---|
| Giao thức | Xác nhận trường dùng OIDC | Nếu chỉ có SAML thì cần làm phần SAML riêng (thêm thư viện, cần duyệt) |
| `issuer` | Địa chỉ gốc của nhà cung cấp (có `/.well-known/openid-configuration`) | Phải là https; so khớp chính xác |
| `client_id` đã đăng ký | Định danh ứng dụng | Trường tạo |
| Client secret (nếu có) | Đổi mã lấy token | Đặt trong một **file riêng** trên máy chủ, mode 0600; không đưa vào cấu hình hay chat |
| Địa chỉ chuyển hướng (`redirect_uri`) được duyệt | Nơi trình duyệt quay lại sau khi đăng nhập | Dạng `https://<tên miền>/v1/auth/oidc/callback` |
| Scopes | Quyền đọc thông tin | Thường `openid profile email` |
| Tên claim chứa **mã sinh viên** | Gắn tài khoản với hồ sơ học vụ | Bắt buộc với sinh viên; ví dụ `student_id` |
| Tên claim chứa **nhóm/vai trò** và các giá trị của nó | Phân biệt sinh viên, giảng viên | Ví dụ `groups` = `["sinhvien"]` |
| Môi trường thử, tài khoản thử được phép dùng | Kiểm chứng trước khi mở thật | Chủ thể thử và giới hạn sử dụng |
| Cách thu hồi phiên, giới hạn tốc độ, thời gian cập nhật dữ liệu | Vận hành | |

## Tệp cấu hình mẫu

Lưu ngoài repository (ví dụ `/etc/campus247/oidc.json`, mode 0640). Không có bí mật trong tệp này.

```json
{
  "issuer": "https://sso.example.edu.vn/realms/huce",
  "client_id": "campus247",
  "client_secret_file": "/etc/campus247/secrets/oidc-client-secret",
  "redirect_uri": "https://chat.example.edu.vn/v1/auth/oidc/callback",
  "scopes": ["openid", "profile", "email"],
  "claims": {"student_code": "student_id", "display_name": "name", "roles": "groups"},
  "role_map": {"sinhvien": "STUDENT", "giangvien": "LECTURER"},
  "student_code_pattern": "^[0-9]{6,10}$",
  "jit_provisioning": false,
  "privileged_subjects": [
    {"sub": "<giá trị sub của chủ dự án trong nhà cung cấp>", "roles": ["SYSTEM_ADMIN", "KNOWLEDGE_ADMIN"]}
  ]
}
```

- `role_map` chỉ nhận `STUDENT` và `LECTURER`. Các vai trò `SYSTEM_ADMIN`, `KNOWLEDGE_ADMIN`, `SUPPORT_OFFICER`, `KNOWLEDGE_CONTRIBUTOR`
  **không bao giờ** lấy từ nhà cung cấp; chỉ cấp cho cặp (issuer, `sub`) được chủ dự án liệt kê trong `privileged_subjects`. Cấu hình nào
  cố ý đặt vai trò quản trị trong `role_map` bị từ chối khi khởi động.
- `jit_provisioning: false` (mặc định): người chưa được cấp tài khoản sẽ bị từ chối. Bật `true` nghĩa là bất kỳ ai nhà cung cấp xác thực và
  ánh xạ được vai trò đều có tài khoản; quyết định này thuộc về chủ dự án.
- Sinh viên bắt buộc có mã sinh viên khớp `student_code_pattern`.

## Kiểm tra trước khi bật

```bash
.venv/Scripts/python.exe -B scripts/oidc_preflight.py --config /etc/campus247/oidc.json
```

In PASS / FAIL / WARN từng bước: cấu hình, vai trò, địa chỉ https, tài liệu discovery và `issuer`, PKCE S256, luồng `code`, thuật toán ký
RS256/ES256, bộ khóa ký. Không in bí mật hay token. Đạt kiểm tra này **chưa chứng minh** đăng nhập chạy được.

## Bật

Đặt biến môi trường `CAMPUS247_OIDC_CONFIG=/etc/campus247/oidc.json` cho tiến trình API rồi khởi động lại. Không đặt biến này thì không có gì thay đổi.
Chạy sau Caddy: giữ `X-Forwarded-Proto: https` (Caddy tự thêm); cookie phiên và cookie lượt đăng nhập chỉ được đánh dấu `Secure` khi yêu cầu
đến trực tiếp bằng https hoặc qua proxy trên chính máy này.

Dữ liệu: tài khoản và lượt đăng nhập ở `<state>/oidc.sqlite3` (đã nằm trong sao lưu), khóa ký phiên ở `<state>/oidc-session.key` (mất khóa chỉ làm mọi người
phải đăng nhập lại).

## Giới hạn đã biết

- Phiên của ứng dụng dài tối đa 1 giờ; tài khoản bị khóa phía nhà cung cấp chỉ mất hiệu lực ở lần đăng nhập sau. Chưa có back-channel logout và chưa gọi
  `end_session_endpoint` của nhà cung cấp khi đăng xuất.
- Vai trò được ghi vào phiên lúc đăng nhập; đổi vai trò có hiệu lực ở lần đăng nhập sau.
- Chưa có nút "Đăng nhập bằng tài khoản trường" trên trang `/login` (xem tiến độ); hiện chỉ vào được bằng địa chỉ `/v1/auth/oidc/start`.
- Chưa kiểm với Keycloak thật hay nhà cung cấp thật; chưa kiểm bằng trình duyệt.
