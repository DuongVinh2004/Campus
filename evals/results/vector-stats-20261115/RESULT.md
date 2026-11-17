# Bước 1.3: chỉ số `vector_failed` (2026-11-15)

Nhánh vector của truy xuất hybrid chỉ được 1,0 s; quá hạn hoặc lỗi thì hệ thống lặng lẽ dùng kết quả từ khóa. Trước bước này
không có số liệu nào cho việc đó. Giờ mỗi lần truy xuất được đếm trong tiến trình API và ghi log (không chứa chữ, mã định danh hay nội dung lỗi):

- `rag_v2_vector_failed reason=timeout|error ms=<số>` cho mỗi lần mất nhánh vector;
- `rag_v2_vector_stats retrievals=.. failed=.. timeouts=.. failed_rate=.. vector_ms_max=..` sau mỗi 25 lần truy xuất (số cộng dồn từ lúc API khởi động);
- `chat_admission_rejected in_flight=.. waiting=.. limit=.. rejected_total=..` cho mỗi 503 (từ bước 1.2).

## Đo ở mức tải giả (1 tiến trình API, provider giả, máy chủ embedding thật, K=12; `p13-vector-50-100.json`)

| Giai đoạn | Lần truy xuất | Mất nhánh vector | Tỉ lệ | Nguyên nhân ghi nhận |
|---|---|---|---|---|
| 50 người × 3 câu | khoảng 150 | 39 | **khoảng 26 %** | 100 % do quá 1,0 s |
| 100 người × 3 câu | khoảng 200 | 143 | **khoảng 71 %** | 100 % do quá 1,0 s |
| Cả hai | 350 | 182 (52 %) | | 182 quá hạn, 0 lỗi khác; vector chậm nhất 1,38 s |

Số theo giai đoạn tính từ chênh lệch giữa các dòng tổng kết (mỗi dòng cách 25 lần), nên là xấp xỉ.

Ý nghĩa: ở tải 100 người, đa số lượt trả lời chỉ dựa vào tìm kiếm từ khóa mà không có tín hiệu lỗi nào. Đó là điểm nghẽn thật của máy chủ embedding
(một khóa chung, chạy tuần tự), và là lý do bước 1.9 đặt tiêu chí `vector_failed` ≤ 1 % cùng thông lượng. Bước này chỉ đo, chưa sửa gì.
Chưa đo: ảnh hưởng của việc mất vector lên chất lượng câu trả lời (cần gate với provider thật).
