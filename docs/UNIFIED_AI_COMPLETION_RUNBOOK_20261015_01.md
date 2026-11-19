# Runbook local Campus 24/7 — 15/10/2026

Runbook này khớp candidate04, BUILD_ID `I0Xq0uJY2BXxvGQBOUo-i`, frontend3019/API8019. Provider là fake deterministic; dữ liệu chỉ là fixture tổng hợp. Xem [báo cáo và giới hạn](UNIFIED_AI_COMPLETION_20261015_01.md) trước khi diễn giải số đo. Các runtime cũ và toàn bộ evidence được giữ.

## Mở và xác định đúng bản

Mở `http://localhost:3019/login`; xác nhận `http://localhost:8019/candidate-manifest` trả đúng candidate04/build/provider. Dùng SV001 hoặc SV024 cho sinh viên và OF002 cho cán bộ fixture. Không nhập credentials/dữ liệu production. Candidate feature-off riêng ở3020/API8020. Những bản này đã được launch trong phiên; không chạy lại `serve` trên cùng port hoặc dùng `init` lên dữ liệu có sẵn.

Nếu process kết thúc, trước tiên đọc exact `fixtures/candidate04/serve.json`, `checks/frontend-04/serve-command.json` và build manifest dưới `infra/local/unified-ai-completion-20261015-01`. Kiểm port/PID và source hashes. Script deliberately ghi evidence exclusive, vì thế không replay `serve`/`init` khi marker đã tồn tại. Chuẩn bị namespace mới được canonical-check và giữ riêng lịch sử launch khi cần launch lại; không xóa marker để vượt bảo vệ, không kill process không xác định.

## Sinh viên

1. Đăng nhập, chọn học phần và mục đích ở /services hoặc panel hỗ trợ. Nháp đề xuất chỉ điền nguồn hợp lệ; kiểm trường còn thiếu và giữ manual edits. Mở nguồn để xác minh.
2. Save, đợi readback rồi có thể reload. Nếu nhiều draft, chọn đúng draft/case; không đoán ID. Preview phải khớp target, recipient, payload và version; chỉ xác nhận đúng preview.
3. Khi cán bộ yêu cầu bổ sung, mở đúng typed item, sửa dữ liệu cần thiết, đọc preview và xác nhận. Kết quả cuối chỉ được coi là hoàn tất khi có receipt và projection đọc lại đúng.
4. /chat: lịch sử thường theo account; mở lại conversation gốc thay vì tạo bản sao để retry. New chat không xóa chat cũ. Chat tạm thời mới phải được server ack `mode=temporary`; tạm thời không dùng personal memory nhưng vẫn có lưu trữ vận hành30 ngày, không có lời hứa xóa vật lý tức thì.

## Cán bộ

Mở đúng queue/case, claim theo quyền rồi mở dossier/nguồn. Nháp private autosave phải hiển thị readback trước khi rời trang. Mỗi mandatory criterion cần review thực; AI readiness không tự tick thay cán bộ. Dùng typed supplement cho phần thiếu, giữ phần không đổi khi delta review. Structured outcome phải dựa trên nguồn và lựa chọn của người có quyền; preview/confirm rồi đọc receipt. Internal notes/draft không được đưa vào public message. Sau reassignment/revoke/version change, tạo preview mới từ state hiện hành, không reuse approval cũ.

## Settings, memory và thông báo

Settings và consent là hai bước có readback; consent không cấp quyền nghiệp vụ. /memory cần consent cá nhân hóa và opt-in riêng. Save/correct/forget/tắt đều preview và confirm; correction có version/CAS. Forget suppress derived context và tự reuse history nhưng giữ chat gốc. Memory off không xóa history; export không hồi sinh forgotten text. Legacy không rõ mode/owner phải giữ nguyên để xử lý có evidence riêng.

/notifications chỉ subscribe trigger/resource/channel/expiry được cấp, có quiet hours và stop tracking. Không đổi channel thành promise gửi email/SMS nếu adapter chưa được xác minh. Mở notification phải reauthorize đúng resource. Trong rehearsal, hai process worker riêng delivery1 rồi0 chứng minh dedup/restart cục bộ; không phải worker production liên tục. Setup notification trong E2E dùng API fixture, không được mô tả là toàn UI.

