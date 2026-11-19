# Campus 24/7 — runbook chặng multi-agent tích hợp 2–3–4

> Runbook guarded lịch sử. Runtime live hiện tại và continuation ledger ở [runbook live](MULTI_AGENT_LIVE_RUNBOOK_20261013.md). Không khởi động writer cũ để thay runtime live hoặc reset caps.

Phạm vi: local/synthetic, kiến trúc Coordinator/Research/Verifier và service giấy xác nhận. Không có benchmark so sánh kiến trúc. [Bàn giao](MULTI_AGENT_INTEGRATED_DELIVERY_20261013.md).

## Runtime hiện tại và dữ liệu

- Giao diện/API riêng: **http://localhost:8003/login**, frontend 3003, build `frontend02`.
- Chế độ đang phục vụ: **guarded**. Hỏi quy định đi vào workflow multi-agent nhưng admission dừng trước inference vì headroom hiện tại thiếu. Điều hướng tĩnh và nghiệp vụ giấy xác nhận vẫn dùng application services. Đây chưa phải runtime RAG multi-agent live được nghiệm thu.
- `scripts/run_multi_agent.py` là entrypoint; `scripts/launch_multi_agent.py` mở process mới và receipt/log mới, từ chối cổng bị chiếm.
- DB run/task/event/cache mới: `infra/local/multi-agent-integrated-20261013-01/agent-runs.sqlite3`.
- Giữ DB hồ sơ `infra/local/certificate-stage1-20261013-01/demo.sqlite3` và lịch sử `infra/local/public-rag-20261013/conversations.sqlite3`. Chỉ append records được cấp quyền; không migration phá hủy.
- Giữ API8000 (paid writer), API8002/front3002, BGE18081/18082, front3000/3001. Không mở Gateway thứ hai, dừng runtime cũ hoặc đổi/reset ledger để thử tính năng.

Các receipt `*-launch.json` ghi PID launcher. Trên Windows venv có thể tạo child Python khác giữ cổng; phải đối chiếu cả PID listening, command và parent trước restart. Chỉ restart process do chặng này tạo, giữ DB/log/build cũ. Không dùng cleanup.

## Cách chạy và build

Python kiểm chứng hiện có: `infra/local/rag-fixture/.venv/Scripts/python.exe`. Từ workspace:

```powershell
& 'infra/local/rag-fixture/.venv/Scripts/python.exe' -B scripts/launch_multi_agent.py
```

Chỉ chạy khi 8003/3003 trống. Frontend phải có build02 đã kiểm chứng. Nếu cần build tiếp, dùng attempt03 mới, không ghi đè build cũ:

```powershell
& 'infra/local/rag-fixture/.venv/Scripts/python.exe' -B scripts/prepare_multi_agent_frontend.py prepare 03
& 'infra/local/rag-fixture/.venv/Scripts/python.exe' -B scripts/prepare_multi_agent_frontend.py build 03
```

Build copy dùng guard `m1_source_guard_20261012_58-repair1.mjs` nguyên byte, không nới rule hoặc xóa output. Đối chiếu và patch đúng frontend path trong launcher nếu đổi attempt; không tự dùng một build chưa qua TypeScript/build verification.

## Live admission và giới hạn

`headroom()` chỉ đọc ledger hiện hành. Snapshot bàn giao vẫn là paid8495/8500, native1990/2000. Có tiền còn lại không cấp thêm provider calls.

| Giới hạn run v1 | Giá trị |
|---|---:|
| Task / concurrency | 8 / 2 |
| Model calls chung, gồm safety/intent/planner/workers/synthesis/verifier/repair | 12 |
| Searches / tools | 4 / 32 |
| Evidence / context bytes | 6 / 15.000 |
| Conservative token reservations | 150.000 |
| Coordinator supplemental rounds / no-progress | 3 / 2 |
| Claim attempts | 2 |
| Processing deadline, cộng dồn qua resume | 30 giây |
| Mỗi model / retrieval tool | tối đa 5 / 12 giây, bị cắt theo thời gian còn lại |

Native worker tính inference theo từng sequence. Profile hiện tại cần worst-case tối đa 36 sequences cho 4 searches (6 rerank pairs + tối đa 3 embeddings mỗi search), token envelope900/sequence và HTTP headroom72. Admission còn kiểm tiền theo giá bảo thủ của ledger hiện có. Gateway/native runtime tiếp tục là hard gate cuối, không dùng headroom readback làm quyền tăng cap.

