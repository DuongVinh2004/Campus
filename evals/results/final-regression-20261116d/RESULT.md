# Regression cuối với môi trường đúng cho từng nhóm (2026-11-16)

Chạy bằng `evals/runners/run_full_regression.py`: suite chính cộng 5 nhóm cần thư mục tạm đã đăng ký (stream-a/b/c, staff-12, completion) và `LEARNING_TEST_ROOT`.
Kết quả: suite chính 4814 đạt, 4 lỗi; các nhóm còn lại 109 + 38 + 42 + 57 + 18 đều đạt. **Từ 112 mục lỗi của mốc còn 4**, đều là chốt chặn chờ con người duyệt và KHÔNG bị lách:
- `test_guard.py::test_reviewed_addition_preserves_historical_baseline_and_ancestry` và `test_retrieval_scope_migration.py::test_reviewed_ancestry_and_forward_only_recovery`: danh sách băm migration đã duyệt không khớp các migration mới; cần người duyệt migration rồi mới mở rộng danh sách.
- `dependency_resolution/test_verifier.py` (2 test): bản phê duyệt dependency của con người không khớp tập ứng viên hiện tại; cần người duyệt lại.

Các mục đã giải (108): 35 `unit/learning` (cần `LEARNING_TEST_ROOT`), 32 `unified_final` + 4 `unified_*` + 2 `integration` (cần thư mục tạm đã đăng ký), 28 `test_runtime_audit_fixes` (stub lệch chữ ký `learning=` và trang admin/staff đã được cho phép; sửa test, không đổi kỳ vọng nào khác), 2 `test_openapi` (contract nay dùng `$ref` cho path; test chọn operation nằm trong tài liệu), 1 `test_import_boundaries` (hàm `record` và `UnavailableScanner` của learning chuyển xuống tầng application), 2 DST ở `learning_entry` (thiếu gói `tzdata==2026.6` đã khóa trong uv.lock; cài đúng wheel, băm khớp).
Ghi chú: các file learning (`application/learning/*`, `infrastructure/learning/*`, `presentation/learning.py`) chưa được git theo dõi nên thay đổi ở đó nằm trong cây làm việc, chưa vào commit.
