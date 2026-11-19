# Chat C — kết quả kiểm cuối và bàn giao, batch 20261015-01

Ngày 15/10/2026, Asia/Bangkok. **Backend cuối: 859 ca duy nhất, 854 đạt, 5 lỗi; release gate chưa đạt.** Cả 75 ca C đạt trong chính lượt tổng này. TypeScript và production build trên snapshot frontend mới đạt, BUILD_ID `uunQdK30YZKwHBmdmoZkW`. Đây là kiểm chứng local/synthetic, chưa phải nghiệm thu người dùng hoặc production.

UNI-031–039 và UNI-041–042 được ghi `implemented` trong phạm vi source local. **UNI-040 vẫn `in_progress`: thiếu consumer thực lưu/đọc/chọn chế độ chat tạm thời.** UNI-043–050 vẫn `in_progress`, full acceptance pending. Không tuyên bố hoàn tất 50 task. Bản này cập nhật kết luận của [checkpoint01](UNIFIED_AI_PARALLEL_C_20261015_01.md) và [tiếp tục02](UNIFIED_AI_PARALLEL_C_20261015_02.md); giữ toàn bộ artifacts và kết quả cũ.

## Source và phạm vi đã đối soát

Đã đọc A `stream-a/handoffs/final-01.json`, B bốn milestones039–042 cùng `stream-b/handoffs/final-01.json`, A `stream-a/integration-acks/personal-03.json`, và báo cáo A/B. `checks/final-handoffs-review-03.json` ghi 213 kiểm tra file/hash đều khớp, gồm file được tham chiếu nhiều lần; đây không phải 213 test hoặc 213 file duy nhất.

`snapshots/manifest-03.json` chứa 1.069 file và preimages tại `snapshots/source-03/`; capture ổn định. Đây là source/hash reference, không phải môi trường runtime hoàn chỉnh tự chạy được. Backend và frontend final kiểm cùng revision; source ổn định trong từng lượt kiểm. Sau kiểm chỉ cập nhật metadata backlog và báo cáo C; implementation đã kiểm giữ nguyên snapshot03, có đối soát cuối riêng.

| Task | Trạng thái source local | Giới hạn cần giữ rõ |
| --- | --- | --- |
| 031–032 | Typed staff outcome, preview/confirm/source binding, receipts; inventory/context hỗ trợ thao tác | UI/operator và authority/rules tổ chức chưa nghiệm thu |
| 033–035 | Typed supplement/correction/delta; handover; business state với projections theo quyền | Consumer explicit stores/resource-context đã kiểm; không suy ra main model writer, legacy chat hoặc atomicity phân tán |
| 036–038 | Batch targets/partial/retry receipts; priority/queue; bottleneck/timing source | Chưa có đầy đủ workload, dữ liệu effort/wait thực hoặc UI usability |
| 039 | Memory actor-scoped, provenance/validity, actual resource-context reader | Main model writer/legacy chat chưa nối; UI chưa kiểm |
| 040 | **Một phần:** correction/CAS/controls, forget suppression, export/retention và manifest invalidation | **Thiếu persistent temporary-chat mode reader/writer/UI**; unknown legacy mode fail closed; chưa công bố hỗ trợ chat tạm thời |
| 041 | Local durable status/feedback/supplement subscriptions/outbox/worker | Deadline thiếu sourced consumer trả503; remote channels unavailable; không hứa deadline notification |
| 042 | Local in-app inbox/next action/stop và UI source | Không có UI/mobile/E2E evidence hoặc remote delivery |

Chi tiết owner: [báo cáo A](UNIFIED_AI_PARALLEL_A_20261015_01.md), [báo cáo B](UNIFIED_AI_PARALLEL_B_20261015_01.md). C không sửa implementation, tests hoặc guard của A/B để làm lượt tổng đạt.

## Kết quả cuối và lỗi còn giữ

`scripts/unified_parallel_c_verify.py combined 03` exit1, source stable, 859 unique `(classname,name)`, 854 pass/5 failure, không skip hoặc cộng totals A+B/history/reruns. Command wall time khoảng334,93s; pytest báo331,47s. Log/XML/command đầy đủ tại `checks/combined-03/`.

Năm lỗi gốc:

1. `tests/integration/test_unified_staff12.py::test_actual_two_process_staff_cas[draft]`.
2. Cùng file, `test_actual_two_process_staff_cas[claim]`.
3. `tests/unified_workflow13a/test_durability.py::test_two_fresh_processes_confirm_one_transaction_and_same_receipt`.
4. `tests/unified_personal13b/test_memory_tracking.py::test_worker_real_process_restart_does_not_redeliver`.
5. `tests/unified_personal13b/test_wired_consumers.py::test_actual_A_business_outbox_two_process_recovery`.

