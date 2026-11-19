# Chặng11 — source UNI-021–025

Nhóm UNI-021–025 đã **implemented trong source local/synthetic**, chưa verified toàn bộ acceptance. Ngày 15/10/2026, Asia/Bangkok. **647 ca backend/hợp đồng duy nhất đạt** theo kết quả mới nhất; TypeScript và production build đạt. Next coding task **UNI-026**, vẫn planned và không triển khai trong phiên này. UNI-003–025 giữ pending verification. Không coding subagent hoặc chat mới.

## Hành vi và consumer

| Task | Source implemented | Giới hạn còn lại |
| --- | --- | --- |
| UNI-021 | Shared `understand_student_goal` trả `IntentProposal`: mục đích, workflow, trường thiếu, ràng buộc và nguồn dữ liệu. `StudentGoal` chỉ nhận explicit statements thuộc allowlist; đọc trường đã lưu qua actor/resource/version. Mục đích nhiều nghĩa yêu cầu làm rõ; đổi workflow không ghi đè hồ sơ đang chọn. Nhánh multi-agent certificate dùng cùng helper. | Nhận diện từ vựng bảo thủ; không có general natural-language extraction hoặc suy diễn dữ liệu cá nhân. Constraints được giữ để xem xét, không tự biến thành quy tắc nghiệp vụ. |
| UNI-022 | `StudentPreparationService` nối resources/workflow/proposal services hiện có. Liệt kê tất cả nháp thuộc chủ thể và yêu cầu chọn đúng hồ sơ; dùng diff của trường đã lưu, workflow package và typed proposal khi nguồn synthetic hợp lệ. Prepare không ghi. Save riêng cần reviewed + exact preparation hash; existing certificate/service transaction kiểm nguồn/mẫu/profile/version và ghi draft/provenance/receipt cùng transaction. Retry dùng cùng operation id, không tạo nháp lặp. | Public certificate source thiếu official effective dates không bị gắn ngày synthetic; dùng workflow package/diff và giữ hạn chế nguồn. Không đăng ký model business-write tool. |
| UNI-023 | Certificate/Service workspaces có trợ giúp theo resource ref đã lưu, lỗi theo trường và liên kết nhóm lỗi; giữ nội dung khi lỗi. UI source và server schema kiểm tên tệp TXT, giới hạn UTF-8 bytes, empty/null; UI dùng UTF-8 decoder strict. VinUni giữ nháp cục bộ và dẫn đến biểu mẫu có server consumer. | OCR chưa cấu hình và được công bố unavailable; không xác thực giấy tờ. Không kiểm UI focus, file picker, mobile hoặc keyboard bằng browser. |
| UNI-024 | Preview/confirm có binding actor/tenant/session/target/version/queue/rule/template/base form; revalidate profile, payload và source effectivity trước gửi. Giữ signed token, expiry, idempotency và audit trong business service hiện có. UI source chỉ bỏ preview sau readback thành công. | Synthetic transaction/replay evidence; không crash drill trên DB giữ lại, không cross-store atomicity hoặc production acceptance. |
| UNI-025 | Shared assistant runtime giữ preparation theo actor/chat qua route. Action inventory được UI consume, ghi rõ hỗ trợ/manual/confirmation/unavailable và bước tiếp theo. Unified schedule/rooms không dùng legacy synthetic-success view; legacy forms chặn submit khi writer chưa nối. Source có responsive wrapping, field labels và error anchors. | Lịch cá nhân, đặt phòng, chat-to-ticket handover chưa có business consumer mới. Mobile/accessibility/usefulness chưa nghiệm thu. Native thiếu business composition công bố unavailable và prepare trả503. |

API mới: `POST /v1/assistant/student:prepare`, `POST /v1/assistant/student:save-draft`, `GET /v1/assistant/student-actions`. Composition công bố `student_preparation`, `student_draft_writer` và `student_ocr` riêng. DTO/schema xuất tại `contracts/json-schema/assistance/student-v1-01/`; exact schema equality được kiểm. Không đổi SurfaceBody schema hiện có.

Save nháp là thao tác trực tiếp sau khi người dùng xem thay đổi; gửi nghiệp vụ tiếp tục qua preview/confirm riêng. Existing settings/grants không được biến thành quyền gửi. Context lấy từ server resource refs đã authorize, không đọc DOM hoặc form chưa lưu. Provenance lưu explicit statements và bản hồ sơ tương ứng; defaults hiển thị để review không được coi là thông tin chính thức.

## Kiểm tra và lỗi đã giữ

Commands từ `C:\Users\Duong Vinh\Vinh`, Python `.venv/Scripts/python.exe -B`. Namespace mới `infra/local/unified-ai-20261015-11`. Không component/DOM/UI test, browser, Playwright/E2E hoặc visual QA.

