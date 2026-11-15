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
