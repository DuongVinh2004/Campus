# F3 — Phân tích tác động khi quy chế thay đổi, phát hiện mâu thuẫn

Phụ thuộc: G-PG ([03](03-policy-rules-engine.md) §6). Dùng F1 để soạn thông báo và F2 để đánh dấu luật cũ.

## 1. Mục tiêu và giá trị

Khi một release tri thức mới lên, hệ thống tự trả lời bốn câu hỏi:
1. **Điều khoản nào đổi**: thêm, bỏ, đổi số, đổi phạm vi, hay chỉ đổi câu chữ.
2. **Cái gì phụ thuộc vào điều khoản đó**: luật F2, nút đồ thị, thông báo F1, ca kiểm thử RAG đang giữ, câu trả lời người dùng từng nhận.
3. **Ai bị ảnh hưởng**: số người theo khóa, ngành hoặc khoa, có ngưỡng k ≥ 5.
4. **Cần làm gì**: duyệt lại luật, sửa gold, soạn sẵn thông báo cho đúng nhóm.

Song song, hệ thống quét tìm **mâu thuẫn** giữa các văn bản đang cùng hiệu lực: cùng chủ thể, cùng phạm vi, cùng thời gian, nhưng giá trị khác nhau. Các ca này đi vào hàng duyệt.

Giá trị: nhà trường biết ngay một thay đổi chạm tới những đâu, thay vì phát hiện khi sinh viên đã nhận câu trả lời cũ. Chất lượng kho tri thức được giữ chủ động.

## 2. Tiêu chí xong (kiểm được)

1. **So khác.** Bộ gold gồm 60 cặp release tổng hợp: lấy đơn vị thật, rồi dùng script đột biến có ghi nhãn để đổi số, đổi phủ định, đổi phạm vi, đổi câu chữ, đánh số lại điều, thêm và bỏ.
   - Bộ phân loại tất định đạt độ chính xác ≥ 99 % và độ phủ 100 % cho các loại {ADDED, REMOVED, NUMERIC, NEGATION, SCOPE}.
   - Khớp điều khoản bị đánh số lại đạt ≥ 95 %.
   - Gold do script đột biến sinh, nên nhãn đúng theo cách tạo.
2. **Tác động.** Mỗi luật F2, nút đồ thị, thông báo F1 hoặc ca eval trích một đơn vị đã đổi đều xuất hiện trong danh sách tác động. Đây là kiểm bao phủ 100 % trên fixture.
3. **Mâu thuẫn tất định.** Trên fixture có 20 cặp sự kiện (`facts.jsonl`) cài mâu thuẫn và 20 cặp nhiễu (cùng chủ thể nhưng khác phạm vi hoặc khác thời gian), cần độ phủ 100 % và 0 dương tính giả.
4. **Mâu thuẫn có model.** Mọi đoạn trích trong ứng viên do model nêu đều đạt kiểm nguyên văn, ứng viên trượt kiểm bị loại. Đo độ chính xác trên 30 cặp gold do model viết từ nguồn thật, có span do code kiểm, rồi ghi số đo; không đặt ngưỡng chặn ở v1.
5. Chạy trọn một lần phân tích trên chỉ mục hiện tại (9 173 đơn vị) trong ≤ 60 s **không kể** bước gọi model; bước model chạy nền và có trần.
6. Không có nội dung câu hỏi hay danh tính người dùng trong kết quả phân tích; chỉ có số đếm, trừ thông báo gửi cho chính chủ ở §7.6.

## 3. Phạm vi

**Trong phạm vi:**
- lưu ảnh chụp đơn vị theo release;
- so khác và phân loại thay đổi;
- khớp điều khoản qua các ấn bản;
- tìm phụ thuộc;
- ước tính nhóm bị ảnh hưởng;
- soạn sẵn thông báo F1;
- quét mâu thuẫn tất định và có model;
- hàng duyệt.

**Ngoài phạm vi:**
- tự sửa nguồn hay tự quyết ấn bản nào thắng, vì người duyệt quyết qua `edition_decisions` hiện có;
- tự gửi thông báo khi không có người bấm xác nhận;
- (cần duyệt) chèn cảnh báo mâu thuẫn vào câu trả lời chat.

## 4. Hiện trạng liên quan

