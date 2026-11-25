# F1 — Thông báo chính thức gửi đúng đối tượng

## 1. Mục tiêu và giá trị

Phòng ban, khoa và giảng viên gửi thông báo cho đúng nhóm người: toàn trường, khoa, khóa, lớp, lớp học phần hoặc vai trò. Thông báo có hạn hiệu lực, có ghi nhận đã đọc, và có nút xác nhận "đã đọc và hiểu" khi cần. Thông báo toàn trường còn hiệu lực được đưa vào kho tri thức, nên chatbot trả lời được "tuần này có gì cần nộp?" và trích đúng thông báo đó. Thông báo cá nhân (theo lớp, theo khoa) chỉ người nhận mới thấy.

Hiện hệ thống chỉ có hộp thư cá nhân do hệ thống tự gửi (nhắc thi, ticket, đặt phòng). Chưa có kênh nào để **con người** gửi thông báo có chủ đích tới một nhóm.

## 2. Tiêu chí xong (kiểm được)

1. Gửi đúng người. Có 40 bộ đối tượng gold do máy sinh trên danh bạ demo 44 tài khoản. Tập người nhận của từng bộ được tính bằng **hai cài đặt độc lập**: bộ giải đối tượng của F1 và một truy vấn tham chiếu viết riêng trong test. Hai tập phải trùng 100 %.
2. Không trùng, không sót khi sự cố. Dừng tiến trình giữa hai lô phát rồi chạy lại: mỗi người đúng 1 dòng giao và 1 thông báo hộp thư. Có test mô phỏng lỗi ở mọi ranh giới lô.
3. Hẹn giờ: thông báo hẹn giờ được phát trong vòng ≤ 60 s sau `publish_at`.
4. Phát 30 000 người nhận tổng hợp trong ≤ 15 s trên máy local. Số đo ghi vào evidence.
5. Hết hạn hoặc thu hồi: thông báo biến khỏi danh sách "đang hiệu lực" và phiên bản trong kho tri thức bị thu hồi. Một test RAG dùng provider giả xác nhận chatbot không còn trích dẫn nó.
6. Quyền:
   - sinh viên không đọc được thông báo không gửi cho mình (404);
   - giảng viên chỉ gửi được cho lớp học phần mình dạy;
   - thống kê theo nhóm < 5 người bị gộp thành "khác".
7. Cờ: tắt `announcements.publish` thì route soạn và gửi trả 404 và job hẹn giờ dừng, nhưng thông báo đã gửi vẫn đọc được qua `announcements.inbox`.

## 3. Phạm vi

**Trong phạm vi:**
- soạn, duyệt (tùy chọn hai người), hẹn giờ, gửi, sửa sau khi gửi (có phiên bản), thu hồi, hết hạn;
- đối tượng theo vai trò, khoa, khóa, lớp, lớp học phần, danh sách subject;
- hộp thư thông báo, đánh dấu đã đọc, xác nhận đã hiểu, nhắc người chưa xác nhận;
- thống kê cho người gửi;
- đồng bộ thông báo toàn trường vào kho tri thức.

**Ngoài phạm vi đợt này:**
- gửi qua email, SMS, Zalo hay web push (B2 chưa làm);
- tệp đính kèm tải lên mới; v1 chỉ cho liên kết tới tài liệu đã phát hành hoặc URL https;
- dịch tự động;
- thông báo khẩn có âm thanh.

## 4. Vai trò và quyền

| Hành động | STUDENT | LECTURER | SUPPORT_OFFICER | KNOWLEDGE_ADMIN | SYSTEM_ADMIN |
|---|---|---|---|---|---|
| Đọc thông báo gửi cho mình | ✓ | ✓ | ✓ | ✓ | ✓ |
| Đọc thông báo công khai khi chưa đăng nhập | khách ✓ | | | | |
| Soạn và gửi cho lớp học phần mình dạy | | ✓ | | | |
| Soạn và gửi theo khoa, khóa, lớp, vai trò | | | ✓ (đơn vị = `unit` của tài khoản) | ✓ | ✓ |
| Gửi toàn trường | | | ✓ (cần người thứ hai nếu bật `announcements.second_approval`) | ✓ | ✓ |
| Duyệt (người thứ hai) | | | ✓, không phải người soạn | ✓ | ✓ |
| Xem danh sách chưa xác nhận | | chỉ thông báo của mình | chỉ thông báo của mình hoặc đã duyệt | ✓ | ✓ |
| Thu hồi | | của mình | của mình | ✓ | ✓ |

