# Kiểm kê trạng thái dùng chung giữa các tiến trình API (bước 1.4, 2026-11-15)

Mục đích: trước khi chạy nhiều tiến trình API (bước 1.8) phải biết cái gì đang nằm trong bộ nhớ của từng tiến trình và cái gì nằm trong file/DB dùng chung.
Phương pháp: đọc mã (`services/api/src/campus247`, `scripts/knowledge_platform.py`), xem các file DB của runtime 8015, và chạy test ghi đồng thời từ 3 tiến trình thật
(`tests/integration/test_sqlite_multiprocess.py`). Phạm vi: đường chạy của runtime 8015. Các kho chỉ có trong đường fixture/demo ghi riêng ở mục 1.

## 1. Kho SQLite

Runtime 8015 hiện có 4 file: `conversations`, `actor-state`, `campus-ops`, `action-idempotency`.

| Kho | Dùng ở 8015 | Chế độ journal hiện tại | Chờ khóa | Test 3 tiến trình ghi đồng thời | Kết luận |
|---|---|---|---|---|---|
| Hội thoại (`sqlite_conversations`) | Có, mỗi lượt ghi | `delete` (mặc định), file 130 MB | 2 s | Đạt: 3 người ghi + 1 người đọc, 120 hội thoại và 120 tin, không lỗi, không trùng số thứ tự. Thử thêm 6 tiến trình × 150 lượt (900 lượt, khoảng 40 lượt/s): 0 lỗi | **Giữ nguyên.** Chịu tải gấp khoảng 9 lần nhu cầu 100 người (khoảng 4,5 lượt/s). Không chuyển sang WAL vì đổi định dạng file 130 MB đang chạy mà chưa có lỗi nào |
| Trạng thái người dùng (`sqlite_actor_state`) | Có (tùy chọn, cả thu hồi phiên, đồng ý, phản hồi) | `delete` | 2 s | Đạt: 120 khóa riêng không mất; khóa tranh chấp mỗi phiên bản có đúng 1 người thắng, người thua nhận `StorageConflict` | Giữ nguyên |
| Idempotency (`application/action/idempotency`) | Có | WAL | 30 s | **Lỗi trước khi sửa**: 3 tiến trình khởi động cùng lúc trên file mới, một tiến trình chết với `database is locked` ở `PRAGMA journal_mode = WAL` (SQLite không chờ khóa cho lệnh này). Sau sửa đạt: mỗi khóa dùng chung có đúng 1 người tạo | **Đã sửa** (retry và bỏ qua khi đã là WAL) |
| Audit (`infrastructure/audit/writer`) | Có | WAL | 5 s | Cùng mẫu lỗi như trên (cùng dòng lệnh) | **Đã sửa** bằng cùng cách |
| Vận hành trường (`sqlite_campus_ops`) | Có | WAL | 15 s | Cùng mẫu lỗi như trên (cùng dòng lệnh) | **Đã sửa** bằng cùng cách. Test ghi đồng thời riêng chưa viết (cần dựng danh tính) |
| Học liệu (`infrastructure/learning/repository`) | Đường riêng của học liệu | không đặt | 15 s | Chưa test | Chưa kiểm; ghi lại |
| Agent runs, assistant memory, certificates, policy graph, service operations, held history | Không có trong runtime 8015 (chỉ trong script fixture/demo) | không đặt | 2–5 s | Chưa test | Kiểm trước khi bật ở runtime nào dùng nó |

WAL tự lưu trong file nên chỉ cần đặt một lần; các lần mở sau chỉ đọc chế độ. Sao lưu dùng API `backup()` của SQLite (an toàn với WAL).

## 2. Trạng thái trong bộ nhớ của từng tiến trình

| Trạng thái | Vị trí | Loại | Khi có nhiều tiến trình | Phân loại |
|---|---|---|---|---|
| Rate limit theo tài khoản | `presentation/middleware/abuse_limits.InMemoryRateLimiterStore` | Bộ đếm | Mỗi tiến trình đếm riêng: giới hạn 30/phút thành 30 × N | **Phải dùng chung** (bước 1.5, **đã làm**: `PostgresRateLimiterStore`, chọn bằng `CAMPUS247_RATE_LIMIT_STORE=postgres`) |
| Điểm kiểm tra liên kết nguồn, quét injection | `agent/nodes/rag_v2._BOUND`, `_HAYSTACKS`, `_prepared` | Cache theo nội dung (khóa bằng băm) | Mỗi tiến trình giữ bản riêng | An toàn (chỉ tốn RAM) |
| Cache xác nhận publication 30 s | `infrastructure/knowledge/publication._attachment_cache`, `_version_cache`, `_acquisition_cache` | Cache có TTL, khóa bằng mtime/băm | Như trên | An toàn |
| Cache chuẩn hóa chữ, follow-up, source snapshot | `lru_cache` ở `values`, `followup`, `source_snapshot` | Hàm thuần | Như trên | An toàn |
| Tiêu đề đã fold, nhóm hàng xóm | `rag_v2/retrieval/hybrid._FOLDED_TITLES`, `neighbors._GROUPS` | Cache thuần | Như trên | An toàn |
| Khóa phòng khi đặt phòng | `infrastructure/repositories/bookings._room_locks` | Khóa luồng | Chỉ khóa trong 1 tiến trình | Cần xem: chỉ an toàn nếu việc đặt phòng chống trùng ở mức DB. `campus_ops` có `BEGIN IMMEDIATE` nên đường 8015 an toàn; `bookings.py` chưa kiểm |
| Thu hồi phiên | `app.py` → `auxiliary_repositories(actor_state_store)` | Kho bền (SQLite actor-state) ở đường 8015 | Dùng chung qua file | An toàn ở 8015. Cần kiểm: `LogoutService(revocation_store=InMemoryRevocationStore())` (`app.py:354`) vẫn là kho trong bộ nhớ |
| Xem trước và xác nhận hành động ghi | `agent/tools/write_flow`: `_PREVIEW_BINDINGS`, `_PREVIEW_METADATA`, `_CONSUMED_PREVIEWS`, **`_CONFIRMATION_SIGNING_KEY = secrets.token_bytes(32)` sinh lại mỗi tiến trình** | Trạng thái bảo mật | Nếu bước xem trước ở tiến trình A mà xác nhận rơi vào tiến trình B thì chữ ký và dấu xem trước không khớp. Hệ thống **từ chối (an toàn)**, không bỏ qua kiểm tra; hậu quả là xác nhận hợp lệ bị từ chối, và tập "đã dùng" không chung nên không có bảo đảm dùng một lần giữa các tiến trình | **Phải dùng chung trước khi bật nhiều tiến trình cho luồng ghi** (khóa ký đọc từ bí mật chung, preview và đã-dùng lưu trong kho bền). Ghi vào điều kiện của bước 1.8 |

## 3. Việc đã làm và việc còn lại

Đã làm (bước 1.4): helper `enable_wal` (retry khi khóa, bỏ qua khi đã WAL) cho idempotency, audit, campus-ops; test ghi đồng thời 3 tiến trình cho hội thoại, trạng thái người dùng và idempotency.

Còn lại, đã đưa vào điều kiện các bước sau:
- 1.5: rate limit dùng chung (Postgres).
- 1.8 (điều kiện để bật >1 tiến trình): luồng xem trước/xác nhận hành động ghi dùng chung (khóa ký và dấu "đã dùng"); kiểm `LogoutService` và `bookings._room_locks`.
- Trước khi dùng ở runtime nào: test đồng thời cho học liệu và các kho chỉ có ở đường fixture.