- `ReleaseWatch` (`application/knowledge/release_check.py`) đã phát hiện release mới và chạy kiểm truy hồi theo cách gộp và trễ (debounce).
- Đơn vị v2 có `unit_id = sha256(version_id|locator|text_sha)[:16]`, `path` dạng "Điều n > Khoản m", `effective_from/until`, `scope`, `parent_unit_id`.
- `facts.jsonl` có 136 sự kiện dạng `(kind, subject chuẩn hóa, value nguyên văn, unit_id, quote, scope)`.
- `edition_decisions.py` và `version_resolver.EditionRelation` giữ quan hệ giữa các ấn bản. `edition_release.py` niêm phong theo trục `programmes, cohorts, academic_years`.
- Cạnh đồ thị có `conflict_key`; `ReviewVerdict` có giá trị `conflicting`.
- `manifest.json` có `release_id`, `binding_sha256`, `files_sha256`. Có nhiều thư mục chỉ mục cũ (`data/rag_v2_index/embedded*`), nhưng **không có cơ chế lưu ảnh chụp theo release**: chỉ mục đang chạy bị build đè (`SubprocessIndexBuilder`).

## 5. Ảnh chụp đơn vị theo release

- Khi `ReleaseWatch` thấy `release_id` mới, job `impact_snapshot` (cờ `policy.impact`) ghi `<STATE>/release-units/<release_id>.jsonl.gz`.
  - Mỗi dòng: `unit_id, document_id, version_id, doc_family, path, page, text_sha256, text, effective_from, effective_until, scope, parent_unit_id`.
  - Kèm `<release_id>.manifest.json` (bản sao manifest và hash tệp gz).
  - Kích thước ước tính vài MB mỗi release (9 173 đơn vị).
  - Giữ 20 release gần nhất cộng mọi release còn được một luật F2 tham chiếu.
- Ghi theo kiểu atomic: ghi `.tmp`, fsync, rồi rename, giống `retain()` trong `knowledge_platform.py`.
- Release đầu tiên khi bật cờ không có bản trước để so. Phân tích ghi `BASELINE_ONLY`.

## 6. So khác và phân loại

### 6.1 Khớp đơn vị giữa hai release

Chạy theo thứ tự, mỗi đơn vị chỉ khớp một lần:

1. **Cùng `unit_id`**: UNCHANGED (vì `unit_id` đã băm cả text).
2. **Cùng `version_id` và `path`**, `text_sha` khác: MODIFIED.
3. **Ấn bản kế tiếp** (`EditionRelation` cho biết version mới thay version cũ), cùng `path` chuẩn hóa ("Điều 10 > Khoản 2", bỏ khoảng trắng và dấu câu): MODIFIED. Nếu text giống hệt thì gán UNCHANGED_TEXT_NEW_EDITION.
4. **Đánh số lại**: trong cặp ấn bản đó, với đơn vị còn lại, ghép theo độ giống Jaccard trên 3-gram từ đã chuẩn hóa ≥ 0,6, cộng `doc_family` trùng và độ sâu `path` trùng. Ghép tham lam theo điểm giảm dần. Kết quả MODIFIED hoặc MOVED, gắn cờ `renumbered`.
5. Còn lại: ADDED ở bản mới, REMOVED ở bản cũ.

### 6.2 Phân loại thay đổi của một cặp MODIFIED (tất định)

Một cặp có thể mang nhiều nhãn:

| Nhãn | Cách phát hiện |
|---|---|
| `WORDING_ONLY` | Text chuẩn hóa (NFC, chữ thường, gộp khoảng trắng, bỏ dấu câu) bằng nhau |
| `NUMERIC` | Đa tập các con số (số, phần trăm, tiền "580.500 đồng", ngày) khác nhau. Dùng lại bộ trích số của `rag_v2/verification/deterministic.py`. Lưu `[{old, new, context_window}]` |
| `NEGATION` | Số từ phủ định ("không", "chưa", "cấm", "không được") khác nhau trong cửa sổ quanh động từ chính. Dùng lại bộ kiểm phủ định của `deterministic.py` |
| `SCOPE` | `scope` của đơn vị khác, hoặc tập thuật ngữ phạm vi (`rag_v2/scope_terms.py`: khóa, ngành, chương trình) khác |
| `EFFECTIVE` | `effective_from/until` khác |
| `DEADLINE` | Ngày hoặc thời hạn trong text khác (con của `NUMERIC`, gắn riêng vì F6 dùng) |
| `TEXT_OTHER` | Khác mà không thuộc nhãn nào ở trên |

