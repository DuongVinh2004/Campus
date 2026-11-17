# Thiết kế chịu tải 100 người dùng: một mã nguồn chạy trên máy này và trên cloud 4 vCPU / 8 GB (2026-11-15)

Trạng thái: **đề xuất**, chưa triển khai.

Bằng chứng: số đo trên máy này với provider giả (`evals/load/fake_provider.py`). Độ trễ của provider giả lấy từ 25.817 lời gọi thật trong ledger. Phần còn lại của pipeline chạy thật: retrieval, embedding, guard, Postgres, ledger (ghi vào thư mục nháp). Không tốn lời gọi trả phí nào.

Chưa đo:
- hành vi người dùng thật;
- giới hạn tốc độ của provider thật;
- hiệu năng trên VM cloud.

Số liệu cho cloud trong tài liệu này là **ước tính** và phải đo lại theo mục 8.

## 1. Nguyên tắc

1. **Một mã nguồn, hai hồ sơ cấu hình.** Máy này và cloud chỉ khác nhau ở file hồ sơ: số worker, giới hạn, biến thể model, đường dẫn. Không có nhánh code riêng cho từng nơi.
2. **Một máy, nhiều tiến trình.** Cả hai nơi đều chạy trên một máy. Không cần load balancer, Redis hay Postgres được quản lý riêng.
3. **Hệ thống tự co theo tài nguyên.** Khi hết sức, nó từ chối sớm và rõ ràng ("Hệ thống đang bận") thay vì treo hoặc bị OOM kill. Ổn định quan trọng hơn số người phục vụ tối đa.
4. **Chất lượng là cổng chặn.** Mọi thay đổi có thể ảnh hưởng câu trả lời phải qua regression gate, và kiểm recall miễn phí trước. Giữ nguyên:
   - bound 5 s cho mỗi lời gọi provider;
   - ngân sách 22 s cho mỗi lượt;
   - các bộ safety/stop chặt;
   - xác thực, phân quyền, xác nhận hành động, kiểm nguồn.

## 2. Hiện trạng đo được (máy này)

Máy: 6 lõi vật lý (12 luồng), 15,6 GB RAM.

| Thành phần | CPU mỗi lượt | RAM riêng (private) | Ghi chú |
|---|---|---|---|
| API (1 tiến trình) | 0,448 s | 870 MB | Bị GIL giới hạn ở khoảng 1 lõi, tức tối đa khoảng 111 lượt/phút |
| Máy chủ mô hình | 0,632 s | **2,9 GB** | Nạp bge-m3 FP32 (2,16 GB trọng số) **và** reranker (2,27 GB). Có một khóa toàn cục, embed p50 157 ms, chạy tuần tự, khoảng 1 lần embed mỗi lượt |
| Postgres | 0,106 s | khoảng 300 MB | |
| Frontend Next.js | không đáng kể | khoảng 80–200 MB | |
| **Tổng** | **1,19 s** | **khoảng 4,2 GB** | |

Kết quả ở 100 người dùng nghĩ 8–25 s, provider giả:

| Lượt/phút | Thành công | p50 | p95 | Ghi chú |
|---|---|---|---|---|
| 111,6 | 93% | 24 s | 35,6 s | 21 lỗi đều là lượt mất 32–43 s, tức quá tải xếp hàng |

Hai rủi ro phát hiện khi đo:
- **Mất chất lượng thầm lặng.** `hybrid.retrieve` chờ embedding 1,0 s rồi chuyển sang chỉ dùng lexical. Khi khóa embedding xếp hàng, nhánh vector rớt mà không có gì báo.
- **Reranker vẫn được dùng.** Engine v2 không dùng nó (`rerank_deadline_s=0`), nhưng đường v1 vẫn dùng: công cụ `search_knowledge` của multi-agent/staff gọi `runtime.py:524–529`. Nó không phải code chết.

## 3. Tải cần phục vụ

| Kịch bản | Chu kỳ một người | Lượt/phút |
|---|---|---|
| **A. Kiểm thử khắt khe** (nghĩ 8–25 s) | khoảng 22,5 s | 267 |
| **B. Người thật** (đọc và gõ 45–90 s, giả định chưa đo) | khoảng 74 s | khoảng 81 |

## 4. Kiến trúc chung cho cả hai nơi

