# F2 — Quy chế thành luật chạy được, mô phỏng "nếu… thì…" có chứng minh

Tài liệu gồm hai phần:
- **G-PG** (§6): đưa đồ thị quy chế lên runtime v2. Đây là nền chung cho F2 và F3.
- **F2** (§7–§15): bộ máy luật và trình mô phỏng.

## 1. Mục tiêu và giá trị

Sinh viên hỏi "nghỉ 3 buổi, giữa kỳ 4 điểm thì có được thi không?" và nhận được ba thứ:
1. **kết luận** do code tính trên luật đã duyệt;
2. **chứng minh**: từng điều kiện, đúng hay sai, với giá trị nào, trỏ về đúng điều khoản;
3. **ngưỡng**: "bạn còn được nghỉ tối đa n buổi".

Model không bao giờ tự quyết kết luận. Nó chỉ giúp hai việc: đề xuất cách chuyển điều khoản thành luật, cán bộ duyệt; và tách số liệu từ câu hỏi, code kiểm lại.

Khác biệt với chatbot thông thường: chatbot chỉ trích đoạn văn và để người đọc tự suy. F2 đưa ra kết luận kiểm chứng được, lặp lại được, có phiên bản và có audit.

## 2. Tiêu chí xong (kiểm được)

1. Có ≥ 5 chủ đề quyết định được mã hóa từ quy chế đã phát hành trong chỉ mục v2 (họ `quy_che`, `so_tay`). Mỗi luật đã qua duyệt, và mọi hằng số trong luật xuất hiện **nguyên văn** trong đoạn trích nguồn (code kiểm).
2. Bộ gold do model viết **chỉ từ văn bản nguồn**, không thấy luật đã mã hóa, ≥ 40 tình huống mỗi chủ đề. Mỗi tình huống có span nguồn do code kiểm. Bộ máy khớp ≥ 98 %. Mọi ca lệch được ghi lý do và xử lý: sửa luật, hoặc loại ca kèm lý do kiểm được.
3. Ca biên sinh tự động (ngay dưới, bằng, ngay trên ngưỡng; thiếu dữ liệu; tổ hợp ALL/ANY; ngoại lệ) đạt 100 %.
4. Thuộc tính:
   - Đơn điệu: với vị từ `x ≤ c`, tăng `x` không bao giờ đổi NOT_SATISFIED thành SATISFIED.
   - Ba trị: thiếu biến cần thiết thì kết quả là UNDETERMINED và liệt kê đúng các biến thiếu. Không bao giờ đoán.
   - Kiểm bằng hypothesis hoặc vòng lặp sinh ngẫu nhiên có seed.
5. Thời gian đánh giá p95 < 50 ms, không gọi model.
6. Luật gắn với phiên bản nguồn. Khi release mới làm đổi đoạn trích của luật, luật chuyển `STALE`, bộ máy trả `UNDETERMINED/RULE_STALE` cho tới khi được duyệt lại. Có test.

## 3. Phạm vi

**Trong phạm vi:**
- G-PG: dựng, duyệt và phát hành đồ thị từ đơn vị `rag_v2`;
- ngôn ngữ luật, bộ đánh giá ba trị, tìm ngưỡng;
- quy trình soạn, duyệt, phát hành luật;
- trang mô phỏng;
- API đánh giá;
- (cần duyệt) nối vào chat.

**Ngoài phạm vi:**
- đọc dữ liệu học vụ thật của sinh viên (chưa có API HUCE). Đầu vào do người dùng nhập;
- tự động ra quyết định hành chính;
- luật có công thức phức tạp (ví dụ tính điểm trung bình tích lũy từ bảng điểm). v1 chỉ nhận giá trị đã tính.

---

## 4. Hiện trạng liên quan

- `domain/policy_graph.py`:
  - nút `Condition` có `ConditionPredicate(comparator ∈ {>,>=,<,<=,=}, value, unit)`;
  - `ConditionGroup` có `operator ∈ {ALL, ANY}` và `members`;
  - cạnh có `requires`, `applies_to`, `has_exception`, `supersedes`, `EffectiveInterval` và `conflict_key`;
  - `GraphScope` gồm `audiences`, `faculties`, `programs`;
  - duyệt bằng `ReviewVerdict` (`approved|rejected|needs_source|conflicting`).
