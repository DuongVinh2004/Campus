# Nhóm A — thiết kế chi tiết và kế hoạch triển khai (17/11/2026, bản 2)

Trạng thái: thiết kế, chưa triển khai. Nguồn: [FEATURE_PROPOSALS_20261117.md](FEATURE_PROPOSALS_20261117.md).
Danh sách task làm được ngay của mọi nhóm: [FEATURE_READY_TASKS_20261117.md](FEATURE_READY_TASKS_20261117.md).
Bám [kế hoạch 2 giai đoạn](04-architecture/ROLLOUT_PLAN_LOCAL_THEN_CLOUD_20261115.md): mọi việc làm và kiểm trên máy này và bản
mô phỏng Docker/systemd. Không thuê VPS, không đặt dịch vụ trả phí, không mở cho người dùng thật.

Bằng chứng của thiết kế: đọc mã và cấu hình hiện tại (dẫn `đường-dẫn:dòng`); chưa chạy thay đổi nào.
Quy ước: ✅ làm được ngay · ⏳ chờ đầu vào (ghi rõ đầu vào nào).

## 0. Hiện trạng đã kiểm

| Hạng mục | Hiện có | Còn thiếu |
|---|---|---|
| Danh tính | `IdentityProviderPort`, `IdentityContext` ([ports/identity.py](../services/api/src/campus247/ports/identity.py)); `LocalCampusIdentityAdapter` chọn bộ xác minh theo issuer ([local_student.py:74](../services/api/src/campus247/infrastructure/identity/local_student.py)); đăng nhập mật khẩu `/v1/knowledge/platform/session` ([knowledge_platform.py:581](../scripts/knowledge_platform.py)). | Không có OIDC/SAML. Cookie `auth_token` chưa có `Secure`. Kiểm `request.client.host` mất tác dụng sau Caddy (mọi client là 127.0.0.1). |
| Thư viện | `pyjwt`, `cryptography`, `prometheus-client`, `structlog`, OpenTelemetry đã ghim trong `pyproject.toml`. | Không cần thêm thư viện Python cho A1–A3. |
| Tín hiệu vận hành | `chat_admission_rejected` ([chat.py:149](../services/api/src/campus247/presentation/chat.py)), `VECTOR_STATS` ([vector_stats.py](../services/api/src/campus247/rag_v2/observability/vector_stats.py)), `LoopWatchdog` ([loop_watchdog.py](../services/api/src/campus247/infrastructure/loop_watchdog.py)), 429 ở [abuse_limits.py:116](../services/api/src/campus247/presentation/middleware/abuse_limits.py), bộ đếm gateway `/health` ([gateway_sidecar.py:99](../scripts/gateway_sidecar.py)), learning worker trong `/health/entry` ([knowledge_platform.py:509](../scripts/knowledge_platform.py)), `BackgroundLeader` ([leader.py](../services/api/src/campus247/infrastructure/leader.py)). | Chỉ là log hoặc bộ đếm từng tiến trình; 2 worker không gộp; không ngưỡng, không cảnh báo. |
| Admin | `/v1/admin/overview` (ticket, đặt phòng, phòng, audit), `require_admin` ([campus_ops/service.py:547](../services/api/src/campus247/application/campus_ops/service.py)). | Không có số liệu hệ thống. |
| Egress | `egress_policy.py` lọc **trường dữ liệu** gửi LLM. | Chưa có allowlist **host** cho kết nối ra ngoài khác (IdP, kênh cảnh báo). |
| Sao lưu | `infra/cloud/backup.py` backup/verify/restore, timer 03:10, giữ 14 bản, `compare_restore.py`, `restore.sh`. | Bản ngoài server có mã hóa; diễn tập tự động; file trạng thái cho dashboard/cảnh báo. |
| CI | `ci.yml`, `security.yaml`, chỉ khi push/PR vào `main`. | AUD-003: `Settings.ENVIRONMENT` dùng `testing` ([settings.py:25](../services/api/src/campus247/bootstrap/settings.py)), mock cho phép `test` ([mock.py:13](../services/api/src/campus247/infrastructure/identity/mock.py)). CI đặt `CAMPUS247_ENV` nhưng Settings đọc `ENVIRONMENT`. Thiếu `LEARNING_TEST_ROOT` và đường import worker (AUD-004). Cài bằng `pip install -e .`/`npm install`, không theo lock. |
| Verifier | `APPROVED_CANDIDATE_SHA256` bằng SHA256 `uv.lock` ghi trong AUD-005 ([verify_dependencies.py:25](../scripts/verify_dependencies.py)). | AUD-005 có vẻ đã đóng; cần chạy lại xác nhận. |