Quyết định D2 ở [README](README.md) chốt bảng này. Kiểm quyền nằm ở application service. Kiểm "lớp mình dạy" dùng thành viên `offerings/{id}/members` có vai trò giảng viên trong repository học liệu.

## 5. Mô hình miền

### 5.1 Thực thể

```
Announcement
  id: uuid7                 code: "TB-2026-000123" (duy nhất, tăng dần theo năm)
  title: 5..200 ký tự       body: 1..10 000 ký tự, Markdown tập con (§5.4)
  category: ACADEMIC | EXAM | FINANCE | STUDENT_AFFAIRS | FACILITIES | EVENT | SYSTEM
  priority: NORMAL | IMPORTANT | URGENT
  issuer_unit: str          # "Phòng Đào tạo", "Khoa CNTT", "Lớp học phần <mã>"
  author_subject_id         revision: int (bắt đầu 1, tăng mỗi lần sửa đã gửi)
  audience: AudienceSpec    audience_hash: sha256(JSON chuẩn hóa)
  publish_at: datetime | None (None = gửi ngay khi xác nhận)
  expires_at: datetime      # bắt buộc; publish_at < expires_at ≤ publish_at + 365 ngày
  requires_ack: bool        ack_deadline: datetime | None (bắt buộc nếu requires_ack; ≤ expires_at)
  source_ref: {"document_no": "123/QĐ-ĐHXD"?, "url": "https://..."?}   # số văn bản gốc nếu có
  links: [{"label", "url" (https) | "knowledge_version_id"}] ≤ 10
  status: DRAFT | PENDING_APPROVAL | SCHEDULED | PUBLISHING | PUBLISHED | EXPIRED | WITHDRAWN
  knowledge_version_id: str | None   # khi đã đồng bộ vào kho
  created_at, updated_at, published_at, withdrawn_at, withdrawn_reason

AudienceSpec (mọi điều kiện trong một "nhóm" là AND; các nhóm là OR; tối đa 10 nhóm)
  groups: [{
    roles?: [STUDENT|LECTURER|SUPPORT_OFFICER|...],
    faculty_codes?: [str], cohorts?: ["66", ...], class_codes?: [str],
    offering_ids?: [uuid],   # lớp học phần trong học liệu
    subjects?: [uuid7] ≤ 500
  }]
  include_guests: bool      # chỉ hợp lệ khi có nhóm "toàn trường" (một nhóm rỗng = mọi tài khoản)
```

`cohort` lấy từ `class_code` theo quy tắc `^(\d{2})` (ví dụ `66IT1` → `66`), đúng định dạng danh bạ hiện có. Tài khoản không có `class_code` (cán bộ) không thuộc khóa nào.

### 5.2 Máy trạng thái

```
DRAFT ──publish-confirm──> (cần duyệt?) ──có──> PENDING_APPROVAL ──approve──> SCHEDULED|PUBLISHING
  │                               └─không──> SCHEDULED (publish_at tương lai) | PUBLISHING (ngay)
  │                                                 │ job tới giờ
  └─xóa nháp (đánh dấu deleted, không xóa dòng)      v
PENDING_APPROVAL ──reject──> DRAFT (kèm ghi chú)   PUBLISHING ──đủ lô──> PUBLISHED ──tới expires_at──> EXPIRED
SCHEDULED ──hủy hẹn──> DRAFT                       PUBLISHED|SCHEDULED ──withdraw-confirm──> WITHDRAWN
PUBLISHED ──revision-confirm──> PUBLISHED (revision+1)
```