- `application/policy_graph/service.py`: `validate`, `review`, `publication_preview`, `publish` (có xác nhận), `traverse` (có giới hạn).
- `application/policy_graph/extraction.py`: model chỉ đề xuất, không duyệt hay phát hành được.
- Đồ thị đang buộc vào chỉ mục và nguồn **v1** qua fingerprint (`bootstrap/app.py:502-514`), nên bị ẩn trên runtime v2 (E3).
- Chỉ mục v2 (`data/rag_v2_index/embedded2`):
  - `units.jsonl` có 9 173 đơn vị, mỗi đơn vị có `unit_id` ổn định, `version_id`, `path` (ví dụ "Điều 14 > Khoản 1"), `text` nguyên văn, `effective_from/until`, `scope`, `parent_unit_id`;
  - phân theo họ: `quy_che` 545, `so_tay` 438, `hoc_phi` 291, `ctdt` 2 911, `thong_bao` 14, `khac` 4 974;
  - `manifest.json` có `release_id`, `binding_sha256`, `corpus_sha256`;
  - `facts.jsonl` có 136 sự kiện đã trích nguyên văn.

## 5. Khái niệm

| Thuật ngữ | Nghĩa |
|---|---|
| **Chủ đề quyết định (topic)** | Một câu hỏi có/không mà quy chế trả lời, ví dụ `EXAM_ELIGIBILITY` (được dự thi kết thúc học phần) |
| **Biến** | Một đại lượng có kiểu, ví dụ `attendance.absent_ratio` (phần trăm), `grade.process_score` (thang 10) |
| **Vị từ** | So sánh một biến với một hằng: `absent_ratio <= 20 percent` |
| **Luật** | Kết luận + cây điều kiện (ALL/ANY/NOT) + phạm vi áp dụng + nguồn cho từng phần |
| **Quyết định** | Kết quả đánh giá: SATISFIED / NOT_SATISFIED / UNDETERMINED, kèm chứng minh |

Mọi ví dụ số trong tài liệu này (20 %, thang 10…) chỉ để minh họa cấu trúc. Chúng **không** khẳng định nội dung quy chế HUCE. Giá trị thật lấy từ nguồn lúc mã hóa.

---

## 6. G-PG — Đồ thị quy chế trên runtime v2

### 6.1 Mục tiêu

Dựng đồ thị từ đơn vị `rag_v2` của release đang chạy, giữ nguyên mô hình và quy trình duyệt của `policy_graph`, và bật lại `/v1/policy-graph/*` trên 8015 sau cờ `policy.graph_v2`.

### 6.2 Thiết kế

1. **Đọc nguồn v2.** Adapter `infrastructure/knowledge/rag_v2_citation_reader.py` cài `CitationSourceReader` (`ports/citation_source.py:27`):
   - ánh xạ `source_id = document_id`, `version_id = version_id`, `chunk_id = unit_id`;
   - `read()` trả `text` nguyên văn của đơn vị từ `units.jsonl` của chỉ mục đang chạy (`runtime.current`), có kiểm `files_sha256` của manifest;
   - `locator = {"path": unit.path, "page": unit.page}`.
2. **Fingerprint.**
   - `index_fingerprint = manifest.binding_sha256`;
   - `source_fingerprint` giữ công thức `domain/policy_graph.source_fingerprint`, với `quote_span_hash = sha256(text đơn vị)`.
   - Đồ thị buộc vào cặp này. Release mới làm đổi `text` của đơn vị được dùng thì nút hoặc cạnh đó thành `STALE` (F3 dùng đúng cơ chế này).
