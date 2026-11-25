# F7 — Gia sư hỏi gợi mở và bản đồ nắm vững của lớp

Phụ thuộc: `learning.practice`, và `learning.ai_explanations` cho phần dùng model. Hai cờ riêng là `learning.tutor` và `learning.mastery_map`; bản đồ nắm vững chạy được **không cần model**.

## 1. Mục tiêu và giá trị

- **Sinh viên**: khi làm sai câu ôn tập, gia sư không đưa đáp án ngay. Nó đưa **thang gợi ý** gồm 3 bậc:
  1. chỉ ra trang và hỏi một câu dẫn dắt;
  2. thu hẹp vào đoạn cụ thể;
  3. giải thích đầy đủ có trích dẫn.

  Mọi gợi ý bám theo trang học liệu giảng viên đã duyệt. Hệ thống ước lượng mức nắm vững từng **khái niệm** và tự xếp lịch ôn.
- **Giảng viên**: trước buổi học thấy bản đồ "lớp đang hổng khái niệm nào": tỉ lệ nắm vững theo khái niệm, câu sai nhiều nhất, phương án nhiễu hay bị chọn. Bản đồ chỉ hiện khi nhóm ≥ 5 sinh viên.

## 2. Hiện trạng liên quan

- `application/learning/practice.py`:
  - câu hỏi chỉ được trích trang nó dẫn (`verify_citation`, `MIN_QUOTE_CHARS = 12`);
  - chấm chính xác bằng code, không model nào chấm;
  - lặp ngắt quãng SM-2 rút gọn (`EASE_START 2.5`, `MAX_INTERVAL_DAYS 365`).
- `practice_sets.py`:
  - thống kê lớp chỉ khi ≥ `MIN_CLASS_FOR_STATS = 5`;
  - trích dẫn chỉ hiện **sau** khi trả lời;
  - có route `practice-sets/{id}/stats`, `practice-items/{id}/attempts`, `practice-sets/{id}/session`.
- Học liệu có `page-explanations` dùng model qua `configure_learning_ai`. Model này chỉ chạy khi runtime có generation và `CAMPUS_LEARNING_AI_ENABLED=true` (`bootstrap/learning.py:254`), có `LearningExplanationVerifier`.
- Lưu trữ học liệu nằm trên **Postgres**, migration mới nhất là `0032_learning_practice.py`. Có guard bắt duyệt hash migration.
- **Chưa có** khái niệm (concept) gắn với câu hỏi hay trang.

## 3. Tiêu chí xong (kiểm được)

1. **Ước lượng nắm vững (BKT).**
   - Cài đặt khớp công thức tham chiếu trên 50 chuỗi trả lời tính tay, sai số < 1e-9.
   - Trên 2 000 sinh viên mô phỏng có mức nắm vững thật đã biết (sinh theo mô hình BKT với tham số ngẫu nhiên có seed), AUC dự đoán câu kế tiếp ≥ 0,75 và độ hiệu chuẩn (ECE) ≤ 0,05.
   - Gold là tham số sinh, nên đúng theo cách tạo.
2. **An toàn gợi ý.** Có 300 lần sinh gợi ý (100 câu × 3 bậc) bằng provider thật, chạy một lần, có trần.
   - Sau bộ lọc code, **0** gợi ý bậc 1–2 lộ đáp án. "Lộ" nghĩa là chứa văn bản phương án đúng, hoặc đáp án ngắn đã chuẩn hóa.
   - **100 %** gợi ý được hiện có trích dẫn nguyên văn từ trang đã duyệt.
   - Tỉ lệ đạt bộ lọc ngay lần đầu ≥ 80 %. Gợi ý trượt thì thay bằng gợi ý mẫu tất định (§6.4).
3. Thống kê bản đồ ẩn ở mọi nhóm < 5 sinh viên. Test quét mọi điểm API của bản đồ với lớp 4 người: không có số liệu từng người.
4. Giảng viên tắt gia sư theo lớp: sinh viên lớp đó không gọi được (403 `TUTOR_DISABLED_FOR_OFFERING`), ôn tập thường vẫn chạy.
5. Trần chi phí: ≤ 30 gợi ý có model/ngày/sinh viên và ≤ 500/ngày toàn hệ thống (D4). Hết thì dùng gợi ý mẫu tất định. Có test.

## 4. Phạm vi

