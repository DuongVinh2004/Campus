# Campus 24/7 — bàn giao implementation multi-agent tích hợp 2–3–4

> Bản bàn giao guarded lịch sử. Quyền tài nguyên và runtime live sau đó được ghi ở [runbook live](MULTI_AGENT_LIVE_RUNBOOK_20261013.md); giữ nguyên kết quả/evidence dưới đây để phục hồi và đối chiếu.

Ngày13/10/2026. **Implementation local đã có và được kiểm chứng theo phạm vi dưới đây; nghiệm thu fresh live generation/quality vẫn `not_verified` vì thiếu provider/native headroom. Không kết luận chặng gộp `completed`.** [Runbook](MULTI_AGENT_INTEGRATED_RUNBOOK_20261013.md).

## Phạm vi và implementation

Theo thay đổi trực tiếp của người dùng: dùng multi-agent trong ứng dụng, gộp chặng2–3–4, bỏ single-agent riêng/router so sánh/benchmark kiến trúc. Không tạo Codex subagent hoặc chat mới. Advanced code/corpus/index/evidence và mọi dữ liệu cũ được giữ.

Coordinator tạo CoverageItems và task DAG typed theo yêu cầu; application kiểm dependency/cycle/task cap/tool allowlist trước dispatch. Research task có mục tiêu/context riêng, lập truy vấn, gọi scoped search/read, giữ câu hỏi gốc cùng thời điểm/điều kiện/phủ định. Verifier task đợi dependency, đọc original refs thay vì tin Research summary. Kết quả chưa đủ dẫn tới Coordinator bổ sung task cụ thể, clarification, phần có căn cứ hoặc dừng. Hai Research độc lập có thể fan-out trong concurrency2 và dùng budget chung.

Synthesis tạo grounded claims; gate deterministic giữ threshold0,78 và các kiểm tra số/đơn vị/comparator/phủ định/điều kiện, sau đó semantic verifier typed. Claim bị chặn có verdict và yêu cầu sửa; tối đa một lần sửa dùng cùng evidence/scope và ngân sách còn lại. Đồng thuận model không thay gate. Coverage status và claim verdict tách biệt. Assistant history chỉ giải tham chiếu, không cấp quyền hay cung cấp quy định. Đã sửa follow-up mất năm/đối tượng ở câu điều kiện điểm rèn luyện sau học bổng; topic switch vẫn không kéo nguồn cũ.

Tái sử dụng `application/single_agent/{contracts,resources,controller}.py` làm tools/resources chung. Workflow mới ở `agent/multi_rag.py`, `application/multi_agent/`. Không hoàn thành hay quảng bá engine single-agent riêng. SQLite run store dùng run/task CAS+lease, events append-only, checkpoints/schema/cursor/usage, cache scope/snapshot/as-of; đây là orchestration store application, không tuyên bố là LangGraph checkpointer protocol.

Identity/session được xác thực lại trước mỗi tool và resume, kể cả thu hồi phiên trong khi Research chạy. Scope/hash/publication/as-of kiểm lại khi merge/retry/cache. Run có typed server context; model không ghi actor/scope/ceiling. UI chỉ hiển thị tiến độ hữu ích, trạng thái partial/error/clarification, citation và terminal; không có raw prompt/chain-of-thought.

## Runtime và preservation

Runtime riêng **http://localhost:8003/login** / frontend3003, guarded admission, build02. Không mở paid writer mới. Public API8000, BGE18081/18082 và hệ hồ sơ8002/front3002 từ chặng1 được giữ. Receipt/log mới ở `infra/local/multi-agent-integrated-20261013-01/`; ownership đã đối chiếu command, parent và PID listening trước restart runtime mới.

Giữ DB hồ sơ và lịch sử hiện có; run/task/cache DB mới additive. Readback sau restart xác nhận conversation browser còn terminal lỗi giới hạn đúng nghĩa; hồ sơ chặng1 `01a1350b-8854-718f-8a37-47c544049501` vẫn READY, có5 audit entries và cùng HTML result hash `e88565283b6cd21700449b49d5ef881c36cfc7232f0fc87b8e74407e142577f3`. Không delete/reset/clean/commit/push, không sửa guard, evidence cũ, dataset/gold hay threshold.

Guard build nguyên byte SHA256 `8f0886295da2214205cf257dd9e1d9476993ed1a7fb0ac67434909fa4af2eae6`. Corpus/index fingerprint `903531eb92b01e4ebb71ef6413b40fcba7b626e3480ddc6e3e580cfe634249fb`, nguồn canonical human-reviewed; trang39 chứa cả mục xác nhận và nghỉ học, không gán điều kiện nghỉ học sang xác nhận. Không đổi provenance sang raw OCR ghép trang.

## Kiểm chứng và acceptance

