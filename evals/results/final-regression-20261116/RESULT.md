# Regression cuối giai đoạn 1 (2026-11-16)

Lệnh: `.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider tests -rfE` trên Windows, runtime local đang chạy. Kết quả: 4955 đạt, 52 lỗi, 60 lỗi dựng fixture, 48 bỏ qua, 1110 s.
Đối chiếu `failures.txt` với `../baseline-20261115/baseline-failures.txt`: **cùng đúng 112 mục, không mục mới, không mục nào khác**. Hai test từng chập chờn (`test_shared_rate_limiter`, `test_background_leader`) đã đạt (nguyên nhân: hết kết nối Postgres, đã giảm cỡ pool và bỏ qua kèm lý do khi hết kết nối).