Bất biến:
- `EXPIRED` và `WITHDRAWN` là trạng thái cuối.
- Đã rời `DRAFT` thì không đổi `audience`. Muốn đổi đối tượng thì thu hồi rồi gửi thông báo mới; điều này giữ đúng "ai đã được gửi" cho audit.
- Sửa sau khi gửi chỉ được đổi `title`, `body`, `links`, `expires_at` (chỉ kéo dài hoặc rút ngắn, không về quá khứ) và `ack_deadline`. Mỗi lần sửa lưu một dòng trong `ann_revisions`.
- Duyệt yêu cầu người duyệt khác người soạn (`approver != author`). Cùng một người thì `409 SAME_PERSON_APPROVAL`.

Khi nào cần duyệt: cờ `announcements.second_approval` bật **và** thỏa ít nhất một điều kiện: (a) có nhóm toàn trường; (b) số người nhận ước tính > 500; (c) `priority = URGENT`.

### 5.3 Giải đối tượng

Port mới `ports/directory.py`:

```python
class RecipientDirectoryPort(Protocol):
    def recipients(self, spec: AudienceSpec, *, at: datetime) -> Iterator[Recipient]   # theo lô 1000, thứ tự subject_id
    def count(self, spec: AudienceSpec) -> AudienceCount       # tổng + phân rã theo khoa/khóa/vai trò (k ≥ 5)
@dataclass(frozen=True)
class Recipient: subject_id: str; roles: tuple[str, ...]; faculty_code: str|None; cohort: str|None; class_code: str|None
```

Cài đặt local `infrastructure/identity/directory_recipients.py` hợp nhất bốn nguồn:
- `LocalDirectoryIdentityAdapter.directory()["accounts"]` (44 tài khoản);
- tài khoản owner, student và staff local;
- thành viên lớp học phần từ repository học liệu (khi `learning.core` bật);
- sau này là OIDC accounts (`oidc.sqlite3`).

Port này **không** đổi `IdentityContext`. Phạm vi truy hồi RAG vẫn như cũ (`local_directory.py:107`).

Ảnh chụp đối tượng: khi chuyển sang `PUBLISHING`, danh sách người nhận được ghi vào `ann_deliveries`. Đó là sự thật về "ai được gửi". Job `announcement_reconcile` chạy mỗi giờ: với thông báo còn hiệu lực, nó bổ sung người **mới** khớp đối tượng (ví dụ sinh viên mới vào lớp), không bao giờ gỡ người đã nhận. Mỗi lần bổ sung ghi audit.

### 5.4 Nội dung

- Markdown tập con: đoạn văn, tiêu đề cấp 3–4, danh sách, in đậm, in nghiêng, liên kết. Không có HTML thô, ảnh hay bảng (v1).
- Hiển thị qua bộ dựng sẵn có của chat (commit `e7d969c` dựng đoạn, danh sách, mục) để giống giao diện câu trả lời.
- Liên kết chỉ `https:`. Giao diện hiện tên miền bên cạnh liên kết. Liên kết `knowledge_version_id` phải trỏ tới phiên bản đang phát hành; kiểm lúc preview.
- Mỗi lần lưu, nội dung qua `PromptInjectionDetector` (`agent/guardrails/prompt_injection.py`) với `TrustDomain.RETRIEVED_EVIDENCE`. Bị gắn cờ thì vẫn gửi được nhưng **không** đồng bộ vào kho tri thức, và người soạn thấy cảnh báo.
- Không cho số CCCD, số tài khoản ngân hàng hay mật khẩu trong nội dung. Dùng bộ lọc tất định sẵn có của `EgressPolicy` để cảnh báo (không chặn cứng, vì có thể là số hiệu văn bản).

## 6. Lưu trữ

Lưu trong tệp `campus-ops.sqlite3` hiện có, để phát thông báo và ghi `ops_notifications` nằm **cùng giao dịch** (`CampusOpsStorePort.tx()`, `notify()`). Bảng mới chỉ được thêm vào (additive); `CampusOpsStore.schema_version` lên 2. Không cần migration Postgres.

