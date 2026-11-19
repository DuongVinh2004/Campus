# Chặng09 — source UNI-011–015

Nhóm UNI-011–015 đã **implemented ở source local/synthetic**, chưa verified toàn bộ acceptance. Bắt đầu trong namespace bằng chứng `unified-ai-20261014-09` và tiếp tục sang 15/10/2026 (Asia/Bangkok). Next coding task là **UNI-016**; không triển khai task đó trong phiên này. UNI-003–015 vẫn nằm trong pending verification. Không mở thêm chat hoặc coding subagent.

## Source đã triển khai

| Task | Thay đổi |
| --- | --- |
| UNI-011 | `UnifiedAssistantProvider` dùng chung state/history/context giữa ChatPage, hội thoại/panel sinh viên, surface hồ sơ/field và khung cán bộ. Tái sử dụng SSE/history decoder, ChatPanel, CitationDrawer và AccessibleDialog hiện có. Client kiểm lại danh tính server; state soạn giữ riêng theo API/mode/tenant/actor/role trong phiên. Đổi route bỏ tham chiếu context cũ. DTO `surface:resolve` chỉ nhận enum surface, resource ID/version và field allowlist; server kiểm actor/tenant/role/owner/queue/version. Không đọc DOM, gửi draft chưa lưu, staff notes hoặc memory. API lỗi giữ error; adapter API không rơi về guidance demo. |
| UNI-012 | Catalog thuộc actor, cursor ràng buộc owner/filter, tìm theo tiêu đề, metadata rename/pin/archive qua preview/confirm/CAS/idempotency/receipt. Metadata là overlay trong actor state, không sửa transcript held. Native SQLite có stable create/turn client IDs, hash intent trước minimization, receipt pending/interrupted/completed. Final assistant và completed receipt commit trong cùng transaction; retry không tạo lại generation. Retention trả trạng thái rõ và giữ dữ liệu nguồn. Storage lỗi không trả danh sách rỗng thành công. |
| UNI-013 | UI dùng API catalog thật cho new/select/search/rename/pin/archive; sidebar và accessible drawer. Restore từng trang với nút đọc tiếp, chặn tiếp tục khi chưa đọc hết; giữ composer, citations và phiên cũ khi lỗi. New chỉ tạo phiên mới, không xóa chat cũ. Trạng thái local/pending/saved/error/interrupted cùng receipt/readback hiện rõ. Reuse endpoint clarification resume có version/CAS. Capability chưa có thì thông báo và chặn consumer. |
| UNI-014 | Renderer chung tận dụng Markdown/GFM và component cũ. Hỗ trợ steps/table/status/read-only proposal và navigation theo schema, route/audience allowlist. UI không suy CTA từ prose; raw markup bị bỏ, image không tự tải. SSE/citation final validation giữ nguyên; text legacy vẫn đọc được với trạng thái chưa xác nhận. Năm schema mới xuất theo Pydantic, có kiểm exact schema và cross-field/authority. |
| UNI-015 | Settings tài khoản và override chat có preview, xác nhận rõ, receipt và readback; giữ nội dung khi network/CAS lỗi. Consent history/personalization/quality tách riêng và yêu cầu suffix `.assistant-features.v1`; declaration cũ không tự bật consumer. Grant management thuộc actor có resource/version/scope, expiry, use count/last-used, locked reason và preview revoke. UI gọi consumer read/source projection với operation ID ổn định; quyền read/prepare không cấp business write. Memory/tools/templates, staff model và proxy preference consumer chưa có được nêu rõ. |

Form, submit/preview/confirmation và staff workflow có trước được giữ. Field help ở hồ sơ server dùng ID/version; biểu mẫu legacy chỉ có draft local thì báo cần tham chiếu server, không đưa toàn bộ dữ liệu biểu mẫu vào context. Projection hồ sơ có nguồn/phiên bản và chỉ giữ trong phiên, được ghi rõ là chưa lưu vào transcript model. Chuẩn bị nháp vẫn cần proposal/workflow evidence ở consumer hồ sơ; settings không tự sửa hoặc gửi nghiệp vụ.

