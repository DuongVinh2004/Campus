# Kế hoạch hợp nhất AI multi-agent cho sinh viên và cán bộ — Campus 24/7

Ngày lập: 14/10/2026, múi giờ Asia/Bangkok; cập nhật chặng10 ngày 15/10. Trạng thái thực hiện: **UNI-001/002 verified; UNI-003–020 implemented ở source local, chưa verified đầy đủ; next_task UNI-021**. Chặng10 nối binding task/goal/scope, specialist/tool/evidence, checkpoint/receipt và budgets vào orchestrator cùng các consumer hiện có. Bộ kiểm backend/hợp đồng chặng10 đạt **608 ca duy nhất** sau khử trùng; TypeScript/production snapshot build đạt. Không chạy test giao diện, human baseline hoặc tải/p95. Không restart runtime, migrate DB gốc hoặc dispatch paid model. Host vẫn quan sát v5/build cũ; source v10 chưa được nạp vào writer/runtime. Bốn database giữ lại không đổi theo mọi bảng/hàng. [Kết quả chặng10 và giới hạn](UNIFIED_AI_SESSION10_20261015.md), [chặng09](UNIFIED_AI_SESSION09_20261015.md), [chặng08](UNIFIED_AI_SESSION08_20261014.md). Trạng thái/evidence mới nhất nằm trong backlog, không suy full acceptance hoặc usefulness từ mô tả thiết kế bên dưới.

**Điểm vào thực hiện:** tài liệu này và [backlog hợp nhất](UNIFIED_AI_IMPLEMENTATION_BACKLOG_20261014.json). Tiếp tục theo `next_task` và evidence thực tế. Một candidate local tại `http://localhost:8006/login`; [khảo sát/baseline/giới hạn](UNIFIED_AI_RUNTIME_INVENTORY_20261014.md). Các source plans giữ nguyên; không chạy hai backlog như hai bộ công việc độc lập.

## 1. Phạm vi hợp nhất và trạng thái trung thực

Hợp nhất toàn bộ yêu cầu và đề xuất của cuộc chat:
- Lưu lịch sử, câu trả lời trực quan, settings và quyền theo từng người.
- Cá nhân hóa, memory có kiểm soát, mục tiêu/task nhiều bước, hỗ trợ chủ động và bàn giao.
- AI hỗ trợ mọi thao tác ở cả hai giao diện, chuẩn bị tối đa để người dùng ít nhập lại, ít tìm kiếm, ít giải thích lại.
- Hiểu đúng mục đích và giữ độ chính xác, nguồn, quyền, phiên bản, xác nhận và kết quả đáng tin cậy.
- Cán bộ có bộ hồ sơ làm việc, checklist có căn cứ, review tập trung vấn đề, draft phản hồi/kết quả, autosave, delta recheck, bổ sung liên thông, batch và dashboard điểm nghẽn.
- Một trung tâm điều phối AI multi-agent dùng chung quy trình và trạng thái nghiệp vụ, có specialist và ngân sách rõ, ngữ cảnh/quyền/memory/internal notes phân tách.

Tài liệu này chi tiết hóa thiết kế đã trao đổi, không cấp quyền destructive/production/paid-service mới, không bổ sung approval gate tài liệu và không sửa safety instructions. Tại lúc lập tài liệu, phạm vi là lập/lưu kế hoạch. Yêu cầu trực tiếp sau đó đã bắt đầu triển khai local/synthetic; không suy quyền production, destructive action, dịch vụ trả phí mới hoặc gửi thông tin cho người khác từ kế hoạch này.

Trạng thái runtime/source ở phần 3 là quan sát mã nguồn, chưa xác nhận môi trường đang phục vụ. Những capability đã có phải được kiểm chứng trước khi tái sử dụng; không gắn completed/verified chỉ vì tồn tại code/test. Bản hợp nhất có 50 task UNI, 26 nhóm yêu cầu REQ và 50 nhóm acceptance AT.

## 2. Nguồn và cách chuyển từ các kế hoạch trước

Tài liệu được giữ nguyên:
1. [Đề xuất cá nhân hóa](ASSISTANT_PERSONALIZATION_PROPOSAL_20261014.md).
2. [Đề xuất nâng cao và AI xuyên ứng dụng](ASSISTANT_ADVANCED_PROPOSAL_20261014.md).
3. [Kế hoạch trước: 30 task AI](ASSISTANT_IMPLEMENTATION_PLAN_20261014.md).
4. [Backlog trước](ASSISTANT_IMPLEMENTATION_BACKLOG_20261014.json).
5. [Đề xuất cán bộ: 12 hạng mục ST](STAFF_ASSISTANT_PROPOSAL_20261014.md).
6. Xác nhận kiến trúc trong chat: multi-agent điều phối chung hai bên, backend kiểm tra và thực hiện.

Backlog mới có source_refs ánh xạ toàn bộ AI-001–030 và ST-01–12 sang UNI. Một task cũ có thể tách sang nhiều UNI; một UNI có thể hợp nhất phần trùng. Những hạng mục multi-agent mới có source CHAT-MULTI-AGENT-CENTER. Không mang trạng thái verified sang vì chưa có evidence triển khai trong cuộc chat này.

Bắt đầu thực hiện bằng UNI, không chạy lại AI/ST riêng. Source refs phục vụ truy vết yêu cầu, không phải công việc phụ thêm. Bản mới là điểm vào thống nhất của kế hoạch này; direct request sau này và instructions áp dụng vẫn có hiệu lực cao hơn.

## 3. Hiện trạng cần tái xác minh trước triển khai

- student-chat.ts lưu localStorage theo mode/user; assistant-context.tsx mặc định guidanceAdapter chưa truyền lượt chat trước. StudentRuntime có điều hướng /chat sang /student/assistant khi áp dụng cho sinh viên.
- AssistantConversation dùng đoạn văn; ChatPanel đã có react-markdown/remark-gfm. Tận dụng renderer và libraries hiện có.
- ConversationMessageService fallback in-memory khi không inject; main.py gọi create_app mặc định. Có SQLite/PostgreSQL repositories; một số launcher đã inject SQLite. Cần chốt đúng launcher/storage trước sửa.
- Chat có create/messages/stream/history restore theo ID, nhưng cần discovery/metadata theo tài khoản. Retention đọc có mốc hết hạn; tạo mặc định 30 ngày phải được xác minh và hiển thị đúng.
- Consent có OPTIONAL_PERSONALIZATION nhưng có trạng thái bộ nhớ/demo; UI không đủ chứng minh persistent grants.
- Multi-agent hiện có coordinator/research/verifier, typed task DAG, evidence/source refs và model budgets. TaskSpec giới hạn roles/tools; role đa dạng hơn trong thiết kế là capability logic dự kiến, không phải các agent đã triển khai.
- CertificateDraftAdapter có biên chuẩn bị/preview; không expose confirm/submit/staff methods cho model. Giữ biên này khi thêm staff DTO/adapters; không mở công cụ ghi tổng quát.
- Có agent-run read/resume/cancel, scope/ownership/version checks. Có draft/preview/confirm/idempotency/receipt và transactional service flows để tái sử dụng sau test.
- StaffTicketWorkspace/staff-policy có snapshots, apply/undo, required review/readiness và nguồn. StaffTicketQueue có confidence/stamp/SLA constants; không coi đó là kết quả xác minh thật.
- useStaffDraft có Map của phiên và save riêng; staff claim service có process-local locks/dictionaries. Không suy ra đủ độ bền hoặc concurrency nhiều instance.
- Launcher có thể phục vụ frontend snapshot riêng dưới infra/local. Working tree có nhiều dirty/untracked/deleted từ trước; không reset/clean hoặc overwrite để có môi trường đẹp.

UNI-001 ghi nhận exact runtime/build/API, role/tenant/subject, storage/retention, nguồn/capabilities và commands đã kiểm chứng; không dump dữ liệu thật/credentials. UNI-002 lập inventory route/action/field cho student, staff và admin. Phần chưa hỗ trợ là gap, không tính là đã đáp ứng “AI ở mọi nơi”.

## 4. Kiến trúc mục tiêu của trung tâm multi-agent

### 4.1. Các lớp và thẩm quyền

Luồng logic:
**Giao diện sinh viên/cán bộ → runtime/context chung → xác thực và scope server → coordinator/task state → specialist cần thiết → kiểm chứng source/rule/output → proposal hoặc trả lời → preview/xác nhận theo workflow → application executor → transaction/receipt/events → views theo quyền.**

Đây là trung tâm điều phối logic; không bắt buộc một process, một model lớn hoặc mọi thao tác đi qua nhiều model calls. Tra cứu trạng thái và kiểm tra quy tắc xác định đi đường ngắn phù hợp; tác vụ phức tạp mới fan out specialist. Tận dụng stack/controller/orchestrator đã có, không thay framework hoặc thêm microservice/graph database nếu chưa có bằng chứng cần.

| Thành phần | Trách nhiệm | Giới hạn |
| --- | --- | --- |
| Coordinator | Giữ mục đích, chọn task/dependencies, phân ngân sách, tổng hợp coverage | Không tự cấp quyền hay xác lập kết quả hành chính |
| Hiểu mục đích | Outcome/purpose/constraints/facts/missing, clarification | Suy luận chưa xác nhận không thành fact |
| Research/knowledge | Tìm nguồn/rule/phiên bản áp dụng | Scope và source hiệu lực kiểm tra server |
| Document/evidence | Trích xuất, đối chiếu, tìm locator, so sánh bổ sung | OCR không chứng nhận tài liệu/chữ ký/con dấu |
| Draft/workflow preparation | Chuẩn bị form/checklist/response/next step có cấu trúc | Không gọi confirm/approve/submit thay cán bộ/người dùng |
| Verifier | Kiểm chứng coverage/claims/evidence, nêu conflict/missing | Model đồng ý không thay domain/authority checks |
| Application executor | Validate, authorize, confirm, version, commit/receipt | Ngoài model; không tin bool user_confirmed do model tạo |

Tên specialist là trách nhiệm logic: có thể là module, typed service call hoặc subtask model tùy UNI-016–018; không cần sáu agent riêng cho một câu đơn giản. Việc nhiều agent trong sản phẩm không cho phép coding agent tự spawn subagents trong phiên làm việc này.

### 4.2. Hợp đồng điều phối và xử lý lỗi

Mỗi run có actor/tenant/scope reference, conversation/task/resource IDs, base versions, goal+constraints, coverage requirements, config fingerprint, as_of, deadline và budgets. Mỗi task có ID/role/goal/dependencies/allowed tools/minimal inputs/expected schema và trạng thái. Server gắn tools/quyền; model chỉ đề xuất hợp lệ.

Handoff dùng typed outputs và evidence refs có thể kiểm tra, không truyền toàn bộ chat/notes/sensitive data giữa specialists. Original source giữ authority; tóm tắt worker không thay source. Các lựa chọn quan trọng unresolved thì làm rõ, missing source thì tìm trong phạm vi hoặc abstain/next step; không gán lỗi thiếu nguồn thành lỗi user thiếu facts.

DAG validation, bounded concurrency/retries/tool calls/model calls/cost/context và cancellation dùng ngân sách chung. Partial worker failure không báo success; checkpoint giữ work nhưng không chứa confirmation token hoặc quyền lưu từ thời điểm cũ. Resume đọc lại identity/scope/resource/source version và chống concurrent executions. Mâu thuẫn agents được kiểm tra nguồn; không dùng đa số phiếu như chân lý.

