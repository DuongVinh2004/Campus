# Tiến độ làm các task A/B/C và hướng dẫn làm tiếp (cập nhật 17/11/2026, tối)

Đọc file này đầu tiên khi tiếp tục. Thiết kế: [GROUP_A](GROUP_A_IMPLEMENTATION_PLAN_20261117.md),
[GROUP_B](GROUP_B_DESIGN_20261117.md), [GROUP_C](GROUP_C_DESIGN_20261117.md). Danh sách task:
[FEATURE_READY_TASKS_20261117.md](FEATURE_READY_TASKS_20261117.md).

## Đã xong (đã commit, chưa push)

Các nhánh xếp chồng: mỗi nhánh tạo từ HEAD của nhánh trước, vì nhánh trước còn commit chưa merge. Nhánh cuối `feat/schedule-ics-feed`
chứa tất cả. Thứ tự: `docs/feature-design-plan` → `fix/schedule-ics-and-timezone` → `fix/learning-session-revocation-boundary` →
`fix/testing-environment-identity` → `feat/source-freshness-state` → `feat/practice-pure-logic` → `feat/ci-regression-mode` → `feat/ops-metrics` → `feat/ops-runtime-wiring` → `feat/ops-web-panel` → `feat/backup-status-files` → `feat/restore-drill` → `feat/offsite-backup` → `feat/source-freshness-api` → `feat/source-freshness-ui` → `feat/reminders-engine` → `feat/schedule-ics-feed`.

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
| A2.5 | `643f276` | `observability/ops_status.py`; 34 test observability đạt |
| A2.6 | `f02fd11` | `presentation/admin_ops.py` (`/v1/admin/operations/status`, `/metrics` chỉ loopback, từ chối mọi header proxy); 13 test đạt |
| A2.5b (nối runtime) | `7f1d34e` | 20 dòng trong `scripts/knowledge_platform.py` (chỉ phần của mình); **chưa chạy trên runtime thật**, cần khởi động lại 8015 (chủ dự án quyết định) |
| A2.7 | `4e4988c` | `features/admin/OperationsPanel.tsx`, `lib/ops-assess.ts`, `lib/ops-status-api.ts`: 19 test vitest đạt, `tsc` sạch |
| A4.1 | `6a10dee` | `backup.py` ghi `LAST_BACKUP.json` (kể cả khi lỗi), lệnh `status`; 8 test đạt |
| A4.2/A4.3 | `624da45` | `rehearse_restore.py` + `rehearse.sh` + timer tháng; 12 test đạt (bước giả). **Chưa chạy trên Postgres thật hay systemd thật** |
| A4.4 | `c3cf551` | `offsite.py` bọc restic; 11 test đạt với restic giả (1 bỏ qua trên Windows). Chưa chạy restic thật |
| C3.2 | `24b2d20`, `47a7ab7` | `freshness_service.py`, `knowledge_freshness.py` (GET /v1/knowledge/freshness, POST .../reviewed), đã nối runtime; 17 test đạt với DB giả. **SQL chưa chạy trên Postgres thật** (cụm local không chạy lúc làm) |
| C3.3 | `872b2c8` | `/knowledge/freshness` + `FreshnessPanel`: 6 test vitest đạt, `tsc` sạch. Chưa có mục menu (cần sửa `AppShell.tsx`, file có thay đổi dở) |
| B1.4 (engine) | `20c9f46` | `application/campus_ops/reminders.py` (nhắc 24 giờ và 2 giờ trước giờ thi, một lần, không nhắc sau hạn, restart không lặp); 25 test đạt cùng `ics.py` |
| B1.3 | `ae81b67` | `GET /v1/students/me/schedule.ics`; 35 test campus_ops đạt |
| B1.4 (nối runtime) | `3f2b073` | vòng nhắc 5 phút trong leader jobs; 3 test đạt. **Chưa chạy trên runtime thật** |

## Việc dở và việc bị chặn

