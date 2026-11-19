# Chat A — source UNI-031–038 và tích hợp chung

Ngày15/10/2026, Asia/Bangkok. UNI-031–038 đã nối consumer ở source local/synthetic; full UI/institutional/production acceptance còn pending. Không nạp source này vào serving runtime. Handoff cuối giữ exact hashes để C kiểm fresh snapshot.

## Source đã nối

- **031:** `application/assistance/case_contracts.py`, `case_workflow.py`, `presentation/case_workflow.py` nối prepare/read/CAS revision, preview public/internal, exact student/recipient/case/version/queue/assignment/source/rule/template, review bắt buộc và confirm. Executor gọi `ServiceRequestService.act` hoặc `CertificateService.act` trong cùng business transaction với audit/outbox/receipt; prepare/preview không chuyển business state. Nháp riêng append-only, source/assignment/review/version drift chặn thực hiện và giữ nháp. Không có model business-write tool. Mẫu/eligibility chính thức chưa xác minh.
- **032:** runtime chung và `ResourceAssistant` gửi explicit surface/intent cùng exact reference. Queue/detail/checklist/editor/error/handover có typed consumer; ambiguous selection yêu cầu chọn hồ sơ. Admin publishing unavailable, giữ thao tác quản trị thủ công theo quyền. Không đọc DOM hoặc unsaved private form, không đưa toàn bộ dossier vào model context. Đây là typed deterministic assistance, chưa có staff model chat.
- **033:** cán bộ tạo nhóm item IDs/criterion/source/reason/accepted format, review/preview/confirm trước yêu cầu công khai. `CaseSupplementPanel` nối checklist sinh viên và map từng response đúng item. Preview/confirm kiểm nguồn, version, provenance; business supplement cũ được tái sử dụng và staff dossier delta recheck phần đổi, giữ phần không đổi. Certificate về SUBMITTED rồi cán bộ tiếp nhận riêng; service về VALIDATING theo hai domain hiện có.
- **034:** selected summary done/open/evidence/next action, visibility public/internal, preview và reauthorize target directory/queue/assignment/session/version. Bàn giao và receipt cùng transaction, restart/readback được kiểm. Certificate transfer chưa có consumer, trả unavailable. Không SLA hoặc tự cấp quyền queue.
- **035:** `/cases/projection:read`, `/events:read` dùng business state/version chung; projection theo quyền, private draft/review/memory không nằm trong student view. Mỗi read kiểm source/session/assignment; frontend refetch khi version đổi/focus/tab visible, ẩn projection khi tab không hiển thị. Metadata invalidation/outbox append-only ghi atomically cùng business event. Không tuyên bố server push hoặc distributed cache invalidation.
- **036:** exact bounded batch manifest tối đa20 targets, từng version/nháp/public payload, check/preview trước outer explicit confirm. Mỗi item có transaction/authorization riêng và durable receipt. Partial/blocked/uncertain được giữ; retry đọc per-item receipt, không replay item đã commit. `StaffCaseInsights` nối selection, preview, confirm và readback batch.
- **037:** nhóm ready/waiting/blocked theo findings/review hiện tại, giữ business order trong nhóm; reason và routing giải thích rõ. Deadline xử lý unavailable do chưa có source xác minh, không tạo confidence/SLA, assignment hay queue-position mutation.
- **038:** staff aggregation scoped theo queues, tối đa100 hồ sơ/lần và báo truncated. Tách observed student wait (WAITING_STUDENT), unit wait (SUBMITTED), age buckets/workflow strata/supplement/transfer/reopen event counts. Active labor/system processing chưa quan sát => null; không đổi policy từ backlog hoặc log raw PII.

Frontend source consumers: `features/assistance/CaseWorkflowPanel.tsx`, `CaseSupplementPanel.tsx`, `CaseProjectionPanel.tsx`, `StaffCaseInsights.tsx`, hai service/certificate workspaces và shared runtime. Contracts exact trong `contracts/json-schema/assistance/cases-v13-02/`.

## Tích hợp B

`wire_assistant_features` gọi registrar B với **repositories được truyền tường minh** qua `create_unified_demo_app`; không tự init/migrate retained personal DB. Memory retrieve/use nối vào actual scoped resource-context API khi caller chọn bounded `memory_terms`, request session recheck và fresh hash. Memory là untrusted declaration, không thay business source/rules. Chat legacy không có server mode => fail closed; chưa có model-writer memory consumer.

`personal_consumers.py` cung cấp durable business outbox read/ack, current recipient registry (metadata và token hash, không lưu bearer token), exact projection và source-permission recheck. Chỉ whitelist public business transitions phát tracking event; draft/preview preparation không tạo notification. Adapter và B cùng kiểm source evidence theo grant hiện hành. Worker/inbox là local in-app, không email/Slack. `/cases/notification:open` trả route/query đã kiểm: service `/services`, certificate staff `/staff`, certificate student `/tickets`; source/version/recipient/assignment/session sai đều chặn. B sở hữu UI memory/notifications và worker, A không sửa các module đó.