Task/run events cho UI gồm trạng thái cần biết như đang đọc nguồn, cần bổ sung, chờ xác nhận, đã commit hoặc lỗi. Không hiển thị raw prompt, secrets hoặc suy nghĩ nội bộ. Trace metadata phải đủ nối task/evidence/action mà tối thiểu dữ liệu riêng.

### 4.3. Dùng chung hồ sơ, tách dữ liệu cá nhân và quyền

Hai phía chia sẻ business state và public exchanges được phép; student view và staff view là projections theo role/resource/queue/assignment. Notes nội bộ, personal memory, settings, nháp chưa gửi và nguồn hạn chế không tự chuyển qua phía còn lại.

Đọc source/cache/evidence, chuẩn bị proposal, resume và execute đều reauthorize. Shared cache chỉ reuse khi scope/versions tương thích và current actor được phép; cache không vượt ACL. Worker chuẩn bị nền cần service scope được cấu hình; không tự dùng mọi quyền cán bộ. Policy/rule/template updates vẫn theo workflow tổ chức hiện hành.

## 5. Thiết kế trải nghiệm hai phía

### 5.1. Sinh viên

- Lịch sử server có discovery, search tiêu đề, rename/pin/archive, phân trang và saved/pending/interrupted states; restore đúng citations/status. Chat mới không xóa dữ liệu.
- Nêu mục đích hoặc thao tác trực tiếp; AI dùng fact hợp lệ đã cấp, chọn workflow, mở/tạo đúng draft, điền sẵn và chỉ hỏi phần còn thiếu làm đổi quyết định.
- UI hỗ trợ ở route/panel/field/tài liệu/error/request/schedule/settings; context tối thiểu theo schema, không copy tình huống sang chat hoặc đọc toàn DOM.
- Manual edits được giữ, AI proposals có diff và version; tài liệu/OCR là candidate cho đến khi xác minh tương ứng.
- Preview mô tả thủ tục/mục đích/recipient/material data/attachments/chi phí hoặc hạn nếu có nguồn. Confirm/receipt theo workflow, không hứa thời hạn chưa có căn cứ.
- Vùng tiếp tục công việc đưa về đúng draft/case/next step qua nhiều phiên. Temporary chat và memory off có semantics rõ.

### 5.2. Cán bộ

- Queue nhóm việc đủ căn cứ để xem xét/cần xác minh/cần bổ sung/đang chờ/bị chặn; priority từ policy/source, reason và next step; giữ vị trí queue.
- Case package chuẩn bị mục đích/facts/documents/timeline/criteria/rules/sources/draft; từng claim mở đúng locator/version.
- Rule checks, AI proposal và officer-reviewed findings tách rõ; readiness không tự tick hoặc bypass mandatory review.
- Chuẩn bị trước và dependency-based invalidation: data→criterion→finding→summary/draft. Source/fact/document/template thay đổi thì recheck đủ phần bị ảnh hưởng; giữ phần khác chỉ khi còn hợp lệ.
- Server autosave nháp theo officer/case/version, CAS nhiều tabs/actors và durable assignment. Saved chỉ sau ack; unsaved safeguards hiện có được giữ.
- Draft public response/internal note/result đúng template, có structured outcome do người có thẩm quyền; pre-execution check recipient/role/queue/assignment/source/version/confirmation.
- Chuẩn bị batch và execute nếu policy/capability cho phép, per-item checks/receipt/partial states; không copy kết luận, mở rộng targets, auto merge/delete/reject duplicate candidates.
- Dashboard active/wait time/age/blockers/supplement/reopen; không đánh giá năng suất bằng số case thô bỏ complexity.

### 5.3. Vòng xử lý khép kín

**Sinh viên nêu mục đích → chuẩn bị nháp và kiểm tra → xác nhận nộp → receipt → chuẩn bị case package cho cán bộ → review bắt buộc → yêu cầu bổ sung có cấu trúc nếu cần → checklist tương ứng ở sinh viên → bổ sung có receipt → delta recheck cán bộ → draft kết quả → xác nhận theo thẩm quyền → receipt và next step hai phía.**

Supplement item có ID, criterion/field, missing fact/document, public reason và quy cách được nguồn xác định. Gom tất cả missing đã biết trong scope, không đòi lại phần đủ hoặc thêm yêu cầu suy đoán. Staff preview/confirm chọn public content; private notes không chuyển. Bổ sung map đúng item để giảm hỏi lại và đọc lại.

Bàn giao chọn done/open/evidence/resources/next step, kiểm tra target/scope và preview trước gửi. Notification chỉ trigger/resource/channel được user chọn; no-change im lặng, dedup/quiet hours/stop tracking/revoke có hiệu lực; event không tự tạo hành động ghi.

## 6. Thiết kế dữ liệu, API và bảo toàn

| Thực thể | Trường cần có | Ràng buộc |
| --- | --- | --- |
| Conversation/Message | actor/tenant, sequence, client ID, title, retention/mode, final status/citations/schema | Durable ack, isolation, paging, retry |
| Preferences/Consent/Grant | actor, choices/purpose/capability/resource, expiry/revoke/version | Policy intersection, CAS, không mặc nhiên consent |
| Workflow/Rule/Template | ID/version/effective interval/applicability/criteria/state/action/mẫu | Một definition và phiên bản áp dụng đúng |
| Intent/Task/Run | goal/facts/provenance/missing/coverage, refs/versions/state/next action/budgets | No fake facts/authority, restart/resume safe |
| Case/Draft/Assignment | case/student/officer/queue, payload/base version/save state | Preserve manual work, concurrency |
| Evidence/Finding/Review | source/rule/resource versions, hashes/locator/data/check type/actor/time | Source trace, mandatory reviews, stale invalidation |
| Supplement/Handover | typed items, public/internal content, target/refs/version/confirmation | Round-trip đúng item và scope |
| Action/Batch/Receipt | operation/exact targets/payload hashes/versions/expiry/idempotency/results | Server authorization, per-item outcomes, no duplicates |
| Memory | actor/type/minimal content/source/time/validity/scope/confirmed/suppressed | Opt-in, update/forget, không private cross-user |
| Subscription/Event/Delivery | actor/resource/trigger/channel/quiet/expiry/dedup/receipt | Reauthorize, no-change suppression |

SQLite local hiện có và PostgreSQL nhiều user được wiring theo môi trường đã xác minh. Migration bổ sung, index owner/tenant/time và resource/criterion/version; cache browser tối thiểu, không lưu toàn bộ hồ sơ riêng trên thiết bị chung. Data/notes/receipts không trở thành prompt instructions hoặc quyền model.

API mới/extension phải chốt trong UNI-004 trước code:
- Conversation list/metadata/message stream hiện có, cursor/version/client id và history/temporary modes.
- Me assistant preferences/capabilities/grants/memory; effective scopes và locked reasons; identity server.
- Typed assistance request nhận goal/context/resource/version; trả interpretation/missing/evidence/proposal/allowed next actions. Không browser tự bind owner hoặc tạo authority.
- Draft/preview/confirm hiện có; mở rộng staff draft/review/supplement/task/batch/subscriptions chỉ nếu chưa có equivalent.
- Server field/domain validation, concealment/error conventions, expected version/CAS, bounded payloads, no-store dữ liệu riêng và idempotency phù hợp.
- Confirmation tokens chỉ trong established UI/API path, không model hoặc checkpoints.

Version áp dụng theo mốc workflow, không mặc định newest cho mọi hồ sơ cũ. Mọi action revalidate material facts, recipient, assignment và applicable sources. Transaction/receipt/audit/outbox nhất quán; timeout đọc lại trước retry. Chỉ báo đã lưu/gửi/hoàn tất theo acknowledgement/receipt/business state.

Giữ legacy localStorage/database/snapshots/dirty files. Import phải xác minh sở hữu, preview, provenance, dedup và receipt; demo không trộn thật. Chưa xác minh thì giữ source và export/next step. Tắt feature vẫn đọc được history/drafts/evidence/receipts và thao tác thủ công; không reset/drop/delete cleanup hoặc sửa safety controls để rollback. Retention/temporary/export/erasure theo lựa chọn được thông báo và policy hiện hành, không auto lưu vô thời hạn.

## 7. Danh mục yêu cầu

Yêu cầu trực tiếp và phần thiết kế bổ sung đã trao đổi đều được truy vết. REQ mô tả mục tiêu; task/AT là cách triển khai và kiểm chứng, không claim capability đã hoạt động.

