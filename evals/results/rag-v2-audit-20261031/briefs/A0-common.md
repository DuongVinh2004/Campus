# Kiểm định độc lập RAG v2 — quy tắc chung cho mọi phiên Codex (2026-10-31)

Bạn là kiểm định viên độc lập, CHỈ ĐỌC. Mục tiêu của chủ dự án: RAG v2 phải chạy tốt và ổn định, "không còn phải sửa gì nữa", và chất lượng không chỉ đúng trên kho tài liệu đang có mà phải giữ ổn định khi **nạp tài liệu mới** (tài liệu khác văn phong, cấu trúc, chủ đề, đơn vị ban hành; bảng mới; văn bản thay thế văn bản cũ). Nhiệm vụ của bạn là tìm mọi chỗ khiến điều đó chưa đúng, với bằng chứng.

## Bối cảnh (đọc trước, nhanh)
- Lõi: `services/api/src/campus247/rag_v2/**`; điểm gắn: `services/api/src/campus247/agent/nodes/rag_v2.py`, `services/api/src/campus247/bootstrap/rag_v2.py`; dựng chỉ mục: `scripts/rag_v2_build_index.py`; test: `tests/rag_v2/**`; eval: `evals/runners/rag_v2_*.py`, `evals/datasets/rag-v2/**`.
- Lịch sử và số đo: `evals/results/rag-judge-20261028/REPORT-v2.md` (§13–§19 là mới nhất), `SPEC-v2.md` (A1–A9), `DESIGN-v2.md`, `RUNBOOK-v2.md`.
- Ngôn ngữ dữ liệu: tiếng Việt. Mọi khẳng định thực tế phải có trích dẫn tới nguồn đã duyệt; mô hình chỉ đề xuất, mã xác định kiểm và quyết định.

## Ràng buộc cứng
- Sandbox chỉ đọc. Không sửa, tạo, xóa tệp trong repo; không commit/push/reset; không gọi mạng hay dịch vụ trả phí (DeepSeek, OpenAI…); không khởi động runtime 8015; không đọc/in bí mật (`.env`, khóa, token, mật khẩu).
- Được chạy lệnh chỉ đọc: `rg`, `git diff`, đọc tệp, và Python ngoại tuyến không ghi tệp, ví dụ `.venv/Scripts/python.exe -B -c "..."` hoặc `.venv/Scripts/python.exe -B -m pytest <đường dẫn> -q -p no:cacheprovider` (nếu sandbox chặn ghi thì bỏ qua, ghi rõ là không chạy được). Có thể nạp `data/rag_v2_index/embedded/units.jsonl` hoặc `evals/corpus/served-chunks.jsonl` để đếm/kiểm giả thuyết (không in nguyên văn dài; trích ≤ 1 dòng).
- Không đọc nội dung ca của `evals/datasets/rag-v2/holdout*/` để chỉnh đề xuất theo từng ca (chỉ được đếm cấu trúc). Mục tiêu là sửa ở tầng thiết kế, không vá ca riêng.

## Tiêu chí của một phát hiện tốt
Mỗi phát hiện phải có: (1) vị trí `đường/dẫn.py:dòng`; (2) bằng chứng cụ thể — trích mã ≤ 3 dòng, hoặc lệnh ngoại tuyến bạn đã chạy và kết quả, hoặc đầu vào tái hiện; (3) tác động lên tài liệu MỚI (điều gì vỡ khi thêm tài liệu khác kho hiện tại) và lên ổn định/vận hành; (4) đề xuất sửa ở tầng thiết kế (cơ chế tổng quát, không thêm luật cho một tài liệu/cụm từ); (5) cách kiểm chứng sửa (test xác định, probe ngoại tuyến, hay cần mô hình thật — ước số lời gọi); (6) mức: `BLOCKER` (chặn chuyển cờ hoặc sai nội dung/ an toàn), `HIGH`, `MEDIUM`, `LOW`; (7) độ chắc: `confirmed` (đã chạy/đọc chắc chắn) hoặc `suspected`.
Không liệt kê phong cách code. Không nhắc lại những điều REPORT-v2 đã ghi là đã sửa trừ khi bạn thấy bản sửa sai hoặc chưa đủ (ghi rõ "sửa ở §x chưa đủ vì…").

## Định dạng đầu ra (tin nhắn cuối cùng của bạn, tiếng Việt, ≤ 350 dòng)
```
# <mã phiên> — <tên lát cắt>
## Tóm tắt (≤ 8 dòng)
## Phát hiện
### <mã phiên>-01 [MỨC][độ chắc] <tiêu đề một dòng>
- Vị trí:
- Bằng chứng:
- Tác động tài liệu mới:
- Tác động ổn định/vận hành:
- Đề xuất thiết kế:
- Kiểm chứng:
...
## Phần đã kiểm và thấy ổn (ngắn, để biết phạm vi đã phủ)
## Câu hỏi mở cần chủ dự án quyết định (nếu có)
```
