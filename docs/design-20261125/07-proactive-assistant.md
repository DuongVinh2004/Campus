# F6 — Trợ lý chủ động nhắc việc

Phụ thuộc: `notifications.inbox`. Lấy tín hiệu từ F1, F3, F5, học liệu và lịch. Không gọi model (D4: 0 lượt).

## 1. Mục tiêu và giá trị

Sinh viên không phải nhớ mọi hạn. Hệ thống ghép các nguồn tín hiệu sẵn có của chính người đó (lịch thi, hạn xác nhận thông báo, thủ tục cần bổ sung, phiếu ra lớp sắp đóng, câu ôn tập đến hạn, quy định vừa đổi có liên quan tới khóa của mình) thành:

1. **"Việc cần làm hôm nay"** trên trang chủ, sắp theo độ gấp;
2. **lời nhắc chủ động** vào hộp thư đúng lúc, có giới hạn tần suất và giờ yên lặng;
3. **bản tin buổi sáng** (tùy chọn) gộp các việc ít gấp vào một thông báo.

Mỗi lời nhắc nói rõ **vì sao** ("Vì bạn có lịch thi môn X lúc 7:30 ngày mai") và có nút "Đã xong", "Nhắc lại sau".

## 2. Tiêu chí xong (kiểm được)

Mô phỏng 14 ngày trên học kỳ demo `DEMO-2026HK1-01` (44 tài khoản), đồng hồ tiêm vào, tín hiệu sinh có kịch bản:

1. Mỗi việc đến hạn được nhắc đúng theo chính sách (§5). So với một "oracle" viết riêng, đơn giản, tính từ cùng kịch bản: trùng 100 %.
2. Không người nào nhận quá **3 nhắc chủ động/ngày** (D7); bản tin và nhắc thi sẵn có không tính vào trần; xem §5.3.
3. Không nhắc trong 22:00–07:00 giờ Việt Nam, trừ mức `CRITICAL` (≤ 2 giờ trước hạn).
4. Không trùng sau khởi động lại. Tiêm khởi động lại ở mọi phút trong 24 giờ đầu mô phỏng, vẫn không có nhắc trùng.
5. "Đã xong" và "Nhắc lại sau" được tôn trọng: không nhắc lại trước giờ hẹn.
6. Tắt từng loại trong tùy chọn thì loại đó không còn nhắc. Tắt `proactive.nudges` thì job dừng và `/v1/nudges/*` trả 404; nhắc thi sẵn có (`reminders.exam`) vẫn chạy theo cờ riêng của nó.
7. Một lần chạy cho 30 000 người tổng hợp hết ≤ 30 s (đo, ghi evidence).

## 3. Hiện trạng liên quan

- `application/campus_ops/reminders.py`:
  - nhắc trước hạn với `DEFAULT_OFFSETS = (24h, 2h)`;
  - mỗi lần chạy chỉ gửi offset gần nhất đã qua, đánh dấu mọi offset đã qua, nên server tắt một ngày cũng chỉ gửi một nhắc;
  - idempotency `ops_reminders_sent(key)`;
  - tùy chọn `ops_reminder_prefs(subject_id, kind, enabled)`.
- `reminder_job.py`: `run_reminders`, `run_exit_ticket_reminders` chạy ở leader.
- Tín hiệu đã có dữ liệu: `ops_schedule` (lịch, thi), `ops_tickets` (`NEED_INFO`), phiếu ra lớp (`learning.exit_tickets`), lịch ôn SM-2 (`learning.practice`, `practice.py`), theo dõi việc cá nhân (`assistant.tracking`).

F6 **tổng quát hóa** mô-đun nhắc sẵn có. Nó không thay mô-đun đó: nhắc thi giữ nguyên hành vi và được ghép vào "Việc cần làm".

## 4. Mô hình

### 4.1 Nhà cung cấp tín hiệu

