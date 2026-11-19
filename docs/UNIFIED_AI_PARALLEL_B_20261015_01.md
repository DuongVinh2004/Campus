# Luồng B — memory, quyền riêng tư và theo dõi

Ngày 15/10/2026, Asia/Bangkok. **57/57 ca B duy nhất theo kết quả mới nhất đạt**; source của consumer trước/sau lượt cuối được kiểm hash. TypeScript độc lập và production build snapshot04 đạt, BUILD_ID `z8D5nXftMrBzAlmxAp283`. Đây là source local/synthetic, không phải release gate tổng hoặc nghiệm thu giao diện. Lỗi nền deadline50ms của SESSION12 chưa được sửa/chạy lại trong B.

| Task | Consumer đã kiểm thật | Trạng thái và phần còn thiếu |
| --- | --- | --- |
| UNI-039 | Actor-owned repository → API preview/confirm/readback → `ScopedContextService` → `memory.retrieve/use` trên resource context có quyền | Implemented trong phạm vi local resource-context. Không nối main model writer hoặc legacy chat memory. |
| UNI-040 | CAS correction, control opt-in/off, forget tombstone, manifest invalidation, export projection, receipt/restart, memory/privacy UI source | **Partial**: các controls đã nối; chưa có temporary-chat mode được lưu/xác minh trên chat thật. Core từ chối đọc/ghi khi reader trả temporary; legacy mode chưa xác minh trả unavailable. Không coi fake mode test là consumer temporary-chat thật. |
| UNI-041 | Business transition của A cùng transaction với append-only `case_tracking_event` → source/ack → worker B → durable inbox | Implemented local cho status/feedback/supplement. Deadline thiếu nguồn xác minh trả503; email/Slack/remote channels unavailable. Worker chỉ chạy trên fixture mới, chưa launch/restart serving runtime. |
| UNI-042 | Recipient-safe inbox API → UI source `/notifications` → actual `notification:open` của A → đúng resource/version/role path và stop preview/confirm | Implemented trong source/local in-app. Browser, UI/mobile/accessibility/usefulness và institutional acceptance pending. |

Memory mặc định tắt và cần consent cá nhân hóa hiện hành cùng xác nhận memory riêng theo disclosure `memory.v1`. Sở thích, mục tiêu, điều cá nhân xác nhận có source actor/session lưu trong kho riêng, thời gian, thời hạn, purpose, scope và revision. Context chỉ đưa tối đa5 mục liên quan, giới hạn100 topic gồm tombstone, không đưa session ID vào projection. Khai báo luôn là dữ liệu không đáng tin, `action_authority=none`; không thay nguồn học vụ, rule hoặc quyền nghiệp vụ. Resource memory rechecks grant/source; staff case memory bị từ chối. Không import history/legacy, không chuyển inference/OCR thành confirmed fact.

Correction dùng CAS cùng receipt/idempotency append-only. Quên giữ nội dung cũ trong revision và tạo suppression có provenance/version; topic không thể tái tạo bằng đổi loại memory hoặc phiên bản resource. Fresh context/use rechecks và hash invalidation ngăn dùng manifest trước sửa/quên. Tắt memory giữ dữ liệu và không xóa history; rút consent ẩn nội dung trong management/export/context. Export là projection memory hiện được phép đọc, không phải export toàn tài khoản. **Không physical deletion** DB/history/index/backup; chưa có erasure hoàn tất hoặc retention deadline được hứa.

Tracking bind đúng actor/tenant/session/roles/units/resource/trigger/channel/expiry/permission version. Thời hạn tối đa theo grant và session, quiet hours có timezone. Khi resource đổi version, source evidence của quyền gốc vẫn phải khớp observation mới. Recipient registry, grant, source, queue/assignment và exact version được kiểm lại trước insert và khi đọc inbox/mở hồ sơ. Private preparation events giữ ở audit, không vào notification outbox. Event trước thời điểm opt-in không tạo delivery. Worker tối đa20 events/jobs mỗi tick, ba attempts cho dependency timeout, durable delay quiet hours, dedup/no-change, stop/revoke suppression. Không tự submit/approve.

Composition thực: `create_unified_demo_app(..., personal_memory_store=explicit_repository, personal_tracking_store=explicit_repository)`. A là người sửa shared wiring. Không có store/reader/consumer thì fail closed, không tự init/migrate retained DB. B registrar đặt route cụ thể trước generic proxy; context consumer dùng `request_guard` và `retrieve/use`. Main model writer chưa dùng memory. In-app consumer không có remote delivery credentials.

Ack A đã đối chiếu: `stream-a/integration-acks/personal-03.json`; mọi file hash trong ack khớp tại chốt B. Handoffs UNI-031/033/035 đã được đọc và consumer event/projection được kiểm trên fixture mới. UNI-034 open contract thực: `POST /v1/assistant/cases/notification:open` với exact event_id; `/services?request=…`, staff certificate `/staff?request=…`, student certificate `/tickets?request=…`. UI B kiểm lại qua endpoint trước navigation, không dựng URL tùy ý. Summary public/internal lấy từ projection có quyền của A.

Evidence nằm trong `infra/local/unified-ai-parallel-20261015-01/stream-b/`:

| Command từ workspace | Exit | Kết quả/evidence |
| --- | --- | --- |
| `.venv/Scripts/python.exe -B scripts/unified_parallel_b_preflight.py` | 0 | Exclusive stream-b; hai preimages frontend; Git state; mọi bảng/hàng của4 retained DB, mode=ro. |
| `… unified_parallel_b_verify.py tests 01` | 1 | Harness timeout180s tại local HTTP fixture trong sandbox. Giữ fixture và `timeout-observed.json`; lượt này không có XML/pass count. Harness đầu chưa giữ captured stdout, hạn chế đã ghi lại. |
| `… unified_parallel_b_verify.py tests 02` | 1 | 26 passed/1 failed: fixture hết hạn sai invariant auth_time; sửa setup, giữ assertion expired session. |
| `… unified_parallel_b_verify.py tests 03/04/05` | 0 mỗi lượt | 27/35/40 ca; CAS/isolation/temporary/missing consumer/worker/recovery/schema, mở rộng dần. |
| `… unified_parallel_b_verify.py tests 06` | 1 | 40 passed/1 failed: generic proxy bắt route memory trước registrar. Sửa priority trong registrar B, giữ assertion401. |
| `… unified_parallel_b_verify.py tests 07` | 1 | 40 passed/1 failed: fixture alias SV002 không tồn tại; dùng alias có sẵn SV024, giữ isolation assertion. |
| `… unified_parallel_b_verify.py tests 08/09/10/11/12` | 0 mỗi lượt | 41/46/52/56/56 ca; actual A+B context/outbox/inbox/role/source/open. Lượt11/12 source hashes trước/sau giữ nguyên. |
| `… unified_parallel_b_verify.py tests 13` | 1 | 56 passed/1 failed: process helper thiếu `packages/synthetic/src`, chưa import identities; sửa bootstrap path, không thay consumer/assertions. |
| `… unified_parallel_b_verify.py tests 14` | 0 | **57 passed**,20.53s; actual A business outbox qua hai process B mới: delivery1 rồi0, inbox/readback đúng. XML/log/command/hashes tại `pytest-14/`. |
| `… unified_parallel_b_frontend.py prepare/build 01/02/03/04` | 0 mỗi lượt | Fresh snapshots, không build apps/web đang phục vụ; guard nguyên byte. Snapshot04 là UI B cuối. |
| `… unified_parallel_b_frontend.py typecheck 01/02/04` | 0 mỗi lượt | `tsc --noEmit --incremental false` trên snapshot riêng; Next build cũng kiểm TypeScript. |
| Ruff `--select E9,F --no-cache` trên source/tests/scripts B | 0 cuối | `lint-final-01.json`. Ba unused imports/variable trong script/test B đã sửa; không đổi policy/assertions. |
| `… unified_parallel_b_verify.py audit 01`; `… unified_parallel_b_finalize.py 01/02/03` | 0 | Read-only retained DB digests, exact owned file hashes/preimage diffs, Git preservation, guard và matching ack. |

Kết quả latest unique lấy theo `(classname,name)` trong XML, không cộng rerun:57 ca cuối. Test warning `asyncio_mode` do disable plugin autoload trong harness sync; không phải product success claim. Hai process độc lập được kiểm trên business fixture riêng của B và trên chính A+B composition. Injected crash trước ack, retry bounds/concurrent workers được kiểm riêng; không tuyên bố distributed/cross-store atomicity hoặc recovery production.

Reproduce trên fixture mới: `.venv/Scripts/python.exe -B scripts/unified_parallel_b_verify.py tests 15` (dùng attempt chưa tồn tại;15–20 được chuẩn bị). Mở `pytest-14/command.json`, `results.xml`, `pytest.log` và `basetemp/test_actual_A_business_outbox_0/unified-process-1.json`/`unified-process-2.json` để đọc recovery evidence hiện có. Worker fixture command chính xác được giữ trong hai process records; không chạy helper vào retained/serving DB. Mọi API đọc có `Cache-Control: no-store`.

B chỉ ghi32 source/schema/test/script paths mới/sửa đã liệt kê trong manifest, cộng báo cáo này; hai file có sẵn đã có preimages. Không sửa master backlog hoặc shared wiring do A sở hữu. Mọi retained DB chỉ mode=ro; init/drift/corruption/restart chỉ trên fixture riêng. Bốn retained DB không đổi mọi bảng/hàng; pre-existing Git entries không mất. AGENTS, package/lockfiles và build guards giữ hash dispatch. Guard SHA256 `8f0886295da2214205cf257dd9e1d9476993ed1a7fb0ac67434909fa4af2eae6`.

Không delete/cleanup/reset/discard, physical erasure, thay protection/budget/thresholds, gọi paid provider/production/remote messaging, commit/push/deploy hoặc restart/reload serving runtime. Không quan sát runtime mới; build/source không được coi là đang phục vụ. Giữ tất cả failure logs, DB fixtures, snapshots và builds. Không component/DOM/browser/Playwright/E2E/visual/mobile tests.

Handoff immutable: `stream-b/handoffs/uni039-01.json`, `uni040-01.json`, `uni041-01.json`, `uni042-01.json`, `final-01.json`. Source B giữ ổn định sau final; repair phải có revision mới. C cần final snapshot tích hợp sau handoff A/B để kết luận tổng. Các giới hạn còn lại: temporary chat actual mode, main model writer memory, official deadline/rules, distributed recovery, UI/mobile/usefulness/institutional/production/full acceptance.