## 1. Thứ tự và phụ thuộc

```
A0 kiểm lại AUD-001/002 ─┐
A5 CI ───────────────────┼─> A2 số liệu ──> A3 cảnh báo ──┐
                         ├─> A4 sao lưu ngoài ────────────┼─> Đợt kiểm tổng hợp (Docker/systemd 4 CPU)
                         └─> A1 OIDC ─────────────────────┘
```

| Mục | Ước lượng | File (các nhánh song song không giao nhau) |
|---|---|---|
| A0 | 0,5–1 ngày | `presentation/learning.py`, `application/learning/service.py`, test |
| A5 | 2–3 ngày | `.github/workflows/`, `bootstrap/settings.py`, `identity/mock.py`, `evals/runners/run_full_regression.py` |
| A2 | 4–5 ngày | `observability/ops_metrics.py` (mới), `presentation/admin_ops.py` (mới), `scripts/gateway_sidecar.py`, `apps/web/src/features/admin/` |
| A4 | 2–3 ngày | `infra/cloud/backup.py`, `infra/cloud/offsite.py`, `infra/cloud/rehearse_restore.py` (mới), unit systemd |
| A1 | 5–7 ngày | `infrastructure/identity/oidc*.py`, `presentation/oidc.py` (mới), `apps/web/src/app/login/` |
| A3 | 3–4 ngày | `observability/alerts.py`, `infrastructure/notify/` (mới), `infra/cloud/watchdog.py` + unit |

Tổng khoảng 17–24 ngày làm việc (ước lượng thô, chưa đo).

---

## A0 — Kiểm lại ranh giới thu hồi phiên (AUD-001/002)

Không thuộc nhóm A gốc nhưng là điều kiện an toàn trước khi dùng thật. Mã có `revalidate_identity`
([learning.py:285](../services/api/src/campus247/presentation/learning.py)), có thể đã sửa một phần.

| ID | Việc | Kiểm chứng | |
|---|---|---|---|
| A0.1 | Chạy lại hai ca tái hiện của audit (`docs/PROJECT_AUDIT_20261111_REPRO.py`) trên mã hiện tại | Ghi kết quả từng ca | ✅ |
| A0.2 | Nếu còn lỗi: kiểm lại principal/session/roles trong transaction trước mutation, và sau mọi `await` trước byte đầu tiên của response | Ca tái hiện thất bại với mã cũ, đạt với mã mới; thêm ca cho PATCH, DELETE, publish, tải tệp | ✅ |

---

## A5 — CI và môi trường kiểm thử tái lập

**Xong khi:** container Ubuntu 24.04 sạch chạy toàn bộ workflow đạt; test AUD-003 thất bại với mã cũ, đạt với mã mới;
không guard nào bị tắt hoặc nới.

### Thiết kế

- **Tên môi trường một nguồn.** `bootstrap/settings.py` export `KNOWN_ENVIRONMENTS = ("development", "testing", "staging", "production")`
  và `SYNTHETIC_IDENTITY_ENVIRONMENTS = {"development", "testing"}`. `mock.py` dùng tập này cộng bí danh cũ `local`, `test`,
  `demo-synthetic` (giữ cho script cũ). `staging` và `production` không bao giờ nằm trong tập.
- **Biến CI.** Grep `CAMPUS247_ENV`: nếu không có mã đọc biến này thì CI đổi sang `ENVIRONMENT=testing`; nếu có thì giữ cả hai.
- **Workflow mới** (`ci.yml`):

| Job | Bước chính |
|---|---|
| `python` | `actions/checkout` → `astral-sh/setup-uv` (ghim phiên bản) → `uv sync --frozen` → `python -B scripts/verify_dependencies.py` → tạo `LEARNING_TEST_ROOT=${{ github.workspace }}/.ci-evidence/learning-${{ github.run_id }}` → `PYTHONPATH=services/worker/src` → `python -B evals/runners/run_full_regression.py --ci --out .ci-evidence/regression` → upload `.ci-evidence/` làm artifact |
| `web` | `pnpm/action-setup` 9.12.0 → `actions/setup-node` (phiên bản như `infra/cloud/build_frontend.sh`) → `pnpm install --frozen-lockfile` → `pnpm --filter web exec tsc --noEmit` → `pnpm --filter web test` |
| `catalog`, `ai-eval`, `release-manifest` | Giữ như cũ, đổi sang `uv sync --frozen` |

  Trigger: `push` vào `main`, `pull_request` mọi nhánh, `workflow_dispatch`.
- **`run_full_regression.py --ci`.** Loại các nhóm cần provider trả phí, ledger thật, OCR native, ClamAV, model 18081/18082, Postgres
  thật. Các nhóm bị loại được in ra cùng lý do, để báo cáo không gộp nhầm "bỏ qua" vào "đạt".

