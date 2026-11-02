# W6 — script runtime 8015: L-23, L-15 (proxy font), L-10 (phía máy chủ), L-19, L-13 (API danh sách hội thoại)

Đọc `W0-common.md` (quy tắc chung; đây chủ yếu là việc Python). Mã phiên W6.

Sở hữu: `scripts/knowledge_platform.py`, `scripts/knowledge_platform_runtime.py`, `services/api/src/campus247/infrastructure/identity/local_student.py`, tệp test mới `tests/operations/test_runtime_audit_fixes.py`. Cả ba tệp mã là việc dở chưa được git theo dõi: chỉ đổi đúng chỗ cần. Đọc không sửa: `services/api/src/campus247/presentation/assistant_state.py`, `application/conversation/catalog.py`, `bootstrap/assistant_features.py`, `tests/operations/test_knowledge_platform_runtime.py`. Tuyệt đối không mở/in `infra/local/**/*credentials*`, `student-identity.json`, `bootstrap-password.txt`.

## Việc
1. **L-23.** `knowledge_platform_runtime.py start` hiện không bật RAG v2: API chạy v1 mà không báo gì nếu thiếu biến môi trường `CAMPUS247_RAG_ENGINE=v2` và `CAMPUS247_RAG_V2_INDEX=data/rag_v2_index/embedded2`.
   - Thêm tham số rõ ràng `--engine {v1,v2}` (mặc định v2) và `--rag-v2-index` (mặc định `data/rag_v2_index/embedded2`), truyền vào môi trường tiến trình API được khởi động. Ghi engine/index vào receipt.
   - Khi tái dùng API đang chạy mà `/health/ready` cho thấy engine khác yêu cầu (`rag_v2.enabled` sai), báo rõ thay vì coi là sẵn sàng.
   - Kiểm sẵn sàng hiện hết hạn trước khi API nạp xong chỉ mục (~40 s) và in "Readiness failed: ConnectError" dù API vẫn lên. Chờ có giới hạn (ví dụ tới 180 s, thăm dò định kỳ) trước khi kết luận.
2. **L-15.** Proxy frontend trong `knowledge_platform.py` (hàm `frontend`, danh sách `page_path` cho phép) trả 404 cho `/fonts/inter-*.woff2`, nên chữ rơi về font serif. Cho phép đường dẫn tài nguyên tĩnh `fonts/` (chỉ GET, giữ chặn `..` và `\`, giữ giới hạn kích thước), và các tài nguyên tĩnh khác mà build thật cần (xem `apps/web/public`). Không mở thêm trang nào.
3. **L-10 (phía máy chủ).** `POST /v1/knowledge/platform/session` trả token trong JSON (`{"token": ...}`), nên web lưu token vào `localStorage`. Bỏ `token` khỏi thân phản hồi; cookie `auth_token` (HttpOnly, SameSite=Strict, max_age 3600) là kênh duy nhất. Các trường khác giữ nguyên. Phiên W7 đang sửa web để không cần token này.
4. **L-19.**
   - Tắt `/docs`, `/redoc`, `/openapi.json` ở app vận hành 8015 (vẫn giữ cho test/dev nếu nơi khác cần).
   - Bộ giới hạn đăng nhập trong `local_student.py` (5 lần/60 s, dùng chung cho mọi người) phải khóa theo tên đăng nhập, không theo toàn cục. Lần thử với tên khác không làm khóa student-local.
5. **L-13 (API).** Giao diện không có danh sách lịch sử, vì runtime 8015 không gắn route danh mục hội thoại.
   - Trong app vận hành, gắn route chỉ-đọc `GET /v1/assistant/conversations?limit=&cursor=&title=` trả đúng dạng của `ConversationCatalogService.page` (`items[]` có `id`, `title`, `updated_at`, `created_at`, `mode`, `can_continue`, `retention_state`…, và `page`), chỉ hội thoại của chính sinh viên, bỏ hội thoại `temporary`.
   - Dùng lại `ConversationCatalogService` nếu dựng được với store/khóa hiện có của runtime; nếu không, viết một route chỉ-đọc tối thiểu dùng `conversation_repository.list_owned_conversations`, cùng dạng phản hồi.
   - Không gắn các route ghi (`:preview`, `:confirm`). Middleware `operational_boundary` đã cho phép tiền tố `/v1/assistant/`.
   - Phiên W7 sẽ gọi route này.
6. **Test** (`tests/operations/test_runtime_audit_fixes.py`, không mạng, không chạy runtime thật; dùng `TestClient`/giả lập như các test vận hành sẵn có): engine/index truyền xuống tiến trình; proxy cho `fonts/` nhưng vẫn chặn `..`; login không còn `token` trong JSON và vẫn đặt cookie; `/openapi.json` 404 ở app vận hành; giới hạn đăng nhập theo tên; danh sách hội thoại chỉ trả của chủ sở hữu, bỏ `temporary`, sinh viên khác không thấy, ẩn danh 401. Chạy thêm `tests/operations` và báo trước/sau.