| Tiêu chí | Bằng chứng đã có | Giới hạn còn lại |
|---|---|---|
| Coordinator/Research/Verifier thực sự phân công | Task DAG, role riêng, trace model/tool/task và conditional supplemental tasks trong tests | Model planning/generation là scripted ports; chưa đo fresh live reasoning |
| Câu đơn/nhiều nguồn/follow-up/scope | Fan-out/dependency; giữ năm/đối tượng/phủ định; topic switch; canonical HTTP/citation readback | Chất lượng/đầy đủ nhiều câu với model thật `not_verified` |
| Thiếu lượt đầu, bổ sung có ích | `backend-13.xml`: Research gọi lexical search/read thật; lần đầu thiếu trang39, truy vấn bổ sung tìm được và readback/hash khớp | Planner/generation/verdict scripted; không phải BGE hoặc live generation |
| DAG/tool/output giả, claim sai | Cycle/unknown/trùng/tool sai/provenance giả bị chặn; claim sai90.000 so nguồn50.000 bị gate chặn; bounded revision | Tests hữu hạn không chứng minh bảo đảm tuyệt đối |
| Missing facts/source/conflict/fault | Clarification/resume; missing source khác model/source timeout/unavailable/failure; partial giữ nghĩa một phần | Chưa đo tỷ lệ đúng phân loại với model thật |
| Limits/deadline/cancel/concurrency | Shared reservations, token/call/tool caps, no-progress/query repeat, elapsed deadline qua resume, cancel join | Cost/native live exhaustion không phát sinh inference mới; kiểm admission và guards hiện có |
| Persistence/cache/reconnect/resume | Reload repository/app; task đã xong không Research lại; CAS/lease, unknown reservation giữ; scope revoked chặn; guarded runtime restart/readback | Crash khi provider thật đang in-flight chưa thử; unknown outcome không tự retry |
| UI và service giấy xác nhận | Build02 exit0;74 frontend tests; browser guarded error/reload; API preview retry cùngID, explicit confirm;44 tests hồ sơ nằm trong regression | UI positive model live chưa kiểm do cap; source/citation positive đã kiểm HTTP bằng scripted model+nguồn thật |

Suite liên quan `backend-12.xml`: **162 passed**,23,90s, exit0. Source corrective bổ sung `backend-13.xml`: **1 passed**,5,22s. Identity/admission/model-timeout suite `backend-14.xml`: **58 passed**,25,22s. Các suite có ca trùng, không cộng thành số tests duy nhất. Reports trước có failures thật và được giữ: lỗi matcher Vitest mới, fixture thiếu faculty/quote quá dài, semantics SSE cũ và follow-up rèn luyện; đã sửa implementation/fixture phù hợp, không đổi gold/threshold để làm xanh.

`frontend-04.json`: **74 passed**,0 failed. `frontend-build-02.json`: compile/TypeScript/static build exit0. Browser đã quan sát đăng nhập, hỏi đáp bị admission chặn, thông báo lỗi và reload cùngconversation; đây là actual guarded UI, không phải live RAG. Bằng chứng backend positive mở nguồn thật/hash/source ownership và terminal history qua HTTP ở `test_multi_agent_api.py`.

Kiểm scoped cuối sau các sửa nhỏ: `backend-15.xml` **38 passed**,22,69s, exit0; gồm workflow, admission, source corrective, API và resume. `runtime-readback-02.json` xác nhận bản runtime cuối sau restart;0 provider/native calls, hồ sơ chặng1 và lịch sử còn nguyên. Không cộng các lần chạy trùng nhau thành một tổng tests.

## Development sources và quality chưa đo

`source-regression-01.json` giữ từng câu của dev48: **34/40** ca có gold source tìm đủ các nguồn bằng lexical search+readback canonical;48 ca chạy,0 provider calls,0 native inference. Misses: **004,009,012,018,029,031**. Đây là phép source-only regression, không phải Advanced baseline mới, benchmark kiến trúc, neural recall, answer correctness hoặc generation. Giữ4 misses neural lịch sử012/020/029/039 trong evidence cũ; không sửa matcher/gold để suy ra đã khắc phục mọi miss.

Ca corrective nguồn thật mới chứng minh một lựa chọn bổ sung có ích cho012; chưa chứng minh khắc phục cả dataset bằng model thật. Không có kết luận multi-agent tốt hơn kiến trúc khác. Corpus presence/hash không đồng nghĩa câu trả lời đủ/correct. Bộ48 là development, không held-out.

Ledger read-only tại các lần nguồn/runtime proof còn **8495/8500 calls**; charged bảo thủ **1,7546595/3USD**, còn1,2453405USD; native **1990/2000 inference**, HTTP2018/6000, tokens394527/750000. Không tăng/reset cap, không refund uncertain reservations. Full profile cần12 paid calls và worst-case36 native sequences/run; hiện không đủ. Ngay ca grounded đơn trong control-flow có8 model calls, vượt5 headroom. Live mode bị chặn trước Gateway; USD còn không thay call cap.

**Các phần chưa kiểm chứng:** fresh live Coordinator/Research/Verifier trên dev questions; chất lượng đúng/đủ và hallucination/citation entailment với model thật; cost/latency live multi-agent; UI positive live; crash/restart giữa provider inference thật. Code runner/tools/admission đã có để tiếp tục khi nguồn lực và writer ownership được cấp/xác minh phù hợp. Không cần so sánh/ablation. Chưa triển khai chặng5–7 hoặc môi trường production.

## Thời gian và evidence

Bắt đầu quan sát tool lúc **11:56:33 UTC13/10/2026** (18:56:33 Bangkok). Giờ chốt/calendar ở `verification-manifest-01.json`. Thời gian Codex active và external wait riêng chưa có telemetry đầy đủ nên để **null**, không lấy calendar duration làm active time. Các test/build duration là thời gian tool đo, không tổng giờ Codex.

Manifest ghi hash code/config/source/outputs, lệnh/exit/test verdict và source corrective trace trích từ DB test trong namespace mới. Git diff so HEAD chứa nhiều dirty changes có trước; không xem toàn diff là do chặng này. Các file deleted và dữ liệu ngoài scope được giữ; artifact mới tên/path riêng, không ghi đè reports cũ.
