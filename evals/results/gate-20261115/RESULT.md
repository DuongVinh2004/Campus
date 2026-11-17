# Bước 1.10: cổng chất lượng `gate run --quick` trên kiến trúc mới (2026-11-15)

Kiến trúc đã chạy: 2 worker API, cổng admission, rate limit Postgres, gateway sidecar, nhánh embedding mới (bộ nhớ đệm, embed sớm). Provider thật (khoảng 600 lời gọi), bộ chấm ngữ nghĩa qua 9router, so với `rag-gate-baseline.json`.

| Suite | n | Hữu ích | Sai | Lỗi | Dừng đúng | p90 | Hồi quy / sửa được |
|---|---|---|---|---|---|---|---|
| safety | 20 | — | 0 | 0 | 20/20 | 3,3 s | 0 / 0 |
| stop | 35 | — | 0 | 0 | 35/35 | 4,0 s | 0 / 0 |
| core | 78 | 80 % (mốc 81,5 %) | 0 | 0 | 13/13 | 5,7 s | 1 / 0 (nằm trong dải sai số của gate) |

**GATE PASSED** (mã thoát 0). Bản ghi lần chạy đạt: `quick-pass.txt`; số liệu từng suite của hai lần chạy nằm trong `evals/results/rag-gate/`.

## Lần chạy đầu thất bại, vì sao

Lần đầu cho kết quả đúng (sai 0, lỗi 0, dừng 20/20 và 35/35, core hữu ích 80 %) nhưng **p90 vượt 20 s** (49,5 s, 39,1 s, 22,3 s). Nguyên nhân không phải hệ thống chậm:
máy khách của gate gửi nhanh hơn 30 yêu cầu mỗi phút cho một tài khoản (câu trả lời giờ nhanh hơn), bị giới hạn tốc độ trả 429 `Retry-After` rồi **ngủ chờ 39–49 s trong lúc đang đo giây**.
Dấu hiệu: các lượt chậm đến thành từng cặp ngay sau khoảng 30 yêu cầu, log API không có lỗi gateway nào và độ trễ phía máy chủ tối đa 8,6 s.
Sửa ở máy khách đo: `rag_natural_eval.py` giữ tối đa 27 yêu cầu mỗi 60 s và **không tính thời gian chờ pacing hay chờ 429 vào số giây**. Không đổi giới hạn, không nới bảo vệ, không đổi ngưỡng của gate.
Lần chạy lại đạt.

Chưa đo: chất lượng ở các suite khác (`realstyle`, `holdout`, `multiturn`, `conflict`); gate đầy đủ (`run` không `--quick`) cần chạy trước một đợt phát hành.
