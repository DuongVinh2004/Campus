# F5 — Agent làm thủ tục từ đầu đến cuối

Phụ thuộc: F2 (kiểm điều kiện), `services.preparations`, `tickets.student`. Dùng thêm F1 và F6 cho nhắc việc.

## 1. Mục tiêu và giá trị

Sinh viên nói "Em muốn xin giấy xác nhận sinh viên" hoặc "Em muốn phúc khảo môn X", và trợ lý dẫn trọn thủ tục qua 7 bước:

1. nhận ra thủ tục;
2. kiểm điều kiện theo luật đã duyệt (F2), có chứng minh;
3. hỏi đúng các thông tin còn thiếu, điền sẵn những gì đã biết;
4. liệt kê giấy tờ cần có;
5. dựng hồ sơ và cho xem trước;
6. **sinh viên bấm xác nhận gửi** (quyết định D9: agent không tự gửi);
7. theo dõi trạng thái; khi cán bộ yêu cầu bổ sung thì giúp soạn phản hồi để sinh viên duyệt.

Giá trị: hồ sơ đến tay cán bộ đã đủ và đúng, ít vòng "cần bổ sung"; sinh viên không phải tự đọc quy chế để biết mình có đủ điều kiện không.

## 2. Quyết định kiến trúc: máy trạng thái tất định, model chỉ là công cụ

Agent **không** tự quyết bước tiếp theo theo kiểu vòng lặp tự do. Mỗi thủ tục là một **định nghĩa dữ liệu** (playbook) có các bước cố định. Code chạy máy trạng thái. Model chỉ được gọi ở ba chỗ có giới hạn:

| Chỗ | Đầu vào | Đầu ra | Kiểm bằng code |
|---|---|---|---|
| Nhận diện thủ tục | Câu của sinh viên + danh mục thủ tục (id, tên, mô tả) | `procedure_id` thuộc danh mục, hoặc `NONE` | Id phải thuộc danh mục; độ tin dưới ngưỡng thì đưa ≤ 3 gợi ý cho sinh viên chọn |
| Tách thông tin | Câu của sinh viên + schema trường của thủ tục | `{field: value}` | Mỗi giá trị chuỗi hoặc số phải xuất hiện **nguyên văn** (sau chuẩn hóa) trong câu; ngày phải parse được; mã học phần đúng mẫu; giá trị trượt kiểm thì bỏ và hỏi lại |
| Soạn phản hồi bổ sung | Yêu cầu bổ sung của cán bộ + thông tin sinh viên nhập | Bản nháp phản hồi | Sinh viên đọc và sửa trước khi gửi; không chèn dữ liệu sinh viên không nhập |

Lý do: thủ tục hành chính cần hành vi lặp lại được, kiểm thử được và audit được. Vòng lặp agent tự do khó chứng minh an toàn với thao tác ghi. Điều này khớp với nguyên tắc "model đề xuất, code quyết định" của dự án và với thiết kế `agent/tools/registry.py` (cấm tham số danh tính, `requires_confirmation`).

## 3. Tiêu chí xong (kiểm được)

1. Bộ gold do model viết: 50 câu yêu cầu tự nhiên mỗi thủ tục, có nhãn thủ tục và giá trị trường. Giá trị là chuỗi con của câu, code kiểm.
   - Nhận diện đúng ≥ 95 %.
   - **Điền sai** (giá trị khác gold được điền vào hồ sơ) ≤ 1 %. Ưu tiên độ chính xác: thà hỏi lại còn hơn điền sai.
   - Điền đủ ≥ 85 %.
2. Không có đường nào tạo ticket mà thiếu bước preview và xác nhận do chính sinh viên bấm. Test gọi API theo mọi thứ tự bước; mọi đường tắt bị 409 hoặc 428.
3. Sinh viên không đủ điều kiện (F2 trả NOT_SATISFIED) thì không gửi được thủ tục có `eligibility: required`; trợ lý hiện chứng minh và đường thay thế. Kết quả UNDETERMINED thì cho gửi kèm ghi chú "chưa xác định điều kiện", để cán bộ quyết.
4. Idempotency: bấm xác nhận hai lần hay mạng chập chờn thì chỉ một ticket được tạo. Có test.
5. Theo dõi: ticket đổi trạng thái thì phiên thủ tục cập nhật trong ≤ 60 s, có thông báo hộp thư (đã có sẵn ở `campus_ops`).
6. Tắt `agent.procedures` thì route 404 và tool biến khỏi chat; phiên dở dang giữ nguyên, bật lại thấy lại.

