# Chặng12 — source UNI-026–030

Ngày 15/10/2026, Asia/Bangkok. UNI-026–030 **implemented trong source local/synthetic**, full acceptance còn pending. **684/685 ca backend/contracts duy nhất đạt** theo kết quả mới nhất; còn1 lỗi nền deadline/reservation50ms. Không có backend release gate xanh. TypeScript độc lập và production build đạt. Next coding task **UNI-031**, chưa triển khai. Không coding subagent hoặc chat mới; không UI/component/DOM/browser/Playwright/E2E/visual test.

## Phạm vi đã nối

- UNI-026: `staff-workspace.v1` phân biệt unchecked/checked/missing_source/error/conflicting. Luồng cán bộ công bố OCR, SLA và AI proposal chưa có consumer; không giả confidence hoặc xác minh con dấu. Hàng đợi legacy bỏ claims cố định, auto-tick và ngoại lệ thay mandatory checks. Nháp mẫu và bản in được nhận diện là tham khảo chưa có căn cứ chính thức.
- UNI-027: service/certificate workspaces consume cùng bộ hồ sơ purpose/facts/timeline/documents/findings/sources/next action, gồm bản chụp profile/học phần và thông tin sinh viên khai báo. Bản chụp học phần không được coi là eligibility hiện tại. Mỗi nguồn mở bằng resource/version/binding; backend tự chọn locator/rendition đã kiểm, không nhận đường dẫn tùy ý. Cache/reviews riêng trong business operations table, không vào public record projection.
- UNI-028: deterministic declarations/source/profile checks khác explicit officer review. Readiness ready/needs_verification/missing/waiting/blocked có lý do; source lỗi không tự tạo rejection. Workflow/criteria/source hashes được bind; đề xuất AI unavailable. Readiness chỉ là trạng thái đối chiếu nội bộ, action_authority=none; các business endpoints tiếp tục giữ quy trình/thẩm quyền riêng.
- UNI-029: chuẩn bị đồng bộ, bounded, không cần worker/outbox hay provider. Cache/reviews/append-only review receipts có checksum dùng cùng business transaction; receipt giữ actor/time/note/dependency. Hash dependency chọn findings cần kiểm lại, giữ phần khác khi binding còn hợp lệ. Diff bổ sung trước/sau được giữ; profile/học phần/source/assignment/version drift chặn sử dụng kết quả cũ. Giới hạn 2s xử lý sau khi lấy lock, SQLite lock timeout hiện có, tối đa24 tiêu chí/200 timeline/50 supplements/3 tài liệu; không retry/provider cost tự động. Đây là kiểm tra deadline sau chuẩn bị và trước commit cache, không phải hard cancellation của từng thao tác file/SQLite bên dưới.
- UNI-030: private server autosave/CAS/receipt/readback hiện có được tăng binding payload/profile/criteria; legacy draft bytes vẫn đọc được và báo binding stale, không rewrite. Business lock bao quanh kiểm quyền và draft commit, session revocation được kiểm lại dưới lock của đúng business DB. Claim/transfer/respond và certificate actions revalidate session trong transaction; transfer làm old officer pending action thất quyền. UI giữ pending intent, text và conflict, chỉ dùng nháp sau saved/readback đúng bản; local hook giữ buffer theo account/record khi đổi context.

Endpoints mới: `POST /v1/assistant/staff-workspace/read`, `/review`, `/source`. Bốn exact schema trong `contracts/json-schema/assistance/staff-v1-01/`. Composition có business consumer công bố capability riêng; native composition thiếu consumer trả503 với bước đối chiếu thủ công, không giả success.

## Kiểm tra

Commands từ workspace, Python `.venv/Scripts/python.exe -B`; evidence mới `infra/local/unified-ai-20261015-12`. Backend dùng local TestClient sockets với escalation trên fixture mới; không gọi provider thật.

| Command | Exit | Kết quả/evidence |
| --- | --- | --- |
| `scripts/prepare_unified_ai_session12.py` | 0 | `preflight.json`:72 preimages,4 consistent read-only snapshots, Git/host/paid/native inventory. |
| `scripts/preserve_unified12_extra.py` | 0 | Thêm1 record preimage capability projection; đây là bản sao bổ sung của1 path đã có trong preflight. Tổng73 preimage records/72 paths. |
| `scripts/prepare_unified12_contracts.py` | 0 | Bốn exact model schemas, `contracts-01.json`; equality được kiểm trong backend. |
| `scripts/verify_unified_ai_session12.py tests 01` | 1 | Combined682:680 passed/2 failed,211.28s. Giữ XML/log/basetemp. |
| `scripts/verify_unified_ai_session12.py tests 02` | 1 | Affected253:252 passed/1 failed,105.90s. Workflow contract đã đạt; deadline fixture còn lỗi. |
| `scripts/verify_unified_ai_session12.py tests 03` | 0 | Final affected109 passed,54.89s;38 ca mới cán bộ. Không chạy lại fixture deadline không sửa trong lượt này. |
| `scripts/prepare_unified_ai_frontend12.py prepare 01/02/03` | 0 mỗi lượt | Fresh snapshots; snapshot02 được giữ, chưa build. |
| `scripts/prepare_unified_ai_frontend12.py build 01/03` | 0 mỗi lượt | Production build và Next TypeScript đạt. Final03 BUILD_ID **tSviX_DAe4wx6NTzaQ-uR**; build01 **uR0qlgRDPRF7hjPcH1NDo** cũng được giữ. |
| `scripts/prepare_unified_ai_frontend12.py typecheck 01/03` | 0 mỗi lượt | Standalone `tsc --noEmit --incremental false` trên snapshot tương ứng đạt. |
| `scripts/verify_unified_ai_session12.py host 01` | 0 | Read-only GET/netstat, không transition. |
| `scripts/verify_unified_ai_session12.py audit 01` | 0 | Mọi bảng/hàng của4 retained DB và paid/native metadata không đổi. Latest outcomes lúc đó684 ca; lượt03 bổ sung1 ca nữa. |
| `scripts/verify_unified12_scope.py 01` | 0 | Preimages/Git entries/guard giữ nguyên, không thêm Ruff E9/F finding. Build03 đang hoàn tất tại thời điểm snapshot audit01. |
| `scripts/verify_unified_ai_session12.py audit 02` | 0 | Final685 latest outcomes,4 all-table/row digests và paid/native metadata giữ nguyên; `test-outcomes-02.json` ghi rõ release gate failed. |
| `scripts/verify_unified12_scope.py 02` | 0 |17 pre-existing paths được sửa,18 files mới, không thêm lint finding hoặc mất Git entry; final03 build ID và guard bytes đã kiểm. |

