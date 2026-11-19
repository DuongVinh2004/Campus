# UNI-043–050 — acceptance và kịch bản C, batch 20261015-01

**Đối soát cuối03:** [report C](UNIFIED_AI_PARALLEL_C_20261015_03.md) và `checks/coverage-final-04.json` là trạng thái mới. Final A/B/ack có213 hash checks khớp; snapshot03 ổn định; backend854/859 với5 lỗi namespace probe gốc,75 C cases đạt, TypeScript/build đạt. Không overall release gate xanh. Source031–039/041–042 implemented local,040 partial vì actual persistent temporary-chat mode reader/writer/UI chưa có; UI/pilot/expert/production và043–050 full acceptance vẫn pending. Map và các đoạn chuẩn bị bên dưới giữ lịch sử; “chờ handoff” đã được giải quyết trong report03, các gap nghiệm thu chưa được đóng.

Ngày 15/10/2026, Asia/Bangkok. Đây là map kiểm chứng và kịch bản chuẩn bị; không phải bằng chứng đã nghiệm thu. Scope local/synthetic, không UI tests, paid/provider hoặc production. Nguồn expected: `UNIFIED_AI_IMPLEMENTATION_PLAN_20261014.md` §§9–11 và `acceptance_groups` trong master backlog. Lỗi deadline/reservation50ms của chặng12 còn mở; không thay assertion, threshold hoặc budget control.

Tiếp tục02: [kết quả C mới](UNIFIED_AI_PARALLEL_C_20261015_02.md). Actual A033/035 và A/B explicit-store consumers đã có scoped C API checks;56 C cases đạt09, matched single/multi fake evaluation và bounded receipt instrumentation đã thực hiện. Final owner hashes/handoffs, combined/build, UI/pilot/expert/institutional/production vẫn pending. Các dòng “chờ” ở map ban đầu mô tả thời điểm chuẩn bị; evidence mới phải đọc cùng report02, không suy final từ số test.

## Task → consumer → bằng chứng cần có

| Task | Consumer/source cần đối chiếu | Bằng chứng và điều kiện còn thiếu |
| --- | --- | --- |
| 043 | Workflow/student confirmation; staff workspace/drafts; actual A035/036 và B040/042 consumers | C security suite cùng suites 06–12/A/B; exact schema equality; deny trước effect; final immutable handoffs, source hashes trước/sau. Chưa đủ consumer thì pending. |
| 044 | Student preparation, service/certificate workspaces; A031/033/035; history/settings/context | Chỉ chuẩn bị kịch bản bên dưới. Không chạy component/DOM/browser/Playwright/E2E/visual/mobile. Build/tsc không thay UI evidence. |
| 045 | `student_preparation.py`, `assistant.py`, actual A031/035 và multi-agent orchestration | Harness `unified_parallel_c_evaluate.py`; 4 smoke cases độc lập, baseline rule/simple và preparation thật; matched selected-multi/staff/expert review còn chờ. Không gọi fake model là gold. |
| 046 | Restore/preparation/completion, A036/038, B039/041, 043 | Instrumentation phân phối latency có n và bounds; p95 chỉ báo khi có đủ observations đã định nghĩa. Fixture sample không chứng minh production SLO; cost chưa quan sát là null. |
| 047 | 044/045/046 và người tham gia/môi trường được phép | Protocol C riêng; chưa có participant/session dữ liệu thật, usefulness pending. |
| 048 | Legacy import, durable receipts/restart, feature-off; 043/047 | Fixture rehearsal được kiểm riêng; full rehearsal còn pending pilot và final integrated source. Không transition retained/serving/production. |
| 049 | Commands/capabilities/permissions/retention/recovery đã quan sát | Runbook C nêu rõ commands đã chạy và phần chưa chạy; không ghi launch result chưa quan sát. |
| 050 | REQ01–26, AT01–50, UNI001–050, immutable handoffs/hash/evidence | Master backlog chỉ cập nhật scope có bằng chứng; giữ records11/12; không đóng cả50 task vì checklist hoặc build. |

## Acceptance → source/test/evidence map

Các test cũ dưới đây là coverage tái sử dụng được đọc từ source. Tên file không chứng minh đã chạy trong C. Kết quả chỉ lấy từ XML/log của đúng attempt, latest `(classname,name)`; không cộng tổng A+B hoặc lịch sử.