## Bằng chứng backend và build

Tất cả commands dưới đây chạy từ `C:\Users\Duong Vinh\Vinh`, dùng `.venv/Scripts/python.exe -B`. Fixtures/output được tạo mới và giữ lại. Không component/DOM tests, browser, Playwright/E2E hoặc visual QA.

| Command/nhóm command | Exit | Kết quả/bằng chứng |
| --- | --- | --- |
| `scripts/prepare_unified_ai_session09.py` và `scripts/preserve_unified09_extra.py` | 0, 0 | 42 preimages, bốn snapshot DB consistent; `preflight.json`, `extra-preimages.json`. |
| Probe `-c "import asyncio; asyncio.run(asyncio.sleep(0)); print('asyncio ready')"` trong sandbox | 1 sau dừng probe riêng | Probe không tiến triển ở socketpair asyncio; chỉ process do phiên này tạo bị ngắt. Sau đó dùng escalation cho local synthetic test runner, không đổi network/security controls. |
| `scripts/prepare_unified09_contracts.py` | 0 | Năm schema mới; `contracts-01.json`, `contracts/json-schema/assistance/unified-consumers-v1/`. |
| `scripts/verify_unified_ai_session09.py tests 01` | 1 | 542 passed/5 failed, 133.44s. Log/JUnit và `test-command-01.json` giữ nguyên. |
| `scripts/verify_unified_ai_session09.py tests 06` | 1 | 559 passed/1 failed, 136.55s. Log/JUnit và `test-command-06.json` giữ nguyên. |
| `scripts/verify_unified_ai_session09.py tests 07` | 0 | 44 affected backend/contract cases passed, 11.88s; `backend-tests-07.xml/log`, `test-command-07.json`. |
| `scripts/prepare_unified_ai_frontend09.py prepare NN` cho 01–05 | 0 từng lần | Mỗi attempt có snapshot mới, không dùng lại build output. |
| `scripts/prepare_unified_ai_frontend09.py build NN` cho 01/02/03 | 0 từng lần | TypeScript/production build đạt; giữ cả ba snapshot/logs. |
| `scripts/prepare_unified_ai_frontend09.py build 04` | 1 | TypeScript phát hiện narrowing của optional resource bên trong callback (`TS18048`); log giữ nguyên. |
| `scripts/prepare_unified_ai_frontend09.py build 05` | 0 | Capture resource ref vào const trước callback; không đổi guard/expected. Final TypeScript/production build đạt, BUILD_ID **SFayfTmpqc6SjBbbNBR4B**; `frontend-build-05.json`. |
| `scripts/read_unified09_host.py` với escalation chỉ đọc | 0 | `host-runtime-read-01.json`; GET health/runtime và netstat, không auth/model/business dispatch. |
| `scripts/verify_unified_ai_session09.py audit 01/02/03` | 0 từng lần | Digest mọi bảng/hàng của bốn DB giữ lại không đổi; paid/native counters không đổi. 01 giữ tình trạng test còn lỗi; 02/03 ghi kết quả latest outcomes. |
| `scripts/verify_unified09_scope.py 01` | 1 | Bảy Ruff findings ở file preimage không thay đổi: candidate helper, definitions, app bootstrap và privacy_notice. Giữ kết quả rộng, không sửa code ngoài phạm vi. |
| `scripts/verify_unified09_scope.py 02` | 0 | Scoped lint trên file thật sự thay đổi/mới, scoped diff check, git status/name-only và guard bytes; `scope-verification-02.json` giữ exact commands/stdout/stderr. Các file có findings trước được chứng minh nguyên hash preimage. |

Tổng **560 ca backend/hợp đồng duy nhất đạt**, lấy kết quả mới nhất theo `(classname,name)` từ reports 01/06/07. Không cộng 542+559+44 và không cộng các phiên lịch sử. Trong đó có 44 ca mới của nhóm consumer/display contracts; bộ cũ cũng được chạy trong các lượt gộp.