| ID | Yêu cầu | Nội dung | Công việc |
| --- | --- | --- | --- |
| REQ-01 | Lịch sử theo tài khoản | Lưu bền vững, danh sách/tìm/open, trạng thái lưu, restore và tiếp tục; new chat không xóa chat cũ. | UNI-001, UNI-004, UNI-006, UNI-007, UNI-011, UNI-012, UNI-013, UNI-040, UNI-044, UNI-047, UNI-048, UNI-049, UNI-050 |
| REQ-02 | Câu trả lời trực quan | Ngắn phù hợp mục đích; bước/bảng/thẻ/proposal/source; responsive, keyboard, dark và tin cũ. | UNI-013, UNI-014, UNI-025, UNI-042, UNI-044, UNI-047, UNI-050 |
| REQ-03 | Settings và cá nhân hóa | Cấu hình từng actor, chat override, bố cục/cách trả lời; giới hạn trong policy và templates hợp lệ. | UNI-009, UNI-015, UNI-032, UNI-039, UNI-040, UNI-047, UNI-049, UNI-050 |
| REQ-04 | Quyền và consent thực thi | Scope theo nguồn/tài nguyên/role/queue/assignment, expiry/revoke; kiểm tra ở server; consent tách quyền thao tác. | UNI-004, UNI-006, UNI-008, UNI-009, UNI-010, UNI-015, UNI-017, UNI-024, UNI-034, UNI-035, UNI-036, UNI-041, UNI-043, UNI-049, UNI-050 |
| REQ-05 | Hiểu đúng mục đích | Outcome/purpose/resource/constraints/facts; clarify phần làm đổi quyết định; giữ mục đích khi chuyển agent/route. | UNI-003, UNI-008, UNI-016, UNI-021, UNI-022, UNI-032, UNI-033, UNI-044, UNI-045, UNI-047, UNI-050 |
| REQ-06 | AI xuyên giao diện sinh viên | Điều hướng, dịch vụ, biểu mẫu, field, tài liệu, lỗi, hồ sơ, lịch, cài đặt; handler có ích theo scope. | UNI-002, UNI-011, UNI-014, UNI-023, UNI-025, UNI-032, UNI-044, UNI-047, UNI-049, UNI-050 |
| REQ-07 | Chuẩn bị thủ tục tối đa | Điền sẵn fact được phép; kiểm tra, missing-group, preview; không ghi đè manual edits hoặc tự quyết trường mơ hồ. | UNI-003, UNI-021, UNI-022, UNI-023, UNI-024, UNI-025, UNI-033, UNI-044, UNI-047, UNI-050 |
| REQ-08 | Chính xác và tin cậy | Nguồn/rule/schema/readiness/version/recipient/receipt; không model confidence hoặc prose thay nghiệp vụ. | UNI-001, UNI-003, UNI-004, UNI-005, UNI-010, UNI-014, UNI-016, UNI-017, UNI-018, UNI-020, UNI-021, UNI-022, UNI-023, UNI-024, UNI-026, UNI-027, UNI-028, UNI-029, UNI-030, UNI-031, UNI-036, UNI-039, UNI-043, UNI-044, UNI-045, UNI-046, UNI-047, UNI-048, UNI-050 |
| REQ-09 | Multi-agent điều phối hai bên | Một trung tâm điều phối logic, specialist theo nhu cầu, typed handoff/DAG/budgets; không mở rộng authority. | UNI-001, UNI-002, UNI-004, UNI-008, UNI-010, UNI-011, UNI-016, UNI-017, UNI-018, UNI-019, UNI-020, UNI-035, UNI-043, UNI-045, UNI-046, UNI-050 |
| REQ-10 | Quy trình và quy tắc dùng chung | Một definition có version/effective dates/mandatory steps/template cho student, staff và backend. | UNI-005, UNI-018, UNI-028, UNI-031, UNI-050 |
| REQ-11 | Bằng chứng và nguồn gốc | Claim/criterion/output truy nguồn; source locator/hash/version/actor/time; thiếu/xung đột/lỗi thời rõ. | UNI-008, UNI-017, UNI-018, UNI-027, UNI-029, UNI-034, UNI-045, UNI-050 |
| REQ-12 | Thực thi chống lỗi và trùng | CAS/version/claim/confirmation/idempotency/atomic receipts; retries/readback không tạo action khác. | UNI-004, UNI-006, UNI-010, UNI-012, UNI-019, UNI-022, UNI-024, UNI-030, UNI-031, UNI-035, UNI-036, UNI-043, UNI-048, UNI-050 |
| REQ-13 | Công việc liên tục | Goal/task/draft/case/run references, state/blockers/next action, restart/resume đúng bước. | UNI-006, UNI-008, UNI-011, UNI-013, UNI-016, UNI-019, UNI-022, UNI-025, UNI-034, UNI-035, UNI-041, UNI-042, UNI-044, UNI-049, UNI-050 |
| REQ-14 | Bộ hồ sơ làm việc cán bộ | Chuẩn bị mục đích/facts/tài liệu/timeline/checklist/căn cứ/dự thảo; mở nguồn trực tiếp. | UNI-026, UNI-027, UNI-028, UNI-029, UNI-032, UNI-037, UNI-047, UNI-050 |
| REQ-15 | Review tập trung vấn đề | Readiness có reason; phân biệt rule/AI proposal/officer review; giữ mọi kiểm tra bắt buộc. | UNI-005, UNI-018, UNI-026, UNI-028, UNI-033, UNI-037, UNI-047, UNI-050 |
| REQ-16 | Chuẩn bị trước và kiểm tra phần đổi | Versioned cache/dependencies/invalidation; compare supplement; không đọc/chạy lại phần không cần. | UNI-029, UNI-033, UNI-038, UNI-046, UNI-047, UNI-050 |
| REQ-17 | Bổ sung liên thông | Typed missing items/criteria/reason, staff preview/confirm public request, student checklist và delta readback. | UNI-033, UNI-034, UNI-035, UNI-038, UNI-041, UNI-044, UNI-047, UNI-050 |
| REQ-18 | Dự thảo phản hồi và kết quả | Templates đúng hiệu lực, structured decision facts/reasons, internal/public riêng, human decision theo thẩm quyền. | UNI-005, UNI-031, UNI-032, UNI-036, UNI-047, UNI-050 |
| REQ-19 | Nháp và phụ trách bền vững | Server autosave theo officer/case/version; concurrent tabs/people/process; không mất nháp hoặc làm trùng. | UNI-006, UNI-010, UNI-030, UNI-031, UNI-037, UNI-050 |
| REQ-20 | Xử lý gộp có kiểm chứng | Exact targets/per-item payload/check/receipt; partial outcomes; execute chỉ khi capability/policy cho phép. | UNI-036, UNI-046, UNI-050 |
| REQ-21 | Ưu tiên, bàn giao và điểm nghẽn | Deadlines/routing có căn cứ; context đúng scope; active/wait time; không tự đổi policy vì backlog. | UNI-002, UNI-034, UNI-037, UNI-038, UNI-042, UNI-050 |
| REQ-22 | Memory có kiểm soát | Opt-in từng actor; source/time/scope; update/abstention/forget suppression; không memory cross-user. | UNI-009, UNI-015, UNI-039, UNI-040, UNI-049, UNI-050 |
| REQ-23 | Hỗ trợ chủ động | Selected trigger/resource/channel/expiry/quiet hours; no-change suppression, dedup, revoke và stop tracking. | UNI-041, UNI-042, UNI-049, UNI-050 |
| REQ-24 | Chất lượng, chi phí và hiệu năng | Baseline, shadow và user pilot; latency/cost/tool limits, privacy metrics và evidence thực. | UNI-001, UNI-003, UNI-020, UNI-038, UNI-043, UNI-045, UNI-046, UNI-047, UNI-049, UNI-050 |
| REQ-25 | AI xuyên giao diện cán bộ/quản trị | Queue/detail/checklist/editor/error/handover/admin; staff intent đúng target; không copy hồ sơ sang chat. | UNI-002, UNI-011, UNI-014, UNI-015, UNI-026, UNI-027, UNI-032, UNI-037, UNI-044, UNI-047, UNI-049, UNI-050 |
| REQ-26 | Bảo toàn, riêng tư và phục hồi | Retain source data/dirty work/builds, verified migration, temporary/retention/export choices, recover without reset. | UNI-001, UNI-006, UNI-007, UNI-008, UNI-009, UNI-012, UNI-015, UNI-020, UNI-035, UNI-039, UNI-040, UNI-042, UNI-043, UNI-046, UNI-048, UNI-049, UNI-050 |

## 8. Lộ trình và các mốc kiểm chứng

Ước lượng toàn phạm vi: **48–76 ngày công kỹ thuật**, khoảng 10–16 tuần nếu một kỹ sư toàn thời gian, chưa tính lịch QA/người tham gia và tích hợp ngoài. Đây là forecast sơ bộ dựa trên tái sử dụng stack; không cộng thẳng hai kế hoạch cũ vì đã loại công việc trùng. UNI-001–003 cập nhật dự báo có evidence; không thay expected results/thresholds để đạt lịch.

Thứ tự mặc định theo U0–U11; dependencies trong backlog là quan hệ kỹ thuật, không approval gate. Một số nhiệm vụ có thể bắt đầu khi đủ dependencies dù nằm ở phase sau; không suy ra permission cho agent delegation. Tests/telemetry bắt đầu trong từng task, không đợi U10.

| Phase | Phạm vi | Ngày công dự kiến | Đầu ra/mốc |
| --- | --- | --- | --- |
| U0 | UNI-001–UNI-003: Khảo sát và baseline | 2–3 | M0: runtime, inventory, ca chuẩn và baseline |
| U1 | UNI-004–UNI-008: Domain, workflow, storage và context | 5–8 | Nguồn dữ liệu/quy trình và bảo toàn |
| U2 | UNI-009–UNI-015: Lịch sử, giao diện, settings và quyền | 5–8 | M1: nền tảng hai vai trò có hiệu lực |
| U3 | UNI-016–UNI-020: Trung tâm multi-agent và task bền vững | 5–8 | Phối hợp đúng scope, evidence và budgets |
| U4 | UNI-021–UNI-025: Sinh viên: hiểu mục đích và chuẩn bị thủ tục | 5–7 | Nộp đúng với receipt |
| U5 | UNI-026–UNI-032: Cán bộ: kiểm chứng và hỗ trợ xử lý | 7–11 | Review/draft/confirm đúng nguồn và thẩm quyền |
| U6 | UNI-033–UNI-035: Bổ sung và bàn giao khép kín hai phía | 3–5 | M2: pilot end-to-end hai bên |
| U7 | UNI-036–UNI-038: Batch, queue và tối ưu điểm nghẽn | 3–5 | M3: throughput có kiểm tra từng hồ sơ |
| U8 | UNI-039–UNI-040: Memory và quyền riêng tư | 3–5 | Cá nhân hóa dài hạn kiểm soát được |
| U9 | UNI-041–UNI-042: Theo dõi sự kiện và hỗ trợ chủ động | 3–5 | M4: chủ động trong grants |
| U10 | UNI-043–UNI-047: Đối kháng, E2E, shadow, tải và pilot | 5–8 | M5: evidence chất lượng và hiệu quả |
| U11 | UNI-048–UNI-050: Diễn tập, tài liệu và bàn giao | 2–3 | M6: deploy-ready nếu đủ evidence; chưa deploy |

M0 xác định đúng đường chạy; M1 đạt lịch sử/renderer/settings/quyền trên candidate; M2 thử một vòng thủ tục qua cả hai phía; M3 mới mở batch/routing; M4 mới mở memory/events đã kiểm chứng; M5/M6 đối soát toàn phạm vi và phương án phục hồi.

Pilot đầu gồm xin cấp giấy, yêu cầu bổ sung và phản hồi hỗ trợ, nối nguồn/workflow hợp lệ. Các case phúc khảo/đánh giá học thuật chỉ mở mức hỗ trợ có đủ dữ liệu, rules và acceptance phù hợp. M2 dùng tập AT tương ứng của UNI-024/031/033/035 qua UI thật; không cần bật memory, events hay batch chưa hoàn thiện. Những chức năng ngoài pilot vẫn là planned/gap, không đánh dấu toàn hệ thống completed.

## 9. Backlog triển khai chi tiết

Mỗi task có dependencies, REQ/AT và source refs trong JSON. “Phạm vi” là vùng dự kiến để đọc/sửa, không cấp quyền sửa mọi file trong thư mục. Khi bắt đầu chốt exact paths và inspected diff, giữ dirty state. Mọi task hiện planned, evidence rỗng. Tên module/API mới chưa tồn tại là thiết kế sẽ chốt trong UNI-004, không giả định đã có.

### UNI-001 — Khảo sát bản chạy, danh tính và storage

**Phase:** U0. **Phụ thuộc:** không. **Nguồn:** AI-001, ST-01.

- Phạm vi: scripts launch/prepare; bootstrap/main; StudentRuntime; staff routes; repositories.
- Thực hiện: Xác định build/API thực tế, mode/tenant/role, storage, retention, nguồn và capabilities; tái hiện các vấn đề trên hai giao diện.
- Điều kiện đạt: Có runtime map và evidence phân biệt source, snapshot, demo và bản dùng thật.
- Truy vết: REQ-01, REQ-08, REQ-09, REQ-24, REQ-26; kiểm chứng AT-01, AT-03, AT-29.

### UNI-002 — Lập ma trận thao tác và quyền của hai bên

**Phase:** U0. **Phụ thuộc:** UNI-001. **Nguồn:** AI-006, AI-020, AI-021.

- Phạm vi: routes/components student/staff/admin; tool/capability registry.
- Thực hiện: Inventory từng thao tác/field/error, vai trò, nguồn, handler và mức explain/prepare/execute; xác định phần chưa hỗ trợ.
- Điều kiện đạt: Mỗi thao tác có handler thật hoặc giới hạn/next step rõ; ownership và internal/public được ghi.
- Truy vết: REQ-06, REQ-09, REQ-21, REQ-25; kiểm chứng AT-02, AT-07, AT-11.

### UNI-003 — Baseline và bộ ca nghiệp vụ hai phía

**Phase:** U0. **Phụ thuộc:** UNI-001, UNI-002. **Nguồn:** AI-002, ST-01.

- Phạm vi: evals/fixtures và E2E candidate mới trong workspace.
- Thực hiện: Tạo ca mục đích rõ/mơ hồ, thủ tục, staff review, bổ sung, nguồn thiếu/cũ và lỗi; đo công sức/active/wait time; expected results có nguồn.
- Điều kiện đạt: Dataset theo case IDs, nguồn và kết quả mong đợi, baseline và ngưỡng pilot chốt trước đánh giá.
- Truy vết: REQ-05, REQ-07, REQ-08, REQ-24; kiểm chứng AT-12, AT-14, AT-30, AT-41, AT-49.