**Trong phạm vi:**
- khái niệm theo lớp học phần, do giảng viên duyệt (model có thể đề xuất);
- gắn khái niệm cho câu hỏi và trang;
- BKT theo (sinh viên, khái niệm);
- thang gợi ý 3 bậc;
- hội thoại gợi mở ngắn (≤ 6 lượt mỗi câu);
- bản đồ nắm vững của lớp;
- phân tích phương án nhiễu;
- gợi ý thứ tự ôn theo khái niệm yếu.

**Ngoài phạm vi:**
- chấm tự luận bằng model (trái nguyên tắc của `practice.py`);
- nhận xét từng cá nhân cho giảng viên (chỉ có số liệu gộp; giảng viên vẫn xem được lượt làm theo quyền học liệu hiện có);
- dự đoán điểm thi.

## 5. Mô hình dữ liệu (Postgres, migration `0033_learning_concepts_tutor.py`; **cần duyệt hash** theo guard)

```sql
CREATE TABLE learning_concepts(
  id UUID PRIMARY KEY, tenant_id TEXT NOT NULL, offering_id UUID NOT NULL,
  label TEXT NOT NULL CHECK (char_length(label) BETWEEN 2 AND 120), description TEXT,
  status TEXT NOT NULL CHECK (status IN ('PROPOSED','APPROVED','RETIRED')),
  origin TEXT NOT NULL CHECK (origin IN ('LECTURER','MODEL_CANDIDATE')),
  created_by TEXT NOT NULL, approved_by TEXT, created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL,
  UNIQUE(offering_id, label));
CREATE TABLE learning_concept_links(
  concept_id UUID NOT NULL REFERENCES learning_concepts(id),
  target_kind TEXT NOT NULL CHECK (target_kind IN ('PRACTICE_ITEM','PAGE')),
  target_id TEXT NOT NULL,                      -- practice item id | "<material_version_id>:<page>"
  weight REAL NOT NULL DEFAULT 1.0 CHECK (weight > 0 AND weight <= 1),
  PRIMARY KEY(concept_id, target_kind, target_id));
CREATE TABLE learning_mastery(
  tenant_id TEXT NOT NULL, offering_id UUID NOT NULL, student_subject_id TEXT NOT NULL, concept_id UUID NOT NULL,
  p_known DOUBLE PRECISION NOT NULL, attempts INTEGER NOT NULL, correct INTEGER NOT NULL,
  last_attempt_at TIMESTAMPTZ NOT NULL, model_version TEXT NOT NULL,
  PRIMARY KEY(offering_id, student_subject_id, concept_id));
CREATE TABLE learning_tutor_settings(
  offering_id UUID PRIMARY KEY, tutor_enabled BOOLEAN NOT NULL DEFAULT FALSE,
  reveal_after_attempts INTEGER NOT NULL DEFAULT 2 CHECK (reveal_after_attempts BETWEEN 1 AND 5),
  model_hints_enabled BOOLEAN NOT NULL DEFAULT FALSE, updated_by TEXT NOT NULL, updated_at TIMESTAMPTZ NOT NULL);
CREATE TABLE learning_tutor_turns(
  id UUID PRIMARY KEY, offering_id UUID NOT NULL, student_subject_id TEXT NOT NULL, practice_item_id TEXT NOT NULL,
  attempt_no INTEGER NOT NULL, level INTEGER NOT NULL CHECK (level BETWEEN 1 AND 3),
  origin TEXT NOT NULL CHECK (origin IN ('MODEL','TEMPLATE')),
  hint_text TEXT NOT NULL, quote_page TEXT NOT NULL, quote_sha256 TEXT NOT NULL,
  student_reply_sha256 TEXT,                     -- chỉ băm; văn bản trả lời gợi mở không lưu lâu
  created_at TIMESTAMPTZ NOT NULL, expires_at TIMESTAMPTZ NOT NULL);   -- 30 ngày
CREATE INDEX ON learning_tutor_turns(student_subject_id, created_at);
```

Ngoài migration này, mọi lưu trữ khác giữ nguyên. Trả lời gợi mở dạng tự do của sinh viên chỉ giữ trong phiên (bộ nhớ hoặc bảng tạm có TTL 24 giờ), để làm ngữ cảnh cho lượt kế tiếp. Trong bảng lâu dài chỉ có băm.

