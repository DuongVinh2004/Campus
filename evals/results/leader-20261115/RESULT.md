# Bước 1.6: leader cho việc nền (2026-11-15)

`BackgroundLeader` (`infrastructure/leader.py`): mỗi tiến trình API chạy một vòng bầu chọn; tiến trình giữ khóa advisory session `pg_try_advisory_lock(727002)`
chạy scheduler, learning worker và OCR, các tiến trình khác chờ ở chế độ standby (`learning_worker_status = "standby"`) và thử lại mỗi 5 s.
Khóa thuộc phiên database nên chính database nhả khóa khi tiến trình chết hoặc kết nối đứt. Leader kiểm tra phiên của mình mỗi 2 s và dừng việc nền ngay khi mất phiên;
việc nền chết bất ngờ thì leader nhả khóa và vòng lặp chạy lại việc (một tiến trình khác có thể nhận khóa trước).
Nối vào `owned_lifespan` của `scripts/knowledge_platform.py`. Không đổi hành vi khi chỉ có 1 tiến trình.

| Kiểm chứng (Postgres thật, mỗi "tiến trình" có pool riêng, khóa ngẫu nhiên cho mỗi test) | Kết quả |
|---|---|
| 3 tiến trình: việc nền chạy ở đúng 1 nơi, các nơi khác không giành lại khi leader khỏe | đạt (số việc chạy đồng thời tối đa = 2 của một tiến trình) |
| Leader chết (hủy và đóng kết nối): tiến trình khác nhận trong khoảng 1 s, không bao giờ có 2 tiến trình cùng chạy | đạt |
| Phiên của leader bị `pg_terminate_backend`: leader dừng việc, một tiến trình nhận, không có 2 leader | đạt |
| Việc nền lỗi: leader khởi động lại việc | đạt |
| Tắt sạch: khóa nhả ngay | đạt |
| Kiểm tra độ nhạy: tắt bầu chọn (khóa luôn thành công) | 3 test chính thất bại, trở lại đạt khi khôi phục |
| Runtime 8015 thật (1 tiến trình) | log `leader_acquired`, learning worker `ready`, khóa 727002 do đúng 1 backend giữ |

Chưa đo: 2 tiến trình API thật chạy cùng lúc (launcher chỉ hỗ trợ 1 tiến trình cho đến bước 1.8); các test dùng nhiều pool trong một tiến trình.
Việc nền do `knowledge_runtime` (nhịp tim xác nhận phát hành) và khởi động ấm RAG v2 cố ý vẫn chạy ở mọi tiến trình: mỗi tiến trình phải tự xác nhận mình đang phục vụ.