### UNI-004 — Hợp đồng dữ liệu, API và lỗi dùng chung

**Phase:** U1. **Phụ thuộc:** UNI-003. **Nguồn:** AI-003.

- Phạm vi: contracts/openapi/json-schema; application models; frontend types.
- Thực hiện: Định nghĩa intent/context/evidence/proposal/task/preferences/grant/supplement/batch; version, pagination, status/errors và backward compatibility.
- Điều kiện đạt: Payload ngoài schema/role/target bị từ chối; stream/citations cũ vẫn đọc được.
- Truy vết: REQ-01, REQ-04, REQ-08, REQ-09, REQ-12; kiểm chứng AT-05, AT-07, AT-18, AT-24.

### UNI-005 — Quy trình, quy tắc và template có hiệu lực

**Phase:** U1. **Phụ thuộc:** UNI-004. **Nguồn:** ST-02.

- Phạm vi: domain/application document_request; knowledge/policy_graph; contracts.
- Thực hiện: Một bộ định nghĩa phục vụ sinh viên, cán bộ và validation; chọn phiên bản áp dụng theo mốc cấu hình; giữ mandatory reviews.
- Điều kiện đạt: Cùng input cho cùng checks; nguồn/phiên bản chưa xác định không tạo kết luận; template có binding.
- Truy vết: REQ-08, REQ-10, REQ-15, REQ-18; kiểm chứng AT-21, AT-31, AT-35.

### UNI-006 — Storage bền vững và transaction

**Phase:** U1. **Phụ thuộc:** UNI-004, UNI-005. **Nguồn:** AI-004.

- Phạm vi: repositories; bootstrap/app/settings; migrations bổ sung.
- Thực hiện: Wiring conversation/settings/consent/grants/runs/drafts/evidence/receipts theo môi trường; indexes và isolation; không fallback in-memory âm thầm.
- Điều kiện đạt: Restart giữ dữ liệu đã commit; concurrency và DB failure có trạng thái đúng; migration fixture bảo toàn.
- Truy vết: REQ-01, REQ-04, REQ-12, REQ-13, REQ-19, REQ-26; kiểm chứng AT-03, AT-05, AT-07, AT-28, AT-33, AT-34.

### UNI-007 — Tương thích và chuyển dữ liệu có bảo toàn

**Phase:** U1. **Phụ thuộc:** UNI-006. **Nguồn:** AI-009, AI-029.

- Phạm vi: student-chat compatibility; import/export service; fixture rehearsal.
- Thực hiện: Xác minh legacy ownership, preview import, provenance, dedup và receipt; demo tách thật; không overwrite nguồn gốc.
- Điều kiện đạt: Unknown owner không import tùy ý; replay không trùng; dữ liệu gốc và build cũ được giữ.
- Truy vết: REQ-01, REQ-26; kiểm chứng AT-06, AT-50.

### UNI-008 — Ngữ cảnh có giới hạn và phân tách hai phía

**Phase:** U1. **Phụ thuộc:** UNI-004, UNI-006. **Nguồn:** AI-005.

- Phạm vi: conversation/context/history; identity/source factories; context contracts.
- Thực hiện: Server lấy history cùng chat, task/resource refs và dữ liệu tối thiểu; tách private memory, notes và role; freshness/version/budgets.
- Điều kiện đạt: Chuyển vai trò/resource không rò ngữ cảnh; context có manifest/source; dữ liệu không tạo quyền.
- Truy vết: REQ-04, REQ-05, REQ-09, REQ-11, REQ-13, REQ-26; kiểm chứng AT-07, AT-11, AT-22, AT-27, AT-48.

### UNI-009 — Preferences và consent bền vững

**Phase:** U2. **Phụ thuộc:** UNI-006. **Nguồn:** AI-012.

- Phạm vi: privacy/consent; preference service/repository/routes.
- Thực hiện: Reply style, locale, tên/xưng hô, verbosity, format, custom instructions; chat override; tách history, personalization và feedback consent.
- Điều kiện đạt: Readback/reload đúng; failure không báo saved; personal instructions không vượt policy.
- Truy vết: REQ-03, REQ-04, REQ-22, REQ-26; kiểm chứng AT-09, AT-44.

### UNI-010 — Grant và kiểm tra quyền tại mọi điểm dùng

**Phase:** U2. **Phụ thuộc:** UNI-004, UNI-006, UNI-009. **Nguồn:** AI-013.

- Phạm vi: authorization; source readers; tool executor; run resume/confirmation.
- Thực hiện: Scope theo actor/queue/assignment/source/resource; một lần/phiên/thời hạn phù hợp; revoke, atomically consume và retry semantics.
- Điều kiện đạt: Read không cấp write; pending/resume/direct API/cache đều revalidate; token không vào model.
- Truy vết: REQ-04, REQ-08, REQ-09, REQ-12, REQ-19; kiểm chứng AT-07, AT-08, AT-18, AT-27, AT-34.

### UNI-011 — Runtime, adapter và context bridge chung

**Phase:** U2. **Phụ thuộc:** UNI-008, UNI-010. **Nguồn:** AI-005, AI-006.

- Phạm vi: assistant-context/adapter; StudentRuntime; ChatPage; staff assistant integration.
- Thực hiện: Cùng state/history/task cho page/panel/form/field; mode rõ; context DTO allowlist, server resolve IDs; không đọc toàn DOM.
- Điều kiện đạt: Đổi route/account không lẫn; API lỗi không trả demo giả; context đúng ở từng field.
- Truy vết: REQ-01, REQ-06, REQ-09, REQ-13, REQ-25; kiểm chứng AT-07, AT-11, AT-27.

### UNI-012 — API lịch sử và metadata hội thoại

**Phase:** U2. **Phụ thuộc:** UNI-006, UNI-010. **Nguồn:** AI-007.

- Phạm vi: conversation application/presentation/repositories; stream result.
- Thực hiện: List owned chats, cursor messages, rename/pin/archive/version; client IDs, commit acknowledgements, final metadata và retention states.
- Điều kiện đạt: Phân trang/retry không thiếu/trùng; interrupted khác completed; lỗi không giả empty success.
- Truy vết: REQ-01, REQ-12, REQ-26; kiểm chứng AT-03, AT-04, AT-05, AT-07.

### UNI-013 — Giao diện lịch sử và tiếp tục

**Phase:** U2. **Phụ thuộc:** UNI-011, UNI-012. **Nguồn:** AI-008.

- Phạm vi: AssistantWorkspace/Conversation; ChatPage; history client; staff surface.
- Thực hiện: Search tiêu đề, new/rename/pin/archive; sidebar/mobile drawer; restore từng phần an toàn; saved/pending/error states.
- Điều kiện đạt: Tìm/open lại được qua UI và thiết bị cùng tài khoản; citations/status giữ đúng; không xóa chat khi new.
- Truy vết: REQ-01, REQ-02, REQ-13; kiểm chứng AT-03, AT-04, AT-05, AT-10.

### UNI-014 — Renderer và nội dung trực quan

**Phase:** U2. **Phụ thuộc:** UNI-004, UNI-011. **Nguồn:** AI-010, AI-011.

- Phạm vi: ChatPanel/AssistantConversation; staff renderer; generation output/policy.
- Thực hiện: Markdown/GFM và safe components chung; short/steps/table/status/proposal; schema CTA; streaming, keyboard/mobile/dark.
- Điều kiện đạt: Câu ngắn vẫn gọn; tin cũ đọc được; unsafe markup không chạy; action không suy từ prose.
- Truy vết: REQ-02, REQ-06, REQ-08, REQ-25; kiểm chứng AT-10, AT-23.

### UNI-015 — Settings và trung tâm quyền cho từng vai trò

**Phase:** U2. **Phụ thuộc:** UNI-009, UNI-010, UNI-011, UNI-014. **Nguồn:** AI-014.

- Phạm vi: assistant settings UI; PrivacyCenter; capability client.
- Thực hiện: Reply/memory/tools/history; scope/expiry/last-used/revoke/locked reasons; staff layout và templates hợp lệ; xem trước lựa chọn.
- Điều kiện đạt: Settings ảnh hưởng đúng pipeline; quyền thực tế rõ; capability chưa có không báo dùng được.
- Truy vết: REQ-03, REQ-04, REQ-22, REQ-25, REQ-26; kiểm chứng AT-08, AT-09, AT-44.

### UNI-016 — Trung tâm điều phối multi-agent

**Phase:** U3. **Phụ thuộc:** UNI-004, UNI-005, UNI-008, UNI-010. **Nguồn:** CHAT-MULTI-AGENT-CENTER.

- Phạm vi: multi_agent/orchestrator/contracts; single_agent controller; agent runs.
- Thực hiện: Phân task DAG có role/scope/resource/version/budget; select specialist theo nhu cầu; simple query đi đường ngắn; preserve goal coverage.
- Điều kiện đạt: DAG hợp lệ; không mất mục đích; có clarification/partial/abstain; không thêm agent không cần.
- Truy vết: REQ-05, REQ-08, REQ-09, REQ-13; kiểm chứng AT-12, AT-24, AT-25, AT-26.

### UNI-017 — Specialist và công cụ có hợp đồng

**Phase:** U3. **Phụ thuộc:** UNI-016. **Nguồn:** CHAT-MULTI-AGENT-CENTER.

- Phạm vi: agent/tools registry/executor; multi_agent service_adapter; role adapters.
- Thực hiện: Tận dụng research/verifier; thêm chức năng hiểu intent/tài liệu/draft dưới DTO typed và tool scope server; không expose confirm/approve cho model.
- Điều kiện đạt: Role không tự tạo tools/quyền; bad output/unauthorized tool bị chặn; internal notes không qua student agent.
- Truy vết: REQ-04, REQ-08, REQ-09, REQ-11; kiểm chứng AT-07, AT-23, AT-24, AT-27.

### UNI-018 — Kiểm chứng evidence, claims và kết quả đề xuất

**Phase:** U3. **Phụ thuộc:** UNI-005, UNI-017. **Nguồn:** AI-011, ST-03.

- Phạm vi: evidence_gate/citations/semantic_support; multi_agent verifier; output models.
- Thực hiện: Read lại source theo scope/version; verify material facts/criteria; detect conflicts/missing; bind source/rule/template vào proposal.
- Điều kiện đạt: Model agreement không thay source checks; không hợp nhất mâu thuẫn thành fact; sources mở được.
- Truy vết: REQ-08, REQ-09, REQ-10, REQ-11, REQ-15; kiểm chứng AT-21, AT-22, AT-23, AT-25, AT-30.

### UNI-019 — Task/run bền vững và tiếp tục công việc

**Phase:** U3. **Phụ thuộc:** UNI-006, UNI-010, UNI-016, UNI-018. **Nguồn:** AI-019.

- Phạm vi: agent_runs; run/task repositories; application workflow; task UI.
- Thực hiện: Bind conversation/goal/draft/case/version, blockers/next action; checkpoint typed; CAS/leases/restart/resume không replay action.
- Điều kiện đạt: State sống qua restart; revalidate scope; completed theo receipt/state; checkpoint không chứa confirmation secrets.
- Truy vết: REQ-09, REQ-12, REQ-13; kiểm chứng AT-08, AT-19, AT-20, AT-28.

### UNI-020 — Ngân sách, trace và lỗi phối hợp

**Phase:** U3. **Phụ thuộc:** UNI-016, UNI-017, UNI-019. **Nguồn:** AI-027.

