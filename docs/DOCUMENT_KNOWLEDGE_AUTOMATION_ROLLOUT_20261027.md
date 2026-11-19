# Gói chuyển bản chính — 27/10/2026

Trạng thái hiện tại: **đã triển khai lên main theo xác nhận trực tiếp “Cho phép triển khai gói lên bản chính” ngày27/10/2026**. Phần mô tả kế hoạch bên dưới được giữ để đối chiếu với đích đã được cho phép.

## Một địa chỉ sử dụng — 20:49 UTC+7

**Entry hiện hành duy nhất: `http://127.0.0.1:8015/services`**, API cùng origin, frontend nội bộ3015/artifact16, schema0022/release27/policy3/114members. `pnpm start` và `scripts/campus.py start/status` dùng main như runtime launcher mặc định; README đã cập nhật. Các chỉ dẫn3115 hoặc build cũ bên dưới là lịch sử, không phải sản phẩm cần chạy song song.

`unified-main-rollout-20261027T134013533500/receipt.json` đã kiểm idle/pending chat và danh tính listener ngay trước khi dừng API rehearsal8017/8018, frontend3018, thay listener main. Counts/pointer/identity hashes/chat records main và rehearsal giữ nguyên; worker được dùng lại. Không xóa snapshot, dữ liệu, credential, backup, ledger hoặc protection.

Menu/đăng nhập chung có chat, dịch vụ học vụ, hồ sơ, lịch học, phòng học, privacy và quản trị theo role. Ba dịch vụ chuẩn bị lưu nháp riêng theo tenant/owner trong actor store; signed preview/explicit review/CAS/replay/current session/revision/receipt được kiểm. UI thật đã lưu và mở lại nháp hỗ trợ `01a17d98-9efa-7368-9604-005529ddb76c`. **Không phải gửi hồ sơ đến HUCE**; không bật các fixture điểm/profile/eligibility dưới tài khoản local. Lịch học/đặt phòng chưa kết nối, privacy không hiển thị dữ liệu thành công giả.

`unified-main-final-20261027T134653685424.json`: kiểm quyền, readback, revocation, old chat và persistence đạt;34backend/9UI/TypeScript/build đạt. Ảnh `ui-unified-main-20261027-01.jpg`/`02.jpg`, chi tiết failure fixture đã sửa và giới hạn trong mục20:49 đầu handoff. Chưa nghiệm thu toàn bộP00–P16; các phần người dùng hoãn và thiếu quyền/đầu vào thật vẫn giữ nguyên.

## Tài khoản sinh viên local — 20:20 UTC+7

Main hiện **build15**, cùng8015/3015/schema0022/gen27/policy3/114members. Tài khoản `student-local` đã được tạo theo yêu cầu trực tiếp, đăng nhập UI và hỏi nguồn công khai thành công; credential ở `infra/local/knowledge-platform-20261023/student-credentials.json`. Role STUDENT, issuer/key riêng, không phải tài khoản HUCE SSO; không có dữ liệu điểm/lịch giả. Owner credentials/key/roles giữ nguyên.

Chat có reader authorization, admin/write/publication vẫn dùng admin policy; student403 admin/original/preview,404 lịch sử owner/API cá nhân, logout401. `student-login-final-20261027T131952325646/receipt.json` xác nhận UI answer/citation hash và các ranh giới này. Runtime `resume-20261027T131241935272`; startup/status chọn `--frontend-name frontend-knowledge-automation-20261027-15`. Chi tiết kiểm và failed checker receipts giữ trong mục20:20 đầu handoff; không coi account mới là kết nối SSO hoặc acceptance toàn bộP00–P16.

## Cập nhật chat — 19:58 UTC+7

Main hiện chạy **build14** (`frontend-knowledge-automation-20261027-14`), API8015/UI3015, schema0022/release27/policy3/114members giữ nguyên. Runtime `resume-20261027T124859734537`; chỉ thay đúng API/frontend khi idle, worker scoped giữ nguyên owner.