### Task

| ID | Việc | Kiểm chứng | |
|---|---|---|---|
| A5.1 | Hợp nhất tên môi trường (AUD-003) + test `create_app` cho 4 môi trường | Test đỏ trước, xanh sau; `production` vẫn từ chối mock | ✅ |
| A5.2 | Sửa biến môi trường của CI | Grep `CAMPUS247_ENV` trước khi đổi | ✅ |
| A5.3 | Thêm `--ci` vào `run_full_regression.py` | In danh sách nhóm chạy và bỏ qua; chạy thử trên Windows | ✅ |
| A5.4 | Viết lại `ci.yml` theo bảng trên (uv/pnpm theo lock, LEARNING_TEST_ROOT, PYTHONPATH, artifact) | YAML hợp lệ (`actionlint` nếu có sẵn, không thì parse YAML) | ✅ |
| A5.5 | Chạy đúng các lệnh của workflow trong container `ubuntu:24.04` | Mọi job đạt; log ở `evals/results/ci-linux-<stamp>/` | ✅ nếu image đã có sẵn; nếu phải tải thì xin phép |
| A5.6 | Chạy lại verifier (AUD-005) và test múi giờ (AUD-009); ghi trạng thái vào báo cáo audit | Lệnh + mã thoát | ✅ |
| A5.7 | Chạy trên GitHub Actions | Mọi job xanh | ⏳ chủ dự án duyệt push nhánh |

---

## A2 — Lớp số liệu vận hành và dashboard quản trị

**Xong khi:** test bộ đếm, ghép worker, quyền và không lộ dữ liệu đều đạt. Chạy tải bằng provider giả 100 × 2: số lượt trên
dashboard khớp `rag_load_test.py`, p95 lệch không quá một mốc, p95 trước/sau khi bật lệch ≤ 2 %.

### Phương án gộp số liệu giữa 2 worker

| Phương án | Lợi | Hại | |
|---|---|---|---|
| **Snapshot JSON từng worker** trong `<state>/ops-metrics/` | Không migration, không thư viện, chạy cả Windows/Linux, worker chết thì file tự cũ | Trễ tới 15 s | **Chọn** |
| Bảng Postgres | Truy vấn linh hoạt | Migration 0032 cần chủ dự án duyệt hash; thêm ghi DB mỗi 15 s | Dự phòng |
| `prometheus_client` multiprocess | Chuẩn | Thiết kế cho gunicorn, chưa kiểm trên Windows, cần thư mục mmap | Không |

### Mô hình dữ liệu (`observability/ops_metrics.py`)

```python
LATENCY_BUCKETS_S = (0.5, 1, 2, 3, 5, 8, 12, 20, 30, inf)

@dataclass
class MinuteBucket:                      # 1 phút, vòng 60 ô
    minute: int                          # epoch // 60
    turns: int; turns_ok: int; turns_abstained: int
    turn_errors: dict[str, int]          # theo mã lỗi đã chuẩn hóa, không có chuỗi exception
    first_token_hist: list[int]; total_hist: list[int]   # đếm theo LATENCY_BUCKETS_S
    admission_rejected: int; rate_limited: dict[str, int]   # theo nhóm route cố định
    loop_blocked: int; loop_blocked_max_ms: int

class OpsMetrics:
    def record_turn(self, *, outcome: str, error_code: str | None, first_token_s: float | None, total_s: float) -> None
    def record_admission_rejected(self) -> None
    def record_rate_limited(self, route_group: str) -> None
    def record_loop_blocked(self, ms: int) -> None
    def snapshot(self) -> dict          # 60 ô + gauge tức thời (in_flight, waiting, limit) + VECTOR_STATS.snapshot()
```

- Thread-safe bằng `threading.Lock` như `VectorStats`. Chỉ có số; nhóm route và mã lỗi là tập cố định.
- **Writer:** task asyncio mỗi 15 s ghi `worker-<pid>.json` (file tạm + `os.replace`, có `pid`, `started_at`, `written_at`).
- **Reader:** `aggregate(dir, now)` đọc mọi file có `written_at` trong 60 s, cộng ô cùng `minute`, trả `workers_reporting`.
  File cũ hơn 10 phút được xóa (đây là file do chính lớp này tạo).

### Điểm móc

