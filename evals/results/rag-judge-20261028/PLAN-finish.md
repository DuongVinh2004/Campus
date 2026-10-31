# Kế hoạch hoàn tất RAG v2 (viết 2026-10-29, dùng cho phiên mới)

Đọc trước, theo thứ tự: `REPORT-v2.md` (số đo, §7–§9 mới nhất), `SPEC-v2.md` (tiêu chí A1–A9), `DESIGN-v2.md`, `RUNBOOK-v2.md`, `resume/README.md`. Quy tắc làm việc: `AGENTS.md` (không commit/push/xóa/reset; không in bí mật; không chi tiêu dịch vụ trả phí ngoài DeepSeek đã dùng). Codex: `codex exec -m gpt-6.1-sol -c model_reasoning_effort="high" -s workspace-write` (đọc: `-s read-only`), bản giao việc mẫu ở `briefs/`.

## 1. Hiện trạng (không cần đo lại)
- v2 chạy được sau cờ `CAMPUS247_RAG_ENGINE=v2`; mặc định v1; runtime 8015 đang chạy v1. Chưa chuyển cờ vì v2 chưa đạt A1–A9.
- Số đo hợp lệ nhất (bộ giữ kín 227 ca, DeepSeek sinh): v1 một lượt: có trả lời 45%, đủ ý 39%, từ chối đúng ca không đáp án 95%; v2 ×3: A4 chuẩn+không dấu 82% / từ khóa 73% / lóng 85% (đạt), A3 82%, A5 88%, A6 93%, A7 2,1%, A8 trung vị 9,2 s, A1(proxy) 24%.
- Từ lần đo đó đã thêm (CHƯA đo đầu–cuối): cổng thực thể lạ, hỏi lại khi đại từ "đó/này" không ngữ cảnh, 6 sửa từ rà soát Codex (nhánh dữ kiện chỉ khi đơn vị không có điều kiện; ràng buộc tiêu đề/phạm vi với hàng DB; quét tiêu đề injection; log không có nội dung; kiểm phủ định cục bộ cho nguồn ngắn), sửa hồi quy hiệu năng kiểm phạm vi (vòng ủy quyền ~0,9 s, 8756 unit hợp lệ). Test: `tests/rag_v2` 314 đạt; nhóm v1 liên quan 954 đạt + 8 đỏ có sẵn (không đổi).
- Chưa làm: v1 bộ giữ kín lượt 2–3; bộ safety v1; bộ safety v2 đủ 610 ca (mới có mẫu 221 ca, nhiễu vì nhà cung cấp quá hạn; số tin cậy: rò canary 0, tool_guard 20/20, injection 32/34, FP ca lành mạnh 1/13); đo lại sau các sửa mới.
- Trở ngại duy nhất lúc dừng: DeepSeek quá hạn ở bước sinh (mỗi lượt ~17 s rồi lỗi; trước đó từng là HTTP 402). Cần số dư/độ ổn định của nhà cung cấp. Người dùng dặn **chạy tiết kiệm**.

## 2. Phân tích khoảng cách tới A1–A9 (ưu tiên theo đòn bẩy)
1. **Độ đủ ý/độ đúng (A1, A4)** là khoảng cách lớn nhất. Trần ngữ cảnh đo ngoại tuyến: ngữ cảnh chứa đủ dữ kiện ở ~83% ca (`rag_v2_context_probe.py`), v2 trả lời đủ ý ~56%. Nút nghẽn nằm ở sinh/kiểm chứng: câu nhiều ý trả lời thiếu; bảng chương trình đào tạo (khoảng 55% bộ ca) có đáp án rải ở nhiều hàng.
2. **A3 (từ chối đúng)**: v2 nhầm câu "gần miền" (hỏi chứng chỉ/khóa học ngoài, kho chỉ có quy định chung). Đã thêm cổng thực thể lạ; cần đo.
3. **A8 (độ trễ)**: dịch vụ v2 trung vị ~3,3 s nhưng đầu–cuối ~8–9 s vì hai lời gọi phân loại v1 (an toàn, định tuyến) tuần tự ~4 s. A8 ≤6 s chỉ đạt nếu giảm phần này (song song hóa hoặc lược lời gọi) — đụng đường an toàn nên cần test an toàn và phê duyệt kiểu rà soát trước khi đổi.
4. **A7 (lỗi <1%)**: lỗi còn lại chủ yếu quá hạn 12 s khi tải cao/nhà cung cấp chậm; cần tinh chỉnh ngân sách thời gian và đo ở độ đồng thời 1–2.
5. **A5 (dẫn đúng mục 88% so với 95%)**: tập trung vào ca bảng chương trình; xem `case_outcomes` của `score` để biết ca nào dẫn sai.
6. **A6 (nhất quán 93%)**: gần ngưỡng; giảm bằng nhiệt độ 0 (đã dùng) và kiểm xác định chặt hơn.
7. **Tính hợp lệ của bộ giữ kín**: đã bị nhìn ở mức tổng hợp và đã dùng để chọn sửa cổng thực thể. Muốn kết luận cuối sạch, tạo **bộ giữ kín mới 100–150 ca** bằng Codex (không tốn DeepSeek), chia theo nhóm, không ai xem khi sửa.

## 3. Các bước (có cổng; mỗi bước nêu số lời gọi DeepSeek ước tính)
**B0. Kiểm tra nhà cung cấp (≈3 lời gọi).** Khởi động lại v2 bằng `resume/restart_rt.ps1 -Engine v2` (cần PYTHONPATH=data\rag_v2_vendor — script đã đặt; sau đó dọn biến môi trường nếu chạy pytest), gửi 1 lượt khởi động nóng + ~45 s, rồi chạy `rag_v2_eval.py run --split dev --limit 2`. Nếu vẫn `error` ~17 s: DỪNG, chờ; không chạy thêm. (Xem log: `rag_v2_failure ... TimeoutError/402`.)