```sql
CREATE TABLE IF NOT EXISTS ann_announcements(
  id TEXT PRIMARY KEY, code TEXT NOT NULL UNIQUE, title TEXT NOT NULL, body TEXT NOT NULL,
  category TEXT NOT NULL, priority TEXT NOT NULL, issuer_unit TEXT NOT NULL,
  author_subject_id TEXT NOT NULL, audience TEXT NOT NULL, audience_hash TEXT NOT NULL,
  publish_at TEXT, expires_at TEXT NOT NULL, requires_ack INTEGER NOT NULL DEFAULT 0, ack_deadline TEXT,
  source_ref TEXT NOT NULL DEFAULT '{}', links TEXT NOT NULL DEFAULT '[]',
  status TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 1, knowledge_version_id TEXT,
  injection_flagged INTEGER NOT NULL DEFAULT 0, publish_cursor TEXT,          -- subject_id cuối đã phát (lô)
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL, published_at TEXT, withdrawn_at TEXT, withdrawn_reason TEXT,
  deleted_at TEXT, row_version INTEGER NOT NULL DEFAULT 1);
CREATE INDEX IF NOT EXISTS ann_status_publish ON ann_announcements(status, publish_at);
CREATE INDEX IF NOT EXISTS ann_author ON ann_announcements(author_subject_id, created_at DESC);
CREATE TABLE IF NOT EXISTS ann_revisions(
  announcement_id TEXT NOT NULL REFERENCES ann_announcements(id), revision INTEGER NOT NULL,
  title TEXT NOT NULL, body TEXT NOT NULL, links TEXT NOT NULL, expires_at TEXT NOT NULL, ack_deadline TEXT,
  change_note TEXT NOT NULL, material INTEGER NOT NULL, actor_subject_id TEXT NOT NULL, at TEXT NOT NULL,
  PRIMARY KEY(announcement_id, revision));
CREATE TABLE IF NOT EXISTS ann_deliveries(
  announcement_id TEXT NOT NULL REFERENCES ann_announcements(id), recipient_subject_id TEXT NOT NULL,
  faculty_code TEXT, cohort TEXT, role TEXT NOT NULL,                       -- để thống kê, không có tên
  delivered_at TEXT NOT NULL, read_at TEXT, read_revision INTEGER, acked_at TEXT, acked_revision INTEGER,
  added_by TEXT NOT NULL DEFAULT 'PUBLISH',                                  -- PUBLISH | RECONCILE
  PRIMARY KEY(announcement_id, recipient_subject_id));
CREATE INDEX IF NOT EXISTS ann_delivery_recipient ON ann_deliveries(recipient_subject_id, delivered_at DESC);
CREATE TABLE IF NOT EXISTS ann_approvals(
  id TEXT PRIMARY KEY, announcement_id TEXT NOT NULL, approver_subject_id TEXT NOT NULL,
  verdict TEXT NOT NULL, note TEXT NOT NULL, at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ann_previews(
  id TEXT PRIMARY KEY, actor_subject_id TEXT NOT NULL, action TEXT NOT NULL, announcement_id TEXT NOT NULL,
  payload_hash TEXT NOT NULL, row_version INTEGER NOT NULL, expires_at TEXT NOT NULL, used_at TEXT);
CREATE TABLE IF NOT EXISTS ann_idempotency(
  actor_subject_id TEXT NOT NULL, key TEXT NOT NULL, result TEXT NOT NULL, at TEXT NOT NULL,
  PRIMARY KEY(actor_subject_id, key));
```

Không xóa dòng nào. Xóa nháp là đặt `deleted_at`. Mọi thay đổi trạng thái gọi `store.audit()` vào `ops_audit` với `action = "ANNOUNCEMENT_<VERB>"`.

**Phát theo lô.** Trạng thái `PUBLISHING` có con trỏ `publish_cursor`. Mỗi lô 1000 người là một giao dịch `IMMEDIATE`, gồm:
1. `INSERT OR IGNORE` vào `ann_deliveries`;
2. với các dòng **thực sự mới chèn** (đếm bằng `changes()`), ghi một `ops_notifications` (`kind=ANNOUNCEMENT`, `link=/announcements/<id>`);
3. cập nhật `publish_cursor`.

