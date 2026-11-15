# Bước 1.13 và 1.14: mô phỏng VPS 4 CPU / 8 GB và diễn tập khôi phục (2026-11-15)

Môi trường: container Docker (`campus247-sim`) trên Ubuntu 24.04 sạch, giới hạn `--cpus=4 --memory=7500m` (VM Docker ở máy này chỉ có 8 GB; 7,32 GiB cgroup, nên khắt khe hơn VPS 8 GB một chút).
Dựng bằng chính `infra/cloud/install.sh` (gói hệ thống, Postgres 17 từ PGDG kèm pgvector, Node 22.11.0 có kiểm checksum, Python 3.12 và môi trường từ `uv.lock`).
Dữ liệu vào bằng **backup thật của runtime local** (`backup.py`, 477 MB, 140 s), khôi phục bằng `backup.py restore`; mô hình, chỉ mục và thư mục fixture gắn chỉ-đọc từ workspace nên runtime local không bị đụng tới. Provider giả (không tốn lời gọi); máy sinh tải chạy **bên trong** cùng giới hạn 4 CPU nên số đo hơi bi quan.

## Dựng và khởi động
`install.sh` chạy hết trên Ubuntu sạch. Khởi động theo thứ tự README (Postgres, mô hình, gateway, 2 API worker): `/health/ready` sẵn sàng, đúng 1 leader việc nền, một câu hỏi thật trả lời có trích dẫn.

## Đo (câu hỏi không lặp)

| | Kịch bản B: 50 người × 3 | Kịch bản A: 100 người × 2 |
|---|---|---|
| Thành công | **100 %** | 96,5 % (7 lượt hết 3 lần thử vì bị báo bận) |
| p50 / p95 / lâu nhất | 7,7 / **13,0** / 13,6 s | 17,0 / 21,1 / 24,2 s |
| 503 lâu nhất | không có | 5,4 s |
| Mất nhánh vector | 0 trên 75 | 1 trên 175 (0,6 %) |
| RAM không thể thu hồi (anon) đỉnh | **4,78 GB = 65 %** giới hạn | 4,96 GB = 68 % |
| Swap, OOM | 0, 0 | 0, 0 |
| Lõi CPU trung bình / đỉnh | 1,3 / 4,1 | 2,2 / 4,0 |

Tiêu chí kế hoạch: kịch bản B thành công ≥ 99 %, p95 ≤ 15 s, RAM đỉnh ≤ 85 %, không OOM: **đạt**. Kịch bản A không sập, không OOM, RAM 68 %: **đạt**; lượt quá tải nhận 503 trong ≤ 5 s: **chưa đạt sát** (tối đa 5,4 s, cổng chờ 4 s cộng độ trễ của vòng lặp khi CPU bão hòa).
Lúc rảnh container dùng 4,7 GiB (chưa gồm frontend khoảng 0,2 GB), trong dự toán 5,75 GB.
**Giả lập này kiểm RAM và tính đúng trên Linux, không kiểm tốc độ CPU của VPS thật** (lõi máy này nhanh hơn vCPU cloud); tốc độ thật chỉ biết ở bước 2.3.

## Chịu lỗi
Giết cả hai worker API: supervisor khởi động lại cả hai, `/health/ready` vẫn sẵn sàng, leader được bầu lại (số lần `leader_acquired` từ 1 lên 2) và một lượt chat trả lời.

## Diễn tập khôi phục (1.14)
Khôi phục từ backup vào môi trường trống: kiểm checksum từng phần rồi `pg_restore` bằng siêu người dùng Postgres. Kết quả đối chiếu với nguồn: **55 bảng, 20.403 dòng Postgres giống hệt**; các kho SQLite hoạt động, chat, vận hành, idempotency, giống hệt bản backup;
bảng hội thoại hơn nguồn 490 hội thoại và 690 tin nhắn **vì chính các bài tải thử trong container ghi thêm** (`counts-restored-after-load.json` chụp sau khi tải).
Diễn tập lộ ra và đã sửa các lỗi thật của bộ công cụ: dump Postgres 17 không khôi phục được vào Postgres 16 (cài từ PGDG), tệp khóa của ledger bị khóa byte-range khi sao chép, bản ghi đặt chỗ của các lượt chưa quyết toán nằm rải rác ngoài 3000 bản mới nhất, chuỗi tệp ủy quyền và thư mục học liệu nằm ngoài thư mục trạng thái,
SQLite chế độ WAL trong thư mục chỉ-đọc, đường dẫn tuyệt đối Windows trong tệp ủy quyền.

