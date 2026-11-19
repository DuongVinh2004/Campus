# Khởi chạy và trình diễn chặng đầu

Đường vào hiện tại: **http://localhost:8002/login**. Giao diện dùng tên và thao tác
dịch vụ thông thường theo yêu cầu bổ sung của người dùng. Mã tài khoản: `SV001`
(sinh viên 1), `SV024` (sinh viên 2), `OF001` (cán bộ hàng đợi HUCE_GENERAL).
Nhập mã và bấm Đăng nhập. Đây vẫn là runtime local với directory/dữ liệu tổng
hợp; thay cách trình bày không kết nối hệ thống trường hoặc mở môi trường production.

## Cấu hình đã kiểm chứng

| Thành phần | Đường chạy |
|---|---|
| UI | Source `apps/web`, build03 ở `infra/local/certificate-stage1-20261013-01/frontend03/acceptance-20261012-58-frontend-repair1-local-repair2`, Next 16.3.8, port 3002 |
| API nghiệp vụ/UI proxy | `scripts/run_certificate_demo.py`, loopback 8002 |
| Persistence | `infra/local/certificate-stage1-20261013-01/demo.sqlite3`; schema additive do SQLiteCertificateRepository khởi tạo |
| RAG | Proxy `/v1/conversations/**` tới public API 8000 đang có; runtime nghiệp vụ không mở Gateway/paid ledger |
| Models | BGE services 18081/18082 đang có, giữ nguyên pin/index/caps |
| Auth | Signed SyntheticIdentityAdapter, actor/role/queue server directory, session jti; revocation hash lưu SQLite |
| Runtime tools | Python `infra/local/rag-fixture/.venv/Scripts/python.exe`; Node bundled trong Codex, dependencies `apps/web/node_modules` |

