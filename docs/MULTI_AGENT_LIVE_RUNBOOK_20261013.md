# Campus 24/7 — vận hành multi-agent live

Runbook này cập nhật trạng thái guarded được ghi trong `MULTI_AGENT_INTEGRATED_RUNBOOK_20261013.md`. Mọi report và receipt cũ được giữ. Phạm vi vẫn là local/synthetic, gộp chặng 2–3–4; không có benchmark kiến trúc hoặc triển khai chặng 5–7.

## Runtime và tài nguyên

Giao diện chính: **http://localhost:8003/login**. Tài khoản local: SV001, SV024, OF001. Frontend3003 giữ build02; API8003 là paid writer duy nhất. URL8000 chuyển tiếp tới8003, nên API hồ sơ8002/front3002 tiếp tục dùng cùng hỏi đáp. Front3000/3001 và các dữ liệu cũ được giữ.

Người dùng đã chọn trực tiếp: **“Tổng 10 USD; áp dụng các trần kỹ thuật đề xuất”**. `infra/local/multi-agent-integrated-20261013-01/resource-authorization-02.json` lưu lựa chọn, snapshot và toàn bộ uncertain reservations trước chuyển tiếp. Trần tích lũy:10USD bảo thủ,10.000 provider calls; native10.000 inference sequences,20.000 HTTP requests,5.000.000 tokens. Không reset/refund usage cũ. Invoice thực tế vẫn unknown.

Người dùng tiếp tục xác nhận **“Cho phép 12.000 calls; giữ tổng 10 USD”**. `resource-authorization-04.json` chỉ nâng provider calls10.000→12.000, bind hash authorization02 và snapshot ổn định sau lượt05:9.925calls/2,8073001USD. Mọi unknown reservations được giữ nguyên, không sửa ledger cũ. Native caps, USD10 và per-run caps giữ nguyên; native recovery vẫn dùng authorization02.

Trước chuyển tiếp:8495 provider calls, charged1,7546595USD; native1990 sequences/394527 tokens. Native worker cũ không ghi mọi GET info: phần HTTP cũ được giữ bảo thủ ở6000 thay vì coi phần chưa đo là0. Counter inference/tokens được giữ nguyên. Worker mới ghi reservation HTTP và inference trước dispatch.

Paid ledger vẫn ở `infra/local/public-rag-20261013/`. Native worker hiện tại ở `infra/local/rag-advanced-models-20261013-10/`, tiếp tục09 sau khi runtime cũ đã ngừng. Recovery03 lưu preflight/counters/launch; recovery02 sau lỗi08 và mọi namespace/logs trước đó được giữ. Cùng ONNX/checksum/model revision, CPU4cores, memory5GiB, token envelope900/sequence, native deadline3s và guard filesystem/network. Không reset quota hoặc hoàn lại inference chưa rõ kết quả.

## Cấu hình và dữ liệu

Runtime multi-agent v15 có tối đa8tasks, concurrency2,12model calls chung,4searches,64tools,6evidence parents,15.000 context bytes,150.000 reserved tokens, deadline30s cộng dồn khi resume. Người dùng đã xác nhận riêng trần64tools và duy nhất `response_format={"type":"json_object"}` cho endpoint/model DeepSeek Flash được duyệt; xem `resource-authorization-03.json`. Validator vẫn từ chối mọi giá trị khác và giữ secrets/PII/purpose guards. JSON mode không bảo đảm nội dung đúng. Research được giao truy vấn; mỗi search thực hiện một query, BM25+BGE-M3+reranker4pairs. Coordinator quyết định tìm bổ sung. Cấu hình retrieval gắn vào snapshot/cache; child chunking và index fingerprint **903531eb92b01e4ebb71ef6413b40fcba7b626e3480ddc6e3e580cfe634249fb** giữ nguyên.

Research/Verifier chọn span IDs do server cấp. Mỗi span là tối đa700ký tự liên tiếp, giữ nguyên mọi ký tự của nguồn; server giải span thành quote rồi kiểm source/hash/scope. Claim vẫn qua deterministic gate và semantic verifier. Format/provenance repairs dùng chung giới hạn; response không rõ kết quả không tự retry/refund.

Khi câu hỏi so sánh các quy trình có tiêu đề đánh số, v15 kiểm mỗi claim với đúng phần của nguồn gốc và yêu cầu tên quy trình rõ ràng. Không gán điều kiện nghỉ học tạm thời sang xác nhận sinh viên trên cùng trang39. Câu hỏi đọc không được chuyển chuyên viên do model tự phân loại; yêu cầu gặp cán bộ rõ ràng vẫn giữ. Quên mã sinh viên yêu cầu xác minh thông tin; chưa tự tạo/gửi hồ sơ. Không xem lời partial chung là đáp án đầy đủ trong chấm chất lượng.

