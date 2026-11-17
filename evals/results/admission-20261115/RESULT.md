# Bước 1.2: admission control, kết quả đo (2026-11-15)

Tải giả (provider giả, không tốn phí), 1 tiến trình API, 100 học sinh ảo × 3 câu, nghĩ 8–25 s, tối đa 3 lần hỏi lại sau 503.
Học sinh ảo chạy chung máy với API nên số đo chậm hơn thực tế một chút.

| Cấu hình | Lượt chạy: p50 / p95 / max | 503 lâu nhất | Bỏ cuộc sau 3 lần thử | Lượt/phút | File |
|---|---|---|---|---|---|
| Mốc (không giới hạn) | 24,4 / 35,7 / 42,9 s | — | 21 lỗi `system_error` (7 %) | 111,6 | `fake9-100real.json` |
| K=24, chờ 5 s | 20,4 / 24,8 / 27,8 s | 6,6 s | 56 | 88 | `p12-adm-100.json` |
| K=12, chờ 5 s | 13,3 / 16,9 / 20,4 s | 6,0 s | 97 | 91 | `p12-adm-100-k12.json` |
| **K=12, chờ 4 s (chọn)** | **11,3 / 14,7 / 17,8 s** | **4,8 s** | 99 | 96 | `p12-adm-100-k12-w4.json` |

Tiêu chí bước 1.2 (1 tiến trình, 100 người): không lượt nào quá 22 s và 503 trả về trong 5 s. Đạt ở cấu hình đã chọn.

Đọc số: nhu cầu khoảng 267 lượt/phút còn một tiến trình chỉ làm được khoảng 100, nên khoảng một phần ba lượt vẫn không được
phục vụ sau 3 lần thử. Cổng không tạo thêm năng lực; nó đổi "treo 30–40 s rồi lỗi" thành "chạy nhanh hoặc được báo bận ngay".
Năng lực thật chỉ tăng ở các bước 1.8 (nhiều worker) và 1.9 (giảm CPU).
Một lượt bị từ chối không lưu gì (không có tin nhắn dở). Thời gian "lượt chạy" gồm cả thời gian chờ slot tối đa 4 s.