## 6. Thiết kế

### 6.1 Khái niệm

- Giảng viên tạo khái niệm bằng tay trong trang quản lý lớp, hoặc bấm "Đề xuất khái niệm":
  - model nhận tối đa 20 trang đã duyệt của lớp (văn bản trang, cắt 1 500 ký tự mỗi trang);
  - trả ≤ 15 khái niệm `{label, description, pages:[n], items:[id]}`;
  - code kiểm `pages` và `items` thuộc lớp, và `label` không trùng.
  - Mọi khái niệm model đề xuất ở trạng thái `PROPOSED`; giảng viên duyệt từng cái.
- Gắn khái niệm cho câu hỏi: mặc định theo trang mà câu hỏi trích (`verify_citation`), là các khái niệm gắn với trang đó. Giảng viên sửa được.
- Một câu hỏi có thể gắn nhiều khái niệm; `weight` chia đều nếu không chỉnh.

### 6.2 BKT (`domain/learning/mastery.py`, thuần)

Tham số mặc định, ghi trong `model_version = "bkt-v1"`:

| Tham số | Giá trị | Ghi chú |
|---|---|---|
| `p_init` | 0,2 | |
| `p_learn` | 0,15 | |
| `p_slip` | 0,10 | |
| `p_guess` | `1/n_choices` cho trắc nghiệm, 0,05 cho trả lời ngắn | |

Mỗi lượt trả lời có `correct ∈ {0,1}` được chấm chính xác bằng code (`practice.py`). Với từng khái niệm `c` gắn với câu:

```
posterior = P(K) (1 - slip) / [P(K)(1 - slip) + (1 - P(K)) guess]          nếu đúng
          = P(K) slip / [P(K) slip + (1 - P(K))(1 - guess)]                   nếu sai
P(K)'     = posterior + (1 - posterior) * p_learn
```

Câu nhiều khái niệm thì cập nhật mỗi khái niệm với `p_learn * weight`. Phân loại:
- `p ≥ 0,95`: "Nắm vững";
- `0,6 ≤ p < 0,95`: "Đang tiến bộ";
- `p < 0,6` với ≥ 3 lượt: "Cần ôn";
- < 3 lượt: "Chưa đủ dữ liệu".

Cập nhật chạy đồng bộ trong cùng giao dịch ghi lượt làm (`practice-items/{id}/attempts`) khi `learning.mastery_map` bật. Bước này chỉ tính số, không gọi model.

Kết hợp với SM-2 sẵn có: SM-2 vẫn quyết lịch từng câu. F7 thêm **thứ tự ưu tiên** trong phiên ôn: câu đến hạn thuộc khái niệm có `p_known` thấp nhất lên trước. SM-2 không đổi.

### 6.3 Thang gợi ý

Khi sinh viên trả lời sai câu `i` (lượt thứ `a`):

| Bậc | Khi nào | Nội dung |
|---|---|---|
| 1 | sai lượt 1 | Chỉ ra trang ("Xem lại trang 12") + một câu hỏi dẫn dắt; có trích ≥ 12 ký tự từ trang |
| 2 | sai lượt 2, hoặc sinh viên bấm "Gợi ý thêm" | Thu hẹp vào đoạn chứa ý cần, kèm câu hỏi hẹp hơn |
| 3 | `a ≥ reveal_after_attempts`, hoặc sinh viên bấm "Xem lời giải" khi đã được phép | Giải thích đầy đủ + đáp án + trích dẫn |

Hội thoại gợi mở: ở bậc 1 và 2 sinh viên có thể trả lời câu dẫn dắt (≤ 500 ký tự). Gia sư đáp bằng gợi ý kế tiếp hoặc câu "Bạn đang đi đúng hướng, thử chọn lại đáp án". Gia sư **không chấm** câu trả lời tự do; muốn được tính điểm, sinh viên phải chọn lại đáp án. Tối đa 6 lượt mỗi câu.

### 6.4 Sinh và kiểm gợi ý