```python
class SignalProvider(Protocol):
    kind: str                                   # "EXAM", "ANNOUNCEMENT_ACK", "TICKET_NEED_INFO", ...
    feature: str                                # cờ F0 của nguồn; tắt thì provider bị bỏ qua
    def items(self, subject_ids: Sequence[str], now: datetime) -> Iterable[ActionItem]   # theo lô
@dataclass(frozen=True)
class ActionItem:
    key: str              # ổn định: "<kind>:<id nguồn>", ví dụ "ann-ack:<announcement_id>"
    subject_id: str
    kind: str
    title: str            # chữ cố định theo mẫu, không lấy từ model
    reason: str           # "Vì …"
    due_at: datetime | None
    link: str             # đường dẫn trong ứng dụng
    urgency_hint: Literal["CRITICAL","HIGH","NORMAL","LOW"] | None = None
    done: bool = False    # nguồn đã biết là xong (ví dụ đã xác nhận, đã nộp)
```

| `kind` | Nguồn | Cờ nguồn | Đến hạn | Xong khi |
|---|---|---|---|---|
| `EXAM` | `ops_schedule` (kind thi) | schedule.personal | giờ thi | qua giờ thi |
| `ANNOUNCEMENT_ACK` | `ann_deliveries` có `requires_ack`, chưa `acked_at` | announcements.inbox | `ack_deadline` | đã xác nhận |
| `ANNOUNCEMENT_URGENT_UNREAD` | `ann_deliveries` `URGENT`, chưa đọc quá 2 giờ | announcements.inbox | — | đã đọc |
| `TICKET_NEED_INFO` | `ops_tickets.status = NEED_INFO` | tickets.student | `updated_at + SLA_DAYS` | trạng thái khác |
| `PROCEDURE_DRAFT` | `proc_runs` chưa gửi, không hoạt động 3 ngày | agent.procedures | `expires_at` | gửi hoặc hủy |
| `EXIT_TICKET_CLOSING` | phiếu ra lớp mở, chưa nộp | learning.exit_tickets | giờ đóng | đã nộp |
| `PRACTICE_DUE` | câu ôn tới hạn theo SM-2 | learning.practice | `next_review_at` | đã ôn |
| `POLICY_CHANGE` | thay đổi F3 mức HIGH có đối tượng khớp người dùng (khóa, ngành) và nhãn `DEADLINE`/`NUMERIC` | policy.impact | — | đã xem |
| `TRACKED_ITEM` | việc trong `assistant.tracking` có hạn | assistant.tracking | hạn | xong |

### 4.2 Chấm mức gấp (tất định)

```
hours_left = (due_at - now) / 1h
urgency =
  CRITICAL  nếu due_at và hours_left ≤ 2
  HIGH      nếu due_at và hours_left ≤ 24, hoặc kind ∈ {ANNOUNCEMENT_URGENT_UNREAD, TICKET_NEED_INFO}
  NORMAL    nếu due_at và hours_left ≤ 72, hoặc kind ∈ {ANNOUNCEMENT_ACK, POLICY_CHANGE}
  LOW       còn lại (PRACTICE_DUE, PROCEDURE_DRAFT không gấp)
urgency = max(urgency, item.urgency_hint)
score = rank(urgency) * 1000 - min(hours_left, 999)       # để sắp "Việc cần làm"
```

## 5. Chính sách nhắc

### 5.1 Khi nào nhắc

| Mức | Thời điểm | Kênh |
|---|---|---|
| CRITICAL | ngay khi vào mức, một lần | hộp thư (bỏ qua giờ yên lặng) |
| HIGH | khi vào mức, một lần; nhắc lại sau 12 giờ nếu chưa xong, tối đa 2 lần | hộp thư |
| NORMAL | một lần | hộp thư, hoặc bản tin nếu người dùng bật bản tin |
| LOW | không nhắc riêng | chỉ trong bản tin và "Việc cần làm" |

Khóa idempotency: `nudge:<item.key>:<subject>:<stage>`, ghi vào `ops_reminders_sent`. `stage` thuộc `CRITICAL`, `HIGH-1`, `HIGH-2`, `NORMAL`. Áp đúng nguyên tắc "offset gần nhất đã qua" của `reminders.py`: vào thẳng CRITICAL thì không gửi bù HIGH.

### 5.2 Giờ yên lặng

22:00–07:00 `Asia/Ho_Chi_Minh`: mọi mức trừ CRITICAL bị hoãn tới 07:00. Lúc 07:00 nếu bản tin bật, các nhắc hoãn gộp vào bản tin.