| Tín hiệu | Chỗ móc |
|---|---|
| Lượt chat | bọc generator SSE trong `open_stream` ([chat.py:136](../services/api/src/campus247/presentation/chat.py)): ghi thời điểm token đầu, kết quả cuối (ok / abstained / mã lỗi) trong `finally` |
| 503 admission | ngay cạnh log `chat_admission_rejected` |
| 429 | hai nhánh trả 429 trong `abuse_limits.py` |
| Vòng lặp bị chặn | callback khi `LoopWatchdog` kết thúc một lần bị chặn |
| Gateway | endpoint mới `GET /v1/status` của sidecar, yêu cầu `x-gateway-token`: bộ đếm + `DailySpendCap` (lời gọi/USD hôm nay, trần) chỉ đọc |
| Model | `GET` health của 18081/18082, timeout 1 s, cache 10 s |
| Nền | `app.state.learning_worker_status`, `BackgroundLeader.is_leader` |
| Hạ tầng | `shutil.disk_usage` của root và thư mục backup; `LAST_BACKUP.json`, `REHEARSAL.json` (A4) |

### API

`GET /v1/admin/operations/status` — dùng `require_admin` như overview; `Cache-Control: no-store`; rate limit 30/phút.

```json
{
  "generated_at": "2026-11-17T10:00:00Z", "workers_reporting": 2,
  "window_minutes": 60,
  "turns": {"last_5m": {"total": 120, "ok": 116, "abstained": 3, "errors": {"AI_WORKFLOW_UNAVAILABLE": 1}},
            "p50_s_le": 5, "p95_s_le": 12, "first_token_p95_s_le": 3},
  "load": {"in_flight": 7, "waiting": 0, "limit": 24, "admission_rejected_5m": 0, "rate_limited_5m": {"chat": 2}},
  "retrieval": {"failed_rate": 0.01, "timeouts": 0, "vector_ms_max": 2100},
  "loop": {"blocked_5m": 0, "blocked_max_ms": 0},
  "gateway": {"reachable": true, "ok": 940, "refused": 0, "failed": 2, "in_flight": 3,
              "today": {"calls": 940, "call_cap": 2000, "usd": "1.21", "usd_cap": "5.00"}},
  "models": {"embedding": "up", "reranker": "up"},
  "background": {"leader": true, "learning_worker": "ready"},
  "storage": {"data_free_pct": 41.2, "backup_free_pct": 41.2},
  "backup": {"last_at": "2026-11-17T03:12:00Z", "verified": true, "offsite": "not_configured", "rehearsal": null},
  "series": {"minute": [...], "turns": [...], "p95_s_le": [...], "error_rate": [...]}
}
```

`GET /metrics` (Prometheus text, cùng số liệu) chỉ nhận client loopback; Caddy không proxy route này.

### Giao diện

Thẻ "Vận hành hệ thống" trong `/admin`, dưới `AdminOverviewPanel`:

- Hàng ô trạng thái: Sẵn sàng · Lượt 5 phút · p95 · Tỉ lệ lỗi · Quá tải (503) · Nhánh vector · Chi phí hôm nay / trần · Model · Sao lưu.
  Màu theo đúng ngưỡng của A3 (bảng ngưỡng dùng chung, export từ một file).
- Biểu đồ đường 60 phút cho p95 và tỉ lệ lỗi (SVG tự vẽ, không thêm thư viện).
- Làm mới 30 s, dừng khi tab ẩn; trạng thái tải/lỗi/trống bằng `AsyncState`; giờ `Asia/Ho_Chi_Minh`; tiếng Việt.

### Task

| ID | Việc | Kiểm chứng | |
|---|---|---|---|
| A2.1 | `OpsMetrics` + vòng ô phút + histogram + p50/p95 theo mốc | Unit test với đồng hồ giả | ✅ |
| A2.2 | Writer/reader snapshot, ghép worker, bỏ file cũ | Test 2 "worker" giả ghi file, reader cộng đúng; file quá hạn bị bỏ | ✅ |
| A2.3 | Móc chat, admission, 429, watchdog | Test lượt giả qua `TestClient`: bộ đếm tăng đúng loại | ✅ |
| A2.4 | `GET /v1/status` cho sidecar | Test thiếu token → 401; có token → đúng số của `DailySpendCap` | ✅ |
| A2.5 | Thăm dò model, đĩa, trạng thái backup | Test với server giả và thư mục tạm | ✅ |
| A2.6 | `/v1/admin/operations/status` + `/metrics` | Sinh viên/giảng viên 403, admin 200; client không phải loopback bị từ chối ở `/metrics`; snapshot không chứa chuỗi câu hỏi đã gửi | ✅ |
| A2.7 | Panel web + test vitest | `tsc`, vitest | ✅ |
| A2.8 | Chạy tải provider giả 100 × 2 trên cổng thử, chụp dashboard | Số khớp `rag_load_test.py`; overhead ≤ 2 % | ✅ (cổng thử; không dừng 8015 khi chưa báo) |

