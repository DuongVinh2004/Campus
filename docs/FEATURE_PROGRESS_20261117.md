# Tiến độ làm các task A/B/C và hướng dẫn làm tiếp (cập nhật 17/11/2026, tối)

Đọc file này đầu tiên khi tiếp tục. Thiết kế: [GROUP_A](GROUP_A_IMPLEMENTATION_PLAN_20261117.md),
[GROUP_B](GROUP_B_DESIGN_20261117.md), [GROUP_C](GROUP_C_DESIGN_20261117.md). Danh sách task:
[FEATURE_READY_TASKS_20261117.md](FEATURE_READY_TASKS_20261117.md).

## Đã xong (đã commit, chưa push)

Các nhánh xếp chồng: mỗi nhánh tạo từ HEAD của nhánh trước, vì nhánh trước còn commit chưa merge. Nhánh hiện tại `feat/ops-metrics`
chứa tất cả. Thứ tự: `docs/feature-design-plan` → `fix/schedule-ics-and-timezone` → `fix/learning-session-revocation-boundary` →
`fix/testing-environment-identity` → `feat/source-freshness-state` → `feat/practice-pure-logic` → `feat/ci-regression-mode` → `feat/ops-metrics`.

| Task | Commit | Kết quả đo được |
|---|---|---|
| B1.2 + phần thư viện B1.1 | `373b76f` | `lib/ics.ts`, `lib/schedule-time.ts`: 23 test vitest đạt. **Chưa commit phần nối vào trang** (xem "Việc dở" bên dưới) |
| A0 (AUD-001/002) | `aba8235` | Test tái hiện đỏ trên mã cũ (PATCH trả 200 và lưu; tải file trả 200), xanh sau sửa. Bộ test học liệu 124 đạt, 1 bỏ qua |
| A5.1/A5.2 (AUD-003) | `b104e0f` | `testing` được phép với adapter synthetic; staging/production vẫn bị từ chối; 24 test đạt |
| C3.1 | `e7c5e41` | `application/knowledge/source_freshness.py`, 20 test đạt |
| B3.1/B3.2 | `e4bca75` | `application/learning/practice.py`, 26 test đạt |
| A5.3/A5.4 | `db86900` | `run_full_regression.py --ci` + `ci.yml` theo lock. Bộ `--ci` chạy cục bộ: **2284 đạt, 5 xfail** (10 phút 53 giây); `tests/delivery` 24 đạt (gồm test hợp đồng CI) |
| A5.6 | (không cần commit) | `verify_dependencies.py` đạt, 34 test dependency đạt, `ZoneInfo('Asia/Ho_Chi_Minh')` chạy → AUD-005 và AUD-009 không còn tái hiện |
| A2.1/A2.2 | `361c89a` | `observability/ops_metrics.py`, gộp worker qua file snapshot |
| A2.3 | `24c8a62` | móc vào chat, 429, watchdog; 15 test hook đạt, test admission/abuse/watchdog cũ vẫn đạt (57) |
| A2.4 | `3fc2279` | gateway `GET /v1/status`; 27 test sidecar đạt |
| A2.5 (phần dựng tài liệu) | `643f276` | `observability/ops_status.py`; 34 test observability đạt |

## Việc dở và việc bị chặn

- **Nối B1.1/B1.2 vào trang lịch**: đã sửa trong working tree `apps/web/src/app/schedule/page.tsx` và
  `apps/web/src/features/schedule/ScheduleView.tsx` (+ test mới `ScheduleView.ics.test.tsx`), vitest 14 đạt, `tsc` sạch. **Không commit**
  vì hai file có thay đổi dở khác của chủ dự án; chủ dự án tự commit cùng thay đổi của mình.
- **A5.5** (chạy workflow trong Linux): Docker không chạy; WSL Ubuntu có nhưng đang tắt, và `uv sync --frozen` phải tải gói. Chờ cho phép tải.
- **A5.7** (chạy CI trên GitHub): chờ duyệt push.
- Test `test_session_revocation_boundary.py` và `test_environments.py` đạt trên working tree, nhưng **không** đạt trên bản checkout sạch của HEAD,
  vì HEAD thiếu các thay đổi dở của chủ dự án mà chúng phụ thuộc (ví dụ payload tạo buổi học, tham số `tenant_id` của adapter).

## Làm tiếp theo thứ tự (mỗi mục là một đơn vị commit được)

1. **A2.5b**: gắn `run_writer` vào runtime (`scripts/knowledge_platform.py`, `owned_lifespan`; file này có thay đổi dở của chủ dự án nên dùng cách "stage chỉ phần của mình") và đặt `OpsConfig`.
2. **A2.6**: `presentation/admin_ops.py`: `GET /v1/admin/operations/status` (`require_admin`, `Cache-Control: no-store`) và `GET /metrics` chỉ loopback; đăng ký router trong `scripts/knowledge_platform.py` hoặc `bootstrap/app.py` (cả hai có thay đổi dở).
3. **A2.7**: panel web trong `apps/web/src/features/admin/`, hiện trong `/admin`.
4. **A4.1–A4.4**: `LAST_BACKUP.json` trong `infra/cloud/backup.py`, `rehearse_restore.py`, timer, `offsite.py` với restic giả.
5. **C3.2–C3.5**, **B1.3–B1.6**, **A3.1–A3.6**, **A1.1–A1.8**, **B2.1–B2.3**, **C1.1–C1.4**, **C2.1/C2.4**, **B3.3–B3.6**, **B4.1–B4.4** (theo `FEATURE_READY_TASKS`).

## Quy tắc đã dùng (giữ nguyên khi làm tiếp)

- Task mới → nhánh mới, commit khi xong và đã kiểm, **không push** khi chưa được duyệt. Chỉ `git add` đường dẫn của mình.
- **File có thay đổi dở của chủ dự án** (kiểm bằng `git status --short <file>`: `M` trước khi mình sửa): không commit nguyên file. Cách làm đã dùng:
  lấy `git show HEAD:<file>`, áp đúng các thay thế của mình lên bản đó (script Python assert mỗi chuỗi cũ xuất hiện đúng một lần), `git hash-object -w`,
  rồi `git update-index --cacheinfo <mode>,<blob>,<path>`. Working tree giữ nguyên.
- Chạy pytest bằng `.venv/Scripts/python.exe -B -m pytest <đường dẫn> -q -o pythonpath="services/api/src services/worker/src packages/synthetic/src" --basetemp=.pytest-tmp-<tên mới> -p no:cacheprovider`
  (biến `PYTHONPATH` dạng `a:b` qua Git Bash không đáng tin; test học liệu cần `LEARNING_TEST_ROOT` trỏ tới thư mục có sẵn trong repo; `--basetemp` phải nằm trong repo).
- Web: `npx vitest run <đường dẫn>` và `npx tsc --noEmit -p .` trong `apps/web`.
- Sửa file bằng công cụ Edit/Write; heredoc Python với `\n` trong chuỗi làm hỏng file (đã gặp).
- Thư mục `.pytest-tmp-aud1/` là rác của lượt này (đã bị bỏ qua khỏi commit); chủ dự án xóa được.