Probe cũ giới hạn fixture trong namespace session12/A/B; khi chạy từ C, child thoát trước readiness/tick. Ba ca đầu hết thời gian đợi readiness sau child exit1; hai ca B báo `ValueError: B fixture only`. Source guards và failure evidence được giữ nguyên. `findings/A-B-002-process-namespace-02.json` ghi đủ năm lỗi và follow-up; không diễn giải chúng là business concurrency đã chạy thành công.

C bổ sung probe chỉ cho exact new C fixtures. Bốn ca thật nhiều process của C đạt trong final: draft CAS và claim CAS mỗi ca một commit/một conflict; hai case confirms có cùng receipt và chỉ một effect; worker restart delivery1 rồi0 trên actual business outbox. Chúng là bằng chứng riêng, **không thay kết quả năm test gốc** và không chứng minh crash atomicity giữa nhiều datastore.

75 ca C gồm 60 ca behavior/process và 15 ca exact schema equality với models cases-v13-02. Coverage gồm bad model outputs/write-tool/injection; actor/recipient/resource/source/payload drift; review mandatory/privacy; numeric confirmation; failure rollback/retry/receipt; batch stale/partial/idempotency; supplement/correction/final result/handover; composed memory/forget/consent/recipient/session checks và worker dedup/restart. C syntax/ruff kiểm 18 file: exit0 (`checks/checkpoint-02/report.json`).

Lỗi nền deadline/reservation50ms `test_deadline_and_token_reservation_stop_before_new_effect` **đã fail scoped01 và ở lịch sử11/12, pass final03 khi assertion/threshold/budget controls không đổi**. Timing sensitivity vẫn chưa xử lý; không đánh dấu fixed hoặc xóa failure. Không chạy lặp để tìm kết quả đẹp.

Hai regression được C phát hiện có retest cuối đạt: `confirmed:1/1.0` trước đây commit như true, nay exact boolean validator chặn; stale certificate supplement binding trước đây không invalidated đúng, nay affected01 3/3 và final03 đạt. Findings A-001 revisions01/02 và A-003 revision01 cùng XML/fixtures gốc được giữ. Early `scoped01` có826/832 pass, source thay đổi; kết quả này không được dùng làm final source evidence.

## Commands cuối đã chạy

Các đường dẫn evidence bên dưới tương đối với `infra/local/unified-ai-parallel-20261015-01/stream-c/`. Python dùng `.venv/Scripts/python.exe -B`; mỗi attempt/fixture exclusive mới. TestClient/process chạy với quyền local socket cần thiết; không gọi provider.

| Command | Exit / quan sát | Evidence |
| --- | --- | --- |
| `unified_parallel_c_verify.py independent 10` | 0;60/60, source stable | `checks/independent-10/command.json` |
| `... verify.py contracts 01` | 0;15/15 exact schemas | `checks/contracts-01/command.json` |
| `... verify.py affected 01` | 0;3/3 certificate binding | `checks/affected-01/command.json` |
| `unified_parallel_c_preserve.py snapshot 03` | 0;1.069 files, stable | `snapshots/manifest-03.json` |
| `unified_parallel_c_verify.py combined 03` | **1;854/859, 5 failures** | `checks/combined-03/command.json`, `.log`, `.xml` |
| `unified_parallel_c_frontend.py prepare 03` | 0;fresh frontend, guard identical | `checks/frontend-03/prepared.json` |
| `... frontend.py build 03` | 0;production build, source stable | `checks/frontend-03/frontend-build-03.json`, `source-after-build.json` |
| `... frontend.py typecheck 03` | 0;`tsc --noEmit --incremental false` | `checks/frontend-03/typescript.json` |
| `unified_parallel_c_preserve.py audit 04` | 0;retained digests/metadata/guard/preimages/Git entries unchanged | `preservation-04.json` |
| `unified_parallel_c_checkpoint.py 02` | 0;859 latest unique/854 pass,18 syntax files, ruff0; pre-final-metadata history preserved | `checks/checkpoint-02/report.json`, `coverage.json` |