---

## A3 — Giám sát và cảnh báo chủ động

**Xong khi:** trên mô phỏng Docker/systemd, bốn kịch bản (dừng model, dừng API, chạm trần chi phí giả, khởi động lại) đều
nhận cảnh báo đúng mức trong ≤ 3 phút và RESOLVED khi hồi phục, có log thời điểm.

### Thiết kế

- **Luật là dữ liệu**, khai báo trong `observability/alert_rules.py`:

```python
@dataclass(frozen=True)
class Rule:
    id: str; severity: Literal["warning", "critical"]
    metric: Callable[[dict], float | None]   # đọc từ status của A2; None = thiếu mẫu, không chấm
    op: Literal[">", "<", ">="]; threshold: float
    for_s: int; min_samples: Callable[[dict], bool] = lambda s: True
```

- **Máy trạng thái** mỗi luật: `OK → PENDING (điều kiện đúng) → FIRING (đúng liên tục for_s) → RESOLVED (sai liên tục 2 chu kỳ) → OK`.
  Gửi khi vào FIRING và RESOLVED; nhắc lại mỗi 30 phút khi còn FIRING. Lưu `<state>/ops-alerts/state.json` và
  `history.jsonl` (append) để khởi động lại không gửi trùng.
- **Ai chấm:** chỉ worker đang là leader (`BackgroundLeader`), chu kỳ 60 s, dùng `aggregate()` của A2.
- **Ngoài ứng dụng:** `infra/cloud/watchdog.py` không import ứng dụng. Mỗi phút thăm dò `/health/ready`, gateway `/health`,
  18081/18082, đĩa; báo khi lỗi 3 lần liên tiếp; lưu trạng thái riêng. Unit `campus247-watchdog.timer`; mọi unit thêm
  `OnFailure=campus247-alert@%n.service`, gọi `watchdog.py notify-unit-failed %i`.
- **Kênh** (`infrastructure/notify/`): `AlertNotifierPort.send(alert: AlertMessage) -> None`, adapter `LogNotifier`,
  `TelegramNotifier` (httpx, timeout 5 s, 1 lần thử lại), `SmtpNotifier` (`smtplib`, STARTTLS/TLS bắt buộc). Cấu hình trong `.env`
  (`CAMPUS247_ALERT_TELEGRAM_TOKEN`, `..._CHAT_ID`, `CAMPUS247_ALERT_SMTP_*`), mode 0600. Allowlist host mới
  `CAMPUS247_ALERT_ALLOWED_HOSTS`; adapter từ chối host ngoài danh sách.
- **Nội dung:** `[CRITICAL] Campus 24/7 · Model server không trả lời · reranker down 2 phút · 10:42 17/11`. Chỉ tên luật,
  giá trị, ngưỡng, thời điểm; không dữ liệu người dùng.

### Luật ban đầu (chỉnh sau tuần đầu, bước 2.8 của rollout)

| Luật | Điều kiện | Mức |
|---|---|---|
| `api_not_ready` | `/health/ready` lỗi 3 phút (watchdog ngoài) | critical |
| `model_down` | 18081 hoặc 18082 không trả lời 2 phút | critical |
| `gateway_cap_reached` | gateway từ chối vì `daily_cap` | critical |
| `gateway_cap_near` | ≥ 80 % trần USD hoặc số lời gọi ngày | warning |
| `overload_503` | 503 > 2 % lượt / 5 phút, tối thiểu 20 lượt | warning |
| `turn_errors` | lỗi > 2 % / 10 phút, tối thiểu 20 lượt | warning |
| `slow_p95` | p95 > 15 s / 10 phút (giai đoạn 1 đo 12–13 s) | warning |
| `vector_lost` | `failed_rate` > 5 % / 10 phút, tối thiểu 25 lượt truy hồi | warning |
| `loop_blocked` | lần bị chặn ≥ 3 s | warning |
| `provider_failing` | gateway `failed` > 5 % / 10 phút | warning |
| `disk_low` | còn < 15 % (warning), < 5 % (critical) | warning / critical |
| `backup_stale` | backup gần nhất > 26 giờ, verify lỗi, hoặc offsite lỗi | warning |
| `rehearsal_failed` | diễn tập khôi phục gần nhất lỗi hoặc > 35 ngày | warning |
| `learning_worker_down` | `unavailable` 10 phút | warning |
| `tls_expiring` | chứng chỉ còn < 14 ngày (chỉ cloud) | warning |

### Task