Mức độ:
- `HIGH` nếu có `NUMERIC`, `NEGATION`, `SCOPE` hoặc `REMOVED`, và đơn vị thuộc họ `quy_che`, `hoc_phi` hoặc `so_tay`;
- `MEDIUM` nếu là `TEXT_OTHER` hoặc `EFFECTIVE`;
- `LOW` nếu là `WORDING_ONLY` hoặc `UNCHANGED_TEXT_NEW_EDITION`.

### 6.3 Tóm tắt thay đổi bằng model (tùy chọn, có trần)

Chỉ áp cho các cặp `HIGH` và `TEXT_OTHER`.
- Model nhận text cũ và mới, trả tối đa 3 phát biểu dạng `{text, old_span, new_span}`.
- Code kiểm `old_span` và `new_span` là chuỗi con nguyên văn, và mọi con số trong `text` xuất hiện trong ít nhất một span.
- Phát biểu trượt kiểm bị bỏ. Trượt hết thì chỉ hiển thị diff.
- Ngân sách D4: 200 lượt/ngày, qua gateway.

## 7. Phân tích phụ thuộc

Với mỗi đơn vị MODIFIED, REMOVED hoặc MOVED (mức ≥ MEDIUM):

| Loại phụ thuộc | Cách tìm | Hành động đề xuất |
|---|---|---|
| Luật F2 | `rule_versions` đang `PUBLISHED` có `source.unit_id` thuộc tập đã đổi | Chuyển `STALE` (việc của job `rule_staleness` ở F2); mục tác động liên kết trình soạn luật |
| Nút và cạnh đồ thị | `policy_node.source` / `policy_edge.source` trỏ đơn vị đã đổi | Đánh dấu `needs_source` trong lần review kế tiếp |
| Thông báo F1 | `ann_announcements.links[].knowledge_version_id` hoặc `knowledge_version_id` trùng version bị thay | Gợi ý sửa thông báo (revision) hoặc thu hồi |
| Ca eval đang giữ | `evals/datasets/rag-v2/*.jsonl` và các bộ giữ lại, ca có `gold_unit_ids` hoặc `gold_chunk_ids` giao với tập đã đổi | Liệt kê ca cần kiểm lại gold; xuất `evals/results/impact-<release>/stale-cases.jsonl` |
| Bộ đệm câu trả lời (L2) | Khóa cache đã gắn fingerprint các dòng được phép (`rag_v2/answer_cache.py:3`) | Kiểm lại là đã tự vô hiệu; nếu chưa thì xóa mục liên quan |
| FAQ dựng sẵn | Đầu ra `scripts/build_huce_faq.py` trích đơn vị đã đổi | Đánh dấu cần dựng lại |
| Câu trả lời đã nhận (§7.6) | Bản ghi tin nhắn trong `conversations.sqlite3` có trích dẫn trùng `version_id` + đơn vị đã đổi | Chỉ đếm; thông báo cho chính chủ khi bật cờ riêng |

### 7.5 Nhóm bị ảnh hưởng

Từ `scope` và thuật ngữ phạm vi của đơn vị đã đổi (khóa, ngành, chương trình, đối tượng), dựng `AudienceSpec` (F1 §5.1) và gọi `RecipientDirectoryPort.count()`. Kết quả chỉ có số đếm theo nhóm, k ≥ 5. Thuật ngữ phạm vi không ánh xạ được sang đối tượng thì ghi `AUDIENCE_UNRESOLVED`, không đoán.

### 7.6 Báo cho người từng nhận câu trả lời (`policy.impact_user_notices`, mặc định tắt, cần chủ dự án duyệt)

- Chỉ áp với hội thoại mà chủ hội thoại đã đồng ý `CONVERSATION_HISTORY` và còn trong hạn lưu.
- Gửi tối đa một thông báo hộp thư mỗi người cho mỗi release: "Một câu trả lời trước đây của bạn dựa trên điều khoản vừa được sửa đổi", kèm liên kết tới hội thoại.
- Không chép nội dung câu hỏi vào thông báo.
- Bước F3.6 trước tiên kiểm bản ghi tin nhắn có lưu `version_id` và định danh đơn vị của trích dẫn không. Nếu không lưu thì tính năng này **không làm được** mà không đổi cách lưu hội thoại; khi đó dừng lại và hỏi chủ dự án.

