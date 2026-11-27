# F4 — Bằng chứng kiểm chứng từng ý của câu trả lời

## 1. Điều chỉnh so với đề xuất ban đầu

Đề xuất ngày 25/11 là "tách câu trả lời thành từng ý, kiểm từng ý với nguồn". Đọc mã cho thấy phần này **đã có ở máy chủ**:

- `rag_v2/service.py:264-272` kiểm **từng phát biểu** (`check_statement`). Kiểm tất định gồm số, mã, ngày, phủ định, đơn vị được dẫn (`verification/deterministic.py`), nơi chốn (`venue.py`) và phạm vi ngành (`SCOPE_MISMATCH`). Sau đó tới kiểm ngữ nghĩa bằng model (`semantic.py`). Có thể bỏ kiểm ngữ nghĩa khi phát biểu là trích nguyên văn (`verbatim.py`, đòn bẩy L1, đang tắt).
- Phát biểu trượt bị loại khỏi câu trả lời. Lý do là mã hữu hạn (`StatementVerdict.reasons`), được đếm vào `trace.statement_rejections`.
- `agent/nodes/rag_v2.py:428-455` chỉ chuyển ra giao diện **các phát biểu đã đạt** (`GroundedClaim(text, citation_ids)`), cùng đoạn trích đã kiểm là nguyên văn (`quote in row["content_text"]`).

Phần **còn thiếu**, và là phạm vi của F4:
1. Người dùng không biết mỗi ý đã qua những kiểm nào, và đoạn nào trong nguồn đỡ cho nó.
2. Không có biên nhận bền để tra lại sau ("câu trả lời hôm đó dựa trên phiên bản nào, còn đúng không?").
3. Không có số đo công khai về tỉ lệ ý bị loại và loại kiểm theo thời gian.

Cỡ ước lượng vì vậy giảm từ L xuống **M**.

**Cần chủ dự án duyệt (D5 và nguyên tắc 6):** F4.1 đụng mã RAG (thêm trường vào `Outcome` và `DraftResponse`). Thay đổi chỉ là **thêm dữ liệu**, không đổi quyết định, ngưỡng, prompt, model hay chỉ mục. Bằng chứng không đổi hành vi là hồi quy cho ra câu trả lời giống hệt (§9).

## 2. Mục tiêu và tiêu chí xong

1. Mỗi ý trong câu trả lời hiện một **huy hiệu kiểm** gọn, ví dụ "Đã đối chiếu nguyên văn" hoặc "Đã đối chiếu số liệu và ý nghĩa". Bấm vào thì mở nguồn và **tô đúng đoạn** đỡ cho ý đó.
2. Cuối câu trả lời có dòng "n ý đã kiểm · m ý bị loại vì không đủ nguồn" khi m > 0. Nội dung của ý bị loại **không** hiện ra.
3. Mỗi câu trả lời có một **biên nhận** (`receipt_id`). Chủ hội thoại mở lại được bất kỳ lúc nào trong hạn lưu, thấy release và phiên bản nguồn, và thấy trạng thái hiện tại của từng nguồn: còn nguyên, đã sửa (liên kết F3), hoặc đã gỡ.
4. Không đổi hành vi: chạy `RagV2Service` trên các ca của bộ natural eval (`evals/datasets/rag-v2/natural-*.jsonl`) với **provider phát lại** (trả đúng phản hồi đã ghi trong sổ cái của lần chạy trước, cùng thứ tự), trước và sau F4.1. Văn bản câu trả lời, trích dẫn và quyết định trả lời hay từ chối trùng 100 %. Không dùng `rag_regression_gate.py run --quick` làm bằng chứng cho bước này, vì cổng đó cần provider thật (~600 lượt gọi). Chạy cổng đó một lần ở cuối, khi chủ dự án đồng ý chi phí.
5. Tô đoạn đỡ: trên 200 cặp (phát biểu, đoạn trích) lấy từ kết quả eval hiện có, đoạn tô chứa mọi con số của phát biểu trong ≥ 99 % ca. Gold tính bằng code.
6. Trang `/knowledge/quality` thêm biểu đồ tỉ lệ ý bị loại theo mã lý do, theo ngày. Chỉ có số đếm.

