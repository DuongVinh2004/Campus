# Protocol pilot C — batch 20261015-01, prepared / not run

Ngày15/10/2026, Asia/Bangkok. UNI-047 và AT-49 **not verified**. Chưa có participants, lịch/session, môi trường pilot được phép, qualified expert hoặc dữ liệu đo thật. Không liên hệ, mời hoặc gửi tin cho ai trong phiên này. UI testing hiện chưa được chạy; 044/045/046 full acceptance còn pending.

Tập dự kiến theo plan hiện có: 8–12 phiên sinh viên, 8–12 phiên cán bộ và4 phiên round-trip ghép. Đây là thiết kế lấy mẫu chưa thực hiện. Dùng nguồn/workflow synthetic rõ ràng cho giai đoạn thử; nếu chuyển sang institutional/real data phải xác định authority và nguồn tương ứng trước. Không chép dữ liệu riêng/credentials vào report.

## Matched scenarios

| Mã | Sinh viên | Cán bộ | Complexity/điều kiện giữ giống |
| --- | --- | --- | --- |
| C-P01 | Giấy xác nhận: purpose/recipient có nguồn và1 field thiếu | Review/source/template/outcome tương ứng | Cùng field count, source versions và missing fact |
| C-P02 | Phúc khảo mô phỏng: chọn học phần và reason | Đối chiếu evidence, không AI quyết định học vụ | Cùng số documents/criteria và source conflicts |
| C-P03 | Bổ sung typed item, không nhập lại phần đủ | Group known missing, delta review và giữ phần không đổi | Cùng số item/round và before/after fields |
| C-P04 | Nguồn cũ/goal mơ hồ/timeout giữ work | Reassign/revoke/stale preview/read receipt | Cùng fault timing và quyền/scope |

Mỗi participant làm baseline manual/simple và assisted trên hai fixtures tương đương, thứ tự cân bằng để giảm học thuộc. Không dùng lại case đã biết đáp án cho cùng người mà bỏ ghi nhận. Staff blind subset xem source và criteria trước khi nhìn gợi ý; disagreements được qualified reviewer đọc original evidence, không majority vote hoặc model self-judge.

## Script thực hiện khi đủ điều kiện

1. Ghi build/API/mode/source+dataset hashes, actor role/scope, case ID và version. Giải thích storage/retention/temporary/suppression; không hứa physical erasure.
2. Participant tự làm goal→draft→preview→confirm; observer ghi cần trợ giúp, lỗi và corrections, không dẫn tới đáp án trong completion metric.
3. Staff tự review nguồn/criteria→supplement hoặc structured result→preview/confirm; observer ghi active, tìm nguồn, đọc lại, soạn, wait categories và errors.
4. Ghép hai vai trò qua typed supplement/receipt/readback; kiểm đúng item, recipient và privacy.
5. Đối chiếu original sources/receipts để chấm completion, first-pass correctness và material correction. Thu feedback effort/confusion riêng với correctness.

Mẫu record (chưa có record đo): `session_id`, pseudonymous `participant_id`, role, scenario, condition/order, complexity, environment/dataset hash, start/end, active_ms, student_wait_ms, unit_wait_ms, system_ms, fields_entered, corrections, source_lookups, help_requests, supplement_rounds, reopens, completion, first_pass_correct, wrong_recipient, unauthorized_access, private_leak, duplicate_effect, receipt_refs, observer_findings, expert_disagreement_status. Không lưu raw private content hoặc confirmation tokens.

Các mục tiêu thiết kế giữ từ plan: giảm40% trường nhập tay ở tác vụ có nguồn hợp lệ, giảm30% thời gian thao tác sinh viên,90% phiên supported hoàn tất không cần hướng dẫn. **Chưa đo/đạt**; staff mục tiêu chốt sau baseline. Báo cohort/n/missingness và task complexity; speed không bù cho lỗi quyền/facts/recipient/mandatory review/duplicate. Không suy usability từ fake smoke/build/backend pass.

Next action thực: hoàn tất và kiểm A/B consumers +043, cho phép và thực hiện044 UI candidate, matched045 và bounded046; sau đó người có thẩm quyền xác định participants/môi trường. Không tự tạo automation hoặc mời participants.