```
trình duyệt ─► frontend ─► API (uvicorn --workers N, dùng chung một cổng; OS tự chia kết nối)
                             │   · admission control: tối đa K lượt đang chạy mỗi worker, chờ ≤ 5 s, quá thì 503 "đang bận"
                             │   · rate limit dùng chung qua Postgres (giữ đúng 30/phút dù có N worker)
                             │   · worker giữ advisory lock của Postgres = leader chạy việc nền
                             ├─► gateway sidecar (1 tiến trình): giữ PaidLedgerWriterLease, giới hạn đồng thời P,
                             │     trần chi tiêu thật; bound 28.000 byte / 1000 token / 5000 ms giữ nguyên
                             ├─► máy chủ mô hình: embedding (+ cache vector truy vấn), reranker tùy hồ sơ
                             └─► Postgres (cùng máy)
```

| Thành phần | Thay đổi | Vì sao chạy được cả hai nơi |
|---|---|---|
| **Nhiều worker** | Chạy N worker uvicorn chung một cổng. API hiện khởi động bằng đối tượng app (`knowledge_platform.py:643`), nên phải tách thành app factory nạp qua import string trước | Windows (spawn) và Linux đều hỗ trợ. Không cần proxy |
| **Rate limit dùng chung** | Thêm một store Postgres cho `AbuseLimiterMiddleware`. Middleware đã nhận `store=` nên chỉ cần thay `InMemoryRateLimiterStore` | Postgres có ở cả hai nơi. Giữ `fail_closed=True` |
| **Leader việc nền** | `owned_lifespan` (scheduler, learning, OCR) chỉ chạy ở worker giữ `pg_try_advisory_lock`. Worker khác bỏ qua | Không phụ thuộc hệ điều hành. Leader chết thì lock nhả và worker khác nhận |
| **Gateway sidecar** | Tách `run_public_rag` thành tiến trình riêng. API gọi qua loopback, có token nội bộ | Lease ledger chỉ có một chủ. Test bắt buộc: mỗi lời gọi ghi đúng 1 lần; sidecar chết thì API báo lỗi rõ, không gọi thẳng provider |
| **Admission control** | Giới hạn số lượt đang chạy mỗi worker, chờ ≤ 5 s | Hệ thống co lại an toàn trên máy yếu |
| **Cache vector truy vấn** | LRU theo (truy vấn đã chuẩn hóa, revision của model) | Kết quả trùng khớp tuyệt đối. Giảm CPU và giảm xếp hàng embedding |
| **Chỉ số `vector_failed`** | Đếm và log tỉ lệ nhánh vector hết giờ | Ngưỡng chấp nhận ≤ 1% |
| **Kiểm tra RAM khi khởi động** | Launcher cộng RAM dự kiến của hồ sơ, từ chối khởi động nếu vượt RAM còn trống | Tránh OOM giữa chừng trên VM nhỏ |

Phải kiểm kê trước khi bật nhiều worker. Đã kiểm sơ bộ:
- hàng đợi tiến độ chat trong `presentation/chat.py` thuộc riêng từng request, lịch sử đọc từ store, nên không cần chia sẻ;
- memo của runtime và publication có TTL, mỗi worker giữ bản riêng là chấp nhận được;
- các kho SQLite dùng chung file trên cùng máy, ghi được tuần tự hóa.

Vẫn cần rà hết trạng thái module-level khác: idempotency, xác nhận hành động, phiên đăng nhập.

## 5. Hai hồ sơ cấu hình (đã chốt cloud 4 vCPU / 8 GB, 2026-11-15)

| Tham số | `local` (máy này) | `cloud` (4 vCPU / 8 GB Linux, CPU không burstable) |
|---|---|---|
| API worker N | 3 | 2 |
| Lượt đang chạy tối đa mỗi worker K | 24 | 16 |
| Đồng thời tới provider P | 40 | 24 |
| Embedding | bge-m3 FP32, **giống hệt hiện tại** | bge-m3 FP32, cùng model và cùng index với `local` |
| Reranker (chỉ đường v1/staff) | Bật | Bật |
| Postgres | Như hiện tại | `shared_buffers=256MB`, `max_connections=40` |
| Frontend | `next start` | `next start` |
| Swap | — | File swap 2 GB, chỉ làm lưới an toàn |
| Giám sát tiến trình | `knowledge_platform_runtime.py` | Cùng launcher, khởi động qua systemd |

