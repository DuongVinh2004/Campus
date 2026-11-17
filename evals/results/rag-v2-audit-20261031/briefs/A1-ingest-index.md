# A1 — Nạp tài liệu, dựng chỉ mục và vòng đời chỉ mục khi có tài liệu mới
Đọc `A0-common.md` cùng thư mục trước và tuân thủ nguyên văn. Mã phiên: A1.

Phạm vi đọc chính: `rag_v2/ingest/units.py`, `rag_v2/ingest/checks.py`, `rag_v2/facts/extract.py`, `rag_v2/adapters/{index_store,memory_index,npy,runtime}.py`, `scripts/rag_v2_build_index.py`, `evals/runners/corpus_export.py`, `bootstrap/rag_v2.py` (phần nạp chỉ mục), `evals/runners/rag_v2_newdoc.py`, tests tương ứng trong `tests/rag_v2/`.

Câu hỏi bắt buộc trả lời (có bằng chứng):
1. Đường đi đầy đủ của MỘT tài liệu mới từ lúc được duyệt/phát hành trong nền tảng tri thức (`application/knowledge/**`, release/generation) tới lúc v2 trả lời được nó. Có tự động không? Nếu chỉ mục là tệp tĩnh dựng tay: khi DB có chunk mới mà chỉ mục chưa có, hệ thống làm gì (im lặng `no_source`? lỗi? cảnh báo?). Khi tài liệu bị thu hồi/hết hiệu lực/thay thế thì sao? Có kiểm `corpus_sha256`/release giữa chỉ mục và DB lúc khởi động hay mỗi lượt không?
2. Tách đơn vị (`units.py`) phụ thuộc vào nhãn `family` của kho hiện tại (`so_tay`, `ctdt`…) và regex tiếng Việt cụ thể ("STT", "mã học phần", "chương trình đào tạo") đến mức nào? Tài liệu mới không có family đã biết, bảng có tiêu đề cột khác, bảng nhiều tầng tiêu đề, danh sách đánh số kiểu khác (a), b), i., Điều/Khoản/Mục, Chương), văn bản thuần không xuống dòng, nội dung OCR lỗi, bảng gộp ô — mỗi loại cho ra unit thế nào? Dùng `served-chunks.jsonl` và tự dựng 4–6 chuỗi đầu vào mẫu (trong bộ nhớ) để chạy hàm tách ngoại tuyến và đo.
3. `facts/extract.py` chỉ trích dữ kiện học phí? Dữ kiện có kiểu dùng ở đâu trong đường trả lời; tài liệu học phí mới với bảng khác cột sẽ bị trích sai/nhầm thế nào (rủi ro trả lời sai từ nhánh dữ kiện bỏ qua kiểm ngữ nghĩa)?
4. Kiểm tra khi dựng (`checks.py`, coverage trong manifest): có phát hiện tài liệu mới bị tách mất nội dung không; ngưỡng là gì; dựng lỗi một phần có bị chấp nhận không.
5. Tính toàn vẹn và tái lập: embed-cache, đổi mô hình nhúng, đổi chiều vector, manifest không ký (REPORT §10 mục 5), thứ tự unit có ổn định giữa các lần dựng không; chi phí dựng lại toàn bộ khi chỉ thêm 1 tài liệu (thời gian, có dựng tăng dần được không).
6. Quy mô: ước bộ nhớ/thời gian khởi động khi kho tăng ×3–×5.

Kết thúc bằng một mục "Thiết kế đề xuất cho vòng đời chỉ mục" (≤ 25 dòng): cách để tài liệu mới được phục vụ mà không cần sửa mã, có kiểm đối chiếu DB↔chỉ mục, và cổng chất lượng tự động khi nạp.