Sửa phản hồi cho bare topic “học bổng”, hướng dẫn DEPENDENCY_UNAVAILABLE trên UI và UUIDv7 client turn receipt. Nguyên nhân hai lỗi đỏ19:37–19:38 có native TimeoutError; không tăng deadline3s hoặc thay nguồn/quyền để vượt lỗi. 67backend/42UI/TypeScript/build đạt; UI thật đã hỏi làm rõ và trả lời câu STEM đúng năm2025–2026, mở citation gốc/hash đạt. `chat-repair-final-20261027T125814141031/receipt.json` giữ kết quả, bao gồm lượt thiếu năm vẫn abstain và giới hạn timeout còn có thể xảy ra. Không sửa/xóa lịch sử lỗi người dùng.

Startup/status dùng `--frontend-name frontend-knowledge-automation-20261027-14`; các chỉ dẫn build13 bên dưới là lịch sử. Chi tiết trong mục19:58 đầu handoff; phần hoãn/nghiệm thu P00–P16 không đổi.

## Cập nhật vận hành — 18:49 UTC+7

**Bổ sung19:00:** lịch đã chạy slot kế tiếp qua mốc900giây thật, không manual tick:18:43:56→18:58:57 (901.083388giây), hai job khác nhau/attempts1/hash đạt,0generation mới. Receipt `schedule-recurring-20261027T115951589140.json`; checkpoint cuối kiểm strict>=900giây. Observation slot1 mới hơn watermark bundle18:45 nên cần đối soát khi phục hồi; bản gốc vẫn giữ trong main.

Đã kiểm lại DB thật:11job deferred thuộc tenant kiểm thử, không phải tenant phục vụ `huce-local-public`. Worker có scope tenant đã bật và xử lý upload mới;11hàng cũ giữ nguyên mọi cột. Không cần giữ `--defer-worker` như một điều kiện để bảo vệ chúng. Hướng dẫn defer ở mục15:58 bên dưới là lịch sử của lần triển khai trước khi kiểm rõ tenant.

- Main0022/build13/8015/3015,120sources/330versions/114members/gen27/policy3. API listener22764/frontend444/worker loop21804 là lần quan sát này, không dùng làm PID cố định. Runtime receipt: `resume-20261027T114317510843` trong namespace knowledge-platform ngày23.
- Worker pulse mới kiểm PID thực/DB/tenant/freshness, có reconnect/backoff; giữ floor2GiB/cap3/lease/fencing/ledger. Scheduler lọc lịch không còn due và slot đã chạy trước LIMIT; PostgreSQL test có hơn200history rows. **61targeted tests passed**, không chạy toàn suite/model campaign.
- Upload PDF có sẵn được background worker xử lý sau disconnect, giữ NEEDS_INFORMATION/DUPLICATE_REVIEW, không tự link/review/publish. URL source Office365 tạo acquisition/job thật qua vòng nền. Lịch phiên900giây hết hạn **19:28:45 ngày27/10 UTC+7**; không có unattended publication authority.
- Đã restart đúng API/worker khi không có pending conversation/live lease; có boot ack mới, lịch cũ không tự nhận lại credential; lịch thay thế cùng phạm vi chạy thật. `operations-restart-20261027T114314164611/receipt.json` xác nhận data/deferred rows/pointer/counters giữ nguyên và0paid calls mới.
- `main-rollout-check-20261027T114439803565`:13/13checks sau restart, dùng lại answer/citations/historical receipt cũ, không generation mới.
- Backup trạng thái mới: `schema-rehearsal-bundle-20261027T114458600701.json`,659artifacts+PG+3SQLite, coherent/restore/fingerprints/replay0022 đạt ở DB mới `_11e1a13bcea7`; tất cả bản cũ giữ nguyên.

