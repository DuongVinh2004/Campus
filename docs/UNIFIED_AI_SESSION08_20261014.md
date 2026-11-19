# Chặng08 — triển khai gộp UNI-007–010

UNI-007, UNI-008, UNI-009 và UNI-010 đã **implemented ở source local/synthetic**, tái sử dụng contracts, preview/confirmation, SQLite actor state, CAS, immutable revisions, receipts, workflow evidence và ACL từ UNI-004–006. Chưa đánh dấu verified toàn bộ acceptance. Next coding task: UNI-011. Không chạy test giao diện và không thay runtime hiện có.

## Phần đã triển khai

| Task | Code và hành vi |
| --- | --- |
| UNI-007 | `LegacyImportService` đọc snapshot student-chat v1/v2, kiểm JSON/size/IDs, bắt buộc bằng chứng owner/tenant/hash do server cấu hình, preview/confirm, lưu nguyên văn nguồn cùng provenance/classification và receipt. Dedup theo nội dung JSON giữ bản đầu, kể cả khác khoảng trắng. Unknown owner bị từ chối. Export trả đúng nguồn ban đầu; proposal/link/action legacy không được đưa vào model, thực thi hoặc lịch sử RAG. Adapter browser chỉ đọc khóa cụ thể, không sửa localStorage. |
| UNI-008 | `ScopedContextService` chỉ ghép cùng chat sinh viên và/hoặc tài nguyên được grant đúng phiên bản; cán bộ nhận projection tài nguyên qua ACL/queue hiện hành. Kiểm mốc message, retention, nguồn, audience, source hash; content tối đa12KB, manifest có hash/expiry và recompose mỗi lần dùng. Lịch sử tối đa5lượt, opt-in riêng; không ghép private memory, notes cán bộ, import legacy, token hoặc field chưa lưu. Budget thất bại không tiêu dùng grant một lần. |
| UNI-009 | `AssistantPreferenceService` lưu locale, reply style, verbosity, format, tên/xưng hô và custom instructions; override cùng chat, preview/confirm/CAS, readback/receipt và history consent có phân trang. Personalization/history/quality là ba mục đích tách biệt. Notice mới có suffix `.assistant-features.v1`; declaration-only consent cũ không tự bật consumer. Main factory đọc lại consent/settings trước grounded generation, giữ custom instructions ở untrusted data block dưới policy/schema/evidence. |
| UNI-010 | `AssistantGrantService` tách active grant khỏi request cũ. Bind actor/tenant/role/units/session khi phù hợp, resource ID/version và source evidence. Có once/session/timed, revoke, CAS, atomic use/revision/receipt và replay theo operation+intent. Consumer context, đọc trường hồ sơ riêng tối thiểu và chuẩn bị proposal/evidence candidate đều kiểm lại mỗi lần. Không ghi business, gửi hoặc duyệt. Token grant/state bị từ chối khi dùng làm confirmation nghiệp vụ. |

Namespace mới: `assistant_preferences`, `chat_preferences`, `legacy_import`, `active_grant`. Giữ model/namespace cũ để đọc payload và receipt có trước; physical actor schema vẫn version1. `SQLiteActorStateStore.commit` thêm guard trong cùng write lock và receipt readback kiểm immutable revision. Không migrate actor/history/run/business gốc.

HTTP mới nằm dưới `/v1/assistant`: preferences/chat preferences, consent notice/preview/history, legacy import preview/confirm/export, grants preview/confirm/read/revoke-preview, receipt, context compose/revalidate, resources:read và proposals:prepare. Body strict không nhận owner/tenant/role từ browser; xác nhận phải là boolean true. `assistant-state-service.ts` cung cấp typed client và browser export chỉ đọc. UI settings/import/grant controls vẫn thuộc consumer tasks sau.

## Bằng chứng kiểm tra