- Prompt (khối cố định theo `agent/prompts/composer.py`, `TrustDomain.RETRIEVED_EVIDENCE` cho văn bản trang, vùng không tin cậy cho câu của sinh viên) nhận: đề, các phương án, đáp án đúng (để model **tránh** nó ở bậc 1–2), văn bản trang được trích, bậc, và lịch sử ≤ 2 gợi ý trước. Model trả JSON `{hint, quote}`.
- Code kiểm:
  1. `quote` là chuỗi con nguyên văn của văn bản trang, dài ≥ `MIN_QUOTE_CHARS`;
  2. ở bậc 1–2, `hint` và `quote` không chứa văn bản chuẩn hóa của phương án đúng, mã phương án ("đáp án B"), hay đáp án ngắn đã chuẩn hóa theo hàm của `practice.py`;
  3. `hint` ≤ 600 ký tự, không có liên kết, không có Markdown ngoài in đậm;
  4. `PromptInjectionDetector` trên `hint`.
- Trượt kiểm thì thử lại một lần với lý do trượt dạng mã. Trượt tiếp thì dùng **gợi ý mẫu tất định**:
  - bậc 1: "Xem lại trang {p}: «{câu đầu của đoạn có điểm token cao nhất với đề}»";
  - bậc 2: thêm câu kế tiếp;
  - bậc 3: dùng lời giải giảng viên đã soạn nếu có, nếu không thì hiện đáp án kèm đoạn trích của câu hỏi.
- Gọi model qua `service.ai_gateway` sẵn có, nên đi qua gateway có trần. Thời hạn 5 s theo giới hạn hiện hành, không nâng.

### 6.5 Bản đồ nắm vững của lớp

Cho giảng viên của lớp (quyền học liệu hiện có):
- **Theo khái niệm**: số sinh viên ở từng nhóm (Nắm vững / Đang tiến bộ / Cần ôn / Chưa đủ dữ liệu), sắp theo tỉ lệ "Cần ôn".
- **Câu sai nhiều nhất**: tỉ lệ đúng lần đầu, và tỉ lệ chọn từng phương án nhiễu (chỉ khi ≥ 5 lượt làm).
- **Xu hướng 14 ngày**: trung bình `p_known` theo khái niệm.
- Mọi ô có n < 5 hiện "< 5" và không hiện tỉ lệ. Không có danh sách tên trong bản đồ.
- Xuất CSV số liệu gộp, theo cùng quy tắc k ≥ 5.

## 7. API (dưới `/v1/learning`, đã nằm trong `ALLOWED_API_PREFIXES`)

| Phương thức, đường dẫn | Ai | Cờ | Mô tả |
|---|---|---|---|
| `GET /v1/learning/offerings/{id}/concepts` | thành viên lớp | mastery_map | Khái niệm đã duyệt (giảng viên thấy cả `PROPOSED`) |
| `POST /v1/learning/offerings/{id}/concepts` · `PUT …/{cid}` · `POST …/{cid}:approve` · `:retire` | giảng viên | mastery_map | Quản lý khái niệm (`row_version`) |
| `POST /v1/learning/offerings/{id}/concepts:suggest` | giảng viên | mastery_map + ai_explanations | Model đề xuất; có trần |
| `PUT /v1/learning/concepts/{cid}/links` | giảng viên | mastery_map | Gắn câu hỏi và trang |
| `GET /v1/learning/offerings/{id}/me/mastery` | sinh viên | mastery_map | Mức nắm vững của tôi theo khái niệm + gợi ý "ôn khái niệm X trước" |
| `GET /v1/learning/offerings/{id}/mastery-map` | giảng viên | mastery_map | Bản đồ lớp (§6.5) |
| `GET /v1/learning/offerings/{id}/mastery-map.csv` | giảng viên | mastery_map | Xuất số liệu gộp |
| `GET/PUT /v1/learning/offerings/{id}/tutor-settings` | giảng viên | tutor | Bật gia sư, ngưỡng lộ lời giải, cho phép gợi ý có model |
| `POST /v1/learning/practice-items/{id}/hints` | sinh viên | tutor | `{attempt_no, level_requested?, reply?}` → `{level, hint, quote, page, origin, remaining_today}`. 403 `TUTOR_DISABLED_FOR_OFFERING`, 409 `HINT_LEVEL_NOT_ALLOWED` (xin lời giải sớm), 429 `HINT_BUDGET` |

## 8. Giao diện

- **Phiên ôn tập** (`PracticeSets.tsx`): sau câu sai hiện khung "Gia sư":
  - gợi ý, đoạn trích (bấm mở trang trong trình đọc học liệu sẵn có, tô đoạn);
  - ô "Trả lời câu hỏi gợi mở" (tùy chọn), nút "Gợi ý thêm";
  - nút "Xem lời giải", bị khóa kèm giải thích cho tới khi được phép;
  - nhãn nhỏ "Gợi ý tự động từ tài liệu lớp" hoặc "Gợi ý mẫu".