3. **Tạo đề xuất.** Có hai đường, cả hai chỉ ra `GraphProposal` (chưa duyệt):
   - (a) Soạn tay: mở rộng `source_mapping.py` thành bộ soạn có cấu trúc trong giao diện quản trị.
   - (b) Model đề xuất theo từng điều của họ `quy_che`, `so_tay`, qua `extraction.py` hiện có. Đầu vào giới hạn: tối đa 8 đơn vị mỗi lần gọi, tối đa 200 lượt mỗi lần dựng; ngân sách D4.
   - Code kiểm mọi `quote` là chuỗi con nguyên văn của `text` đơn vị, kiểm mọi `ConditionPredicate.value` xuất hiện trong `quote`, và dùng lại `structural_issues()`.
4. **Duyệt và phát hành.** Dùng nguyên `review`, `publication_preview`, `publish`. Người duyệt là `KNOWLEDGE_ADMIN`, theo `PolicyGraphService.reviewer`.
5. **Lưu trữ.** Repository SQLite sẵn có (`sqlite_policy_graph.py`), tệp mới `<STATE>/policy-graph-v2.sqlite3`. Không đụng tệp v1.
6. **Nối runtime.** Trong `make_app()` khi `policy.graph_v2` bật:
   - tạo `PolicyGraphService(repository, RagV2CitationSourceReader, index_fingerprint, source_fingerprint)`;
   - truyền vào `create_app(policy_graph=…)`;
   - thêm `/v1/policy-graph/` vào `ALLOWED_API_PREFIXES`.
   - Giao diện `/knowledge/policy-graph` đã ẩn hoặc hiện theo API (E3), nên không phải sửa thêm.
7. **Không đổi đường trả lời chat.** Đồ thị chưa được agent chat dùng khi chỉ bật `policy.graph_v2`. Nối vào chat là F2.7, cần duyệt.

### 6.3 Nghiệm thu G-PG

- Một đồ thị đề xuất cho ≥ 3 điều quy chế đi qua đủ validate → review → publish trên runtime 8015 với tài khoản owner (`KNOWLEDGE_ADMIN`).
- Mọi `quote` đạt kiểm nguyên văn.
- Đổi `text` một đơn vị trong chỉ mục giả thì nút liên quan thành `STALE`.

---

## 7. Ngôn ngữ luật

### 7.1 Từ vựng biến (`config/policy/variables.toml`, được duyệt như mã)

```toml
[variables."attendance.absent_ratio"]
type = "number"; unit = "percent"; min = 0; max = 100
label = "Tỉ lệ số tiết vắng mặt của học phần"
input = "USER"            # USER | DERIVED | RECORD (RECORD = từ hệ thống học vụ, sau này)
derive = "attendance.absent_periods / course.total_periods * 100"   # khi đủ hai biến gốc

[variables."attendance.absent_periods"]
type = "integer"; unit = "period"; min = 0; max = 300; label = "Số tiết đã vắng"; input = "USER"

[variables."grade.process_score"]
type = "number"; unit = "point10"; min = 0; max = 10; step = 0.1; label = "Điểm quá trình"; input = "USER"

[variables."student.cohort"]
type = "string"; pattern = "^[0-9]{2}$"; label = "Khóa (ví dụ 66)"; input = "PROFILE"   # lấy từ hồ sơ khi có

[variables."discipline.level"]
type = "enum"; values = ["NONE","REPRIMAND","WARNING","SUSPENSION"]; label = "Mức kỷ luật hiện tại"; input = "USER"
```

Quy tắc của từ vựng:
- Kiểu `number | integer | boolean | enum | string | date`.
- Đơn vị thuộc tập đóng: `percent, point10, point4, credit, period, day, semester, vnd`.
- Đổi đơn vị chỉ theo bảng tất định, ví dụ `point10 ↔ letter` **không** được đổi tự động.
- `DERIVED` là biểu thức số học trên biến khác (`+ - * /`, không gọi hàm), được phân tích bằng bộ parser nhỏ, không dùng `eval`.

### 7.2 Cấu trúc luật (JSON, có JSON Schema `config/policy/rule.schema.json`)