Lệnh startup/status hiện dùng `--frontend-name frontend-knowledge-automation-20261027-13`; không cần chạy migration lại. Chi tiết kết quả, các failed checker receipts giữ lại, ma trận P00–P16 và phần hoãn/chặn nằm ở mục18:49 đầu [handoff](DOCUMENT_KNOWLEDGE_AUTOMATION_HANDOFF_20261027.md). Không coi thay đổi vận hành này là whole-plan semantic acceptance.

## Kết quả triển khai — 15:58 UTC+7

- Main DB `campus247_knowledge_local_20261023` đã nâng0018→0022, không backfill nội dung. `rollout-preflight-20261027T084915271098.json` giữ baseline; `rollout-migration-20261027T085214082149.json` xác nhận các hàng/cột cũ trong9bảng nguồn/version/artifact/review/release/member/pointer/job khớp hoàn toàn. Giữ120sources/330versions/114members/gen27/policy3.
- API8015 **PID17940**, frontend3015 **PID444**, build13; fresh live boot ack đạt. Wrapper PID8304/1916 không phải listener. Runtime receipt `infra/local/knowledge-platform-20261023/resume-20261027T085226306869/receipt.json`.
- Đã dừng đúng prototypeAPI11100 sau khi kiểm command/listener và không còn pending chat. Paid writer được main nhận khóa OS bình thường, không sửa khóa/ledger. Prototype8018 chạy lại **không generation**, PID11360, cùng DB/artifact/SQLite cũ; frontend3018/PID18312 giữ nguyên.
- Preflight phát hiện11job cũ đều DRAFT/EXTRACT/attempts0. Theo chỉ dẫn để tài liệu chưa xong xử lý sau, runtime dùng **`--defer-worker`**: không claim/chạy lại các job đó. Queue/evidence giữ nguyên; chưa có worker quét chung cho các upload mới. Muốn vận hành ingestion tiếp phải chọn phạm vi/job cụ thể, không chạy lệnh start thiếu cờ này một cách mặc định. Vòng scheduler trong API vẫn chạy cho lịch được cấu hình bằng phiên hợp lệ.
- `main-rollout-check-20261027T085405885806`: câu hỏi thực K71/cử nhân/2026–2027 tổng hợp Quy chế1486 vàQĐ924 trả lời50giờ và592.500đ/tín chỉ trong9.080s, mở cả2nguồn200/hash khớp. Historical citation/history/original và auth checks đạt. Checker lúc đầu đòi duplicate SSE chưa đúng contract; API thực trả409 kèm receipt cũ, không tự sinh lại.
- Sửa **checker**, giữ nguyên contract/app/expected facts. `main-rollout-check-20261027T085538074526`: **13/13 kiểm tra đạt**, dùng lại đúng câu trả lời trên, không gọi thêm model. Duplicate409→receipt200/COMPLETED/cùng assistant_message_id, paid snapshot giữ nguyên; logout/revocation401, anonymous admin/source401. Không biến409 thành lỗi ứng dụng hoặc bỏ idempotency.
- UI main đăng nhập owner cũ, mở lịch sử câu trả lời thực và hiển thị hai nguồn thành công. Ảnh `ui-main-answer-20261027-16.png`, tab để lại ở câu trả lời này.
- Backup trước deploy mới: `schema-rehearsal-bundle-20261027T084928784392.json`, source0018,649artifacts+PG+3SQLite, restore/migrate0022/replay/coherent capture đạt. Backup **sau deploy**: `schema-rehearsal-bundle-20261027T085621179427.json`, source0022, restore sang DB mới `campus247_automation_20261026_4af66d45f061`,649artifacts+3SQLite và fingerprints/replay đạt. Mở rộng backup helper chỉ cho exact source0018/0022; cấm restore0022 xuống0021. Mọi backup/DB cũ còn nguyên.
- Kiểm launcher sau cờ defer-worker:18passed. Core/UI/OCR full436/5skipped/20UI/TypeScript0 của prototype vẫn là regression trước deploy; không tự nhận đã chạy lại toàn suite trên main.
- Giữ cả receipt kiểm migration đầu `rollout-migration-20261027T085136157308.json`: data hashes đúng nhưng phép so UUID/datetime typed với JSONstring trảfalse. Lượt sửa chuẩn hóa cùng serialization xác nhận pointer/hash đúng; không thay giá trị mong đợi hoặc dữ liệu DB.