Với 8 GB, model và index **giữ nguyên như hiện tại** ở cả hai nơi. Không đổi gì có thể làm thay đổi câu trả lời, nên kết quả gate trên máy này áp dụng được cho cloud. INT8 (mục 6) chỉ còn là tùy chọn giảm CPU sau này.

### Ngân sách RAM cho cloud 8 GB (ước tính, phải đo lại)

| Thành phần | RAM |
|---|---|
| Hệ điều hành và dịch vụ hệ thống | 400 MB |
| Postgres | 350 MB |
| Frontend | 200 MB |
| Gateway sidecar | 100 MB |
| Máy chủ mô hình (FP32 embedding và reranker, đo 2,9 GB private) | 2.900 MB |
| 2 API worker (870 MB mỗi worker) | 1.800 MB |
| **Tổng** | **khoảng 5,75 GB** |
| Dư cho page cache, đỉnh tải, sao lưu | khoảng 2,25 GB |

Khi khởi động, launcher kiểm tra tổng RAM dự kiến của hồ sơ và từ chối chạy nếu RAM còn trống không đủ.

### Năng lực dự đoán trên cloud (ước tính)

CPU mỗi lượt tùy theo model embedding:
- **FP32 (đã chốt, giữ nguyên model):** API khoảng 0,35 s sau tối ưu, embedding 0,63 s (giảm khi cache trúng), Postgres 0,1 s, tổng **khoảng 1,0–1,1 s**;
- INT8 (tùy chọn): embedding ước tính 0,25–0,35 s, tổng khoảng 0,75 s.

vCPU cloud có thể chậm hơn lõi máy này 1–1,5 lần. Tính ở mức dùng 75% CPU:

| VM | Model | Lượt/phút ước tính | Kịch bản B (khoảng 81 lượt/phút) | Kịch bản A (267 lượt/phút) |
|---|---|---|---|---|
| 2 vCPU / 4 GB | INT8 (bắt buộc) | khoảng 80–120 | Vừa, sát ngưỡng | Không; admission trả "đang bận" |
| **4 vCPU / 8 GB (đã chốt)** | **FP32** | **khoảng 110–170** | **Dư 1,4–2 lần** | **Không đạt; admission trả "đang bận"** |
| 4 vCPU / 8 GB | INT8 | khoảng 160–240 | Dư | Gần đạt |
| Máy này, hồ sơ `local` | FP32 | khoảng 220–270 (6 lõi vật lý) | Dư | Sát ngưỡng; chỉ biết sau khi đo ở bước 1.9 |

Kết luận trung thực: trên VM rẻ, thiết kế nhắm tới **100 người dùng thật**, phục vụ ổn định và co lại an toàn khi bị dồn. Nó **không** nhắm tới 100 người bắn câu hỏi liên tục.

### Cấu hình khuyến nghị: 4 vCPU / 8 GB RAM, CPU chuyên dụng (không burstable)

| Cấu hình | Chạy được khi | Đánh giá |
|---|---|---|
| 2 vCPU / 4 GB | **Chỉ khi** INT8 qua cổng chất lượng và reranker tắt. 1 worker | Tối thiểu. CPU là điểm nghẽn, sát ngưỡng ở kịch bản B |
| 4 vCPU / 6 GB | INT8 và 2 worker. FP32 chỉ chạy được với 1 worker (khoảng 4,2 GB) | Tạm được |
| **4 vCPU / 8 GB** | **Cả FP32 lẫn INT8**, 2 worker (FP32 khoảng 5,1 GB, INT8 khoảng 3,5 GB) | **Khuyến nghị.** Chất lượng không phụ thuộc việc INT8 có qua cổng hay không. Còn chỗ cho swap/page cache. Kịch bản B dư sức |

Lý do chọn 4 vCPU / 8 GB:
- CPU quan trọng hơn RAM. VM rẻ loại "burstable/shared CPU" bị hạ tốc khi tải kéo dài, tránh loại này.
- Tiền gọi model ở kịch bản B là khoảng 16,5 USD cho một giờ cao điểm, lớn hơn nhiều so với chênh lệch tiền thuê giữa các cấu hình VM.

## 6. Embedding INT8: tùy chọn giảm CPU, không bắt buộc với 8 GB