## 4. Phạm vi

**Thủ tục v1:** 3 loại đang có trong `SERVICE_KINDS` (`application/campus_ops/service.py:26`) cộng 2 loại mới (additive):

| `procedure_id` | `service_kind` | Kiểm điều kiện (F2 topic) | Trường chính |
|---|---|---|---|
| `student-certificate` | `STUDENT_CERTIFICATE` | không | mục đích, số bản, ngôn ngữ (vi/en), cách nhận |
| `grade-appeal` | `GRADE_APPEAL` | `GRADE_APPEAL_WINDOW` (trong hạn phúc khảo) | mã học phần, học kỳ, loại điểm, lý do |
| `general-support` | `GENERAL_SUPPORT` | không | chủ đề, mô tả |
| `leave-of-absence` (mới) | `LEAVE_OF_ABSENCE` | `LEAVE_OF_ABSENCE_ELIGIBILITY` | lý do, từ học kỳ, số học kỳ, giấy tờ minh chứng |
| `course-withdrawal` (mới) | `COURSE_WITHDRAWAL` | `COURSE_WITHDRAWAL_WINDOW` | mã học phần, học kỳ, lý do |

Hai loại mới thêm vào `SERVICE_KINDS` và nhãn trạng thái, và đi qua hàng đợi cán bộ sẵn có (`/v1/staff/tickets`). Luật F2 cho các topic kể trên được mã hóa ở F2.8. Thiếu luật thì thủ tục chạy với `eligibility: skipped`, và giao diện ghi rõ "Hệ thống chưa kiểm điều kiện".

**Ngoài phạm vi:**
- tải tệp minh chứng lên (v1 chỉ là danh sách tự khai "đã có"; tải tệp cần cơ chế quét virus như học liệu, để gói sau);
- gửi thay sinh viên;
- thanh toán lệ phí.

## 5. Định nghĩa thủ tục (`config/procedures/*.toml`, duyệt như mã)

```toml
id = "grade-appeal"
version = 1
title = "Phúc khảo kết quả học tập"
service_kind = "GRADE_APPEAL"
description = "Đề nghị chấm lại bài thi kết thúc học phần."
eligibility = { topic = "GRADE_APPEAL_WINDOW", mode = "required" }   # required | advisory | skipped
sources = ["unit:<unit_id điều khoản về phúc khảo>"]                    # hiện ở bước 1 để sinh viên đọc
roles = ["STUDENT"]

[[fields]]
key = "course_code"; label = "Mã học phần"; type = "string"; pattern = "^[A-Z]{2,4}[0-9]{3,4}$"; required = true
extract = true
[[fields]]
key = "semester"; label = "Học kỳ"; type = "enum"; values_from = "profile.semesters"; required = true
[[fields]]
key = "score_kind"; label = "Loại điểm"; type = "enum"; values = ["FINAL_EXAM"]; default = "FINAL_EXAM"
[[fields]]
key = "reason"; label = "Lý do"; type = "text"; min = 10; max = 1000; required = true; extract = true

[[documents]]
key = "none"; label = "Không cần giấy tờ kèm theo"

[eligibility_inputs]          # ánh xạ trường thủ tục → biến F2
"exam.result_published_at" = { from = "profile.exam_result_date", course = "course_code" }   # nếu có dữ liệu
"request.date" = { from = "now" }

[ticket]
title_template = "Phúc khảo {course_code} — {semester}"
summary_fields = ["course_code", "semester", "reason"]
```

- Schema kiểm lúc khởi động: khóa duy nhất, `service_kind` có trong `SERVICE_KINDS`, `topic` có trong F2 (nếu `required`), mẫu regex hợp lệ.
- `values_from = "profile.*"`: lấy từ dữ liệu của chính sinh viên, ví dụ lịch học hay học phần đã đăng ký từ `ops_schedule`. Không có dữ liệu thì cho nhập tay.