| AT | Source/consumer và regression source | Giới hạn cuối |
| --- | --- | --- |
| 01–02 | runtime inventory; action inventories; source composition; `test_unified_student11.py`, A032 | UI build/API binding và action inventory qua UI pending |
| 03–06 | conversation/catalog/legacy import; `test_unified_consumers09.py`, `test_unified_storage_completion.py`, `test_unified_actor_features.py` | Reload/relogin/device UI và real legacy ownership pending |
| 07–09 | grants/preferences/scoped_context; actor features/consumers09/staff12; C tampered confirmation | Actual B memory/tracking consumers phải kiểm thêm, không dùng core pass thay wiring |
| 10–11 | shared renderer/runtime/context source; consumers09, coordination10 | Accessibility/mobile/dark/keyboard/route UX không chạy |
| 12–17 | `assistant.py`, `student_preparation.py`; `test_unified_student11.py`; C evaluation cases | Gold synthetic giới hạn; institutional rules/OCR authenticity không suy ra |
| 18–19 | service/certificate preview+confirm, receipts; `test_service_stage6.py`, `test_certificate_stage1.py`; C changed form/actor/record tests | C chỉ gọi fixture; A031/036 cần exact source/recipient binding và crash checks riêng |
| 20–21 | durable coordination, workflow/source bindings; coordination10/student11/staff12 | Source/readiness không tự cấp execution authority |
| 22–28 | source reader/evidence gate/multi-agent contracts and store; `test_multi_agent_integrated.py`, coordination10; C bad outputs/write tools | Lỗi nền deadline50ms giữ mở. Provider thật0; distributed recovery chưa chứng minh |
| 29–33 | staff evidence/checklist/dependency cache/drafts; `test_unified_staff12.py`, storage completion; C review-note injection | UI autosave/reload không được suy từ backend restart |
| 34–38 | assignments, A031/033/034/035 actual consumers; staff12 process/C stale cross-record review | A handoff và per-recipient public/internal readback chưa có tại chuẩn bị |
| 39–41 | A036 batch receipts/partials, A037 priority, A038 timing/complexity | Chờ A source/handoff; load không bắn vào serving runtime |
| 42–44 | B memory DTO/service/repository, privacy UI source, actual context consumer | Integration request `memory-01.json` tự ghi core in_progress; chưa tính implemented/verified |
| 45–46 | B subscription/event worker/inbox và A durable business event consumer | Local inbox, recipient/revoke/quiet/restart; remote channels không cấu hình, không gửi tin |
| 47–48 | C regressions + combined exact backend; bounded instrumentation | Không overall score che lỗi quyền; unobserved metrics=null |
| 49 | Pilot protocol C, independent/matched real sessions | Chưa có participants/measurements; không gọi synthetic là usefulness |
| 50 | read-only retained digest/preimages, fresh source snapshots, unchanged build guard; import/restart fixture tests | Không deploy/stop/reload runtime, không xóa dữ liệu/build/log/evidence |

## UNI-044 — kịch bản UI đã chuẩn bị, chưa chạy

Fixture mới tách namespaces/student/staff và tenant; ghi source hash/build ID/API/mode, actor IDs đã giảm dữ liệu, resource/version và receipts. Không dùng UI mock session như server authority. Trước khi chạy thật phải có consumer A031/033/035, 043 phù hợp và chỉ dẫn mới cho phép UI testing.

| Bước | Thao tác và kỳ vọng | Evidence phải thu khi được chạy |
| --- | --- | --- |
| 1 | Student nêu goal rõ hoặc mơ hồ. Mơ hồ hỏi lựa chọn; không tự chọn target. | Exact source input/version và intent/clarification |
| 2 | Prepare draft: dùng fact có nguồn, giữ manual edit, chọn đúng draft. | Field provenance/diff/missing group; không submit |
| 3 | Review preview rồi confirm đúng payload/recipient/version/expiry. | Preview hash và business receipt; không lưu token vào report |
| 4 | Staff đúng queue/assignment mở dossier và source locator/version. | Public/internal projections; mandatory review chưa tự tick |
| 5 | Staff tạo và confirm typed supplement items đã biết. | Item IDs/criterion/reason/format/source; không private notes |
| 6 | Student sửa đúng items, giữ fields không đổi và nhận receipt. | Mapped correction IDs, before/after versions, stable retry key |
| 7 | Staff delta recheck, nguồn thay đổi hoặc transfer/revoke chặn draft cũ. | Affected/reused criterion hashes; stale denial và giữ nháp |
| 8 | Staff chọn structured outcome, preview recipient/result, confirm. | Required reviews, exact result/template/source binding, receipt |
| 9 | Student và staff đọc cùng business state theo quyền. | Exact case/result/receipt, private note/memory không xuất hiện |
| 10 | Đổi route/history/settings/context/account, reload/new chat. | Goal/resource continuity, saved vs pending/error; không leak hoặc mất dữ liệu |

Fault branches chuẩn bị: wrong actor/tenant/queue/recipient; changed payload/preview/source/template; source missing/conflict; disconnected save/confirm; crash before/after commit; duplicate retry; CAS tabs/officers; revoke during pending; stale one batch item; restart worker/no-change/quiet hours; memory off/temporary/forget suppression. Mỗi nhánh cần evidence riêng, không thay bằng tổng score.

## 046/048 — instrumentation và rehearsal

Định nghĩa trước khi đo: monotonic duration quanh **restore**, **prepare** và **complete đến receipt/readback**, tách system time với active/student wait/unit wait. Báo sample count, concurrency, dataset hash, warm/cold cache, outcome correctness, queue depth/bounds, retry/fault counts và actual dispatch metadata. Harness có `distribution`: dưới20 observations không báo p95; mẫu fixture20+ chỉ mô tả mẫu đó. Không gán usd=0 cho model cost chưa đo; paid dispatch của C=0, model USD=null. Không thay budgets để tăng throughput.

Rehearsal được phép chỉ dùng DB fixtures mới của C: import preview/confirm/dedup và unknown owner deny; restart committed history/draft/receipt; native composition thiếu consumer trả unavailable; feature-off vẫn có manual/readback path nếu source thực hỗ trợ. Không mở writer/init/migrate retained DB. 048 full acceptance vẫn cần043/047 thật. Production checklist chỉ là tài liệu reviewable, không cấp deployment authorization.
