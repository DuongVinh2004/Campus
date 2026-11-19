# Nhóm C — chất lượng AI và vòng phản hồi: thiết kế chi tiết (17/11/2026)

Trạng thái: thiết kế, chưa triển khai. Nguồn: [FEATURE_PROPOSALS_20261117.md](FEATURE_PROPOSALS_20261117.md).
Danh sách task làm được ngay: [FEATURE_READY_TASKS_20261117.md](FEATURE_READY_TASKS_20261117.md).
Bằng chứng của thiết kế: đọc mã hiện tại (dẫn `đường-dẫn:dòng`); chưa chạy thay đổi nào. Quy ước: ✅ làm được ngay · ⏳ chờ đầu vào.

**Ràng buộc chính:** cả ba mục **đo và báo**, không đổi truy hồi, prompt, model, index hay giới hạn 5 s của provider. Đổi nào
chạm vào cách sinh câu trả lời đều được đánh ⏳ và chờ chủ dự án.

---

## C1 — Hàng đợi "lỗ hổng tri thức"

### Hiện trạng

- Feedback câu trả lời: `POST /v1/conversations/{id}/messages/{id}/feedback` với `HELPFUL`/`NOT_HELPFUL` và bình luận ≤ 2000 ký tự
  ([presentation/feedback.py:28](../services/api/src/campus247/presentation/feedback.py)), lưu ở `SQLiteFeedbackRepository`
  ([sqlite_auxiliary.py:81](../services/api/src/campus247/infrastructure/repositories/sqlite_auxiliary.py)). Kèm `source_document_version_ids`,
  `model_version`, `prompt_version`.
- Agent có trạng thái `ABSTAINED` và `gate_decision` ([agent/state.py:22](../services/api/src/campus247/agent/state.py)).
- Có bộ phát hiện dữ liệu cá nhân theo luật ([crawl/pii.py](../services/api/src/campus247/application/knowledge/crawl/pii.py)): CCCD, số điện thoại,
  email cá nhân, tiêu đề bảng có mã sinh viên.
- Chưa có nơi gom các tín hiệu này cho người quản trị nội dung.

### Câu hỏi riêng tư (cần chủ dự án chọn)

Câu hỏi của sinh viên là nội dung cá nhân. Người quản trị nội dung đọc được chúng là một thay đổi về quyền riêng tư.

| Phương án | Người quản trị thấy | |
|---|---|---|
| **P1 — chỉ số đếm** | Số lần từ chối/đánh giá kém theo nguồn được truy hồi và theo cụm; không có chữ câu hỏi | ✅ làm được ngay |
| **P2 — sinh viên chủ động gửi** | Thêm câu hỏi đã lọc dữ liệu cá nhân, chỉ khi sinh viên bấm "Báo thiếu thông tin" và đồng ý trong hộp thoại | ⏳ C-D1 duyệt nội dung đồng ý + thời hạn lưu |
| P3 — tự động lưu chữ câu bị từ chối | Mọi câu bị từ chối, đã lọc dữ liệu cá nhân | ⏳ C-D1; không đề xuất |

Đề xuất: P1 ngay, P2 khi được duyệt, không làm P3.

### Thiết kế

- **Sự kiện** (`gap_events`, bảng SQLite mới trong state, không qua Alembic):
  `id, at, kind (ABSTAINED | NOT_HELPFUL | REPORTED), release_id, top_versions [≤5 version_id], top_scores, gate_reasons [mã],
  cluster_key, question_redacted (NULL trừ khi P2 và có đồng ý), consent_at, expires_at`.
  Không lưu `subject_id`, `conversation_id`, tên hay chữ câu trả lời.
- **Ghi:** sau khi lượt chat kết thúc với `ABSTAINED` hoặc gate từ chối; khi feedback `NOT_HELPFUL` (lấy `source_document_version_ids` của câu trả lời);
  khi sinh viên gửi báo cáo (P2). Ghi bất đồng bộ, lỗi ghi không làm hỏng lượt chat.
- **`cluster_key`** tính tại chỗ, không gửi chữ ra ngoài:
  - P1: khóa theo tập nguồn (`sorted(top_versions[:3])`) cộng mã lý do gate.
  - P2: thêm cụm theo nội dung, dùng embedding `bge-m3` local (18081) và ghép greedy với cosine ≥ 0,85. Không gọi provider trả phí.
- **Lọc dữ liệu cá nhân (P2):** dùng lại luật của `pii.py` và thay bằng `[đã ẩn]`; câu nào còn dấu hiệu mã sinh viên/CCCD sau khi lọc thì bỏ chữ, chỉ giữ số đếm.
- **Thời hạn lưu:** 90 ngày (`expires_at`), job leader xóa bản ghi hết hạn. Đây là dữ liệu do chính tính năng tạo; vẫn cần chủ dự án duyệt thời hạn trong C-D1.
- **API cho quản trị** (`require_admin` hoặc vai trò `KNOWLEDGE_ADMIN`):
  - `GET /v1/knowledge/gaps?since&kind` → danh sách cụm: số lần, lần gần nhất, nguồn liên quan (tên + phiên bản), lý do gate, tối đa 3 câu mẫu (chỉ P2).
  - `POST /v1/knowledge/gaps/{cluster}/decision` với `{"action": "NEEDS_SOURCE" | "SOURCE_OUTDATED" | "OUT_OF_SCOPE" | "RESOLVED", "note", "release_ref"}`.
    Ghi audit; `RESOLVED` cần tham chiếu release đã thay đổi.
