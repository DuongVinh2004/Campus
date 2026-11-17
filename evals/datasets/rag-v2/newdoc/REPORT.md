# T16 — Dữ liệu thử nạp tài liệu mới
Tài liệu giả lập: 8793/QĐ-ĐHXDHN; 2.402 từ theo khoảng trắng, khoảng 3–5 trang tùy dàn trang; 11 điều; bảng 3 cột, 5 hàng dữ liệu; liên hệ bằng tên bộ phận.
Chủ đề mới: mượn, sử dụng và hoàn trả máy đọc sách điện tử phục vụ học tập.
Kiểm vắng trên toàn bộ giá trị JSON đã giải mã của 2.019 đoạn kho: casefold, đ→d, NFD bỏ dấu, gộp khoảng trắng; “máy đọc sách”, “đọc sách điện tử”, “mượn máy đọc” đều 0 lần; số hiệu không trùng.
Tổng 25 câu: 18 answer, 7 abstain; UTF-8 với ký tự Unicode nguyên dạng (ensure_ascii=False).
Answer: 001–006 nhiều ý (6), 007–009 hỏi bảng (3), 010–012 điều kiện/ngoại lệ (3), 013–018 còn lại (6).
Abstain: 019–021 gần miền (3), 022–023 ngoài phạm vi (2), 024–025 thiếu đối tượng (2); hai câu thiếu đối tượng có absent_terms rỗng.
Variant trong answer: form=5, no_diacritics=5, keyword=4, slang=4; toàn bộ: form=7, no_diacritics=7, keyword=5, slang=6.
Chạy `python -B evals/datasets/rag-v2/newdoc/check.py`: exit 0, lỗi còn lại=0; code kiểm chuỗi nguồn/facts/quote, từ vắng, câu trùng và phân bố; chỉ tạo dữ liệu, không đo RAG hay đọc mã/kết quả/báo cáo RAG v2.
