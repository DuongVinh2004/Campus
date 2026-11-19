# Chat C — checkpoint UNI-043–050, batch 20261015-01

**Cập nhật cuối:** [report03](UNIFIED_AI_PARALLEL_C_20261015_03.md) ghi final stable snapshot, backend854/859 với5 lỗi gốc, TypeScript/build đạt và UNI-040 còn thiếu consumer chat tạm thời. Phần dưới giữ nguyên checkpoint lịch sử, không phải trạng thái hiện tại.

Ngày15/10/2026, Asia/Bangkok. **Phần độc lập đã thực hiện; final integration chưa sẵn sàng.** 043–050 đều `in_progress`, full acceptance pending. Không tuyên bố hoàn tất50 task. Source status001–042, requirement/task definitions và toàn bộ record chặng11/12 trong backlog giữ nguyên.

## Kết quả đã quan sát

43 ca C mới nhất đạt trong `checks/independent-06`, source hash ổn định trong lượt kiểm;5 ca rehearsal khác đạt trong `checks/rehearsal-01`, cũng ổn định. **48 latest unique `(classname,name)` của C đạt**, không cộng reruns, totals A+B hoặc684/685 lịch sử. Đây là kiểm chứng scoped local fixtures, không phải combined release gate.

Coverage C mới: model authority/write-tool/bad-output injection; altered student actor/form/record confirmation; private review-note injection; cross-record stale review; client authority; native missing consumer; missing/type-invalid metric observations; exact boolean staff confirmation; receipt write failure rollback rồi retry; competing confirmations; batch target hash/stale item/partial/retry; memory mode/consent/revoke sát use; recipient/session drift sát worker insert;2 worker instances tranh delivery. Existing suites06–12 được đưa vào runner combined đã chuẩn bị, chưa chạy combined khi thiếu final handoffs.

**Regression C-A-001:** lượt05 phát hiện `confirmed:1` và `1.0` được nhận như `true`, commit READY trên fixture. Finding01 ghi exact source/hash/reproduction; C không sửa source A. Source sau đó có `CaseConfirm.exact_confirmation` before validator; lượt06 giữ nguyên assertions, hai ca này đạt. Finding02 ghi scoped retest; vẫn cần owner revised/final handoff và final combined validation. Giữ toàn bộ failure XML/log/fixtures/preimages.

**Lỗi nền riêng:** session12 có684/685 unique passed, còn `test_deadline_and_token_reservation_stop_before_new_effect` deadline50ms (reservation/pending1, fake call0). C không chạy lại hoặc đóng lỗi đó, không sửa assertion/timeout/budget controls và không gọi backend release gate xanh.

## Commands và evidence

Mọi Python command dùng `.venv/Scripts/python.exe -B`, từ workspace. TestClient chạy local sockets với quyền thực thi được xét tự động; không gọi provider hoặc phục vụ runtime khác.

