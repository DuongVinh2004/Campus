W10 đã hoàn tất phần mã và kiểm thử được giao.

1. Đã sửa và nguyên nhân gốc

- W9 miễn trừ quá rộng khi thấy từ khóa chính sách/hồ sơ, làm câu hỏi hạn nộp thoát khỏi bảo vệ cũ. Đã loại tín hiệu hạn chót, thời hạn, gia hạn, trễ/quá hạn và các biến thể không dấu khỏi `is_public_policy_question`; giữ nguyên `_public_waiver_deadline_reference` để quyết định ngoại lệ có giới hạn.
- AU-A18, AU-P06 và toàn bộ ca W9 vẫn đạt; không phải đổi kỳ vọng W9. Test nghiệm thu `test_public_financial_deadlines.py` không sửa và khớp nhánh sao lưu.
- API v2 tự thêm đường dẫn tuyệt đối `data/rag_v2_vendor` vào `PYTHONPATH`, giữ giá trị có sẵn; v1 và các tiến trình khác không bị thêm vendor.
- Mặc định chọn snapshot đã có `.next/BUILD_ID` mới nhất, ưu tiên thời gian `built_at` trong biên nhận build, thiếu thì dùng mtime của `BUILD_ID`; bỏ build thất bại. `--frontend-name` vẫn thắng, không tự build.
- `campus.py start/status` truyền rõ `--defer-worker --engine v2 --rag-v2-index data/rag_v2_index/embedded2` cho script runtime.

2. Tệp đổi và test

- `services/api/src/campus247/agent/nodes/safety_rules.py`
- `scripts/knowledge_platform_runtime.py`
- `scripts/campus.py`
- `tests/unit/agent/test_audit_routing_20261101.py`
- `tests/operations/test_runtime_audit_fixes.py`
- Báo cáo này: [W10-report.md](/C:/Users/Duong%20Vinh/Vinh/evals/results/audit-opus-20261101/impl/W10-report.md).

Thêm/mở rộng 62 ca: 52 ca an toàn, 10 ca runtime. Tên test mới:
- `test_deadline_signals_never_use_the_broad_public_policy_exception`
- `test_public_rule_wording_cannot_hide_an_incident_or_assertion`
- `test_public_policy_cannot_hide_other_priority_signals`
- `test_frontend_defaults_to_latest_recorded_build_not_name_or_mtime`
- `test_frontend_without_build_time_uses_build_id_mtime`
- `test_explicit_frontend_name_wins_over_latest`
- `test_frontend_selection_without_a_build_fails_without_building`
- `test_campus_passes_complete_v2_runtime_options_without_external_environment`
Mở rộng `test_start_passes_explicit_engine_and_index_to_api` cho v1/v2 với `PYTHONPATH` thiếu, rỗng và có sẵn.

3. Lệnh và kết quả

Lệnh cuối từ gốc repo:
`.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider tests/knowledge_platform tests/test_safety_rules.py tests/test_intent_routing.py tests/unit/agent tests/rag_v2 tests/operations tests/integration/retention/test_retention_safety.py tests/unit/ai/test_multi_provider.py::test_multi_provider_safety_fallback_to_offline_fake --basetemp=.pytest-tmp-W10-final-20261101 --tb=short --durations=5`

- Trước sửa, bộ chính: **1.438 đạt / 5 đỏ / 41 bỏ qua**, exit 1; đúng 5 lỗi hạn nộp nêu trong brief.
- Test tái hiện tập trung trên mã cũ: **181 đạt / 34 đỏ**, exit 1. Rà thêm biến thể trễ/quá hạn: **22 đạt / 12 đỏ**, exit 1 trước bản sửa bổ sung.
- Sau sửa, nhóm tập trung: **227 đạt / 0 đỏ**, exit 0.
- Bộ đầy đủ cuối, gồm toàn bộ thư mục yêu cầu và mọi test có tên chứa `safety`: **1.506 đạt / 0 đỏ / 41 bỏ qua**, exit 0; 2 cảnh báo cũ `LEGACY_EMBED_CACHE_IGNORED`.
- `tests/operations` cùng 6 tệp safety/deadline: **200 đạt / 0 đỏ**, exit 0 (86 operations, 114 safety/deadline).
- Đọc duy nhất bằng `git show backup/worktree-20261101-audit:services/api/src/campus247/agent/nodes/safety_rules.py`, nạp logic sao lưu trong bộ nhớ và chạy 6 tệp safety/deadline: **114 đạt / 0 đỏ**, exit 0. Đối chiếu thêm 54 chuỗi high/critical trong các tệp đó: mức, cờ khủng hoảng và lý do đều giữ nguyên. Không có ca cũ đạt chuyển đỏ.
- Từ `apps/web`: `npx.cmd --no-install vitest run src/features/chat` → **136 đạt / 0 đỏ**, exit 0; `npx.cmd --no-install tsc --noEmit --incremental false` → sạch, exit 0. Dùng `.cmd` vì PowerShell chặn `npx.ps1`; tắt incremental để không ghi tệp buildinfo ngoài phạm vi W10.
- Python của runtime nhập NumPy qua vendor thành công: **2.3.5**, exit 0. Kiểm tra chỉ đọc chọn `frontend-knowledge-ui-20261101b`, có `BUILD_ID`.

4. Quyết định thiết kế và giới hạn

Giữ nguyên thứ tự ưu tiên critical/high và ngoại lệ hạn nộp cũ; chỉ thu hẹp miễn trừ W9. Chọn snapshot lúc gọi lệnh, không chốt tên tại import. Các biên nhận build hiện có không chứa thời gian, nên dùng mtime của `BUILD_ID`; khi bằng nhau dùng tên làm tiêu chí phụ ổn định.
Bằng chứng là test offline xác định với tiến trình/HTTP/provider giả, đối chiếu logic sao lưu và kiểm tra nhập NumPy bằng Python runtime; chưa đo trải nghiệm người dùng thật.

5. Cần phối hợp / rủi ro

41 ca tích hợp vẫn bỏ qua vì thiếu điều kiện rehearsal/live/OCR được bật rõ ràng. Chưa khởi động/build runtime 8015 theo đúng brief; không gọi dịch vụ trả phí, không tắt tiến trình, không commit/push/xóa dữ liệu. Nếu listener dùng engine hoặc snapshot khác, script vẫn từ chối và giữ nguyên tiến trình.
Tài liệu `.claude/skills/campus247/references/verification.md` còn hướng dẫn đặt `PYTHONPATH` thủ công; nằm ngoài quyền sửa W10 nên cần phiên sở hữu tài liệu cập nhật. Đã kiểm tra trạng thái Git, phạm vi và whitespace; giữ nguyên việc dở và tệp của W8.