Lô cuối chuyển `PUBLISHED`. Sự cố giữa chừng thì job tiếp tục từ con trỏ. Khóa chính `(announcement_id, recipient)` chặn trùng.

Hộp thư: thông báo `URGENT` có `ops_notifications.title` tiền tố "[Khẩn] ". Mọi mức đều dùng cùng hộp thư hiện có, nên huy hiệu chưa đọc ở AppShell hoạt động sẵn.

## 7. API

Mọi route thuộc tiền tố `/v1/announcements`, được thêm vào `ALLOWED_API_PREFIXES`. Phản hồi có dữ liệu cá nhân mang `Cache-Control: no-store`. Lỗi theo `create_problem_details`.

### 7.1 Người soạn và người duyệt

| Phương thức, đường dẫn | Mô tả | Cờ |
|---|---|---|
| `POST /v1/announcements/drafts` | Tạo nháp. Body: title, body, category, priority, audience, publish_at, expires_at, requires_ack, ack_deadline, source_ref, links. Trả `{id, code, row_version}` | publish |
| `PUT /v1/announcements/{id}` | Sửa nháp. Body như trên + `row_version`. Sai version thì `409 ANNOUNCEMENT_CONFLICT` | publish |
| `POST /v1/announcements/{id}:audience-preview` | `{total, by_role:[{role,n}], by_faculty:[…], by_cohort:[…], guests_included, warnings:["LARGE_AUDIENCE","EMPTY_AUDIENCE"]}`. Nhóm < 5 gộp vào "khác". Không trả tên | publish |
| `POST /v1/announcements/{id}:publish-preview` | Kiểm toàn bộ (quyền gửi tới từng nhóm, thời gian, liên kết, nội dung). Trả `{preview_id, confirmation_token, expires_at(+10'), summary:{total, publish_at, needs_approval, knowledge_sync}, warnings}` | publish |
| `POST /v1/announcements:publish-confirm` | `Idempotency-Key` + `{preview_id, confirmation_token}`. Trả trạng thái mới | publish |
| `POST /v1/announcements/{id}:approve` / `:reject` | Người thứ hai. `{note ≥ 8 ký tự, row_version}` | second_approval |
| `POST /v1/announcements/{id}:unschedule` | `SCHEDULED → DRAFT` | publish |
| `POST /v1/announcements/{id}:revision-preview` → `:revision-confirm` | Sửa sau khi gửi. `{title?, body?, links?, expires_at?, ack_deadline?, change_note, material: bool}`. `material=true` thì gửi thêm một thông báo hộp thư "Đã cập nhật" cho người đã nhận | publish |
| `POST /v1/announcements/{id}:withdraw-preview` → `:withdraw-confirm` | `{reason ≥ 10 ký tự}`. Thu hồi; nếu có `knowledge_version_id` thì thu hồi phiên bản trong kho (§8) | publish |
| `GET /v1/announcements/authored?status=&cursor=&limit=` | Thông báo tôi soạn hoặc tôi duyệt | publish |
| `GET /v1/announcements/approvals?cursor=` | Hàng đợi chờ duyệt mà tôi được duyệt | second_approval |
| `GET /v1/announcements/{id}/stats` | `{delivered, read, acked, read_rate, by_faculty:[…], by_cohort:[…], timeline:[{hour, reads}]}` (k ≥ 5) | publish |
| `GET /v1/announcements/{id}/pending-acks?cursor=` | Chỉ khi `requires_ack`; chỉ người soạn, người duyệt hoặc quản trị. Trả `{subject_id, display_name, class_code}`. Mỗi lần xem ghi audit `ANNOUNCEMENT_PENDING_ACKS_VIEWED` | publish |

### 7.2 Người nhận