| ID | Việc | Kiểm chứng | |
|---|---|---|---|
| A3.1 | `Rule`, máy trạng thái, lưu trạng thái | Unit test đồng hồ giả: FIRING đúng lúc, thiếu mẫu không chấm, RESOLVED, nhắc lại, không gửi trùng sau restart | ✅ |
| A3.2 | Bộ luật trên + bảng ngưỡng dùng chung với A2 | Test từng luật với snapshot mẫu | ✅ |
| A3.3 | `AlertNotifierPort`, `LogNotifier`, `TelegramNotifier`, `SmtpNotifier`, allowlist host | Test với server HTTP/SMTP giả trong tiến trình | ✅ |
| A3.4 | Chạy luật trong leader | Test: chỉ leader gửi; đổi leader không gửi trùng | ✅ |
| A3.5 | `infra/cloud/watchdog.py`, timer, `campus247-alert@.service`, `OnFailure=` trong `render_units.py` | `systemd-analyze verify`; test script với server giả | ✅ |
| A3.6 | Bốn kịch bản trên mô phỏng Docker/systemd | Log thời điểm cảnh báo và RESOLVED | ✅ (dùng kênh giả) |
| A3.7 | Kênh thật (Telegram/email) | Một tin thử tới chủ dự án | ⏳ chọn kênh + đặt token |
| A3.8 | Watchdog cho máy Windows (Task Scheduler) | — | ⏳ chủ dự án muốn bật hay không |

---

## A4 — Sao lưu ngoài máy và diễn tập khôi phục

**Xong khi:** kịch bản mất VM (xóa container chính, dựng lại từ kho ngoài) khôi phục đạt trong mô phỏng; diễn tập tự động
chạy được và ghi `REHEARSAL.json`; sai mật khẩu kho thì lỗi rõ, không ghi gì ra đĩa.

### Phương án kho ngoài

| Phương án | Lợi | Hại | |
|---|---|---|---|
| **restic** | Mã hóa phía máy, khử trùng lặp, S3/B2/SFTP, một binary | Phải tải binary (ghim sha256) | **Chọn** |
| `age` + `rclone` | Đơn giản từng phần | Hai công cụ, tự lo giữ bản và khử trùng lặp | Dự phòng |
| `rsync` qua SSH, không mã hóa | Không cần công cụ mới | Backup chứa khóa ký và identity; không mã hóa là không chấp nhận được | Không |

### Thiết kế

- **`LAST_BACKUP.json`** do `backup.py backup` ghi trong thư mục `--out` sau mỗi lần:
  `{"stamp", "folder", "bytes", "manifest_sha256", "verified": true|false, "duration_s"}`. Thêm `backup.py status` in file này.
- **`infra/cloud/offsite.py`** bọc restic: `init`, `push --backup <dir>` (gắn tag `daily`, index chỉ vào Chủ nhật với tag `index`),
  `forget` (`--keep-daily 14 --keep-weekly 8 --keep-monthly 6 --prune`), `check --read-data-subset 5%`, ghi `OFFSITE.json`.
  Mật khẩu kho đọc từ `RESTIC_PASSWORD_FILE` (mode 0600), không phải biến môi trường dòng lệnh; không in ra log.
  Binary tải bằng `fetch_runtime_deps.sh` với phiên bản và sha256 ghim.
- **Unit:** `campus247-offsite.service` (`After=campus247-backup.service`; backup gọi `OnSuccess=campus247-offsite.service`).
- **`infra/cloud/rehearse_restore.py`** (mỗi tháng, timer riêng):
  1. lấy bản mới nhất (từ restic nếu đã cấu hình, không thì từ thư mục backup local) vào `/var/tmp/campus247-rehearsal-<stamp>`;
  2. `backup.py verify`;
  3. `backup.py restore` vào root rỗng, database tạm `campus247_rehearsal_<stamp>`;
  4. `compare_restore.py`;
  5. chạy API trên cổng thử với root đó, đợi `/health/ready`;
  6. ghi `REHEARSAL.json`; chỉ xóa thư mục và database tạm do chính lần này tạo, kể cả khi lỗi.
- **Máy Windows (tùy chọn):** Task Scheduler chạy `backup.py backup` hằng ngày sang ổ khác.
- **Khóa:** chủ dự án giữ một bản mật khẩu kho ngoại tuyến. Mất mật khẩu là mất toàn bộ bản sao.

### Task

