# A4 — Tích hợp, an toàn, vận hành và ổn định runtime
Đọc `A0-common.md` cùng thư mục trước và tuân thủ nguyên văn. Mã phiên: A4.

Phạm vi đọc chính: `agent/nodes/rag_v2.py`, `bootstrap/rag_v2.py`, `bootstrap/settings.py` (cờ v2), `agent/graph.py` (điểm rẽ v2), `agent/nodes/async_io.py` (song song hóa phân loại), `application/conversation/stream_result.py`, `application/knowledge/{platform,platform_models,release_members,original_excerpt}.py` và source_snapshot (`scope_allows`, cache ủy quyền), `infrastructure/knowledge/runtime.py`, `application/retrieval/profile.py`, phần `presentation/**`/`history_presentation` chạm kết quả v2, `tests/architecture/**`, test tích hợp trong `tests/rag_v2/**`, `evals/results/rag-judge-20261028/resume/restart_rt.ps1`.

Câu hỏi bắt buộc trả lời (có bằng chứng):
1. Ủy quyền nguồn mỗi lượt và cache (stale-while-revalidate theo release/generation/policy/phạm vi): khi một tài liệu bị thu hồi hoặc hết hiệu lực, hoặc release mới phát hành, bao lâu thì v2 ngừng/bắt đầu dùng nó? Có cửa sổ nào v2 trích dẫn nguồn đã thu hồi không? Unit trong chỉ mục mà DB không còn — xử lý thế nào (REPORT nói bị loại ở bước ủy quyền; kiểm lại)?
2. Mọi đường lỗi từ lõi v2 tới SSE: ngoại lệ, quá hạn, nhà cung cấp 402/timeout, chỉ mục thiếu/hỏng, numpy thiếu, cache lạnh — người dùng thấy gì, `outcome_kind` là gì, có lẫn "lỗi hệ thống" với "không có nguồn" không (ảnh hưởng A7 và sự trung thực).
3. An toàn: dữ liệu không tin cậy từ tài liệu mới (prompt injection trong nội dung/tiêu đề/đường dẫn/bảng) — quét ở đâu, có bỏ sót trường nào khi ghép ngữ cảnh/viết lại/kiểm ngữ nghĩa không; v2 có bỏ qua bất kỳ cổng nào của v1 (evidence_gate, output_guard, kiểm trích dẫn tồn tại) không; hợp đồng trích dẫn với web có giữ không; log/trace/debug có ghi PII hoặc nội dung không (kiểm `CAMPUS247_RAG_V2_DEBUG_DIR`, log `rag_v2_*`).
4. Đồng thời và tài nguyên: chỉ mục trong bộ nhớ dùng chung giữa request có an toàn luồng không; cache ủy quyền dưới tải đồng thời (thundering herd khi lạnh); bộ nhớ; số lời gọi mô hình mỗi lượt (an toàn + định tuyến + viết lại + sinh + sửa + ngữ nghĩa) và tác động A8.
5. Vận hành: phụ thuộc numpy qua `data/rag_v2_vendor` + `PYTHONPATH`; khởi động lạnh 25–35 s; có health check riêng cho v2 không; hành vi khi `CAMPUS247_RAG_ENGINE=v2` mà chỉ mục lệch release; khả năng lui về v1; cấu hình nằm ở đâu.
6. Quản lý mã: toàn bộ `rag_v2/`, `tests/rag_v2/`, runner và script dựng chỉ mục hiện CHƯA được git theo dõi (`git status` báo `??`). Đánh giá rủi ro và thứ tự đưa vào kiểm soát phiên bản (chỉ đề xuất, không thực hiện).
7. Ranh giới kiến trúc: module miền v2 có import `agent/**`, `infrastructure/**`, `presentation/**` không (DESIGN-v2 cấm); có test kiến trúc phủ v2 chưa.

Kết thúc bằng mục "Điều kiện vận hành tối thiểu để bật v2 mặc định" (≤ 25 dòng, dạng checklist kiểm được).