- Phạm vi: agent budget/gateway/telemetry; run events; worker limits.
- Thực hiện: Bound model/tool/context/retry/time/cost chung; metadata trace agent/task/evidence; dedup work/cache by scope; cancellation/partial results.
- Điều kiện đạt: Không loop vô hạn; failure giữ work và giới hạn; user thấy trạng thái hữu ích, không raw prompts/chain-of-thought.
- Truy vết: REQ-08, REQ-09, REQ-24, REQ-26; kiểm chứng AT-26, AT-27, AT-28, AT-48.

### UNI-021 — Hiểu mục đích sinh viên và làm rõ

**Phase:** U4. **Phụ thuộc:** UNI-005, UNI-011, UNI-018. **Nguồn:** AI-015.

- Phạm vi: conversation understanding/followup; intent specialist; document_request assistant.
- Thực hiện: Outcome/purpose/resource/constraints/facts với provenance; hỏi chỉ missing đổi quyết định; goal change không ghi đè nháp.
- Điều kiện đạt: Đúng workflow với ca rõ; ca mơ hồ không tự chọn; không hỏi lại fact hợp lệ đã được phép.
- Truy vết: REQ-05, REQ-07, REQ-08; kiểm chứng AT-12, AT-13, AT-14.

### UNI-022 — Tự chuẩn bị bản nháp thủ tục

**Phase:** U4. **Phụ thuộc:** UNI-019, UNI-021. **Nguồn:** AI-016.

- Phạm vi: certificate/service application/gateways; form stores; draft specialist.
- Thực hiện: Tạo/mở đúng draft; điền sẵn dữ liệu có căn cứ; hướng dẫn phần thiếu; đề xuất diff cho nháp đã sửa; giữ resource/version.
- Điều kiện đạt: User không nhập lại field có nguồn; manual edits được giữ; nhiều draft không chọn bừa.
- Truy vết: REQ-05, REQ-07, REQ-08, REQ-12, REQ-13; kiểm chứng AT-13, AT-14, AT-15, AT-16, AT-20.

### UNI-023 — Trợ giúp trường, đính kèm và lỗi

**Phase:** U4. **Phụ thuộc:** UNI-022. **Nguồn:** AI-017.

- Phạm vi: VinUniForm; CertificateWorkspace/ServiceWorkspace; attachments/validation.
- Thực hiện: Field-level help, missing-group, safe formatting, format/size checks; OCR candidate nếu có runtime phù hợp; source-grounded errors.
- Điều kiện đạt: Sửa đúng chỗ; OCR không xác thực giấy tờ; required/domain validation ở server; không mất nháp.
- Truy vết: REQ-06, REQ-07, REQ-08; kiểm chứng AT-15, AT-16, AT-17.

### UNI-024 — Preview, xác nhận và kết quả sinh viên

**Phase:** U4. **Phụ thuộc:** UNI-010, UNI-018, UNI-022, UNI-023. **Nguồn:** AI-018.

- Phạm vi: confirmation/idempotency; certificate/service preview/confirm; student UI.
- Thực hiện: Bind payload/target/version/expiry; pre-execution revalidate; stable retry key và readback khi timeout; no false success.
- Điều kiện đạt: Không submit trước confirm; không duplicate sau crash; trạng thái dựa receipt, không prose.
- Truy vết: REQ-04, REQ-07, REQ-08, REQ-12; kiểm chứng AT-08, AT-18, AT-19, AT-21.

### UNI-025 — Phủ thao tác sinh viên và mobile

**Phase:** U4. **Phụ thuộc:** UNI-002, UNI-013, UNI-014, UNI-015, UNI-024. **Nguồn:** AI-020.

- Phạm vi: registry; navigation/services/requests/schedule/rooms/privacy surfaces.
- Thực hiện: Nối context/capability thật vào từng action trong inventory; ngoài scope có next step rõ; cùng purpose qua route.
- Điều kiện đạt: Mọi action trong scope pilot được test; toàn inventory có mức support trung thực; UI accessible.
- Truy vết: REQ-02, REQ-06, REQ-07, REQ-13; kiểm chứng AT-02, AT-10, AT-11, AT-20.

### UNI-026 — Hiển thị độ tin cậy cán bộ bằng dữ liệu thật

**Phase:** U5. **Phụ thuộc:** UNI-001, UNI-014, UNI-018. **Nguồn:** ST-01.

- Phạm vi: StaffTicketQueue; staff response schemas; staff capability registry.
- Thực hiện: Tách demo, loại claims/confidence ghi cứng khỏi luồng thật bằng typed evidence state; chưa có check thì chưa xác minh.
- Điều kiện đạt: Không dùng số 99.8%/OCR stamp/SLA constants như facts; giữ dữ liệu và mandatory controls.
- Truy vết: REQ-08, REQ-14, REQ-15, REQ-25; kiểm chứng AT-22, AT-29, AT-31.

### UNI-027 — Bộ hồ sơ làm việc và provenance

**Phase:** U5. **Phụ thuộc:** UNI-018, UNI-019, UNI-026. **Nguồn:** ST-03.

- Phạm vi: staff application; StaffTicketWorkspace/Reviews; evidence repository.
- Thực hiện: Summary purpose/facts/timeline/documents/criteria/source/next action; từng nhận định mở source locator/version; internal/public projections.
- Điều kiện đạt: Cán bộ tìm căn cứ ngay; summary thiếu/conflict không suy đoán; đúng case/student và scope.
- Truy vết: REQ-08, REQ-11, REQ-14, REQ-25; kiểm chứng AT-07, AT-22, AT-30, AT-36.

### UNI-028 — Checklist và readiness theo workflow

**Phase:** U5. **Phụ thuộc:** UNI-005, UNI-027. **Nguồn:** ST-05.

- Phạm vi: staff-policy; domain criteria/workflow; findings UI/service.
- Thực hiện: Rule checks và AI proposals tách officer review; ready/needs verification/missing/waiting/blocked có reason; keep mandatory checks.
- Điều kiện đạt: Không tự tick/bypass review; failed source không tự từ chối; source/criteria version đúng.
- Truy vết: REQ-08, REQ-10, REQ-14, REQ-15; kiểm chứng AT-21, AT-30, AT-31.

### UNI-029 — Chuẩn bị trước và kiểm tra phần thay đổi

**Phase:** U5. **Phụ thuộc:** UNI-020, UNI-027, UNI-028. **Nguồn:** ST-04.

- Phạm vi: worker/outbox; findings dependency/cache; staff UI diff.
- Thực hiện: Dependencies data→criterion→finding→draft; cache by hashes/versions; invalidate tác động; compare supplement before/after.
- Điều kiện đạt: Kết quả stale bị chặn; recheck đủ phần ảnh hưởng; giữ checks khác chỉ khi hợp lệ; bounded costs.
- Truy vết: REQ-08, REQ-11, REQ-14, REQ-16; kiểm chứng AT-21, AT-22, AT-32, AT-48.

### UNI-030 — Nháp cán bộ, assignment và cạnh tranh bền vững

**Phase:** U5. **Phụ thuộc:** UNI-006, UNI-010, UNI-019. **Nguồn:** ST-06.

- Phạm vi: useStaffDraft; staff claim/transfer/respond; repositories.
- Thực hiện: Server autosave officer/case/version, saved/pending/error, CAS across tabs; durable claims kiểm soát nhiều process; preserve unsaved safeguards.
- Điều kiện đạt: Reload không mất saved drafts; không overwrite; assignment/revoke invalidates pending action.
- Truy vết: REQ-08, REQ-12, REQ-19; kiểm chứng AT-08, AT-16, AT-28, AT-33, AT-34.

### UNI-031 — Dự thảo kết quả và kiểm tra trước cán bộ thực hiện

**Phase:** U5. **Phụ thuộc:** UNI-018, UNI-028, UNI-030. **Nguồn:** ST-08, AI-021.

- Phạm vi: staff respond/certificate/service; templates; previews/executor.
- Thực hiện: Structured outcome/facts/reasons; bind recipient/case/rule/template/version; human required reviews; transaction/audit/receipt consistency.
- Điều kiện đạt: Thông tin trọng yếu không hallucinate; internal note không gửi nhầm; đúng thẩm quyền; retry không action trùng.
- Truy vết: REQ-08, REQ-10, REQ-12, REQ-18, REQ-19; kiểm chứng AT-18, AT-19, AT-21, AT-31, AT-35, AT-36.

### UNI-032 — Trợ lý ở mọi thao tác cán bộ và quản trị

**Phase:** U5. **Phụ thuộc:** UNI-002, UNI-011, UNI-015, UNI-027, UNI-031. **Nguồn:** AI-021, ST-05.

- Phạm vi: staff queue/detail/checklist/editor/error/admin; registry/context bridge.
- Thực hiện: Interpret staff intent tied to selected cases/actions; same work context; approved templates/settings; assist every inventory action or explicit limit.
- Điều kiện đạt: Không copy hồ sơ sang chat; ambiguous multi-case clarifies; role boundaries và mandatory decisions giữ.
- Truy vết: REQ-03, REQ-05, REQ-06, REQ-14, REQ-18, REQ-25; kiểm chứng AT-02, AT-07, AT-11, AT-12, AT-31, AT-35.

### UNI-033 — Vòng bổ sung có cấu trúc nối hai bên

**Phase:** U6. **Phụ thuộc:** UNI-023, UNI-024, UNI-029, UNI-031. **Nguồn:** ST-07.

- Phạm vi: supplement field/item APIs; student assistant/forms; staff draft/recheck.
- Thực hiện: Item IDs/criteria/reasons/accepted format; group known missing; staff confirm public request; student checklist; map response and delta checks.
- Điều kiện đạt: Không hỏi thừa/nhỏ giọt known missing; private note không chuyển; mục đã giải quyết được giữ.
- Truy vết: REQ-05, REQ-07, REQ-15, REQ-16, REQ-17; kiểm chứng AT-13, AT-17, AT-32, AT-36, AT-37.

### UNI-034 — Bàn giao và theo dõi work liên đơn vị

**Phase:** U6. **Phụ thuộc:** UNI-019, UNI-031, UNI-033. **Nguồn:** AI-025, ST-10.

- Phạm vi: HandoverPanel/staff transfer; queues/task views; handover contract.
- Thực hiện: Selected summary done/open/evidence/next step và preview; reauthorize target/assignment; public/internal scope; no promise unverified SLA.
- Điều kiện đạt: Người nhận có đủ context được phép; không toàn bộ memory/history; transfer receipt/state đúng.
- Truy vết: REQ-04, REQ-11, REQ-13, REQ-17, REQ-21; kiểm chứng AT-08, AT-19, AT-34, AT-36, AT-38.

### UNI-035 — Trạng thái hồ sơ dùng chung và hiển thị theo quyền

**Phase:** U6. **Phụ thuộc:** UNI-025, UNI-032, UNI-033, UNI-034. **Nguồn:** AI-006, AI-021.

- Phạm vi: case/task/event projections; student/staff clients; source scope.
- Thực hiện: Một business state/versions; role-specific views; source changes/revokes refresh affected projections; private memory không hợp nhất giữa actors.
- Điều kiện đạt: Hai bên thấy status nhất quán phần được phép; cross-role context/cache không rò hoặc quyết định từ snapshot cũ.
- Truy vết: REQ-04, REQ-09, REQ-12, REQ-13, REQ-17, REQ-26; kiểm chứng AT-07, AT-11, AT-20, AT-27, AT-36, AT-37, AT-38.

### UNI-036 — Chuẩn bị và thực hiện gộp có kiểm soát

**Phase:** U7. **Phụ thuộc:** UNI-010, UNI-020, UNI-029, UNI-031, UNI-035. **Nguồn:** ST-09.