Lợi ích ước tính:
- RAM giảm khoảng 4 lần, từ 2,2 GB xuống khoảng 0,6 GB;
- embed nhanh khoảng 2–3 lần.

Rủi ro: vector thay đổi. Vì vậy phải **embed lại cả 9.173 unit** bằng cùng model INT8; không trộn vector FP32 và INT8.

1. Lượng tử hóa model (dynamic INT8 của ONNX Runtime). Ghim checksum giống quy trình fixture hiện tại.
2. Embed lại index trên máy này: một lần, tốn CPU, không tốn tiền.
3. **Cổng miễn phí:** `rag_recall_probe.py`, yêu cầu top-12 ≥ 96,5% (hiện 97,3%) và top-5 ≥ 91,8% (hiện 92,6%).
4. **Cổng trả phí:** `gate run --quick`, rồi gate đầy đủ một lần.
5. Đạt thì dùng **cùng index INT8 ở cả hai nơi**. Một artifact duy nhất nên kết quả gate áp dụng được cho cả hai. Không đạt thì giữ FP32 ở máy này và xem lại cấu hình cloud (thuê 8 GB hoặc dịch vụ embedding ngoài, kèm gate riêng).

Lưu ý: binding ONNX hiện tại dùng DLL Windows được ghim checksum. Trên Linux cần một bản `.so` tương ứng, cũng được ghim checksum.

## 7. Việc phải làm để chạy được trên Linux (chưa kiểm hết)

| Việc | Ghi chú |
|---|---|
| Binding ONNX C-API | Hiện nạp `onnxruntime.dll` bằng `WinDLL`. Thêm `libonnxruntime.so` cùng phiên bản, giữ kiểm checksum. So khớp vector giữa Linux và Windows |
| Khóa ledger trả phí | `scripts/public_rag_ledger.py` dùng `msvcrt.locking`. Thêm nhánh `fcntl` cho Linux |
| Postgres | Launcher dùng bản Postgres đóng gói cho Windows (`pg_ctl.exe`, `initdb.exe`, `vector.dll`). Trên Linux dùng Postgres hệ thống với `pgvector` và `btree_gist` |
| Phụ thuộc Python | Runtime là Python 3.12.14 với `uv.lock`. numpy trong `data/rag_v2_vendor` là bản nhị phân Windows; trên Linux cài theo `uv.lock` |
| Kiểm tra đường dẫn (`checked_path`, reparse point) | Giữ nguyên quy tắc. Trên Linux dùng `is_symlink`/`is_junction` (3.12). Cần test |
| Launcher (`knowledge_platform_runtime.py`) | Loại bỏ chỗ gọi `powershell.exe`. Dùng `psutil` cho cả hai nơi. Kèm một unit systemd |
| Bảo mật khi ra Internet | Chỉ mở cổng 443 (HTTPS, reverse proxy nhẹ như Caddy). API, gateway, mô hình, Postgres chỉ nghe loopback. Khóa bí mật trong file env quyền 600. Không đưa file credential lên server |
| Sao lưu | Dump Postgres hằng ngày cộng ledger. Ledger hiện là khoảng 200 nghìn file nhỏ, cần gom hoặc nén theo ngày |
| Dữ liệu | Chỉ đưa lên cloud index công khai và dữ liệu cần thiết. Dữ liệu sinh viên thật lên cloud cần người dùng quyết định riêng |

## 8. Kế hoạch triển khai (cloud 4 vCPU / 8 GB)

> Kế hoạch chi tiết hai giai đoạn (local sẵn sàng cho cloud, rồi deploy khi người dùng thông báo) nằm ở [ROLLOUT_PLAN_LOCAL_THEN_CLOUD_20261115.md](ROLLOUT_PLAN_LOCAL_THEN_CLOUD_20261115.md). Bảng dưới là bản tóm tắt.

Nguyên tắc thứ tự:
- làm hết trên máy này trước;
- thử bằng provider giả, không tốn tiền;
- chỉ thuê server khi bản Linux đã chạy đạt trong môi trường giả lập 4 CPU / 8 GB;
- lời gọi trả phí dồn vào cuối, mỗi lần đều có mục đích rõ.

Mỗi giai đoạn kết thúc bằng test và bài đo. Chưa đạt thì chưa sang giai đoạn sau.

