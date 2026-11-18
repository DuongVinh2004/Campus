# RAG chạy được với tài liệu bất kỳ: tiến độ và cách tiếp tục (cập nhật 2026-11-19 đêm)

Mục tiêu của chủ hệ thống: RAG phải hoạt động với bất kỳ tài liệu nào được thêm vào. Tài liệu này là điểm lưu để một phiên mới (hoặc phiên sau lần đặt lại hạn mức 02:30) tiếp tục mà không phải đọc lại cuộc trò chuyện.

## Đã có
- Bộ đo trên tài liệu chưa từng thấy (R1): `evals/runners/rag_unseen_doc_eval.py`, 5 tài liệu tổng hợp + 47 câu hỏi có đáp án kiểm bằng code trong `evals/datasets/unseen-docs/`. Chạy:
  `PYTHONPATH="data/rag_v2_vendor;services/api/src;services/worker/src;scripts;." infra/local/rag-fixture/.venv/Scripts/python.exe -B -X utf8 evals/runners/rag_unseen_doc_eval.py --out evals/results/unseen-docs/<tên>.json` (cần model nhúng 18081 và gateway sidecar 8025 đang chạy; `--only id,id --verbose` để xem câu sinh ra; `--no-llm-check` chỉ kiểm đáp án với tài liệu, không tốn hạn mức nhà cung cấp). Mỗi lượt chạy đủ 47 câu tốn khoảng 100–150 lượt gọi nhà cung cấp: đừng chạy lặp khi chưa sửa gì.
- Số đo gốc (mã trước R2–R4, 2026-11-18): 42/47 tốt (89%); lỗi nằm ở nhóm `dimension_absent` (câu nêu ngành mà bảng không chia theo ngành), 1 câu `major_present`, 1 câu bị coi nhầm là ngoài phạm vi vì từ khóa "nấu ăn". Kết quả: `evals/results/unseen-docs/baseline-20261118.json`.
- R2: `rag_v2/vocabulary.py`: tên ngành đọc từ chính tài liệu (cụm sau "ngành", cột "Ngành" của bảng), chữ viết tắt sinh tự động; không còn phụ thuộc danh sách viết tay để nhận diện tên trong câu hỏi (`Understanding.scope_terms`). `RagV2Service(facts, vocabulary)`, nối vào `bootstrap/rag_v2.py`. Đã bỏ từ khóa "nấu ăn" khỏi danh sách ngoài phạm vi.
- R3: `rag_v2/scope_terms.py` + `service.py`: kiểm từng phát biểu có nguồn mang đúng tên phạm vi trong câu hỏi hay không; nếu không thì bộ chấm ngữ nghĩa nhận câu hỏi đã cắt tên đó (`_verify_scoped`), và phần mở đầu câu trả lời nói rõ "các nguồn không nêu riêng cho …". Thêm truy xuất lần hai không có tên, gộp 7 + 5 ứng viên. Generator nhận `scope_names` và có đoạn hướng dẫn trong `generation/prompt.py`.
- Test: `tests/rag_v2` 748 đạt (gồm `test_scope_names_20261118.py`).

## Số đo hiện tại (cuối 2026-11-19, sau R2 + R3 + R4)
- Bộ `unseen-docs` (đã dùng để chỉnh, nay là bộ hồi quy): **47/47** (gốc 42/47), `evals/results/unseen-docs/after-final.json`.
- Bộ giữ lại `unseen-docs-heldout` (3 tài liệu và 18 câu viết SAU khi chỉnh xong, chạy một lần không chỉnh): **17/18 (94%)**, `heldout-first-run.json`. Câu duy nhất bị chấm sai (lh-06, hỏi khóa K71 trong khi dòng là K70) trả lời "chưa đủ căn cứ" kèm thông tin chung; chữ "Thứ Ba" bị chấm sai do nằm trong gợi ý liên quan, không phải câu trả lời. Đây là số đo trung thực về khả năng tổng quát; mọi lần chỉnh sau nên giữ bộ này không đụng tới.
- `tests/rag_v2`: 749 đạt.
- Bộ tự nhiên cũ, 60 câu đầu của `natural-cases-20261114`, chạy trực tiếp vào API: helpful 30 (50%) so với 33 (55%) của `final.jsonl` lưu lại; dead_end 6/6; p50 4,3 s so với 8,4 s. Chênh lệch nằm ở họ Q1-0053 ("tốt nghiệp giỏi … bị hạ xuống một mức khi bị kỷ luật") bị chặn bởi bộ chặn đầu ra của `agent/nodes/rag_v2.py` (`GUARD_BLOCKED_MESSAGE`, kèm `rag_v2/discipline.py`), không phải do thay đổi này: các câu đó không có tên phạm vi nên các đường mới không chạy. Cùng gốc với câu mẫu "Điều kiện xếp loại tốt nghiệp giỏi" bị từ chối. Đó là chốt an toàn từ các phiên trước (chưa commit), nên chưa nới; cần chủ hệ thống xem lại ngưỡng của nó.

Cơ chế đã làm (đều không gắn với tài liệu hay chủ đề cụ thể):
- `vocabulary.py`: tên ngành đọc từ tài liệu, chữ viết tắt tự sinh.
- `scope_terms.py` + `service._verify_scoped`: bộ chấm ngữ nghĩa nhận câu hỏi đã cắt tên mà nguồn của phát biểu không mang (trừ khi phát biểu tự nêu ngành khác); phần mở đầu nói rõ "nguồn không nêu riêng cho …".
- `table_rows.py`: khi nguồn là bảng không chia theo tên được hỏi, bổ sung mọi dòng áp dụng cho khóa và năm hỏi mà mô hình bỏ sót, và dùng các dòng đó thay cho từ chối; mỗi dòng một câu "cột: ô" lấy nguyên văn và kiểm bằng `check_statement`.
- truy xuất lần hai không có tên (gộp 7 + 5), `scope_names` cho generator.
- `verification/deterministic.py`: tiêu đề tài liệu không còn làm hỏng phép kiểm phủ định (chỉ nới, không bao giờ chặt hơn trước).
- `facts/extract.py`: phạm vi theo từng dòng; nhận cột tiền theo tên cột và đơn vị.

## Việc còn lại, theo thứ tự
1. Chủ hệ thống xem ngưỡng của bộ chặn đầu ra về kỷ luật (họ Q1-0053, câu mẫu tốt nghiệp giỏi): chặn nhầm quy định chung về xếp loại tốt nghiệp.
2. Mở rộng bộ giữ lại khi có thêm loại tài liệu (PDF quét, bảng nhiều tầng tiêu đề, văn bản nhiều điều khoản); mỗi lần chỉ chạy một lần, không chỉnh theo từng câu.
3. Commit các sửa trong tệp `rag_v2` cũ (xem mục D của `NEXT_SESSION_PROMPT_20261118.md`).

## Quy tắc khi tiếp tục
- Không đổi giới hạn 5 s của nhà cung cấp, model, hay chỉ mục đang chạy. Bộ đo chạy trên chỉ mục tạm trong bộ nhớ.
- Runtime 8015 đang chạy mã mới nhất (khởi động lúc 23:00 ngày 2026-11-19); ClamAV đang tắt vì thiếu RAM.
- Tiết kiệm hạn mức: đọc đúng chỗ, in ít, không chạy bộ đo đầy đủ sau mỗi sửa nhỏ (dùng `--only`).