| Phương thức, đường dẫn | Mô tả | Cờ |
|---|---|---|
| `GET /v1/announcements/mine?filter=unread|active|all&category=&cursor=&limit=20` | Thông báo gửi cho tôi; mặc định `active` (PUBLISHED và chưa hết hạn), mới nhất trước, URGENT chưa đọc lên đầu | inbox |
| `GET /v1/announcements/{id}` | Chi tiết (phiên bản mới nhất + lịch sử sửa nếu có). Lần đầu mở đặt `read_at`, `read_revision`. Không phải người nhận thì `404` | inbox |
| `POST /v1/announcements/{id}/ack` | Idempotent; ghi `acked_at`, `acked_revision`. Phiên bản có `material=true` mới hơn bản đã xác nhận thì giao diện yêu cầu xác nhận lại | inbox |
| `GET /v1/announcements/public?cursor=` | Thông báo có `include_guests`, không cần đăng nhập | inbox |

### 7.3 Mã lỗi

| HTTP | code | Khi nào |
|---|---|---|
| 403 | `ANNOUNCEMENT_FORBIDDEN_AUDIENCE` | Người soạn không được gửi tới một nhóm trong đối tượng; phản hồi chỉ ra nhóm đó |
| 404 | `ANNOUNCEMENT_NOT_FOUND` | Không tồn tại hoặc không phải người nhận |
| 409 | `ANNOUNCEMENT_CONFLICT` | `row_version` cũ |
| 409 | `ANNOUNCEMENT_STATE` | Hành động không hợp lệ ở trạng thái hiện tại |
| 409 | `SAME_PERSON_APPROVAL` | Người soạn tự duyệt |
| 410 | `PREVIEW_EXPIRED` | Preview hết hạn hoặc đã dùng |
| 422 | `ANNOUNCEMENT_INVALID` | Kèm `errors: [{field, code}]`: `TITLE_LENGTH`, `EXPIRY_RANGE`, `ACK_DEADLINE`, `LINK_SCHEME`, `LINK_VERSION_NOT_PUBLISHED`, `AUDIENCE_EMPTY`, `AUDIENCE_TOO_MANY_SUBJECTS`… |
| 429 | `ANNOUNCEMENT_RATE` | > 20 thông báo/ngày/người soạn, hoặc > 3 thông báo URGENT/ngày/đơn vị |

## 8. Đồng bộ vào kho tri thức (`announcements.knowledge_sync`)

Chỉ đồng bộ thông báo **công khai**: có nhóm toàn trường **và** `include_guests=true`, hoặc toàn bộ sinh viên. Lý do: truy hồi hiện chỉ dùng phân loại `PUBLIC` (`LocalScope` trong `knowledge_platform.py`). Đưa thông báo theo lớp vào kho chung sẽ làm người ngoài lớp thấy được.

Luồng:
1. Khi chuyển `PUBLISHED`, sinh tệp văn bản UTF-8 `announcement-<code>-r<revision>.txt`. Nội dung: tiêu đề, đơn vị ban hành, số văn bản gốc (nếu có), ngày hiệu lực `[publish_at, expires_at)` và thân bài.
2. Gọi `KnowledgePlatform.upload()` như luồng hiện có, vì luồng này nhận `.txt` (`application/knowledge/platform.py:61`). Metadata gồm `source_kind=ANNOUNCEMENT`, `effective_from`, `effective_to`, `origin_ref=<announcement id>`.
3. Duyệt:
   - Người gửi là `KNOWLEDGE_ADMIN` thì tự phê duyệt theo luồng sẵn có.
   - Người khác thì phiên bản vào hàng đợi duyệt `/knowledge/documents`, như tài liệu của `KNOWLEDGE_CONTRIBUTOR` (cần người thứ hai).
   - Thông báo vẫn gửi tới người nhận ngay, không chờ bước duyệt kho.
4. Sửa có `material=true`: tải phiên bản mới, quan hệ `supersedes` với phiên bản cũ.
5. Hết hạn hoặc thu hồi: gọi `revoke` (`/v1/knowledge/platform/documents/{version_id}/revoke`). Job `announcement_expiry` chạy mỗi 5 phút.
6. Nội dung bị `injection_flagged` thì không đồng bộ (§5.4).

Đây **không** phải thay đổi lõi RAG. Thông báo chỉ là thêm một nguồn văn bản đi qua đúng luồng nạp, kiểm và phát hành hiện có. Chỉ số truy hồi được kiểm lại bằng `release_check` như mọi release khác.

