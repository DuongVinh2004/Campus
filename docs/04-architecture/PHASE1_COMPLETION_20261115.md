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
| 1.9 Giảm CPU, gỡ nghẽn embedding | Đạt. Sau khi tái dùng kết nối SQLite: 3 lần chạy API mới cho thành công 100 %, 99,5 %, 100 %, p95 khoảng 11,8 s, `vector_failed` 0, 503 trong 4,5 s | `evals/results/cpu-20261115/` |
| 1.10 Gate chất lượng | Đạt (sau khi sửa máy khách đo). safety 20/20, stop 35/35, core 80 %, sai 0 | `evals/results/gate-20261115/` |
| 1.11 Port Linux | Đạt cho phần máy chủ chạy và **frontend**: build từ lockfile bằng `infra/cloud/build_frontend.sh` trên Ubuntu 24.04, 5 trang chính trả 200, 796 test web đạt. Vector Windows và Linux giống hệt từng bit | `evals/results/linux-port-20261115/` |
| 1.12 Bộ triển khai cloud | Đạt. Cài trọn trên Ubuntu 24.04 sạch; sinh đơn vị systemd từ hồ sơ | `infra/cloud/` |
| 1.13 Giả lập 4 CPU / 8 GB | Đo lại trên mã cuối: B 100 %, p95 8,3 s, RAM 67 %, không OOM; A khi đã nóng 99,5 %, p95 12,9 s, 503 trong 5,0 s; A ngay sau khởi động nguội 89 % (cần làm nóng mô hình trước khi mở) | `evals/results/cloud-sim-20261115/` |
| 1.14 Diễn tập khôi phục | Đạt. Postgres 55 bảng và 20.403 dòng giống hệt; SQLite giống backup | như trên |
| 1.15 Giảm lời gọi | Đã làm và đo bằng provider thật. L4: 89,8 % token vào đã từ cache. L1: chỉ tiết kiệm tối đa 1,7 % và bật cùng L2 thì 2/4 lần gate có câu sai, **để tắt**. L2: giảm 8,6 % khi câu hỏi lặp, gate lần nguội PASSED, **để tắt mặc định** chờ chủ dự án. Gặp lỗi chập chờn ~1 % lượt (hết ngân sách 30 s) chưa tìm ra gốc | `evals/results/l115-20261116/` |

## Định nghĩa "sẵn sàng deploy" (mục 1.3 của kế hoạch)

- [x] Hồ sơ `local`, tải giả kịch bản A: thành công trung bình 99,8 % trên 3 lần chạy API mới (mục tiêu 99 %), p95 khoảng 11,8 s, `vector_failed` 0, 503 trong 4,5 s.
- [x] Test: Windows không có lỗi mới so với mốc; Linux chạy các nhóm phần máy chủ, các test chỉ Windows được bỏ qua kèm lý do trong `tests/conftest.py`.
- [x] Gate chất lượng PASSED trên kiến trúc mới.
- [x] Hồ sơ `cloud` giả lập (mã cuối) đạt kịch bản B (100 %, p95 8,3 s) và kịch bản A khi nóng (99,5 %, p95 12,9 s, 503 trong 5,0 s); lần chạy nguội ngay sau khởi động chỉ 89 %, nên cần bước làm nóng.
- [x] `infra/cloud/install.sh` dựng được hệ thống từ Ubuntu sạch (đã chạy trong container).
- [x] Sao lưu và khôi phục đã diễn tập.
- [x] Không có bí mật hay credential trong repo và `infra/cloud/` (đã quét).
- [x] Runbook `infra/cloud/README.md`.

## Việc cần chủ dự án quyết định trước giai đoạn 2

1. **Kịch bản A đã đạt trên máy này** (không cần INT8 hay VPS lớn hơn để đạt mục tiêu của kế hoạch). Vẫn nên đo lại trên VPS thật ở bước 2.3 vì tốc độ CPU khác.
2. **Trần chi tiêu thật của gateway** (cloud đang có giá trị tạm 5 USD và 2.000 lời gọi mỗi ngày; trần này đã chạm ngay trong ba lần chạy tải 100 người, nên chắc chắn phải nâng).
3. **Dữ liệu nào lên cloud**: chỉ kiến thức công khai hay cả tài khoản và hội thoại thật. Bản backup mặc định không chứa mật khẩu dạng chữ.
4. **Module học liệu** cần ClamAV bản Linux; hiện cloud chạy với module này tắt.
5. **VPS, tên miền, nơi lưu backup ngoài máy chủ.**

## Chưa kiểm chứng (nói rõ)

Tốc độ thật của CPU VPS, HTTPS thật với tên miền (cấu hình Caddy đã qua `caddy validate`), khởi động thật dưới systemd (đơn vị đã qua `systemd-analyze verify`), tải 100 người với provider thật, giám sát và cảnh báo, hành vi người dùng thật.
Các số đo tải dùng provider giả có độ trễ lấy từ ledger thật; gate dùng câu hỏi có đáp án đã kiểm bằng code.

## Việc phát hiện thêm khi làm nốt (cần chủ dự án biết)

- **Lỗi chập chờn khoảng 1 % lượt** (hết ngân sách 30 s, trả `AI_WORKFLOW_UNAVAILABLE`) với provider thật; có từ trước các thay đổi này, chưa tìm ra gốc; làm gate dễ trượt oan (chi tiết `evals/results/l115-20261116/RESULT.md`).
- **Nhiều file nguồn chưa được git theo dõi** (ví dụ `scripts/run_public_rag.py`, `application/conversation/stream_result.py`; chỉ 29 trên 397 file trong `scripts/` được theo dõi). Triển khai cloud bằng `git clone` sẽ thiếu chúng; cần commit hoặc đóng gói từ cây làm việc ở bước 2.1.
- L1 và L2 đã làm nhưng tắt; bật L2 là một dòng cấu hình `CAMPUS247_RAG_ANSWER_CACHE=on` khi chủ dự án đồng ý.
