# Lệnh và mức kiểm tra

Chạy từ thư mục gốc repo. Python dùng venv: `.venv/Scripts/python.exe` (cờ `-B` để không ghi `__pycache__`).

## Runtime (cổng 8015)

```bash
pnpm start      # = .venv/Scripts/python.exe -B scripts/campus.py start
pnpm build      # chỉ tạo artifact frontend để kiểm, không khởi động bản khác
.venv/Scripts/python.exe -B scripts/campus.py status
```

`start` không đổi cổng, không tắt tiến trình đang chiếm cổng; tiến trình đang chạy được tái dùng, nên mã API/web mới chỉ có hiệu lực sau khi dừng đúng tiến trình đó. Chạy `status` để biết trạng thái thật.

Runtime 8015 gồm: API (`scripts/knowledge_platform.py serve --generation --port 8015 --frontend-port 3015`, proxy luôn cả trang web), frontend là một snapshot build bất biến phục vụ ở 3015 (`scripts/knowledge_platform_frontend.py build --name <tên mới>`), Postgres native `127.0.0.1:55437`, mô hình nhúng local `127.0.0.1:18081`. Lệnh khởi động đầy đủ (RAG v2, chỉ mục đã kiểm định):

```bash
PYTHONPATH=data/rag_v2_vendor infra/local/rag-fixture/.venv/Scripts/python.exe -B -X utf8 scripts/knowledge_platform_runtime.py start --defer-worker --engine v2 --rag-v2-index data/rag_v2_index/embedded2 --frontend-name <snapshot>
```

`PYTHONPATH=data/rag_v2_vendor` cần cho numpy của v2 (venv runtime không có numpy). API nạp chỉ mục khoảng 40 s; sau đó tác vụ làm nóng nguồn chạy nền, `/health/ready` → `rag_v2.warm` = `pending|ready|failed`. Kiểm `rag_v2.enabled: true` sau khi khởi động. `pnpm lint` (tsc) đã kiểm chạy được. Hạ tầng compose (`compose.yaml`: Postgres pgvector 5433, Redis 6380) không phải DB của runtime 8015.

### Thêm tài liệu mới vào kho

Thiết kế: `docs/04-architecture/KNOWLEDGE_AUTO_PUBLICATION_DESIGN_20261116.md`. `pnpm start` bật worker nhập liệu; worker chỉ nhận việc khi RAM trống ≥ 2 GB (thiếu thì chờ). Một lệnh duy nhất cho mọi vai trò: `POST /v1/knowledge/platform/documents` (trang `/knowledge/documents`): `KNOWLEDGE_ADMIN` đăng trực tiếp (tick xác nhận), `KNOWLEDGE_CONTRIBUTOR` gửi duyệt, người duyệt khác tác giả bấm Duyệt một lần. Phần còn lại tự chạy trong worker (`application/knowledge/auto_publication.py`): kiểm tra tự động → gom lô ~30 s → release + xác nhận bởi danh tính dịch vụ `auto-publisher` → dựng chỉ mục (`scripts/refresh_rag_v2_index.py` chạy như tiến trình con, ghi `rag_v2_index_registry`) → mỗi tiến trình API tự nạp nóng chỉ mục mới (`bootstrap/rag_v2.py`: `SwappableRagNode` + `RagV2IndexReloader`, 5 s một lần; tắt bằng `CAMPUS247_RAG_V2_HOT_RELOAD=0`) và báo `rag_v2_index_ack` → trạng thái ACTIVE ("chatbot dùng được từ …"). Trong lúc nạp `/health/ready` trả `snapshot_state: refreshing` (vẫn ready, tối đa 10 phút). Bảng trạng thái tạo idempotent bằng `CREATE TABLE IF NOT EXISTS` (không có migration Alembic vì runtime chỉ chấp nhận vài revision schema). Cấp tài khoản người đóng góp: `scripts/provision_knowledge_contributor.py --identity <owner-identity.json> --username <tên>` (chủ hệ thống chạy; không tự tạo). Bộ cào trang HUCE: `/knowledge/crawl` (chỉ quản trị), nguồn mới mặc định chỉ chạy thử, tuân robots.txt, ~3 s/yêu cầu, loại trang có dữ liệu cá nhân, URL đã có trong kho thì báo `EXISTS` chứ không ghi đè. Kiểm: `KNOWLEDGE_PLATFORM_LIVE_TESTS=1 pytest tests/knowledge_platform --basetemp=<thư mục trong repo>` (tenant riêng trong Postgres local; URL nguồn là duy nhất toàn nền tảng nên test dùng tên miền con ngẫu nhiên).

