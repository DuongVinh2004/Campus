# RAG chạy được với tài liệu bất kỳ: tiến độ và cách tiếp tục (cập nhật 2026-11-19 đêm)

Mục tiêu của chủ hệ thống: RAG phải hoạt động với bất kỳ tài liệu nào được thêm vào. Tài liệu này là điểm lưu để một phiên mới (hoặc phiên sau lần đặt lại hạn mức 02:30) tiếp tục mà không phải đọc lại cuộc trò chuyện.

## Đã có
- Bộ đo trên tài liệu chưa từng thấy (R1): `evals/runners/rag_unseen_doc_eval.py`, 5 tài liệu tổng hợp + 47 câu hỏi có đáp án kiểm bằng code trong `evals/datasets/unseen-docs/`. Chạy:
  `PYTHONPATH="data/rag_v2_vendor;services/api/src;services/worker/src;scripts;." infra/local/rag-fixture/.venv/Scripts/python.exe -B -X utf8 evals/runners/rag_unseen_doc_eval.py --out evals/results/unseen-docs/<tên>.json` (cần model nhúng 18081 và gateway sidecar 8025 đang chạy; `--only id,id --verbose` để xem câu sinh ra; `--no-llm-check` chỉ kiểm đáp án với tài liệu, không tốn hạn mức nhà cung cấp). Mỗi lượt chạy đủ 47 câu tốn khoảng 100–150 lượt gọi nhà cung cấp: đừng chạy lặp khi chưa sửa gì.
- Số đo gốc (mã trước R2–R4, 2026-11-18): 42/47 tốt (89%); lỗi nằm ở nhóm `dimension_absent` (câu nêu ngành mà bảng không chia theo ngành), 1 câu `major_present`, 1 câu bị coi nhầm là ngoài phạm vi vì từ khóa "nấu ăn". Kết quả: `evals/results/unseen-docs/baseline-20261118.json`.
- R2: `rag_v2/vocabulary.py`: tên ngành đọc từ chính tài liệu (cụm sau "ngành", cột "Ngành" của bảng), chữ viết tắt sinh tự động; không còn phụ thuộc danh sách viết tay để nhận diện tên trong câu hỏi (`Understanding.scope_terms`). `RagV2Service(facts, vocabulary)`, nối vào `bootstrap/rag_v2.py`. Đã bỏ từ khóa "nấu ăn" khỏi danh sách ngoài phạm vi.
- R3: `rag_v2/scope_terms.py` + `service.py`: kiểm từng phát biểu có nguồn mang đúng tên phạm vi trong câu hỏi hay không; nếu không thì bộ chấm ngữ nghĩa nhận câu hỏi đã cắt tên đó (`_verify_scoped`), và phần mở đầu câu trả lời nói rõ "các nguồn không nêu riêng cho …". Thêm truy xuất lần hai không có tên, gộp 7 + 5 ứng viên. Generator nhận `scope_names` và có đoạn hướng dẫn trong `generation/prompt.py`.
- Test: `tests/rag_v2` 748 đạt (gồm `test_scope_names_20261118.py`).

## Số đo hiện tại (sau R2 + R3 + R4)
**45/47 tốt (96%)**, không câu `wrong` hay `dead_end` (gốc 42/47): `evals/results/unseen-docs/after-r2r4.json`. `tests/rag_v2` 749 đạt. Còn hai câu `incomplete` (hp-02, hp-03): trả lời thật nhưng thiếu các dòng chương trình khác, vì tên ngành được hỏi (Trí tuệ nhân tạo, Quản lý đô thị) CÓ xuất hiện ở bảng học phí thực hành K70 nên đường "trả từng dòng bảng" (`rag_v2/table_rows.py`) nhường cho đường sinh bằng mô hình, và mô hình liệt kê không đủ.

Cơ chế đã làm (đều không gắn với tài liệu hay chủ đề cụ thể):
- `vocabulary.py`: tên ngành đọc từ tài liệu, chữ viết tắt tự sinh.
- `scope_terms.py` + `service._verify_scoped`: bộ chấm ngữ nghĩa nhận câu hỏi đã cắt tên mà nguồn của phát biểu không mang (trừ khi phát biểu tự nêu ngành khác); phần mở đầu nói rõ "nguồn không nêu riêng cho …".
- `table_rows.py`: bảng không chia theo tên được hỏi thì trả mọi dòng áp dụng cho khóa và năm hỏi, mỗi dòng một câu "cột: ô" lấy nguyên văn, kiểm bằng `check_statement`, không gọi mô hình.
- truy xuất lần hai không có tên (gộp 7 + 5), `scope_names` cho generator, bỏ từ khóa "nấu ăn" khỏi danh sách ngoài phạm vi.
- `verification/deterministic.py`: tiêu đề tài liệu không còn tính là từ phủ định của mọi câu lấy từ tài liệu (tiêu đề như "... không phải văn bản chính thức" làm hỏng mọi phát biểu, một lỗi vận hành thật với tài liệu mới).
- `facts/extract.py`: phạm vi theo từng dòng (dòng K71 không còn gán cho K70), nhận cột tiền theo tên cột và đơn vị (đồng, vnđ, /tháng, /học kỳ).

## Việc còn lại, theo thứ tự
1. (tùy chọn) hp-02/hp-03: chọn bảng theo độ gần giữa câu hỏi và tiêu đề bảng ("thực hành" so với "học phí"), hoặc chỉ coi bảng là "mang tên" khi dòng của bảng áp dụng đúng khóa hỏi; hiện bảng thực hành K70 thiếu khóa trong chính dòng nên không loại được theo khóa.
2. Nạp mã mới vào runtime 8015 (khởi động lại, xem memory `runtime-8015-startup-gotchas`; RAM tight, ClamAV đang tắt), rồi hỏi lại thử câu học phí K67/CNTT và chạy `rag_natural_eval.py` trên bộ cũ để chắc không giảm so với `evals/results/rag-natural-20261114/` (tốn hạn mức nhà cung cấp, chạy một lần).
3. Commit: các tệp `rag_v2` chung với thay đổi chưa commit từ trước, nên chờ chủ hệ thống quyết (xem `NEXT_SESSION_PROMPT_20261118.md` mục D).

## Quy tắc khi tiếp tục
- Không đổi giới hạn 5 s của nhà cung cấp, model, hay chỉ mục đang chạy. Bộ đo chạy trên chỉ mục tạm trong bộ nhớ.
- Runtime 8015 đang chạy bản mã trước R2–R4 (đã nạp lúc khởi động); khởi động lại để nạp mã mới chỉ khi xong bước 4 (xem memory `runtime-8015-startup-gotchas`; ClamAV đang tắt vì thiếu RAM).
- Tiết kiệm hạn mức: đọc đúng chỗ, in ít, không chạy bộ đo đầy đủ sau mỗi sửa nhỏ (dùng `--only`).