- Backend gộp: `scripts/verify_unified_ai_session08.py tests 06`, exit0, **515 passed /116.93s**. Sau rà soát notice, tập bị ảnh hưởng `tests 07`, exit0, **107 passed /32.40s**, gồm một ca mới. Tổng lấy kết quả mới nhất theo classname/name: **516 ca duy nhất**, không cộng reruns.
- Test mới kiểm restart/readback, actor/tenant/role/queue/session, consent withdrawal/notice change, chat override/CAS, unknown legacy owner/provenance/export/dedup, one-time concurrent use, revoke/use race, exact retry intent, cached context/source freshness, transfer cán bộ, minimal read/candidate preparation, rollback receipt và budget, đồng thời từ chối dùng read grant để confirm ghi nghiệp vụ.
- TypeScript và Next production build trên snapshot mới đạt; kết quả cuối trong `frontend-build-02.json`. Giữ preservation guard có trước nguyên byte. Bản build mới chưa phục vụ thay bản live. Không component/browser/E2E/mobile test.
- Python static checks `ruff --select E9,F --no-cache` trên file mới đạt. Scoped `git diff --check` đạt; toàn repo vẫn có finding có trước ở `apps/web/src/app/globals.css:945` (blank EOF), không sửa ngoài phạm vi.
- Audit bốn DB retained so consistent snapshots: mọi bảng/hàng/hash business/actor/history/runs không đổi; paid/native counters không đổi. Preimages, logs/JUnit, commands, builds và scoped diff giữ trong `infra/local/unified-ai-20261014-08/`.

Giữ cả bằng chứng lỗi: lượt04 đạt507/508 vì fixture gọi assign thiếu target thay vì claim; sửa fixture theo API hiện có. Lượt05 đạt104/105 vì so DTO đã chuẩn hóa (có `evidence:null`) với dict chưa chuẩn hóa; sửa so sánh theo contract, không đổi expected nghiệp vụ. Lượt01/02 và diagnostic03 bị dừng ở socketpair nội bộ asyncio do sandbox trước khi chạy ứng dụng; log stack được giữ. Lượt04 trở đi chạy ngoài sandbox với fixture/output mới để local asyncio hoạt động; không đổi runtime hoặc safety control.

## Phần chưa verified và giới hạn

Không có kiểm giao diện thực, relogin/device/tab/offline UX, human baseline/usefulness, paid/live model behavior hoặc load/p95/throughput mới. Không coi synthetic pass là nghiệm thu thực tế.

Chưa có bằng chứng owner cho dữ liệu legacy thật; cấu hình mặc định không tự gắn account hiện tại cho dữ liệu trên thiết bị. Import là collection bảo toàn riêng, không chuyển đáp án cũ thành citation hoặc transcript đáng tin. Không xóa/overwrite dữ liệu nguồn.

Staff chat và future task references chưa có metadata/consumer phù hợp nên fail closed. Resource staff context dùng ACL hiện có; draft/notes riêng không đi vào context. Preferences chỉ có consumer trong main factory; candidate giữ proxy tới writer8003 nên runtime writer hiện hữu chưa đọc settings/grant mới. Không có quyền từ config/code để tự restart, reload hoặc thay nguồn runtime đang chạy.

Grant là quyền bổ sung chỉ cho read/prepare trong consumer mới; source readers/cache/run resume cũ tiếp tục dùng server scope và revalidation đã có. Business executor giữ ACL/preview/confirmation/version/idempotency riêng. Atomicity của grant use nằm trong actor SQLite; resource/source từ business store là quan sát được kiểm lại, không phải transaction nguyên tử xuyên hai DB. Không dùng grant này để cấp write hoặc tuyên bố đã thực thi business action.

Trạng thái runtime và bảo toàn cuối được ghi bằng read-only audit trong `session-verification-02.json`. Phiên không restart/reload/stop runtime của người dùng, dispatch paid model, commit/push/deploy, sửa safety controls hoặc cleanup dữ liệu. Các test processes do phiên này tạo khi bị sandbox chặn được dừng riêng; mọi fixture/output giữ lại.