Acknowledgements append-only trong `stream-a/integration-acks/`. Handoffs031/033/035 được công bố sớm, revision cuối giữ bản cũ. C sở hữu master backlog và kết luận tích hợp cuối; A không sửa backlog.

## Kiểm tra và lỗi giữ lại

Evidence nằm trong `infra/local/unified-ai-parallel-20261015-01/stream-a/`. Python dùng `-B`, idempotency/basetemp/DB mới mỗi attempt; TestClient cần socketpair local ngoài sandbox Windows. Không gọi provider hoặc UI/component/DOM/browser/Playwright/E2E/visual/mobile tests.

| Evidence / command | Exit / kết quả |
| --- | --- |
| `scripts/unified_parallel_a_workspace.py` | 0; preimages, Git status, consistent read-only all-table/row digests của4 retained DB. |
| Lượt01/02 sandbox | Dừng trước test do Windows TestClient socketpair kẹt; trace02 và fixtures giữ nguyên. |
| `unified_parallel_a_verify.py 03/04` | 03:14 passed/1 DTO fixture normalization mismatch;04:15 passed. |
| Lượt05/06 | 05:26 passed/1 sai alias fixture (SV002 không tồn tại);06:32 passed/8 C namespace setup errors, không phải business check. C đã tự kiểm trong namespace C. |
| Lượt07 |152 passed/2 old process probes chỉ cho namespace chặng12; không sửa probes/assertions/timeout. |
| Lượt08/09/10 |32 passed;3 actual A+B integration passed;5 integration passed sau whitelist/source-grant recheck. |
| **Lượt11** |**352 passed/2 deselected**, gồm A two-process confirmation và receipt-failure rollback, workflows/services/certificates/student/staff/actor/context/contracts. Hai old namespace probes giữ nguyên. |
| Lượt12/13 | Giữ lỗi certificate supplement mới: timestamp quan sát thay đổi giữa preview/confirm đã sửa binding theo source identities/hashes/fingerprint, giữ mốc record/package. Ca test vòng đầy đủ ban đầu chưa gọi officer accept riêng; đã bổ sung đúng bước đó và giữ assertion VALIDATING sau accept. |
| **Lượt14** |**79 passed** final affected, gồm42 ca A; certificate success/source drift/type validation, exact boolean, recipient, stale, CAS, transfer/revoke, partial batch/restart/readback, event/projection, outbox/worker/context và2 process mới. |
| `unified_parallel_a_frontend.py prepare/typecheck/build 01/02` | Mỗi lệnh exit0; fresh snapshots. Final02 BUILD_ID `e1lwvBfjk0xQXu-gPwJrW`. Guard SHA256 `8f0886295da2214205cf257dd9e1d9476993ed1a7fb0ac67434909fa4af2eae6`, nguyên byte. |
| Ruff E9/F scoped source |0, không finding. |

**Lỗi nền còn tồn tại:** lượt13 tái hiện `tests/unit/agent/test_multi_agent_integrated.py::test_deadline_and_token_reservation_stop_before_new_effect`: deadline50ms, reservation/model_calls=1 nhưng fake provider calls=0. Không sửa budget/deadline controls, assertion hoặc timeout. Không có backend release gate xanh.

C phát hiện numeric `1`/`1.0` qua `Literal[True]`; A thêm exact `value is True` trước DTO validation cho single/batch confirms. A exact tests đạt; C `A-001-strict-confirmation-02.json` ghi43 ca scoped đạt. Mọi finding/log trước vẫn giữ.

Khử trùng latest XML03–14 theo `(classname,name)`: **355/356 ca thực thi đúng namespace đạt**, còn1 lỗi nền50ms; không cộng reruns hoặc ca lịch sử SESSION12. Ngoài đó có10 identities chẩn đoán harness (8 C namespace +2 old process namespace) giữ failure record; raw XML latest tổng366 identities. Đây không phải356 ca nghiệm thu toàn hệ thống.

## Bảo toàn và giới hạn

Preimages11 exact source files; snapshot dispatch giữ nguyên. Audit cuối so mọi bảng/hàng của4 retained DB với preflight, chỉ mở `mode=ro`. Source dirty/untracked trước đó được giữ; A chỉ patch scope của mình. Không sửa AGENTS/protection/lockfiles/budget controls/build guard, không delete/cleanup/reset/discard/commit/push/deploy hoặc stop/restart/reload serving runtime. Không ghi source B/C hoặc sửa test cũ. Logs, fixtures, failed attempts và snapshots/builds giữ lại.

Source này là candidate local; chưa chứng minh current serving runtime, official institutional rules/templates/eligibility, full UI/accessibility/mobile, pilot usefulness, production load/SLA hoặc distributed atomicity giữa business và personal stores. C cần final fresh snapshot/combined checks; không dùng synthetic/backend/build thay những acceptance đó.