| Command/script | Exit / kết quả | Evidence thuộc `infra/local/unified-ai-parallel-20261015-01/stream-c/` |
| --- | --- | --- |
| `unified_parallel_c_preserve.py init` | 0; namespace exclusive,969 source hashes lúc preflight,4 retained DB ro digests | `preflight-01.json`, `preimages/backlog-before-01.json` |
| `unified_parallel_c_verify.py independent 01` | interrupted;14 contract dots, TestClient startup hang trong sandbox | `checks/independent-01/backend.log`, `interrupted.json`; không count như run hoàn chỉnh |
| `... independent 02` | pytest1:22/25; thêm lỗi console encoding ở runner | `checks/independent-02/`; C test expectation errors, không app regression |
| `... independent 03` | 0;25/25, source stable | `checks/independent-03/` |
| `... independent 04` | 0;29/29; source thay đổi ở script handoff A trong lúc chạy | `checks/independent-04/`; không final integration evidence |
| `... independent 05` | 1;35/37; numeric confirmation regression | `checks/independent-05/`, `findings/A-001-strict-confirmation-01.json` |
| `... independent 06` | 0;43/43, source stable | `checks/independent-06/`, `findings/A-001-strict-confirmation-02.json` |
| `... rehearsal 01` | 0;5/5; import ownership/preview/receipt/dedup, history/draft restart/readback, unavailable | `checks/rehearsal-01/` |
| `unified_parallel_c_evaluate.py prepare 01` | 0; prepare-only protocol/dataset | `fixtures/evaluation-01.json`; original gold retained |
| `... smoke 01` | 1; import error before fixture creation | `checks/evaluation-smoke-import-01.json` |
| `... smoke 02` | 1;2/4 material next-action checks; C gold used choose_workflow instead of clarify for ambiguous goal | `fixtures/evaluation-smoke-02/report.json`, `checks/gold-correction-01.json` |
| `... smoke 03` | 0;4/4 strengthened intent/effect/authority/no-token checks; business/source unchanged | `fixtures/evaluation-smoke-03/report.json` |
| `unified_parallel_c_load.py 01 --samples 24` | 0;24 valid outcomes, business/source stable | `fixtures/load-01/report.json` |
| `unified_parallel_c_preserve.py audit 01` | 0;4 all-table/row digests, paid/native metadata, guard, preimage và Git entries giữ nguyên | `preservation-01.json` |
| `unified_parallel_c_checkpoint.py 01` | 0;48 latest unique đạt,10 Python files parse/lint E9/F đạt; backlog scope/records/raw suffix giữ nguyên | `checks/checkpoint-01/report.json`, `coverage.json`, `backlog.patch` |
| `unified_parallel_c_preserve.py snapshot 01` | 1; source `apps/web/src/lib/assistant-state-service.ts` đổi giữa chụp | `snapshots/attempt-01-failure.json`, partial `snapshots/source-01/` được giữ; không có completed manifest |
| `unified_parallel_c_preserve.py audit 02` | 0; final checkpoint bảo toàn4 DB/metadata/guard/preimages/Git entries | `preservation-02.json` |

Ba kỳ vọng sai trong test mới của C được sửa có preimage và căn cứ contract hiện có: preview đã chuyển `PENDING_CONFIRMATION`; tampered form trả422 `PAYLOAD_HASH_MISMATCH`; unknown workflow dùng `clarify`, còn `choose_workflow` cho goal-changed resource. Không nới tập kết quả để pass; sau sửa kiểm exact status/code và toàn bộ business state không đổi. Scorer thêm required presence/type gates để missing observation không được tính là đúng abstention. Tests cũ/A/B assertions và thresholds giữ nguyên.

Smoke4 ca so simple-rule intent với actual student prepare-only, selected-multi/staff031/035 comparison chưa chạy; không human/expert review. Không gọi model output là gold hoặc fake outcome là usefulness. Cost USD chưa quan sát=null; paid calls0. Phép đo24 lần tuần tự trong-process fixture: restore p95**11,6286ms**, prepare p95**40,8717ms**, khoảng20,02 prepare operations/s cho vòng restore+prepare. Không suy production throughput/SLO từ mẫu này; completion-to-receipt/queue/cache/fault workload còn thiếu.

## Handoff và technical dependencies

Đã đọc A `handoffs/uni031-01.json` và actual case DTO/service/repository/router/bootstrap/UI source. API consumer `/v1/assistant/cases/*` thực tồn tại. `checks/uni031-hash-review-01.json` đối chiếu14 files: hash `case_workflow.py` đã đổi sau handoff, nên không công nhận handoff031 là current stable milestone. C kiểm actual consumer riêng trên scoped revision, không suy final.

Đã đọc B `integration-requests/memory-01.json` và `registrar-02.json`, core source/worker/routers và tests. Registrar02 tự nêu chưa có composition ack/context hook và cần A033/035/034; không công nhận memory/tracking source implemented từ registrar/core pass. Khi tạo checkpoint này chưa có A033/035/final, B039–042/final hoặc integration ack/readback đủ để final. Không gửi cross-chat messages/automation.