```json
{
  "rule_id": "exam-eligibility.attendance",
  "topic": "EXAM_ELIGIBILITY",
  "version": 3,
  "conclusion": {"code": "ELIGIBLE", "label": "Được dự thi kết thúc học phần"},
  "applies": {
    "audiences": ["STUDENT"], "cohorts": {"from": "64", "to": null}, "programs": ["*"],
    "effective": {"from": "2024-09-01T00:00:00+07:00", "to": null}
  },
  "when": {"all": [
    {"id": "c1", "pred": {"var": "attendance.absent_ratio", "op": "<=", "value": 20, "unit": "percent"},
     "source": {"unit_id": "…", "version_id": "…", "path": "Điều 10 > Khoản 2", "quote": "… không vượt quá 20% …"}},
    {"id": "c2", "not": {"pred": {"var": "discipline.level", "op": "in", "value": ["SUSPENSION"]}},
     "source": {"…": "…"}}
  ]},
  "exceptions": [
    {"rule_id": "exam-eligibility.excused-absence", "effect": "OVERRIDE_SATISFIED",
     "source": {"…": "…"}}
  ],
  "on_undetermined": {"refer_to": "ACADEMIC_SERVICES", "service_kind": "GENERAL_SUPPORT"},
  "graph_refs": ["node:cond:dk-du-thi-chuyen-can", "edge:requires:…"],
  "status": "PUBLISHED",
  "content_sha256": "…"
}
```

- `op ∈ {<, <=, >, >=, =, !=, in, not_in, between}`. `between` là `[a, b]`, có cờ mở hay đóng cho từng đầu.
- Nút logic: `all`, `any`, `not`, `pred`. Độ sâu ≤ 6, ≤ 40 vị từ mỗi luật.
- `source` bắt buộc ở mọi vị từ và ở kết luận. `quote` phải là chuỗi con nguyên văn của `text` đơn vị. Với vị từ so sánh số, chuỗi số của `value` (theo các dạng viết `20`, `20%`, `20 %`, `hai mươi phần trăm` trong bảng chuẩn hóa) phải xuất hiện trong `quote`.
- `exceptions[].effect ∈ {OVERRIDE_SATISFIED, OVERRIDE_NOT_SATISFIED, DEFER_TO_STAFF}`.
- Một chủ đề có thể có nhiều luật, mỗi luật một tập phạm vi áp dụng. Bộ máy chọn luật theo §8.2.

### 7.3 Lưu trữ

SQLite `<STATE>/policy-rules.sqlite3`:

```sql
CREATE TABLE IF NOT EXISTS rule_drafts(id TEXT PRIMARY KEY, rule_id TEXT NOT NULL, body TEXT NOT NULL,
  author_subject_id TEXT NOT NULL, origin TEXT NOT NULL,       -- MANUAL | MODEL_CANDIDATE
  row_version INTEGER NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS rule_reviews(id TEXT PRIMARY KEY, draft_id TEXT NOT NULL, reviewer_subject_id TEXT NOT NULL,
  verdict TEXT NOT NULL, note TEXT NOT NULL, at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS rule_versions(rule_id TEXT NOT NULL, version INTEGER NOT NULL, body TEXT NOT NULL,
  content_sha256 TEXT NOT NULL, graph_version TEXT NOT NULL, release_id TEXT NOT NULL, binding_sha256 TEXT NOT NULL,
  status TEXT NOT NULL,                                         -- PUBLISHED | STALE | RETIRED
  published_by TEXT NOT NULL, published_at TEXT NOT NULL, retired_at TEXT,
  PRIMARY KEY(rule_id, version));
CREATE TABLE IF NOT EXISTS rule_test_vectors(rule_id TEXT NOT NULL, version INTEGER NOT NULL, vector_id TEXT NOT NULL,
  origin TEXT NOT NULL,                                         -- BOUNDARY | COMBINATORIAL | GOLD_MODEL
  inputs TEXT NOT NULL, expected TEXT NOT NULL, source_span TEXT, verdict TEXT, PRIMARY KEY(rule_id, version, vector_id));
CREATE TABLE IF NOT EXISTS rule_evaluations_stats(day TEXT NOT NULL, topic TEXT NOT NULL, outcome TEXT NOT NULL,
  n INTEGER NOT NULL, PRIMARY KEY(day, topic, outcome));          -- chỉ đếm, không lưu đầu vào
```