- **Nối B1.1/B1.2 vào trang lịch**: đã sửa trong working tree `apps/web/src/app/schedule/page.tsx` và
  `apps/web/src/features/schedule/ScheduleView.tsx` (+ test mới `ScheduleView.ics.test.tsx`), vitest 14 đạt, `tsc` sạch. **Không commit**
  vì hai file có thay đổi dở khác của chủ dự án; chủ dự án tự commit cùng thay đổi của mình.
- **Hiện panel vận hành trên `/admin`**: đã thêm 2 dòng vào `apps/web/src/app/admin/page.tsx` trong working tree (không commit, file có thay đổi dở của chủ dự án). Cần dựng lại frontend snapshot mới thấy trên 8015.
- Trang lịch (`schedule/page.tsx`) nên dùng `item.kind === "EXAM"` do API đã trả `kind` thay vì đoán theo tên môn (B1.1); chưa sửa vì file có thay đổi dở.
- **A5.5** (chạy workflow trong Linux): Docker không chạy; WSL Ubuntu có nhưng đang tắt, và `uv sync --frozen` phải tải gói. Chờ cho phép tải.
- **A5.7** (chạy CI trên GitHub): chờ duyệt push.
- Test `test_session_revocation_boundary.py` và `test_environments.py` đạt trên working tree, nhưng **không** đạt trên bản checkout sạch của HEAD,
  vì HEAD thiếu các thay đổi dở của chủ dự án mà chúng phụ thuộc (ví dụ payload tạo buổi học, tham số `tenant_id` của adapter).

## Làm tiếp theo thứ tự (mỗi mục là một đơn vị commit được)

1. **C3.4–C3.5** (nhắc hạn nguồn, nhãn trong CitationDrawer), **B1.5–B1.6** (nhắc phiếu ra lớp, cài đặt nhắc), **A3.1–A3.6**, **A1.1–A1.8**, **B2.1–B2.3**, **C1.1–C1.4**, **C2.1/C2.4**, **B3.3–B3.6**, **B4.1–B4.4** (theo `FEATURE_READY_TASKS`).

## Quy tắc đã dùng (giữ nguyên khi làm tiếp)

- Task mới → nhánh mới, commit khi xong và đã kiểm, **không push** khi chưa được duyệt. Chỉ `git add` đường dẫn của mình.
- **File có thay đổi dở của chủ dự án** (kiểm bằng `git status --short <file>`: `M` trước khi mình sửa): không commit nguyên file. Cách làm đã dùng:
  lấy `git show HEAD:<file>`, áp đúng các thay thế của mình lên bản đó (script Python assert mỗi chuỗi cũ xuất hiện đúng một lần), `git hash-object -w`,
  rồi `git update-index --cacheinfo <mode>,<blob>,<path>`. Working tree giữ nguyên.
- Chạy pytest bằng `.venv/Scripts/python.exe -B -m pytest <đường dẫn> -q -o pythonpath="services/api/src services/worker/src packages/synthetic/src" --basetemp=.pytest-tmp-<tên mới> -p no:cacheprovider`
  (biến `PYTHONPATH` dạng `a:b` qua Git Bash không đáng tin; test học liệu cần `LEARNING_TEST_ROOT` trỏ tới thư mục có sẵn trong repo; `--basetemp` phải nằm trong repo).
- Web: `npx vitest run <đường dẫn>` và `npx tsc --noEmit -p .` trong `apps/web`.
- Sửa file bằng công cụ Edit/Write; heredoc Python với `\n` trong chuỗi làm hỏng file (đã gặp).
- Bẫy vitest: `beforeEach(() => mock.mockReset())` trả về mock, vitest gọi nó như hàm dọn dẹp sau test; dùng `beforeEach(() => { mock.mockReset(); })`.
- Thư mục `.pytest-tmp-aud1/` là rác của lượt này (đã bị bỏ qua khỏi commit); chủ dự án xóa được.