## Bảng kiểm tra theo loại thay đổi

Chọn dòng gần nhất; chỉ chạy thứ liên quan.

| Thay đổi | Kiểm tra |
|---|---|
| Văn bản, CSS, style nhỏ ở web | `pnpm lint` (tsc), test vitest của file liên quan |
| Component/tính năng web | `pnpm --filter web test` (vitest), `pnpm lint`; xem trên trình duyệt nếu đổi giao diện |
| Luồng người dùng, responsive | Playwright. `apps/web/e2e/*.spec.ts` chưa có config mặc định; `e2e-live/*.pw.ts` dùng `playwright.live.config.ts` (Chrome cục bộ, `baseURL` còn trỏ cổng cũ 3115, cần đổi sang 8015 khi chạy). Cần runtime đang chạy |
| Route/logic API | `.venv/Scripts/python.exe -B -m pytest -q tests/<thư mục liên quan>` |
| Đổi hợp đồng API | Cập nhật `contracts/`, chạy `tests/contract`, `tests/contracts` |
| Đổi import/lớp | `-m pytest -q tests/architecture`. Hiện đã có 1 vi phạm cũ (kiểm 2026-11-25): `presentation/oidc.py` import `infrastructure.identity.oidc*`, nên test này đang đỏ. Đừng gây thêm vi phạm; sửa bằng cách đưa qua `ports` khi đụng tới file đó |
| Migration | Test migration trong `tests/` liên quan; kiểm trên DB tạm, không chạm DB có dữ liệu thật (DB trống cần `CREATE EXTENSION vector` trước `alembic upgrade head`, xem `infra/local/audit-20261125/migration_roundtrip.sh`) |
| OCR native, ClamAV thật | `LEARNING_OCR_NATIVE_HTTP=1 LEARNING_OCR_RUNTIME_DIR=... LEARNING_OCR_FIXTURE_PDF=... LEARNING_TEST_ROOT=... PYTHONPATH=services/worker/src pytest tests/learning_entry/test_accessible_text_http.py tests/learning_entry/test_scan_real_daemon.py` (thiếu `PYTHONPATH` worker thì báo `No module named 'campus247_worker'`) |
| RAG, prompt, guardrail, grounding | Test `tests/evals`, `tests/knowledge_platform`; `evals/validate_contracts.py`; gate trong `evals/gates` |
| Bảo mật, quyền, xác nhận hành động | Test an toàn liên quan (ví dụ `tests/test_safety_rules.py`) và case red-team |
| CI, release | Test tương ứng trong `.github/workflows/ci.yml` (`tests/delivery`, `tests/evals/test_audit_remediation_gate.py`) |

Nguyên tắc: kiểm tra vừa đủ với rủi ro. Thay đổi nhỏ không cần chạy toàn bộ bộ test; thay đổi chạm quyền, dữ liệu, hành động ghi hoặc RAG thì phải có kiểm tra xác định tương ứng.

## Trung thực khi báo xong

Nêu lệnh đã chạy và kết quả. Ghi bằng chứng là gì trong một câu. Ca tổng hợp có đáp án chuẩn kiểm bằng mã là bằng chứng nghiệm thu hợp lệ; mức dùng được với người dùng thật vẫn ghi là chưa đo. Phần chưa chạy, chưa kết nối, hoặc bị chặn phải ghi rõ.