Live entrypoint có `--mode live`, nhưng hiện **không đủ headroom và sẽ từ chối trước khi mở Gateway**. Muốn kiểm chứng live sau này cần nguồn lực được người dùng cấp rõ, cộng phương án chuyển ownership paid writer đã xác minh. Không tự tăng/reset8500 calls, 2000 inference hay cap3USD. Không khởi chạy lệnh live song song với writer8000.

## API, resume và recovery

Giữ `/v1/conversations`, `messages:stream`, lịch sử và source citation APIs. Extension SSE `agent.status` version1 chỉ có phase, task ID/role/status và source count; không có chain-of-thought. Terminal giữ `run_id` khi có workflow mới. `partial_answer` và `system_error` phân biệt phần có nguồn với lỗi xử lý; dữ liệu cũ vẫn giải mã được.

Run APIs trong phạm vi hội thoại sở hữu:

- `GET /v1/conversations/{conversation_id}/agent-runs/{run_id}`
- `GET .../{run_id}/events?after={sequence}` để đọc lại event đã lưu, không inference mới.
- `POST .../{run_id}:resume` với `expected_version` và nội dung user bổ sung.
- `POST .../{run_id}:cancel` với `expected_version`.

UI tiếp tục run đang `waiting_user` qua CAS khi người dùng trả lời clarification; reload dùng stable run binding. Resume chỉ claim run waiting hoặc running đã hết lease. Không resume terminal đã hoàn tất. Source refs luôn đọc lại theo identity/session/scope hiện tại, schema/snapshot/config phải khớp. Task hoàn tất được khôi phục, không gọi lại Research. Pending provider outcome không xác định được giữ nguyên reservation và trả `MODEL_OUTCOME_UNKNOWN`; không tự retry/refund. Deadline xử lý đã dùng và usage tiếp tục cộng dồn, thời gian chờ user không được tính là inference time.

Mất SSE sau khi terminal multi-agent đã kiểm chứng: lịch sử được lưu trước delta. Reload hoặc GET run/events để phục hồi; `Last-Event-ID` trên POST stream được từ chối409, không tạo lượt mới. Đường Advanced cũ giữ semantics SSE hiện có. Khi hủy, join các task đang chạy; task chưa dispatch được đóng, không xóa hồ sơ hay đảo effect đã commit.

Cache chứa typed task result và source refs; key gắn actor/scope, as-of, locale, source/index/model/config, schema và goal/task. Hit vẫn đọc original sources và kiểm hash/eligibility; Verifier không tin cached summary.

## Giấy xác nhận

Service adapter chỉ đề xuất hoặc preview **draft đã có ID/version ổn định**. Retry cùng draft chỉ resume preview. Không có `confirm`/`submit` trong adapter; confirmation token không đưa vào model/checkpoint. Sinh viên vẫn phải xem trước và xác nhận qua backend, cán bộ vẫn tiếp nhận/bổ sung/duyệt/từ chối qua service hiện có. UI và bản giấy giữ yêu cầu bỏ nhãn demo/mô phỏng; provenance synthetic vẫn ở nội bộ.

## Kiểm chứng lại

Chọn tên output/basetemp mới chưa tồn tại. Mọi lệnh và exit code ở `verification-manifest-01.json`; mỗi JUnit/Vitest report giữ cả failures lịch sử. Event loop Windows cần loopback `socketpair`; sandbox từng chặn bước tạo loop, không phải lỗi controller. Dùng quyền local phù hợp cho test, không bỏ guard.

Source-only runner (lexical/source readback thật, không gọi BGE/provider):

```powershell
& 'infra/local/rag-fixture/.venv/Scripts/python.exe' -B scripts/evaluate_multi_agent_sources.py --output 'C:\Users\Duong Vinh\Vinh\infra\local\multi-agent-integrated-20261013-01\source-user-01.json'
```

`verify_multi_agent_runtime.py` đọc lại guarded HTTP/history và hồ sơ chặng1, thêm một conversation synthetic mới bị admission chặn. Chọn output mới. Không dùng source-only hoặc doubles để báo fresh live generation, completeness/correctness hay held-out quality.

Phục hồi vận hành: tiếp tục sử dụng URL8002 của chặng1 và writer8000 đã giữ nguyên; không cần reset dữ liệu. Nếu run snapshot/config đã đổi, giữ record cũ và mở yêu cầu mới rõ ràng; không sửa checkpoint để ép resume.
