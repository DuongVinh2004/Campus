# Campus 24/7 — bàn giao multi-agent live chặng 2–3–4

Bắt đầu 13/10/2026, kiểm chứng tiếp tục sang14/10 theo Asia/Bangkok. Phạm vi local/synthetic. Hệ thống đang phục vụ tại [Campus 24/7](http://localhost:8003/login), với API8003 là paid writer duy nhất và API8000 chuyển tiếp. Frontend3003 dùng build02; cùng business/history DB và endpoints giấy xác nhận chặng1 được tích hợp trong8003. Runtime cũ8002/3002 đã ngừng trước lượt khôi phục03; dữ liệu và bằng chứng được giữ. Chất lượng thực tế được ghi riêng với control flow; đã hoàn tất development11 v14 và focused12 v15; runtime hiện tại v15 giữ admission khi thiếu headroom.

## Thay đổi đã triển khai

Coordinator tạo coverage và DAG từ yêu cầu/evidence; Research có search/read/inspect, Verifier đọc lại nguồn gốc và kiểm từng requirement. Task độc lập chạy với concurrency2; dependency chờ kết quả. Server validate schema, DAG, scope, source eligibility, hash và ngân sách trước effect. Model chỉ đề xuất assignment gọn; server mở rộng thành TaskSpec với allowlist cố định. Extra tools/quyền bị từ chối. Claims qua deterministic gate0,78 và semantic verifier, không lấy đồng thuận agent làm nguồn.

V15 giữ model calls12/run, tools64/run đã được duyệt, searches4, tasks8, concurrency2, attempts2, context15.000bytes, reserved tokens150.000 và deadline30s cộng dồn khi resume. DeepSeek Flash dùng duy nhất JSON object mode đã được xác nhận; secrets/PII/purpose/endpoint validator tiếp tục hoạt động. Format/query repairs có tính usage; provider timeout/outcome không rõ không tự gọi lại hoặc hoàn quota. Sau validate, server gộp DAG độc lập khi cần và thu hẹp supplemental tasks tới các mục thiếu; requirements và quyền không bị mở rộng. Evidence rỗng luôn bị từ chối hỗ trợ, không lấy model agreement làm bằng chứng.

Advanced RAG tái sử dụng BM25+BGE-M3+reranker, corpus131rows và index `903531eb92b01e4ebb71ef6413b40fcba7b626e3480ddc6e3e580cfe634249fb`. Profile tích hợp dùng một query/search và rerank4pairs; mặc định Advanced và index không bị viết lại. Snapshot/cache gắn retrieval policy, actor/scope/as-of/source/index/model/config. Lịch sử user giải follow-up; assistant history không là nguồn hoặc quyền.

Service adapter gọi đúng dịch vụ giấy xác nhận hiện có qua form/draft/preview typed. Free-text chưa tự điền rồi gửi hồ sơ. Preview, explicit confirmation, idempotency, audit và version guards được giữ; adapter không cấp model quyền confirm/submit hoặc quyết định duyệt hồ sơ.

V11/V12 thêm kiểm scope từ tiêu đề đánh số trong nguồn gốc: khi câu hỏi so sánh nhiều quy trình, mỗi claim phải ghi rõ quy trình và được kiểm với phần tương ứng, không gán chữ ký/phí/thanh toán từ phần khác trên cùng trang. Semantic gate vẫn kiểm quan hệ và điều kiện. Câu tra cứu không nhận handover effect chỉ vì model chọn nhầm route; yêu cầu gặp cán bộ rõ ràng vẫn được giữ. Quên mã sinh viên sinh hướng dẫn xác minh, không bịa mã hoặc gửi hồ sơ. Partial/error về phí, SLA, vay và thời điểm tương lai nêu đúng loại thông tin chưa xác minh.

## Tài nguyên đã được người dùng xác nhận

V13/V14 phân biệt claims được nguồn hỗ trợ với câu hỏi đã được trả lời đầy đủ. Giấy tờ vay không thành bảo đảm duyệt vay. Với câu hỏi quan hệ, chỉ subset liên quan có từng claim qua deterministic0,78, scope của đúng phần nguồn, source readback và independent semantic verifier mới được trả partial; các claim bị loại vẫn giữ verdict insufficient trong audit. Tên quy trình hỗ trợ generation lấy từ tiêu đề nguồn gốc, không lấy gold. Known completed schema failure có bounded repair; raw malformed output không được lưu/echo và unknown outcome không retry. Không đổi source bytes, gate threshold hoặc quyền.

`resource-authorization-02.json` giữ trần10USD bảo thủ, native10.000 inference/20.000HTTP/5.000.000tokens và provider10.000calls ban đầu. `resource-authorization-03.json` ghi xác nhận tools64 và JSON mode chính xác. `resource-authorization-04.json` bind hash02 và snapshot ổn định sau lượt05, chỉ nâng provider calls lên12.000 theo câu trả lời “Cho phép 12.000 calls; giữ tổng 10 USD”.

Snapshot trước04:9.925calls/2,8073001USD, input6.254.147tokens/output775.880tokens. Toàn bộ14 unknown reservations giữ nguyên. Không reset/refund/sửa ledger cũ. Chi phí là conservative reservation charge theo ledger, không phải invoice; số tiền thực tế được provider tính vẫn unknown. Native HTTP cũ thiếu telemetry được giữ bằng envelope6.000 thay vì suy ra0; inference/tokens và các reservation mới giữ nguyên.

## Bằng chứng kiểm chứng

Mọi artifact nằm tại `infra/local/multi-agent-integrated-20261013-01/`; file mới được tạo riêng, report lỗi cũ giữ nguyên. `backend-tests-61.xml` ghi295tests v15 qua trong41,02s;59 ghi289tests v14 qua trong42,64s, gồm v14, API, giấy xác nhận, admission, tiếp nối ngân sách, JSON mode, semantic coverage và subset partial có audit giữ claim bị loại. `backend-tests-58.xml` ghi284tests v13 qua;55 ghi206tests v12 qua. Các lần kiểm chồng lặp không cộng thành số tests độc lập. Frontend giữ74tests và build02 đã qua, chỉ tái sử dụng khi hashes code khớp bản build.

`live-fanout-proof-01.json` bind hash ca031/lượt05: ResearchT1/T3 cùng running trước khi một task hoàn tất; T2/T4 chỉ chạy sau dependency tương ứng. Đây là model/tool live thật, không phải Codex subagents. Các ca tìm bổ sung và chất lượng cuối cần đọc coverage/source riêng; nhiều task hoặc có nguồn mới chưa tự chứng minh đáp án tốt hơn.

`live-crash-01.json` dừng đúng API sở hữu sau durable model/provider reservation9539. Dispatch/outcome provider ghi unknown. `live-crash-resume-01.json` kiểm restart/resume terminal unknown, zero model redispatch, giữ reservation và stale CAS409. `live-service-restart-after-02.json` kiểm preview bằng token phiên gốc chỉ giữ trong bộ nhớ: preview/version/audit không đổi; không confirm/lặp business effect. `live-service-restart-attempt-01.json` giữ ca409 khi đăng nhập phiên khác, đúng session binding.

`live-readback-02.json` kiểm history/terminal/source của owner, non-owner404 và hồ sơ READY chặng1 giữ5audit cùng HTML hash `e88565283b6cd21700449b49d5ef881c36cfc7232f0fc87b8e74407e142577f3`. Ảnh `live-citation-ui-06.jpg` ghi câu trả lời v12 tải từ lịch sử, nguồn HUCE trang39 và toàn bộ đoạn gốc. Phần2 xác nhận và phần3 nghỉ học tạm thời cùng trang vẫn được giữ trong nguồn; không chuyển điều kiện giữa hai thủ tục.

## Kết quả chất lượng

Chốt kiểm chứng: development11 v14/native10 đủ48ca/52turns,0system errors,52history khớp,46citations/0hash mismatch;442calls/0,3570795USD, p50=11.828ms/p95=20.235ms. Review11 chấm47/48correctness2,36/48completeness2,35ca có factual citations entailment2; ca018 thiếu trang39 giữ nguyên là chưa đạt.

V15 thêm alias search hẹp “giấy chứng nhận sinh viên”→“giấy xác nhận sinh viên”. Original goal, điều kiện/phủ định/thời gian, scope và bytes nguồn giữ nguyên; alias audit chỉ giữ hashes, query lặp vẫn bị chặn.295tests qua/41,02s. Test60 có1kỳ vọng sai về original goal được giữ cùng294tests qua; sửa kỳ vọng để kiểm đúng original goal cộng supplemental query, giữ ràng buộc implementation.

Focused12 kiểm018 trên v15:grounded answer,8calls/0,0059409USD,10.562ms,history/source39/hash khớp và trace alias/neural search/readback/verifier thật. Full48 vẫn là v14; không gọi focused1ca là full48fresh v15. Review12 bind từng ca/report/runtime:48correctness2,37completeness2,36ca có factual citations entailment2.11ca còn partial/incomplete, gồm note chung và026chỉ giữ một quy trình. Đây là manual Codex/development, chưa có independent human verdict; không tuyên bố production readiness hoặc usability toàn corpus.

Readback03 sau restart v15 xác nhận zero new provider/native calls; owner history/terminal/source, non-owner404 và hồ sơ READY cùng5audit/HTML hash giữ nguyên. Fanout proof03 bind run UI v14 với ResearchT1/T3 overlap và Verifier chờ dependency. Resume snapshot khác bị chặn, terminal cũ vẫn đọc được.

Ledger cuối:11.994/12.000calls,4,4043015/10USD bảo thủ,14unknown reservations nguyên trạng; invoice unknown.6calls còn lại dưới admission12/run nên không nhận run paid mới. Không nâng trần hoặc bỏ admission. Chặng5 có thể bắt đầu code/tests/graph nguồn công khai độc lập; live mới cần tài nguyên được xác nhận cụ thể. Manifest02 chốt code/fingerprints/evidence/quality/acceptance/calendar; active/external wait unknown.

| Tiêu chí | Kết quả và phạm vi bằng chứng |
|---|---|
|1 · Vai trò/hợp đồng | Live task/coverage/claim traces và adversarial tests61 |
|2 · Single/multi/follow-up/tìm bổ sung | Full11, focused12 sửa018, corrective fault03 v10 giữ scope; chất lượng còn incomplete |
|3 · DAG/song song/quyền | Fanout proof03 v14 và fake DAG/tool denial tests61 |
|4 · Verifier/thiếu nguồn/lỗi | Gate0,78/scope/readback/semantic và wrong-consensus tests61; error khác missing_source |
|5 · Tài nguyên/cancel/unknown | Admission/reservation/concurrency/deadline/cancel tests61; caps và14unknown giữ nguyên |
|6 · Persistence/quyền hiện tại | Crash/resume/preview restart proofs và readback03; không lặp business effect |
|7 · UI/chặng1 | Ảnh progress/source/partial/error thật; READY hash5audit, certificate API tests, frontend74/build02 hashes |
|8 · Báo cáo trung thực | Từng ca/lỗi/not_verified, hashes, source quality, usage/latency và calendar tách active unknown |

Các tiêu chí được kiểm trong phạm vi nêu trên; đây không phải chất lượng hoàn hảo mọi ca hoặc bằng chứng kiến trúc tốt hơn hệ khác.


`live-ui-after-02.json` bind run v14 thực tế: câu hỏi cách bắt đầu/nhận giấy trả đúng website, chọn mẫu và vị trí nhận;11provider calls. `live-progress-ui-02.jpg` ghi busy, `live-role-progress-ui-01.jpg` ghi đang tìm/đọc nguồn và nhãn nội dung tạm, `live-citation-ui-07.jpg` ghi mở toàn bộ nguồn trang39. Không gửi confirmation hồ sơ. Ảnh error/partial trước đó giữ tại `live-error-ui-01.jpg`/`live-partial-ui-01.jpg`. Ảnh `live-progress-ui-01.jpg` cũ thực tế là terminal refusal; không dùng nó để chứng minh progress.

Dev48 là development, không heldout hoặc đánh giá độc lập của con người. Lượt05:v5/native08,48ca/51turns,3system errors,51history readback khớp,48citations mở được/0hash mismatch, latency p50=14.657ms/p95=24.906ms. Usage386calls/0,2906001USD bảo thủ. `live-quality-review-05.json` chấm từng ca từ câu trả lời và nguồn, không coi error/refusal có đáp án trong nguồn là quality success. Các lỗi chọn mẫu, điều kiện đủ và định dạng được giữ để review.

Lượt06 kiểm v6:48ca/52turns,3system errors,52history readback khớp,39citations/0hash mismatch. Lượt focused07 kiểm v7:10ca/12turns,1failure; report này giữ nguyên. Lượt08 kiểm toàn bộ v10:48ca/52turns,0system errors,52history readback khớp,42citations/0hash mismatch,417calls/0,3249015USD; latency p50=13.297ms/p95=22.859ms. `live-quality-review-08.json` đọc nguồn và chấm48ca:43correctness2,33completeness2; các câu so sánh còn gán scope mơ hồ, ca032 bị chuyển hỗ trợ sai và ca034 chưa giải quyết điều kiện đủ. Không coi lượt08 đã đạt acceptance chất lượng. Lượt focused09 kiểm v11:6ca/8turns,0errors,8history khớp,5citations/0hash mismatch,70calls/0,0592932USD; ca025/026 đã ghi rõ tên quy trình nhưng lời partial còn chung. Lượt development09 đã dừng sau lỗi native, như ghi bên dưới; gold/expected behavior không vào model prompt.

`live-corrective-fault-03.json` qua trên v10: search đầu chạy native thật rồi cố ý bỏ candidates một lần; model đổi query, search tiếp trả nguồn thật, readback/hash và Verifier/claims qua trước trả lời đúng phòng Hành chính Tổng hợp trang39. Usage10calls/0,0072000USD bảo thủ, native10inference sequences. Đây là controlled fault dùng live model/neural tools qua in-process ASGI, không phải phép đo TCP/SSE latency hoặc bằng chứng usability chung. Hai probe thất bại01/02 giữ nguyên. Lượt08 phục vụ bình thường không có fault này.

Lượt development09 (v12/native08) bị dừng sau lỗi native lặp:21ca/21turns đã ghi,9errors,21history khớp,13citations/0hash mismatch;27ca chưa chạy là not_verified. Aggregate09 được dựng từ các file từng ca giữ nguyên, có `aborted=true`; không gọi đây là lượt48 hoàn thành. Snapshot ổn định11.061calls/3,6557631USD,14unknown reservations giữ nguyên. Native09 tiếp tục toàn bộ counters08 bằng recovery02, không đổi guards. Focused10 trên v12/native09 kiểm3ca từng lỗi:3turns/0errors/3history khớp/3citations không sai hash,28calls/0,0221955USD. Lượt development10 đã hoàn thành với2system errors, như kết quả bên dưới. Runner từ đây dừng dispatch sau3lỗi vận hành liên tiếp và ghi các ca chưa chạy là not_verified.

## Vận hành và bảo toàn

Lượt development10 hoàn thành v12/native09:48ca/52turns,2system errors (006native,040claim format),52history khớp,44citations/0hash mismatch;433calls/0,3443808USD, p50=14.172ms/p95=24.515ms. `live-quality-review-10.json` chấm48ca:44correctness2,38completeness2,33entailment2, verdict not_met;026refusal và034thiếu quan hệ vay vẫn chưa đạt. `live-fanout-proof-02.json` bind ca019/lượt10: Research độc lập T1/T3 thực sự overlap, Verifier T2/T4 chờ dependency, cùng hashes nguồn35/39 và history. V14 sửa các điểm đã quan sát nhưng kết quả mới phải được chấm riêng.

Trước lượt11, kiểm read-only thấy các PID/cổng runtime trước không còn hoạt động. `native-recovery-preflight-03.json` và `native-recovery-launch-03.json` khôi phục native10 tiếp tục09 với cùng guards/caps; build02 frontend và proxy khởi động bằng receipts/logs mới. Không dừng process khác, reset usage hoặc ghi đè namespace cũ. Snapshot trước UI v14:11.533calls/4,0326600USD,14unknown reservations giữ nguyên.

Xem [runbook live](MULTI_AGENT_LIVE_RUNBOOK_20261013.md). Launcher không tự dừng process. Trước restart, đối chiếu receipt, cổng listening, command và parent của đúng process do lượt này tạo. Native recovery dùng namespace kế tiếp mới và authorization02; giữ09 và mọi logs/counters. Khi snapshot/config khác, resume cũ bị chặn, terminal/history vẫn đọc được.

Giữ business DB, history DB, agent/task/cache DB, index, guard, stage1 evidence và mọi dirty/staged/untracked/ignored/deleted state có sẵn. Không cleanup, reset, commit, push, deploy hoặc phá hủy dữ liệu. Manifest cuối ghi fingerprints/hashes, từng test/report, phạm vi kiểm chứng và calendar time; active/external wait time ghi unknown khi không có phép đo đáng tin cậy.