Tùy chọn F1.8 (`announcements.chat_tool`, mặc định tắt): một tool chỉ đọc `announcements.list_mine` cho agent chat, để trả lời "có thông báo gì cho em?" bằng thông báo cá nhân. Đây là thêm tool vào luồng chat nên **cần chủ dự án duyệt** trước khi làm.

## 9. Việc nền (chạy ở tiến trình leader)

| Job | Chu kỳ | Việc | Cờ |
|---|---|---|---|
| `announcement_publisher` | 30 s | `SCHEDULED` tới giờ → `PUBLISHING`; tiếp tục mọi `PUBLISHING` dở theo lô | announcements.publish |
| `announcement_reconcile` | 60 phút | Bổ sung người mới khớp đối tượng cho thông báo còn hiệu lực | announcements.publish |
| `announcement_expiry` | 5 phút | `PUBLISHED` quá `expires_at` → `EXPIRED`; thu hồi bản trong kho | announcements.publish |
| `announcement_ack_reminders` | 15 phút | Người chưa xác nhận: nhắc 24 giờ và 2 giờ trước `ack_deadline`, dùng `reminders.py` (`Candidate`, `ops_reminders_sent`, khóa `ann-ack:<id>:<subject>`), tôn trọng `ops_reminder_prefs` kind `ANNOUNCEMENT_ACK` | announcements.publish |

Mọi job chạy trong `start_jobs()` của `knowledge_platform.py` và được bọc cờ theo F0 §4.7.

## 10. Giao diện

| Màn hình | Đường dẫn | Ai | Nội dung chính |
|---|---|---|---|
| Hộp thông báo | `/announcements` | mọi người đăng nhập | Thẻ "Đang hiệu lực / Chưa đọc / Tất cả"; lọc theo loại; mỗi mục có huy hiệu mức, đơn vị, hạn, trạng thái xác nhận; khẩn chưa đọc nổi lên đầu |
| Chi tiết | `/announcements/[id]` | người nhận | Thân bài dựng như câu trả lời chat; số văn bản gốc; liên kết (hiện tên miền); "Cập nhật lúc…" với lịch sử; nút "Tôi đã đọc và hiểu" khi `requires_ack` |
| Soạn thảo | `/announcements/manage/new`, `/announcements/manage/[id]` | người soạn | Trình soạn có xem trước; bộ dựng đối tượng dạng chip (vai trò, khoa, khóa, lớp, lớp học phần) kèm số người nhận cập nhật trực tiếp (gọi `audience-preview`, debounce 400 ms); chọn giờ gửi, hạn; bật xác nhận; khối preview cuối liệt kê cảnh báo |
| Quản lý | `/announcements/manage` | người soạn, người duyệt | Danh sách theo trạng thái; hàng đợi duyệt; thống kê (biểu đồ cột đọc theo giờ, tỉ lệ đọc và xác nhận theo khoa/khóa); danh sách chưa xác nhận |
| Công khai | `/announcements/public` | khách | Danh sách thông báo công khai |
| Trang chủ | `/` | sinh viên | Thẻ "Thông báo mới" (3 mục chưa đọc) |
| Học liệu | trang lớp học phần | giảng viên | Nút "Gửi thông báo cho lớp", mở trình soạn với đối tượng điền sẵn `offering_ids=[id]` |

Ngoài ra:
- Điều hướng: thêm `nav.announcements` (biểu tượng `Megaphone`), cờ `announcements.inbox`. Thêm `nav.announcementsManage` cho người soạn, cờ `announcements.publish`.
- Có tiếng Việt và tiếng Anh (`lib/i18n`). Trạng thái rỗng, đang tải, lỗi và hết quyền theo nếp `campus-*`.
- Khả năng tiếp cận: mức khẩn không chỉ báo bằng màu (có chữ "Khẩn"); nút xác nhận có `aria-describedby` tới hạn xác nhận.

## 11. Quan sát