Final source snapshot, final combined backend/exact contracts, TypeScript và production build **pending**. `unified_parallel_c_frontend.py` đã chuẩn bị wrapper dùng guard nguyên byte; chưa chạy do thiếu stable final handoffs. Không build trên `apps/web` hoặc build đang phục vụ. Snapshot checkpoint nếu có chỉ là hash/preimage source, không phải complete runnable environment hoặc final acceptance. Guard SHA256 retained: `8f0886295da2214205cf257dd9e1d9476993ed1a7fb0ac67434909fa4af2eae6`.

Snapshot thử01 đã fail khi source upstream đổi; giữ nguyên partial snapshot và failure record, không retry/busy-poll hoặc dùng nó cho final checks. Mọi lượt final sau handoff phải dùng số snapshot/fixture/build mới. [Checkpoint/coverage/diff](../infra/local/unified-ai-parallel-20261015-01/stream-c/checks/checkpoint-01/report.json), [bảo toàn02](../infra/local/unified-ai-parallel-20261015-01/stream-c/preservation-02.json), [snapshot failure](../infra/local/unified-ai-parallel-20261015-01/stream-c/snapshots/attempt-01-failure.json).

## Artifacts chuẩn bị và phần còn pending

- [Acceptance/source/evidence map và044/046/048 scripts](UNIFIED_AI_ACCEPTANCE_C_20261015_01.md): AT01–50, task043–050, round-trip đầy đủ và fault branches.
- [Pilot protocol](UNIFIED_AI_PILOT_C_20261015_01.md): matched student/staff/round-trip, baseline/counterbalance/blind review và measurement fields; chưa participants hoặc real pilot data.
- [Runbook C](UNIFIED_AI_RUNBOOK_C_20261015_01.md): role instructions, source/receipt/permissions/retention/suppression/recovery và honest limitations; không launch result.
- [Master backlog](UNIFIED_AI_IMPLEMENTATION_BACKLOG_20261014.json): chỉ scoped C progress/evidence và parallel checkpoint record;001–042/session11/session12 giữ nguyên.

UI/component/DOM/browser/Playwright/E2E/visual/mobile chưa chạy theo direct instruction. User usefulness, qualified expert review, institutional rules/templates/eligibility, distributed/cross-store production recovery và production acceptance vẫn pending.048 full rehearsal cần043/047 thật; local5 ca không thay deployment rehearsal hoặc cấp deployment authorization.

## Bảo toàn và next action

Retained DB chỉ `mode=ro`/query_only/consistent read transaction, output chỉ schema/count/digest, không raw rows. Mọi writes/init/drift/fault thuộc fixture namespace C mới. Preimages có cả dirty/untracked backlog; preserved original session11/12 suffix bytes đã đối chiếu. Không delete/cleanup/reset/discard, sửa controls/protection/schema/lockfile/shared fixtures, commit/push/deploy hoặc stop/restart/reload serving runtime. Không paid/native model dispatch, contacts/messages hoặc production changes.

Next action thực: đọc A033/035/final và B039–042/final mới cùng integration acks; đối chiếu source hashes/API/UI composition và bổ sung C tests trên actual consumers. Sau source revision ổn định, tạo **fresh final source snapshot và fixture attempt mới**, chạy combined backend/exact contracts, guarded frontend prepare→build→typecheck; kiểm source hashes trước/sau và audit preservation lần mới. Giữ baseline50ms failure riêng. Sau đó cập nhật backlog theo observed scope, không chờ hoặc giả UI/pilot đã được phép/hoàn tất. Hiện hết phần kiểm chứng độc lập có thể kết luận; checkpoint này giữ đường tiếp tục cụ thể thay vì busy-poll vô hạn.
