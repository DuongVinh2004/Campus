# Tải 100 người dùng với provider thật (2026-11-16)

Máy này (i7-10850H, 6 lõi), runtime local: 2 worker API, gateway sidecar, máy chủ embedding cùng máy, **provider DeepSeek thật** qua sidecar, giới hạn 30 yêu cầu/phút mỗi tài khoản được tạm gỡ chỉ để một tài khoản tổng hợp đóng vai nhiều người (`CAMPUS_LOADTEST_NO_RATE_LIMIT=1`), câu hỏi không lặp, mỗi người nghĩ 8–25 s. Máy sinh tải chạy cùng máy nên số đo hơi bi quan. Chi phí khoảng 2.400 lời gọi trong ba lần chạy.

| Lần chạy | Thành công | p50 / p95 / lâu nhất | 503 lâu nhất | Lời gọi hỏng | Mất nhánh vector |
|---|---|---|---|---|---|
| 25 người × 2 | 100 % | 4,7 / 7,1 / 8,4 s | không có | 0 / 217 | 4 % |
| 100 × 2, chờ vector 1,0 s | 100 % | 9,2 / 13,2 / 15,5 s | 4,4 s | 0 / 872 | **khoảng 20 %** |
| 100 × 2, chờ vector 2,5 s | **99,5 %** (1 lượt hết 3 lần thử vì bận) | 9,7 / **13,1** / 15,5 s | 4,3 s | 0 / 1.103 | **0 trên khoảng 200** |

Phát hiện: với tải thật, nhánh vector của truy xuất bị mất ở khoảng 20 % lượt khi giới hạn chờ là 1,0 s (máy chủ embedding tranh CPU với API), nghĩa là các lượt đó chỉ dựa vào tìm từ khóa. Đã nâng giới hạn lên 2,5 s (`VECTOR_TIMEOUT_S`, đổi được bằng `CAMPUS247_VECTOR_TIMEOUT_S`; ngân sách lượt 22 s): mất nhánh vector về 0, p95 không đổi (13,1 s), vector lâu nhất 1,57 s. Cổng chất lượng sau thay đổi: **PASSED** (safety 20/20, stop 35/35, core 78 %, sai 0, lỗi 0).
Tiêu chí kịch bản A của thiết kế (thành công ≥ 99 %, p95 ≤ 15 s, 503 ≤ 5 s, `vector_failed` ≤ 1 %, không loop bị chặn): đạt trên máy này. Trung bình 4,4 lời gọi mỗi lượt, 75 % token vào được cache của provider, 0 lỗi 429, 0 `loop_blocked`, 0 `graph_failure`.
Chưa đo: CPU 4 vCPU thật của VPS (máy này mạnh hơn), người dùng thật (hành vi, câu hỏi thật), và phân phối câu hỏi lặp.