## 6. Máy trạng thái của một phiên

```
STARTED ─> ELIGIBILITY ─(NOT_SATISFIED & required)─> BLOCKED ──(sinh viên sửa đầu vào)──> ELIGIBILITY
   │            │(SATISFIED | UNDETERMINED | skipped)
   │            v
   │        COLLECTING ─(đủ trường bắt buộc)─> DOCUMENTS ─> READY_FOR_PREVIEW
   │                                                         │ submit-preview
   │                                                         v
   │                                                     PREVIEWED ─submit-confirm─> SUBMITTED ─> TRACKING
   │                                                                                    │ ticket.status
   │                                                         ┌──────────────────────────┤
   │                                                         v                          v
   │                                                  NEED_INFO (giúp soạn phản hồi)   RESOLVED | REJECTED | CANCELLED (cuối)
   └─ cancel (mọi trạng thái trước SUBMITTED) ─> CANCELLED
EXPIRED: phiên chưa gửi, không hoạt động 30 ngày (job), dữ liệu trường bị xóa, chỉ giữ dòng trạng thái
```

Bất biến:
- `SUBMITTED` chỉ đạt được qua `submit-confirm` có token hợp lệ, do chính chủ phiên gửi.
- Ticket tạo bằng `CampusOpsService.submit_ticket(identity, body, idempotency_key)`, với khóa idempotency = `procedure-run:<run_id>`. Một phiên tạo nhiều nhất một ticket.
- Sau `SUBMITTED`, trường của phiên không sửa được nữa. Thông tin bổ sung đi qua phản hồi ticket (`student_reply`).
- Mọi chuyển trạng thái ghi `ops_audit` với `action = "PROCEDURE_<STATE>"`.

## 7. Lưu trữ

Lưu trong `campus-ops.sqlite3` để việc tạo ticket và chuyển phiên sang `SUBMITTED` nằm cùng giao dịch:

```sql
CREATE TABLE IF NOT EXISTS proc_runs(
  id TEXT PRIMARY KEY, owner_subject_id TEXT NOT NULL, procedure_id TEXT NOT NULL, procedure_version INTEGER NOT NULL,
  state TEXT NOT NULL, fields TEXT NOT NULL DEFAULT '{}',           -- chỉ trường của thủ tục
  field_origin TEXT NOT NULL DEFAULT '{}',                           -- field -> USER | EXTRACTED_CONFIRMED | PROFILE | DEFAULT
  eligibility TEXT,                                                   -- kết quả F2 rút gọn: outcome, rule@version, proof hash
  documents TEXT NOT NULL DEFAULT '{}', ticket_id TEXT REFERENCES ops_tickets(id),
  row_version INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, expires_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS proc_runs_owner ON proc_runs(owner_subject_id, updated_at DESC);
CREATE TABLE IF NOT EXISTS proc_previews(id TEXT PRIMARY KEY, run_id TEXT NOT NULL, payload_hash TEXT NOT NULL,
  row_version INTEGER NOT NULL, expires_at TEXT NOT NULL, used_at TEXT);
```

Trường lấy bằng model chỉ lưu sau khi sinh viên **xác nhận** từng giá trị trên giao diện; khi đó `field_origin = EXTRACTED_CONFIRMED`. Câu gốc của sinh viên không được lưu.

## 8. API (`/v1/procedures`, thêm vào `ALLOWED_API_PREFIXES`; chỉ `STUDENT`)