### 5.3 Trần tần suất

≤ 3 nhắc chủ động/ngày/người (D7), đếm trên các mức HIGH và NORMAL được gửi riêng. Vượt trần thì phần còn lại chuyển vào bản tin hôm sau, hoặc "Việc cần làm" nếu bản tin tắt. CRITICAL không bị trần chặn nhưng vẫn được đếm. Nhắc thi cũ (`reminders.exam`) giữ hành vi riêng; khi `proactive.nudges` bật, provider `EXAM` **thay** job cũ để tránh nhắc đôi. Thứ tự chuyển giao như sau: job cũ dừng khi `proactive.nudges` bật, và dùng chung `ops_reminders_sent` với khóa cũ `exam:<id>` cho giai đoạn chuyển tiếp, nên không gửi lại.

### 5.4 Bản tin (`proactive.digest`)

07:00 mỗi ngày, một thông báo hộp thư "Hôm nay bạn có n việc", liệt kê ≤ 7 việc theo `score`, mỗi việc một dòng có liên kết. Không có việc thì không gửi. Khóa `digest:<subject>:<yyyy-mm-dd>`.

### 5.5 Tùy chọn người dùng

Mở rộng `ops_reminder_prefs` (đã có `subject_id, kind, enabled`):
- mỗi `kind` ở §4.1 một dòng;
- thêm `DIGEST` (mặc định tắt) và `QUIET_HOURS` (mặc định bật, không tắt được trong v1).

Mặc định bật: EXAM, ANNOUNCEMENT_ACK, ANNOUNCEMENT_URGENT_UNREAD, TICKET_NEED_INFO, EXIT_TICKET_CLOSING. Mặc định tắt: PRACTICE_DUE, PROCEDURE_DRAFT, POLICY_CHANGE, TRACKED_ITEM.

Hoãn và xong: bảng mới trong `campus-ops.sqlite3`:

```sql
CREATE TABLE IF NOT EXISTS nudge_states(subject_id TEXT NOT NULL, item_key TEXT NOT NULL,
  state TEXT NOT NULL,                 -- DONE | SNOOZED
  until TEXT, updated_at TEXT NOT NULL, PRIMARY KEY(subject_id, item_key));
CREATE TABLE IF NOT EXISTS nudge_daily(subject_id TEXT NOT NULL, day TEXT NOT NULL, sent INTEGER NOT NULL,
  PRIMARY KEY(subject_id, day));
```

`DONE` do người dùng bấm chỉ ẩn việc khỏi nhắc và khỏi "Việc cần làm". Nó **không** đổi dữ liệu nguồn: không coi là đã nộp hay đã xác nhận.

## 6. Job

`proactive_nudges` (leader, cờ `proactive.nudges`), chạy mỗi 5 phút:
1. lấy danh sách subject đang hoạt động (có phiên trong 60 ngày, hoặc có tín hiệu);
2. với từng lô 500 người, gọi mọi provider có cờ nguồn bật;
3. bỏ việc `done`, việc bị `DONE` hay `SNOOZED` còn hạn, và loại tắt trong tùy chọn;
4. chấm mức, xác định `stage`, áp giờ yên lặng và trần;
5. ghi thông báo và khóa idempotency trong **một** giao dịch mỗi lô (`store.tx()`, `store.notify()`).

`proactive_digest` (leader, cờ `proactive.digest`): kiểm mỗi 5 phút, chạy lúc 07:00 VN, hoặc lần chạy đầu sau 07:00 nếu server vừa bật lại; idempotent theo ngày.

## 7. API (`/v1/nudges`)

| Phương thức, đường dẫn | Mô tả |
|---|---|
| `GET /v1/nudges/today` | "Việc cần làm" của tôi, tính trực tiếp: `[{key, kind, title, reason, due_at, urgency, link}]` sắp theo `score`, ≤ 20 |
| `POST /v1/nudges/{item_key}:done` | Ẩn việc (idempotent) |
| `POST /v1/nudges/{item_key}:snooze` | `{hours ∈ {1, 3, 24}}` |
| `POST /v1/nudges/{item_key}:restore` | Bỏ `DONE` hoặc `SNOOZED` |
| `GET /v1/nudges/preferences` · `PUT …` | Bật tắt từng loại + bản tin; mở rộng `GET/PUT /v1/notifications/preferences` hiện có (cùng bảng) |