Phiên bản đã phát hành là bất biến. Sửa luật nghĩa là phát hành `version + 1`; bản cũ thành `RETIRED`, nhưng vẫn tra được để tái lập một quyết định cũ.

---

## 8. Bộ máy đánh giá (`domain/policy_rules/`, thuần, không I/O)

### 8.1 Logic ba trị (Kleene)

| A | B | A ∧ B | A ∨ B | ¬A |
|---|---|---|---|---|
| T | U | U | T | F |
| F | U | F | U | T |
| U | U | U | U | U |

- Vị từ có biến thiếu cho ra U.
- Biến `DERIVED` chỉ tính được khi đủ biến gốc.
- Chia cho 0 cho ra U, kèm lỗi `DERIVATION_INVALID`.

### 8.2 Chọn luật áp dụng

Đầu vào gồm `topic`, `as_of` (mặc định hôm nay, giờ Việt Nam), `cohort`, `program`.

1. Lọc luật `PUBLISHED` của chủ đề có `effective` chứa `as_of`, có `cohorts` chứa `cohort` (so sánh theo số), và có `programs` chứa `program` hoặc `*`.
2. Luật bị `supersedes` bởi một luật khác cũng thỏa bước 1 thì bị loại.
3. Còn đúng 1 luật thì dùng luật đó.
4. Còn 0 luật: kết quả `UNDETERMINED/NO_APPLICABLE_RULE`.
5. Còn > 1 luật **cùng kết luận**: đánh giá tất cả. Cùng kết quả thì gộp chứng minh; khác kết quả thì `UNDETERMINED/RULE_CONFLICT`, đồng thời bắn sự kiện cho F3.
6. Thiếu `cohort` mà các luật khác nhau theo khóa: kết quả `UNDETERMINED`, biến thiếu là `student.cohort`.

### 8.3 Ngoại lệ

Đánh giá luật chính trước, rồi tới từng ngoại lệ (luật con, cùng cách chọn).

- Ngoại lệ ra T thì áp `effect`.
- Ngoại lệ ra U trong khi luật chính ra F, và ngoại lệ có thể lật kết quả, thì kết quả cuối là U. Biến thiếu là biến của ngoại lệ. Ví dụ: "Vắng có phép không?".
- Nhiều ngoại lệ T với `effect` mâu thuẫn thì `UNDETERMINED/EXCEPTION_CONFLICT`.

### 8.4 Kết quả

```json
{
  "topic": "EXAM_ELIGIBILITY", "outcome": "NOT_SATISFIED",
  "conclusion": {"code": "ELIGIBLE", "label": "Được dự thi kết thúc học phần"},
  "rule": {"rule_id": "exam-eligibility.attendance", "version": 3, "content_sha256": "…",
           "release_id": "01a172fe-…", "graph_version": "…"},
  "as_of": "2026-11-25", "inputs_used": {"attendance.absent_ratio": 25.0, "discipline.level": "NONE"},
  "derived": {"attendance.absent_ratio": {"from": {"attendance.absent_periods": 9, "course.total_periods": 36}}},
  "proof": {"op": "all", "value": "F", "children": [
     {"id": "c1", "value": "F", "text": "Tỉ lệ vắng 25 % ≤ 20 %", "source": {"path": "Điều 10 > Khoản 2", "quote": "…", "unit_id": "…"}},
     {"id": "c2", "value": "T", "text": "Không đang bị đình chỉ", "source": {"…": "…"}}]},
  "exceptions": [{"rule_id": "exam-eligibility.excused-absence", "value": "U", "missing": ["attendance.excused"]}],
  "missing": [],
  "thresholds": [{"var": "attendance.absent_periods", "flip_at": 7, "direction": "<=",
                  "text": "Cần vắng không quá 7 tiết để thỏa điều kiện này"}],
  "refer_to": null,
  "disclaimer_code": "SIMULATION_NOT_DECISION"
}
```

### 8.5 Tìm ngưỡng

Với mỗi biến số trong một vị từ trên đường quyết định:

- Vị từ dạng tuyến tính `f(x) op c`. `DERIVED` chỉ gồm phép nhân hoặc chia cho hằng và cộng hoặc trừ, nên vẫn tuyến tính theo một biến khi giữ các biến khác cố định. Giải ra ngưỡng dạng đóng.
- Biến `integer` thì làm tròn theo hướng an toàn: `≤` làm tròn xuống, `≥` làm tròn lên. Kiểm lại bằng cách đánh giá ở ngưỡng và ngưỡng ± 1 bước.
- Biểu thức không tuyến tính thì bỏ qua, không đoán.

### 8.6 Văn bản giải thích

Câu chữ sinh từ mẫu cố định theo `op` và `unit` (`lib/i18n` có tiếng Việt và tiếng Anh), không dùng model. Ví dụ `"{label} {value_fmt} {op_text} {const_fmt}"` cho ra "Tỉ lệ vắng 25 % vượt mức tối đa 20 %".

---

## 9. Quy trình soạn và duyệt luật

```
Đồ thị v2 đã phát hành (Condition/ConditionGroup/has_exception)
   │  (a) bộ chuyển tất định: Condition.predicate + biến được gán  → bản nháp luật
   │  (b) model đề xuất gán biến cho Condition chưa có biến (≤ 8 nút/lượt)
   v
rule_drafts ──validate──> lỗi cấu trúc / nguyên văn / đơn vị / phạm vi
   │ sinh vector BOUNDARY + COMBINATORIAL tự động
   │ chạy GOLD_MODEL (mục 12) → báo cáo khớp/lệch
   v
review (KNOWLEDGE_ADMIN, khác người soạn nếu người soạn không phải KNOWLEDGE_ADMIN)
   v
publish-preview → publish-confirm (token, idempotency, audit) → rule_versions (PUBLISHED)
```

- Bộ chuyển (a) đọc `ConditionPredicate(comparator, value, unit)` có sẵn trong đồ thị. Phần còn thiếu chỉ là gán biến cho từng Condition, lưu vào `PolicyNode.qualifiers` dạng `var:<key>`. Làm vậy giữ nguyên schema đồ thị, không cần đổi mô hình.
- Chặn phát hành khi còn một trong các điều sau:
  - lỗi validate;
  - vector `BOUNDARY` hoặc `COMBINATORIAL` sai;
  - tỉ lệ khớp `GOLD_MODEL` < 98 %, hoặc còn ca lệch chưa có phán quyết của người duyệt (`RULE_FIX_NEEDED` hay `CASE_INVALID` kèm ghi chú ≥ 20 ký tự).
- Khi release mới: job `rule_staleness` (cờ `policy.rules`), kích bởi `ReleaseWatch`, so `quote_span_hash` của mọi `source` trong luật đang `PUBLISHED`. Khác thì luật thành `STALE`, gửi thông báo hộp thư cho `KNOWLEDGE_ADMIN` và nạp vào hàng đợi F3.

## 10. API

| Phương thức, đường dẫn | Ai | Mô tả |
|---|---|---|
| `GET /v1/policy/topics` | mọi người | Danh sách chủ đề đang có luật hợp lệ: `{topic, label, description, cohorts, effective_from, rule_count}` |
| `GET /v1/policy/topics/{topic}/form?as_of=&cohort=&program=` | mọi người | Biểu mẫu biến cần nhập, sinh từ luật áp dụng: `[{var, label, type, unit, min, max, step, values, help, source:{path}}]` theo thứ tự xuất hiện trong cây; biến `PROFILE` điền sẵn nếu có |
| `POST /v1/policy/evaluate` | mọi người | `{topic, as_of?, cohort?, program?, inputs:{…}}` → kết quả §8.4. Biến lạ, sai kiểu hay ngoài miền thì 422 `POLICY_INPUT_INVALID` kèm `errors[{var, code}]` |
| `POST /v1/policy/what-if` | mọi người | Như trên + `vary: [var]` → ngưỡng và kết quả tại các điểm mẫu |
| `GET /v1/policy/rules?topic=&status=` | KNOWLEDGE_ADMIN, CONTRIBUTOR | Danh sách luật và nháp |
| `POST /v1/policy/rules/drafts` · `PUT …/{id}` | KNOWLEDGE_ADMIN, CONTRIBUTOR | Soạn luật (`row_version`) |
| `POST /v1/policy/rules/drafts/{id}:from-graph` | như trên | Chạy bộ chuyển (a) từ các nút đồ thị chỉ định |
| `POST /v1/policy/rules/drafts/{id}:suggest-variables` | như trên | Đường (b), có trần lượt gọi |
| `POST /v1/policy/rules/drafts/{id}:validate` | như trên | Trả lỗi, vector đã sinh, kết quả gold |
| `POST /v1/policy/rules/drafts/{id}:review` | KNOWLEDGE_ADMIN | `{verdict: approved|rejected|needs_source, note}` |
| `POST /v1/policy/rules/drafts/{id}:publish-preview` → `POST /v1/policy/rules:publish-confirm` | KNOWLEDGE_ADMIN | Preview, token, idempotency |
| `POST /v1/policy/rules/{rule_id}:retire-preview` → `:retire-confirm` | KNOWLEDGE_ADMIN | Ngừng một luật |
| `GET /v1/policy/rules/{rule_id}/versions/{v}/vectors` | KNOWLEDGE_ADMIN | Vector và phán quyết |