| ID | Việc | Kiểm chứng | |
|---|---|---|---|
| A4.1 | `LAST_BACKUP.json` + `backup.py status` | Test backup vào thư mục tạm, đọc lại file | ✅ |
| A4.2 | `rehearse_restore.py` dùng backup local | Chạy trên Windows với root tạm; chạy trong mô phỏng Docker | ✅ |
| A4.3 | Timer diễn tập hằng tháng | `systemd-analyze verify` | ✅ |
| A4.4 | `offsite.py` + unit | Test logic với restic giả (script ghi lại tham số) | ✅ |
| A4.5 | Kịch bản mất VM với restic thật, kho SFTP ở container thứ hai | Khôi phục đạt; sai mật khẩu lỗi rõ | ⏳ duyệt tải restic |
| A4.6 | Kho ngoài thật (B2/S3/máy khác) | `offsite.py check` đạt | ⏳ chọn nơi lưu, chi phí, tạo tài khoản |
| A4.7 | Lịch backup trên máy Windows | — | ⏳ chủ dự án muốn bật hay không, ổ đích |

---

## A1 — Đăng nhập SSO (chuẩn bị đầy đủ, chưa nối HUCE)

**Xong khi:** mọi ca dưới đây đạt với IdP giả; tài liệu "điền cấu hình HUCE" liệt kê đúng giá trị trường phải cấp và lệnh
chạy bộ kiểm kết nối. Không khẳng định đã tích hợp HUCE.

### Thiết kế

- **Giao thức:** OIDC Authorization Code + PKCE S256. SAML chỉ làm nếu HUCE chỉ có SAML (cần thư viện và `xmlsec` native → quyết định riêng).
- **Cấu hình** (`OidcConfig`, đọc từ env + một file JSON trong state):

```json
{
  "issuer": "https://idp.example.edu.vn/realms/huce",
  "client_id": "campus247", "client_secret_env": "CAMPUS247_OIDC_CLIENT_SECRET",
  "redirect_uri": "https://chat.example.edu.vn/v1/auth/oidc/callback",
  "scopes": ["openid", "profile", "email"],
  "claims": {"student_code": "student_id", "display_name": "name", "roles": "groups"},
  "role_map": {"sinhvien": "STUDENT", "giangvien": "LECTURER"},
  "student_code_pattern": "^[0-9]{6,10}$",
  "jit_provisioning": false,
  "privileged_subjects": [{"sub": "…", "roles": ["SYSTEM_ADMIN"]}]
}
```

- **Luồng:**
  1. `GET /v1/auth/oidc/start?next=/chat` kiểm `next` là đường dẫn tương đối nội bộ; tạo `state`, `nonce`, `code_verifier`;
     lưu bảng `oidc_login_attempts` (TTL 10 phút, dùng một lần); cookie `oidc_attempt` (id ngẫu nhiên, `HttpOnly`, `SameSite=Lax`,
     `Secure` khi HTTPS); 302 tới `authorization_endpoint`.
  2. `GET /v1/auth/oidc/callback?code&state` tra attempt theo cookie, kiểm `state` khớp và chưa dùng, đánh dấu đã dùng; đổi code
     (httpx, timeout 5 s, host issuer trong allowlist); xác minh ID token; ánh xạ danh tính và vai trò; tạo phiên; 302 tới `next`.
  3. Lỗi bất kỳ → 302 `/login?error=<mã>`, không tạo phiên, log mã lỗi (không log token).
- **Xác minh ID token** (`pyjwt` + `PyJWKClient`, discovery cache 1 giờ, JWKS làm mới khi gặp `kid` lạ, tối đa 1 lần/phút):
  `algorithms=["RS256", "ES256"]`; `iss` khớp tuyệt đối; `aud` chứa `client_id`; kiểm `azp` khi nhiều audience; `exp`, `iat`, `nbf`
  lệch ≤ 60 s; `nonce` khớp.
- **Phiên riêng:** issuer `urn:campus247:issuer:oidc-session`, payload như `LocalOwnerIdentityAdapter.mint_token`, khóa HMAC riêng
  trong state, TTL ≤ 3600 s, `jti` và `session_id` ghi vào kho thu hồi. Không bao giờ dùng ID/access token của IdP làm phiên.
  `LocalCampusIdentityAdapter` thêm nhánh cho issuer này; các kiểm quyền phía sau giữ nguyên.
- **Ánh xạ danh tính:** bảng `oidc_subjects(issuer, sub, subject_id UUIDv7, created_at, last_login_at, disabled)` trong
  `actor-state.sqlite3` (store SQLite, không qua Alembic). Chưa có ánh xạ và `jit_provisioning=false` → từ chối `ACCOUNT_NOT_PROVISIONED`.
- **Vai trò:** `STUDENT`/`LECTURER` từ `role_map`. `STUDENT` bắt buộc có `student_code` khớp mẫu, thiếu thì từ chối.
  `SYSTEM_ADMIN`, `KNOWLEDGE_ADMIN`, `SUPPORT_OFFICER`, `KNOWLEDGE_CONTRIBUTOR` chỉ từ `privileged_subjects`; claim của IdP không bao giờ cấp các vai trò này.
