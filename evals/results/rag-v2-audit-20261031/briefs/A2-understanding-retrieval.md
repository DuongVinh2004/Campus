# A2 — Hiểu câu hỏi và truy xuất: khả năng tổng quát sang tài liệu mới
Đọc `A0-common.md` cùng thư mục trước và tuân thủ nguyên văn. Mã phiên: A2.

Phạm vi đọc chính: `rag_v2/understanding/{analyze,normalize}.py`, `rag_v2/retrieval/{bm25,hybrid,neighbors}.py`, `rag_v2/adapters/http_reranker.py`, `rag_v2/service.py` (phần gọi retrieve, scope, fact lookup), source_snapshot trong `application/knowledge/**` (`scope_allows`), tests tương ứng; `evals/runners/rag_v2_retrieval_probe.py`, `rag_v2_context_probe.py` (để hiểu cách đo ngoại tuyến).

Câu hỏi bắt buộc trả lời (có bằng chứng):
1. Liệt kê MỌI từ vựng/luật viết tay gắn với kho hiện tại trong hiểu câu hỏi (bảng chủ đề `hoc_phi`/`quy_che`…, `_SUGGEST`, danh sách từ dừng, bảng viết tắt trong `normalize.py`, luật thiếu phạm vi học phí, `own_school`, luật ngoài phạm vi). Với mỗi luật: nó ảnh hưởng quyết định nào (từ chối/hỏi lại/lọc/định hướng truy xuất); câu hỏi về một chủ đề MỚI không có trong bảng (ví dụ quy định mượn thiết bị, nghiên cứu khoa học, ký túc xá mới) đi qua đường nào; có luật nào có thể từ chối/hỏi lại nhầm câu hỏi hợp lệ về tài liệu mới không. Tự viết 10–15 câu hỏi mẫu về chủ đề không có trong bảng và chạy `analyze` ngoại tuyến để chứng minh.
2. Truy xuất lai (BM25 + vector + nhánh neo mã + RRF): tham số (k, kích thước nhánh, k RRF, giới hạn top), cách hòa điểm (A6 nhất quán), hiện tượng "một tài liệu lớn chiếm hết chỗ" (REPORT §18.1 đã thấy với tiêu đề tài liệu) — đã có cơ chế tổng quát chưa? Khi kho tăng gấp 3 hoặc có tài liệu mới dài lặp tiêu đề, recall của tài liệu ngắn bị ảnh hưởng thế nào? Đo bằng script ngoại tuyến trên `data/rag_v2_index/embedded` nếu chạy được (nhánh BM25 không cần mô hình nhúng; nếu cần vector cho câu hỏi thì ghi rõ không đo được).
3. Bộ lọc phạm vi (khóa/ngành/năm/hiệu lực; `scope_allows(..., any_requested=True)` của §19): tài liệu mới không khai khóa/ngành thì có bị lọc mất không; tài liệu mới khai phạm vi theo cách khác (ví dụ "áp dụng từ K70", "các khóa tuyển sinh từ 2024") được hiểu không; luật nào phụ thuộc định dạng mã K\d\d.
4. Văn bản thay thế: khi có hai phiên bản quy chế (cũ hết hiệu lực, mới), truy xuất/ủy quyền chọn bản nào; có ưu tiên bản mới/hiệu lực không; mâu thuẫn giữa hai nguồn được phát hiện ở đâu.
5. Reranker: đang tắt; đường dự phòng khi bật/tắt; có rủi ro hành vi khác nhau giữa môi trường không.
6. Hiệu năng truy xuất mỗi lượt và độ phức tạp theo số unit.

Kết thúc bằng mục "Thiết kế đề xuất cho hiểu câu hỏi + truy xuất không phụ thuộc kho" (≤ 25 dòng): thay từ vựng viết tay bằng gì (ví dụ từ vựng/viết tắt sinh tự động từ kho lúc dựng chỉ mục), cơ chế đa dạng tài liệu tổng quát, và các phép đo ngoại tuyến làm cổng.
