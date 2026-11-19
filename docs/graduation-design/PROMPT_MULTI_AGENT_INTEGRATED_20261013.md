# Prompt tiếp tục chat chặng 2 — Multi-agent tích hợp

Dán phần trong khối dưới đây vào chat đang làm chặng 2. Đây là prompt tiếp tục từ trạng thái hiện có, không yêu cầu xóa code hoặc tạo chat mới.

```text
Tiếp tục triển khai Campus 24/7 trong chat này theo thay đổi phạm vi trực tiếp của tôi:
“tôi muốn dùng multi agent luôn, ko cần so sánh nữa, gộp chặng 2-3-4 lại”.

Thay mục tiêu single-agent riêng và yêu cầu so sánh trong prompt trước bằng một chặng MULTI-AGENT TÍCH HỢP gồm toàn bộ phần chức năng cần thiết của chặng 2–3–4. Triển khai code, tích hợp vào ứng dụng và kiểm chứng; không dừng ở kế hoạch hoặc tài liệu. Tiếp tục từ code đã viết trong chat này, không bắt đầu lại bằng việc xóa/reset dữ liệu hay bỏ thay đổi đang có.

1. Phạm vi hiện hành

Đọc AGENTS.md, docs/GRADUATION_PROJECT_PLAN_20261013.md, docs/graduation-design/README.md, docs/graduation-design/00_SHARED_ARCHITECTURE.md và docs/graduation-design/02_MULTI_AGENT_INTEGRATED.md.

Các file 02_SINGLE_AGENT_RAG.md, 03_MULTI_AGENT_SYSTEM.md và 04_ADAPTIVE_ORCHESTRATION.md là tham khảo kỹ thuật cũ. Những mục xây single-agent riêng, router chọn Advanced/single/multi, so sánh kiến trúc, ngân sách tương đương hoặc ablation đã được thay bằng phạm vi mới. Không cần viết hoặc chạy các phép so sánh đó. Giữ code/corpus/index/evidence Advanced RAG hiện có để tái sử dụng và phục hồi.

Vẫn cần đánh giá chất lượng multi-agent: độ đúng/đầy đủ, coverage, citations, quyền, lỗi, persistence/resume, calls/tokens/cost và latency. Không suy ra multi-agent tốt hơn kiến trúc khác khi không đo so sánh. Chặng 5–7 giữ số hiện có; phần graph mở rộng, phúc khảo/hỗ trợ/quản trị tri thức và đánh giá cuối thuộc các chặng đó. Service adapter trong chặng gộp chỉ nối luồng giấy xác nhận đã có.

2. Kiểm kê và tận dụng công việc dở

Workspace là C:\Users\Duong Vinh\Vinh. Trước sửa, đọc file liên quan, kiểm tra git status và canonical/reparse paths, xác định runtime/ownership/ledger. Bảo toàn toàn bộ dirty/staged/untracked/ignored/deleted state, DB, corpus, index, nguồn, evidence và guard. Chỉ dùng patch có phạm vi; không commit/push, xóa/reset/clean hoặc mở môi trường production mới.

Chat này đã tạo application/single_agent/__init__.py, contracts.py, resources.py, controller.py và infrastructure/repositories/sqlite_agent_runs.py. Kiểm tra trạng thái thực tế, tính đúng và phần còn dở trước khi sử dụng. Tái sử dụng coverage/tools/resource/store thành phần chung hoặc Research worker nếu phù hợp. Tên single_agent đang có không ép phải hoàn thành một engine single-agent riêng; không cần xóa hoặc đổi tên hàng loạt. Có thể refactor bằng patch/module mới/adapter có chuyển tiếp phục hồi.

Không tạo chat mới hoặc Codex subagent. “Multi-agent” ở nhiệm vụ này là các agent bên trong ứng dụng Campus 24/7.

3. Kiến trúc cần thực hiện

- Coordinator: hiểu mục tiêu và lịch sử hợp lệ, lập CoverageItems và TaskPlan/DAG, phân công, đánh giá phần thiếu, quyết định tìm bổ sung/hỏi rõ/tổng hợp/chuyển hỗ trợ/dừng.
- Research: nhận mục tiêu con, lập và sửa truy vấn, gọi search_knowledge/read_source theo scope hiện tại, giữ provenance, đọc đủ parent và tìm bổ sung có ích.
- Verifier: nhận claims cùng source refs, mở nguồn gốc để kiểm điều kiện/phủ định/số/đơn vị/hiệu lực, phát hiện mâu thuẫn và phần thiếu, trả verdict typed và yêu cầu sửa/tìm tiếp.
- Service adapter: chuẩn bị draft/preview giấy xác nhận khi người dùng yêu cầu, qua service đã có quyền; việc gửi vẫn cần preview và explicit confirmation, quyết định cán bộ vẫn qua backend.

Các vai trò có thể dùng chung model nền, nhưng có context, prompt, hợp đồng và tool allowlist riêng. Thực hiện phân công/loop phụ thuộc dữ liệu thực tế; không biến một chuỗi prompt cố định thành “multi-agent” bằng cách đổi tên node. Câu đơn giản có thể chỉ cần một Research task rồi Verifier, câu nhiều vấn đề mới fan-out khi đủ tài nguyên. Đường hỏi đáp quy định mặc định dùng kiến trúc multi-agent này; điều hướng tĩnh và service flow vẫn qua application services phù hợp.

Application xác thực mọi đề xuất model trước dispatch. Model không tự sửa actor/role/scope, mở quyền, tăng ceilings, xác nhận hoặc thực thi nghiệp vụ. Truy hồi giữ publication/as-of/audience/scope; retry/subquery/cache/resume áp lại quyền hiện tại. Assistant history và kết quả agent khác không là nguồn sự thật.

4. Coverage, tools, DAG và vận hành

Tạo/reuse schemas RunContext, EvidenceRecord, CoverageItem, ClaimRecord, TaskPlan/TaskResult, ToolResult, ActionProposal và terminal adapter. Coverage phân biệt supported, missing_user_fact, missing_source, conflicting, out_of_scope. Evidence giữ source/version/locator/chunk/parent/hash/excerpt gốc; contextual metadata/FAQ và rank score không tự là bằng chứng.

Toolset bounded: search_knowledge, read_source, inspect_evidence, prepare_service_draft khi được cấp quyền. Không cho model gọi browser/network/code tùy ý. Giữ điều kiện cần/đủ, thời điểm, đối tượng, phủ định và giải tham chiếu hội thoại; topic switch không dùng nguồn cũ.

Task DAG có dependency/allowlist/lease/version/attempt/deadline; chặn cycle, task giả/trùng/vượt cap và output sai schema. Task độc lập được chạy đồng thời khi profile cho phép, dependency chạy đúng thứ tự. Research thiếu một phần thì Coordinator chọn nhiệm vụ bổ sung cụ thể. Verifier đọc source refs thay vì tin summary của Research; đồng thuận giữa agent không thay evidence gate.

Điều phối thích ứng trong multi-agent chọn số task, concurrency, số lượt tìm và early exit theo coverage/usage. Có bounds cho task/candidates/context/model/tool calls, query/evidence fingerprints, no-progress, deadline và cancellation. Không cần router giữa ba kiến trúc. Phân biệt missing_source, conflicting, timeout, model/tool failure và budget_exhausted; trả lời phần có căn cứ hoặc chuyển hỗ trợ với thông báo hữu ích.

Admission/reservation/reconciliation dùng ledger chung, gồm mọi agent, verifier, synthesis và retry; không nhân cap theo số worker. Cache gắn scope/source/index/model/config/version/as-of và revalidate trước hit. Ghi usage thật; thiếu telemetry là unknown.

Lưu run/task/coverage/evidence refs/claims/verdict/checkpoint/cursor/usage bền vững. Resume xác thực actor và source eligibility hiện tại; lease/CAS tránh hai worker nhận cùng task. Crash/restart/reconnect giữ kết quả đã lưu; side effects qua transactional executor/idempotency/audit, không lặp hồ sơ. Không lưu secret/raw prompts/chain-of-thought vào checkpoint hoặc UI.

Giữ API/SSE/history/citation compatibility qua adapter. UI cho thấy tiến độ/task/source, clarification/partial/error đúng nghĩa và terminal reload được. Domain rules ở application/domain, không ở route/UI. Giao diện và bản giấy xác nhận tiếp tục không có nhãn demo/mô phỏng theo yêu cầu trước; internal provenance và môi trường synthetic vẫn trung thực.

5. Bàn giao và giới hạn runtime

Đọc docs/CERTIFICATE_STAGE1_INVENTORY_20261013.md, CERTIFICATE_STAGE1_RUNBOOK_20261013.md, CERTIFICATE_STAGE1_DELIVERY_20261013.md và evidence infra/local/certificate-stage1-20261013-01/. Chặng 1 có 44 backend tests, 28 frontend tests và build cuối qua; luồng sinh viên/cán bộ giữ dữ liệu qua restart. Đây là bằng chứng local/synthetic đã quan sát, không phải production readiness.

Giữ nguyên demo.sqlite3, lịch sử hồ sơ/session/audit và mọi evidence. Dataset evals/datasets/certificate-development-20261013.json gồm 48 câu là development/regression, không phải held-out. Có 4 misses nguồn CERT-DEV-012/020/029/039 và thông báo thiếu bằng chứng về phí còn khó hiểu; xử lý bằng nguồn/behavior thật, không sửa gold/ngưỡng để làm xanh.

Corpus phục vụ là canonical human-reviewed, khác raw OCR ghép trang. Đối chiếu source/version/chunk/locator/hash thực tế; trang 39 có các mục giấy xác nhận và nghỉ học khác nhau, không gán nhầm điều kiện. Index/model/config fingerprint phải được ghi cho implementation mới.

Public API8000 và BGE18081/18082 là runtime từ công việc trước, giữ shared paid/native ledger; không dừng/restart hoặc tạo writer thứ hai khi chưa xác minh ownership và phương án chuyển tiếp. Front3000/3001 cũng là runtime trước. API hồ sơ8002/front3002 thuộc launcher chặng1; đối chiếu receipt/PID ancestry trước restart nếu cần. PostgreSQL ownership chưa được xác minh, không tự coi DB disposable.

Snapshot bàn giao chặng1 trong delivery-readback-01.json: paid calls8495/8500, conservative charged1.7546595USD trong cap3USD, còn5 provider calls; native inference1990/2000, HTTP2018/6000, tokens394527/750000, còn10 inference. Đây là snapshot cũ, kiểm ledger hiện hành bằng read-only trước mọi live plan. Không tự tăng/reset cap, hoàn lại uncertain reservations hoặc mở Gateway writer khác để inspect/evaluate. USD còn không thay call cap.

Triển khai và kiểm deterministic/offline/cached evidence trước, tận dụng công việc độc lập. Live chỉ chạy khi toàn bộ headroom đủ. Nếu acceptance live thật sự thiếu tài nguyên, hoàn thiện phần độc lập/runner trước, báo chính xác phần chưa kiểm chứng và tài nguyên/quyền còn thiếu; không dừng từ đầu hoặc gắn nhãn live cho doubles/cache. Không có phép so sánh bắt buộc nên không tiêu tài nguyên cho benchmark kiến trúc.

6. Tiêu chí nghiệm thu chặng gộp

- Coordinator/Research/Verifier hoạt động với hợp đồng riêng; trace cho thấy phân công thực sự theo mục tiêu/evidence.
- Câu đơn/nhiều nguồn/follow-up giữ điều kiện/scope; clarification cho thiếu user facts; không bịa khi thiếu nguồn, mâu thuẫn hoặc lỗi.
- Có ca lượt tìm đầu thiếu bằng chứng, agent chọn search/read bổ sung có ích; tool thật, source readback/hash đúng.
- DAG hợp lệ; task độc lập thực sự fan-out khi profile đủ, task phụ thuộc đợi kết quả; output/tool/DAG giả bị chặn trước effect.
- Verifier chặn claim không được nguồn hỗ trợ; hai agent đồng ý sai không vượt gate.
- Loop/no-progress, cap/deadline/cancel dừng đúng; reservations đồng thời không vượt ceilings.
- Crash/restart/reload/reconnect/resume/cache giữ task/terminal và kiểm quyền/source hiện tại, không lặp side effects.
- UI/citations/history chạy qua backend; luồng giấy xác nhận và preview/confirmation chặng1 không hồi quy.
- Kiểm thử phù hợp, build và kiểm UI cần thiết qua. Ghi từng ca/verdict/failure/skip/not_verified, fingerprint, usage/cost/latency thật hoặc unknown. Không yêu cầu benchmark single/multi/Advanced hoặc ablation.

Doubles chỉ chứng minh schema/control flow/fault/concurrency; source checks và live generation được ghi riêng. Chỉ kết luận completed khi acceptance đã qua; phân biệt implementation đã có với phần chưa được kiểm chứng.

7. Cách thực hiện và đầu ra

Làm theo lát cắt: kiểm kê và schemas/tools → Coordinator/Research/Verifier/DAG → budget/controller/persistence → API/SSE/UI → kiểm chứng và bàn giao. Điều chỉnh kỹ thuật linh hoạt theo code thực tế, không yêu cầu duyệt tài liệu/task catalog lịch sử. Tiếp tục phần đã được cho phép mà không hỏi lại approval thực thi.

Ghi thời gian Codex hoạt động, thời gian chờ và calendar riêng; chưa đo thì không bịa. Chia sẻ cập nhật ngắn bằng tiếng Việt trong lúc làm. Tạo evidence/output mới với tên/path riêng, không ghi đè lượt cũ. Kết thúc bằng implementation local chạy được, runbook, runtime receipt/config và cách phục hồi, báo cáo từng acceptance cùng giới hạn trung thực. Không tự tạo chat/chặng sau khi chưa có yêu cầu mới.
```