- **Đăng xuất:** thu hồi phiên local; có `end_session_endpoint` thì chuyển tiếp kèm `id_token_hint` (lưu tạm trong attempt, không trong cookie).
  Tài khoản bị khóa phía IdP có hiệu lực ở lần đăng nhập sau; TTL 1 giờ giới hạn thời gian lộ.
- **Cùng tồn tại:** `CAMPUS247_AUTH_PROVIDERS=local,oidc`; `GET /v1/auth/providers` → `{"providers": [{"id": "oidc", "label": "Tài khoản trường"}]}`;
  trang `/login` hiện nút khi có. Tài khoản local, khóa và lịch sử cũ giữ nguyên.
- **Cookie `Secure`:** đặt khi `request.url.scheme == "https"` hoặc `X-Forwarded-Proto: https` từ proxy tin cậy (Caddy trên loopback).
  Áp dụng cho cả đăng nhập local. Ghi rõ trong tài liệu rằng kiểm `client.host` không có tác dụng sau proxy; giữ kiểm `Origin`.

### Task

| ID | Việc | Kiểm chứng | |
|---|---|---|---|
| A1.1 | IdP giả trong tiến trình (khóa RSA từ `cryptography`, discovery/JWKS/token qua `httpx.MockTransport`) | Dùng được trong pytest | ✅ |
| A1.2 | `OidcConfig` + bộ xác minh ID token | Ca âm: sai `iss`, sai `aud`, hết hạn, sai chữ ký, `alg=none`, HS256 ký bằng public key, `nonce` sai, đổi khóa JWKS vẫn đạt | ✅ |
| A1.3 | Bảng attempt + `oidc_subjects` trong actor-state, ánh xạ vai trò | Ca: thiếu mã sinh viên, claim tự khai admin, JIT tắt, tài khoản bị disable | ✅ |
| A1.4 | Route start/callback/logout/providers + phiên riêng + nhánh issuer mới | `state` dùng lại bị từ chối; `next` ngoài domain bị từ chối; IdP timeout không tạo phiên | ✅ |
| A1.5 | Cookie `Secure` theo scheme/proxy | Test có và không có `X-Forwarded-Proto` | ✅ |
| A1.6 | Ca của `HUCE_INTEGRATION_READINESS`: `/me` đúng chủ thể, không truy cập chéo, phiên thu hồi bị từ chối | Test integration | ✅ |
| A1.7 | Nút "Đăng nhập bằng tài khoản trường" + lỗi hiển thị trên `/login` | vitest; Playwright với IdP giả | ✅ |
| A1.8 | Tài liệu "điền cấu hình HUCE" + lệnh kiểm kết nối (`scripts/oidc_preflight.py`: discovery, JWKS, redirect) | Chạy với IdP giả | ✅ |
| A1.9 | Keycloak trong Docker với realm tổng hợp | Đăng nhập đầu-cuối | ⏳ duyệt tải image |
| A1.10 | Nối HUCE thật | Bộ kiểm A1.8 + A1.6 trên môi trường HUCE cấp | ⏳ issuer, client, redirect URI, mô tả claim từ HUCE |

---

## Quyết định cần chủ dự án (nhóm A)

| # | Quyết định | Chặn | Đề xuất |
|---|---|---|---|
| A-D1 | Push nhánh để chạy CI trên GitHub | A5.7 | Push nhánh feature, không merge `main` |
| A-D2 | Ai xem dashboard vận hành | — (mặc định `require_admin`) | Giữ `require_admin` |
| A-D3 | Kênh cảnh báo và ai đặt token | A3.7 | Telegram, email dự phòng |
| A-D4 | Watchdog/backup tự động trên máy Windows | A3.8, A4.7 | Bật backup sang ổ khác; watchdog chưa cần |
| A-D5 | Tải `restic` (ghim sha256) | A4.5 | Đồng ý |
| A-D6 | Nơi lưu ngoài server và chi phí | A4.6 | B2 hoặc S3 tương thích (chưa báo giá) |
| A-D7 | Tải image Keycloak | A1.9 | Tùy chọn; IdP giả đã đủ cho test |
| A-D8 | Bật JIT khi đăng nhập SSO lần đầu | — (mặc định tắt) | Tắt |

## Bằng chứng

Mỗi task ghi lệnh, mã thoát, file kết quả trong `evals/results/group-a-<id>-<stamp>/`; ghi phần chưa đo (người dùng thật, VPS thật,
kênh thật). Không ghi đè bằng chứng cũ.