| Command | Exit | Kết quả/evidence |
| --- | --- | --- |
| `scripts/prepare_unified_ai_session11.py` | 0 | `preflight.json`: 61 preimages, 4 consistent read-only DB snapshots, Git status/runtime/paid/native inventory. |
| `scripts/preserve_unified11_extra.py` | 0 | 2 preimages bổ sung cho schedule/rooms; tổng63 records. |
| `scripts/prepare_unified11_contracts.py` | 0 | Hai schema mới, `contracts-01.json`. |
| `scripts/verify_unified_ai_session11.py tests 01` | 1, interrupted | Sandbox TestClient/anyio setup bị treo, chưa có assertion result; dừng đúng exec session của lượt thử này. Giữ log/basetemp; không tính vào tổng ca. |
| `scripts/verify_unified_ai_session11.py tests 02` | 1 | 639 passed/2 failed, 174.67s, tổng641. |
| `scripts/verify_unified_ai_session11.py tests 03` | 1 | 645 passed/1 failed, 170.58s, tổng646. |
| `scripts/verify_unified_ai_session11.py tests 04` | 0 | 205 affected cases passed, 68.22s; gồm backend cuối, native unavailable và deadline fixture không đổi. |
| `scripts/prepare_unified_ai_frontend11.py prepare 01/02` | 0 mỗi command | Hai fresh source snapshots, giữ mọi build cũ. |
| `scripts/prepare_unified_ai_frontend11.py build 01/02` | 0 mỗi command | TypeScript và Next production build đạt; final02 BUILD_ID **1LtL1mfpy5AGl_UWEM7T9**. Snapshot01 **8a6tfPeyFhWpTKeEpZMH-** cũng được giữ. |
| `scripts/verify_unified_ai_session11.py host 01` | 0 | Read-only GET/netstat; current endpoints không quan sát được, không transition. |
| `scripts/verify_unified_ai_session11.py audit 01/02/03` | 0 mỗi command | Giữ failure state01; final latest test outcomes, scoped source diff, all-table/row DB preservation và paid/native metadata. |
| `scripts/verify_unified11_scope.py 01/02/03` | 0 mỗi command | Preimages, exact diff/Git status, new Ruff E9/F findings, guard bytes và build IDs. Không mất pre-existing Git entry, không thêm lint finding. |

Tổng647 dựa latest `(classname,name)` trong XML02–04, không cộng reruns hoặc608 ca chặng10. Kiểm mới gồm actor/role/session isolation, malformed authority input, chọn nháp, manual-edit/CAS conflict, goal change, source/profile drift, service/certificate save/replay, concurrent same operation, restart/readback fixture, attachment boundaries, exact confirm binding và capability absence. Backend chạy local synthetic với escalation để TestClient dùng local sockets; không gọi model/provider.

Hai lỗi02: vocabulary chưa nhận câu rõ nghĩa “Cần cán bộ hỗ trợ”; retry đồng thời đọc shared receipt bằng reader sai bảng certificate/service. Sửa vocabulary và dispatch reader theo `resource_kind` trong receipt, đóng transaction trước readback; giữ nguyên assertions. Lượt03 lỗi ở fixture có sẵn `test_deadline_and_token_reservation_stop_before_new_effect`, deadline50ms: reservation durable đã ghi nhưng fake provider chưa bắt đầu (`model_calls=1`, `len(model.calls)=0`). Fixture đạt ở04 mà không đổi ngưỡng/assertion hoặc orchestration source. Điều này ghi nhận tính nhạy scheduling; một lượt rerun đạt không chứng minh đã loại bỏ flakiness. Logs lỗi02/03 giữ nguyên.

## Bảo toàn và runtime

63 source preimages được kiểm hash. Audit mọi bảng/hàng của bốn DB giữ lại đều không đổi: `unified-ai-20261014-01/business-candidate01.sqlite3`, `unified-ai-20261014-05/actor-state.sqlite3`, `public-rag-20261013/conversations.sqlite3`, `multi-agent-integrated-20261013-01/agent-runs.sqlite3` dưới `infra/local/`. DB nguồn chỉ mở mode=ro để snapshot/digest; fixture init và corruption tests chỉ dùng DB mới của phiên này. Paid/native metadata không đổi; provider dispatch của phiên này **0**.

`source-changes-03.patch` so với preimages và `scope-verification-03.json` giữ danh mục source edits/new files, Git status/diff và hashes. Pre-existing dirty/untracked/ignored/deleted work được giữ. Không delete/reset/clean/discard, commit/push/deploy, retained DB migration, sửa safety/hook/backup/recovery control hoặc stop/restart/reload runtime của người dùng.

Build preservation guard giữ nguyên byte, SHA256 **8f0886295da2214205cf257dd9e1d9476993ed1a7fb0ac67434909fa4af2eae6**. Các snapshot/build/log/failure/fixture giữ nguyên, không cleanup.

Current GET8006/8003 trả URLError và listener inventory rỗng, cả host observation01. **Không xác minh được runtime hiện tại**; v5/build d7WLzedC5Vjq3fb11xvgM chỉ là quan sát lịch sử ở chặng10. Source candidate **unified-local-v11** và build mới chưa được nạp bằng phiên này; không suy ra runtime đang tắt hay dữ liệu bị mất từ giới hạn quan sát.

## Chưa nghiệm thu

- UI/mobile/keyboard/dark/accessibility, device/offline/account-switch UX và human usefulness theo yêu cầu được để sau; build không chứng minh các tiêu chí này.
- Official rules/effective dates/templates, institutional eligibility, production/load/p95/throughput chưa verified; không bật business capability chỉ vì có endpoint legacy.
- General extraction, OCR, personal schedule, room booking và chat handover chưa được tạo consumer trong batch này. Không tuyên bố đã hoàn thành toàn bộ student automation.
- Source/new native composition chưa handoff vào retained runtime. Cross-store atomicity và distributed business recovery không nằm trong bằng chứng này.

Backlog cập nhật implemented riêng UNI-021–025, pending verification UNI-003–025 và next_task **UNI-026**. Record chặng10 được giữ; UNI-026 không triển khai.
