W6 đã hoàn tất sửa mã theo brief; chưa triển khai lên runtime 8015.

**1. Đã sửa và nguyên nhân gốc**

- L-23: bổ sung `--engine {v1,v2}` mặc định v2, `--rag-v2-index` mặc định `data/rag_v2_index/embedded2`; truyền môi trường cho API và ghi receipt. Trước đây script phụ thuộc môi trường bên ngoài, dễ chạy nhầm v1.
- Kiểm `/health/ready` trước đăng nhập kiểm trạng thái release; báo rõ engine sai/không xác định, không tái dùng âm thầm. API được thăm dò tối đa 180 giây thay vì 35 giây khi nạp chỉ mục chậm.
- L-15: thêm `fonts/` vào proxy GET; giữ chặn `..`, dấu gạch chéo ngược và giới hạn 10 MiB. `apps/web/public` chỉ có `fonts/` và `images/`; không mở thêm trang.
- L-10: bỏ `token` khỏi JSON đăng nhập, giữ các trường khác và cookie `auth_token` HttpOnly, SameSite=Strict, max-age 3600.
- L-19: ẩn `/docs`, `/docs/oauth2-redirect`, `/redoc`, `/openapi.json` trong app vận hành; bộ đếm đăng nhập chuyển từ toàn cục sang từng username, giữ 5 lần/60 giây.
- L-13: thêm GET `/v1/assistant/conversations?limit=&cursor=&title=` chỉ đọc lịch sử của sinh viên hiện tại, bỏ `temporary`, hỗ trợ phân trang/tìm tên và trạng thái lưu giữ; không gắn route preview/confirm.

**2. Tệp và test đã thêm**

- Sửa `scripts/knowledge_platform.py`, `scripts/knowledge_platform_runtime.py`, `services/api/src/campus247/infrastructure/identity/local_student.py`.
- Thêm `tests/operations/test_runtime_audit_fixes.py`: 40 ca qua các test sau:
  - `test_login_uses_only_httponly_cookie`
  - `test_login_keeps_origin_and_password_guards`
  - `test_operational_schema_routes_are_not_public`
  - `test_proxy_allows_build_assets`
  - `test_proxy_rejects_traversal_and_additional_pages`
  - `test_proxy_keeps_response_size_limit`
  - `test_student_login_limit_is_per_username`
  - `test_student_login_window_expires`
  - `test_conversation_catalog_is_owned_filtered_and_read_only`
  - `test_catalog_rejects_ineligible_identity`
  - `test_catalog_rejects_invalid_or_revoked_session`
  - `test_catalog_preserves_metadata_and_matches_shared_page_contract`
  - `test_start_passes_explicit_engine_and_index_to_api`
  - `test_start_cli_defaults_to_v2`
  - `test_start_cli_accepts_explicit_engine_and_index`
  - `test_missing_index_stops_before_any_start_or_state_access`
  - `test_api_reuse_rejects_wrong_or_unknown_engine_before_login`
  - `test_readiness_polls_past_slow_index_load_and_stays_bounded`
  - `test_readiness_reports_engine_mismatch_without_retry`
- Báo cáo: `evals/results/audit-opus-20261101/impl/W6-report.md`.

**3. Lệnh và kết quả trước/sau**

- Gốc repo, `.venv/Scripts/python.exe -B -m pytest -q tests/operations -p no:cacheprovider`: trước sửa **36 đạt / 0 đỏ**.
- Test tái hiện: cùng Python, `-m pytest -q tests/operations/test_runtime_audit_fixes.py -p no:cacheprovider --basetemp=.pytest-tmp-W6-red2-20261101 --tb=short`: mã cũ **10 đạt / 17 đỏ**; sau đó bổ sung 13 ca bảo vệ.
- Sau sửa, cùng Python, `-m pytest -q tests/operations -p no:cacheprovider --basetemp=.pytest-tmp-W6-green2-20261101 --tb=short`: **76 đạt / 0 đỏ**, gồm **40 ca W6 đạt**; exit 0.
- Từ `apps/web`, `npx.cmd --no-install vitest run src/features/chat`: trước **121 đạt / 3 đỏ**, lần cuối **131 đạt / 3 đỏ**; exit 1. Có thêm 10 ca của phiên song song; 3 ca đỏ vẫn là 2 `ChatPanel.test.tsx` và 1 `history.test.ts` có sẵn.
- Tiếp theo `npx.cmd --no-install tsc --noEmit`: **0 lỗi**, exit 0. Dùng `npx.cmd` vì PowerShell chặn `npx.ps1`; lượt cuối đặt npm offline/tắt update notifier.
- Đã kiểm lại phạm vi Git và mã thay đổi; không commit/push/reset/clean/xóa tệp.

**4. Thiết kế và giới hạn bằng chứng**

- `ConversationCatalogService` kế thừa scope chỉ nhận synthetic; sinh viên local có `is_synthetic=False`. Dùng route tối thiểu theo phương án brief cho phép, trên repository và actor store hiện có; giữ kiểm tenant, phiên, vai trò, chủ sở hữu và binding metadata.
- Phản hồi giữ metadata tên/pinned/archived, thời hạn lưu giữ và cursor gắn chủ sở hữu/bộ lọc; một test so toàn bộ JSON với `ConversationCatalogService.page`.
- Bằng chứng là TestClient, SQLite thử nghiệm trong workspace, tiến trình/HTTP/đồng hồ giả và các kiểm tra tự động; không gọi mô hình, không đọc tệp bí mật. Chưa đo thời gian nạp chỉ mục thật hay mức dùng được với người dùng thật.

**5. Cần phối hợp / rủi ro**

- W7 dùng cookie đăng nhập và endpoint danh sách mới; cần triển khai đồng bộ phần web bỏ phụ thuộc token JSON/localStorage.
- Không khởi động, build hoặc gọi runtime 8015 theo W0. Các thay đổi chỉ có hiệu lực sau lần triển khai được phép.
- Ba tệp mã vẫn chưa được Git theo dõi như ban đầu; giữ nguyên dữ liệu và thay đổi sẵn có. Ba test web đỏ cũ nằm ngoài phạm vi W6.
