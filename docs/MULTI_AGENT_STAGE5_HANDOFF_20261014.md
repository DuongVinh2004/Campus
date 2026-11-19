# Campus 24/7 — chuyển tiếp sang chặng 5

Người dùng yêu cầu trực tiếp: “khi xong chặng này thì mở đoạn chat mới và làm chặng tiếp theo”. Chặng 2–3–4 gộp đã được triển khai, kiểm chứng và bàn giao trong phạm vi local/synthetic; tiếp theo là **Policy Graph RAG**, theo `docs/graduation-design/05_POLICY_GRAPH_RAG.md`. Chỉ dẫn mới cho phép mở một chat chặng5, thay cho câu không tạo chat trong attachment cũ. Không tạo Codex subagent; multi-agent là vai trò bên trong ứng dụng.

Đọc AGENTS hiện hành. Quy trình governance/ready/approved/task-output/2repair cũ là reference; không thêm gate phê duyệt tài liệu. Giữ toàn bộ dữ liệu và quyền, secrets, source verification, preview/confirmation, ngân sách và recovery. Workspace duy nhất được ghi là `C:\Users\Duong Vinh\Vinh`; không commit/push/deploy/cleanup/reset/delete hoặc ghi bên ngoài. Git có nhiều dirty/untracked/deleted state trước đó, không thuộc riêng chặng này.

## Trạng thái và bằng chứng

- Runtime hiện tại multi-agent-v15, API8003 paid writer duy nhất; proxy8000, frontend3003 build02. API worker10336/launcher13108, native18081/18082 worker21908, frontend23056, proxy13460 là PID quan sát cuối; phải kiểm receipt/cổng/command/parent lại trước tác động.
- Native namespace10 tiếp tục09: `infra/local/rag-advanced-models-20261013-10/`. Same signed ONNX/model revision, CPU4physical cores, memory5GiB, token900/sequence, native3s và filesystem/network guards. Không dùng namespace10 làm output mới; nếu thực sự phục hồi, namespace11 tiếp tục10 với authorization02 và checks hiện có.
- Index `903531eb92b01e4ebb71ef6413b40fcba7b626e3480ddc6e3e580cfe634249fb`,131public rows, corpus `data/huce-public-20261013`/`data/huce-faq-20261013`. BM25+BGE-M3/reranker4pairs, one query/search, parent full-source reader; Advanced defaults và index cũ giữ nguyên.
- Policy tối đa12model calls/64tools/4searches/8tasks/concurrency2/attempts2/15.000context bytes/150.000reserved tokens/deadline30s tích lũy. Claims gate0,78, procedure scope và independent semantic checks; subset partial chỉ giữ claims liên quan đã qua tất cả gates, rejected claims giữ audit. V15 có alias hẹp cho chứng nhận sinh viên trong supplemental query; original goal/scope/negation/time giữ nguyên.
-295backend tests qua trong41,02s (`backend-tests-61.xml`), frontend74/build02 hashes được giữ. Full development11 v14:48ca/52turns,0system errors,52history khớp,46citations/0hash mismatch,442calls/0,3570795USD; p50=11.828ms/p95=20.235ms. Focused12 v15 sửa018:1ca,8calls,source39/hash/history khớp. Không gọi đây là full48fresh v15.
- Manual Codex/source review12:48correctness2,37completeness2,36ca có factual citations entailment2;11ca còn partial/incomplete. Dev48 không heldout, không independent human assessment hoặc production readiness. Giữ limitation về partial note chung,026chỉ trả một quy trình và coverage quá rộng ở một số ca; không giấu bằng model agreement.
- Bàn giao: `docs/MULTI_AGENT_LIVE_DELIVERY_20261013.md`, runbook cùng thư mục, `infra/local/multi-agent-integrated-20261013-01/verification-manifest-02.json`, `live-quality-review-12.json`, `live-readback-03.json`, `live-ui-readback-03.json`, `live-fanout-proof-03.json`, live crash/resume/corrective/preview-restart proofs. Mọi failed/aborted report trước đó giữ nguyên.