**B1. Việc không tốn DeepSeek, làm ngay trong lúc chờ (Codex + ngoại tuyến).**
 a. Codex tạo bộ giữ kín mới (`evals/datasets/rag-v2/holdout2/`), cùng định dạng, kiểm bằng `rag_v2_cases.py validate`; đừng trộn vào `cases.jsonl` cũ.
 b. Codex (read-only) rà tiếp: các phần chưa rà (adapters/index_store, http_reranker, bootstrap) và các sửa mới.
 c. Ngoại tuyến cải thiện nhóm bảng chương trình: tách câu hỏi nhiều ý thành các truy vấn con và hợp nhất ngữ cảnh (đo bằng `rag_v2_context_probe.py`; đã thử tách đơn giản không tăng, cần hướng khác như lập chỉ mục theo "hàng bảng + tiêu đề cột"). Chỉ giữ nếu tăng "đủ dữ kiện trong ngữ cảnh" ≥ +3 điểm trên dev.
 d. Thiết kế (chưa bật) song song hóa hai nút phân loại; viết test an toàn trước.

**B2. Tập rẻ xác nhận các sửa (≈80 lời gọi).** `cases-ho-cheap.jsonl` đã có ở `runs/` (39 ca không đáp án + 40 ca có đáp án của giữ kín cũ). Điều kiện đi tiếp: A3 trên 39 ca ≥ 95%; không ca có đáp án nào mới bị từ chối do cổng mới (so với `v2-holdout-f2.json`).

**B3. Hồi quy dev (≈136 lời gọi).** `runs/cases-dev-sample.jsonl` (49 nhóm): đủ ý ≥ 64/116 (mốc trước), lỗi ≤ 3.

**B4. Bộ giữ kín v2 ×3 trên bộ MỚI (≈ 3 × số ca).** `--repeat 3 --concurrency 2`; KHÔNG đọc tệp kết quả khi đang chạy (bộ chạy ghi nguyên tử, đọc đồng thời gây PermissionError — bọc vòng thử lại như `resume/protocol-*.sh`). Chấm bằng `rag_v2_eval.py score`.

**B5. v1 trên cùng bộ mới ×1 (≈ số ca)** để so sánh công bằng (`compare`). v1 ×3 chỉ khi cần nhất quán A6 của v1 (không bắt buộc).

**B6. Bộ safety (A9).** v2 đủ 610 ca (≈610–900 lời gọi vì nhiều lượt); chạy `rag_v2_suite.py run` (lần đầu KHÔNG dùng `--resume`; lần sau mới `--resume`), chấm bằng `score`. Chỉ nên chạy khi B0 xanh liên tục (nhiễu quá hạn làm hỏng điểm như lần trước). v1 chỉ chạy mẫu nếu cần so sánh (nhóm an toàn dùng chung nút v1).

**B7. Quyết định cờ.** Chỉ chuyển sang v2 khi A1–A9 đạt trên bộ giữ kín mới ×3, v2 không kém v1 ở tiêu chí nào, và A9 sạch (rò canary 0, FP ≤ 8%). Nếu không đạt: ghi rõ tiêu chí nào chặn và số đo; giữ v1; cân nhắc dùng v2 chỉ cho nhóm đạt (chưa hỗ trợ — cần thiết kế riêng).

**B8. Chốt.** Cập nhật `REPORT-v2.md` (số đo cuối, giới hạn), `RUNBOOK-v2.md`, đặt runtime về trạng thái đã quyết, xóa các biến môi trường gỡ lỗi (`CAMPUS247_RAG_V2_DEBUG_DIR`), cài numpy chính thức cho venv fixture thay cho bản sao `data/rag_v2_vendor`.

## 4. Ngân sách và an toàn chi phí
- Tổng lời gọi ước tính đầy đủ: B2 80 + B3 136 + B4 ~700 (bộ mới ~230 ca ×3) + B5 ~230 + B6 ~700 ≈ 1.850. Chạy theo cổng; nếu cổng B2/B3 không đạt thì sửa ngoại tuyến rồi mới tốn tiếp.
- Không chạy khi B0 đỏ. Không bao giờ chạy hai bộ chạy cùng lúc trên cùng runtime (nhiễu độ trễ và quá hạn).
- Không dùng khóa Gemini trong môi trường: đó là chi tiêu chưa được cấp và làm số đo v1/v2 không còn so sánh được.

## 5. Bẫy đã gặp (đừng lặp lại)
- Heredoc bash/PowerShell làm hỏng chuỗi có `\b`, `\d`, `\n`: ghi mã bằng công cụ Write/Edit hoặc tệp script riêng, rồi kiểm `chr(8)` (backspace) không còn trong mã.
- `import logging` cục bộ trong khối `except` gây `UnboundLocalError` ở nhánh khác của cùng hàm.
- Đọc tệp JSON kết quả khi bộ chạy đang ghi → `PermissionError`; bộ safety `--resume` trên tệp chưa tồn tại → `ValueError`.
- Cổng nhà cung cấp chặn yêu cầu >28.000 byte JSON (ngữ cảnh sinh ≤19.000 byte), `max_output_tokens ≤ 1000`, `deadline ≤ 5000 ms`.
- Cache ủy quyền nguồn lạnh ~25–35 s: luôn khởi động nóng. Chạy pytest phải bỏ `PYTHONPATH=data\rag_v2_vendor` (numpy 3.12 không tương thích venv 3.13).
