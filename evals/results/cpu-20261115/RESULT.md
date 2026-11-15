# Bước 1.9: giảm CPU và gỡ nghẽn embedding (2026-11-15)

Đo bằng tải giả (provider giả), 2 worker API, 100 người nghĩ 8–25 s. Máy này vẫn chạy cả Chrome, Claude, Defender (khoảng 1,7 lõi), nên số đo
có nhiễu; mọi lần so sánh dùng cùng cách đo.

## Nguyên nhân tìm được

1. **Nghẽn embedding là vòng phản hồi.** Mọi yêu cầu embedding xếp hàng sau một khóa chung. Khách chỉ chờ 1,0 s rồi bỏ nhưng yêu cầu vẫn nằm trong hàng và mô hình **vẫn chạy nó**:
   việc vô ích làm hàng dài thêm và gây thêm lần quá hạn. Mỗi lần embed còn tốn 2 yêu cầu (một lần kiểm danh tính `/info` cộng một lần `/embed`, mỗi lần một lượt khóa và một file ledger)
   và dựng mới một client HTTP kèm kho chứng chỉ TLS (khoảng 10 ms CPU).
2. **CPU của API.** Khoảng một phần tư thời gian CPU bận của API là băm lại nội dung mọi dòng nguồn được phép ở mỗi lượt (`_rows_fingerprint`).
   Sau đó là mở SQLite nhiều lần mỗi lượt (kiểm thu hồi phiên, hội thoại) kèm kiểm tra đường dẫn.

## Thay đổi (không đổi vector, không đổi kiểm tra nào)

| Thay đổi | Tác dụng |
|---|---|
| Máy chủ mô hình bỏ qua yêu cầu mà khách đã ngắt kết nối (chỉ nhìn, không tiêu thụ dữ liệu); ghi nhận `http-…-abandoned` | hết việc vô ích, hàng ngắn lại |
| Kiểm danh tính mô hình tối đa 30 s một lần (và lại ngay sau mọi lỗi) thay vì mỗi lần embed | một nửa số yêu cầu và lượt khóa |
| Client embedding không dựng kho chứng chỉ TLS (HTTP loopback) | bớt khoảng 10 ms CPU mỗi lần |
| Bộ nhớ đệm vector câu hỏi (cùng văn bản thì cùng vector), chia sẻ cuộc gọi đang chạy, không giữ lỗi, người chờ hết giờ không hủy cuộc gọi chung | câu hỏi lặp chỉ embed một lần |
| Embed câu hỏi **sớm**, lúc lượt chat bắt đầu phân loại an toàn và định tuyến (1–2 s chờ provider), thay vì chờ trong cửa sổ 1,0 s của truy xuất | giấu hàng đợi sau thời gian chờ provider; câu hỏi tiếp nối hoặc không tìm kiếm thì bỏ qua |
| Băm nội dung mỗi dòng nguồn một lần cho mỗi đối tượng chuỗi (chuỗi không đổi tại chỗ nên `is` chứng minh nội dung không đổi; các trường khác so sánh theo giá trị) | bỏ phần CPU lớn nhất của API |

## Kết quả (câu hỏi không lặp: 100 người × 2 câu, rút không hoàn lại từ 220 câu, API khởi động mới nên bộ nhớ đệm trống)

| | Trước | Sau |
|---|---|---|
| Mất nhánh vector (`vector_failed`) | khoảng 37–52 % | **0,7 %** (1 trên 150 lần truy xuất; lần chạy trước 0 trên 150) |
| p95 lượt chạy | 14,8 s (tải lặp câu hỏi) | **14,3 s** (lâu nhất 16,0 s) |
| Thành công | 96,7–97,7 % | **98,5 %** (lần chạy trước 97,5 %) |
| CPU mỗi lượt: API | 0,89 s | 0,65 s |
| CPU mỗi lượt: máy chủ mô hình | 0,94 s | 0,65 s |
| CPU Postgres, sidecar | 0,22 s, 0,07 s | 0,14 s, 0,04 s |

