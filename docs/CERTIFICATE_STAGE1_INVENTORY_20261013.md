# Chặng đầu — kiểm kê trước triển khai (13/10/2026)

Workspace: `C:/Users/Duong Vinh/Vinh`, kiểm tra bằng Resolve-Path và Git. Có nhiều
thay đổi tracked/untracked và sáu file tài liệu đã deleted từ trước; giữ nguyên.
Không commit/push, không sửa archive, corpus, index hoặc bằng chứng lịch sử.

| Thành phần | Trạng thái | Bằng chứng đọc trực tiếp | Khoảng trống / bước tiếp |
|---|---|---|---|
| Login / actor | Cần tích hợp | `presentation/identity.py`, signed SyntheticIdentityAdapter | Frontend login gọi `/api/v1/auth/demo-login`, backend có `/v1/auth/demo-session`; shell tự đổi về sinh viên. Nối account demo server và session/queue binding |
| Gateway frontend | Cần tích hợp | `lib/data/api/api-gateway.ts`, `lib/api/client.ts` | Nhiều UnsupportedOperationError, các trang API riêng không dùng store thống nhất. Tạo gateway hồ sơ theo contract thật |
| API hồ sơ | Chưa triển khai mutation | `presentation/document_requests.py` | Chỉ list/get từ dict, student-only; cần drafts/preview/confirm/staff/supplement/result |
| Persistence | Cần tích hợp | `repositories/composition.py`, `ticket/confirm.py` | Dict confirmation khác dict query, không restart-safe. Tái sử dụng hướng SQLite local như conversation, port transaction riêng; không mở PG chưa rõ ownership |
| Confirmation / retry | Cần tích hợp | `domain/action/{preview,confirmation}.py` | Token validation chưa so session/conversation/version; ledger ticket local memory; cần transaction và consume một lần |
| Cán bộ | Chưa triển khai hồ sơ này | `app/staff/page.tsx` đọc handovers | Nối hàng đợi document requests, reason, CAS và quyền queue |
| Chat/citation/history | Đã có, cần kiểm thực tế | `run_public_rag.py`, SQLiteConversationRepository, source router | Runtime public riêng giữ ledger; hồ sơ cần panel chuẩn bị qua service, không gửi tự động |
| Checkpoint | Chưa nối bootstrap | `agent/graph.py` có checkpointer optional; bootstrap không truyền | Chặng này dùng draft/preview bền vững để tiếp tục an toàn; không tuyên bố LangGraph recovery |
| Khởi chạy/test | Cần kiểm | pytest/vitest và prepare_public_rag_frontend | Build bản mới trong namespace riêng, giữ guard. Runtime hồ sơ không khởi tạo gateway paid |

Quan sát Windows chỉ đọc: public API 8000 (PID 21172), frontend 3000 (1108),
frontend advanced 3001 (17624), BGE 18081/18082 (20376). Không thấy listener
8001 hoặc PostgreSQL 5432/5433 trong lần kiểm này. Không dừng các tiến trình.
Sandbox không đọc được CIM; đã kiểm lại với quyền chỉ đọc ngoài sandbox.

Backlog theo phụ thuộc:
1. Domain/hợp đồng giấy xác nhận, port transaction và SQLite additive; kiểm state/CAS/auth/consume/restart.
2. Application service + router + demo identity; kiểm API trên database mới.
3. Gateway và UI sinh viên/cán bộ + panel chat; kiểm lỗi/retry cùng dữ liệu.
4. Bộ phát triển 40–60 ca/rubric/runner; đo retrieval thật và live generation có giới hạn ngân sách.
5. Build/browser/restart evidence + hướng dẫn chạy/demo và báo cáo giới hạn.

Nguồn nghiệp vụ: snapshot sổ tay HUCE 2026–2027 trang 35 và 39. Publication/PDF
web chưa tải được bằng web tool ở lần kiểm đầu; không coi snapshot là xác nhận
hiệu lực chính sách thực tế. Form mục đích, nơi nộp, số lượng và giao nhận số là
cấu hình mô phỏng; không suy ra phí/SLA hay bắt buộc CCCD/ảnh từ giao diện cũ.
