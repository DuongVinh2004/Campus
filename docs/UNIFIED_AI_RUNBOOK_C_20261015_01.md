# Runbook kiểm chứng C — batch 20261015-01

**Observed final03:** [report C](UNIFIED_AI_PARALLEL_C_20261015_03.md) ghi các command thực đã chạy: `snapshot 03` stable1069 files; `verify combined 03` exit1,854/859 với5 original process-namespace failures; `frontend prepare/build/typecheck 03` exit0, BUILD_ID `uunQdK30YZKwHBmdmoZkW`, guard nguyên byte. Không dùng lại attempt03 hoặc snapshots dở01/02.75 C cases đạt không thay năm failure gốc; deadline50ms pass final nhưng từng fail scoped/historical, chưa fixed. UNI-040 chưa có actual persisted temporary-chat consumer; chế độ không rõ fail closed. Memory context chỉ resource-context explicit stores; deadline tracking thiếu sourced consumer503, remote channels unavailable. Chưa kiểm UI/pilot hoặc launch serving runtime. Final evidence/handoff/preservation và exact metadata diff được liên kết trong report03; các khối lệnh chuẩn bị dưới đây không tự chứng minh đã chạy.

Ngày15/10/2026, Asia/Bangkok. Chỉ áp dụng workspace `C:\Users\Duong Vinh\Vinh`, local synthetic fixtures trong namespace C. Đây là hướng dẫn kiểm chứng đã chuẩn bị; không xác nhận đã launch hay deploy candidate. Runtime đang phục vụ chưa được xác minh trong C. Không stop/restart/reload, paid/provider, UI tests hoặc production actions.

Tiếp tục02 đã chạy scoped current-consumer regressions (`independent07–09`), `unified_parallel_c_compare.py 04` và `unified_parallel_c_case_measure.py 01` trên fixtures mới. [Report02](UNIFIED_AI_PARALLEL_C_20261015_02.md) ghi command/exit/limitations. `unified_parallel_c_verify.py scoped NN` là early broad regression trước final handoff; chỉ `combined NN` sau stable final snapshot mới được xét final integration evidence. Mọi attempt/output phải mới; không reuse snapshot01/02 dở. Không dùng local fixture đo được làm production benchmark hoặc user usefulness.

## Kỹ sư kiểm chứng

Đọc report C, immutable `stream-a/handoffs`, `stream-b/handoffs`, B integration requests và A integration acks trước kết luận. So hashes với actual files/composition/API/UI source. Registrar/schema/core pass đơn lẻ không đủ công bố capability đã implemented.

Commands từ workspace, dùng Python hiện có, không install/update:

```powershell
.venv/Scripts/python.exe -B scripts/unified_parallel_c_preserve.py init
.venv/Scripts/python.exe -B scripts/unified_parallel_c_evaluate.py prepare 01
.venv/Scripts/python.exe -B scripts/unified_parallel_c_verify.py independent 01
.venv/Scripts/python.exe -B scripts/unified_parallel_c_evaluate.py smoke 01
```

`init` chỉ chạy khi namespace chưa tồn tại; các số attempt phải mới và không ghi đè. Giữ toàn bộ fixture/log/XML/failure. Nếu local TestClient bị sandbox chặn, giữ log và dùng attempt mới có quyền local socket; không thay expected hoặc serving runtime. Đọc command.json/report.json để biết command nào thực sự chạy và exit code, không coi khối hướng dẫn này là evidence.

Sau final handoffs A/B và review actual hashes, tạo `snapshot NN` bằng preserve script, chạy `combined NN` bằng verify script. Runner từ chối thiếu final handoffs hoặc source snapshot không khớp. Final evidence còn cần fresh frontend snapshot, `tsc --noEmit --incremental false` và production build với `preserve-build.mjs` nguyên byte; không build ở `apps/web`. Snapshot source là preimage/hash reference, không giả complete runtime environment. Nếu source đổi giữa checks, giữ attempt đó như scoped evidence và tạo attempt mới sau revision. Không cộng XML lịch sử/A+B totals; latest unique `(classname,name)` và giữ lỗi nền deadline50ms riêng dù rerun may pass.

`preserve ... audit NN` đọc retained DB bằng `mode=ro`, query_only/consistent transaction và so schema/all-table/row digests; so paid/native metadata, build guard và Git entries. Không instantiate writer/init/migrate retained DB. Hash/digest không xuất raw row data.

## Sinh viên / cán bộ: hành vi cần kiểm trước khi hướng dẫn dùng thật

Sinh viên chọn đúng tài khoản/case; nêu goal; xem fact provenance, missing fields và diff; giữ manual changes; chỉ confirm sau preview đúng payload/recipient/version. Khi timeout, đọc receipt/state trước retry. New chat, memory off và forget suppression không xóa history. Chưa có UI evidence nên các bước này là script kiểm, không xác nhận UX dùng được.

Cán bộ kiểm queue/assignment/source versions và mandatory criteria; readiness là đối chiếu nội bộ, không quyết định hành chính. Notes riêng không đưa vào public response. Typed supplement phải chọn item/reason/source, preview và confirm; kết quả phải có structured outcome/template/recipient và business receipt. Transfer/revoke/source drift yêu cầu đọc lại và tạo preview hợp lệ mới; giữ nháp cũ để phục hồi nội dung.

Memory chỉ bật bằng explicit opt-in theo actor và consumer thật. Forget dùng suppression/tombstone có version/provenance, không physical delete history/index/backup. Temporary phải fail closed nếu không biết mode. Notification chỉ local in-app khi resource/trigger/channel/recipient/grant đã kiểm; no-change im lặng; stop/revoke phải chặn delivery sau. Chưa có handoff consumer tương ứng thì báo unavailable và bước thủ công, không hứa notification.

## Phục hồi và hỗ trợ

Giữ pending text khi CAS/error; đọc saved version/receipt bằng đúng actor/resource trước retry; stable idempotency key theo intent. Ghi minimal case/version/command/exit/error/evidence refs vào findings C cho owner A/B, không sửa source ngoài ownership. Storage/corrupt/missing consumer trả503 hoặc conflict theo contract, không fake empty success. Không reset/cleanup DB/cache/build/log để làm xanh.

Support: chưa có đầu mối tổ chức/production được xác minh. Các lỗi kỹ thuật trong batch chuyển bằng artifact `stream-c/findings`, không gửi cross-chat/email/Slack. UI/pilot/human usefulness/institutional sources/distributed production recovery và launch result đều pending.048 full rehearsal cần043/047,049/050 full acceptance giữ dependencies đó.