## 3. Thiết kế

### 3.1 Dữ liệu kiểm cho từng phát biểu (F4.1, cần duyệt)

Thêm vào `rag_v2/types.py`:

```python
@dataclass(frozen=True)
class StatementCheck:
    deterministic: Literal["PASSED","SKIPPED"]          # số, mã, ngày, phủ định, đơn vị dẫn, nơi chốn, phạm vi
    verbatim: bool                                       # phát biểu là chuỗi con nguyên văn của một nguồn được dẫn
    semantic: Literal["PASSED","SKIPPED_VERBATIM","NOT_RUN"]
    support_spans: tuple[tuple[str, int, int], ...]      # (unit_id, start, end) trong Unit.text

@dataclass(frozen=True)
class Outcome:
    ...                                                  # các trường hiện có giữ nguyên
    checks: tuple[StatementCheck, ...] = ()              # song song với statements, cùng độ dài
    rejected_counts: Mapping[str, int] = field(default_factory=dict)   # mã lý do → số ý bị loại
```

- `checks` được điền đúng ở chỗ `service.py` đang có kết quả (`verdicts`, kết quả `verify_semantic`, kết quả `verbatim`). Không thêm phép kiểm mới. Phát biểu đã vào `statements` thì `deterministic` luôn là `PASSED` (vì phát biểu trượt đã bị loại); trường này có để hiển thị cho rõ.
- `rejected_counts` lấy từ `trace.statement_rejections` đã có.
- `agent/nodes/rag_v2.py` chép hai trường này vào `DraftResponse` (thêm trường tùy chọn `claim_checks`, `rejected_counts`). Luồng SSE đưa chúng vào sự kiện kết thúc, dưới dạng trường **thêm**, nên client cũ bỏ qua được.

### 3.2 Tìm đoạn đỡ (tất định, không gọi model)

Với phát biểu `s` và mỗi đơn vị `u` mà nó dẫn:

1. Nếu `s` (đã chuẩn hóa khoảng trắng) là chuỗi con của `u.text`, đoạn đỡ chính là vị trí đó.
2. Nếu không, tách `u.text` thành câu theo dấu chấm, chấm phẩy và xuống dòng, có giữ số thập phân. Chấm điểm từng câu theo:
   - (a) số lượng số, mã và ngày của `s` có trong câu, trọng số 3;
   - (b) độ phủ token (đã bỏ dấu) của `s` trong câu, trọng số 1.
3. Chọn cửa sổ liên tiếp tối đa 3 câu có điểm cao nhất, sao cho chứa mọi con số của `s` nếu có thể.
4. Ràng buộc: đoạn đỡ nằm trong `u.text` và trong `quote` đã cắt cho trích dẫn (`rerank_excerpt`). Nếu không nằm trong `quote`, mở rộng hiển thị tới đoạn chứa nó, không đổi `quote` gửi đi.

Code nằm ở `rag_v2/outcome/support_spans.py`, là hàm thuần, có test.

### 3.3 Biên nhận câu trả lời (F4.2, cờ `chat.evidence_receipts`)

SQLite `<STATE>/answer-receipts.sqlite3`:

```sql
CREATE TABLE IF NOT EXISTS answer_receipts(
  receipt_id TEXT PRIMARY KEY,              -- uuid7
  owner_subject_id TEXT NOT NULL,           -- chủ hội thoại
  conversation_id TEXT NOT NULL, message_id TEXT NOT NULL,
  release_id TEXT NOT NULL, binding_sha256 TEXT NOT NULL,
  outcome_kind TEXT NOT NULL,               -- answer | partial | refuse | clarify
  statements_sha256 TEXT NOT NULL,          -- băm danh sách phát biểu (không lưu lại văn bản: văn bản đã nằm trong tin nhắn)
  sources TEXT NOT NULL,                    -- JSON [{unit_id, document_id, version_id, path, page, text_sha256}]
  checks TEXT NOT NULL,                     -- JSON song song với phát biểu: StatementCheck (không có text)
  rejected_counts TEXT NOT NULL,
  created_at TEXT NOT NULL, expires_at TEXT NOT NULL,      -- = hạn lưu của hội thoại
  UNIQUE(conversation_id, message_id));
```