Final frontend summary: `checks/frontend-final-summary-03.json`. Build dùng inherited preparation pipeline và guard nguyên byte SHA256 `8f0886295da2214205cf257dd9e1d9476993ed1a7fb0ac67434909fa4af2eae6`, các Next/TypeScript/font templates trước đó và root-page→home-view shim đã ghi trong prepared manifest. Không build trực tiếp `apps/web` hoặc build đang phục vụ; không suy build đã chạy chứng minh UI hoặc live runtime.

Snapshot01/02 giữ partials/failure do source drift. Independent07 giữ lỗi C CAS setup,08 pass nhưng source drift; compare01 giữ interruption do sandbox,02/03 giữ harness errors; mọi attempt trước có trong reports01/02. Không xóa hoặc ghi đè evidence thất bại.

## Evaluation, đo đạc và phần nghiệm thu còn thiếu

UNI-045: `fixtures/evaluation-smoke-03/report.json` có4 prepare-only smoke cases. `fixtures/matched-comparison-04/report.json` chạy actual single graph và selected-multi graph trên3 điều kiện nguồn synthetic giống nhau: current/missing/wrong numeric claim. Cả hai giữ material gates đúng; fake model dispatch single=3/2/4, multi=8/5/8; durable dispatch counts khớp. Scripted model ports đo control flow, không đo chất lượng model hoặc lợi ích người dùng. Gold synthetic fee50.000 không phải mức phí chính thức; staff031/035 consumer được kiểm riêng, không phải staff model outcome generator. Expert/blind/human review chưa chạy; model USD=null.

UNI-046: load01 có24 observations tuần tự trong process, restore p95=11,6286ms, prepare p95=40,8717ms. Case-measure01 có3 first confirm→public readback từ32,6971 đến41,7914ms, p95=null vì n<20;24 warm receipt reads theo3 case p95=14,9242ms. Không phải24 independent user sessions hoặc production SLO; queue/cache/concurrency/full workload và active labor chưa đo. Separate fault tests là correctness evidence, không thành load statistics.

UNI-048:5 fixture rehearsal checks import/ownership/dedup/history-draft-receipt restart/readback/unavailable đạt và đã nằm trong859 unique cuối; không cộng thêm5. Full rehearsal còn phụ thuộc043/047, feature-off/serving/production chưa nghiệm thu. UNI-044 UI scripts và UNI-047 pilot protocol đã chuẩn bị, **không chạy component/DOM/browser/Playwright/E2E/visual/mobile tests hoặc phiên người dùng**. Human usefulness/institutional rules/real legacy ownership/distributed recovery/production đều pending.

## Backlog, bảo toàn và bàn giao

Master backlog ghi next coding gap `UNI-040`, source031–039/041–042 `implemented`,040 và043–050 `in_progress`, mọi full acceptance mới vẫn pending. `pending_verification` bổ sung031–042, không nâng task nào thành `verified`. REQ01–26/AT01–50 mapping và task definitions giữ nguyên; không dùng số test hoặc build để đóng requirement. `parallel_c_record` cũ giữ lịch sử; record mới là `parallel_c_final_record`. `last_session` vẫn nguyên record12, không dùng nó làm current status; đọc record mới/continuation_note này.

Preimages metadata nằm trong `preimages/`, gồm `backlog-before-patch-04.json`. UNI001–030 và toàn bộ raw suffix `session11_record`/`last_session` được giữ nguyên. Exact scoped diff/hash/source comparison cuối: `checks/reporting-final-04.json`, `backlog-final-04.patch`, `reporting-metadata-final-04.patch`, `coverage-final-04.json`. C handoff là `handoffs/final-01.json`; preservation sau metadata ở `preservation-05.json`.

Audit04 đọc4 retained DB bằng `mode=ro`/query_only: schema và tất cả table/row digests không đổi; paid/native metadata, guard, backlog preimage và pre-existing Git entries không đổi. Không ghi raw retained rows/token vào báo cáo. Paid/provider calls=0; không runtime transition, production, deletion, reset/cleanup, commit/push/deploy, cross-chat message hoặc automation. Không xác nhận current serving version; build mới chưa được phục vụ.

Việc còn lại: owner040 hoàn thiện actual temporary mode consumer; owner probes xử lý compatibility namespace có bảo vệ, giữ kết quả gốc; xử lý deadline50ms timing sensitivity. [Acceptance map](UNIFIED_AI_ACCEPTANCE_C_20261015_01.md), [pilot protocol](UNIFIED_AI_PILOT_C_20261015_01.md) và [runbook](UNIFIED_AI_RUNBOOK_C_20261015_01.md) giữ phần UI/expert/pilot và vận hành chưa chạy rõ ràng.
