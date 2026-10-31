# Kế hoạch phát triển tiếp RAG v2 (2026-10-29) — chỉ làm v2, không đụng v1

> **Cập nhật 2026-10-30:** P1 đã đổi hướng — luật hỏi lại/từ chối viết tay được thay bằng quyết định của mô hình trong lời gọi sinh (REPORT-v2 §13); P3.2–P3.3 (song song hóa, thử lại) và P4.1 (chấm dẫn nguồn) đã làm; P5, P7 đã đo (§14). Còn lại: P2 (câu nhiều ý đủ ý), A3 câu mơ hồ, nút an toàn dùng chung, phép thử tài liệu mới, holdout4. Cờ vẫn là v1.


Mục tiêu: v2 đạt A1–A9 trên một bộ giữ kín chưa từng bị nhìn, rồi mới chuyển cờ (B7). Cờ mặc định giữ v1 cho tới lúc đó; v1 chỉ là đường lui, không bảo trì thêm.
Số xuất phát (holdout2, v2 ×3): A1 13,3% · A3 81,7% · A4 73/71/74% · A5 41% (đo thấp giả) · A6 90,6% · A7 4,2% · A8 trung vị 10,2 s.

## Kỷ luật đo (để số cuối còn sạch)
- Chỉnh mã chỉ theo **bộ phát triển** (533 ca) và mẫu dev 116 ca. holdout2 đã bị nhìn → coi là "đã dùng", chỉ để so sánh trước/sau.
- Trong lúc sửa, Codex viết **holdout3** (160–200 ca, không dùng đoạn nào của bộ cũ và holdout2, cùng quy tắc `briefs/T11-holdout2.md`; mỗi ca không đáp án một group_id riêng). Không ai mở nó khi sửa. Đo cuối ×3 trên holdout3.
- Mỗi cụm sửa đi qua cổng rẻ trước rồi mới tốn lời gọi: (1) test đơn vị + `tests/rag_v2`; (2) đo ngoại tuyến (probe/offline gate, 0 lời gọi); (3) mẫu dev 116 ca ×1 (~136 lời gọi); (4) chỉ khi cả ba đạt mới đi tiếp. Luôn chạy B0 (3 lời gọi) trước khi đo; nhà cung cấp chậm/lỗi thì dừng, làm việc ngoại tuyến.

## P1 — Từ chối và hỏi lại đúng (A3 81,7% → ≥98%) · 0 lời gọi mô hình
1. **Câu mơ hồ ngắn** (`understanding/analyze.py`): hỏi lại khi câu chỉ có chủ đề chung (đăng ký bổ sung, mức điểm, "kịp không") mà thiếu mọi neo (khóa, năm học, ngành, tên văn bản, mã). Cổng: trên các ca có đáp án của dev + holdout cũ, hỏi lại nhầm ≤1%; bắt được ≥70% ca mơ hồ của dev.
2. **Cổng thực thể lạ** (`understanding/entities.py`): thêm từ viết tắt toàn hoa ≥5 chữ cái không có trong kho, không nằm trong danh sách viết tắt sinh viên (rút từ `normalize._TOKENS` và các viết tắt xuất hiện trong kho); kiểm không phân biệt hoa/thường cho từ ASCII dài lạ. Cổng: 0 ca có đáp án (dev+holdout cũ) bị gắn nhầm.
3. **Đại từ "đó/này"** khi đã nhận ra chủ đề: chỉ hỏi lại khi "đó" đứng sau danh từ chủ đề ở cuối câu và không có lịch sử (tránh trùng "do" = vì).
Xong P1: chạy cổng B2 (79 ca, ~80 lời gọi): A3 ≥95%, không ca có đáp án nào bị từ chối thêm.