| # | Giai đoạn | Việc chính | Kiểm chứng để qua | Trả phí |
|---|---|---|---|---|
| G0 | Chốt mốc xuất phát | Commit phần tối ưu hiệu năng đã làm lên một nhánh riêng (cần anh đồng ý). Lưu số đo hiện tại làm mốc | Test hiện có đạt, mốc đo được lưu | 0 |
| G1 | Ổn định 1 tiến trình | Admission control (K lượt, chờ ≤ 5 s, 503 "đang bận"). Chỉ số `vector_failed`. File hồ sơ `local`/`cloud`. Kiểm tra RAM khi khởi động | Tải giả 100 người: không lượt nào > 22 s; quá tải trả 503 trong ≤ 5 s | 0 |
| G2 | Nhiều tiến trình | Rà trạng thái module-level. Store rate limit trên Postgres. Leader bằng advisory lock. Gateway sidecar giữ ledger. `uvicorn --workers 3` | Tải giả kịch bản A: thành công ≥ 99%, p95 ≤ 15 s. Giết 1 worker, giết sidecar, kiểm ledger ghi đúng 1 lần | 0 |
| G3 | Giảm CPU | Cache vector truy vấn. Memo kiểm đường dẫn. Dùng lại kết nối SQLite. `_build_index` từ index đầy đủ. Mục tiêu ≤ 0,8 s mỗi lượt | Test tương đương (cùng đầu vào cho cùng kết quả). Đo CPU từng thành phần | 0 |
| G4 | Cổng chất lượng lần 1 | `gate run --quick` trên kiến trúc mới, provider thật | Gate PASSED: safety/stop không giảm | khoảng 600 |
| G5 | Port Linux | Binding ONNX `.so` có checksum. Launcher dùng `psutil`. Kiểm đường dẫn trên Linux. Unit systemd. Caddy HTTPS. File env quyền 600. Script sao lưu | Toàn bộ test chạy trên Linux (WSL2). Giả lập **4 CPU / 8 GB** (WSL2 hoặc container có giới hạn): tải giả kịch bản B và A đạt mục 10 | 0 |
| G6 | Thuê VM và đo | Thuê VPS 4 vCPU / 8 GB theo tháng hoặc giờ, dùng thử hoặc còn hoàn tiền. Triển khai bằng script của G5. Chạy tải giả **ngay trên VM** | Đạt mục 10 trên VM thật. Không đạt thì đổi nhà cung cấp trong hạn hoàn tiền | 0 (chỉ tiền thuê) |
| G7 | Kiểm với provider thật trên VM | Thăm dò mức đồng thời của provider (10→24). Gate đầy đủ một lần. Canary 100 người × 2 lượt | 0 lỗi 429, thành công ≥ 98%, gate PASSED, chi tiêu ≤ trần | khoảng 3.450 |
| G8 | Mở cho người dùng | Chỉ mở cổng 443. Giám sát: health, tỉ lệ 503, `vector_failed`, chi tiêu ngày. Sao lưu hằng ngày. Runbook khôi phục | Thử khôi phục từ bản sao lưu một lần | 0 |
| G9 | Giảm lời gọi (sau khi chạy ổn) | L1, L4, rồi L2 (mục 9), mỗi cái `--quick` gate | Gate PASSED; số lời gọi mỗi lượt giảm đúng như đo | khoảng 600–1.200 |
| | **Tổng trả phí** | | | **khoảng 4.650–5.250 lời gọi ≈ 4–5 USD** |

Quyết định cần anh đưa ra (chỉ chặn đúng giai đoạn liên quan):

| Quyết định | Chặn giai đoạn |
|---|---|
| Có commit phần tối ưu đã làm lên nhánh riêng không | G0 |
| Trần chi tiêu thật cho gateway, ví dụ theo ngày | G2 (đặt giá trị), G7 (bắt buộc) |
| Duyệt ngân sách kiểm thử trả phí khoảng 4–5 USD | G4, G7, G9 |
| Chọn nhà cung cấp VPS cụ thể; anh tự thuê và thanh toán | G6 |
| Dữ liệu nào lên cloud: chỉ index công khai, hay cả tài khoản và dữ liệu sinh viên thật | G6 |
| Tên miền cho HTTPS | G8 |

## 9. Giảm lời gọi trả phí (giống nhau ở cả hai nơi, mỗi cái qua gate)

