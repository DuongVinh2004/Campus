# Task làm được ngay — nhóm A, B, C (17/11/2026)

Lọc từ [nhóm A](GROUP_A_IMPLEMENTATION_PLAN_20261117.md), [nhóm B](GROUP_B_DESIGN_20261117.md) và [nhóm C](GROUP_C_DESIGN_20261117.md).

**"Làm được ngay"** nghĩa là task đạt cả sáu điều kiện:
- không cần quyết định của chủ dự án;
- không gọi provider trả phí;
- không tải phần mềm mới;
- không dùng dịch vụ bên ngoài;
- không đổi cách truy hồi hay cách sinh câu trả lời;
- không dùng dữ liệu thật.

Kết quả: **66 task làm được ngay**, **17 task chờ đầu vào**.

Ghi chú khi làm:
- **Cần model server 18081/18082 đang chạy:** B4.1 và C2.1.
- **Thay đổi web:** phải dựng lại snapshot frontend mới thấy trên 8015.
- **Chạy tải A2.8:** dùng cổng thử, không dừng 8015 khi chưa báo.

Ước lượng là số thô, chưa đo. Cỡ task: S < 0,5 ngày · M 0,5–1,5 ngày · L 2–3 ngày.

## Đợt 1 — sửa lỗi và nền móng nhỏ (khoảng 3–4 ngày)

Độc lập với nhau, làm theo thứ tự bất kỳ. Ưu tiên hai lỗi người dùng gặp ngay ở trang lịch.

| ID | Việc | Cỡ | Vì sao trước |
|---|---|---|---|
| B1.1 | Sửa ba lỗi trang lịch: mất ngày giờ gốc, thứ tính theo múi giờ trình duyệt, "Thiết kế…" bị nhận là lịch thi | S | Lỗi hiển thị có thật |
| B1.2 | `lib/ics.ts` đúng RFC 5545 (UID, DTSTAMP, DTSTART/DTEND, CRLF, escape, gập dòng) | S | File `.ics` hiện không nhập được vào ứng dụng lịch |
| A0.1 | Chạy lại ca tái hiện AUD-001/002 trên mã hiện tại | S | Lỗi P1 an toàn, cần biết còn hay không |
| A5.1 | Hợp nhất tên môi trường (AUD-003) + test `create_app` 4 môi trường | S | Mở đường cho CI |
| A5.2 | Sửa biến môi trường của CI | S | — |
| A5.6 | Chạy lại verifier dependency (AUD-005) và test múi giờ (AUD-009), ghi trạng thái | S | Đóng hồ sơ audit |
| C3.1 | Hàm tính trạng thái hiệu lực/rà soát nguồn | S | Nền cho C3 |
| B3.1 | Bộ kiểm nguồn trích dẫn cho câu ôn tập | S | Nền cho B3 |
| B3.2 | Thuật toán lặp lại ngắt quãng | S | Nền cho B3 |

## Đợt 2 — CI đầy đủ và sửa AUD nếu còn (khoảng 2–3 ngày)

| ID | Việc | Cỡ | Phụ thuộc |
|---|---|---|---|
| A0.2 | Nếu A0.1 còn lỗi: kiểm lại quyền trong transaction và trước byte đầu | M | A0.1 |
| A5.3 | `run_full_regression.py --ci` | M | A5.1 |
| A5.4 | Viết lại `ci.yml` theo lock | M | A5.3 |
| A5.5 | Chạy workflow trong container `ubuntu:24.04` (nếu image chưa có thì xin phép tải trước) | M | A5.4 |

## Đợt 3 — sáu nhánh song song (file tách rời)

| Nhánh | Task theo thứ tự | Tổng |
|---|---|---|
| **Vận hành** | A2.1 → A2.2 → A2.3 → A2.4 → A2.5 → A2.6 → A2.7 → A2.8, rồi A3.1 → A3.2 → A3.3 → A3.4 → A3.5 → A3.6 | ~8 ngày |
| **Sao lưu** | A4.1 → A4.2 → A4.3 → A4.4 | ~2 ngày |
| **Đăng nhập** | A1.1 → A1.2 → A1.3 → A1.4 → A1.5 → A1.6 → A1.7 → A1.8 | ~5–7 ngày |
| **Sinh viên** | B1.3 → B1.4 → B1.5 → B1.6; B2.1 → B2.2 → B2.3 | ~4–5 ngày |
| **Tri thức** | C1.1 → C1.2 → C1.3 → C1.4; C3.2 → C3.3 → C3.4 → C3.5; C2.1 → C2.4 → C2.2 (timer cloud); C2.3 sau A2/A3 | ~6–7 ngày |
| **Ôn tập + ngôn ngữ** | B3.3 (migration chỉ trên DB tạm) → B3.4 → B3.5 → B3.6; B4.1 → B4.2 → B4.3 → B4.4 | ~7–9 ngày |

Một người làm tuần tự thì đợt 3 khoảng 32–38 ngày. Thứ tự đề xuất:
1. **Vận hành:** cần trước giai đoạn 2.
2. **Tri thức:** C3 nhỏ, giá trị rõ.
3. **Sinh viên.**
4. **Sao lưu.**
5. **Đăng nhập.**
6. **Ôn tập + ngôn ngữ.**

## Task chờ đầu vào

| ID | Việc | Đầu vào tối thiểu cần |
|---|---|---|
| A5.7 | CI trên GitHub | Duyệt push nhánh |
| A3.7 | Kênh cảnh báo thật | Chọn Telegram/email; bạn tự đặt token vào `.env` |
| A3.8, A4.7 | Watchdog/backup tự động trên máy Windows | Có muốn bật không; ổ đích backup |
| A4.5 | Thử restic thật | Duyệt tải binary restic (ghim sha256) |
| A4.6 | Kho ngoài server thật | Nơi lưu + chi phí + tài khoản do bạn tạo |
| A1.9 | Keycloak cục bộ | Duyệt tải image |
| A1.10 | Nối HUCE | Issuer, client, redirect URI, mô tả claim từ HUCE |
| B1.7 | URL đăng ký lịch có token | Quyết định riêng tư |
| B1.8 | Lịch thật | A1 + API lịch của HUCE |
| B2.4 | Web push | Đồng ý gửi qua dịch vụ push trình duyệt; chọn `pywebpush` hay tự cài |
| B3.3 (áp DB chính) | Bảng ôn tập trên DB thật | Duyệt hash migration 0032 |
| B3.7 | Sinh nháp câu hỏi bằng AI | Ngân sách gọi provider |
| B4.5 | Câu trả lời tiếng Anh | Có cần không (quyết sau số đo B4.1) |
| C1.5 | Sinh viên gửi câu hỏi thiếu thông tin | Duyệt nội dung đồng ý, thời hạn lưu 90 ngày |
| C2.5 | Gate sinh câu trả lời hằng tuần | Ngân sách ~600 lời gọi/tuần |
| C2.6 | Baseline truy hồi | Chọn baseline (đề xuất: lần chạy C2.1 đầu) |
| C3.6 | Hạn rà soát do người đặt | Duyệt hash migration |

## Quy trình mỗi task

Mỗi task chạy trên nhánh riêng (`feat/…`, `fix/…`) và chỉ commit file của task. Commit khi đã kiểm; push chỉ khi được duyệt.
Bằng chứng (lệnh, mã thoát, file kết quả) lưu trong `evals/results/<id>-<stamp>/`.
