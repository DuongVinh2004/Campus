# Bước 1.7: gateway sidecar (2026-11-15)

Tiến trình riêng `scripts/gateway_sidecar.py` (cổng 8025, chỉ loopback) giữ khóa ledger trả phí, ngân sách, giới hạn đồng thời tới provider và
trần chi tiêu theo ngày. Nó dùng nguyên `Gateway` đã giữ lại nên ledger, đặt chỗ và quyết toán, chính sách egress và các cận (28.000 byte,
1000 token đầu ra, 5000 ms mỗi lời gọi) không đổi. API gọi qua `RemoteGateway` với token nội bộ (`gateway-sidecar.token`); tiến trình API
không còn khóa provider, khóa ledger hay đường HTTP tới provider. Launcher khởi động sidecar trước API và đưa URL và đường dẫn token cho API.

| Kiểm chứng | Kết quả |
|---|---|
| Mỗi lời gọi ghi ledger đúng 1 lần (tải giả 50 + 100 người, ledger giả) | sidecar `ok=1746` = 1746 file đặt chỗ = 1746 file kết quả |
| Tải giả không ghi vào ledger trả phí | 202.549 file trước và sau |
| 1 lượt chat thật qua sidecar (provider thật, có trích dẫn) | sidecar `ok=4` lời gọi, ledger trả phí 202.549 → 202.557 (4 đặt chỗ + 4 kết quả) |
| Sidecar chết: API trả lỗi kết nối rõ ("Mình đang gặp lỗi kết nối…"), log `GatewayUnavailable`, không có lời gọi trực tiếp | đạt; ledger trả phí không đổi |
| Vượt trần: từ chối 429 trước mọi lời gọi (`DailySpendCap`, theo thay đổi của snapshot ngân sách trong ngày ICT) | đạt ở test; chưa thử ở runtime thật vì trần local là 0 |
| Sai hoặc thiếu token, body sai hoặc quá lớn | từ chối trước khi chạm gateway (401, 400, 413) |
| Tải giả 100 người qua sidecar, K=12 | lượt chạy p50 10,5 s, p95 12,9 s, tối đa 13,9 s; 503 tối đa 4,5 s; RSS API 524 MB (trước 600–640 MB) |

Trần chi tiêu: **local = 0 (không trần theo ngày)**, đúng chế độ chỉ-kế-toán đã chạy ở máy này từ trước (ledger không có `hard_cap_usd`).
**cloud = 5,00 USD và 2.000 lời gọi mỗi ngày chỉ là giá trị tạm** để gateway cloud không bao giờ chạy không trần; giá trị thật do chủ dự án chọn trước giai đoạn 2.
Trần chặn lời gọi *mới*; lời gọi đang chạy được phép xong, nên vượt trần tối đa khoảng (số lời gọi đồng thời) × (chi phí đặt chỗ của một lời gọi).
Đồng thời tới provider của local giữ 16 (đúng giá trị hiện tại; con số 40 trong bản thiết kế chỉ nâng sau khi đo ở bước 2.4).
Token nằm trong file ở thư mục workspace (quyền mặc định của người dùng Windows); chưa có xoay vòng token.