Main phục vụ local đã kiểm. Tài liệu/semantic graph chưa hoàn tất, independent review, service authority tự xuất bản và HUCE SSO/API cá nhân vẫn có giới hạn như cuối tài liệu; không coi toàn bộ P00–P16 đã nghiệm thu.

## Đích chính xác

- Workspace: `C:\Users\Duong Vinh\Vinh`.
- PostgreSQL loopback `127.0.0.1:55437`, database `campus247_knowledge_local_20261023`: nâng forward-only **0018 → 0022** bằng bốn migration 0019–0022 hiện có. Thêm intake/lineage/acquisition/edition decisions/corrections; không xóa dữ liệu hoặc tự backfill phê duyệt nội dung.
- API `127.0.0.1:8015`, frontend `127.0.0.1:3015`, immutable build **frontend-knowledge-automation-20261027-13**. Hiện hai cổng main chưa chạy; không coi PID trong bàn giao cũ là PID sống.
- Giữ release `01a172fe-1822-7679-a515-335e063dd1fa`, generation **27**, policy **3**, **114** members; nguồn main **120**, versions **330** trước chuyển. Không activate/rollback release, duyệt nguồn hay nhập dữ liệu prototype vào main.
- Chuyển quyền ghi paid ledger bằng cách dừng đúng prototype API đang sở hữu lease khi không còn request đang chạy, chờ khóa OS được giải phóng bình thường, rồi khởi động main. Không xóa/đổi khóa, reset ledger hoặc tăng budget. Prototype có thể phục vụ lại không generation để đối chiếu.
- Worker main dùng queue hiện có; kiểm danh sách pending/live jobs trước khởi động. Không reset attempts, lease hay gán duyệt cho job bị chặn.

## Chứng cứ đã có

- `verify-20261027T073302095623`: **436 backend passed, 5 skipped** (năm opt-in main DB), **20 UI passed**, TypeScript exit0; local OCR thực đã chạy.
- Kiểm entrypoint/launcher và follow-up sau thay đổi cuối: **31 passed**; command bên dưới. Có guard đúng tên DB, schema được hỗ trợ, frontend path/port; không nhận nhầm rehearsal process làm main.
- `live-independent-20261027T071521803644`: 11 câu trong shard đã giữ, 9 câu trả lời và 2 từ chối câu hỏi cá nhân. `candidate-material-20261027-01.json`: không có lỗi trường nội dung được kiểm. Đây là regression có giới hạn, không phải nghiệm thu ngữ nghĩa độc lập toàn bộ sản phẩm.
- `conversation-probe-20261027T072140717220`: chuỗi học phí/phạm vi/đổi chủ đề đạt; hai lỗi lab nối tiếp và hai tài liệu được lưu nguyên. Sau sửa, `conversation-probe-20261027T073342900434`: hai kịch bản đó đạt, câu tổng hợp mở được cả hai nguồn đúng hash.
- `application-load-20261027T074634045889`: hai request ứng dụng đồng thời HTTP200, trả lời và citation hash đạt, 10.832/9.885 giây. Không suy thành throughput/SLA.
- `schedule-probe-20261027T073929376851`: background loop thật tạo acquisition/job URL và readiness AWAITING_CONFIRMATION; không gọi manual tick. Hai observation HTTP200 được giữ; HTML còn yêu cầu linked original/metadata, không bị tự duyệt. Lịch thử đã cancel theo bản ghi bổ sung, mọi evidence còn nguyên. Pointer trước/sau giống nhau.
- Bundle mới `schema-rehearsal-bundle-20261027T072224263352.json`: backup PostgreSQL + **649** artifacts + ba SQLite; fingerprint/integrity/cross-store capture đạt; restore vào DB mới `campus247_automation_20261026_1603ba3a7a79`, nâng0022 và replay đạt. Dump trước migration cùng bản gốc được giữ.
- `restore-runtime-20261027T073301641623.json`: API phục hồi8017 cấp boot ack mới, đọc lại citation gốc/hash thành công; anonymous admin bị từ chối và logout thu hồi phiên. Không tái dùng ack cũ.
- UI8018 đăng nhập owner có sẵn, hỏi đáp, mở nguồn gốc và tải lại lịch sử thành công. Ảnh `ui-candidate-citation-20261027-14.png`; không xác nhận đối chiếu thay người dùng.