- **UI:** tab "Lỗ hổng tri thức" trong `/knowledge`: bảng cụm sắp theo số lần 14 ngày, lọc theo loại, mở nhanh luồng tiếp nhận nguồn
  (`KnowledgeIntake`) với gợi ý tên nguồn; badge "mới" khi cụm tăng > 50 % so với tuần trước.
- **Sinh viên (P2):** trong `AnswerFeedback`, khi câu trả lời là từ chối hoặc đánh giá kém, hiện nút "Báo thiếu thông tin". Hộp thoại nói rõ
  sẽ gửi gì, ai đọc, giữ bao lâu, và cho sửa câu trước khi gửi.

### Task

| ID | Việc | Kiểm chứng | |
|---|---|---|---|
| C1.1 | Bảng `gap_events` + repository + xóa hết hạn | pytest với thư mục tạm | ✅ |
| C1.2 | Ghi sự kiện ABSTAINED/gate từ chối/NOT_HELPFUL (P1, không chữ) | pytest: lượt từ chối tạo đúng 1 sự kiện không chứa chữ câu hỏi; ghi lỗi không làm hỏng lượt | ✅ |
| C1.3 | `cluster_key` theo nguồn + API danh sách + quyết định + audit | Test quyền: sinh viên 403 | ✅ |
| C1.4 | Tab UI trong `/knowledge` | vitest | ✅ |
| C1.5 | Báo thiếu thông tin có đồng ý, lọc dữ liệu cá nhân, cụm theo embedding local | pytest: câu có CCCD/số điện thoại bị ẩn hoặc bỏ chữ | ⏳ C-D1 |

---

## C2 — Hồi quy chất lượng định kỳ

### Hiện trạng

- `rag_regression_gate.py run --quick` khoảng 7 phút, cần provider thật (khoảng 600 lời gọi) và client có giới hạn 30 yêu cầu/phút mỗi tài khoản
  ([rag_regression_gate.py:3](../evals/runners/rag_regression_gate.py)).
- `rag_v2_retrieval_probe.py` chỉ đo truy hồi, **không gọi model sinh câu trả lời**, dùng embedding/reranker local; báo rank của unit gold và tỉ lệ
  qua preselect + rerank ([rag_v2_retrieval_probe.py:1](../evals/runners/rag_v2_retrieval_probe.py)).

### Thiết kế

- **Hằng đêm, miễn phí — truy hồi:** `evals/runners/nightly_retrieval.py` chạy probe trên split dev cố định (`--limit 120`), ghi
  `evals/results/nightly/<date>/retrieval.json` (không ghi đè), rồi append một dòng tóm tắt vào `evals/results/nightly/trend.jsonl`:
  `date, release_id, index_sha, recall@1/5/10, survive_rerank, vector_failed, duration_s`.
  - Chạy 02:30 (trước backup 03:10), đồng thời 2, để không tranh model server với người dùng; bỏ qua khi có > 3 lượt chat đang chạy (đọc từ A2).
  - So với baseline cố định (`evals/results/nightly/baseline.json`, chủ dự án chọn bản nào làm baseline): tụt quá ngưỡng tạo cảnh báo `quality_regression` (A3).
  - Ngưỡng ban đầu: recall@5 tụt > 3 điểm phần trăm hoặc `survive_rerank` tụt > 5 điểm. Kiểm ý nghĩa thống kê bằng `tolerance()` có sẵn trong gate.
- **Hằng tuần, trả phí — sinh câu trả lời:** `gate run --quick` mỗi Chủ nhật, cùng cách lưu trend. ⏳ chờ ngân sách.
- **Kích hoạt theo thay đổi:** khi một release kho tri thức mới được kích hoạt, chạy truy hồi một lần (miễn phí) và đánh dấu dòng trend bằng `trigger=release`.
- **Hiển thị:** thẻ "Chất lượng truy hồi" trong dashboard A2: sparkline 30 ngày recall@5, lần chạy gần nhất, cảnh báo nếu có.

### Task

| ID | Việc | Kiểm chứng | |
|---|---|---|---|
| C2.1 | `nightly_retrieval.py`: chạy probe, lưu kết quả, append trend, so baseline | Chạy thật một lần trên máy này (cần 18081/18082); lần chạy thứ hai không ghi đè | ✅ |
| C2.2 | Lịch chạy: systemd timer trên cloud; Task Scheduler trên máy này (tùy chọn) | `systemd-analyze verify` | ✅ timer · ⏳ A-D4 cho Windows |
| C2.3 | Luật `quality_regression` trong A3 + thẻ trong dashboard A2 | Unit test với trend mẫu | ✅ (sau A2/A3) |
| C2.4 | Chạy khi kích hoạt release mới | pytest với hook giả | ✅ |
| C2.5 | Gate sinh câu trả lời hằng tuần | — | ⏳ C-D2 ngân sách (~600 lời gọi/tuần) |
| C2.6 | Chọn baseline | — | ⏳ C-D3 (đề xuất: lần chạy đầu tiên của C2.1 trên release hiện tại) |