| Phương thức, đường dẫn | Mô tả |
|---|---|
| `GET /v1/procedures` | Danh mục: `{id, title, description, eligibility_mode, fields:[{key,label,type,required}], documents, sources}` |
| `POST /v1/procedures/runs` | `{procedure_id}` → phiên `STARTED`, rồi tự chạy bước điều kiện nếu đủ dữ liệu hồ sơ |
| `POST /v1/procedures/runs:from-text` | `{text ≤ 1000}` → `{suggestions:[{procedure_id, title}], run?: {...}, extracted: [{field, value, span:[s,e]}]}`. Không tạo phiên khi độ tin thấp. Trường tách được trả về để **xác nhận**, chưa lưu |
| `GET /v1/procedures/runs?state=&cursor=` | Phiên của tôi |
| `GET /v1/procedures/runs/{id}` | Trạng thái, trường, kết quả điều kiện (gồm chứng minh F2 đầy đủ, đánh giá lại khi mở), bước tiếp theo, ticket liên kết |
| `PUT /v1/procedures/runs/{id}/fields` | `{fields:{…}, confirm_extracted:[keys], row_version}` → kiểm hợp lệ; chuyển trạng thái nếu đủ |
| `POST /v1/procedures/runs/{id}/eligibility` | Chạy lại F2 với trường hiện tại và các biến bổ sung `{inputs}` (ví dụ khi bị UNDETERMINED) |
| `PUT /v1/procedures/runs/{id}/documents` | `{documents:{key: true|false}}` (tự khai) |
| `POST /v1/procedures/runs/{id}:submit-preview` | Dựng `ticket` từ mẫu; trả `{preview_id, confirmation_token, ticket_preview:{title, summary, fields}, eligibility_note}` |
| `POST /v1/procedures/runs:submit-confirm` | `Idempotency-Key` + token → tạo ticket, phiên chuyển `SUBMITTED` |
| `POST /v1/procedures/runs/{id}:cancel` | Hủy phiên chưa gửi |
| `POST /v1/procedures/runs/{id}/follow-up-draft` | Khi `NEED_INFO`: `{notes?}` → bản nháp phản hồi. Gửi bằng `POST /v1/tickets/{ticket_id}/reply` hiện có, do sinh viên bấm |

Lỗi: `409 PROCEDURE_STATE`, `409 PROCEDURE_CONFLICT` (row_version), `422 PROCEDURE_FIELD_INVALID` (kèm `errors[{field,code}]`), `409 PROCEDURE_NOT_ELIGIBLE` (kèm chứng minh), `410 PREVIEW_EXPIRED`, `428 CONFIRMATION_REQUIRED`, `429 PROCEDURE_RATE` (≤ 10 phiên mới/ngày/người).

## 9. Nối vào chat (F5.6, **cần duyệt** vì đụng luồng chat)

- Tool chỉ đọc mới trong `agent/tools/registry.py`:
  - `procedure.suggest(text)`: trả gợi ý thủ tục;
  - `procedure.status()`: trả các phiên của tôi.
  - Cả hai có `is_write=False` và cờ `agent.procedures`.
- Khi câu hỏi có ý định làm thủ tục, chat hiện **thẻ thủ tục** (tên, các bước, nút "Bắt đầu cùng trợ lý"). Thẻ mở khung thủ tục ngay trong chat, dùng các API ở §8.
- Không có tool ghi nào cho model. Mọi ghi đi qua nút trên giao diện, theo preview và xác nhận.
- Khi chưa được duyệt, lối vào là trang `/services`: thêm nút "Làm cùng trợ lý" ở từng dịch vụ, và ô "Bạn cần làm thủ tục gì?" gọi `runs:from-text`.

## 10. Giao diện

- **Khung thủ tục** (`features/procedures/ProcedureRunner.tsx`), dùng ở `/services/procedures/[run_id]` và nhúng được trong chat:
  - thanh bước (Điều kiện → Thông tin → Giấy tờ → Xem trước → Đã gửi → Theo dõi);
  - bước Điều kiện hiện thẻ kết quả F2 (huy hiệu, cây chứng minh, ngưỡng). NOT_SATISFIED thì kèm "Bạn có thể: …" (đường thay thế khai trong playbook, ví dụ hỏi phòng ban qua `general-support`);
  - bước Thông tin là biểu mẫu sinh từ `fields`. Giá trị do trợ lý tách có viền "Trợ lý điền từ câu của bạn — kiểm tra lại", nút ✓ xác nhận từng giá trị, và tô đoạn tương ứng trong câu gốc (giữ ở bộ nhớ trình duyệt, không gửi lên lưu);
  - bước Xem trước hiện ticket như cán bộ sẽ thấy, cùng nút "Gửi hồ sơ" (nút chính duy nhất);
  - bước Theo dõi hiện dòng thời gian trạng thái ticket; khi `NEED_INFO` có nút "Soạn phản hồi cùng trợ lý".