`item_key` được kiểm thuộc về người gọi: provider phải sinh ra nó cho subject đó. Nếu không thì 404.

## 8. Giao diện

- **Trang chủ** (`features/home`): khối "Việc cần làm hôm nay" ở đầu trang với sinh viên. Mỗi việc là thẻ gồm biểu tượng theo loại, tiêu đề, dòng "Vì…", đếm ngược ("còn 5 giờ"), nút chính (đi tới), menu "Đã xong", "Nhắc sau 1 giờ/3 giờ/ngày mai". Không có việc thì hiện câu "Bạn không có việc gấp nào hôm nay."
- **Thông báo**: thông báo do F6 sinh có nhãn "Nhắc việc" và hai nút nhanh (Đã xong / Nhắc sau) ngay trong `/notifications`.
- **Tùy chọn**: mục "Nhắc việc" trong trang thông báo, có công tắc theo loại và bản tin buổi sáng.
- Khả năng tiếp cận: đếm ngược có văn bản đầy đủ cho trình đọc màn hình ("còn 5 giờ, hạn 14:00 hôm nay").

## 9. Bảo mật và quyền riêng tư

- Chỉ dùng dữ liệu của chính người nhận, trong hệ thống. Không gửi ra kênh ngoài (email, Zalo) ở v1.
- Không có model, không có dữ liệu rời máy.
- `POLICY_CHANGE` chỉ dựa trên khóa và ngành, là thuộc tính hồ sơ. Không suy luận từ hội thoại.

## 10. Quan sát

`nudges_sent_total{kind,urgency}`, `nudges_deferred_total{reason=quiet|cap}`, `nudge_run_seconds`, `nudges_done_total{kind}`, `nudges_snoozed_total{kind}`. Tỉ lệ "đã xong sau nhắc" là chỉ số hữu ích với người dùng thật, hiện **chưa đo**.

## 11. Kiểm thử

| Loại | Nội dung |
|---|---|
| Đơn vị | Chấm mức; chọn stage; giờ yên lặng ở ranh giới 21:59, 22:00, 06:59, 07:00; trần; khóa idempotency |
| Mô phỏng 14 ngày | `tests/proactive/test_semester_simulation.py`: kịch bản tín hiệu sinh có seed trên 44 tài khoản; oracle độc lập; tiêu chí 1–5 |
| Chuyển giao nhắc thi | Bật `proactive.nudges` giữa chừng thì không nhắc đôi môn đã nhắc |
| Hiệu năng | 30 000 người tổng hợp |
| API và web | `today`, `done`, `snooze`, `restore`, tùy chọn; vitest khối "Việc cần làm" |
| Cờ | Tắt từng cờ nguồn thì provider tương ứng bị bỏ; ma trận F0 |

## 12. Rủi ro

| Rủi ro | Giảm |
|---|---|
| Nhắc quá nhiều, người dùng tắt hết | Trần 3/ngày; bản tin; mặc định tắt loại ít gấp |
| Nhắc sai do dữ liệu nguồn sai | Mỗi nhắc có "Vì…" và liên kết nguồn; người dùng báo sai qua phản hồi |
| Nhắc đôi với job cũ | Chuyển giao có kiểm soát (§5.3) và test |

## 13. Kế hoạch gói con

| Gói | Nội dung | Cỡ |
|---|---|---|
| F6.1 | Domain: `ActionItem`, chấm mức, chính sách, giờ yên lặng, trần + test | S |
| F6.2 | Provider cho nguồn đã có (EXAM, TICKET_NEED_INFO, EXIT_TICKET_CLOSING, PRACTICE_DUE, TRACKED_ITEM) | M |
| F6.3 | Provider cho nguồn mới (ANNOUNCEMENT_*, PROCEDURE_DRAFT, POLICY_CHANGE), làm khi F1, F5, F3 xong | S |
| F6.4 | Job + bản tin + chuyển giao nhắc thi + mô phỏng 14 ngày | M |
| F6.5 | API + trang chủ + tùy chọn | M |
