# Số đo mốc trước giai đoạn 1 (bước 1.0, 2026-11-15)

Mục đích: có số liệu "trước" để so với "sau" ở các bước 1.2–1.13 của
[ROLLOUT_PLAN_LOCAL_THEN_CLOUD_20261115.md](../../../docs/04-architecture/ROLLOUT_PLAN_LOCAL_THEN_CLOUD_20261115.md).

Cách đo: tải giả bằng `evals/runners/rag_load_test.py` với provider giả (`evals/load/fake_provider.py`, độ trễ lấy từ ledger thật),
nên không tốn lời gọi trả phí. Mỗi học sinh ảo nghĩ 8–25 s giữa hai câu. Đo bằng 1 tiến trình API.

Bằng chứng: các file kết quả có sẵn trong `evals/results/rag-load/` (đo sáng 2026-11-15). Bước 1.0 **không chạy lại** tải giả,
vì làm vậy phải dừng runtime 8015 đang chạy. Chỉ có 1 file nguồn sửa sau lần đo: `infrastructure/knowledge/runtime.py`
(09:29, sau lần đo 09:24; là phần memo xác nhận publication 30 s). Nếu cần số chính xác cho file đó, đo lại ở bước 1.2 khi đã phải khởi động lại runtime.

## Máy này

| Mục | Giá trị |
|---|---|
| CPU | i7-10850H, 6 lõi / 12 luồng |
| RAM | 15,6 GB tổng, khoảng 3,8 GB trống lúc ghi mốc (runtime 8015 đang chạy) |
| Runtime | 1 tiến trình API (cổng 8015), frontend 3015, máy chủ mô hình riêng, Postgres native 55437 |

## Tải giả, 1 tiến trình API

| Người dùng cùng lúc | Câu hỏi/người | Thành công | p50 | p95 | Lượt/phút | CPU API p50 / p95 | RSS API tối đa | File |
|---|---|---|---|---|---|---|---|---|
| 50 | 4 | 100 % | 6,57 s | 11,14 s | 87,4 | 71 % / 138 % | 643 MB | `fake-system-50.json` |
| 100 | 3 | 93 % (21 lượt `system_error`) | 24,42 s | 35,65 s | 111,6 | 102 % / 128 % | 623 MB | `fake9-100real.json` |

Đọc số: một tiến trình chạm trần khoảng 1 lõi, khoảng 111 lượt/phút. 100 người với thời gian nghĩ 8–25 s cần khoảng 267 lượt/phút,
nên hàng đợi dài và các lượt lỗi là lượt quá hạn 32–43 s. Đây là mốc để các bước 1.2 (admission control) và 1.8–1.9 (nhiều worker, giảm CPU) cải thiện.

## CPU mỗi lượt (từ các lần đo trước, ghi trong memory dự án)

| Thành phần | CPU mỗi lượt |
|---|---|
| API | 0,45 s |
| Máy chủ embedding (khóa chung, chạy tuần tự, p50 157 ms mỗi lần embed) | 0,63 s |
| Postgres | 0,11 s |
| **Tổng** | **khoảng 1,19 s** |

## Bộ test hiện có

Lệnh (chạy từ gốc repo, thư mục tạm nằm trong workspace):

```bash
.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider --basetemp=.pytest-tmp-P1-0-20261115 \
  tests/api tests/evals tests/knowledge_platform tests/architecture
```

Kết quả (`pytest.log`, mã thoát 1): **1255 đạt, 41 bỏ qua, 1 lỗi**, 198,8 s.

Lỗi duy nhất: `tests/architecture/test_import_boundaries.py::test_import_boundaries_enforced`. Test dừng ở vi phạm đầu tiên nó gặp:
`application/learning/service.py` import `campus247.infrastructure.learning.metrics` (thư mục `application/learning` và `infrastructure/learning`
chưa được git theo dõi, là phần việc có từ trước). Skill dự án cũng ghi một vi phạm cũ khác ở `application/knowledge/applicability.py`.
Đây là lỗi có sẵn trước giai đoạn 1; giai đoạn 1 không được thêm vi phạm mới. Chưa sửa vì ngoài phạm vi 1.0.

Các thư mục còn lại của `tests/` cũng đã chạy (`pytest-rest.log`, `pytest-rest2.log`):

| Nhóm | Kết quả |
|---|---|
| `tests/contract`, `contracts`, `chaos`, `campus_ops`, `integration`, `delivery` | 573 đạt, 6 bỏ qua, **8 lỗi** |
| `tests/rag_v2`, `unit`, `worker`, `security`, `platform`, `performance`, `load`, `operations`, `release`, `pilot`, `learning_*`, `unified_*`, `test_*.py` | 2989 đạt, 43 lỗi, 60 lỗi dựng fixture |
| **`tests/rag_v2` (đường RAG chính)** | **không có lỗi nào** |

Toàn bộ danh sách 112 mục lỗi/dựng fixture nằm trong `baseline-failures.txt`; các bước sau chỉ được **không thêm** mục nào ngoài danh sách này.
Nguyên nhân quan sát được (chưa sửa, ngoài phạm vi 1.0):

- 35 lỗi `unit/learning`: thiếu biến môi trường `LEARNING_TEST_ROOT`.
- 28 lỗi dựng fixture `operations/test_runtime_audit_fixes.py`: "exclusive registered fixture required"; thêm 32 lỗi dựng fixture ở `unified_final` (`SimpleNamespace` không có `fetchval`).
- 2 lỗi `contracts/test_openapi.py` (lỗi kiểu dữ liệu trong chính test, chạy lại riêng vẫn lỗi) và 2 lỗi `integration/test_unified_staff12.py` hai tiến trình CAS (quá hạn, chạy lại riêng vẫn lỗi).
- 2 lỗi guard di trú ("migration source changed or unreviewed") và 2 lỗi hai tiến trình CAS ở `test_unified_storage_completion.py`.
- 1 lỗi `tests/architecture` (đã nêu ở trên) và các lỗi lẻ ở `unified_*`, `learning_entry`, `dependency_resolution`.

Không có lỗi nào nằm trong đường RAG, cổng chất lượng hay tải; nhưng đây là phiên bản chưa commit nên cũng chưa biết lỗi nào có từ trước commit `2747cab`.

Chưa chạy: test web (vitest/playwright), vì bước 1.0 không đụng tới `apps/web`.

## Chưa đo trong mốc này

- Hành vi người dùng thật; hiệu năng VPS; giới hạn tốc độ của provider.
- Tải giả kịch bản A với câu hỏi không lặp (sẽ đo ở bước 1.9).