Tiêu chí bước 1.9 (kịch bản A, câu hỏi không lặp): `vector_failed` ≤ 1 % **đạt**; p95 ≤ 15 s **đạt**; thành công ≥ 99 % **chưa đạt** (98,5 %, hai lần chạy 97,5–98,5 %).
Phần thiếu không phải lượt phục vụ bị lỗi: cả 197 lượt đã chạy đều thành công. 3 trên 200 lượt bị cổng admission báo bận 4 lần liền lúc dồn đỉnh rồi bỏ cuộc.
Nhu cầu của kịch bản A khoảng 200 lượt/phút còn máy này phục vụ khoảng 107–120. Hai worker API đã chạm trần một lõi mỗi worker lúc đỉnh (peak 2,55 lõi).
Worker thứ ba cần thêm khoảng 0,9 GB bộ nhớ riêng nhưng máy chỉ còn khoảng 1,25 GB trống với hai worker đang chạy, nên không bật. Theo bảng rủi ro của kế hoạch,
không hạ tiêu chí; các lựa chọn là chấp nhận mục tiêu kịch bản B kèm 503 khi bị dồn, hoặc xét INT8 (mục 6 bản thiết kế), hoặc để VPS 4 vCPU / 8 GB đo ở bước 2.3.

## Còn lại và chưa đo

- Còn khoảng 25 % CPU API trong mở SQLite và kiểm tra đường dẫn (mỗi lần mở kiểm lại chống reparse point); mình **không** nới các kiểm tra này để lấy CPU. Có thể giảm số lần mở bằng cách gộp các lần kiểm tra thu hồi trong một lượt, nhưng việc đó đổi độ trễ thu hồi phiên nên cần quyết định riêng.
- Máy chủ mô hình: embedding FP32 vẫn khoảng 0,65 s CPU mỗi lượt (không đổi model, không đổi luồng ONNX, không đổi vector).
- Chưa đo ảnh hưởng lên chất lượng câu trả lời: bước 1.10 chạy gate với provider thật. Vector không đổi nên không kỳ vọng thay đổi, nhưng chưa có số.
- Bộ nhớ đệm vector mỗi worker giữ riêng (không chia sẻ giữa worker).

## Cập nhật cuối ngày: tái dùng kết nối SQLite đóng nốt kịch bản A

Profile lại ở 100 người cho thấy phần CPU còn lại của API nằm ở việc mở SQLite: kiểm thu hồi phiên và đọc ghi hội thoại mở file hơn chục lần mỗi lượt
(mỗi lần mở gồm kiểm đường dẫn `resolve` và duyệt reparse point của mọi thư mục cha, hai pragma và kiểm schema), khoảng một phần năm CPU bận của API.

Thay đổi (`sqlite_reuse.py`, dùng ở kho hội thoại và kho trạng thái người dùng): mỗi luồng giữ một kết nối tối đa 2 giây rồi đóng và mở lại qua **toàn bộ** đường kiểm cũ
(đường dẫn, schema, tenant), nên các lớp bảo vệ vẫn chạy mỗi 2 giây và sau mọi lỗi. Một kết nối chỉ cho một người dùng tại một thời điểm: dùng lồng nhau hoặc xen kẽ trên cùng luồng nhận kết nối mới như cũ,
nên không giao dịch nào commit hoặc rollback giao dịch khác; mỗi lần dùng vẫn kết thúc bằng `with connection:`, kết nối rảnh không giữ giao dịch hay khóa.

Kịch bản A (100 người × 2 câu, không lặp, API mới khởi động nên bộ nhớ đệm trống), ba lần chạy:

| Lần | Thành công | p50 / p95 / lâu nhất | 503 lâu nhất | Mất vector |
|---|---|---|---|---|
| 1 | 100 % | 9,4 / 11,8 / 13,8 s | 4,2 s | 0 |
| 3 | 99,5 % | 9,1 / 11,6 / 12,8 s | 4,5 s | 0 |
| 4 | 100 % | 9,4 / 11,9 / 12,7 s | 4,4 s | 0 |

(Lần 2, chạy tiếp trên cùng tiến trình nên có hưởng bộ nhớ đệm, không dùng làm số chính: 99,5 %.) Trung bình 99,8 %.
Tiêu chí kịch bản A của bước 1.9 **đạt**: `vector_failed` ≤ 1 %, p95 ≤ 15 s, thành công ≥ 99 %, 503 trong 5 s.
Số đo tại máy này, còn nhiễu từ Chrome, Claude và Defender; mỗi lần chạy 200 lượt nên một lượt hỏng đổi 0,5 điểm.
