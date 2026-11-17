# W10 — giữ nguyên bảo vệ "hạn nộp" của luật an toàn; hoàn tất lệnh khởi động một bước

Đọc `W0-common.md` (quy tắc chung; đây là việc Python). Mã phiên W10.

Sở hữu: `services/api/src/campus247/agent/nodes/safety_rules.py`, `tests/unit/agent/test_audit_routing_20261101.py`, `scripts/knowledge_platform_runtime.py`, `scripts/campus.py`, `tests/operations/test_runtime_audit_fixes.py`. **Không** sửa `tests/knowledge_platform/test_public_financial_deadlines.py`; đó là test an toàn có chủ đích và là tiêu chí nghiệm thu.

## 1. Hồi quy an toàn do W9
W9 thêm `is_public_policy_question()` trong `safety_rules.py` và dùng nó để bỏ qua các luật `financial_impact` / `disciplinary_or_legal` / `academic_rights_impact`. Hàm này rộng quá: chỉ cần "hồ sơ" + "miễn/học phí" là đủ để bỏ qua, nên câu hỏi về **hạn nộp/thời hạn** thoát khỏi logic bảo vệ sẵn có (`_public_waiver_deadline_reference`). Logic cũ chỉ cho qua hạn nộp công khai có giới hạn (có năm học hoặc số thông báo, không cá nhân, không gia hạn, không tiền/nợ). Kết quả: 5 ca trong `tests/knowledge_platform/test_public_financial_deadlines.py` đỏ (`'normal' == 'high'`), ví dụ "Em muốn miễn giảm học phí, hồ sơ của em nộp khi nào?", "Hạn nộp hồ sơ miễn giảm học phí hiện nay là ngày nào?".

Yêu cầu:
- `is_public_policy_question` không được miễn trừ câu có tín hiệu thời hạn/hạn chót: hạn nộp, thời hạn, hết hạn, gia hạn, khi nào, ngày nào, bao giờ, trước ngày… (dạng đã chuẩn hóa không dấu). Các câu đó phải đi đúng logic cũ, cho cùng kết quả như trước W9.
- Giữ các ca W9 đã sửa:
  - AU-A18 "Hồ sơ minh chứng miễn giảm học phí em phải nộp lại mỗi học kỳ hay chỉ nộp một lần?" → `normal`;
  - AU-P06 "Em bị bắt quả tang dùng điện thoại trong phòng thi thì chắc chắn bị đình chỉ học đúng không?" → không bị đưa sang chuyển cán bộ chỉ vì từ khóa;
  - các ca biến hình W9 khác trong `test_audit_routing_20261101.py`.
- Nếu một ca W9 mâu thuẫn với test an toàn có sẵn thì test có sẵn thắng: sửa kỳ vọng ca W9 và ghi lý do.
- Rà toàn bộ hàm mới để không có lối khác làm hạ mức các câu đang `high`/`critical` trong các test an toàn sẵn có. Chạy và báo kết quả:
  - `tests/knowledge_platform` (toàn bộ);
  - `tests/test_safety_rules.py`, `tests/test_intent_routing.py`, `tests/unit/agent`, `tests/rag_v2`;
  - mọi test có tên chứa `safety` trong `tests/`.
  So với nhánh sao lưu `backup/worktree-20261101-audit` (trạng thái trước mọi sửa hôm nay; dùng `git stash`/`git worktree` là KHÔNG được — chỉ đọc bằng `git show backup/worktree-20261101-audit:<đường dẫn>` nếu cần so). Không ca nào từng đạt được phép chuyển thành đỏ.

## 2. Lệnh khởi động một bước (L-23 phần còn lại)
- `knowledge_platform_runtime.py start` khi `--engine v2` phải tự thêm `data/rag_v2_vendor` vào `PYTHONPATH` của tiến trình API (venv runtime không có numpy; hiện người vận hành phải tự đặt). Giữ `PYTHONPATH` sẵn có nếu có.
- Hằng `FRONTEND` mặc định đang là snapshot cũ `frontend-knowledge-automation-20261027-16`.
  - Đổi để mặc định dùng snapshot `frontend-knowledge-*` có `.next/BUILD_ID`, mới nhất theo thời điểm build ghi trong tệp `<tên>-build.json` cạnh thư mục snapshot ở `infra/local/knowledge-platform-20261023/` (hoặc mtime của BUILD_ID nếu không có).
  - `--frontend-name` vẫn thắng.
  - Không tự build.
- `scripts/campus.py start` (`pnpm start`) gọi script runtime: phải chạy được RAG v2 đầy đủ mà không cần biến môi trường ngoài. Không đổi cổng, không tắt tiến trình đang chạy.
- Test trong `tests/operations/test_runtime_audit_fixes.py`: PYTHONPATH có vendor khi v2 và không thêm khi v1; chọn snapshot mới nhất; `--frontend-name` thắng; `campus.py start` truyền đúng. Chạy `tests/operations`.
