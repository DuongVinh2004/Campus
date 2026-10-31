# A3 — Sinh, kiểm chứng, kết quả có kiểu: đúng nội dung và ổn định
Đọc `A0-common.md` cùng thư mục trước và tuân thủ nguyên văn. Mã phiên: A3.

Phạm vi đọc chính: `rag_v2/service.py`, `rag_v2/generation/{generate,prompt,rewrite,json_output,contacts}.py`, `rag_v2/verification/{deterministic,semantic}.py`, `rag_v2/outcome/compose.py`, `rag_v2/discipline.py`, `rag_v2/types.py`, `rag_v2/observability/trace.py`, tests tương ứng; công cụ chẩn đoán `evals/results/rag-judge-20261028/runs/{thin_diag,ver_why,trace_rejections}.py` (chỉ để hiểu).

Câu hỏi bắt buộc trả lời (có bằng chứng):
1. Prompt sinh/viết lại/kiểm ngữ nghĩa có ví dụ hoặc chỉ dẫn gắn với kho hiện tại không (ví dụ "K70_and_earlier", "KS/KTS")? Tài liệu mới có quy ước đặt tên/phạm vi khác thì mô hình bị dẫn sai thế nào?
2. Kiểm xác định (`deterministic.py`): liệt kê từng luật (số không có trong nguồn, phủ định theo cụm/câu, mã, trích dẫn…), điều kiện kích hoạt, và trường hợp dương tính giả/âm tính giả với văn phong khác (văn bản luật nhiều phủ định kép, bảng số liệu, đơn vị tiền/khối lượng khác, ngày dạng khác "ngày 01 tháng 9 năm 2026" và "01/09/2026", số La Mã, số viết bằng chữ, phần trăm). Viết 10–20 cặp (nguồn, phát biểu) mẫu và chạy `check_statement` ngoại tuyến để chứng minh từng điểm. Phát biểu SAI nào lọt qua kiểm xác định và chỉ còn kiểm ngữ nghĩa chặn?
3. Kiểm ngữ nghĩa: khi lời gọi lỗi/quá hạn/JSON hỏng thì kết quả là gì (từ chối an toàn hay nhận phát biểu)? Có đường nào phát biểu chưa kiểm ngữ nghĩa được hiển thị (nhánh dữ kiện, phát biểu "đơn giản")? `REPAIRABLE` và vòng sửa một lần có thể đưa phát biểu sai vào không?
4. Đóng gói ngữ cảnh: `CONTEXT_BYTES`, ≤6 hàng, đoạn cha ≤19 KB, trần 28 KB của cổng; tài liệu mới có đoạn cha rất dài (ví dụ một chunk 60 KB, bảng 500 hàng) thì bị cắt thế nào, có cắt mất điều kiện/ngoại lệ không, có báo `partial` trung thực không.
5. Câu hỏi nhiều ý (nút thắt A1 trong REPORT): hiện có cơ chế kiểm độ phủ từng ý chưa? Đề xuất cơ chế tổng quát, kiểm được bằng mã.
6. Quyết định `decision` của mô hình (answer/clarify/no_source/out_of_scope): ánh xạ sang kết quả, các kiểm chặn mô hình tự tuyên bố sai (ví dụ `answer` mà 0 phát biểu qua kiểm), độ ổn định giữa các lượt (nhiệt độ, seed, thứ tự nguồn).
7. `discipline.py`, `contacts.py`: luật theo cụm từ cụ thể ("kỷ luật") — tổng quát được không, có nên tồn tại trong lõi không.
8. Ngân sách thời gian, thử lại, hủy, xử lý ngoại lệ trong `service.py`: có nhánh nào ném ngoại lệ chưa bắt (REPORT đã gặp `UnboundLocalError`), có rò nội dung vào log không; đọc kỹ từng nhánh lỗi.

Kết thúc bằng mục "Thiết kế đề xuất cho sinh + kiểm chứng ổn định trên văn phong mới" (≤ 25 dòng).
