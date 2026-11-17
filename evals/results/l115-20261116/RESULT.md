# Bước 1.15: giảm lời gọi trả phí (L1, L4, L2), đo bằng provider thật (2026-11-16)

Đo bằng `rag_regression_gate.py run --quick` (133 lượt: safety 20, stop 35, core 78) trên runtime local, provider thật qua gateway sidecar, đếm lời gọi bằng sổ cái (`evals/runners/ledger_window.py`, mỗi lời gọi có route). Cơ sở: 463 lời gọi cho 133 lượt, tức **3,48 lời gọi mỗi lượt** (grounded_faq 149, sensitive_classifier 133, route_intent 121, kiểm ngữ nghĩa 60).

## L4: cache tiền tố prompt ở provider — đã có sẵn, không cần đổi code
Provider tự cache tiền tố. Sổ cái giờ ghi thêm `cached_input_tokens` mỗi lời gọi (`scripts/run_public_rag.py`). Trên 463 lời gọi: **89,8 % token vào được phục vụ từ cache** (937 nghìn trên 1,04 triệu), theo route: grounded_faq 94,5 %, kiểm ngữ nghĩa 83,7 %, route_intent 82,6 %, sensitive_classifier 73,0 %. Số lời gọi không đổi, giá token giảm sẵn; phần việc là đo, đã đo.

## L1: bỏ kiểm ngữ nghĩa khi mọi phát biểu là đoạn trích nguyên văn — làm xong, **để tắt**
Mã: `rag_v2/verification/verbatim.py`, nối trong `rag_v2/service.py`; công tắc `CAMPUS247_RAG_SKIP_VERBATIM_SEMANTIC` = `off` (mặc định) | `shadow` | `on`. Điều kiện: mỗi phát biểu là đoạn trích của đúng một nguồn được dẫn (≥ 20 ký tự, có từ của câu hỏi), phạm vi không bị nới, không thiếu slot.
- Chế độ shadow (vẫn hỏi mô hình rồi so): trên 60 lần kiểm ngữ nghĩa chỉ **8 lần (13 %)** đủ điều kiện, mô hình đồng ý cả 8. Tiết kiệm tối đa khoảng **1,7 % số lời gọi**, thấp hơn nhiều so với ước tính 17,5 % của thiết kế, vì câu trả lời của mô hình hầu hết là diễn đạt lại chứ không trích nguyên văn.
- Bật `on` cùng L2: 4 lần chạy gate, **2 đạt, 2 trượt**; cả hai lần trượt có đúng một câu trả lời **sai** ở suite core (`NAT-R2-Q1-0033-scenario`: nói B+ là 7,0–7,9 thay vì 8,0–8,4). Chín lần chạy khác với L1 tắt hoặc shadow không có câu sai nào. Chưa chứng minh được nguyên nhân (mẫu nhỏ), nhưng lợi ích 1,7 % không đáng rủi ro này: **không bật L1**.

## L2: cache câu trả lời cho câu hỏi lặp — làm xong, **để tắt mặc định**
Mã: `rag_v2/answer_cache.py`, nối trong `agent/nodes/rag_v2.py`; công tắc `CAMPUS247_RAG_ANSWER_CACHE` (`off` mặc định). Khóa = dấu vân tay tập nguồn được phép + câu hỏi đã chuẩn hóa + phiên bản prompt; chỉ lưu câu trả lời đủ, có trích dẫn, một lượt; TTL 6 giờ, 512 mục mỗi worker. Router và safety vẫn chạy mỗi lượt; sau khi trúng cache vẫn kiểm lại nguồn được dẫn và output guard.
- Chỉ L2 bật, chạy gate hai lần liên tiếp: lần nguội **GATE PASSED** (464 lời gọi, như cơ sở); lần nóng (cùng 133 câu hỏi lặp lại) 424 lời gọi, **giảm 8,6 %** (grounded_faq 149 → 129, kiểm ngữ nghĩa 61 → 41, 20 lượt trúng cache), không có câu sai, chỉ trượt vì 1 lượt lỗi hệ thống ở suite stop (xem dưới).
- Tỉ lệ trúng trong dùng thật **chưa đo** (chưa có người dùng thật); 8,6 % là của bài lặp lại toàn bộ câu hỏi, không phải dự báo.
- Rủi ro cần chủ dự án biết: một câu trả lời sai ngẫu nhiên của mô hình sẽ bị giữ tối đa 6 giờ. Vì vậy để tắt cho tới khi chủ dự án quyết định.