Hiện mỗi lượt tốn khoảng 4,1 lời gọi, khoảng 9,9 nghìn token vào, khoảng 0,0034 USD.

| # | Đòn bẩy | Giảm | Rủi ro |
|---|---|---|---|
| L1 | Bỏ kiểm ngữ nghĩa khi mọi phát biểu là đoạn trích nguyên văn của unit được dẫn (kiểm bằng code) | tối đa 17,5% lời gọi | Rất thấp |
| L4 | Cache tiền tố prompt ở provider, nếu provider hỗ trợ | Giảm giá token | Không |
| L2 | Cache câu trả lời cho câu hỏi công khai một lượt, lặp lại. Khóa theo release/policy generation, scope, phiên bản prompt. Vẫn chạy safety mỗi lượt | khoảng 3 trên 4 lời gọi khi trúng | Thấp. Tỉ lệ trúng thực tế chưa đo |
| L3 | Gộp router và safety vào một lời gọi | khoảng 24% | Trung bình; safety chặt |
| L5 | Đóng gói ít unit hơn khi độ tin cậy cao | Giảm token | Trung bình |

## 10. Tiêu chí chấp nhận

| Bài kiểm | Ngưỡng |
|---|---|
| `local`, provider giả, kịch bản A | Thành công ≥ 99%, p95 ≤ 15 s, không lượt nào > 22 s, `vector_failed` ≤ 1%, 503 ≤ 1% |
| `cloud` (giả lập 4 CPU / 8 GB, rồi VM thật), kịch bản B | Thành công ≥ 99%, p95 ≤ 15 s, RAM đỉnh ≤ 85%, không có OOM, không dùng swap trong trạng thái ổn định |
| `cloud`, kịch bản A | Không sập, không OOM. Lượt quá tải nhận 503 "đang bận" trong ≤ 5 s, không lượt nào treo > 22 s |
| Chịu lỗi | Một worker chết thì phần còn lại vẫn phục vụ và leader chuyển giao. Sidecar chết thì báo lỗi rõ, không có lời gọi nào ngoài ledger |
| Chất lượng | Recall INT8 đạt ngưỡng ở mục 6. Regression gate PASSED: safety/stop không giảm |
| Provider thật | Canary: thành công ≥ 98%, 0 lỗi 429, chi tiêu ≤ trần |

## 11. Chọn nơi thuê và chi phí (tra ngày 2026-11-15)

Giá dưới đây lấy từ trang tổng hợp và trang của nhà cung cấp. Có nguồn mâu thuẫn nhau; phải xác nhận lại trên trang chính thức trước khi mua.

### Điều quan trọng nhất về chất lượng: loại CPU, không phải tên hãng

Tải của hệ thống là CPU kéo dài (embedding và xử lý mỗi lượt). Có ba loại CPU:
- **burstable**: chạy bằng tín dụng CPU, hết tín dụng thì bị hạ tốc;
- **shared**: CPU dùng chung với máy khác, bị "steal time";
- **dedicated**: CPU riêng.

Khi đông người, CPU burstable hoặc shared làm p95 tăng vọt. Nơi nào cũng phải chạy bài thử tải giả (P6) trên VM thật **trong thời gian dùng thử hoặc hoàn tiền**, trước khi trả dài hạn.

### So sánh cấu hình khoảng 4 vCPU / 8 GB