- Phạm vi: batch proposal/service; staff selection/preflight; executor/receipts.
- Thực hiện: Exact target list/versions/individual payloads; prepare/check/confirm/execute if allowed; per-item authorization, partial outcomes và retry receipts.
- Điều kiện đạt: Không target drift/copy outcomes; stale item không chạy; đã commit không gửi lại; capability chưa có chỉ prepare.
- Truy vết: REQ-04, REQ-08, REQ-12, REQ-18, REQ-20; kiểm chứng AT-08, AT-18, AT-19, AT-34, AT-39.

### UNI-037 — Hàng đợi và ưu tiên có căn cứ

**Phase:** U7. **Phụ thuộc:** UNI-028, UNI-032, UNI-035. **Nguồn:** ST-05, ST-10.

- Phạm vi: StaffQueue/staff-policy; routing/queue domain; task views.
- Thực hiện: Ready/waiting/blocked groups, deadlines sourced, transparent priority policy; suggest routing without auto unauthorized assignment; preserve queue position.
- Điều kiện đạt: Không tự tạo SLA hoặc ưu tiên theo model score; duplicate candidates không auto merge/delete/reject.
- Truy vết: REQ-14, REQ-15, REQ-19, REQ-21, REQ-25; kiểm chứng AT-21, AT-31, AT-34, AT-40.

### UNI-038 — Dashboard điểm nghẽn và cải tiến quy trình

**Phase:** U7. **Phụ thuộc:** UNI-020, UNI-033, UNI-034, UNI-037. **Nguồn:** ST-10.

- Phạm vi: telemetry/event aggregations; staff dashboard.
- Thực hiện: Separate active/student wait/unit wait/system time; supplements/transfers/reopen/age/blockers; aggregation in scope và tối thiểu data.
- Điều kiện đạt: Không đánh giá throughput bỏ complexity; bottleneck có evidence; không tự đổi policy khi backlog cao.
- Truy vết: REQ-16, REQ-17, REQ-21, REQ-24; kiểm chứng AT-40, AT-41, AT-48.

### UNI-039 — Memory cá nhân của từng actor

**Phase:** U8. **Phụ thuộc:** UNI-008, UNI-009, UNI-010, UNI-019. **Nguồn:** AI-022.

- Phạm vi: memory repository/service/retrieval; bounded context; settings.
- Thực hiện: Preferences/goals/confirmed facts có source/time/validity/scope; staff memory không tái dùng hồ sơ sinh viên khác; relevant-only context.
- Điều kiện đạt: Opt-in, isolation, update/contradiction/abstain đúng; source học vụ hiện hành không bị thay bằng memory.
- Truy vết: REQ-03, REQ-08, REQ-22, REQ-26; kiểm chứng AT-07, AT-22, AT-27, AT-42.

### UNI-040 — Sửa, quên, chat tạm thời và riêng tư

**Phase:** U8. **Phụ thuộc:** UNI-007, UNI-012, UNI-015, UNI-039. **Nguồn:** AI-023.

- Phạm vi: memory UI/API; derived index/summary invalidation; conversation modes.
- Thực hiện: Forget suppression tránh tái tạo từ history; CAS sửa; temporary không personal memory; retention/export/erasure disclosure đúng.
- Điều kiện đạt: Memory off không xóa history; forgotten item không về context; choices có hiệu lực server và không lẫn actors.
- Truy vết: REQ-01, REQ-03, REQ-22, REQ-26; kiểm chứng AT-06, AT-09, AT-43, AT-44.

### UNI-041 — Subscriptions và sự kiện bền vững

**Phase:** U9. **Phụ thuộc:** UNI-010, UNI-019, UNI-020, UNI-033, UNI-035. **Nguồn:** AI-024.

- Phạm vi: business events/outbox/worker; subscription repository/service.
- Thực hiện: Selected resource/trigger/channel/expiry, new feedback/supplement/deadline sourced; dedup/retry/no-change/quiet hours; reauthorize delivery.
- Điều kiện đạt: Revoke/unsubscribe chặn delivery sau; restart không nhân; event không tự submit/approve.
- Truy vết: REQ-04, REQ-13, REQ-17, REQ-23; kiểm chứng AT-08, AT-21, AT-45, AT-46.

### UNI-042 — Thông báo và next action hai bên

**Phase:** U9. **Phụ thuộc:** UNI-014, UNI-015, UNI-034, UNI-041. **Nguồn:** AI-025.

- Phạm vi: notification/task UI; channel adapters allowed; staff/student assistant.
- Thực hiện: Reason/source/updated_at/next action/stop tracking; safe preview, channel privacy, open exact resource; handover links.
- Điều kiện đạt: Không spam/no-change; không lộ private data trong kênh chưa cấp; nguồn thiếu không hứa thời hạn.
- Truy vết: REQ-02, REQ-13, REQ-21, REQ-23, REQ-26; kiểm chứng AT-10, AT-36, AT-38, AT-45, AT-46.

### UNI-043 — Contract, quyền, lỗi và đối kháng toàn hệ

**Phase:** U10. **Phụ thuộc:** UNI-024, UNI-035, UNI-036, UNI-040, UNI-042. **Nguồn:** AI-026, ST-11.

- Phạm vi: unit/API/integration/security suites; synthetic fixtures.
- Thực hiện: Schema/state/readiness/grants/source-version, bad agent output/injection, stale approval, wrong recipient, concurrency/crash/batch faults; test từng task từ sớm.
- Điều kiện đạt: Không overall score che lỗi quyền; gold có nguồn; report command/exit/build; không đổi expected để pass.
- Truy vết: REQ-04, REQ-08, REQ-09, REQ-12, REQ-24, REQ-26; kiểm chứng AT-07, AT-08, AT-18, AT-19, AT-23, AT-24, AT-25, AT-26, AT-27, AT-28, AT-31, AT-34, AT-39, AT-47, AT-50.

### UNI-044 — E2E xuyên sinh viên và cán bộ

**Phase:** U10. **Phụ thuộc:** UNI-025, UNI-032, UNI-033, UNI-035, UNI-043. **Nguồn:** AI-028.

- Phạm vi: browser candidate tests/mobile/accessibility; pilot scripts.
- Thực hiện: Goal→draft→confirm→staff review→supplement→student correction→staff result→receipt; history/settings/context across routes.
- Điều kiện đạt: Đúng build/API, real UI evidence, roles/data/receipt đúng; synthetic/browser pass chưa thay user pilot.
- Truy vết: REQ-01, REQ-02, REQ-05, REQ-06, REQ-07, REQ-08, REQ-13, REQ-17, REQ-25; kiểm chứng AT-01, AT-02, AT-03, AT-10, AT-11, AT-12, AT-14, AT-15, AT-19, AT-20, AT-31, AT-35, AT-37, AT-49.

### UNI-045 — Shadow evaluation và ích lợi của multi-agent

**Phase:** U10. **Phụ thuộc:** UNI-003, UNI-018, UNI-020, UNI-024, UNI-031, UNI-035. **Nguồn:** AI-026, ST-11.

- Phạm vi: eval datasets; controller/agent run reports; staff review scripts.
- Thực hiện: Prepare-only trên fixture/nguồn được phép; baseline simple/single vs selected multi; measure correct intent/facts/actions, latency/cost; expert review disagreements.
- Điều kiện đạt: Multi-agent được giữ ở nơi có evidence hữu ích; không majority vote thay truth; staff blind subsets giảm lệ thuộc gợi ý.
- Truy vết: REQ-05, REQ-08, REQ-09, REQ-11, REQ-24; kiểm chứng AT-12, AT-22, AT-24, AT-25, AT-26, AT-30, AT-35, AT-47, AT-49.

### UNI-046 — Hiệu năng, chi phí và tải

**Phase:** U10. **Phụ thuộc:** UNI-020, UNI-029, UNI-036, UNI-038, UNI-039, UNI-041, UNI-043. **Nguồn:** AI-027.

- Phạm vi: instrumentation/budgets/context/DB/worker; load fixtures.
- Thực hiện: Measure p95 restore/prepare/complete, throughput, valid outcomes/cost, queue bounds/caching; fault behavior; no secrets/raw private logs.
- Điều kiện đạt: Load không bypass checks; clear partial/failure; limits per run/user/service có hiệu lực; report baseline.
- Truy vết: REQ-08, REQ-09, REQ-16, REQ-20, REQ-24, REQ-26; kiểm chứng AT-26, AT-27, AT-28, AT-32, AT-39, AT-41, AT-48.

### UNI-047 — Pilot người dùng hai phía

**Phase:** U10. **Phụ thuộc:** UNI-044, UNI-045, UNI-046. **Nguồn:** AI-028, ST-12.

- Phạm vi: student/staff task scripts; allowed participants/environment.
- Thực hiện: Phiên thử độc lập và end-to-end; measure effort/corrections/completion/first-pass/supplement cycles; same complexity/data/conditions.
- Điều kiện đạt: Người dùng thực xác minh usefulness; chưa có participants thì not_verified; không gọi synthetic pass là usability.
- Truy vết: REQ-01, REQ-02, REQ-03, REQ-05, REQ-06, REQ-07, REQ-08, REQ-14, REQ-15, REQ-16, REQ-17, REQ-18, REQ-24, REQ-25; kiểm chứng AT-10, AT-12, AT-30, AT-31, AT-35, AT-37, AT-41, AT-49.

### UNI-048 — Diễn tập chuyển luồng và phục hồi

**Phase:** U11. **Phụ thuộc:** UNI-007, UNI-043, UNI-047. **Nguồn:** AI-029, ST-12.

- Phạm vi: new fixture candidates; migration/import/wiring/feature config.
- Thực hiện: Compatibility data/history/drafts/receipts, turn features off without losing work, source/runtime rehearsal; prepare exact deployment checklist.
- Điều kiện đạt: Old snapshots/data/protections giữ; failed feature có manual/readback path; production chưa thực hiện.
- Truy vết: REQ-01, REQ-08, REQ-12, REQ-26; kiểm chứng AT-03, AT-06, AT-19, AT-28, AT-50.

### UNI-049 — Runbook và hướng dẫn sử dụng

**Phase:** U11. **Phụ thuộc:** UNI-048. **Nguồn:** AI-030.

- Phạm vi: docs student/staff/settings/runtime/verification.
- Thực hiện: Record proved launch/check commands, capabilities/limits/retention/permissions, support/recovery and evidence refs; tutorial theo từng vai trò.
- Điều kiện đạt: Tài liệu khớp bản kiểm chứng; no fake claims; user biết cách tiếp tục, sửa/quên/tắt và phục hồi.
- Truy vết: REQ-01, REQ-03, REQ-04, REQ-06, REQ-13, REQ-22, REQ-23, REQ-24, REQ-25, REQ-26; kiểm chứng AT-01, AT-02, AT-09, AT-44, AT-49, AT-50.

### UNI-050 — Đối soát phạm vi và bàn giao kế hoạch

**Phase:** U11. **Phụ thuộc:** UNI-049. **Nguồn:** AI-030.

