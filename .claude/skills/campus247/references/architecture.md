# Kiến trúc và quy ước

## Backend `services/api/src/campus247`

| Lớp | Vai trò | Không được import |
|---|---|---|
| `domain` | Luật nghiệp vụ thuần, thực thể, chính sách | fastapi, sqlalchemy, langgraph, redis, presentation, infrastructure, bootstrap |
| `application` | Use case điều phối domain qua `ports` | fastapi, presentation, infrastructure, bootstrap |
| `ports` | Giao diện (Protocol) cho thế giới ngoài | — |
| `agent` | LangGraph: state, node, tool, grounding, guardrails, hitl | Chỉ đề xuất; không tự thực thi hành động ghi |
| `presentation` | Route HTTP, schema, ánh xạ lỗi | infrastructure |
| `infrastructure` | Adapter DB, Redis, model, file | presentation |
| `bootstrap` | Lắp ghép phụ thuộc, settings, app | — |
| `observability` | Log, trace, metric (structlog, OpenTelemetry) | — |

Ranh giới được kiểm bằng `tests/architecture/test_import_boundaries.py` theo `tests/architecture/layers.yaml`. Đụng import thì chạy test này.

Nguyên tắc:

- Mô hình chỉ đề xuất. Mã xác định xác thực, phân quyền và thực thi.
- Luật nghiệp vụ ở `domain`/`application`, không ở route, UI, node đồ thị hay adapter.
- Mọi hành động ghi cần: kiểm quyền, xem trước, xác nhận của người dùng, idempotency, audit.
- Đổi API thì cập nhật `contracts/openapi/v1/openapi.yaml` cùng lúc (và JSON Schema/AsyncAPI nếu liên quan); test hợp đồng ở `tests/contract`, `tests/contracts`.
- Ghim phiên bản phụ thuộc (đã ghim trong `pyproject.toml`/`pnpm-lock.yaml`); không đổi ngưỡng test hoặc kết quả mong đợi để cho qua.
- Migration ở `services/api/migrations` (Alembic). Chỉ thêm, không phá dữ liệu có sẵn.
- Không đưa secret, token, dữ liệu cá nhân, prompt ẩn vào code, log hay evidence.

## Chuẩn code (vừa đủ chuyên nghiệp)

- Python: type hint đầy đủ cho API công khai; `ruff` và `mypy` có trong dev deps, chạy trên file đã sửa khi thấy cần. I/O dùng `async`, model dữ liệu dùng Pydantic v2.
- Một hệ phân cấp ngoại lệ nội bộ, ánh xạ sang mã lỗi API nhất quán ở `presentation`; thông báo cho người dùng bằng tiếng Việt, rõ ràng, không lộ chi tiết nội bộ.
- Phân quyền theo vai trò (sinh viên, nhân viên, quản trị) kiểm ở `application/authorization`, không rải trong route hay UI.
- Log có cấu trúc, mang correlation id, không chứa dữ liệu cá nhân hay secret; một lỗi chỉ log một lần.
- Hàm ngắn, tên rõ nghĩa, không lặp lại logic; bình luận chỉ giải thích "vì sao". Thêm test cạnh hành vi mới, ưu tiên fake thay vì mock sâu.
- Commit (khi được yêu cầu): Conventional Commits như lịch sử repo (`feat:`, `fix:`, `chore:`), mỗi commit một ý.
- Quyết định kiến trúc quan trọng ghi ngắn trong `docs/` nếu cần; không bắt buộc.

## Frontend `apps/web`

- App Router trong `src/app`, tính năng trong `src/features/<tên>`, thành phần dùng chung `src/components`, gọi API qua `src/lib/api/client.ts`.
- Token thiết kế ở `src/styles/tokens.css`, nguyên tắc nhận diện ở `apps/web/DESIGN.md`; dùng token, đừng hard-code màu.
- Văn bản giao diện bằng tiếng Việt; trạng thái tải/lỗi/rỗng qua `AsyncState`, `Skeleton`, `Toast`.
- Truy cập: HTML ngữ nghĩa, nhãn, focus, tương phản, hiển thị tốt ở mobile. Có `src/test/accessibility.test.tsx` và `e2e/responsive.spec.ts`.
- Test locator ưu tiên role/label; thêm `data-testid` ổn định khi cần.
