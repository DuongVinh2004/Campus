# Bước 1.5: rate limit dùng chung (2026-11-15)

`PostgresRateLimiterStore` (cửa sổ trượt trong Postgres, quyết định dưới khóa advisory theo từng khóa, giờ lấy từ đồng hồ database).
Chọn bằng `CAMPUS247_RATE_LIMIT_STORE=postgres` (launcher đặt cho API; mặc định `memory`). Quy tắc và hành vi middleware giữ nguyên:
30/phút cho `/v1/conversations`, `fail_closed=True`, 429 kèm `Retry-After`, 503 khi store lỗi.

| Kiểm chứng | Kết quả |
|---|---|
| 3 pool độc lập (đại diện 3 tiến trình) đua trên một khóa, 90 yêu cầu, giới hạn 30 | đúng 30 được phép, 60 bị chặn |
| Đếm lùi `remaining`, `Retry-After`, khóa khác độc lập, cửa sổ hết hạn | đạt |
| Store lỗi hoặc không có pool | middleware trả 503 `Retry-After: 30` (fail closed); luật fail-open vẫn phục vụ |
| Runtime 8015 thật, 35 yêu cầu liên tiếp vào `/v1/conversations/...` | 30 qua, 5 bị 429; `Retry-After: 59`; 35 yêu cầu trong 0,38 s (khoảng 11 ms mỗi yêu cầu gồm cả limiter) |

Bảng `app_rate_limit_hit` được tạo lười lần dùng đầu (`CREATE TABLE IF NOT EXISTS`, tuần tự hóa bằng khóa advisory), chưa có migration Alembic:
thêm migration sẽ buộc nâng tập phiên bản chấp nhận ở nhiều nơi. Hàng tự rời cửa sổ và bị xóa ở lần gọi kế tiếp của cùng khóa; cứ 500 lần gọi dọn hàng cũ hơn một ngày.
Chưa đo: tải thật 100 người với limiter Postgres (bước 1.8 và 1.9 sẽ đo khi có nhiều tiến trình); test đua dùng pool trong cùng một tiến trình, không phải 3 tiến trình hệ điều hành.