V15 đang phục vụ với cùng per-run caps. Model đề xuất assignment gọn; server gán allowlist theo role và validate toàn DAG trước effect. DAG độc lập quá tốn calls được gộp, giữ mọi coverage requirement; task bổ sung thu hẹp tới các mục chưa đủ nguồn, vẫn kiểm references/cycle/rights trước thu hẹp. Khi chỉ còn room cho synthesis/claim checks, phần đã kiểm chứng có thể trả partial; không chuyển thiếu coverage thành full success. ID task còn trống và trạng thái task thật được đưa vào context; mã lỗi DAG cố định được dùng cho repair, không raw exception.

Evidence rỗng luôn thành missing_source với zero supports, không gọi model để đồng ý với điều không có nguồn. Khi có nguồn, Research/Verifier vẫn đề xuất/kiểm report riêng và claims qua gates. Query cũ chỉ giữ trong bộ nhớ cho Research tránh lặp; checkpoint tiếp tục chỉ lưu fingerprints. Đề xuất query lặp có tối đa một lượt sửa tính vào calls chung; query trùng vẫn bị chặn trước native/tool dispatch. Clarification phân biệt tra cứu chung với chọn mẫu; current_request tách câu hiện tại với user goal cũ. Partial về duyệt vay hoặc thời điểm tương lai nêu rõ phần chưa xác minh. Resume có pending model trả terminal unknown, không redispatch/refund.

DB hồ sơ `infra/local/certificate-stage1-20261013-01/demo.sqlite3`, DB history `infra/local/public-rag-20261013/conversations.sqlite3` và DB run/task/cache `infra/local/multi-agent-integrated-20261013-01/agent-runs.sqlite3` tiếp tục được dùng. Không delete/reset/migration phá hủy. Service giấy xác nhận vẫn cần preview và explicit confirmation; model không gửi hay quyết định hồ sơ.

Trạng thái mới nhất: v15/native10. Native10 tiếp tục counters09 sau khi runtime cũ đã ngừng; recovery03 giữ preflight/launch/namespace cũ và caps. V14 dùng các trần per-run đã mô tả, bổ sung partial chỉ chứa claims liên quan được kiểm chứng và audit giữ claims bị loại; không hạ gate hoặc đổi nguồn. 295backend tests qua trong41,02s, frontend build02/74tests được tái sử dụng theo hashes. Xem delivery và manifest mới nhất để biết acceptance/chất lượng cuối; các đoạn v12 trên là lịch sử implementation.

## Khởi động và phục hồi

Các `*-live-launch.json` lưu command/PID launcher. Windows venv có child Python giữ cổng: đối chiếu PID listening, command và parent với receipt trước dừng đúng process sở hữu. Giữ mọi DB, namespace, log, build và ledger. Không chạy launcher khi cổng còn bị chiếm.

Khi native/proxy/frontend còn hoạt động và API8003 đã được giải phóng qua kiểm tra ownership:

```powershell
& 'infra/local/rag-fixture/.venv/Scripts/python.exe' -B scripts/launch_multi_agent_live.py --api-only
```

Launcher không tự dừng process. `--api-only` ghi receipt/log mới, lấy lease writer trước credentials và tiếp tục cumulative ledger. API8000 chỉ là proxy, không mở Gateway. Không chạy lại paid entrypoint cũ để reset về trần3USD.

Nếu toàn bộ runtime đã ngừng, có thể khởi động riêng frontend build hiện có bằng `scripts/launch_multi_agent.py --frontend-only`; cổng3003 phải trống. Khởi động native bằng namespace kế tiếp mới, cùng predecessor/authorization; proxy8000 rồi API8003 live sau khi dependencies sẵn sàng. Recovery03 lưu đúng commands/PIDs cho trường hợp này. Không launch API guarded xen giữa hoặc chạy hai paid writers. Kiểm receipt/cổng/command/parent trước mọi thao tác dừng process. Runtimes8002/3002 hiện đã ngừng nhưng các endpoints giấy xác nhận tích hợp8003 dùng cùng business DB và kết quả cũ.

Nếu native worker thực sự cần phục hồi, kiểm ownership và giải phóng18081/18082 trước. Dùng namespace kế tiếp chưa tồn tại, ví dụ11 tiếp tục10, cùng authorization:

```powershell
& '.venv/Scripts/python.exe' -B scripts/serve_rag_models.py --state 'infra/local/rag-advanced-models-20261013-11' --predecessor 'infra/local/rag-advanced-models-20261013-10' --resource-authorization 'infra/local/multi-agent-integrated-20261013-01/resource-authorization-02.json'
```

Continuation xác thực caps/counters và namespace kế tiếp; không hoàn lại inference chưa rõ kết quả. Không dùng hoặc ghi đè namespace đã tồn tại. Khi snapshot/config đã đổi, giữ run cũ; resume từ cấu hình khác bị chặn, có thể mở yêu cầu mới rõ ràng.

## Kiểm chứng

Kết quả cuối: development11 v14 đủ48ca/52turns,0system errors,52history khớp,46citations không sai hash; focused12 v15 sửa018 bằng alias hẹp,8calls/nguồn39 đúng. Review12 bind từng revision, ghi48correctness2 nhưng chỉ37completeness2; không gọi focused1ca là full48fresh v15. Readback03 giữ READY hash5audit và zero provider/native usage. Manifest02/delivery giữ các lỗi/refusal/aborted cũ.

Ledger11.994/12.000calls,4,4043015/10USD,14unknown nguyên trạng. Còn6calls dưới admission12/run; health/history/citations và business endpoints vẫn phục vụ nhưng không nhận paid run mới. Không tăng cap hoặc giảm admission để né giới hạn. Sau restart token cũ có thể cần đăng nhập local lại; owner history/kết quả vẫn giữ. Chặng5 có thể triển khai local/source/tests trước, xin đúng tài nguyên bổ sung khi thực sự cần live.


```powershell
& 'infra/local/rag-fixture/.venv/Scripts/python.exe' -B scripts/evaluate_multi_agent_live.py --output 'infra/local/multi-agent-integrated-20261013-01/live-user-new.json'
```

Runner gọi HTTP của writer hiện hữu, không mở Gateway thứ hai. Chỉ câu hỏi/lịch sử user vào app; expected behavior/required concepts nằm ngoài prompt. Từng ca có artifact riêng, không overwrite. Report ghi SSE progress trước terminal, citations/hash/source readback, history, tasks/events/coverage/claims, calls/tokens/cost bảo thủ và latency. Không tự confirm hồ sơ hoặc resend request không rõ outcome.

Ba ca liên tiếp lỗi vận hành khiến runner dừng dispatch và giữ aggregate/từng ca; refusal/clarification an toàn không bị tính thành lỗi hệ thống. `aborted`, `abort_reason`, `expected_cases` và `not_verified_case_ids` phân biệt lượt dừng với lượt hoàn tất. Native `/info` chỉ xác nhận metadata; phải có generation/neural tools thực tế mới kiểm được inference. Lượt development09 bị dừng21ca/9errors được giữ, native09 tiếp tục counters08, focused10 sau recovery kiểm3ca thật và qua. Không xóa hoặc sửa kết quả lỗi để làm lượt mới đạt.

Bộ48 là development, không held-out. Kiểm đúng/đủ/entailment bằng đọc nguồn riêng; terminal successful hoặc hash khớp không tự thành quality success. Lượt01:48ca/50turns,27turn errors. Lượt02:48ca/51turns,15turn errors. Lượt focused03:6ca,3retrieval errors. Lượt04:v4/native08,48ca/52turns,8turn errors,52history readback khớp,35citation mở được/0hash mismatch. Lượt05 kiểm toàn bộ v5; xem report/chốt bàn giao mới để biết kết quả. Các lỗi và ca clarification chưa phù hợp của v4 được giữ; không gọi chúng là quality success.

Bài thử crash thực tế lưu ở `live-crash-01.json` và `live-crash-resume-01.json`: đúng API sở hữu bị dừng sau durable model/provider reservation9539; dispatch/outcome provider ghi unknown, không suy ra đã hoàn thành inference. Restart/resume giữ reservation, không gọi lại/refund; terminal/history và stale CAS409 được kiểm. `live-readback-02.json` xác nhận owner/non-owner và hồ sơ READY cũ giữ cùng hash.

Preview được bind với phiên ban đầu. Đăng nhập mới sau restart có thể đọc hồ sơ của cùng owner nhưng không tự được dùng preview của phiên khác; `live-service-restart-attempt-01.json` giữ ca409 này. `live-service-restart-after-02.json` kiểm bằng token gốc chỉ giữ trong bộ nhớ: preview/version/audit không đổi sau restart; không confirm hoặc lặp business effect.
