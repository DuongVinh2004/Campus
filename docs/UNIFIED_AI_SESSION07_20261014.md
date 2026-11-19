# Chặng07 — hoàn thiện code storage và nháp cán bộ

UNI-006 đã **implemented** ở source local/synthetic. Bộ kiểm tra backend gộp đạt **457 test**; các kiểm tra ảnh hưởng sau sửa lint cũng đạt. Có **12 component tests** chạy trước chỉ đạo mới và một build production/TypeScript thành công. Theo yêu cầu trực tiếp ưu tiên code, **chưa test browser/giao diện**; full acceptance vẫn pending. Next coding task là UNI-007. Không coi đây là hoàn thành toàn bộ50task hoặc nghiệm thu usefulness.

## Code hoàn thiện

- Main factory có explicit `ACTOR_STATE_STORAGE_MODE` và `AGENT_RUN_STORAGE_MODE`; file cấu hình phải được khởi tạo, lỗi không fallback sang memory. Feedback, yêu cầu riêng tư và token-hash revocation dùng typed actor storage và atomic state/revision/receipt. Auth và logout dùng cùng SessionService, revocation sống qua restart. Consent vẫn được chọn rõ bằng mode riêng.
- Feedback giữ comment riêng, binding tới immutable answer/source IDs; metadata model/prompt chưa biết trả `unknown`. Receipt có API readback kiểm lại owner/history. Privacy requests chỉ nhận yêu cầu, không tự export/delete. Retry với client UUIDv7 ổn định trả receipt cũ; đổi intent cùng ID bị409.
- Candidate source v7 đọc history qua adapter read-only, không initialize/migrate live DB và không gọi writer khi đọc message/ghi feedback. Projection giữ final status, citations và retention hiện hành. Run GET/resume vẫn qua writer để giữ source revalidation cũ.
- StaffDraftService lưu manual text, business version, workflow/source observation, actor/queue và draft version. Chỉ cán bộ đang phụ trách đúng tenant/role được đọc/ghi. Transfer chặn cán bộ cũ, giữ revision cũ và không đưa text của họ cho người nhận. Save chỉ báo thành công sau atomic receipt; CAS/replay tách draft version khỏi business version.
- StaffDraftEditor tích hợp service/certificate workspaces qua flag `NEXT_PUBLIC_UNIFIED_DURABLE_DRAFTS`. Autosave tuần tự, debounce, retry giữ nguyên intent/client ID, CAS giữ local text và cho đối chiếu server. Cached text chỉ hiện sau readback đúng actor/tenant. Chuyển vào ô phản hồi là thao tác riêng có reauthorization; chưa gửi, approve hoặc thay kiểm tra nghiệp vụ.
- Conversation/run tenant metadata chặn dùng chung DB trái tenant; không suy tenant cho dữ liệu legacy không rõ provenance. State payload/key/owner, timezone/version, run event sequence và task/cache JSON được kiểm đọc, không sửa dữ liệu lỗi để làm test đạt.

Settings/grant/proposal services của chặng06 được giữ: stored grants chỉ là request/expired/revoked, declarations không cấp quyền. Preferences chưa ảnh hưởng model pipeline; business executor vẫn giữ preview/confirmation/version/idempotency riêng. Nháp/proposal observation không phải transaction xuyên hai DB. Outcome/template/execution linking thuộc UNI-030/031; consumer permissions/personalization thuộc UNI-009/010/015; import legacy thuộc UNI-007.

## Kiểm tra và phạm vi bằng chứng

Command chính: `.venv/Scripts/python.exe -B scripts/verify_unified_ai_session07.py batch-tests`, exit0, **457 passed,101.20s**. `post-lint-tests`, exit0, kiểm lại tập ảnh hưởng sau chỉnh imports/lint. Sau chỉnh exception type nội bộ,3corrupt-run cases kiểm lại đạt, không cộng reruns vào457. Pytest tắt autoload/cache và mỗi lần dùng basetemp/JUnit/idempotency DB mới. Test dùng deterministic fixtures, không dispatch model; test nhiều process là hai subprocess storage thực cùng tranh CAS/resume, một commit/claim và một conflict.

