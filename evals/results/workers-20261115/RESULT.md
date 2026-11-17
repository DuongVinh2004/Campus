# Bước 1.8: nhiều tiến trình API (2026-11-15)

`scripts/knowledge_platform.py serve --workers N` chạy N tiến trình API dùng chung cổng 8015 bằng chế độ nhiều worker của uvicorn.
Ứng dụng được dựng trong vòng lặp sự kiện của từng worker lúc lifespan startup (`DeferredApp` và `worker_app`), vì `make_app` là coroutine mở pool database.
Launcher nhận `--workers` từ hồ sơ (1 đến 4); hồ sơ `local` nay là **2 worker**.

## Điều kiện đã làm (từ kiểm kê 1.4)

- Luồng xem trước và xác nhận hành động ghi: preview, siêu dữ liệu, dấu "đã dùng" trong `write-previews.sqlite3` dùng chung; khóa ký dẫn xuất từ một bí mật chung.
  Test với tiến trình thật: preview tạo ở tiến trình A được xác nhận đúng một lần ở B; 4 tiến trình xác nhận cùng lúc chỉ 1 thắng; khóa khác, preview lạ, preview bị sửa đều bị từ chối.
- Khóa ký token xác nhận của nền tảng tri thức: trước là chuỗi mặc định cố định, nay là một bí mật ngẫu nhiên bền dùng chung.
- `LogoutService` và `bookings._room_locks`: đã kiểm, không ảnh hưởng đường 8015.

## Đo (tải giả, provider giả, máy này; 100 người, nghĩ 0–1 s, 4 câu mỗi người, K=12 mỗi worker)

| | Lượt phục vụ mỗi phút | p50 / tối đa | CPU API (p50 / p95) |
|---|---|---|---|
| 1 worker | 69,0 | 11,5 / 18,3 s | 92 / 110 % |
| **2 worker** | **125,4** | 13,0 / 19,5 s | 191 / 248 % |

Tỉ lệ **1,82 lần** (tiêu chí ≥ 1,8 lần), không lượt nào quá 22 s. Lượt phục vụ = lượt hoàn tất, không tính lượt bỏ cuộc sau 3 lần bị báo bận.

Tải thực tế 100 người, nghĩ 8–25 s, 3 câu (2 worker, so với 1 tiến trình ở bước 1.7): tỉ lệ thành công 96,7 % (trước 77,3 %), bỏ cuộc 9 lượt (trước 68),
lượt chạy p50 12,2 s và tối đa 17,5 s, 503 tối đa 4,8 s. Ở 50 người: không lượt nào bị báo bận, p50 6,5 s (trước 8,9 s).
`vector_failed` vẫn 37–40 % ở tải này: nghẽn embedding là việc của bước 1.9.

## Chịu lỗi

Giết worker đang là leader việc nền: uvicorn khởi động worker thay thế, worker còn lại nhận khóa leader (`leader_acquired`), `/health/ready` vẫn sẵn sàng và một lượt chat vẫn trả lời.
Một worker chuẩn bị bị giết không làm mất lượt đang chạy ở worker kia.

## Lưu ý

- `/health/entry` do worker nhận yêu cầu trả lời, nên có thể hiện `learning.worker: standby` khi rơi vào worker không phải leader.
- Dừng API phải dừng cả tiến trình cha và các worker con (worker con không chứa `knowledge_platform.py serve` trong dòng lệnh); dừng chỉ tiến trình cha để lại worker mồ côi giữ cổng.
- Mỗi worker dựng chỉ mục xác thực riêng lần đầu (cache theo nội dung); RAM mỗi worker khoảng 480–530 MB RSS khi tải (ước tính hồ sơ giữ 870 MB).
- Số liệu có sự cạnh tranh CPU của máy này (embedding, Postgres, sidecar và máy sinh tải chạy chung 6 lõi); VPS thật sẽ khác (bước 2.3).
