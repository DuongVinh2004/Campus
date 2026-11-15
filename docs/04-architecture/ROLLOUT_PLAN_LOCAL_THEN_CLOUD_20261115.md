# Kế hoạch triển khai 2 giai đoạn: local trước, cloud khi được lệnh (2026-11-15)

Thiết kế và số đo: [CAPACITY_100_USERS_DESIGN_20261115.md](CAPACITY_100_USERS_DESIGN_20261115.md). Cấu hình cloud đã chốt: **4 vCPU / 8 GB**, Linux, CPU không burstable. Model và index giữ nguyên ở cả hai nơi.

| Giai đoạn | Làm ở đâu | Khi nào bắt đầu | Kết thúc khi |
|---|---|---|---|
| **1. Local, sẵn sàng cho cloud** | Máy này (Windows) và giả lập Linux trên máy này | Khi người dùng bảo bắt đầu | Đạt toàn bộ "Định nghĩa sẵn sàng deploy" (mục 1.3) |
| **2. Deploy lên cloud** | VPS 4 vCPU / 8 GB | **Chỉ khi người dùng thông báo** | Chạy thật, có giám sát, đã thử khôi phục |

Quy tắc chung cho cả hai giai đoạn:
- Giữ nguyên bound 5 s mỗi lời gọi provider, ngân sách 22 s mỗi lượt, các bộ safety/stop chặt, xác thực, phân quyền, xác nhận hành động, kiểm nguồn.
- Không commit, push hay deploy nếu không có lệnh rõ ràng.
- Không đưa file credential, khóa bí mật hay dữ liệu cá nhân vào repo hoặc lên server khi chưa được duyệt.
- Mọi thay đổi có thể ảnh hưởng câu trả lời phải qua regression gate.

---

## Giai đoạn 1: chạy trên máy này, luôn sẵn sàng cho cloud

### 1.1 Cách giữ "luôn sẵn sàng deploy"