## 8. Phát hiện mâu thuẫn (`policy.conflicts`)

### 8.1 Tất định trên sự kiện

Với mọi cặp sự kiện `(f1, f2)` ở release hiện tại, đánh dấu ứng viên `FACT_VALUE_CONFLICT` khi thỏa đủ:
- cùng `kind` và cùng `subject` chuẩn hóa;
- `value` chuẩn hóa khác nhau;
- phạm vi giao nhau (theo `Scope` của `rag_v2`: cùng hoặc chứa nhau);
- khoảng hiệu lực giao nhau;
- khác `unit_id`.

Không gọi model. Độ phức tạp O(n²) theo nhóm `(kind, subject)`, nhỏ vì chỉ có 136 sự kiện.

### 8.2 Tất định trên đồ thị và luật

- Cạnh cùng `conflict_key`, phạm vi và thời gian giao nhau, nhưng vị từ khác nhau: ứng viên `GRAPH_CONFLICT`.
- Sự kiện `RULE_CONFLICT` hoặc `EXCEPTION_CONFLICT` từ bộ máy F2: ứng viên `RULE_CONFLICT`, kèm hai luật và đầu vào mẫu (đầu vào tổng hợp, không phải của người dùng).

### 8.3 Có model trên cặp điều khoản gần nhau (`policy.conflicts`, có trần)

1. Tập đơn vị: họ `quy_che`, `so_tay`, `hoc_phi`, `thong_bao` còn hiệu lực (khoảng 1 300 đơn vị).
2. Lấy hàng xóm từ `embeddings.npy` của chỉ mục: top-5 theo cosine ≥ 0,85, **khác `document_id`**, phạm vi giao nhau. Chạy local, không gọi model.
3. Lọc thêm: hai đơn vị có chung ít nhất một từ khóa chủ đề (ví dụ học phí, tín chỉ, điểm, hạn), và một trong hai có con số hoặc phủ định.
4. Model phân loại cặp thành `CONSISTENT | CONFLICT | SUPERSEDES | DIFFERENT_SCOPE | UNCLEAR`, kèm `span_a`, `span_b`, `explanation` ≤ 300 ký tự. Prompt theo nếp `SEMANTIC_PROMPT` (nguồn là dữ liệu, không phải chỉ dẫn).
5. Code kiểm span nguyên văn. Chỉ `CONFLICT` và `SUPERSEDES` vào hàng duyệt.
6. Theo dõi cặp đã xét bằng `pair_hash = sha256(sorted(text_sha_a, text_sha_b))`, nên không xét lại cặp chưa đổi. Quét đầy đủ khi bật lần đầu; sau đó chỉ quét các cặp có ít nhất một đơn vị đổi trong release.
7. Ngân sách tính chung với §6.3 (D4: 200 lượt/ngày). Hết ngân sách thì tiếp tục hôm sau. Tiến độ hiện trên giao diện.

### 8.4 Hàng duyệt mâu thuẫn

Người duyệt (`KNOWLEDGE_ADMIN`) chọn một phán quyết:

| Phán quyết | Hành động hệ thống |
|---|---|
| `REAL_CONFLICT` | Ghi nhận; tùy chọn mở "quyết định ấn bản" (`edition_decisions`) để đánh dấu bản nào thay bản nào; tùy chọn soạn ticket gửi đơn vị ban hành |
| `SUPERSEDED` | Mở trình quyết định ấn bản điền sẵn hai version |
| `DIFFERENT_SCOPE` | Ghi chú phạm vi; gợi ý bổ sung metadata phạm vi cho đơn vị |
| `NOT_CONFLICT` | Chặn `pair_hash` này |

Mọi phán quyết có ghi chú ≥ 8 ký tự và audit. (Cần duyệt, F3.7) Khi có `REAL_CONFLICT` chưa giải, câu trả lời chat trích một trong hai đơn vị sẽ có dòng mở đầu cố định "Có hai văn bản đang quy định khác nhau về nội dung này; vui lòng liên hệ phòng ban". Điểm này đụng đường trả lời nên cần chủ dự án duyệt.

## 9. Lưu trữ

SQLite `<STATE>/policy-impact.sqlite3`:

```sql
CREATE TABLE IF NOT EXISTS impact_runs(id TEXT PRIMARY KEY, from_release TEXT, to_release TEXT NOT NULL,
  trigger TEXT NOT NULL,                       -- RELEASE | MANUAL
  status TEXT NOT NULL,                        -- RUNNING | DONE | FAILED | BASELINE_ONLY
  counts TEXT NOT NULL DEFAULT '{}', started_at TEXT NOT NULL, finished_at TEXT, error_code TEXT);
CREATE TABLE IF NOT EXISTS impact_changes(run_id TEXT NOT NULL, change_id TEXT NOT NULL, old_unit_id TEXT, new_unit_id TEXT,
  document_id TEXT, doc_family TEXT, path_old TEXT, path_new TEXT, kind TEXT NOT NULL,       -- ADDED|REMOVED|MODIFIED|MOVED|UNCHANGED_TEXT_NEW_EDITION
  labels TEXT NOT NULL, severity TEXT NOT NULL, numeric_diff TEXT NOT NULL DEFAULT '[]', summary TEXT,
  PRIMARY KEY(run_id, change_id));
CREATE TABLE IF NOT EXISTS impact_items(run_id TEXT NOT NULL, item_id TEXT NOT NULL, change_id TEXT NOT NULL,
  kind TEXT NOT NULL,                          -- RULE|GRAPH|ANNOUNCEMENT|EVAL_CASE|FAQ|CONVERSATION_COUNT
  target_ref TEXT NOT NULL, audience_counts TEXT, status TEXT NOT NULL,   -- OPEN|RESOLVED|DISMISSED
  resolved_by TEXT, resolved_at TEXT, note TEXT, PRIMARY KEY(run_id, item_id));
CREATE TABLE IF NOT EXISTS conflict_candidates(id TEXT PRIMARY KEY, origin TEXT NOT NULL,   -- FACT|GRAPH|RULE|MODEL
  unit_a TEXT NOT NULL, unit_b TEXT NOT NULL, pair_hash TEXT NOT NULL, span_a TEXT NOT NULL, span_b TEXT NOT NULL,
  explanation TEXT, model_label TEXT, release_id TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS conflict_pair ON conflict_candidates(pair_hash, origin);
CREATE TABLE IF NOT EXISTS conflict_reviews(id TEXT PRIMARY KEY, candidate_id TEXT NOT NULL, reviewer_subject_id TEXT NOT NULL,
  verdict TEXT NOT NULL, note TEXT NOT NULL, action_ref TEXT, at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS conflict_scan_state(pair_hash TEXT PRIMARY KEY, label TEXT NOT NULL, at TEXT NOT NULL);
```

## 10. API (`/v1/policy/impact`, `/v1/policy/conflicts`; người dùng: `KNOWLEDGE_ADMIN`)

| Phương thức, đường dẫn | Mô tả |
|---|---|
| `GET /v1/policy/impact/runs?cursor=` | Danh sách lần phân tích, có số đếm theo mức và loại |
| `POST /v1/policy/impact/runs` | Chạy tay `{from_release, to_release}` (cả hai phải có ảnh chụp); 202 + run id |
| `GET /v1/policy/impact/runs/{id}` | Tóm tắt: số thay đổi theo mức, theo văn bản; số mục tác động theo loại; nhóm ảnh hưởng |
| `GET /v1/policy/impact/runs/{id}/changes?severity=&doc=&label=&cursor=` | Danh sách thay đổi; mỗi mục có `old_text`, `new_text`, đoạn tô khác (diff theo từ), `numeric_diff`, `summary` đã kiểm |
| `GET /v1/policy/impact/runs/{id}/items?kind=&status=` | Mục tác động |
| `POST /v1/policy/impact/items/{run_id}/{item_id}:resolve` | `{status: RESOLVED|DISMISSED, note}` |
| `POST /v1/policy/impact/runs/{id}/announcement-draft` | `{change_ids:[…]}` → tạo **nháp** F1 với đối tượng đã ước tính, tiêu đề "Thay đổi quy định về …" và thân bài liệt kê thay đổi kèm trích dẫn. Trả `announcement_id`; người dùng sửa và gửi theo luồng F1. Cờ `policy.impact_announcements` |
| `GET /v1/policy/conflicts?status=&origin=` | Hàng duyệt |
| `POST /v1/policy/conflicts:scan` | Quét lại (tất định ngay; phần model xếp hàng) |
| `POST /v1/policy/conflicts/{id}:review` | `{verdict, note, open_edition_decision?: bool}` |