Nếu hai cổng 8002/3002 đang chạy, dùng URL trên. Không chạy thêm writer hoặc dừng
PID ngoài ownership đã kiểm chứng. Nếu chúng đã dừng, khởi chạy build03 đã có:

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONIOENCODING = 'utf-8'
& 'C:\Users\Duong Vinh\Vinh\infra\local\rag-fixture\.venv\Scripts\python.exe' -B scripts/launch_certificate_demo.py start 03
```

Launcher ghi receipt PID và log mới, từ chối cổng bị chiếm. Giữ mọi database và
artifact cũ. Nếu RAG 8000 chưa chạy, nghiệp vụ vẫn chạy; chat hiển thị lỗi phụ
thuộc. Không tự mở một RAG writer mới hoặc reset ngân sách để chữa lỗi đó.

Cho checkout chưa có namespace này: `scripts/certificate_stage1_workspace.py`
tạo directory/evidence mới; sau đó `prepare_certificate_frontend.py prepare 03`
và `... build 03`, rồi launcher. Các script từ chối ghi đè artifact cũ. Các bản
build dùng guard đã có nguyên byte, không thay safety rules. Không chạy lại build
trên directory đã có `.next`; chọn namespace/attempt mới có phạm vi rõ ràng.

## Kịch bản trình diễn

1. Đăng nhập `SV024`, mở Hỏi đáp AI, hỏi “Xin giấy xác nhận sinh viên bắt đầu từ đâu?”.
2. Mở citation, Mở đoạn nguồn gốc; kiểm trang 35/39 và nội dung nguồn.
3. Bấm Chuẩn bị hồ sơ từ hội thoại. Điền mục đích và nơi nộp; có thể lưu bản nháp.
4. Xem trước hồ sơ. Sửa nếu cần, sau đó Xác nhận gửi hồ sơ. Mã và trạng thái đến từ backend.
5. Đổi tài khoản sang `OF001`, mở Cán bộ, chọn cùng hồ sơ, Tiếp nhận.
6. Ghi yêu cầu bổ sung và bấm Yêu cầu bổ sung.
7. Đăng nhập lại sinh viên, mở hồ sơ, sửa thông tin, nhập nội dung, Xác nhận gửi bổ sung.
8. Cán bộ tiếp nhận lại, ghi lý do rồi Duyệt và cấp giấy xác nhận hoặc Từ chối có lý do.
9. Sinh viên mở hồ sơ, lịch sử xử lý, Xem kết quả. Reload vẫn đọc cùng dữ liệu.

Hồ sơ đã kiểm từ chat trên build03:
`01a1350b-8854-718f-8a37-47c544049501`, chủ `SV024`, trạng thái READY.
Hồ sơ kiểm luồng bổ sung trước đó:
`01a134f1-4c47-7667-b5a6-95d7c9f9e51f`, chủ `SV001`, READY, tám event.
Giữ chúng làm bằng chứng; tạo hồ sơ mới nếu muốn trình diễn lại.

Tệp đính kèm trong phạm vi này là tối đa ba tệp `.txt` chứa nội dung tổng hợp,
16 KB/tệp, lưu cả nội dung trong backend; chưa có upload PDF/ảnh hoặc malware scanning.
Kết quả là HTML có thể xem trong iframe sandbox, chưa có chữ ký số/email/giao nhận thật.

## Hợp đồng thực tế

| Endpoint | Dữ liệu / quyền |
|---|---|
| POST `/v1/auth/demo-login` | `{account}`; server chọn directory identity, trả signed token và user |
| GET `/v1/users/me`, POST `/v1/auth/logout` | Actor từ signed session; logout lưu revocation hash |
| POST `/v1/document-requests/drafts` | `{form, document_id?, expected_version?}`; sinh viên chủ hồ sơ |
| POST/GET `/{id}/preview` dưới `/v1/document-requests` | Tạo/tiếp tục preview, TTL 300s, cùng actor/session |
| POST `/{id}/confirm` | `{preview_id, confirmation_token, idempotency_key, form}`; payload hash/consume/replay trong transaction |
| GET `/v1/document-requests`, GET `/{id}` | Chỉ hồ sơ của sinh viên; cursor offset + limit |
| GET `/v1/staff/document-requests`, GET `/{id}` | SUPPORT_OFFICER được grant HUCE_GENERAL; không thấy draft/pending |
| POST `/v1/staff/document-requests/{id}/{action}` | accept/request_supplement/approve/reject; expected_version, idempotency_key, note |
| POST `/v1/document-requests/{id}/supplement` | Chủ hồ sơ WAITING_STUDENT, expected_version/key/note/form |
| GET `/v1/document-requests/{id}/result` | Chủ hồ sơ hoặc cán bộ đúng queue; phải có result |
| POST `/v1/document-assistant` | `{message}` → intent/missing_fields/proposal; không tự gửi hồ sơ |
| GET `/v1/certificate-guidance` và `/sources/{id}` | Nguồn snapshot công khai, locator/hash; không bịa phí/SLA |

Form: purpose, recipient, quantity 1–3, delivery_method DIGITAL/PICKUP,
attachments `{name,content}`. Profile/name/code/program đến từ backend.
Các envelope và form không nhận actor/role/owner/status từ client. Lỗi RFC 9457;
stale state/idempotency conflict trả 409, ownership bị che bằng 404.

Chuỗi trạng thái: DRAFT → PENDING_CONFIRMATION → SUBMITTED → VALIDATING →
PROCESSING → READY. Nhánh bổ sung: VALIDATING/PROCESSING → WAITING_STUDENT →
SUBMITTED; cán bộ tiếp nhận lại. Nhánh từ chối: VALIDATING/PROCESSING → REJECTED.
Domain giữ các trạng thái/model cũ; chỉ thêm WAITING_STUDENT và các transition
chuyên biệt. SQLite transaction ghi state, replay và audit cùng lúc; version CAS
chặn hai quyết định trên cùng snapshot. Chưa nối LangGraph checkpointer: recovery
được chứng minh qua draft/preview/service bền vững, không gọi là graph recovery.

## Kiểm thử và baseline

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
& 'C:\Users\Duong Vinh\Vinh\infra\local\rag-fixture\.venv\Scripts\python.exe' -B -m pytest -q -p pytest_asyncio.plugin -p no:cacheprovider tests/api/test_certificate_stage1.py --basetemp='C:\Users\Duong Vinh\Vinh\infra\local\certificate-stage1-20261013-01\pytest-user-01' --junitxml='C:\Users\Duong Vinh\Vinh\infra\local\certificate-stage1-20261013-01\backend-user-01.xml'
```

Chỉ dùng basetemp/output chưa tồn tại: pytest có thể dọn basetemp nếu tái sử dụng.
`verify_certificate_restart.py` đã chạy tiến trình thật trên 8003 với database
riêng; script từ chối chạy lại trên artifact đã tồn tại để giữ evidence.

Frontend: từ `apps/web` dùng Node bundled chạy `node_modules/vitest/vitest.mjs run`
các test CertificateWorkspace/chat/history/AppShell, `--no-cache` và report mới.
Sandbox Windows có thể từ chối realpath/socket; lần kiểm đã dùng ngữ cảnh có
quyền phù hợp, không thay ACL hoặc security policy của máy.

Baseline: `scripts/evaluate_certificate_rag.py retrieval --output <file-mới>`.
Không gọi generation. Bộ 48 ca và rubric nằm trong `evals/`. Generation chỉ chạy
khi writer hiện tại và ngân sách/caps được kiểm; đọc số liệu hiện có trước khi
chọn ít ca bằng `--only`. Sau phép kiểm này chỉ còn ít provider/native calls,
không chạy lại toàn bộ live suite và không nâng/reset cap. Xem báo cáo bàn giao.