## Lỗi hệ thống chập chờn gặp trong lúc đo (chưa tìm ra gốc)
Khoảng 1 trên 100 lượt kết thúc bằng `AI_WORKFLOW_UNAVAILABLE` (hết ngân sách 30 s của lượt) và máy khách thấy lỗi 40–60 s. Gặp cả khi L1 và L2 đều tắt (hai lần chạy shadow) và cũng gặp ở lần chạy 2026-11-15 trước các thay đổi hôm nay (4 lỗi), nên không do L1 hay L2.
Ảnh chụp ngăn xếp lúc kẹt (log `graph_stalled`) cho thấy lượt đang chờ phản hồi của sidecar ở bước kiểm ngữ nghĩa; độ trễ provider trong sổ cái bình thường (p99 2,4 s, tối đa 4,4 s, 4 lời gọi hỏng trên 5.757). Chưa xác định vì sao lượt đến được bước đó muộn đến vậy.
Hệ quả cho cổng chất lượng: suite safety (20) và stop (35) trượt ngay nếu có 1 lỗi, nên mỗi lần chạy có khoảng 30–50 % khả năng trượt dù không có câu sai nào; vì thế các kết luận ở trên dựa trên câu sai và số lời gọi, không chỉ trên "PASSED".
Bổ sung quan sát (giữ lại): log `graph_failure kind=...`, `graph_stalled ...` và `stream_prepare_failure site=1 errors=<mã>`.

## Tóm tắt
| Đòn bẩy | Kết quả | Trạng thái |
|---|---|---|
| L4 | 89,8 % token vào đã từ cache; sổ cái ghi `cached_input_tokens` | xong (không cần đổi hành vi) |
| L1 | tiết kiệm tối đa 1,7 % lời gọi; bật cùng L2 thì 2/4 lần gate có câu sai | làm xong, tắt |
| L2 | −8,6 % lời gọi khi câu hỏi lặp; gate lần nguội PASSED | làm xong, tắt mặc định |

## Cập nhật cuối ngày: gốc của lỗi timeout chập chờn đã tìm ra và sửa

Bộ dò mới `infrastructure/loop_watchdog.py` (chạy trong mỗi worker API, ghi `loop_blocked ... at <hàm>`) cho thấy vòng lặp sự kiện của một worker **bị chặn 3–8 s liên tục trong `socket.accept()`** (hàng chục lần mỗi lần chạy gate: 481 báo cáo trong 6 lần chạy core). Hai worker dùng chung một socket lắng nghe mà ở mức hệ điều hành trên Windows nó ở chế độ chặn, còn asyncio gọi `accept()` lặp lại cho tới khi nhận "would block": worker thua cuộc (hoặc xin kết nối thứ hai) đứng yên cả vòng lặp tới khi có khách kế tiếp. Vòng lặp chết thì timeout của lượt cũng không chạy được, nên lượt trên worker đó chạm trần 30 s và trả `AI_WORKFLOW_UNAVAILABLE`. Tải mô phỏng không thấy vì khi có nhiều kết nối liên tục, khách kế tiếp đến ngay.
Một lần thử "ép non-blocking" không đủ (vẫn 287 báo cáo). Sửa đúng: `scripts/knowledge_platform.py::_serialize_accepts_between_workers` (chỉ Windows; Linux dùng chung cờ O_NONBLOCK nên không bị): các worker lần lượt accept qua khóa tệp, chỉ accept khi socket sẵn sàng đọc và chỉ một kết nối mỗi lần.
Kết quả: **0 báo cáo `loop_blocked`, 0 `graph_failure`**, gate nhanh **PASSED 2/2** (kể cả không lỗi nào ở safety/stop), kiểm tra tải 600 kết nối đồng thời không lỗi liên quan (các 503 đó là kiểm tra sẵn sàng hết pool Postgres, không phải accept).
Hệ quả: các số "gate trượt vì 1 lỗi" ở trên đều do lỗi này, không do L1/L2. Câu sai B+ khi bật L1 vẫn là quan sát riêng nên L1 vẫn để tắt.
Sửa kèm: `BackgroundLeader` đợi `1,5 × check_s` sau khi lấy khóa rồi mới chạy việc nền, để leader cũ chắc chắn đã dừng (bài test chuyển leader chập chờn 2/4 lần vì hai leader chạy chồng ngắn; nay 6/6 đạt).
Regression Windows toàn bộ trên mã cuối: `evals/results/final-regression-20261116b/` (113 mục = 112 mục mốc + 1 test leader chập chờn, nay đã sửa và đạt khi chạy riêng và cùng nhóm).

## Đo lại L1 + L2 sau khi sửa hạ tầng (`l1l2-on-fixed/`)
Cùng cấu hình bật L1 và L2, gate nhanh chạy 2 lần liên tiếp (nguội rồi nóng): **cả hai PASSED**, không câu sai, không lỗi, 0 `loop_blocked`, 0 `graph_failure`. Lời gọi: 454 (nguội, cơ sở 463, −1,9 %, chủ yếu từ L1: kiểm ngữ nghĩa 60 → 51) và 402 (nóng, −13 %: grounded_faq 149 → 122, kiểm ngữ nghĩa 26; 29 lượt trúng cache, 16 lần L1 bỏ qua).
Tổng cộng với L1 bật: 6 lần gate, 4 đạt và 2 có câu B+ sai (cả hai trước khi sửa hạ tầng). Với L1 tắt hoặc shadow: 0 câu sai trên 9+ lần. Mẫu còn nhỏ nên **kết luận giữ nguyên: L1 để tắt (lợi ích ≤ 2 % lời gọi), L2 để tắt mặc định cho chủ dự án quyết định**; cả hai bật được bằng một biến môi trường và đã có đường đo (`ledger_window.py`).