- Phạm vi: unified master/backlog; requirement/acceptance coverage.
- Thực hiện: Verify requirements, tasks, source mapping, evidence and remaining gaps; status done chỉ theo phạm vi/evidence; next task rõ.
- Điều kiện đạt: Không claim production nếu chưa deploy; old tasks không chạy lại trùng; mọi yêu cầu có status và giới hạn trung thực.
- Truy vết: REQ-01, REQ-02, REQ-03, REQ-04, REQ-05, REQ-06, REQ-07, REQ-08, REQ-09, REQ-10, REQ-11, REQ-12, REQ-13, REQ-14, REQ-15, REQ-16, REQ-17, REQ-18, REQ-19, REQ-20, REQ-21, REQ-22, REQ-23, REQ-24, REQ-25, REQ-26; kiểm chứng AT-01, AT-02, AT-03, AT-04, AT-05, AT-06, AT-07, AT-08, AT-09, AT-10, AT-11, AT-12, AT-13, AT-14, AT-15, AT-16, AT-17, AT-18, AT-19, AT-20, AT-21, AT-22, AT-23, AT-24, AT-25, AT-26, AT-27, AT-28, AT-29, AT-30, AT-31, AT-32, AT-33, AT-34, AT-35, AT-36, AT-37, AT-38, AT-39, AT-40, AT-41, AT-42, AT-43, AT-44, AT-45, AT-46, AT-47, AT-48, AT-49, AT-50.

## 10. Bộ nghiệm thu hợp nhất

AT là nhóm scenario, mỗi nhóm phải phân rã thành test cases có input, nguồn/expected results, actor/scope, phiên bản, lệnh/runtime và evidence khi thực hiện. Nhóm có nhiều bề mặt phải test các đường thực thi thực tế, không chỉ happy path. Mỗi task làm tests liên quan trước verified; việc tồn tại AT không chứng minh test đã chạy.

| ID | Nhóm kiểm chứng | Kết quả cần đạt |
| --- | --- | --- |
| AT-01 | Đúng runtime/build/API/mode/identity/storage | Bằng chứng UI gắn đúng candidate; pass ở snapshot khác không tính đã sửa bản dùng. |
| AT-02 | Độ phủ thao tác hai vai trò | Inventory có handler và mức hỗ trợ được thử; unsupported được ghi gap, không tính là đã hỗ trợ. |
| AT-03 | History qua reload/relogin/restart/thiết bị | Lượt được ack commit còn đúng actor/order/retention; chưa commit có trạng thái chính xác. |
| AT-04 | Discovery và metadata phân trang | Search/open/rename/pin/archive/version; nhiều trang không mất/trùng. |
| AT-05 | Pending/stream/final/citations | Retry/timeout/interrupt đúng trạng thái; final source map bất biến theo message. |
| AT-06 | Legacy/import/demo/unknown ownership | Giữ dữ liệu gốc, preview/receipt/dedup; không gắn owner tùy ý hoặc demo vào thật. |
| AT-07 | Isolation actor/tenant/role/queue | Direct API/source/cache/resume/UI không đọc/chỉnh trái quyền hoặc lộ internal notes. |
| AT-08 | Grant expiry/revoke/race | Read không thành write; one-time consumption hợp lệ; pending action revalidates. |
| AT-09 | Settings persistence và concurrent edits | Saved/readback/chat override/CAS đúng; offline failure không báo đã lưu. |
| AT-10 | Renderer/accessibility/streaming | Short/list/table/cards/copy/source/mobile/dark/keyboard; không tràn toàn trang. |
| AT-11 | Context xuyên route/field/panel và đổi tài khoản | Goal/resource/error context đúng; không mất hoặc rò dữ liệu hai bên. |
| AT-12 | Intent rõ/mơ hồ/thiếu thông tin | Expected workflow/clarification đúng; không chọn thủ tục hay target quan trọng bằng đoán. |
| AT-13 | Đổi mục đích/ràng buộc giữa chừng | Reinterpret và diff cần thiết; giữ nháp/manual work; không action theo goal cũ. |
| AT-14 | Không hỏi/nhập lại fact hợp lệ | Dữ liệu đã có nguồn và được cấp được dùng đúng; missing thật mới hỏi. |
| AT-15 | Auto draft và provenance trường | Field types/domain checks đúng, có nguồn; inference và OCR candidate không bị giả fact. |
| AT-16 | Manual edits/stale/multiple drafts | Không overwrite hoặc chọn bừa; version conflict hiển thị và giữ work. |
| AT-17 | Tài liệu/OCR/required fields | File checks và schema/server validation; không xác thực con dấu/chữ ký từ detection. |
| AT-18 | Exact preview/confirmation | Đổi payload/recipient/target/version/expiry không dùng approval cũ; chưa confirm không chạy. |
| AT-19 | Crash/timeout quanh business commit | Read receipt và stable retries; không submit/send/issue/book hai lần. |
| AT-20 | Task continuity và receipt-based completion | Nhiều phiên/restart đúng resource/step; checkpoint không tự thực thi hay cấp quyền. |
| AT-21 | Rule/source/template effective versions | Chọn phiên bản áp dụng theo mốc cấu hình; source/rule đổi không làm kết luận stale được dùng. |
| AT-22 | Evidence và factual/semantic checks | Claim/criterion/output truy nguồn; missing/conflict không thành fact; UI không confidence giả. |
| AT-23 | Untrusted documents/tools/memory/output | Injection không tạo quyền, tool, executable UI hoặc thay workflow; unsafe links bị xử lý. |
| AT-24 | DAG/role/tool/output contracts | Cycle/unknown role/tool/bad output rejected; authority bound server; coverage không mất. |
| AT-25 | Mâu thuẫn giữa agents hoặc nguồn | Original evidence được đọc lại; không majority vote/fabricated synthesis; unresolved được nêu rõ. |
| AT-26 | Agent partial failure/cancel/budgets | Bound retries/time/cost/context; giữ work; partial/abstain đúng, không fake success. |
| AT-27 | Scope/freshness của cache và handoff | Cached evidence reauthorized; subagent chỉ nhận minimal context phù hợp; revoke làm invalidation đúng. |
| AT-28 | Durable runs và nhiều process | Concurrent resume/lease/version và restart không duplicate transition hoặc mất committed result. |
| AT-29 | Staff integrity của demo/checks/confidence | Constants 99.8%, stamp/SLA claims không hiển thị như evidence thật; unknown có reason. |
| AT-30 | Staff case package và source navigation | Đúng sinh viên/case/facts/timeline; mở chính xác locator/version, không bỏ blocker. |
| AT-31 | Readiness và mandatory reviews | Ready không bỏ required officer checks; model confidence/tick count không thay criterion truth. |
| AT-32 | Incremental recheck dependencies | Document/rule/fact/template đổi invalidates đủ findings/output; unrelated còn hợp lệ mới giữ. |
| AT-33 | Staff autosave/reload/concurrent tabs | Committed draft sống qua restart; saved/pending/error đúng; manual text không ghi đè. |
| AT-34 | Claim/assignment/transfer/concurrent officers | Một action đúng owner/queue; reassignment/revoke chặn old proposal; không mất drafts. |
| AT-35 | Official draft và structured outcome | Đúng mẫu/fields/facts/reasons/version; decision do cán bộ/workflow, không prose model. |
| AT-36 | Internal/public/recipient boundaries | Notes/memory/confidential attachments không lọt phản hồi hay notification; recipient bind đúng. |
| AT-37 | Supplement loop hai bên | Group known missing, typed item IDs, public request confirmed; bổ sung resolve đúng item, không hỏi lại. |
| AT-38 | Handover liên đơn vị | Đủ done/open/evidence/next step trong scope; transfer/public preview/receipt đúng, không share toàn chat. |
| AT-39 | Batch preflight/partial/retry | Exact list, per-item authorize/version/receipt; stale blocked, no target drift/copy outcome/duplicate. |
| AT-40 | Priority và routing minh bạch | Lý do theo policy/deadline/source; duplicate candidates không auto merge/delete/reject. |
| AT-41 | Bottleneck và effort metrics | Tách active/student wait/unit wait/system/complexity; số vòng bổ sung và reopen được đo đúng. |
| AT-42 | Memory temporal/update/contradiction | Opt-in đúng actor, relevance/validity; status học vụ lấy nguồn hiện hành. |
| AT-43 | Forget và derived contexts | Memory quên không tái tạo từ history/index/summary; giữ chat gốc theo lựa chọn riêng. |
| AT-44 | Temporary/history/retention/privacy | Memory off không xóa history; temporary không personal memory; disclosure đúng storage vận hành. |
| AT-45 | Events/quiet hours/revoke/restart | No-change im lặng, dedup, scope trước delivery; stop tracking có hiệu lực. |
| AT-46 | Notifications/channels/next action | Kênh/preview dữ liệu đúng quyền; mở resource đúng; không unverified promise hoặc auto write. |
| AT-47 | Adversarial facts/actions và lỗi hệ thống | Bad IDs/OCR/source/stale approvals/DB/audit/delivery failures không tạo quyết định sai hoặc rò dữ liệu. |
| AT-48 | Performance/cost/load/privacy | p95/throughput/cost measured; context/tool/retry/queue limits; no raw private logs; kiểm tra không bypass dưới tải. |
| AT-49 | Pilot thực hai bên và usefulness | Same tasks/conditions/complexity; người tham gia thật đánh giá completion/corrections/effort; synthetic chưa đủ. |
| AT-50 | Rollout/recovery/data compatibility | Feature off giữ history/evidence/drafts/receipts/manual path/safety; migration không overwrite nguồn. |

## 11. Cách kiểm chứng chất lượng và hiệu quả

### 11.1. Các lớp kiểm tra

- Unit/domain: required fields, schema, state transitions, rule applicability, version/CAS, intent interpretation và source bindings.
- Contract/API: owner/role/queue/assignment, scope/revoke, pagination, idempotency, confirmations, no-store/error conventions và typed agent outputs.
- Integration/fault: database/runtime restart, concurrent claim/resume, source changed, cache invalidation, audit/worker/delivery failure, timeout quanh commit, batch partial outcomes.
- Security/adversarial: wrong target/recipient, scope escalation, instructions trong source/tools/memory, unsafe render, stale approval/checkpoint và private notes leakage.
- Agent evaluations: correct goal coverage/clarify/facts/workflow, source re-read, unresolved conflicts, output validity, latency/cost và run bounds. Không self-judge duy nhất hoặc majority vote thay gold.
- Shadow staff: chỉ chuẩn bị; gold/source/qualified reviewer đối chiếu, một số phiên đánh giá không nhìn gợi ý trước để kiểm tra lệ thuộc. Cán bộ khác AI không tự là lỗi; cần căn cứ.
- Real browser và người dùng: đúng build/API, desktop/mobile/keyboard/dark, phiên sinh viên/cán bộ độc lập và vòng hai bên. Thiếu người tham gia thì user acceptance not_verified.

### 11.2. Dataset, baseline và metrics

UNI-003 đề xuất tối thiểu 60 ca mục đích/sinh viên, 40 ca staff/criteria/delta/supplement và 30 ca quyền/lỗi/agent/batch, có thể tái sử dụng fixtures đúng nguồn hiện có. Mỗi ca có resource versions, expected material facts, workflow/action và khi nào phải hỏi/abstain. Chia rõ ca thường/ngoại lệ/missing source/OCR/multi-actor; không lấy model output làm gold.

Pilot đề xuất ít nhất 8–12 phiên sinh viên, 8–12 phiên cán bộ và 4 phiên round-trip ghép, khi có người/môi trường được phép. Báo sample/cohort/limitations, không suy rộng từ test nhỏ hoặc thay người dùng bằng synthetic tests. Có chỉ số effort, completion và correctness riêng.

Giữ các mục tiêu UX đề xuất trước để chốt theo baseline trước pilot: giảm ít nhất 40% trường nhập tay ở tác vụ có nguồn hợp lệ, giảm ít nhất 30% thời gian thao tác sinh viên, ít nhất 90% phiên pilot hoàn tất tác vụ được hỗ trợ không cần người hướng dẫn. Đây là mục tiêu thiết kế, chưa đạt hoặc được đo. Cán bộ đo active time/tìm nguồn/đọc lại/soạn/supplement rounds/first-pass/reopen; chốt mục tiêu sau baseline thay vì hứa tỷ lệ chưa có căn cứ.

