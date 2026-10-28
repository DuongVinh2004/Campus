# Lệnh và mức kiểm tra

Chạy từ thư mục gốc repo. Python dùng venv: `.venv/Scripts/python.exe` (cờ `-B` để không ghi `__pycache__`).

## Runtime (cổng 8015)

```bash
pnpm start      # = .venv/Scripts/python.exe -B scripts/campus.py start
pnpm build      # chỉ tạo artifact frontend để kiểm, không khởi động bản khác
.venv/Scripts/python.exe -B scripts/campus.py status
```

`start` tự build khi mã đổi, không đổi cổng, không tắt tiến trình đang chiếm cổng. Chạy `status` để biết trạng thái thật; `ConnectError` nghĩa là runtime chưa chạy. `pnpm lint` (tsc) đã kiểm chạy được. Hạ tầng cục bộ: `compose.yaml` (Postgres pgvector 5433, Redis 6380).

## Bảng kiểm tra theo loại thay đổi

Chọn dòng gần nhất; chỉ chạy thứ liên quan.

| Thay đổi | Kiểm tra |
|---|---|
| Văn bản, CSS, style nhỏ ở web | `pnpm lint` (tsc), test vitest của file liên quan |
| Component/tính năng web | `pnpm --filter web test` (vitest), `pnpm lint`; xem trên trình duyệt nếu đổi giao diện |
| Luồng người dùng, responsive | Playwright. `apps/web/e2e/*.spec.ts` chưa có config mặc định; `e2e-live/*.pw.ts` dùng `playwright.live.config.ts` (Chrome cục bộ, `baseURL` còn trỏ cổng cũ 3115, cần đổi sang 8015 khi chạy). Cần runtime đang chạy |
| Route/logic API | `.venv/Scripts/python.exe -B -m pytest -q tests/<thư mục liên quan>` |
| Đổi hợp đồng API | Cập nhật `contracts/`, chạy `tests/contract`, `tests/contracts` |
| Đổi import/lớp | `-m pytest -q tests/architecture`. Hiện đã có 1 vi phạm cũ: `application/knowledge/applicability.py` import `infrastructure.knowledge.repository`, nên test này đang đỏ. Đừng gây thêm vi phạm; sửa bằng cách đưa qua `ports` khi đụng tới file đó |
| Migration | Test migration trong `tests/` liên quan; kiểm trên DB tạm, không chạm DB có dữ liệu thật |
| RAG, prompt, guardrail, grounding | Test `tests/evals`, `tests/knowledge_platform`; `evals/validate_contracts.py`; gate trong `evals/gates` |
| Bảo mật, quyền, xác nhận hành động | Test an toàn liên quan (ví dụ `tests/test_safety_rules.py`) và case red-team |
| CI, release | Test tương ứng trong `.github/workflows/ci.yml` (`tests/delivery`, `tests/evals/test_audit_remediation_gate.py`) |

Nguyên tắc: kiểm tra vừa đủ với rủi ro. Thay đổi nhỏ không cần chạy toàn bộ bộ test; thay đổi chạm quyền, dữ liệu, hành động ghi hoặc RAG thì phải có kiểm tra xác định tương ứng.

## Trung thực khi báo xong

Nêu lệnh đã chạy và kết quả. Test tổng hợp đạt không chứng minh dùng được thật với dữ liệu trường. Phần chưa chạy, chưa kết nối, hoặc bị chặn phải ghi rõ.