---

## C3 — Cảnh báo nguồn lỗi thời

### Hiện trạng

- Phiên bản nguồn có `effective_from`/`effective_until` ([platform_models.py:45](../services/api/src/campus247/application/knowledge/platform_models.py)).
- Truy vấn kho đã **loại nguồn hết hiệu lực** (`effective_until IS NULL OR effective_until > clock_timestamp()`,
  [platform.py:238](../services/api/src/campus247/application/knowledge/platform.py)); evidence gate cũng chặn trích dẫn quá hạn
  ([evidence_gate.py:283](../services/api/src/campus247/agent/grounding/evidence_gate.py)).
- Phần còn thiếu: nguồn **không có** `effective_until` (gồm 12 nguồn chưa rõ khóa áp dụng) không bao giờ bị nhắc rà soát, và người quản trị
  không được báo trước khi nguồn sắp hết hiệu lực. Khi hết hiệu lực, nguồn lặng lẽ biến khỏi câu trả lời.

### Thiết kế

- **Hạn rà soát tính ra, không lưu (giai đoạn 1, không migration):**
  - có `effective_until` → mốc là `effective_until`;
  - không có → `review_due = max(effective_from, thời điểm công bố phiên bản) + 12 tháng`, cộng cờ `applicability_unknown` cho 12 nguồn chưa rõ khóa;
  - trạng thái: `OK`, `DUE_SOON` (≤ 30 ngày), `OVERDUE`, `EXPIRED`.
- **Giai đoạn 2 (nếu cần):** cột `review_due_at` + `review_owner` để người quản trị đặt hạn riêng → migration mới → ⏳ duyệt hash.
- **API:** `GET /v1/knowledge/freshness` (`KNOWLEDGE_ADMIN`) → danh sách nguồn kèm trạng thái, mốc, lý do, số lần được trích 30 ngày
  (lấy từ sự kiện C1 và trích dẫn đã lưu); sắp theo `OVERDUE` và mức dùng.
  `POST /v1/knowledge/freshness/{version_id}/reviewed` ghi một lần rà soát (người, thời điểm, ghi chú; bảng SQLite `source_reviews`),
  và lần rà soát này dời `review_due` thêm 12 tháng. Không đổi nội dung hay hiệu lực của nguồn.
- **Nhắc:** job leader hằng ngày gửi thông báo trong ứng dụng cho người quản trị nội dung ở T−30 và T−7 ngày (idempotent như B1), và tóm tắt
  `OVERDUE` mỗi thứ Hai. Tham gia cảnh báo A3 dưới dạng `info`, không gửi ra kênh ngoài.
- **Phía sinh viên (chỉ giao diện):** trong `CitationDrawer`, nguồn `OVERDUE` hiện nhãn "Nguồn quá hạn rà soát — nên đối chiếu văn bản gốc".
  Không đổi chữ câu trả lời và không đổi truy hồi. Nguồn `EXPIRED` đã bị loại sẵn nên không bao giờ hiện.

### Task

| ID | Việc | Kiểm chứng | |
|---|---|---|---|
| C3.1 | Hàm thuần tính trạng thái hiệu lực/rà soát | Unit test bốn trạng thái, biên 30 ngày, thiếu ngày | ✅ |
| C3.2 | `GET /v1/knowledge/freshness` + `source_reviews` + `POST …/reviewed` | pytest trên DB tạm/bản sao; quyền | ✅ |
| C3.3 | Trang "Hiệu lực nguồn" trong `/knowledge` | vitest | ✅ |
| C3.4 | Job nhắc T−30/T−7 + tóm tắt thứ Hai | pytest đồng hồ giả, không trùng | ✅ |
| C3.5 | Nhãn trong `CitationDrawer` (cần API trả trạng thái kèm trích dẫn) | vitest; kiểm câu trả lời không đổi chữ | ✅ |
| C3.6 | Hạn rà soát do người quản trị đặt (migration) | — | ⏳ C-D4 duyệt hash migration |

---

## Quyết định cần chủ dự án (nhóm C)

| # | Quyết định | Chặn | Đề xuất |
|---|---|---|---|
| C-D1 | Cho sinh viên chủ động gửi câu hỏi (P2): nội dung đồng ý, thời hạn lưu 90 ngày, ai đọc | C1.5 | Đồng ý P2, không làm P3 |
| C-D2 | Ngân sách gate sinh câu trả lời hằng tuần (~600 lời gọi) | C2.5 | Hằng tuần sau khi lên cloud |
| C-D3 | Chọn baseline truy hồi | C2.6 | Lần chạy C2.1 đầu tiên |
| C-D4 | Migration hạn rà soát do người đặt | C3.6 | Chưa cần; dùng hạn tính ra trước |