Frontend component suite gồm StaffDraftEditor và hai workspaces,12tests đạt. Build dùng snapshot mới và preservation guard giữ nguyên byte-for-byte; TypeScript và Next production build đạt, build ID `ICdzNGE7r89XQ1ao7_BOz`. Build này chưa thay bản live. Không có browser/E2E/mobile hoặc human measurement mới.

`compatibility-retry`, exit0, dùng bốn clone mới: đọc513conversations/1310messages/497runs; mọi hàng/count/hash của bảng có trước giữ nguyên. Held reads không ghi schema. Rehearsal migration chỉ thêm `conversation_schema`/`agent_schema` trên clone; không gán tenant bằng suy đoán.

| Acceptance | Evidence local | Phần còn cần full verification |
| --- | --- | --- |
| AT-03 | Restart readback, owner/order/retention, missing store không trả empty success | Browser/device/relogin trên bản được chọn |
| AT-05 | Chat SSE/regression, immutable final/source projection, feedback binding | Browser interrupt/retry trên bản được chọn |
| AT-07 | Direct API tenant/owner/role/queue, history/source/cache/resume và actor-switch component checks | Browser isolation toàn bộ luồng |
| AT-28 | Hai process CAS/resume, lease/version và committed final result qua restart | Nạp writer source/migration với transition được kiểm |
| AT-33 | Private drafts restart, audit/receipt rollback, concurrent CAS và component retry/manual edits | Browser reload/concurrent tabs/network failure |
| AT-34 | Business action regression, transfer chặn old officer read/save và giữ drafts | Old proposal/executor consumer kiểm xuyên luồng UNI-031 |

Lỗi được giữ nguyên bằng chứng: lần backend02 có445pass/1fail do fixture cố dùng history đã bind tenant khác; sửa fixture chọn history riêng, giữ test từ chối cross-tenant. Lần frontend đầu dùng config path tương đối bị lỗi startup, sửa path tuyệt đối rồi12tests đạt. Rehearsal01 đặt kiểm anonymous sau demo-login nên client còn cookie; chuyển kiểm trước login và chạy trên clone02, không giảm expected401. Tất cả output/clone của lần lỗi được giữ.

Lint toàn phạm vi ban đầu báo81diagnostics, gồm lỗi pre-existing và import/style mới; các lỗi mới đã sửa bằng scoped patches và file Python mới full lint đạt. Final scope audit so baseline preimages của file có trước, không coi lint toàn repository là pass; không có lint diagnostics mới so baseline. `git diff --check` toàn repo còn finding có trước ở `apps/web/src/app/globals.css:945` (blank EOF), được giữ.

## Bản chạy và bảo toàn

Runtime đang phục vụ8006 vẫn **unified-local-v5**, frontend3006 vẫn build `d7WLzedC5Vjq3fb11xvgM`. Source v7/build mới được giữ để chạy phối hợp sau; không restart runtime của người dùng để làm kiểm tra giao diện. Writer8003/native không restart, không thêm paid Gateway, không migrate history/run gốc. Snapshot business/actor/history/runs và preimages được giữ trong namespace07; final audit kiểm lại ownership/runtime, row hashes và paid/native counters. Chưa bắt đầu human baseline, không commit/push/deploy hoặc cleanup dữ liệu.

Evidence: `infra/local/unified-ai-20261014-07/` chứa `preflight.json`, `extra-preflight-01.json`,26source preimages và một extra preimage, bốn consistent snapshots, `backend-tests-01..06.xml`, command/logs02..06, `frontend-tests-01.json`, `frontend-build-01.json`, các clone rehearsal01/02, `migration-compatibility-02.json`, `source-changes-01/02.patch` và `session-verification-01/02.json`. Scripts chỉ dùng output exclusive-create; không chạy lại vào path đã tồn tại.