Đánh giá không cần đăng nhập, vì quy chế là công khai. Rate limit dùng `rate_limit_store` sẵn có (30 lượt/phút/IP hoặc người dùng). Đầu vào **không được lưu**. Chỉ `rule_evaluations_stats` tăng theo `(ngày, chủ đề, kết quả)`.

## 11. Giao diện

- **`/policy/simulator`** (cờ `policy.simulator`): chọn chủ đề (thẻ có mô tả) → biểu mẫu sinh từ `form` → nút "Kiểm tra".
  - Kết quả: huy hiệu lớn (Đạt / Chưa đạt / Chưa đủ thông tin), cây chứng minh dạng danh sách lồng, mỗi dòng có ✓/✗/? và liên kết "Xem điều khoản" mở `CitationDrawer` sẵn có.
  - Khối "Nếu thay đổi" có thanh trượt cho biến số, kết quả cập nhật theo `what-if` (debounce 300 ms).
  - Khối "Cần hỏi phòng ban" khi có `refer_to`, với nút tạo ticket nháp (đi qua `tickets.student`, có preview).
  - Dòng miễn trừ cố định: "Kết quả mô phỏng theo quy chế đã phát hành, không thay quyết định của nhà trường."
- **Quản trị luật** `/knowledge/policy-rules` (cờ `policy.rules`):
  - danh sách luật theo chủ đề và trạng thái (STALE nổi đỏ);
  - trình soạn hai cột: trái là cây điều kiện kéo thả từ nút đồ thị, phải là đoạn nguồn tô sáng phần `quote`;
  - tab "Kiểm thử" hiện vector và gold, ca lệch, ô phán quyết;
  - preview phát hành.
- **Chat** (F2.7, cần duyệt): thẻ "Kiểm tra điều kiện" xuất hiện khi câu hỏi khớp một chủ đề. Thẻ mở trình mô phỏng ngay trong chat, với các số đã tách sẵn từ câu hỏi.
- Khả năng tiếp cận: cây chứng minh dùng `role="tree"`; trạng thái không chỉ báo bằng màu; thanh trượt có ô nhập số tương đương.

## 12. Bộ gold do model viết (cách làm đúng `AGENTS.md`)

1. Với mỗi chủ đề, model nhận **chỉ** các đơn vị nguồn mà luật trích, không thấy luật đã mã hóa. Model viết ≥ 40 tình huống: mô tả tự nhiên, giá trị biến, kết luận kỳ vọng, và span nguồn biện minh.
2. Code kiểm:
   - span là chuỗi con nguyên văn của đơn vị;
   - giá trị nằm trong miền của biến;
   - tình huống không trùng nhau (băm đầu vào);
   - tỉ lệ ca biên ≥ 30 % (ít nhất một biến ở ngưỡng ± 1 bước).