- Ghi ngay sau khi tin nhắn trợ lý được lưu, trong cùng tầng repository hội thoại, bằng giao dịch riêng. Ghi lỗi thì **không** làm hỏng câu trả lời: biên nhận thiếu, ghi log `answer_receipt_write_failed`.
- Biên nhận theo hạn lưu của hội thoại. Hội thoại bị xóa hoặc hết hạn (quyền riêng tư) thì biên nhận bị xóa theo, và đó là ngoại lệ duy nhất cho phép xóa, theo yêu cầu quyền riêng tư sẵn có.
- Không lưu câu hỏi, câu trả lời hay danh tính ngoài `owner_subject_id`.

### 3.4 Kiểm lại biên nhận

`GET /v1/answer-receipts/{receipt_id}`, chỉ chủ sở hữu (khác người thì 404):

```json
{"receipt_id": "…", "created_at": "…", "release_id": "…",
 "statements": [{"index": 1, "checks": {"deterministic": "PASSED", "verbatim": false, "semantic": "PASSED"},
                 "sources": [{"path": "Điều 10 > Khoản 2", "doc_title": "…", "page": 4,
                              "status_now": "UNCHANGED"}]}],
 "rejected_counts": {"NUMBER_NOT_IN_SOURCE": 1},
 "now": {"release_id": "…", "sources_changed": 0, "sources_removed": 0, "impact_run_id": null}}
```

`status_now` so `text_sha256` với release hiện tại qua ảnh chụp F3 hoặc trực tiếp `units.jsonl`, và có ba giá trị `UNCHANGED | CHANGED | REMOVED`. Khi `CHANGED` và cờ `policy.impact` bật, kèm `impact_run_id` để mở trang tác động. Người dùng thường chỉ thấy câu "Nguồn đã được sửa đổi sau lần trả lời này".

Thêm tiền tố `/v1/answer-receipts` vào `ALLOWED_API_PREFIXES`.

### 3.5 Giao diện (F4.3, cờ `chat.evidence_ui`)

- `ClaimEvidence.tsx` (đã có, đang xử lý `isUnsupported` và `citationIndices`) nhận thêm `checks` và `supportSpans`.
- Huy hiệu gọn đặt sau ý, bằng chữ chứ không chỉ biểu tượng:
  - `verbatim=true`: "Nguyên văn";
  - `semantic=PASSED`: "Đã đối chiếu";
  - các trường hợp khác: "Đã kiểm số liệu".
  - Có `title` và `aria-label` giải thích ("Ý này trùng nguyên văn với Điều 10, Khoản 2").
- Bấm huy hiệu hay số trích dẫn mở `CitationDrawer`, cuộn tới đoạn đỡ và tô bằng `<mark>`, kèm nhãn "Đoạn đỡ cho ý 2".
- Dòng cuối: "3 ý đã kiểm với nguồn · 1 ý bị loại vì không đủ nguồn" (chỉ khi có ý bị loại), cùng liên kết "Xem biên nhận" mở hộp thoại theo §3.4.
- Cán bộ (`SUPPORT_OFFICER`, `KNOWLEDGE_ADMIN`) thấy thêm mã lý do của ý bị loại, ví dụ "1 × số không có trong nguồn". Đây là quyết định D5.
- Dùng chung nếp với giao diện bố cục câu trả lời mới (commit `e7d969c`: đoạn, danh sách, mục theo `claim_groups`).

### 3.6 Số đo (F4.4)

- `AnswerQualityStore` (`application/knowledge/answer_quality.py`) thêm bảng đếm theo `(ngày, mã lý do)` và `(ngày, loại kiểm: verbatim/semantic)`, ghi từ `rejected_counts` và `checks`. Không có người, không có câu hỏi.
- Trang `/knowledge/quality` thêm thẻ "Kiểm chứng": tỉ lệ ý bị loại trên 7 hoặc 30 ngày, phân theo mã, và tỉ lệ ý nguyên văn so với ý cần kiểm ngữ nghĩa.