## Chưa kiểm
Caddy và HTTPS thật (cần tên miền), systemd thật (container không có systemd; đơn vị chỉ được sinh ra và kiểm bằng test chứ chưa khởi động), frontend Linux, tải với provider thật, giám sát và cảnh báo.
Phần sao lưu ngoài máy chủ (off-site) và diễn tập khôi phục trên VPS thật nằm ở giai đoạn 2.

## Đo lại trên mã cuối (sau khi tái dùng kết nối SQLite) — 2026-11-16

Dựng lại ảnh Docker từ mã cuối, cùng giới hạn `--cpus=4 --memory=7500m`, provider giả, câu hỏi không lặp. Tệp: `sim-b-50-final.json`, `sim-a-100-final.json`, `sim-a-100-final-warm.json`, `cg-*-final*.json`.

| | B: 50 × 3 | A: 100 × 2, ngay sau khi khởi động (nguội) | A: 100 × 2, đã chạy nóng |
|---|---|---|---|
| Thành công | **100 %** | 89 % (22 lượt hết thử vì bận) | **99,5 %** (1 lượt) |
| p50 / p95 / lâu nhất | 5,9 / **8,3** / 9,8 s | 19,1 / 24,2 / 27,8 s | 9,8 / **12,9** / 15,5 s |
| 503 lâu nhất | không có | 5,4 s | **5,0 s** |
| RAM anon đỉnh | 4,91 GB = 67 % | 66 % | 69 % |
| OOM, swap | 0, 0 | 0, 0 | 0, 0 |

Kịch bản B đạt rõ (p95 8,3 s so với 13,0 s trước khi tái dùng kết nối). Kịch bản A khi đã chạy nóng đạt 99,5 %, p95 12,9 s, 503 trong 5,0 s.
**Hạn chế ghi nhận:** lần chạy A đầu tiên ngay sau khi khởi động chỉ đạt 89 % vì nhánh vector hết thời gian ở các truy vấn đầu (7 đến 10 lần mất nhánh vector trên 75 lượt tìm kiếm, toàn bộ nằm trong lần chạy nguội này; lần chạy nóng không thêm lần nào). Nghĩa là mô hình embedding cần được làm nóng trước khi nhận tải đỉnh; khi mở cho người dùng nên chạy vài câu hỏi khởi động trước.
Một lần chạy A khác chỉ đạt 69 % không phải do hiệu năng: **trần gọi trong ngày của gateway (2.000 lời gọi, giá trị tạm của hồ sơ cloud) đã chạm** và gateway từ chối đúng thiết kế (`reason=daily_cap`). Lần chạy được loại khỏi số đo; trần được đặt lại chỉ trong container mô phỏng rồi chạy lại ra kết quả nóng ở trên. Điều này cũng nghĩa là trần 2.000 lời gọi/ngày không đủ cho tải 100 người, chủ dự án cần chọn trần thật.
Giết cả hai worker API: `/health/ready` trở lại 200 sau chưa tới 30 s, supervisor dựng lại hai worker, `leader_acquired` từ 1 lên 2.

## Kiểm bổ sung trong container (2026-11-16)
- `caddy validate` với `Caddyfile.example` (đặt `CAMPUS247_DOMAIN`): **Valid configuration**.
- `systemd-analyze verify` các đơn vị `campus247-api/frontend/gateway/models.service` đã sinh ra: không báo lỗi; đơn vị backup chỉ cảnh báo bit thực thi (sinh ra từ việc sao chép từ Windows, không ảnh hưởng).
- Vẫn chưa kiểm: khởi động thật dưới systemd (container không có init), HTTPS thật với tên miền, frontend Linux, tốc độ CPU của VPS thật.