## Lệnh triển khai và kiểm tra (đã chạy; không lặp migration để “làm sạch”)

Từ workspace, dùng Python hiện có `infra/local/rag-fixture/.venv/Scripts/python.exe`:

```powershell
# Chỉ sau khi kiểm lại identity, jobs, free space và giữ bundle mới nếu dữ liệu main thay đổi:
& infra/local/rag-fixture/.venv/Scripts/python.exe -B -X utf8 scripts/knowledge_platform.py migrate --revision 0022
& infra/local/rag-fixture/.venv/Scripts/python.exe -B -X utf8 scripts/knowledge_platform_runtime.py start --frontend-name frontend-knowledge-automation-20261027-13 --defer-worker
& infra/local/rag-fixture/.venv/Scripts/python.exe -B -X utf8 scripts/knowledge_platform_runtime.py status --frontend-name frontend-knowledge-automation-20261027-13 --defer-worker
```

Lệnh `start` không migration/bootstrap/stop process. Giữ default migration0018 và frontend-v14 cho caller cũ; bản mới phải chọn tường minh. Không chạy `start` khi prototype còn giữ paid writer lease. Bước stop phải dựa vào PID/command/listener vừa xác minh, không dùng số PID lịch sử trong tài liệu này.

Sau chuyển: kiểm schema0022, counts/release/generation/policy/membership như trên, boot ack mới, owner login/logout, anonymous401, lịch sử/citation cũ, một câu hỏi nguồn thật và frontend build. Nếu có sai khác, dừng trước các bước tiếp theo và giữ logs; không tự sửa dữ liệu để khớp.

## Khôi phục và giới hạn

Migration forward-only. Không downgrade hoặc ghi đè DB gốc/SQLite để quay lại. Nếu startup thất bại, giữ DB sau migration và mọi logs; phục hồi backup vào **namespace mới** bằng workflow đã kiểm, xác minh fingerprints và citations, rồi trình đích chuyển kết nối cụ thể. Bản phục hồi không chứa các ghi mới sau thời điểm snapshot; phải giữ chúng để đối soát. Không tự xóa, đổi tên hoặc thay thế DB cũ. Không tuyên bố có rollback in-place.

Native deadline3000ms, CPU/memory guards, TLS/DNS/URL validation, paid ledger, auth/revocation, idempotency, fencing và confirmation vẫn giữ. Lịch bám phiên đã đăng nhập, hết hạn cùng phiên; restart cần resume đúng phiên. RELEASE_DUE chỉ báo readiness, chưa có service authority tự xuất bản không giám sát.

Nguồn chưa hoàn tất/semantic graph/partial amendment và duyệt độc lập tiếp tục hoãn theo chỉ dẫn dùng nguồn đã hoàn tất. Không giả HUCE SSO hoặc API điểm/lịch cá nhân. Những giới hạn này không được đổi thành facts hay approval để đóng P00–P16.

## Kiểm entrypoint có thể lặp lại

```powershell
& infra/local/rag-fixture/.venv/Scripts/python.exe -B -X utf8 -m pytest tests/operations/test_knowledge_platform_runtime.py tests/unit/conversation/test_followup_question_m2.py -q -p no:cacheprovider
```