Bộ đếm `announcements_published_total{category,priority}`, `announcement_deliveries_total`, `announcement_publish_batch_seconds` (histogram), `announcement_publish_stuck` (gauge: số thông báo ở `PUBLISHING` quá 5 phút, có cảnh báo), `announcement_knowledge_sync_failures_total`. Log không chứa nội dung thông báo hay danh sách người nhận, chỉ id, mã và số đếm.

## 12. Kiểm thử và nghiệm thu

| Loại | Nội dung |
|---|---|
| Đơn vị (domain) | Máy trạng thái: mọi cặp (trạng thái, hành động) hợp lệ và không hợp lệ; kiểm thời gian; chuẩn hóa `audience_hash`; quy tắc cần duyệt; quy tắc cohort từ `class_code` |
| Gold giải đối tượng | `tests/announcements/fixtures/audiences.jsonl`: 40 bộ do máy sinh (tổ hợp vai trò/khoa/khóa/lớp/subject, có OR giữa nhóm và trường hợp rỗng). Gold tính bằng truy vấn SQL tham chiếu trên bảng nạp từ danh bạ, độc lập với mã giải. Yêu cầu trùng 100 % |
| Quyền | Ma trận vai trò × hành động (bảng §4), gồm giảng viên gửi cho lớp không dạy (403), cán bộ gửi ngoài đơn vị theo chính sách |
| Bền vững | Tiêm lỗi sau lô k (k = 0..n); chạy lại; kiểm đúng 1 delivery và 1 notification mỗi người |
| Hiệu năng | 30 000 người tổng hợp; đo thời gian phát; ghi `evals/results/announcements-<date>/perf.json` |
| Đồng bộ kho | Provider giả: sau khi gửi thông báo công khai, câu hỏi về nội dung trả lời có trích dẫn; sau thu hồi thì từ chối hoặc không trích |
| API | Hợp đồng OpenAPI xuất bằng script giống `export_learning_openapi.py`; test 422 theo từng mã trường |
| Web | Vitest cho bộ dựng đối tượng, chi tiết, nút xác nhận; `web_acceptance.mjs`: cán bộ gửi tới lớp `66IT1` → sinh viên `66IT1` thấy, `66IT2` không thấy |
| Cờ | Ma trận F0 cho 4 cờ `announcements.*` |

Bằng chứng nghiệm thu là các ca do máy sinh, có gold tính độc lập bằng code. Khả năng dùng với người dùng thật: chưa đo.

## 13. Rủi ro

| Rủi ro | Giảm |
|---|---|
| Gửi nhầm đối tượng | Preview số người nhận theo nhóm; người thứ hai duyệt cho đối tượng lớn; thu hồi kèm thông báo "đã thu hồi" |
| Thông báo dồn dập làm người dùng bỏ qua | Giới hạn tần suất (429); F6 gộp vào bản tin |
| Danh bạ demo khác dữ liệu thật | Port tách biệt; khi có OIDC/API học vụ chỉ đổi adapter |
| Kho tri thức có nhiều bản thông báo ngắn hạn | Chỉ đồng bộ thông báo công khai; tự thu hồi khi hết hạn; theo dõi số bản đang hiệu lực |
| SQLite tranh khóa khi phát lớn | Lô 1000; giao dịch ngắn; job chỉ ở leader |

## 14. Kế hoạch gói con

| Gói | Nội dung | Cỡ |
|---|---|---|
| F1.1 | Domain: thực thể, máy trạng thái, kiểm hợp lệ, quy tắc duyệt; test | S |
| F1.2 | `RecipientDirectoryPort` + adapter local + gold 40 bộ | M |
| F1.3 | Schema campus-ops v2 + repository + phát theo lô bền vững | M |
| F1.4 | API soạn, preview, confirm, duyệt, thu hồi, sửa + API người nhận + OpenAPI | M |
| F1.5 | Job publisher, reconcile, expiry, ack reminders + cờ | S |
| F1.6 | Đồng bộ kho tri thức + test RAG giả | M |
| F1.7 | Web: hộp thông báo, chi tiết, soạn thảo, quản lý, thống kê, trang chủ, học liệu | L |
| F1.8 | (cần duyệt) tool chat `announcements.list_mine` | S |