3. Chạy bộ máy. Ca lệch đi vào hàng duyệt với một trong ba phán quyết: luật sai (sửa), ca sai (loại, kèm lý do), hoặc mơ hồ (ghi vào F3 như ứng viên mâu thuẫn).
4. Báo cáo: `evals/results/policy-rules-<date>/<topic>.json` gồm số ca, khớp, lệch theo phán quyết, và hash luật.

Một câu cho báo cáo: *bằng chứng là các tình huống do model viết từ văn bản nguồn, span nguồn được code kiểm, kết luận đối chiếu với bộ máy tất định; chưa đo với người dùng thật.*

## 13. Bảo mật và an toàn

- Kết luận luôn mang `disclaimer_code`. Không có API nào biến kết quả mô phỏng thành quyết định hay ghi vào hồ sơ.
- Đầu vào người dùng không lưu, không log. Log chỉ có `topic`, `outcome`, `rule_id@version` và thời gian xử lý.
- Biến `PROFILE` chỉ điền từ hồ sơ của **chính** người dùng, chỉ khi có đồng ý `OPTIONAL_PERSONALIZATION`.
- Luật mới hoặc sửa luôn cần người duyệt `KNOWLEDGE_ADMIN`. Model không có đường ghi vào `rule_versions`.
- Prompt cho đường (b) và bộ gold đặt đoạn nguồn trong `TrustDomain.RETRIEVED_EVIDENCE`, theo nếp `agent/prompts/composer.py`.

## 14. Quan sát

Bộ đếm `policy_evaluations_total{topic,outcome}`, histogram `policy_evaluation_ms`, gauge `policy_rules_stale` (> 0 thì cảnh báo cho quản trị), bộ đếm `policy_rule_conflicts_total`. Trang `/admin` thêm ô "Luật: n đang dùng · k cần duyệt lại".

## 15. Rủi ro

| Rủi ro | Giảm |
|---|---|
| Quy chế mơ hồ, khó mã hóa | Kết luận `DEFER_TO_STAFF`; chủ đề chỉ đưa vào khi đạt gold ≥ 98 % |
| Người dùng coi mô phỏng là quyết định | Miễn trừ cố định; không có đường ghi hồ sơ; câu chữ "mô phỏng" |
| Người dùng nhập sai số liệu | Hiện lại giá trị đã dùng; kiểm miền; ngưỡng giúp tự kiểm |
| Quy chế đổi mà luật không đổi | `STALE` tự động khi đổi nguồn; F3 phân tích tác động |
| Phạm vi khóa hoặc ngành sai | Chọn luật theo `applies`; thiếu khóa thì hỏi lại, không giả định |

## 16. Kế hoạch gói con

| Gói | Nội dung | Cỡ | Ghi chú |
|---|---|---|---|
| G-PG.1 | `RagV2CitationSourceReader` + fingerprint v2 + test | S | |
| G-PG.2 | Bộ soạn đề xuất từ đơn vị v2 (tay + model) + kiểm nguyên văn | M | dùng ngân sách D4 |
| G-PG.3 | Nối `PolicyGraphService` vào 8015 sau `policy.graph_v2`; mở tiền tố route; nghiệm thu §6.3 | S | |
| F2.1 | Từ vựng biến + JSON Schema luật + parser biểu thức | S | |
| F2.2 | Bộ đánh giá ba trị, chọn luật, ngoại lệ, chứng minh, ngưỡng + test thuộc tính | M | |
| F2.3 | Store luật + quy trình nháp, validate, duyệt, phát hành + `rule_staleness` | M | |
| F2.4 | Sinh vector tự động + gold do model viết + báo cáo | M | |
| F2.5 | API công khai (`topics`, `form`, `evaluate`, `what-if`) + API quản trị | M | |
| F2.6 | Giao diện mô phỏng + quản trị luật | L | |
| F2.7 | (cần duyệt) nối vào chat: nhận diện chủ đề, tách số từ câu hỏi (mọi số phải có nguyên văn trong câu), thẻ mô phỏng | M | đụng luồng chat |
| F2.8 | Mã hóa ≥ 5 chủ đề thật từ `quy_che`/`so_tay` + gold | L | công việc nội dung |