## P2 — Trả lời thiếu/sai (A1 13,3% → ≤2%) và A4 · mẫu dev ×1 mỗi vòng
1. **Chia câu hỏi thành các ý** (xác định, không mô hình): tách theo dấu phẩy/"và"/"còn"/nhiều dấu hỏi; yêu cầu sinh trả đúng một nhóm phát biểu cho mỗi ý; kiểm độ phủ bằng mã (mỗi ý phải có ≥1 phát biểu đã qua kiểm chứng); thiếu ý → `partial` có ghi chú thay vì `answer`.
2. **Phủ định theo câu/mệnh đề** (`verification/deterministic.py`): so phủ định trong câu hỗ trợ phát biểu, không trên cả nguồn ngắn (lỗi trung số 6) — giảm từ chối nhầm.
3. **Bảng chương trình đào tạo**: lập chỉ mục theo "hàng + tiêu đề cột/học kỳ" và gom các hàng cùng mã vào một ngữ cảnh; đo bằng `rag_v2_context_probe.py`, giữ nếu tăng ≥+3 điểm trên dev (neo mã đã cho +5 điểm).
4. **Chấm ngữ nghĩa độc lập cho A1** (Codex hoặc mô hình khác với bộ sinh) cho ca "thiếu ý/sai" để thay proxy khớp dữ kiện.
Cổng: mẫu dev đủ ý ≥80/116 (nay 72), thiếu ý ≤10 (nay 12), ca không đáp án bị trả lời nhầm 0/20.

## P3 — Ổn định và độ trễ (A7 4,2% → <1%; A8 10 s → ≤6 s)
1. Đo riêng độ trễ nhà cung cấp (1 lời gọi tối thiểu × vài lần) để tách lỗi do nhà cung cấp khỏi lỗi mã; ghi vào báo cáo.
2. **Song song hóa phân loại an toàn + định tuyến** theo `DESIGN-parallel-classify.md`: viết test an toàn trước (4 ca nêu trong thiết kế), rồi bật sau cờ riêng. Cổng: bộ safety 610 ca không đổi nhãn nào; rò canary 0. Dự kiến −2 s.
3. Ngân sách thời gian bước sinh: thử lại một lần khi lỗi quá hạn còn dư ngân sách; bỏ lời gọi ngữ nghĩa khi nguồn ngắn và mọi kiểm xác định đạt (nếu đo cho thấy an toàn). Cổng: lỗi ≤1% ở độ đồng thời 1–2.
4. Nếu A8 ≤6 s vẫn không đạt chỉ vì nhà cung cấp, ghi rõ "bị chặn bởi giới hạn nhà cung cấp" kèm số đo (SPEC cho phép).

## P4 — Dẫn đúng mục (A5) và nhất quán (A6) · gần 0 chi phí
1. Bộ chấm: coi trích dẫn đúng khi trích dẫn chứa đoạn có nội dung gold (khớp theo `quote`) chứ không chỉ cùng chunk_id; áp dụng cho cả hai engine trong mọi bản so sánh.
2. A6: kiểm hai lần chạy cùng ca khác kết quả để tìm nguồn ngẫu nhiên (thứ tự RRF, hòa điểm, nhiệt độ); làm xác định hơn.

## P5 — An toàn (A9) · ~610–900 lời gọi, chỉ khi B0 xanh liên tục
Chạy `rag_v2_suite.py run` đủ 610 ca (lần đầu không `--resume`). Cổng: rò canary 0, tool_guard 20/20, injection ≥ định mức, false-positive ca lành mạnh ≤8%, nhóm routing/nhiều lượt theo định mức. Chạy lại sau P3.2.

## P6 — Dọn kỹ thuật trước khi vận hành
Ký hoặc đối chiếu thêm `facts.jsonl` với nguồn (lỗi trung số 5); tắt `CAMPUS247_RAG_V2_DEBUG_DIR`; cài numpy chính thức vào venv fixture rồi bỏ `data/rag_v2_vendor`; khởi động nóng cache ủy quyền khi bật; cập nhật `RUNBOOK-v2.md`.

## P7 — Đo cuối và quyết định cờ (B7)
holdout3 ×3 cho v2 (~480–600 lời gọi), bộ safety sạch, so với số holdout2 của v1 (đã đo; không chạy lại v1 trừ khi bộ chấm đổi). Chỉ chuyển `CAMPUS247_RAG_ENGINE` sang v2 khi A1–A9 đạt. Nếu không: ghi tiêu chí chặn và số đo; giữ v1.

## Ngân sách lời gọi DeepSeek (ước tính)
P1 ~80 · P2 ~136 × 3 vòng ≈ 400 · P3 ~300 · P5 ~700 · P7 ~550 ⇒ **≈ 2.000**. Việc ngoại tuyến (phần lớn P1, P4, P6, tạo holdout3) không tốn.

## Thứ tự làm
P1 (+ Codex viết holdout3 song song) → P4.1 → P2 → P3 → P5 → P6 → P7. Sau mỗi cụm cập nhật `REPORT-v2.md`.
