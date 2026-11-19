# Chặng đầu của một ứng dụng AI hợp nhất

Điểm vào duy nhất cho candidate: **http://localhost:8006/login**. Synthetic accounts SV001/SV024 (sinh viên), OF001/OF002 (cán bộ theo queue), KA001/KA002 (nguồn). Đây là bản local đang triển khai, không phải bản hoàn tất 50 tasks hoặc production. Các bản trước giữ nguyên để bảo toàn dữ liệu; candidate dùng bản sao SQLite nhất quán, không tự đồng bộ ngược sang8004.

UNI-001/002 verified: runtime/build/API, source-snapshot hashes, identity/storage/retention và ma trận handler/gap. UNI-003 implemented:14cases, existing technical baseline và protocol; chưa đo công sức/active/wait của người dùng nên chưa verified. UNI-004 in_progress: strict context/resource/evidence DTO, JSON Schemas, read-only endpoint, một bootstrap và panel dùng chung hai vai trò. Chưa nhận toàn bộ UNI-004 hoặc mở các task phụ thuộc như đã verified.

Panel “Trợ giúp hồ sơ” trên `/services` đọc lại ID/version ở server. Service hiện có kiểm tenant/session/role/queue/owner trước projection. Response không có profile, internal notes, form content, confirmation token hoặc action tools. Nguồn current/checksum được đọc lại; source khác snapshot thì `source_changed`, thiếu nguồn thì `missing_source`; không suy readiness từ model confidence. Manual form edits được giữ. Certificate context API dùng public snapshot có disclaimer; giao diện certificate chưa gắn panel trong slice này.

Một app kết hợp certificate, phúc khảo/hỗ trợ, quản trị nguồn và proxy conversation/policy graph tới writer8003 hiện có. Candidate không mở Gateway hoặc paid writer mới. Staff model chat, settings/grants/memory bền vững, discovery history, typed supplement, batch, schedule/room integration và các tiêu chí pilot còn ở backlog. Existing staff action/confirmation gaps vẫn được ghi nhận; context endpoint không thêm quyền hành động.

## Kiểm chứng thực tế

- 117 tests nền pass, 27 tests backend mới pass, 10 tests frontend pass; total 154 không tính các lần chạy lại. Reports: `infra/local/unified-ai-20261014-01/baseline-tests-01.xml`, `context-tests-03.xml`, `frontend-tests-02.xml`.
- Next compiler + TypeScript exit0, build `hDhVsK9aYcM0G4z95mzzj`. Guard SHA256 `8f0886295da2214205cf257dd9e1d9476993ed1a7fb0ac67434909fa4af2eae6` giữ byte-for-byte. Build wrapper lần đầu lỗi inCP1252 sau compiler thành công; đã sửa UTF-8, giữ artifact/report và kiểm lại build bằng verifier, không cleanup/rebuild vào output cũ.
- Frontend test invocation đầu sai cwd, bịEPERM ở thư mục cũ; không đổi permission hoặc dữ liệu. Chạy lại đúng `apps/web` pass. API test đầu dùng route introspection không phù hợp lazy router của FastAPI; chuyển sang kiểm OpenAPI và HTTP behavior, giữ expected paths/status. Các evidence thất bại vẫn được giữ.
- API candidate đã nạp source cuối sau restart riêng child listener được xác minh command/parent/port; old8003/8004/frontends giữ. Launcher PID khác child listener trên Windows; không suy ownership từ PID đơn lẻ.
- Browser SV001/OF002 thấy cùng caseREADY/version8, cùng source v2/hash, cùng cảnh báo source thay đổi. Chỉ login/read/context; không gửi/nộp/xử lý lại record cũ. Screenshots `browser-student-context-01.jpg`, `browser-staff-context-01.jpg`; DOM observation trong `browser-verification-01.json`.
- Verifier live xác nhận khác sinh viên/wrongqueue404, stale409, shared evidence/state đúng, no-store và no action authority. Row count+hash từng bảng business gốc bằng candidate sau readback; pre-existing Git status entries giữ. Manifest `candidate-verification-01.json`; scope không mở rộng thành user acceptance.
- 3 warnings duplicate OpenAPI operation-ID từ proxy cũ được giữ trong reports, cần xử lý trong UNI-004. Không có model calls hoặc cost measurements trong phiên.
- `git diff --check` toàn working tree báo blank line ở EOF của `apps/web/src/app/globals.css`, là file dirty từ trước và không sửa trong phiên. Kiểm scope các file mới riêng qua manifest/source patch; không sửa thay đổi không liên quan để làm check xanh.

## Tiếp tục

Đọc backlog và `next_task=UNI-003`. Hoàn tất phần baseline effort/active/wait thiếu bằng protocol đã lưu trước khi chốt UNI-003, rồi hoàn tất các contracts còn thiếu của UNI-004. Không dùng thời gian chạy test/automation thay human active time. Synthetic pass chưa chứng minh giảm công sức hoặc usefulness; không tự liên hệ participants.

CLI đã chạy: `scripts/unified_ai_candidate.py prepare`, `build`, `start`. **Không chạy lại** vào frontend01/business-candidate01/launch01 hoặc cổng đang có owner. Các artifacts được tạo exclusive; script từ chối replay/overwrite. Candidate API runtime identity tại `/v1/assistant/runtime`, capability theo actor tại `/v1/assistant/capabilities`.

Tắt/handoff/deploy cần exact targets và verification riêng; giữ data/snapshots/protections. Không có commit, push, deploy, automation, paid writer mới hay destructive cleanup trong phiên này.