- **"Mức nắm vững của tôi"**: thanh theo khái niệm với chữ trạng thái, cùng nút "Ôn khái niệm này".
- **Bản đồ lớp** cho giảng viên, trong trang quản lý lớp: bản đồ nhiệt khái niệm × nhóm, bảng câu sai nhiều nhất có biểu đồ phương án, xu hướng. Bảng màu theo skill `dataviz`; có bảng số thay thế cho trình đọc màn hình.
- **Quản lý khái niệm**: danh sách, duyệt đề xuất, kéo thả gắn trang và câu hỏi.

## 9. Bảo mật và quyền riêng tư

- k ≥ 5 cho mọi số liệu lớp (dùng chung `MIN_CLASS_FOR_STATS`).
- Văn bản trả lời gợi mở không lưu lâu; chỉ giữ băm.
- Gợi ý có model chỉ dùng trang **đã duyệt** của chính lớp, và chỉ khi giảng viên bật `model_hints_enabled` cho lớp **và** cờ toàn hệ thống bật (quyết định D8).
- Không dùng dữ liệu nắm vững cho mục đích khác (không đưa vào chat, không đưa vào F6 trừ loại `PRACTICE_DUE` mà người dùng tự bật).

## 10. Quan sát

`tutor_hints_total{level,origin}`, `tutor_hint_filter_rejected_total{reason}`, `tutor_hint_latency_ms`, `mastery_updates_total`. Chỉ số học tập (tỉ lệ đúng lượt sau khi nhận gợi ý) có ích với người dùng thật, hiện **chưa đo**.

## 11. Kiểm thử

| Loại | Nội dung |
|---|---|
| BKT | 50 chuỗi tính tay; mô phỏng 2 000 sinh viên có seed (AUC, ECE); nhiều khái niệm với trọng số |
| Bộ lọc gợi ý | Ca cài: gợi ý chứa phương án đúng, chứa "đáp án B", quote không nguyên văn, có link, có injection → đều bị chặn |
| Sinh gợi ý thật | 300 lần, một lần chạy có trần; lưu báo cáo `evals/results/tutor-<date>/` |
| Quyền và k-ẩn danh | Lớp 4 người; giảng viên lớp khác; sinh viên gọi bản đồ (403) |
| Trần chi phí | Hết trần thì `origin=TEMPLATE` |
| Migration | Áp 0033 trên DB tạm (như cách làm 0032), kiểm guard hash |
| Web | Vitest khung gia sư, mức nắm vững, bản đồ; `web_acceptance.mjs` với lớp mô phỏng E4 |
| Cờ | Ma trận F0 cho `learning.tutor`, `learning.mastery_map` |

## 12. Rủi ro

| Rủi ro | Giảm |
|---|---|
| Gợi ý lộ đáp án | Kiểm code nhiều lớp; mẫu tất định khi trượt; đo bằng 0 % sau lọc |
| BKT sai lệch với lớp thật (tham số mặc định) | Ghi rõ "ước lượng"; `model_version`; về sau có thể ước tham số theo lớp (EM) khi có dữ liệu thật |
| Giảng viên hiểu sai bản đồ | Chú thích từng nhóm; "Chưa đủ dữ liệu" tách riêng |
| Migration cần duyệt | Gói F7.1 dừng ở bước duyệt hash; các gói không cần DB (bộ lọc, BKT thuần) làm trước |

## 13. Kế hoạch gói con

| Gói | Nội dung | Cỡ | Ghi chú |
|---|---|---|---|
| F7.1 | Migration 0033 + repository | S | **cần duyệt hash** |
| F7.2 | BKT thuần + mô phỏng + tích hợp vào ghi lượt làm | M | |
| F7.3 | Khái niệm: CRUD, duyệt, đề xuất có model, gắn | M | |
| F7.4 | Thang gợi ý: sinh, kiểm, mẫu tất định, trần | M | |
| F7.5 | Bản đồ lớp + CSV | S | |
| F7.6 | Giao diện (phiên ôn, mức của tôi, bản đồ, quản lý khái niệm) | L | |