| Nơi | Gói | Giá/tháng | CPU | Nhận xét |
|---|---|---|---|---|
| VPS Việt Nam (Viethosting KVM) | 4 vCPU + 8 GB, giá theo thành phần | khoảng 768.000 VND (khoảng 30 USD) | Shared, chất lượng chưa rõ | **Rẻ nhất**, gần người dùng, dữ liệu nằm trong nước. Phải đo CPU trước |
| VPS Việt Nam (Vinahost Cloud 8G) | 4 vCPU / 11 GB | khoảng 74 USD | Chưa rõ | Đắt hơn VPS VN khác |
| DigitalOcean Singapore | Basic 4 vCPU / 8 GB | khoảng 48 USD | Shared | Ổn định, dễ dùng, tính tiền theo giờ |
| DigitalOcean Singapore | CPU-Optimized 4 vCPU / 8 GB | khoảng 80–109 USD (nguồn mâu thuẫn) | Dedicated | Chất lượng CPU tốt nhất nhóm này, đắt |
| Hetzner Singapore | CCX13: 2 vCPU dedicated / 8 GB | khoảng 54 EUR (tăng giá từ 15/06/2026) | Dedicated | Hết rẻ ở Singapore; băng thông chỉ 1 TB |
| AWS Lightsail | 2 vCPU / 8 GB | 44 USD | **Burstable** | Không hợp tải kéo dài. Gói 4 vCPU / 16 GB là 84 USD |
| GCP Singapore | e2-standard-2 (2 vCPU / 8 GB) | khoảng 60 USD | Shared-core động | Đắt so với cấu hình. e2-standard-4 khoảng 120 USD |
| Oracle Always Free | ARM Ampere, nay còn khoảng 2 OCPU / 12 GB | 0 | ARM | Có rủi ro thu hồi khi ít dùng, khó xin capacity, phải port sang ARM. Chỉ hợp để thử |
| Azure for Students | 100 USD tín dụng (GitHub Student Pack) | 0 trong lúc còn tín dụng | Tùy gói, B-series là burstable | Hợp để chạy P6/P7 thử trên cloud thật |

AWS và GCP có lợi thế về dịch vụ quản lý. Với một VM duy nhất, lợi thế đó không đáng tiền: cùng cấu hình mà giá cao hơn 1,5–3 lần.

### Chọn RAM

| RAM | Tiết kiệm so với 8 GB | Đánh đổi |
|---|---|---|
| 4 GB | khoảng 10–20 USD/tháng | Bắt buộc INT8 và tắt reranker. Chỉ 1 worker. Nếu INT8 không qua cổng chất lượng thì không có đường lùi |
| 6 GB | ít, và ít nhà cung cấp có gói này | Model FP32 chỉ chạy được với 1 worker |
| **8 GB** | — | **Chọn mức này.** Chạy được cả FP32 lẫn INT8, 2 worker, còn dư cho cache và sao lưu |

### Tổng chi phí hằng tháng: tiền gọi model là phần lớn

Tiền gọi model khoảng 0,0034 USD mỗi câu hỏi (giá bảo thủ, chưa áp đòn bẩy L1–L5).

| Số câu hỏi/tháng | Tiền gọi model | Cộng VPS VN khoảng 30 USD | Cộng DO Basic 48 USD |
|---|---|---|---|
| 5.000 | khoảng 17 USD | khoảng 47 USD | khoảng 65 USD |
| 20.000 (ví dụ 2.000 SV × 10 câu) | khoảng 68 USD | khoảng 98 USD | khoảng 116 USD |
| 50.000 | khoảng 170 USD | khoảng 200 USD | khoảng 218 USD |

Hệ quả: tiết kiệm 10–20 USD ở server ít tác dụng hơn nhiều so với giảm lời gọi model (L1, L2). Đầu tư server đủ mạnh để giữ chất lượng là hợp lý.

### Khuyến nghị

1. **Thử miễn phí trước:** mô phỏng 4 GB / 2 CPU trên máy này (P6). Sau đó dùng tín dụng Azure for Students để chạy thử trên cloud thật.
2. **Chạy chính thức:** VPS Việt Nam KVM **4 vCPU / 8 GB** (khoảng 700–800 nghìn VND/tháng), với điều kiện bài thử tải trên VM đó đạt tiêu chí ở mục 10. Không đạt thì chuyển sang **DigitalOcean Singapore 4 vCPU / 8 GB** (khoảng 48 USD).
3. **Dữ liệu cá nhân:** đặt server ở Việt Nam giảm câu hỏi về chuyển dữ liệu ra nước ngoài. Câu hỏi của sinh viên vẫn được gửi tới provider model ở nước ngoài, nên điều này cần nhà trường xác nhận riêng; đây không phải tư vấn pháp lý.

## 12. Giới hạn của dự đoán

- Số liệu cho cloud là ước tính từ máy này. vCPU thật có thể chậm hơn; P6 và một lần đo trên VM thật sẽ chốt số.
- Mức tăng tốc và chất lượng của INT8 chưa đo trên corpus này.
- Kịch bản B dùng thời gian nghĩ giả định. Tải giả lặp câu hỏi nên các cache theo câu hỏi trông hiệu quả hơn thực tế.
- Provider giả không mô phỏng giới hạn tốc độ của provider thật.