## 11. Giao diện (`/knowledge/impact`, `/knowledge/conflicts`)

- **Dòng thời gian release**: mỗi release một thẻ với số thay đổi HIGH, MEDIUM, LOW và nút "Xem tác động".
- **Trang một lần phân tích**: ba cột lọc (văn bản, mức, nhãn) và danh sách thay đổi. Mỗi thay đổi mở được khung so sánh hai cột cũ và mới: chữ đổi được tô; số đổi hiện "20 % → 25 %".
  - Bên phải là "Phụ thuộc": luật (liên kết trình soạn), thông báo, ca eval, cùng số người ảnh hưởng theo nhóm.
  - Nút "Soạn thông báo cho nhóm ảnh hưởng" mở trình soạn F1 với nháp đã điền.
- **Hàng mâu thuẫn**: thẻ hai đoạn trích đặt cạnh nhau, có nhãn nguồn gốc (tất định hay model), nút phán quyết và ô ghi chú.
- Trang `/admin` thêm ô "Release mới: n thay đổi quan trọng chưa xử lý · m mâu thuẫn chờ duyệt".

## 12. Quan sát

Bộ đếm `impact_runs_total{status}`, `impact_changes_total{severity}`, gauge `impact_items_open`, `conflicts_open`, bộ đếm `conflict_model_calls_total`. Cảnh báo khi có thay đổi HIGH chưa xử lý quá 72 giờ.

## 13. Kiểm thử

| Loại | Nội dung |
|---|---|
| Gold so khác | `scripts/eval/make_impact_mutations.py` sinh 60 cặp release đột biến có nhãn từ đơn vị thật; đo độ chính xác và độ phủ theo nhãn |
| Đơn vị | Khớp đánh số lại; trích số tiền và ngày dạng Việt Nam ("580.500 đồng", "ngày 15/9/2025"); phủ định |
| Bao phủ phụ thuộc | Fixture có luật, thông báo, ca eval trích đơn vị sẽ bị đột biến; 100 % xuất hiện trong mục tác động |
| Mâu thuẫn tất định | 20 cặp cài + 20 cặp nhiễu |
| Mâu thuẫn có model | Provider giả trả span sai thì ứng viên bị loại; trần ngân sách được tôn trọng; `pair_hash` không xét lại |
| Hiệu năng | Phân tích 9 173 đơn vị ≤ 60 s (không model); ghi số đo |
| Quyền | Chỉ `KNOWLEDGE_ADMIN`; vai trò khác 403 |
| Cờ | Ma trận F0 cho `policy.impact`, `policy.conflicts`, `policy.impact_announcements`, `policy.impact_user_notices` |

## 14. Rủi ro

| Rủi ro | Giảm |
|---|---|
| Ghép nhầm điều khoản khi đánh số lại | Ngưỡng Jaccard + cùng họ, cùng độ sâu; cờ `renumbered` hiện rõ; gold đo |
| Quá nhiều ứng viên mâu thuẫn giả | Lọc nhiều tầng; chặn theo `pair_hash`; số đo độ chính xác |
| Chi phí model | Trần ngày; chỉ quét cặp mới đổi; phần tất định chạy trước |
| Lộ dữ liệu người dùng qua §7.6 | Mặc định tắt; chỉ chính chủ; không chép câu hỏi; cần duyệt |
| Ảnh chụp chiếm đĩa (ổ máy chủ dự án từng chỉ còn 4,3 % trống) | Nén gz, giữ 20 bản, có chỉ số dung lượng trong ops |

## 15. Kế hoạch gói con

| Gói | Nội dung | Cỡ |
|---|---|---|
| F3.1 | Ảnh chụp đơn vị theo release + job | S |
| F3.2 | Khớp và phân loại tất định + gold đột biến | M |
| F3.3 | Phân tích phụ thuộc (luật, đồ thị, thông báo, eval, FAQ, cache) + nhóm ảnh hưởng | M |
| F3.4 | Tóm tắt có model + kiểm span | S |
| F3.5 | Mâu thuẫn tất định + có model + hàng duyệt | M |
| F3.6 | (cần duyệt) báo cho người từng nhận câu trả lời | S |
| F3.7 | (cần duyệt) dòng cảnh báo mâu thuẫn trong câu trả lời | S |
| F3.8 | API + giao diện + nháp thông báo F1 | M |