## 4. Bảo mật và quyền riêng tư

- Biên nhận chỉ chủ hội thoại đọc được. Cán bộ hỗ trợ đọc được biên nhận chỉ khi sinh viên đã cấp `assistant.grants` cho hội thoại đó, theo nếp grant hiện có.
- Không lộ nội dung ý bị loại, vì có thể là câu sai.
- Mã lý do ẩn với sinh viên, để không gợi ý cách lách kiểm.

## 5. Quan sát

Bộ đếm `answer_statements_total{check}`, `answer_statements_rejected_total{reason}`, `answer_receipt_write_failed_total`. Cảnh báo khi tỉ lệ loại tăng gấp 2 lần trung bình 7 ngày (có thể do release mới làm hỏng nguồn).

## 6. Kiểm thử

| Loại | Nội dung |
|---|---|
| Không đổi hành vi | Phát lại phản hồi provider đã ghi trên các ca natural eval, trước và sau F4.1; so văn bản, trích dẫn, terminal: trùng 100 %. Cổng `--quick` với provider thật chạy một lần ở cuối, khi được đồng ý chi phí |
| Đơn vị | `support_spans`: nguyên văn, khác dấu, nhiều số, số tiền và ngày dạng Việt Nam, đơn vị dài; đoạn luôn nằm trong `Unit.text` |
| Gold đoạn đỡ | 200 cặp từ `evals/results/rag-natural-*`; đo tỉ lệ đoạn chứa đủ số |
| Biên nhận | Ghi và đọc; người khác 404; hết hạn bị xóa theo hội thoại; `status_now` khi đơn vị đổi hoặc bị gỡ (chỉ mục giả) |
| Web | Vitest cho `ClaimEvidence` (huy hiệu, aria, tô đoạn), dòng ý bị loại, hộp thoại biên nhận |
| Chấp nhận | `web_acceptance.mjs`: hỏi một câu có số, thấy huy hiệu, mở nguồn thấy `<mark>` chứa số |
| Cờ | Tắt `chat.evidence_ui` thì giao diện như hiện nay; tắt `chat.evidence_receipts` thì không ghi biên nhận và route 404 |

## 7. Rủi ro

| Rủi ro | Giảm |
|---|---|
| Đổi mã RAG làm lệch câu trả lời | Chỉ thêm trường; hồi quy so trùng 100 %; cần duyệt |
| Người dùng hiểu huy hiệu là "chắc chắn đúng" | Câu chữ "đã đối chiếu với nguồn", không phải "đúng"; giữ miễn trừ hiện có |
| Biên nhận tăng dung lượng | Không lưu text; xóa theo hạn hội thoại |

## 8. Kế hoạch gói con

| Gói | Nội dung | Cỡ | Ghi chú |
|---|---|---|---|
| F4.0 | Provider phát lại: một `LlmGateway` giả đọc phản hồi đã ghi (khóa theo băm yêu cầu) để chạy `RagV2Service` lặp lại được. `evals/runners/rag_natural_eval.py` hiện **chưa** có chế độ này; kiểm bằng mã nguồn ngày 26/11 | S | làm trước F4.1 |
| F4.1 | Thêm `checks` và `rejected_counts` vào `Outcome`, `DraftResponse`, SSE + hồi quy không đổi hành vi (dùng F4.0) | S | **cần duyệt** |
| F4.2 | `support_spans` + biên nhận + API kiểm lại | M | |
| F4.3 | Giao diện huy hiệu, tô đoạn, biên nhận | M | |
| F4.4 | Số đo trên trang chất lượng | S | |

## 9. Bằng chứng nghiệm thu

Một câu cho báo cáo: *bằng chứng là hồi quy so trùng trước và sau, cộng 200 cặp phát biểu và nguồn lấy từ eval sẵn có với gold đoạn đỡ tính bằng code; khả năng hiểu huy hiệu của người dùng thật chưa đo.*