## Khi lỗi hoặc không rõ kết quả

- Timeout/429: giữ draft/ID; đợi rate window, đọc state/receipt trước. Không gửi lại confirm chỉ vì UI chưa nhận response. `ui-flow-08`/`ui-readback-01` có ví dụ thật từ fixture.
- Conflict/stale/revoke: giữ manual draft và đọc version/assignment/grant/source hiện hành. Không dùng model prose làm receipt hoặc bỏ mandatory check.
- Storage/audit unavailable: không báo đã lưu hay đã hoàn tất. Giữ evidence, đọc lại khi storage có thể dùng; không reset database hoặc sửa receipt bằng tay.
- Feature-off: candidate3020 chứng minh manual save/reload/confirm và staff claim. Không flip serving feature, migrate DB cũ hoặc xóa history để đạt rehearsal.
- Không rõ owner/legacy mode/nguồn chính thức: giữ dữ liệu gốc và ghi thiếu thông tin. Không gắn tài khoản tùy ý, không dùng fixture thay quyết định trường.

## Các lệnh đã chứng minh

Chạy tại `C:\Users\Duong Vinh\Vinh`, bằng Python workspace. Đây là record, không phải hướng dẫn replay vào đường đã có. Không xóa output cũ để chạy lại.

```powershell
.\.venv\Scripts\python.exe -B scripts/unified_completion.py verify 08
.\.venv\Scripts\python.exe -B scripts/unified_completion_frontend.py prepare 04
.\.venv\Scripts\python.exe -B scripts/unified_completion_frontend.py build 04
.\.venv\Scripts\python.exe -B scripts/unified_completion_frontend.py typecheck 04
.\.venv\Scripts\python.exe -B scripts/unified_completion_candidate.py init 04
.\.venv\Scripts\python.exe -B scripts/unified_completion_candidate.py serve 04
.\.venv\Scripts\python.exe -B scripts/unified_completion_frontend.py serve 04
```

Verify08 đã tạo877 test cases duy nhất,0 skip/failure. Build/typecheck exit0. Init chỉ dùng target mới hoàn toàn. Backend verify/audit lần sau phải chọn một số hai chữ số chưa tồn tại; frontend/candidate wrapper hiện chỉ cho các attempt01–04 đã dùng và từ chối đè output. Muốn candidate mới phải thêm đúng target/port không xung đột qua scoped patch có preflight, không nới guard hoặc tái sử dụng folder cũ.

Playwright CLI đã cài được dùng sau khi hai UI kernels không khởi tạo; harness `infra/local/unified-ai-completion-20261015-01/ui-runner.cjs` mở profile/temp/downloads trong scope riêng, chặn ngoài loopback. Mỗi `stage-NN` phải chưa tồn tại. `mobile-07 04 <case-id>` đã kiểm390px, labels/skip link, staff detail, dark màu ổn định và sampled heading contrast. Chưa kiểm toàn WCAG/screen reader. Không dùng ảnh lúc loading hay transition làm proof final.

## Trước review/pilot hoặc rollout thật

Đọc `coverage.json` và source/build binding; giữ nguyên toàn bộ failures/logs. Reviewer dùng original evidence, blind subset và ghi disagreement; fake model không chấm usefulness. `pilot-session-template.json` chưa có participants/session: chỉ ghi observation thật, tách system/active/student wait/unit wait và missingness. Không tự điền điểm, gọi synthetic actor là participant hay gửi lời mời.

Budget hiện còn34 calls; full matched evaluation không được admitted với reserve36 cho nhánh multi riêng. Giữ limits/cost controls và báo thiếu điều kiện. Chưa deploy, chưa xác minh official rules/fees/deadlines hoặc distributed cross-store recovery; cần môi trường và authority cụ thể cho bước đó. Không có thao tác phá hủy hoặc chuyển serving được ủy quyền bởi runbook này.