Bốn lỗi lượt01 do endpoint truy cập `Request.app` khi gọi trực tiếp với Request tối giản. Sửa lấy optional app từ ASGI scope, giữ behavior disconnect/cancellation và expected không persist partial answer. Fixture grant management ban đầu dùng session grant rồi tạo login mới, nên lock là đúng; đổi fixture kiểm active management sang timed và thêm ca riêng xác nhận session change bị khóa. Lượt06 phát hiện assertion mới viết dùng authority `none`, trong khi contract ActiveGrant đã có `read_or_prepare_only`; sửa expectation/TypeScript theo contract hiện có, không cấp write hoặc hạ business guard. Tập bị ảnh hưởng sau đó đạt toàn bộ.

Các static checks hẹp từng chạy đạt trước audit rộng. `scope-verification-01.json` giữ bảy findings ngoài phần source thay đổi, không tuyên bố toàn repo lint sạch. Scoped check cuối đạt; không sửa blank EOF có trước trong globals.css hoặc các dirty/deleted files khác.

## Bảo toàn và runtime

Audit đối chiếu toàn bộ bảng/hàng của business candidate, actor state, conversations và agent-runs với snapshot consistent trước phiên: đều không đổi. Preimages xác minh lại hash; scoped diff giữ trong `source-changes-03.patch`. Git status cuối giữ các pre-existing entries, bao gồm dirty/staged/untracked/deleted state. Không cleanup, delete/reset/discard, commit/push/deploy, live DB initialization/migration hoặc thay safety control.

Sandbox preflight trả URLError và không thấy listener; đó là giới hạn quan sát, không phải chứng cứ runtime đã tắt. Probe host chỉ đọc cuối quan sát **unified-local-v5 tại8006**, frontend3006 **d7WLzedC5Vjq3fb11xvgM**, writer8003 và các native listener có trước. Giá trị runtime/health trùng record cuối chặng08. Phiên này không restart/stop/reload/handoff runtime; build v9 mới không được phục vụ thay build cũ. Preservation guard trong các snapshot giữ nguyên byte và SHA256. Bản build04 lỗi cũng được giữ lại.

## Giới hạn và phần chưa verified

- Chưa chạy UI/browser/human usefulness, keyboard/mobile/dark, cross-device/tab/account-switch/offline UX, load/p95/throughput hoặc production acceptance. TypeScript/build không chứng minh các tiêu chí đó.
- Proxy retained writer chưa tiêu dùng settings mới hoặc native stable create/turn receipts. API/UI khai báo đúng capability; yêu cầu stable ID gửi trực tiếp qua proxy bị từ chối. Source native có receipt consumer, không có quyền tự nạp nó vào runtime hiện hữu.
- Staff/admin model chat chưa có transcript/channel metadata và consumer phù hợp; history/model chat fail closed. Staff resource context tiếp tục kiểm ACL/queue/assignment hiện tại. Không nối staff notes/private draft sang model context.
- Context projection exchanges chỉ giữ trong phiên; refresh transcript không biến chúng thành lịch sử model đã lưu. Pending/interrupted native receipts giữ sự bất định, không tự regenerate. Legacy proxy chưa có receipt nên đọc lại lịch sử hoặc mở chat mới là bước rõ ràng.
- Metadata actor state và held transcript là hai store; archive chặn lượt bắt đầu sau readback, không tuyên bố transaction nguyên tử xuyên hai DB hay hủy generation đã bắt đầu. Catalog title search chưa được đo ở volume lớn.
- Legacy text/citations/receipt ở storage được giữ; citation không có final metadata hợp lệ không được nâng thành nguồn verified trong UI. Real legacy ownership vẫn cần evidence server như chặng08.
- Quality consent không bật training. Memory/tools/templates chưa có consumer trong trung tâm. Prepare-draft cần schema proposal/workflow và business xác nhận riêng; không có business write từ grant này.

Backlog cập nhật implemented cho UNI-011–015 và `next_task=UNI-016`, giữ full acceptance pending cho UNI-003–015. Báo cáo chặng08 và record trước được bảo toàn.
