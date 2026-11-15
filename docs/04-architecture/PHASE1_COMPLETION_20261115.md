# Giai đoạn 1 (local, sẵn sàng cho cloud): kết quả và việc còn lại (2026-11-15)

Kế hoạch: [ROLLOUT_PLAN_LOCAL_THEN_CLOUD_20261115.md](ROLLOUT_PLAN_LOCAL_THEN_CLOUD_20261115.md). Thiết kế: [CAPACITY_100_USERS_DESIGN_20261115.md](CAPACITY_100_USERS_DESIGN_20261115.md).
Giai đoạn 2 (deploy lên VPS) **chưa bắt đầu**, chờ lệnh của chủ dự án.

## Từng bước

| Bước | Kết quả | Bằng chứng |
|---|---|---|
| 1.0 Mốc | Đạt. 112 mục lỗi có sẵn được ghi làm mốc so sánh | `evals/results/baseline-20261115/` |
| 1.1 Hồ sơ cấu hình | Đạt. `local.toml`, `cloud.toml`, kiểm RAM trước khi khởi động | `infra/profiles/`, `scripts/runtime_profile.py` |
| 1.2 Admission control | Đạt. 100 người, 1 tiến trình: lượt chạy tối đa 17,8 s, 503 trong 4,8 s | `evals/results/admission-20261115/` |
| 1.3 `vector_failed` | Đạt. Đo: mất nhánh vector 26 % (50 người) và 71 % (100 người) trước khi sửa | `evals/results/vector-stats-20261115/` |
| 1.4 Trạng thái dùng chung | Đạt. Sửa lỗi khóa WAL khi nhiều tiến trình khởi động cùng lúc; kiểm kê | `docs/04-architecture/SHARED_STATE_INVENTORY_20261115.md` |
| 1.5 Rate limit dùng chung | Đạt. 3 pool đua cho đúng 30/90; fail closed | `evals/results/shared-limiter-20261115/` |
| 1.6 Leader việc nền | Đạt. Một leader, tiếp quản khi chết hoặc mất phiên | `evals/results/leader-20261115/` |
| 1.7 Gateway sidecar | Đạt. Ledger đúng một lần mỗi lời gọi; API không giữ khóa provider | `evals/results/gateway-sidecar-20261115/` |
| 1.8 Nhiều worker | Đạt. 69 lên 125 lượt/phút (1,82 lần); xác nhận hành động ghi dùng chung | `evals/results/workers-20261115/` |
| 1.9 Giảm CPU, gỡ nghẽn embedding | **Một phần.** `vector_failed` 0,7 % và p95 14,3 s đạt; thành công 98,5 % (mục tiêu 99 %) chưa đạt | `evals/results/cpu-20261115/` |
| 1.10 Gate chất lượng | Đạt (sau khi sửa máy khách đo). safety 20/20, stop 35/35, core 80 %, sai 0 | `evals/results/gate-20261115/` |
| 1.11 Port Linux | Đạt cho phần máy chủ chạy. Vector Windows và Linux giống hệt từng bit | `evals/results/linux-port-20261115/` |
| 1.12 Bộ triển khai cloud | Đạt. Cài trọn trên Ubuntu 24.04 sạch; sinh đơn vị systemd từ hồ sơ | `infra/cloud/` |
| 1.13 Giả lập 4 CPU / 8 GB | Đạt kịch bản B (100 % thành công, p95 13,0 s, RAM 65 %, không OOM); kịch bản A không sập nhưng 503 lâu nhất 5,4 s | `evals/results/cloud-sim-20261115/` |
| 1.14 Diễn tập khôi phục | Đạt. Postgres 55 bảng và 20.403 dòng giống hệt; SQLite giống backup | như trên |
| 1.15 Giảm lời gọi (tùy chọn) | **Không làm.** Các đòn bẩy L1, L2, L4 đổi cách kiểm chứng hoặc cần cổng chất lượng đầy đủ; chỉ làm khi chủ dự án muốn giảm chi phí | |

## Định nghĩa "sẵn sàng deploy" (mục 1.3 của kế hoạch)

- [~] Hồ sơ `local`, tải giả kịch bản A: `vector_failed` và p95 đạt, **thành công 98,5 % thay vì 99 %** (3 trên 200 lượt hết 3 lần thử vì cổng admission báo bận lúc dồn đỉnh).
- [x] Test: Windows không có lỗi mới so với mốc; Linux chạy các nhóm phần máy chủ, các test chỉ Windows được bỏ qua kèm lý do trong `tests/conftest.py`.
- [x] Gate chất lượng PASSED trên kiến trúc mới.
- [x] Hồ sơ `cloud` giả lập đạt tiêu chí kịch bản B; kịch bản A chỉ lệch ở thời gian trả 503 (5,4 s so với 5 s).
- [x] `infra/cloud/install.sh` dựng được hệ thống từ Ubuntu sạch (đã chạy trong container).
- [x] Sao lưu và khôi phục đã diễn tập.
- [x] Không có bí mật hay credential trong repo và `infra/cloud/` (đã quét).
- [x] Runbook `infra/cloud/README.md`.

## Việc cần chủ dự án quyết định trước giai đoạn 2

1. **Kịch bản A thiếu 0,5 điểm phần trăm.** Máy này (và VPS 4 vCPU) phục vụ khoảng 107–125 lượt/phút trong khi 100 người hỏi cùng lúc cần khoảng 200. Chọn một: chấp nhận mục tiêu kịch bản B kèm báo bận khi bị dồn; hoặc dùng VPS lớn hơn; hoặc xét embedding INT8 (cần cổng chất lượng riêng).
2. **Trần chi tiêu thật của gateway** (cloud đang có giá trị tạm 5 USD và 2.000 lời gọi mỗi ngày).
3. **Dữ liệu nào lên cloud**: chỉ kiến thức công khai hay cả tài khoản và hội thoại thật. Bản backup mặc định không chứa mật khẩu dạng chữ.
4. **Module học liệu** cần ClamAV bản Linux; hiện cloud chạy với module này tắt.
5. **VPS, tên miền, nơi lưu backup ngoài máy chủ.**

## Chưa kiểm chứng (nói rõ)

Tốc độ thật của CPU VPS, Caddy và HTTPS thật, systemd thật (đơn vị chỉ được sinh và kiểm bằng test), frontend trên Linux, tải với provider thật, giám sát và cảnh báo, hành vi người dùng thật.
Các số đo tải dùng provider giả có độ trễ lấy từ ledger thật; gate dùng câu hỏi có đáp án đã kiểm bằng code.