- **Danh sách phiên** "Thủ tục của tôi" trên `/services`.
- Có tiếng Việt và tiếng Anh, theo nếp `campus-*`. Mọi nút ghi có trạng thái đang gửi và chống bấm đôi (idempotency phía máy chủ là lớp chính).

## 11. Bảo mật và quyền riêng tư

- Phiên chỉ chủ phiên thấy (404 với người khác). Cán bộ chỉ thấy ticket đã gửi, như hiện nay.
- Câu gốc gửi cho model đi qua `EgressPolicy.validate_and_minimize` (như `bootstrap/assistant_features.py`). Câu bị từ chối thì chỉ cho chọn thủ tục bằng tay.
- Prompt đặt câu của sinh viên trong vùng dữ liệu không tin cậy. Model không thấy dữ liệu hồ sơ.
- Không tool ghi, không tham số danh tính (`FORBIDDEN_ARGUMENTS`). Executor kiểm cờ lúc thực thi.
- Ngân sách D4: 300 lượt/ngày cho F5 (nhận diện + tách + soạn), tính qua gateway. Hết ngân sách thì chuyển sang chọn bằng tay, giao diện vẫn chạy đủ.

## 12. Quan sát

Phễu `procedure_runs_total{procedure, final_state}`, thời gian từ `STARTED` tới `SUBMITTED`, `procedure_extraction_rejected_total{field}` (giá trị trượt kiểm nguyên văn), `procedure_need_info_total{procedure}` (so với ticket tạo tay, để đo chất lượng hồ sơ khi có người dùng thật; hiện **chưa đo**).

## 13. Kiểm thử

| Loại | Nội dung |
|---|---|
| Đơn vị | Máy trạng thái: mọi cặp (trạng thái, hành động); bất biến một phiên một ticket; hết hạn |
| Playbook | Mọi tệp `config/procedures/*.toml` qua schema; tham chiếu F2 topic và `SERVICE_KINDS` hợp lệ |
| Gold nhận diện và tách | 5 × 50 câu do model viết, code kiểm nhãn trường là chuỗi con; đo đúng, sai, đủ; provider thật chạy một lần (trong ngân sách), lưu kết quả; CI dùng bản ghi của lần chạy đó |
| An toàn ghi | Test thứ tự bước (bỏ preview, token người khác, token hết hạn, gửi hai lần) |
| Tích hợp | Luồng đầy đủ với F2 giả: đủ điều kiện → gửi → cán bộ `NEED_INFO` → sinh viên phản hồi → `RESOLVED`; thông báo hộp thư đúng |
| Web | Vitest `ProcedureRunner` (từng bước, xác nhận giá trị tách, nút gửi bị khóa khi thiếu); `web_acceptance.mjs` chạy một thủ tục trọn vẹn với `student-local` và `staff-local` |
| Cờ | Ma trận F0 |

## 14. Rủi ro

| Rủi ro | Giảm |
|---|---|
| Điền sai thông tin | Kiểm nguyên văn; sinh viên xác nhận từng giá trị; đo tỉ lệ điền sai |
| Sinh viên tin là đã nộp chính thức với nhà trường | Ghi rõ "hồ sơ gửi tới hệ thống Campus 24/7 (dữ liệu mô phỏng)" chừng nào chưa nối hệ thống một cửa thật |
| Luật F2 chưa có cho một thủ tục | `eligibility: skipped` hiện rõ; không chặn |
| Model không sẵn sàng | Chọn tay, biểu mẫu tay vẫn đầy đủ |

## 15. Kế hoạch gói con

| Gói | Nội dung | Cỡ |
|---|---|---|
| F5.1 | Schema playbook + 5 playbook + 2 `SERVICE_KINDS` mới | S |
| F5.2 | Máy trạng thái + store + tạo ticket cùng giao dịch + idempotency | M |
| F5.3 | Kiểm điều kiện qua F2 (ánh xạ trường → biến) | S |
| F5.4 | Nhận diện và tách có kiểm nguyên văn + gold | M |
| F5.5 | API + theo dõi trạng thái + soạn phản hồi bổ sung | M |
| F5.6 | (cần duyệt) tool chỉ đọc và thẻ thủ tục trong chat | S |
| F5.7 | Giao diện `ProcedureRunner` + danh sách phiên + `/services` | L |