Tách thời gian cán bộ làm khỏi thời gian chờ sinh viên/đơn vị khác/system; so cùng loại việc/độ phức tạp/dữ liệu/điều kiện. Error metrics: wrong intent/fact/recipient, false-ready/missed conflict, material corrections, source-stale use, duplicate execution, unauthorized access và internal/public leak. Speed improvement không được coi là đạt nếu correctness/authority gates không đạt.

Multi-agent so với đường baseline phù hợp (rules/direct typed service/simple controller): đo coverage/fact/action correctness và cost/latency, giữ central orchestration nhưng giảm fan-out nơi không hữu ích. Không đánh đổi quyền/verification để tăng throughput. Load tests vẫn kiểm tra domain/permission/confirmation.

Điều kiện bắt buộc cho capability mở: các ca bảo toàn/identity/grant/mandatory review/exact confirmation/receipt/chống trùng liên quan pass; không còn lỗi nghiêm trọng đã biết chưa xử lý. Chỉ áp dụng cho tập thử/môi trường được chứng minh, không tuyên bố độ đúng tuyệt đối ngoài thực tế. Thay scope/expected results cần lý do và chỉ dẫn người dùng thích hợp; không âm thầm hạ tiêu chí để pass.

### 11.3. Lệnh kiểm tra tham chiếu cho lần triển khai sau

Các package scripts/test paths dưới đây đã có trong mã quan sát, **chưa chạy ở lần lập kế hoạch này**. Đọc tests/runners và side effects trước chạy. Dùng runtime có sẵn, fixtures và output directories mới trong workspace đã preflight; không default temp/cache ngoài scope, không reset/delete dữ liệu hoặc dừng process đang dùng để test. Không tự install/update dependencies vì lệnh lỗi.

~~~powershell
# Workspace root; chọn subset phù hợp thay đổi và kiểm tra test fixture boundaries trước chạy.
pnpm --filter web lint
pnpm --filter web test -- src/features/chat/history.test.ts src/features/chat/sse.test.ts src/features/chat/ChatPanel.test.tsx src/app/chat/page.history.test.tsx src/app/chat/page.resume.test.tsx
python -m pytest tests/unit/conversation/test_sqlite_local_history.py tests/unit/conversation/test_context.py tests/api/test_chat_sse.py
python -m pytest tests/unit/agent/test_multi_agent_admission.py tests/unit/agent/test_multi_agent_integrated.py tests/api/test_multi_agent_api.py
python -m pytest tests/api/test_privacy_notice_consent.py tests/api/test_privacy_authorization.py tests/security/test_action_confirmation.py
python -m pytest tests/api/test_certificate_stage1.py tests/api/test_service_stage6.py tests/api/test_ticket_write.py
~~~

Tạo test mới cho staff autosave/delta/supplement/batch/dual-role contexts khi task làm; không giả file test đã tồn tại. Build/E2E candidate theo launcher đã kiểm tra, giữ .next/build/snapshots đang dùng. Nếu runner tự cleanup hoặc ghi ngoài workspace thì đổi sang fixture/runtime phương án bảo toàn trong scope sau inspection, không bypass protection.

Evidence của task gồm command, exit code, build/environment, cases/expected vs observed, artifact paths và limitations; không raw secrets/private chat. “implemented” chưa đủ “verified”; unit fake pass chưa đủ real-world usability.

## 12. Quyết định, rủi ro và phát hành có kiểm soát

| Điểm cần chốt | Mặc định/giới hạn đề xuất | Task |
| --- | --- | --- |
| Runtime và identity | Verify exact build/API/subject/tenant/role; demo tách thật | UNI-001 |
| Độ phủ UI/capabilities | Inventory tất cả thao tác; unsupported là gap, không fake capability | UNI-002,025,032 |
| History retention | Theo lựa chọn/thông báo và policy; kiểm tra 30 ngày hiện tại, không tự vô thời hạn | UNI-001,004,012 |
| Model/agents/infra | Tận dụng hiện có; specialist logic và đường ngắn có ngân sách; không agent nào tự có quyền ghi | UNI-016–020 |
| Rules/effective version | Một definition, applicable version theo mốc workflow; unknown thì chưa kết luận | UNI-005 |
| Memory | Opt-in theo actor; không memory cá nhân trong temporary; không staff memory lẫn student facts | UNI-039–040 |
| Batch | Prepare trước; execute chỉ workflow cho phép, exact list và per-item revalidation | UNI-036 |
| Notification | Off đến khi chọn trigger/scope/channel; ưu tiên in-app có privacy scope | UNI-041–042 |
| Paid/live/source access | Fakes mặc định, dùng nguồn/live/budgets đã được cấp và xác minh; không quyền mới từ plan | UNI-003,045–047 |
| Pilot người dùng | Participants/environment rõ; chưa có thì report chưa nghiệm thu | UNI-047 |
| Production | Chuẩn bị reviewable candidate và evidence trước bước phát hành được yêu cầu | UNI-048 |

Rủi ro và test trọng tâm: sai build (AT-01), owner mapping (AT-06/07), settings hình thức (AT-09), intent sai (AT-12/13), evidence/confidence giả (AT-22/29), source applicability sai (AT-21), stale cache (AT-27/32), mất nháp/claim race (AT-33/34), bổ sung nhỏ giọt (AT-37), agent tool escalation/injection (AT-23/24), sai target/batch/retry (AT-18/19/39), memory poisoning/forget (AT-42/43), private note leak (AT-36/46), cost loops (AT-26/48).

Rollout: preserved candidate local → prepare-only/shadow → pilot workflow/capability → mở dần theo role/cohort được phép → xem xét production theo direct request sau. Source/input imports và migrations diễn tập trên fixtures mới được xác định, giữ bản gốc. Khi lỗi, ngừng feature tương ứng qua cấu hình phát hành riêng, giữ source/history/drafts/evidence/receipts/readback/manual path; không chỉnh hoặc vô hiệu hóa safety controls, cleanup hoặc reset để phục hồi.

## 13. Hướng dẫn tiếp tục thực hiện sau

1. Đọc bản hợp nhất này và backlog mới, instructions hiện hành và direct request mới nhất.
2. Resolve workspace/exact paths, git status và dirty state; preserve mọi user/agent work. Read file trước targeted patch; kiểm tra canonical destinations/symlinks và diff sau mutation.
3. Bắt đầu UNI-001 nếu chưa có evidence; code/runtime có thể đổi từ ngày lập. Không tự chạy old AI/ST backlog thêm lần nữa.
4. Chọn task planned có dependencies verified và scope cụ thể. Nếu bằng chứng code hiện tại đã đáp ứng, kiểm chứng và tái sử dụng; không viết lại chỉ để theo kiến trúc giấy.
5. Status planned → in_progress → implemented → verified. failed/needs_input có lý do và next step; elapsed time không tạo approval. Không marking success chỉ vì gần hết thời gian.
6. Tests tương ứng trong từng task; UI/model/live tests đúng quyền/budget/environment. Không giữ lỗi quyền/source/confirmation để tiết kiệm latency.
7. Cập nhật evidence, actual scope, remaining gaps, last_session và next_task; mọi trạng thái phải phản ánh kết quả thật.
8. Không commit/push/deploy, destructive action, gửi người khác, mở paid access hoặc tạo automation chỉ từ plan. Không tự spawn coding agents do kế hoạch có multi-agent sản phẩm.
9. Kết thúc phiên giữ dữ liệu/snapshots/runtime đang dùng; report task đã làm, kiểm chứng, giới hạn và task tiếp theo.

Câu bắt đầu sau:
> Thực hiện kế hoạch docs/UNIFIED_AI_IMPLEMENTATION_PLAN_20261014.md và backlog hợp nhất, bắt đầu từ UNI-001. Xác minh trạng thái hiện tại, bảo toàn dữ liệu và triển khai theo phụ thuộc, có kiểm chứng cho cả sinh viên, cán bộ và trung tâm multi-agent.

Trạng thái tại bàn giao: implementation_started false; next_task UNI-001; 50 task planned; evidence rỗng. Có code nền tảng trước đó nhưng chưa verified theo plan mới. Không có automation hoặc tác vụ nền được tạo; application tests và production changes chưa thực hiện trong lần lập kế hoạch.

## 14. Truy vết các hạng mục trước và nguồn tham chiếu

| Source item | Công việc hợp nhất |
| --- | --- |
| AI-001 | UNI-001 |
| AI-002 | UNI-003 |
| AI-003 | UNI-004 |
| AI-004 | UNI-006 |
| AI-005 | UNI-008, UNI-011 |
| AI-006 | UNI-002, UNI-011, UNI-035 |
| AI-007 | UNI-012 |
| AI-008 | UNI-013 |
| AI-009 | UNI-007 |
| AI-010 | UNI-014 |
| AI-011 | UNI-014, UNI-018 |
| AI-012 | UNI-009 |
| AI-013 | UNI-010 |
| AI-014 | UNI-015 |
| AI-015 | UNI-021 |
| AI-016 | UNI-022 |
| AI-017 | UNI-023 |
| AI-018 | UNI-024 |
| AI-019 | UNI-019 |
| AI-020 | UNI-002, UNI-025 |
| AI-021 | UNI-002, UNI-031, UNI-032, UNI-035 |
| AI-022 | UNI-039 |
| AI-023 | UNI-040 |
| AI-024 | UNI-041 |
| AI-025 | UNI-034, UNI-042 |
| AI-026 | UNI-043, UNI-045 |
| AI-027 | UNI-020, UNI-046 |
| AI-028 | UNI-044, UNI-047 |
| AI-029 | UNI-007, UNI-048 |
| AI-030 | UNI-049, UNI-050 |
| CHAT-MULTI-AGENT-CENTER | UNI-016, UNI-017 |
| ST-01 | UNI-001, UNI-003, UNI-026 |
| ST-02 | UNI-005 |
| ST-03 | UNI-018, UNI-027 |
| ST-04 | UNI-029 |
| ST-05 | UNI-028, UNI-032, UNI-037 |
| ST-06 | UNI-030 |
| ST-07 | UNI-033 |
| ST-08 | UNI-031 |
| ST-09 | UNI-036 |
| ST-10 | UNI-034, UNI-037, UNI-038 |
| ST-11 | UNI-043, UNI-045 |
| ST-12 | UNI-047, UNI-048 |

Các mappings trên là scope consolidation, không chuyển trạng thái completion hoặc authority. Backlog JSON giữ source_refs từng task cùng REQ/AT/dependencies và progress fields.

Nguồn chuyên môn đã đối chiếu trong quá trình trao đổi:
- [react-markdown](https://github.com/remarkjs/react-markdown): renderer/components và giới hạn plugins.
- [OWASP Authorization](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html), [AI Agent Security](https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html), [Transaction Authorization](https://cheatsheetseries.owasp.org/cheatsheets/Transaction_Authorization_Cheat_Sheet.html): scoped tools/identity/approval binding và execution checks.
- [W3C PROV Overview](https://www.w3.org/TR/prov-overview/): entity/activity/agent provenance; không yêu cầu thêm graph database.
- [LongMemEval](https://arxiv.org/abs/2410.10813), [AgentDojo](https://arxiv.org/abs/2406.13352): nhóm đánh giá memory và agent/tool dưới dữ liệu không đáng tin cậy; không thay benchmark nghiệp vụ hoặc pilot người dùng.
- Mã nguồn/đề xuất nội bộ được liệt kê tại phần 2–3 và task scopes; tồn tại code/test không chứng minh live capability đã đạt.