1. **Một mã nguồn, hai hồ sơ.** Mọi khác biệt giữa máy này và cloud nằm trong `infra/profiles/local.toml` và `infra/profiles/cloud.toml`: số worker, giới hạn, đường dẫn, cổng, mức đồng thời tới provider, trần chi tiêu. Code không được có `if windows` cho logic nghiệp vụ. Phần khác hệ điều hành chỉ nằm trong lớp adapter: launcher, binding ONNX, kiểm tra đường dẫn.
2. **Không thêm phụ thuộc chỉ có trên Windows.** Không gọi PowerShell/WMI trong code mới. Không dùng đường dẫn tuyệt đối kiểu `C:\`.
3. **Kiểm Linux liên tục.** Sau mỗi bước, chạy bộ test trong WSL2 Ubuntu (đã có trên máy) song song với Windows. Bước chưa qua trên cả hai thì chưa coi là xong.
4. **Script triển khai được viết và thử ngay trong giai đoạn 1** (`infra/cloud/`), chạy được vào một máy Linux sạch. Giai đoạn 2 chỉ còn là chạy lại script đó trên VPS.

### 1.2 Các bước

Mỗi bước kết thúc bằng test và một bài đo. Chưa đạt thì không sang bước sau.

| Bước | Việc | File/khu vực chính | Kiểm chứng để qua | Trả phí |
|---|---|---|---|---|
| **1.0 Mốc xuất phát** | Lưu số đo hiện tại (CPU mỗi lượt, tải giả 50/100 người). Commit phần tối ưu đã làm lên nhánh riêng **nếu người dùng đồng ý** | `evals/load/README.md` | Test hiện có đạt (`--basetemp` trong workspace). Mốc đo được lưu | 0 |
| **1.1 Hồ sơ cấu hình** | Thêm `infra/profiles/{local,cloud}.toml`. Launcher đọc hồ sơ. Kiểm tra RAM khi khởi động: từ chối chạy nếu RAM trống không đủ cho hồ sơ | `scripts/knowledge_platform_runtime.py`, `infra/profiles/` | Hồ sơ `local` khởi động giống hệt hiện tại. Hồ sơ thiếu RAM bị từ chối với thông báo rõ | 0 |
| **1.2 Admission control** | Mỗi worker tối đa K lượt đang chạy (đo ở 1.2: K=12 cho local), chờ tối đa 4 s (chờ 5 s làm 503 về sau 6 s khi máy bão hòa), quá thì 503 "Hệ thống đang bận, thử lại sau ít giây". Frontend hiển thị đúng thông báo này | middleware API, `apps/web` (xử lý 503) | Tải giả 100 người, 1 tiến trình: **không lượt nào > 22 s**. 503 trả về trong ≤ 5 s | 0 |
| **1.3 Chỉ số `vector_failed`** | Đếm và log khi nhánh vector hết giờ, kèm số đếm 503 và số lượt đang chạy | `rag_v2/retrieval/hybrid.py`, log API | Có số liệu trong log. Đo được tỉ lệ ở mức tải 50/100 người | 0 |
| **1.4 Rà trạng thái dùng chung** | Liệt kê mọi trạng thái module-level: idempotency, xác nhận hành động, phiên, cache. Rà các kho SQLite: hiện chỉ idempotency, audit, campus_ops bật WAL và `busy_timeout`; các kho khác (conversations, actor_state, agent_runs, assistant_memory, certificates, policy_graph, service_operations) phải được kiểm và bật nếu thiếu | toàn bộ `services/api/src`, `infrastructure/repositories/sqlite_*.py` | Có bảng kiểm kê. Test ghi đồng thời từ 3 tiến trình vào từng kho SQLite: không mất bản ghi, không lỗi "database is locked" | 0 |
| **1.5 Rate limit dùng chung** | Store Postgres cho `AbuseLimiterMiddleware`, giữ `fail_closed=True` và các quy tắc hiện có (30/phút với chat) | `presentation/middleware/abuse_limits.py`, `bootstrap/app.py` | Test: N worker vẫn chặn đúng 30/phút cho mỗi tài khoản. Postgres lỗi thì từ chối (fail closed) | 0 |
| **1.6 Leader việc nền** | Scheduler, learning worker, OCR chỉ chạy ở worker giữ `pg_try_advisory_lock`. Leader chết thì worker khác nhận | `owned_lifespan` trong bootstrap | Test: 3 worker thì việc nền chỉ chạy một nơi. Giết leader thì việc nền tiếp tục ở worker khác | 0 |
| **1.7 Gateway sidecar** | Tách gateway trả phí thành tiến trình riêng: giữ `PaidLedgerWriterLease`, mức đồng thời P, **trần chi tiêu thật** (giá trị do người dùng chọn). API gọi qua loopback, có token nội bộ. Bound 28.000 byte / 1000 token / 5000 ms giữ nguyên. Chuyển chỗ cài provider giả sang sidecar (lời gọi HTTP tới provider nay nằm ở đó) | `scripts/run_public_rag.py`, adapter gateway của API, `evals/load/` | Test: mỗi lời gọi ghi ledger đúng 1 lần. Sidecar chết thì API báo lỗi rõ, không gọi thẳng provider. Vượt trần thì từ chối. Tải giả vẫn không ghi vào ledger trả phí | 0 |
| **1.8 Nhiều worker** | API hiện khởi động bằng **đối tượng app** (`uvicorn.Server(uvicorn.Config(app, ...))` ở `knowledge_platform.py:643`), nên không bật `workers` trực tiếp được. Phải tách thành app factory nạp qua import string, đọc cấu hình từ biến môi trường, rồi mới chạy N worker theo hồ sơ (local 2–3 tùy RAM trống, cloud 2) | `scripts/knowledge_platform.py`, launcher, `bootstrap/app.py` | Tải giả: thông lượng ≥ 1,8 lần so với 1 tiến trình, không có lỗi mới do nhiều tiến trình. Giết 1 worker thì phần còn lại vẫn phục vụ | 0 |
| **1.9 Giảm CPU và gỡ nghẽn embedding** | API: memo kiểm đường dẫn (vẫn chặn reparse point), dùng lại kết nối SQLite, `_build_index` từ index đầy đủ. Embedding: hiện mọi lần embed và rerank đi qua **một khóa chung, chạy tuần tự** (177 ms mỗi lần embed, tối đa khoảng 340 lần/phút); tách khóa embedding khỏi reranker, đo các thiết lập luồng của ONNX, thêm cache vector truy vấn. Mục tiêu tổng ≤ 0,8 s CPU mỗi lượt | `rag_v2`, `application/knowledge/values.py`, kho identity, `scripts/serve_rag_models.py` | Test tương đương: cùng đầu vào cho cùng kết quả, vector không đổi. Đo CPU từng thành phần. **Tải giả kịch bản A, 100 người, với câu hỏi không lặp: thành công ≥ 99%, p95 ≤ 15 s, `vector_failed` ≤ 1%** | 0 |
| **1.10 Cổng chất lượng lần 1** | `gate run --quick` với provider thật trên kiến trúc mới | `evals/runners/rag_regression_gate.py` | **Gate PASSED**: safety/stop không giảm, các bộ khác trong dải dung sai | khoảng 600 |
| **1.11 Port Linux** | Các chỗ gắn Windows đã xác định trong code: (a) khóa ledger dùng `msvcrt.locking` (`scripts/public_rag_ledger.py`), cần nhánh `fcntl` cho Linux; (b) binding ONNX nạp `onnxruntime.dll` bằng `WinDLL`, cần `libonnxruntime.so` cùng phiên bản, có kiểm checksum; (c) launcher gọi `powershell.exe` và `pg_ctl.exe`/`initdb.exe` của bản Postgres đóng gói kèm `vector.dll`, trên Linux dùng Postgres hệ thống với gói `pgvector` và `btree_gist`; (d) numpy trong `data/rag_v2_vendor` là bản nhị phân Windows, trên Linux cài numpy 2.3.5 theo `uv.lock`; (e) kiểm đường dẫn (reparse point) cần nhánh symlink cho Linux. Cố định Python 3.12 và cài phụ thuộc bằng `uv sync` từ `uv.lock` | `scripts/public_rag_ledger.py`, `infra/local/rag-fixture/onnx_capi_*.py`, `scripts/knowledge_platform*.py`, `values.checked_path` | Toàn bộ test đạt trong WSL2 Ubuntu; hồ sơ `local` trên Windows vẫn đạt. **So khớp số học**: vector embedding của 200 truy vấn mẫu trên Linux khớp Windows (cosine ≥ 0,9999) và `rag_recall_probe.py` trên Linux không thấp hơn Windows quá 0,5 điểm | 0 |
| **1.12 Bộ triển khai cloud** | `infra/cloud/`: script cài đặt cho máy Linux sạch (Python 3.12 và uv, Node, Postgres có pgvector), unit systemd cho từng tiến trình, Caddy HTTPS (chỉ mở 443; các dịch vụ khác nghe loopback), file env mẫu (không chứa bí mật). Script chuyển dữ liệu: dump và khôi phục Postgres, chép các file SQLite, index, model có kiểm checksum. Script sao lưu và khôi phục. Xoay vòng log; gom theo ngày các file nhỏ của ledger trả phí và của máy chủ mô hình (máy chủ mô hình ghi 2–3 file mỗi lần suy luận, khoảng 36 nghìn file trong một ngày đo) | `infra/cloud/` (mới) | Chạy script trên **một Ubuntu sạch trong WSL2 hoặc container** thì hệ thống lên được và trả lời được câu hỏi | 0 |
| **1.13 Giả lập cloud 4 CPU / 8 GB** | Chạy hồ sơ `cloud` trong container giới hạn `--cpus=4 --memory=8g`, dùng Docker Desktop đã có. Lúc chạy phải tạm dừng runtime local để đủ RAM (máy hiện chỉ còn khoảng 3 GB trống). Máy ảo WSL2 mặc định chỉ được khoảng một nửa RAM máy (khoảng 7,8 GB); nếu không đủ thì cần người dùng đồng ý nâng giới hạn trong `.wslconfig`, hoặc giả lập ở 7,5 GB | `infra/cloud/`, `evals/load/` | Kịch bản B thành công ≥ 99%, p95 ≤ 15 s, RAM đỉnh ≤ 85%, không OOM. Kịch bản A: không sập, lượt quá tải nhận 503 trong ≤ 5 s. **Giả lập này kiểm RAM và tính đúng trên Linux, không kiểm được tốc độ CPU của VPS** (lõi máy này nhanh hơn vCPU cloud); tốc độ thật chỉ biết ở bước 2.3 | 0 |
| **1.14 Diễn tập khôi phục** | Sao lưu, xóa môi trường giả lập, khôi phục từ bản sao lưu | `infra/cloud/` | Khôi phục xong thì hội thoại, tài khoản thử và ledger còn nguyên | 0 |
| **1.15 Giảm lời gọi (tùy chọn)** | L1 (bỏ kiểm ngữ nghĩa khi trích nguyên văn), L4 (cache tiền tố prompt nếu provider hỗ trợ), rồi L2 (cache câu trả lời công khai) | `rag_v2/service.py`, gateway | Mỗi cái `gate run --quick` PASSED. Số lời gọi mỗi lượt giảm đúng như đo | khoảng 600–1.200 |

Thứ tự có lý do:
- 1.2–1.3 làm trước để hệ thống ổn định và quan sát được ngay cả khi chỉ có 1 tiến trình;
- 1.4 làm trước 1.5–1.8 để không bật nhiều worker khi còn trạng thái chưa dùng chung;
- tiêu chí kịch bản A đặt ở 1.9 chứ không ở 1.8, vì chỉ thêm worker thì chưa đủ: embedding chạy tuần tự và tổng CPU của máy (5,3 trên 6 lõi ở 1,19 s mỗi lượt) vẫn là điểm nghẽn;
- 1.10 (tốn phí) chỉ chạy sau khi mọi thay đổi kiến trúc đã xong, để không phải gate lại nhiều lần.

Bật và tắt từng phần: admission control, số worker và cache vector đều điều khiển bằng hồ sơ, nên có thể quay về cấu hình 1 tiến trình như hiện nay bất cứ lúc nào cho tới khi 1.10 đạt.

Ba bước lớn nhất về công sức: 1.7 (gateway sidecar), 1.8 (app factory và nhiều worker), 1.11 (port Linux). Các bước còn lại nhỏ hơn rõ rệt.

### 1.2b Rủi ro đã biết

| Rủi ro | Xử lý |
|---|---|
| Kịch bản A (267 lượt/phút) có thể không đạt trên máy này dù đã tối ưu, vì embedding FP32 tốn 0,63 s CPU mỗi lượt | Báo số đo thật, không hạ tiêu chí. Khi đó các lựa chọn là: chấp nhận mục tiêu kịch bản B kèm 503 khi bị dồn, hoặc xét INT8 (mục 6 bản thiết kế, có cổng recall miễn phí) |
| Cache theo câu hỏi trông hiệu quả hơn thực tế vì tải giả lặp câu hỏi | Mọi bài đo chấp nhận dùng bộ câu hỏi không lặp |
| ONNX Runtime trên Linux cho vector khác nhẹ so với Windows | Bước 1.11 so khớp vector và chạy recall probe; gate đầy đủ chạy lại trên VPS ở 2.5 |
| Ba worker trên máy này cần thêm khoảng 1,7 GB RAM trong khi chỉ còn khoảng 3 GB trống | Kiểm tra RAM khi khởi động; hồ sơ `local` mặc định 2 worker, lên 3 khi đủ RAM |
| Nhiều tiến trình cùng ghi một file SQLite | Bước 1.4 kiểm từng kho và có test ghi đồng thời trước khi bật nhiều worker |

### 1.3 Định nghĩa "sẵn sàng deploy"

Giai đoạn 1 xong khi **tất cả** mục dưới đây đạt và có bằng chứng: lệnh, mã thoát, file kết quả.

- [ ] Hồ sơ `local` trên Windows: tải giả kịch bản A đạt (bước 1.9), hoặc người dùng đã chọn hướng xử lý theo mục 1.2b nếu không đạt
- [ ] Toàn bộ test đạt trên Windows **và** WSL2 Ubuntu
- [ ] Regression gate PASSED trên kiến trúc mới (bước 1.10)
- [ ] Hồ sơ `cloud` trong giả lập 4 CPU / 8 GB đạt tiêu chí (bước 1.13)
- [ ] Script `infra/cloud/` dựng được hệ thống từ máy Linux sạch (bước 1.12)
- [ ] Sao lưu và khôi phục đã diễn tập thành công (bước 1.14)
- [ ] Không có bí mật hay credential nào trong repo hoặc trong `infra/cloud/`
- [ ] Runbook triển khai và khôi phục viết xong (`infra/cloud/README.md`)

### 1.4 Quyết định cần người dùng trong giai đoạn 1

| Quyết định | Chặn bước | Không có thì làm gì |
|---|---|---|
| Có commit phần tối ưu lên nhánh riêng không | 1.0 | Vẫn làm tiếp, giữ nguyên thay đổi chưa commit |
| Trần chi tiêu của gateway, ví dụ theo ngày | 1.7 | Làm sidecar với trần tạm cho test; trần thật phải có trước giai đoạn 2 |
| Duyệt khoảng 600 lời gọi cho gate (khoảng 0,5 USD) | 1.10 | Mọi bước khác vẫn làm được; chỉ 1.10 và 1.15 chờ |
| Cho phép dừng runtime local trong lúc giả lập | 1.13 | Chạy giả lập ở lúc người dùng không dùng máy |
| Cho phép nâng giới hạn RAM của WSL2 trong `.wslconfig` (nếu cần) | 1.13 | Giả lập ở 7,5 GB và ghi rõ trong báo cáo |
| Nếu kịch bản A không đạt trên máy này: chấp nhận mục tiêu kịch bản B, hay xét INT8 | sau 1.9 | Tiếp tục các bước khác; báo số đo thật |

---

## Giai đoạn 2: deploy lên cloud (chỉ khi người dùng thông báo)

Điều kiện bắt đầu:
- giai đoạn 1 đã đạt "sẵn sàng deploy";
- người dùng thông báo bắt đầu.

Trước khi chạm vào server, người dùng cần cung cấp:

| Đầu vào | Ghi chú |
|---|---|
| VPS 4 vCPU / 8 GB, Ubuntu LTS, **người dùng tự thuê và thanh toán** | Ưu tiên VPS Việt Nam KVM. Dự phòng: DigitalOcean Singapore. Nên chọn gói có dùng thử hoặc hoàn tiền |
| Cách truy cập: SSH key do người dùng tạo | Không gửi mật khẩu qua chat |
| Tên miền và quyền trỏ DNS | Dùng cho HTTPS |
| Dữ liệu nào lên cloud | Chỉ index công khai, hay cả tài khoản và dữ liệu sinh viên thật |
| Khóa provider cho server | Người dùng tự đặt vào file env trên server, không qua chat |
| Trần chi tiêu thật và ngân sách kiểm thử khoảng 3.450 lời gọi (khoảng 3 USD) | |

### 2.1 Các bước

| Bước | Việc | Kiểm chứng để qua | Trả phí |
|---|---|---|---|
| **2.1 Dựng server** | Chạy script `infra/cloud/` trên VPS. Bật tường lửa (chỉ mở 22 và 443), swap 2 GB, cập nhật bảo mật tự động | Health check đạt. Từ ngoài chỉ thấy được cổng 443 | 0 |
| **2.2 Đưa dữ liệu lên** | Chép index, model (có kiểm checksum) và dữ liệu đã được duyệt | Checksum khớp. Index đọc được | 0 |
| **2.3 Đo trên VM thật** | Tải giả (provider giả) ngay trên VPS, kịch bản B rồi A | Đạt mục 10 của bản thiết kế. **Không đạt thì đổi nhà cung cấp trong hạn hoàn tiền**, chưa tốn lời gọi trả phí nào | 0 |
| **2.4 Thăm dò provider** | Tăng dần số lời gọi đồng thời từ 10 lên 24, ghi 429 và độ trễ | 0 lỗi 429 ở mức P của hồ sơ. Nếu có 429 thì hạ P | khoảng 150 |
| **2.5 Gate đầy đủ trên VPS** | `gate run` đầy đủ một lần | Gate PASSED | khoảng 2.500 |
| **2.6 Canary** | 100 người × 2 lượt với provider thật | Thành công ≥ 98%, 0 lỗi 429, chi tiêu ≤ trần, ledger khớp số lời gọi | khoảng 800 |
| **2.7 Mở cho người dùng** | Trỏ tên miền và bật HTTPS. Giám sát: health, tỉ lệ 503, `vector_failed`, chi tiêu ngày. Sao lưu hằng ngày, có bản lưu ngoài server | Thử khôi phục một lần trên VPS. Cảnh báo chi tiêu hoạt động | 0 |
| **2.8 Theo dõi tuần đầu** | Xem log hằng ngày: lượt lỗi, 503, `vector_failed`, chi phí thật so với dự đoán | Báo cáo số thật so với dự đoán | 0 |

Đường lùi: máy này vẫn giữ nguyên hồ sơ `local`. Nếu cloud có sự cố, quay lại chạy local trong khi sửa.

### 2.2 Tổng chi phí giai đoạn 2

| Khoản | Ước tính |
|---|---|
| Kiểm thử trả phí (2.4–2.6) | khoảng 3.450 lời gọi ≈ 3 USD |
| VPS 4 vCPU / 8 GB | khoảng 770.000 VND/tháng (VPS VN) hoặc khoảng 48 USD/tháng (DigitalOcean) |
| Tiền gọi model khi chạy thật | khoảng 0,0034 USD mỗi câu hỏi; giảm thêm sau khi áp L1/L2 |

---

## Bằng chứng và báo cáo

- Mỗi bước ghi lại: lệnh đã chạy, mã thoát, file kết quả (`evals/results/...`), số đo trước và sau.
- Tải giả dùng provider giả có độ trễ lấy từ ledger thật. Gate dùng bộ câu hỏi có đáp án đã kiểm bằng code.
- Chưa đo được bằng phương pháp này: hành vi người dùng thật, hiệu năng VPS cụ thể (chỉ biết sau 2.3), giới hạn tốc độ của provider (chỉ biết sau 2.4).