Final preservation đọc tại `session-verification-02.json` và `test-outcomes-02.json`; final scoped diff sau khi chốt báo cáo tại `scope-verification-03.json` và `complete-source-changes-03.patch` (scope02 cũng được giữ). Tổng **685 ca duy nhất:684 passed/1 failed** dựa latest `(classname,name)` XML01–03; không cộng reruns hoặc647 ca lịch sử chặng11.

38 ca mới kiểm scope actor/tenant/queue/assignment/session, public/internal isolation, source locator/hash/version, profile/học phần drift, five-state readiness, explicit review/idempotency/provenance, supplement delta và reuse, stale binding, corrupt cache/receipt fail-closed, thiếu consumer, input authority injection, autosave/CAS/restart/readback, legacy draft byte compatibility và **hai process thật** tranh claim/draft trên fixture mới. Không biến API synthetic checks thành nghiệm thu tính hữu ích thực tế hoặc browser tabs/reload UX.

Lỗi01 `test_source_hash_failure_remains_an_error_and_unknown_workflow_milestone_stops`: thay đổi ban đầu đã chuyển lỗi hash workflow API cũ thành HTTP200. Đã sửa bằng cờ nội bộ riêng cho staff preparation/draft read: API workflow cũ vẫn409; staff evidence giữ trạng thái lỗi/xung đột để cán bộ xử lý, không tạo rejection. Assertions cũ giữ nguyên và đạt02/03.

Lỗi còn lại ở01 và02 là `tests/unit/agent/test_multi_agent_integrated.py::test_deadline_and_token_reservation_stop_before_new_effect`: deadline50ms; durable reservation/pending đã được ghi nhưng fake provider chưa được gọi (`usage.model_calls=1`, `len(model.calls)=0`). Chặng11 đã ghi nhận cùng lỗi; phiên này tái hiện hai lần. Read-only inspection thấy `BoundedGateway.generate` lưu reservation/pending trước lần kiểm deadline ngay trước dispatch. **Không sửa `single_agent/resources.py`, controls ngân sách/deadline hoặc assertion/threshold**, theo giới hạn bảo toàn safety controls của yêu cầu. Chưa loại bỏ lỗi này; không tuyên bố toàn bộ combined backend đạt hoặc chỉ dựa vào rerun để xóa failure record.

## Bảo toàn và giới hạn

Preimages được kiểm hash;73 records/72 paths, gồm pre-existing dirty/untracked source và backlog. Audit mọi bảng/hàng của4 retained DB không đổi: `unified-ai-20261014-01/business-candidate01.sqlite3`, `unified-ai-20261014-05/actor-state.sqlite3`, `public-rag-20261013/conversations.sqlite3`, `multi-agent-integrated-20261013-01/agent-runs.sqlite3` dưới `infra/local/`. DB nguồn chỉ mở mode=ro; mọi fixture init, drift và corruption thuộc namespace mới của chặng12. Metadata paid/native không đổi; provider thật của phiên này0. Git entries pre-existing không mất, không thêm lint E9/F finding so với preimages.

Build dùng fresh source snapshots và guard nguyên byte, SHA256 **8f0886295da2214205cf257dd9e1d9476993ed1a7fb0ac67434909fa4af2eae6**. Giữ cả logs lỗi/lượt chạy, snapshots chưa build và mọi build cũ. Không delete/cleanup/reset/discard, sửa safety/hook/backup/recovery controls, commit/push/deploy, đổi dữ liệu production hoặc restart/reload serving runtime.

Current GET8006/8003 trước mutation và host observation01 trả URLError, netstat inventory rỗng trong môi trường quan sát. **Không xác minh được runtime hiện tại**; không suy ra runtime đã tắt hoặc dữ liệu bị mất từ giới hạn quan sát. Source candidate **unified-local-v12**/build03 chưa được nạp vào serving runtime trong phiên này.

Full acceptance/UI/mobile/accessibility/usefulness/official institutional rules/load/production còn pending. Luồng cán bộ legacy session/mock không được coi là server consumer mới. Chưa có staff model proposal/OCR, official SLA, typed supplement/business result drafting của UNI-031 hoặc distributed worker recovery; chúng không được quảng cáo là đã sẵn sàng.

Business record và actor draft vẫn ở hai SQLite stores: lock nghiệp vụ tuần tự hóa assignment với private save, mỗi draft revision/receipt atomic trong actor store; **không có bằng chứng distributed/cross-store atomicity hoặc crash recovery production**. Readiness nội bộ không thay outcome preview/confirmation/authorization, không chứng minh mẫu hoặc eligibility chính thức. UNI-031 chưa triển khai. Backlog giữ nguyên record chặng11, đánh dấu implemented riêng UNI-026–030 với các giới hạn trên; pending verification UNI-003–030 và next_task **UNI-031**.