## Dữ liệu và ngân sách tiếp tục

Business DB `infra/local/certificate-stage1-20261013-01/demo.sqlite3`; history `infra/local/public-rag-20261013/conversations.sqlite3`; run/task/cache/idempotency ở `infra/local/multi-agent-integrated-20261013-01/`. Hồ sơ READY `01a1350b-8854-718f-8a37-47c544049501` vẫn5audit/HTML hash `e88565283b6cd21700449b49d5ef881c36cfc7232f0fc87b8e74407e142577f3`. Đọc history/terminal/source đã qua owner/non-owner404 sau v15 restart; snapshot khác không được resume. Preview bind phiên, đăng nhập mới không cho dùng preview phiên cũ; không confirm hoặc lặp effect để kiểm thử.

Paid ledger cuối11.994/12.000calls,4,4043015/10USD bảo thủ, còn5,5956985USD; invoice unknown.14unknown reservations giữ nguyên, không refund/reset. Authorization02/03/04 giữ đúng các lựa chọn người dùng trước đó.6calls dưới admission12/run nên **không có headroom cho run paid mới**. Native hiện7976HTTP/4630inference/797145tokens trên trần20.000/10.000/5.000.000; HTTP cũ thiếu telemetry giữ conservative floor6000.

Bắt đầu code/schema/source mapping/tests và review UI độc lập. Không mở paid Gateway thứ hai, chạy replay gọi là fresh, hạ admission để né quota hoặc tự nâng cap. Khi cần live extraction/query, chuẩn bị implementation/tests/runner và đề xuất đúng provider call extension trong tổng10USD cho người dùng xác nhận. Không biến thiếu ngân sách thành lý do dừng phần triển khai độc lập.

## Công việc chặng 5

Thực hiện code và tích hợp thật, dùng thiết kế05 làm reference cho mục tiêu; không dừng ở kế hoạch. Ưu tiên xác nhận/phúc khảo và nhóm học vụ có nguồn hợp lệ. Graph-assisted retrieval là cam kết; không yêu cầu ablation/graph-on-off hoặc thêm graph database khi relational schema hiện có phù hợp.

Schema graph/version/source mapping giữ Procedure/Form/Clause/Unit/Audience/ConditionGroup ALL-ANY/Exception/EffectiveInterval và edges requires/applies_to/handled_by/defined_by/has_exception/supersedes. Mỗi edge gắn source/version/locator/hash/scope/hiệu lực/review verdict; LLM extraction chỉ candidate, không tự thành fact/rule phê duyệt. Giữ aliases khác trường/đối tượng/đơn vị riêng, không tự merge.

Builder/review/publish giữ raw proposal và verdict, source/hash/quantifier/temporal conflicts, namespace/index/source fingerprint và recovery. Traversal có depth/node/cycle bounds, AuthorizationFilter trước neighbor count/suggestions/errors. Re-read nguồn gốc trước rerank/context/coverage/claims; graph summary/path không thay source evidence. Không tự diễn giải ngày hiệu lực hoặc supersedes toàn văn khi nguồn chưa rõ.

Tích hợp repository/query service/tool vào Research theo scope hiện tại; review UI hiển thị edge, source clause, condition group, hiệu lực/verdict. Kiểm additive storage, dangling/cycle/duplicate aliases, ALL khác ANY, scope/temporal conflicts, leakage, version mismatch và graph-assisted retrieval. Dùng fakes/deterministic tests phù hợp và kiểm nguồn thật riêng; live chỉ khi headroom/authority thực sự có. Giữ hybrid fallback và luồng giấy xác nhận chặng1, không mở nghiệp vụ phúc khảo mới thuộc chặng6. Chặng7 đánh giá cuối hệ thống đã chọn.
