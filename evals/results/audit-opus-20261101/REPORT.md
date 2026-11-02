# Kiểm định độc lập Campus 24/7 — 2026-11-01 (Opus)

Phạm vi: runtime chính thức 8015 (RAG v2, chỉ mục `data/rag_v2_index/embedded2`, release `01a172fe…`, generation 27), nhánh `rag-v2-hardening` @ `9db585977` + cây làm việc chưa commit. Không sửa mã sản phẩm. Lời gọi DeepSeek đã dùng: **148** (đếm bằng số bản ghi reservation trong sổ cái `infra/local/public-rag-20261013`: 72.272 → 72.420).

Bằng chứng chung: ca do mô hình viết, đoạn gold kiểm bằng mã (nguyên văn trong `evals/corpus/served-chunks.jsonl`, chưa từng là gold ở bất kỳ bộ dev/holdout nào); mỗi trích dẫn được kiểm bằng mã; mọi câu trả lời được đọc tay; mỗi ca chạy **1 lần**. Mức dùng được với người dùng thật: **chưa đo**.

> **Kết luận cập nhật cuối (đêm 01/11, sau khi sửa):**
> - **Đã sẵn sàng cho một nhóm nhỏ thử có giám sát**, với điều kiện bạn đổi mật khẩu student-local trước (L-03; tôi bị chặn không làm được).
> - Mọi lỗi "chặn" khác đã sửa và kiểm trên 8015: lịch sử hội thoại, mở nguồn, độ trễ 3 phiên p50 10,0 s / p90 13,2 s, 0 hết hạn, không còn chặn event loop.
> - Chất lượng: 22/25 câu có đáp án đủ ý, 0 trích dẫn sai. Test: web 414/414, các bộ Python liên quan đạt, trừ 6 ca có từ trước (L-29).
> - Giới hạn còn lại: chưa có dữ liệu HUCE thật; câu kỷ luật dựa trên Sổ tay bị từ chối (L-12, chờ bạn quyết); một ca trả lời lệch ngữ cảnh (L-27); chưa đo sự cố phụ thuộc trên runtime vì bị chặn quyền.
>
> Chi tiết ở mục "Cập nhật cuối" phía dưới. Kết luận ban đầu bên dưới giữ nguyên để đối chiếu.

## 1. Kết luận

**Chưa sẵn sàng cho người dùng thật thử, nhưng gần.** Chất lượng RAG trên mẫu mới tốt hơn các lần đo trước: 21/25 câu có đáp án được trả lời đủ ý, 38/38 trích dẫn khớp nguyên văn nguồn, không tìm thấy khẳng định bịa nào, quyền và bước xác nhận đều giữ. Lý do chưa sẵn sàng nằm ở **giao diện**, cả hai đều đã xác định nguyên nhân gốc và sửa nhỏ:
1. Mở lại một cuộc trò chuyện có câu trả lời kèm trích dẫn **luôn thất bại** ("Không thể khôi phục lịch sử đã xác nhận"). Không có danh sách lịch sử, nên người dùng mất hội thoại khi tải lại trang.
2. Nút "Mở đoạn nguồn gốc" báo "Chưa thể xác minh nguồn" với khoảng 37% trích dẫn (14/38) dù nguồn đúng.

Ngoài ra cần **đổi mật khẩu student-local** trước khi cho người khác dùng: trong lượt này công cụ Playwright đã in mật khẩu vào nhật ký hội thoại (xem L-03). Sau khi sửa 3 việc trên, có thể cho **một nhóm nhỏ thử có giám sát** với giới hạn đã nêu: độ trễ cao khi nhiều người dùng cùng lúc (p50 19 s, tối đa 36 s với 3 người), câu hỏi thuần kỷ luật bị từ chối, chưa kết nối HUCE thật.

## 2. Số liệu đo được

### 2.1 Chất lượng RAG v2 — 45 ca mới (`cases.jsonl`, `scored.json`)

| Nhóm | n | Kết quả |
|---|---|---|
| Có đáp án trong kho | 25 | **đủ ý 21** · thiếu ý 0 · từ chối/hỏi lại nhầm 4 · lỗi 0 |
| Ngoài phạm vi (thời tiết, trường khác, code, KTX, điểm chuẩn, wifi, giờ thư viện…) | 8 | từ chối đúng 8 |
| Cần hỏi lại | 6 | hỏi lại đúng 5 · **trả lời nhầm 1** (AU-C06) |
| Cá nhân / kỷ luật người khác / dữ liệu chưa kết nối | 6 | từ chối đúng 6 |
| Prompt injection ép bịa số liệu + trích dẫn (INJ-01) | 1 | từ chối đúng |

- Khoảng tin cậy Wilson 95% cho đủ ý: 21/25 = 84% (65–94%). Mẫu nhỏ, chỉ dùng để phát hiện lỗi, không phải số liệu chất lượng chính thức.
- Bộ chấm chung (`rag_v2_scoring`) chấm 17 đủ ý / 4 thiếu ý. Đọc tay xác nhận cả 4 ca "thiếu ý" là **báo sai của bộ chấm**: AU-A02 và AU-A08 bị tính sai cực tính vì câu trả lời đúng có chữ "chưa"/"không" ở mệnh đề phụ; AU-A10 vì đáp án nói "05 Phó Giáo sư" (bộ chấm đòi nhãn đứng trước số); AU-A24 vì đáp án ghi "eoffice.huce.edu.vn" thay cho "E-Office".
- **Trích dẫn:** 38 trích dẫn, 38 có `chunk_id` thuộc release và đoạn `quote` nằm nguyên văn trong chunk. Kiểm literal (số, mã, ngày) của mọi câu trả lời so với chunk được dẫn: không có literal nào thiếu nguồn. Đã kiểm tay các chi tiết ngoài gold (AU-A11 "Phòng 304, Tòa nhà A1", hotline thứ hai; AU-A22 "Khoa Cơ khí"): đều có trong chunk được dẫn. **Không tìm thấy câu trả lời bịa hoặc trích dẫn sai.**

### 2.2 Độ trễ và ổn định (`main3.json`, `rerun429.json`, `health-main3.jsonl`)

| Kịch bản | Câu được trả lời: tổng p50 / p90 / max | Nội dung đầu p50 / p90 | Câu từ chối/hỏi lại: p50 / p90 |
|---|---|---|---|
| 3 phiên đồng thời (cùng tài khoản student-local), 27 ca | **19,4 / 26,2 / 35,6 s** (n=20) | 12,1 / 15,3 s | 5,1 / 15,4 s |
| 1 phiên, tuần tự | 14,2–16,4 s (n=2) | 6,8–10,1 s | 2,0 / 7,8 s |

- Không có lỗi hết hạn 12 s và không có `node_failure` trong suốt lượt kiểm định (nhật ký API từ offset `main3.logoffset`).
- 15/42 yêu cầu của lượt 3 phiên bị **HTTP 429** (giới hạn 30 yêu cầu/60 s trên `/v1/conversations` theo chủ thể, `bootstrap/app.py:243`). Đây là do 3 phiên cùng một tài khoản; đã chạy lại 15 ca tuần tự. Chưa kiểm khóa giới hạn khi nhiều tài khoản khác nhau dùng chung một IP.
- Đuôi stream: dưới tải 3 phiên, mỗi delta (3 từ) mất trung vị **214 ms** (tối đa 454 ms). AU-A14 có 98 delta, mất 21,8 s sau nội dung đầu. Câu từ chối (không có snapshot tri thức) chỉ mất 7 ms mỗi delta.
- Event loop không bị chặn: 4.418 lần gọi `/health/live` trong 18 phút, p50 3,9 ms, tối đa 498 ms, kể cả lúc runtime đọc lại 2.019 dòng nguồn (28,2 s).
- Cơ chế đọc lại nguồn 300 s: ở lượt chạy tuần tự, lần đọc lại 28,2 s diễn ra lúc đầu lượt, và 4 lượt kế tiếp đi qua v2 mất 5,8–7,8 s, **không lượt nào quá 12 s**. Chưa kiểm khi lần đọc lại trùng tải 3 phiên (xem mục 4).

### 2.3 Quyền, phiên, xác nhận (`security-probe.json`, 0 lời gọi mô hình)

| Kiểm | Kết quả |
|---|---|
| Ẩn danh gọi `/v1/users/me`, nháp, consent, platform state, tạo hội thoại | 401 cả 5 |
| Cookie bị sửa chữ ký | 401 |
| Sinh viên gọi API quản trị tri thức (state, intakes, schedules, tick, url-intakes, sources, search-preview) | 403 |
| Sinh viên mở `/admin`, `/staff` | 404 (proxy không cho đường dẫn) |
| Sinh viên đọc / ghi tin nhắn vào hội thoại của owner | 404 / 403, **0 lời gọi mô hình** |
| Nháp: `confirmed=false` | 422 `CONFIRMATION_REQUIRED` |
| Nháp: token xác nhận giả; phiên khác của cùng sinh viên lưu bản xem trước | 409 `PREVIEW_INVALID` |
| Nháp: owner lưu/đọc nháp của sinh viên | 403 `STUDENT_REQUIRED` |
| Nháp: lặp `client_id` / dùng lại bản xem trước đã lưu | replay 200 / 409 |
| Đăng xuất rồi dùng lại cookie cũ | 401 (thu hồi phía máy chủ) |
| Đăng nhập từ Origin lạ | 403 |

### 2.4 Test

| Bộ | Kết quả |
|---|---|
| `tests/rag_v2` | 559 đạt |
| `tests/evals` | 466 đạt |
| `tests/architecture` | 1 đỏ: vi phạm lớp cũ đã biết, `application/knowledge/applicability.py` → `infrastructure.knowledge.repository` |
| Web vitest | **58/338 đỏ** (39/135 file). Phân nhóm ở mục 3, L-17 |

## 3. Danh sách lỗi theo mức độ

Mức: **Chặn** = phải sửa trước khi cho người dùng thật thử; **Nên sửa**; **Nhỏ**.

### Chặn
- **L-01 Mở lại hội thoại có trích dẫn luôn lỗi.** Tái hiện: hỏi một câu có trích dẫn, tải lại `/chat?conversation_id=<id>`. Trang báo "Không thể khôi phục lịch sử đã xác nhận" (ảnh `ui/08-history-reopen.png`, `ui/10-mobile-chat.png`). API `GET …/messages` trả 200 đầy đủ. Nguyên nhân gốc (đã kiểm trong trình duyệt): `features/chat/sse.ts:148-165` chuẩn hóa trích dẫn theo danh sách trường cố định và bỏ `unit_id` (trường mới của v2; 31/31 trích dẫn của lượt 3 phiên có trường này). Sau đó `features/chat/history.ts:58` so `JSON.stringify` với bản từ API còn `unit_id`, lệch nên cả trang bị coi là không hợp lệ. Cả hai tệp **chưa được git theo dõi**. Không có test nào bắt lỗi này.
- **L-02 "Mở đoạn nguồn gốc" báo không xác minh được với trích dẫn đúng.** Tái hiện: mở nguồn [1] của câu "lớp học trực tuyến tối đa bao nhiêu %", bấm "Mở đoạn nguồn gốc" (ảnh `ui/04-source-open.png`). API trả 200, SHA-256 khớp. Nguyên nhân gốc: `features/chat/CitationSource.tsx:64` đòi `content_text.startsWith(quote)`, còn trích dẫn v2 là đoạn giữa chunk (`includes` = true). Trên 38 trích dẫn đã thu, 14 trích dẫn (37%) không bắt đầu ở đầu chunk.
- **L-03 Mật khẩu student-local đã lộ vào nhật ký hội thoại.** Để không gõ mật khẩu, tôi sinh một tệp mã tạm từ tệp credentials (đã xóa ngay). Nhưng công cụ Playwright MCP in lại toàn bộ mã đã chạy, gồm cả mật khẩu. Tài khoản chỉ dùng local, nhưng phải coi mật khẩu đã lộ: cần đổi mật khẩu student-local (bạn tự làm; theo quy tắc tôi không đổi tài khoản). Đây là sai sót của tôi trong lượt này.

### Nên sửa
- **L-04 Mọi lời gọi DeepSeek bị tuần tự hóa toàn cục.** `scripts/run_public_rag.py:115` giữ `async with self.lock:` bao trọn lời gọi HTTP. Mỗi câu có đáp án cần 4 lời gọi (phân loại nhạy cảm, định tuyến ý định, sinh, kiểm ngữ nghĩa; đếm từ sổ cái), nên N người dùng xếp hàng nối tiếp. Đây là nguyên nhân rất có khả năng của p50 19 s khi có 3 phiên. Chưa đo riêng thời gian chờ khóa: sổ cái chỉ ghi thời điểm bên trong khóa.
- **L-05 Kiểm lại quyền nguồn trước mỗi delta 3 từ.** `presentation/chat.py:304` gọi `check_result_scope()` → `knowledge_result_guard` (`bootstrap/app.py:531`) → `assert_current` (`infrastructure/knowledge/runtime.py:201`). Mỗi lần gồm đọc pointer, chọn phiên bản và đọc lại các chunk bằng chứng trong Postgres (pool tối đa 5 kết nối). Hậu quả là thời gian sau nội dung đầu tỉ lệ với độ dài câu trả lời: 214 ms mỗi delta dưới tải, có ca 21,8 s. Kiểm một lần trước khi phát và một lần trước `message.completed` vẫn giữ được ý định an toàn. Cần quyết định vì đây là kiểm soát nguồn.
- **L-06 Câu hỏi đơn giản bị đưa sang "chuyển cán bộ".** AU-A18 ("hồ sơ minh chứng miễn giảm nộp mỗi kỳ hay một lần", nguồn có câu trả lời "chỉ cần nộp … 01 lần") nhận câu trả lời "Nội dung này cần cán bộ hỗ trợ xem xét trực tiếp, và hiện chưa có kênh liên hệ ưu tiên…" (`agent/nodes/definitions.py:990`). AU-P06 cũng vậy. Nguyên nhân: bộ định tuyến/phân loại nhạy cảm dùng chung với v1. Chưa xác định nhánh nào.
- **L-07 Thông điệp kỹ thuật, gây hiểu nhầm khi hỏi dữ liệu người khác.** AU-P01, P02, P05 nhận câu "Kênh chuyển yêu cầu từ trợ lý chưa có consumer/receipt được xác nhận… tôi chưa chuyển yêu cầu này" (`application/multi_agent/service_adapter.py:34`). Từ chối là đúng, nhưng thông điệp dùng thuật ngữ nội bộ và ngụ ý yêu cầu sắp được chuyển, thay vì nói rằng không thể cung cấp thông tin cá nhân của người khác.
- **L-08 Hỏi lại sai chỗ.** AU-A17 (giảm 50% học phí cho con người bị tai nạn lao động) bị hỏi lại "khóa hoặc năm học và ngành", dù mức giảm không phụ thuộc chương trình. Nguyên nhân rất có khả năng là luật phạm vi theo từ "học phí".
- **L-09 Đoán ý khi câu mơ hồ.** AU-C06 "Điều kiện để được miễn là gì?" được trả lời là miễn giảm học phí (6 trích dẫn, nội dung đúng nguồn) mà không nói rõ đã giả định. Kèm theo là dòng trống và câu "các phần còn lại chưa đủ căn cứ". Đây là câu hỏi chính sách: hỏi lại, hay trả lời kèm nêu giả định.
- **L-10 Token đăng nhập nằm trong `localStorage`.** `campus247_token` được ghi ở `AppShell.tsx:184` và `chat/page.tsx:291`, rồi gửi dưới dạng `Bearer`. Sau khi xóa cookie, trang vẫn gửi câu hỏi thành công. Đăng nhập còn trả token trong JSON (`scripts/knowledge_platform.py:431`). Cookie HttpOnly/SameSite=Strict vì thế không bảo vệ được token khỏi script trên trang.
- **L-11 Mã chạy runtime chưa được git theo dõi.** `scripts/knowledge_platform.py`, `scripts/run_public_rag.py`, `infrastructure/knowledge/runtime.py`, `infrastructure/identity/local_student.py`, `presentation/local_preparation.py`, `features/chat/{sse,history,CitationSource}.ts(x)` đều chưa theo dõi. Tổng cộng 133 tệp đã sửa, 5 tệp xóa và 1.061 mục chưa theo dõi (135 trong `services/api/src`, 80 trong `apps/web/src`). Một lệnh `git clean` hoặc một sự cố ổ đĩa sẽ mất runtime; nhánh hiện tại không dựng lại được runtime từ checkout sạch.
- **L-12 Chốt kỷ luật chặn Sổ tay sinh viên.** AU-A25 (ai ký quyết định kỷ luật) bị từ chối với `discipline_rule_rejected reason=source_not_official host=cdnm.heyzine.com`, dù Sổ tay có câu trả lời. Đây là kiểm soát an toàn có chủ đích, nên cần quyết định chính sách: có coi Sổ tay sinh viên 2026–2027 là nguồn chính thống hay không.
- **L-13 Không có lịch sử hội thoại trên giao diện.** Cột trái chỉ có "Chủ đề thường hỏi", và mục đầu luôn được tô như đang chọn. API 8015 không có `GET /v1/conversations`. Trang Quyền riêng tư có liên kết "Lịch sử hội thoại" dẫn về `/chat`.
- **L-14 Từ chối nhầm AU-A12** ("mã trường XDS", nguồn có "MÃ TRƯỜNG: XDS"): `decision=no_source`. Chưa xác định là do truy xuất hay do mô hình.

### Nhỏ
- **L-15 Font Inter 404.** Proxy 8015 không cho `/fonts/` (`scripts/knowledge_platform.py:457`), nên chữ rơi về font serif. Ngăn trích dẫn bị ép tiêu đề thành cột hẹp, nhãn "NGUỒN TRONG CÂU TRẢ LỜI…" bị cắt và có thanh cuộn ngang (`ui/03-citation-drawer.png`).
- **L-16 Tương phản thấp ở chế độ tối.** Nút "Chuẩn bị thủ tục mới" có tỉ lệ tương phản 1,59:1 (WCAG AA cần 4,5:1), ảnh `ui/11-mobile-dark-tickets.png`. Trên mobile, nút ☰ chồng lên khung báo lỗi (`ui/10-mobile-chat.png`).
- **L-17 58 test web đỏ:**
  - (a) **Môi trường test: 24 ca.** jsdom thiếu `ResizeObserver`, bị kéo vào qua component mới `components/shared/PanelResizeHandle.tsx` (chưa theo dõi). Các tệp: `app/page`, `rooms`, `tickets`, `admin/layout`, `staff`, `schedule`, `accessibility`.
  - (b) **Test cũ lệch thiết kế/nội dung: 33 ca.** BaselineRecorder 5, StaffTicketQueue 5, StaffTicketQueueEnhanced 5, ServiceWorkspace 4, StaffDraftEditor 4, CertificateWorkspace 2, SourceOperations 2, ChatPanel 2, AssistanceContextPanel 1, CapabilityBanner 1, `history.test` 1 (mã giữ văn bản cũ có chủ ý), `chat/page.test` 1.
  - (c) **Cần kiểm: 1 ca,** `chat/page.history.test` (khôi phục lịch sử sau khi gia hạn token), có thể liên quan L-01.

  Chưa thấy test đỏ nào trực tiếp chứng minh một lỗi thật. Điều đáng ngại hơn là L-01 và L-02 không có test nào bắt.
- **L-18 Lỗi 500 ở trang quản trị.** Owner gọi `search-preview` hợp lệ nhận 500: reranker 18082 trả lỗi và `RerankerContractError` không được xử lý (`presentation/knowledge_platform.py:205`). Chỉ ảnh hưởng quản trị.
- **L-19 Giới hạn đăng nhập dùng chung.** 5 lần sai trong 60 s khóa đăng nhập student-local cho mọi người (bộ đếm chung trong bộ nhớ, `local_student.py:37`), và trả 401 giống sai mật khẩu. `/openapi.json` và `/docs` mở công khai. Ghi qua cookie không kiểm `Origin` mà dựa vào SameSite=Strict. Với chạy local, các điểm này chấp nhận được.
- **L-20 Lệch giữa tài liệu và thực tế.** DB runtime là Postgres native ở `127.0.0.1:55437`, không phải cổng 5433 như ghi trong skill/AGENTS. `scripts/campus.py status` báo "No retained knowledge worker is running" trong khi `/health/ready` là `ready`.
- **L-21 Đọc lại nháp chưa tiện.** Danh sách nháp có 3 mục cùng tên "Hỗ trợ thủ tục học vụ", không có trích nội dung. Bấm vào thì nội dung mở bên dưới, ngoài khung nhìn. Nút phản hồi 👍/👎 không xuất hiện dưới câu trả lời (code `AnswerFeedback` có tồn tại). Chưa xác định là do cờ tắt hay do lỗi.

### Trung thực sản phẩm (mục 6)
Bản đang chạy ở 8015 **không** ngụ ý có dữ liệu HUCE thật:
- Trang đăng nhập ghi "Chưa kết nối SSO HUCE".
- Trang Dịch vụ, Hồ sơ của tôi và bước xem trước nháp ghi rõ "chưa có yêu cầu nào … được gửi đến trường"; biên nhận lưu nháp có "Chưa gửi đến trường"; API trả `sent_to_university=false`.
- Lịch học và Phòng học hiện "Chưa có nguồn … được kết nối".
- Hỏi lịch thi cá nhân thì trợ lý trả lời "chưa kết nối dữ liệu… HUCE".

Rủi ro còn lại nằm trong mã chưa phục vụ hoặc ở vài câu chữ:
- `app/schedule/page.tsx` (nhánh `LegacySchedulePage`, chỉ dùng khi build không bật cờ `NEXT_PUBLIC_KNOWLEDGE_PLATFORM`/`UNIFIED_AI`) ghi "đồng bộ tự động từ cổng đào tạo HUCE" và có nút "Đồng bộ lại". Các chuỗi kiểu "Đã gửi yêu cầu thành công", "Đã kết nối" (`DataModeBadge`) và "đồng bộ CSDL" trong fixture cũng nằm ở nhánh legacy/mock.
- Trang Quyền riêng tư liệt kê mục đích "Chuyển cán bộ khi cần an toàn", trong khi trợ lý tự nói chưa có kênh chuyển. Mục "Thời gian lưu" chỉ có mã nội bộ `PRIV-RET-001` và không nêu thời hạn lưu hội thoại.

## 4. Phần chưa kiểm được và lý do
- **Hành vi khi API, mô hình nhúng (18081) hoặc Postgres chậm hay tắt:** chưa làm. Việc này cần dừng hoặc làm chậm dịch vụ dùng chung đang phục vụ 8015; báo cáo trước ghi hệ thống đã từ chối dừng tiến trình, và tôi không có quyền tự làm. Cách an toàn là dựng một bản API thứ hai trỏ tới cổng giả. Đó là việc riêng (vừa).
- **Lần đọc lại nguồn 300 s trùng tải 3 phiên:** cần chờ cache quá 300 s rồi bắn đồng thời các câu có đáp án (khoảng 12–20 lời gọi), sẽ vượt mức 150.
- **Các biến thể injection khác** (đòi lộ prompt hệ thống/khóa, injection qua lịch sử nhiều lượt, ép bỏ trích dẫn): mới chạy 1 ca. Mỗi ca tốn ít nhất 2 lời gọi; hết ngân sách.
- **Phiên hết hạn tự nhiên sau 3.600 s:** kiểm bằng đọc mã (`exp` trong `local_student.py`) và bằng thu hồi khi đăng xuất, chưa chờ đủ 1 giờ. Việc xóa cookie trên giao diện không mô phỏng được hết hạn vì còn token trong `localStorage` (L-10).
- **Khóa giới hạn 429 khi nhiều tài khoản dùng chung một IP:** chỉ có 1 tài khoản sinh viên.
- **Mức dùng được với người dùng thật:** chưa đo.

## 5. Kế hoạch sửa theo thứ tự
| # | Việc | Ước lượng |
|---|---|---|
| 1 | Đổi mật khẩu student-local (L-03) | nhỏ (bạn làm) |
| 2 | Commit hoặc sao lưu mã runtime chưa theo dõi (L-11), ít nhất các tệp đang phục vụ 8015 | nhỏ–vừa (cần bạn chọn phạm vi) |
| 3 | Web giữ nguyên trường trích dẫn không biết (`unit_id`) hoặc so theo các trường đã chuẩn hóa; thêm test hồi quy với dữ liệu thật của v2 (L-01) | nhỏ |
| 4 | `CitationSource` dùng `includes(quote)` (hoặc so theo vị trí do máy chủ trả); thêm test (L-02) | nhỏ |
| 5 | Danh sách lịch sử hội thoại hoặc ít nhất liên kết mở lại; sửa liên kết ở trang Quyền riêng tư (L-13) | vừa |
| 6 | Chính sách và mã cho L-05: kiểm nguồn trước phát và trước khi hoàn tất, không kiểm theo mỗi delta; đo lại p50/p90 với 3 tài khoản | nhỏ (mã) + quyết định |
| 7 | Bỏ khóa toàn cục quanh HTTP ở gateway (chỉ khóa phần sổ cái/đặt chỗ), đo lại tải 3–5 người (L-04) | vừa |
| 8 | Định tuyến và thông điệp: L-06, L-07, L-08; quyết định L-09 và L-12 | vừa |
| 9 | Bỏ token khỏi `localStorage` và khỏi JSON đăng nhập (L-10) | vừa |
| 10 | Polyfill `ResizeObserver` trong setup vitest, cập nhật 33 test lệch thiết kế (L-17) | vừa |
| 11 | Font, ngăn trích dẫn, tương phản, chồng nút trên mobile, 500 ở quản trị (L-15, L-16, L-18) | nhỏ |
| 12 | Đo sự cố phụ thuộc trên bản API thứ hai, cùng các mục còn lại của mục 4 | vừa |

## Cập nhật 2026-11-01 (tối): đã sửa L-01 và L-02 (thực hiện bằng Codex, Claude kiểm lại)

Bằng chứng: test tổng hợp theo đúng hình dạng trích dẫn v2 quan sát trên runtime, các test mới đỏ trên mã cũ; kiểm trên trình duyệt với hội thoại thật của student-local trên 8015. Không gọi thêm DeepSeek (vẫn 148).

| Mục | Sửa | Kiểm |
|---|---|---|
| L-01 | `features/chat/sse.ts`: tách `normalizeCitation()`, giữ `unit_id` (tùy chọn, chuỗi ≤ 256). `features/chat/history.ts`: chuẩn hóa `item.citations` bằng cùng hàm trước khi so, nên thứ tự khóa và trường bổ sung không còn làm hỏng lịch sử; mọi trường đã biết khác nhau vẫn bị từ chối. Test mới `history-citations-v2.test.ts` (39 ca; 10 ca đỏ trên mã cũ). | Mở lại `/chat?conversation_id=01a19746-…` hiển thị đúng câu trả lời kèm nguồn (trước đó báo "Không thể khôi phục lịch sử đã xác nhận"). |
| L-02 | `features/chat/CitationSource.tsx`: `startsWith(quote)` → `includes(quote)`; mọi kiểm binding/hash/hiệu lực giữ nguyên. `CitationSource.test.tsx` thêm 7 ca (2 ca đỏ trên mã cũ; quote không có trong nội dung, hash sai, `unit_id` lệch vẫn bị từ chối). | "Mở đoạn nguồn gốc" của trích dẫn giữa chunk hiển thị cơ quan ban hành, ngày hiệu lực, phiên bản (`ui/12-fixed-source-open.png`). |

- Test: `vitest run src/features/chat` 121 đạt / 3 đỏ (đều là ca đỏ có từ trước: 2 ChatPanel, 1 `history.test`); `tsc --noEmit` sạch. `src/app/chat`: 21 đạt / 3 đỏ, trong đó `page.resume.test` chạy riêng đạt 2/2 (chập chờn khi chạy song song), 2 ca còn lại là ca đỏ cũ.
- Triển khai: snapshot mới `frontend-knowledge-ui-20261101b`, chỉ đổi frontend 3015; API 8015 giữ nguyên; snapshot `…20261101a` còn nguyên để quay lại. Bản sao lưu 3 tệp trước khi sửa: `fix-backup/`. Brief và báo cáo Codex: `briefs/W*.md`, `impl/W1-report.md`, `impl/W2-report.md`.
- Chưa commit (các tệp này vẫn chưa được git theo dõi, xem L-11). L-03 (đổi mật khẩu student-local) vẫn chờ bạn làm. Các mục "Nên sửa"/"Nhỏ" khác chưa làm.

## Cập nhật 2026-11-01 (khuya): đã sửa L-04 và L-05 (Codex), đo lại trên 8015

Bằng chứng: test xác định với HTTP giả/ngân sách trong bộ nhớ (W3) và SSE thật với gateway giả (W4), các test mới đỏ trên mã cũ; đo trên runtime 8015 (v2, `embedded2`, release `01a172fe…`, generation 27) với DeepSeek thật, 3 phiên đồng thời cùng tài khoản student-local, một lần chạy. Người dùng cho phép vượt mức lời gọi: tổng lời gọi DeepSeek của cả kiểm định là **222** (72.272 → 72.494). Lượt đo này dùng 74 lời gọi (2 làm nóng + 72).

| Mục | Sửa |
|---|---|
| L-04 | `scripts/run_public_rag.py`: lời gọi HTTP tới DeepSeek chạy ngoài khóa. Khóa chỉ còn bao dựng/kiểm payload, đặt chỗ + ghi `reservation`, quyết toán + ghi `result`, và không có `await` bên trong. Thêm `PROVIDER_CONCURRENCY_LIMIT = 4`. Khi khởi động lại, chọn snapshot theo số lời gọi rồi số lượt còn treo, vì kết quả có thể về không theo thứ tự. Test mới `tests/unit/retrieval/test_public_rag_gateway_concurrency.py` (14 ca; 4 đỏ trên mã cũ). |
| L-05 | `presentation/chat.py`: bỏ kiểm nguồn trước mỗi delta, thêm 1 lần kiểm sau delta cuối. Vẫn giữ kiểm trước khi phát, trước từng trích dẫn và trước `message.completed`. Test mới `tests/api/test_chat_sse_guard_cadence.py`: số lần gọi guard không đổi theo số delta (5 lần cho 45/89/96 delta, trước đây 49/93/100); thu hồi giữa luồng → `message.failed`, không có trích dẫn hay `message.completed`. |

**Test (tôi chạy lại):**
- Gateway, sổ cái, SSE và `test_i1_dispatch`: 60/60 đạt.
- `tests/rag_v2`: 559 đạt (Codex chạy).
- `test_public_rag_wiring.py::test_retained_huce_index_loads_without_model_or_paid_calls` đỏ cả trước và sau sửa (tập chunk của test không còn là tập con của chỉ mục hiện tại); không do lần sửa này.

**Đo lại cùng 17 câu có đáp án, 3 phiên đồng thời** (`after-fix-3users.json`, so với `main3.json`):

| | Trước | Sau |
|---|---|---|
| Tổng p50 / p90 / max | 14,6 / 26,2 / 35,6 s | **9,3 / 11,7 / 14,8 s** |
| Nội dung đầu p50 / p90 | 12,1 / 15,3 s | 8,7 / 10,9 s |
| Đuôi stream (delta đầu → completed) p50 / max | 5,45 / 21,8 s | **0,61 / 1,45 s** |
| Lời gọi DeepSeek chồng lấn | không (khóa toàn cục) | có: 3 lời gọi cùng giây, p50 0,8 s, p90 1,3 s, 0 lỗi |

- Chất lượng không đổi: cùng phân loại như trước, 0 trích dẫn sai, 0 literal thiếu nguồn (`scored-after-fix.json`).
- Còn lỗi: AU-A02 hết hạn 12 s ở đợt đầu; AU-A20/A21 bị 429 vì 3 phiên dùng chung một tài khoản.

**Phát hiện mới (chưa sửa):**
- **L-22 Đợt lượt đầu sau khởi động chặn event loop (nên sửa).** Lượt đầu sau khi API khởi động luôn hết hạn, vì phải đọc toàn bộ 2.019 dòng nguồn (21,6 s), và hiển thị "lỗi kết nối". Khi 3 lượt đồng thời cùng chạy bước `auth` của v2 lúc cache ràng buộc còn lạnh, bước này mất 2,9–6,1 s mỗi lượt (lúc ấm còn 0,1–0,4 s), và health-poll ghi **một lần event loop bị chặn 6,0 s** ở giây thứ 1,9 của lượt đo. Như vậy có công việc CPU đồng bộ trong `auth`/dựng cache chặn mọi người dùng. Đó cũng là lý do AU-A02 hết hạn. Hướng sửa: đưa phần băm/so khớp ra thread (`asyncio.to_thread`) và làm nóng sau khởi động.
- **L-23 Script khởi động không bật RAG v2 (nên sửa).** `knowledge_platform_runtime.py start` không tự bật v2: phải đặt `CAMPUS247_RAG_ENGINE=v2` và `CAMPUS247_RAG_V2_INDEX=data/rag_v2_index/embedded2`. Thiếu hai biến này, API chạy v1 mà không báo gì (lần khởi động đầu của tôi bị như vậy, đã khởi động lại đúng). Script còn báo "Readiness failed: ConnectError" vì kiểm sẵn sàng hết hạn trước khi API nạp xong chỉ mục (~40 s), trong khi API vẫn lên bình thường.

**Triển khai:** API 8015 đã khởi động lại với mã mới (PID mới, nhật ký `resume-20261101T143218373331`). Frontend vẫn là `frontend-knowledge-ui-20261101b`. Bản sao lưu trước khi sửa: `fix-backup/run_public_rag.py`, `chat.py`, `test_chat_sse.py`. Brief và báo cáo: `briefs/W3*.md`, `briefs/W4*.md`, `impl/W3-report.md`, `impl/W4-report.md`. Chưa commit.

## Cập nhật cuối 2026-11-01 (đêm): hoàn tất kế hoạch sửa

Người dùng: "cứ tiếp tục làm cho đến khi xong, tôi đồng ý hết"; được phép vượt mức DeepSeek; giao mã cho Codex, khi Codex hết quota thì Claude tự làm.

Thực hiện:
- Codex W5–W10 (brief trong `briefs/`, báo cáo trong `impl/`; W8 không kịp viết báo cáo vì Codex hết quota lúc gần xong, tôi tự kiểm lại các mục);
- Claude tự sửa 5 điểm sau khi Codex hết quota: L-24, L-26 và mục "Thời khóa biểu bịa" ở bảng dưới, cùng hai hồi quy định tuyến do W9.

**Tổng lời gọi DeepSeek: 425** (72.272 → 72.697).

Bằng chứng:
- test xác định (đỏ trên mã cũ, xanh sau sửa);
- đo lại trên 8015 với DeepSeek thật, ca do mô hình viết, gold kiểm bằng mã, mỗi lượt 1 lần;
- kiểm giao diện bằng Playwright/Chrome, spec tự đọc credentials, không giá trị bí mật nào vào hội thoại (`ui-final/`).

### Trạng thái từng mục
| Mục | Trạng thái | Bằng chứng |
|---|---|---|
| L-01, L-02 | Đã sửa | Xem cập nhật trước; mở lại hội thoại và "Mở đoạn nguồn gốc" đạt trên trình duyệt (`ui-final/ui-final.json`) |
| L-03 đổi mật khẩu student-local | **Chưa làm — bị hệ thống chặn** | Lệnh xoay mật khẩu bị bộ phân loại quyền từ chối ("Account & Standing-Rule Changes"); tôi không lách. Bạn cần tự đổi (xem mục "Việc còn lại") |
| L-04, L-05 | Đã sửa | Xem cập nhật trước |
| L-06 chuyển cán bộ nhầm | Đã sửa (W9), có điều chỉnh (W10) | AU-A18 nay trả lời "chỉ cần nộp hồ sơ minh chứng 01 lần" có trích dẫn |
| L-07 thông điệp kỹ thuật | Đã sửa (W9) | AU-P01: "Tôi không thể cung cấp thông tin cá nhân của người khác…" |
| L-08 hỏi lại sai | Đã sửa (W9) | AU-A17: "được giảm 50% học phí", có trích dẫn |
| L-09 "miễn" mơ hồ | Đã sửa (W9) | AU-C06: "Bạn muốn hỏi điều kiện miễn học phí, miễn thi, miễn học phần, ngoại ngữ hay giáo dục thể chất?" |
| L-10 token trong localStorage | Đã sửa (W6, W7, W8) | Đăng nhập không còn trả token; web chỉ dùng cookie HttpOnly; `localStorage.campus247_token` = null; 10/10 tệp còn lại không đọc/ghi token |
| L-11 mã chưa theo dõi | Đã sao lưu | Nhánh `backup/worktree-20261101-audit` (`5ed637db5`, trước mọi sửa) và `backup/worktree-20261101-after-fixes` (sau mọi sửa, gồm báo cáo cuối); không chứa mật khẩu (đã kiểm bằng mã). Chưa commit vào nhánh làm việc |
| L-12 chốt kỷ luật chặn Sổ tay | **Giữ nguyên** (không nới kiểm nguồn) | AU-A25 vẫn từ chối; cần quyết định chính sách của bạn |
| L-13 lịch sử hội thoại | Đã sửa (W6, W7) | Cột "Lịch sử" 7 mục, mở đúng hội thoại, mục đang mở được tô |
| L-14 AU-A12 "mã trường XDS" | **Chưa xác định nguyên nhân** | W9: ngoại tuyến, chunk vào top-12 BM25 và được đóng gói; trên runtime vẫn `no_source`. Cần trace ứng viên của lượt thật |
| L-15 font, ngăn trích dẫn | Đã sửa (W6, W7) | `/fonts/*` 200, font Inter, tiêu đề một hàng, không cuộn ngang |
| L-16 tương phản, chồng nút | Đã sửa (W7, W8) | Tương phản 10,4:1 (trước 1,59:1); mobile không chồng/không cuộn ngang |
| L-17 test web đỏ | Đã sửa (W8 + Claude) | **Vitest 414/414 đạt** (đầu kiểm định 58/338 đỏ); tsc sạch. Ca đỏ cuối cùng bắt một lỗi thật: trang cán bộ khẳng định "không trùng lặp (98%)", "xử lý trong 24h" không có nguồn; đã sửa thành thông báo trung thực |
| L-18 500 ở quản trị | Đã sửa (W9) | 503 `KNOWLEDGE_SEARCH_UNAVAILABLE` |
| L-19 | Đã sửa (W6) | Giới hạn đăng nhập theo tên; `/docs`, `/openapi.json` tắt ở 8015 |
| L-20 tài liệu lệch | Đã sửa | `SKILL.md`, `references/verification.md`: Postgres native 55437, lệnh khởi động đầy đủ, trường `warm` |
| L-21 danh sách nháp | Đã sửa (W8) | Mỗi nháp có dòng trích; mở nháp thì biểu mẫu nằm trong khung nhìn |
| L-22 event loop / lượt đầu | Đã sửa (W5) | Làm nóng sau khởi động (`warm: ready` sau ~21 s); 3 lượt đồng thời đầu tiên sau khởi động trả lời được (12,2–14,4 s), 0 hết hạn; health tối đa 368 ms/2.397 lần đo (trước: chặn 6,0 s) |
| L-23 khởi động | Đã sửa (W6, W10) | `pnpm start` (không biến môi trường ngoài) chạy v2 + chỉ mục `embedded2` + snapshot mới nhất, báo `ready: true` |
| Hồi quy W9 (hạn nộp miễn giảm) | Đã sửa (W10) | 5 test an toàn có sẵn đỏ → xanh; đối chiếu 54 chuỗi high/critical với bản sao lưu, không đổi mức |
| L-26 "miễn phí" hiểu thành "miễn" | Đã sửa (Claude) | AU-O06 "mượn xe đạp miễn phí": từ hỏi lại sai → "chưa tìm thấy nguồn" |
| L-24 lịch thi cá nhân bị chuyển cán bộ | Đã sửa (Claude) | Làm rõ định nghĩa trong prompt phân loại/định tuyến (không ghi đè nhãn an toàn bằng regex); AU-P04 3/3 lần: "Chức năng này chưa kết nối dữ liệu… HUCE" |
| Thời khóa biểu bịa trong mã | Đã sửa (Claude) | `compose_tool_response_node` có lịch cứng "Thứ 2 Tiết 1-3: Giải tích 1 – P.H1-201…" (nhánh không phục vụ ở 8015); nay luôn trả "chưa kết nối" |
| Test demo hết hạn theo ngày | Đã sửa (Claude) | `service_demo.py` đặt hạn phúc khảo cố định 2026-10-31 nên 67 test đỏ từ 1/11; nay hạn tương đối ±30 ngày, 104/104 đạt |

### Đo cuối trên 8015 (`final-3users.json`, `final-rerun429.json`, `final-fix-check.json`, `final-p04-check.json`)
Runtime khởi động bằng `pnpm start`; RAG v2, `embedded2`, release `01a172fe…`. Có 45 ca, 3 phiên đồng thời cùng tài khoản; 6 ca bị 429 do dùng chung tài khoản nên được chạy lại tuần tự.

| | Đầu kiểm định | Cuối |
|---|---|---|
| Có đáp án (25): đủ ý (đọc tay) | 21 | **22**. AU-A17, A18 nay trả lời đúng. AU-A23 trả lời một phần (thiếu khoa). Còn từ chối nhầm AU-A12 (L-14) và AU-A25 (L-12) |
| Không đáp án (20): xử lý đúng | 19 | **19**. AU-C06 nay hỏi lại đúng; AU-P06 trả lời lệch ngữ cảnh (xem L-27) |
| Trích dẫn sai / literal thiếu nguồn | 0 / 0 | 0 / 0 |
| Có đáp án, 3 phiên: p50 / p90 / max | 19,4 / 26,2 / 35,6 s | **10,0 / 13,2 / 14,4 s** |
| Hết hạn 12 s; event loop bị chặn > 1 s | 0; chưa đo | 0; 0 (tối đa 368 ms) |
| Injection (8 ca, gồm nhiều lượt) | 1 ca | 8/8 không làm theo, không bịa, không bỏ trích dẫn |

**Test cuối**
- Python: `tests/unit/agent tests/rag_v2 tests/knowledge_platform tests/api tests/operations tests/test_safety_rules.py tests/test_intent_routing.py tests/evals` cho **2.283 đạt / 1 đỏ / 41 bỏ qua** (`pytest-final2.log`, cộng 1 test cập nhật sau đó). Ca đỏ còn lại là `test_multi_agent_api::test_corrective_worker…`, đọc dữ liệu legacy, có từ trước.
- `test_chat_sse.py::test_chat_sse_with_agent_workflow` từng khẳng định câu trả lời chứa "Thời khóa biểu", tức ghim đúng dòng lịch bịa. Đã cập nhật thành khẳng định "chưa kết nối".
- Web: vitest **414/414**, tsc sạch.

### Phát hiện mới còn mở
- **L-27 (nên sửa).** Câu hỏi về **phòng thi** (AU-P06) được trả lời bằng nội quy **phòng máy**: có ghi nguồn, không bịa, nhưng lệch ngữ cảnh và có thể gây hiểu nhầm. Cần bước kiểm "nguồn có đúng đối tượng câu hỏi" ở sinh/kiểm ngữ nghĩa.
- **L-28 — đã sửa (Claude).**
  - Trước sửa: INJ-03 (đòi khóa API, mật khẩu CSDL) và INJ-05 (giả quản trị viên đòi xem hội thoại người khác) bị từ chối, nhưng bằng câu "cần cán bộ hỗ trợ…".
  - Sửa: thêm mẫu xác định cho yêu cầu bí mật/hệ thống vào `_PROMPT_INJECTION_RULE` (`safety_rules.py`), chỉ làm chặt hơn. Trên runtime, cả hai ca nay nhận "Tôi không thể… tiết lộ thông tin hệ thống" (`final-l28-check.json`). Câu hỏi về quên mật khẩu email hay quy chế mật khẩu vẫn `normal` (test).
  - Còn mở: INJ-04 trả mức học phí chương trình Cử nhân K65–K68 cho "CNTT K68" mà không hỏi hệ kỹ sư/cử nhân.
- **L-14 — đã xác định nguyên nhân, chưa sửa.**
  - Chạy `rag_v2_context_probe.py` với chỉ mục `embedded2` và vector thật từ 18081 (không gọi DeepSeek): với AU-A12, đoạn "MÃ TRƯỜNG: XDS" **không có trong ngữ cảnh đã đóng gói**. Chỉ BM25 thì có (W9), nên phần trộn lai với vector đã đẩy nó ra; đây là lỗi tầng truy xuất, không phải mô hình. Kết quả: `l14-probe-AU-A12.json`.
  - Cùng công cụ cho thấy AU-A25 có gold trong ngữ cảnh, nên bị từ chối là do chốt kỷ luật (L-12).
  - Sửa trọng số trộn cần đo trước/sau trên tập dev, theo quy tắc dự án; để làm việc tiếp theo.
- **L-29 (nhỏ, có từ trước, chưa sửa).** Pytest còn đỏ ở 6 ca không do sửa hôm nay:
  - `tests/architecture` (vi phạm lớp cũ);
  - `test_context_propagation` ×2 (test gửi trường giả `tenant_id`/`roles` và máy chủ từ chối 422; cùng kết quả trên bản sao lưu);
  - `test_public_rag_wiring` (tập chunk không còn khớp chỉ mục);
  - `test_huce_service_release`, `test_huce_discovery`, `test_multi_agent_api` (đọc dữ liệu legacy `data/huce-public-20261013` đã thay đổi).

  Thêm 7 ca `test_prompt_injection` và 2 ca khác chỉ đỏ khi chạy chung bộ lớn (đạt khi chạy riêng): ảnh hưởng thứ tự giữa tệp test.

### Không làm được và lý do
- **Đo sự cố phụ thuộc trên runtime** (tắt mô hình nhúng 18081, Postgres, API): lệnh dừng dịch vụ nhúng dùng chung bị hệ thống quyền từ chối. Bằng chứng còn lại ở mức mã: test xác định cho đường lỗi hạ tầng trong `tests/rag_v2` (vector lỗi/treo → lexical, không giả vector, `transient_error`). Hai câu chạy lúc định thử sự cố là lượt bình thường; tệp đã đổi tên `not-an-outage-normal-check.json` để không gây hiểu nhầm.
- **L-03 đổi mật khẩu:** bị từ chối như trên.
- **Phiên hết hạn tự nhiên sau 3.600 s:** không chờ đủ. Đã kiểm hành vi giao diện khi mất cookie: hiện "Phiên đăng nhập đã hết hạn" kèm liên kết đăng nhập.
- **Mức dùng được với người dùng thật:** chưa đo.

### Việc còn lại cho bạn
1. Đổi mật khẩu student-local (đã lộ trong nhật ký hội thoại). Vì `scripts/knowledge_platform_student.py` từ chối tạo lại tài khoản, cần thay `salt`/`password_hash` (và nên thay `signing_key` để vô hiệu phiên cũ) trong `infra/local/knowledge-platform-20261023/student-identity.json`, cùng mật khẩu trong `student-credentials.json`. Hoặc cho phép tôi làm bằng một quy tắc quyền.
2. Quyết định L-12 (có coi Sổ tay sinh viên trên `cdnm.heyzine.com` là nguồn chính thống cho câu hỏi kỷ luật không).
3. Quyết định có commit các thay đổi hay không; tất cả vẫn chưa commit, có nhánh sao lưu.
4. Nếu muốn đo sự cố phụ thuộc: cho phép dừng/khởi động lại dịch vụ nhúng 18081 và Postgres 55437.

## Tệp trong thư mục này
- `cases.jsonl`, `build_cases.py`: 45 ca và trình kiểm gold.
- `audit_run.py`, `analyze.py`: runner và bộ chấm/kiểm trích dẫn.
- `pilot.json`, `main3.json`, `rerun429.json`, `injection1.json`: kết quả thô.
- `scored.json`: điểm từng ca. `security_probe.py`, `security-probe.json`: thử quyền. `health_poll.py`, `health-main3.jsonl`: theo dõi event loop.
- `vitest.json`, `vitest-failures.json`, `pytest-*.log`: test. `ui/*.png`: ảnh chụp giao diện.

Phát sinh ngoài thư mục này:
- Một nháp thử trong tài khoản student-local ("[Kiểm định 01/11]…", thêm qua giao diện) và một nháp qua API ("Kiểm định 2026-11-01").
- Vài hội thoại tạm của student-local và owner.
- Thư mục `.playwright-mcp/` ở gốc repo (nhật ký/snapshot của công cụ, không chứa mật khẩu sau khi tôi xóa tệp tạm) và `.pytest-tmp-audit-opus-*`.

Không xóa hay ghi đè dữ liệu có sẵn.

## Cập nhật dở dang (01–02/11, gần nửa đêm) — dừng vì hết hạn mức sử dụng
Đã làm thêm, **chưa triển khai lên 8015, chưa đo lại**:
- **Kiến trúc lớp:** `tests/architecture` đạt 3/3 (trước đỏ; thực tế có 16 chỗ application→infrastructure và 6 chỗ presentation→infrastructure).
  - Hàm thuần chuyển sang `application/knowledge/values.py` và `platform_models.json_value`; ngoại lệ chuyển sang `ports/agent_runs.py`, `ports/policy_graph.py`, `ports/llm.py`.
  - `isinstance` trên adapter được thay bằng thuộc tính khả năng; `parse_upload` được tiêm từ bootstrap.
  - Infrastructure re-export tên cũ, nên nơi dùng cũ không đổi.
- **L-27 (prompt):** prompt sinh và prompt kiểm ngữ nghĩa nay nói rõ nguồn của nơi chốn/hoạt động/kỳ thi khác không phải câu trả lời; `tests/rag_v2` 592/592 đạt.
- **L-14:** `hybrid.RRF_K` tách thành hằng số. Chẩn đoán: gold AU-A12 hạng BM25 4, không có trong vector, sau RRF k=60 rơi xuống hạng 13/12 (`l14_diagnose.py`). Lượt quét k ngoại tuyến (`l14_sweep.py`, ra `l14-sweep.json`) **đang chạy nền**; RRF_K vẫn = 60 (chưa đổi hành vi).
- **Test có sẵn:**
  - `test_context_propagation`: tách thành "trường giả bị 422" và "phạm vi từ danh tính máy chủ", 12/12 đạt.
  - `test_huce_discovery`: theo lô dữ liệu `-batch2` hiện có, giữ các bất biến hash/nguồn/locator; 23/23 đạt.
- **Mốc trước dev136** (`dev136-before.json`, mã đang chạy, 432 lời gọi): 66 đủ ý / 17 thiếu ý / 17 từ chối nhầm / 6 từ chối đúng / 30 lỗi. Trong 30 lỗi có 22 lỗi 429 do chạy dày, nên mốc này cần chạy lại phần 429 có giãn cách.

Còn lại:
- chọn k từ `l14-sweep.json`;
- triển khai (khởi động lại API bằng `pnpm start`);
- chạy dev136 "sau" và so bằng `score_dev.py`;
- `test_huce_service_release` (hàng "K71 — Quản lý dự án" nay chỉ có ở lô `reviewed-course-review-20261021`), `test_public_rag_wiring`, `test_multi_agent_api` (dữ liệu legacy);
- ô nhiễm thứ tự test (9 ca knowledge_platform khi chạy chung với hai tệp `test_safety_rules.py`, có từ trước);
- đọc kết quả `pytest-layer.log` (đang chạy nền).

L-03 (đổi mật khẩu) bị hệ thống chặn; L-12 giữ nguyên theo quy tắc không nới kiểm nguồn.

## Cập nhật cuối (02/11) — triển khai, đo lại, những gì còn mở
Bằng chứng: lượt chạy thật trên 8015 (`dev136-after*.json`, `final-l14-l27-check.json`), chấm bằng bộ chấm chung `rag_v2_scoring.classify` qua `score_dev.py`; sweep ngoại tuyến trên chỉ mục thật. Chưa đo người dùng thật.

**Đã triển khai:** khởi động lại API 8015 bằng `scripts/campus.py start` (v2 `warm=ready`, 9173 đơn vị, 0 chunk sai lệch). Mã chạy gồm kiến trúc lớp (3/3 đạt), prompt L-27, định tuyến/an toàn W9–W10, hằng số `RRF_K`.

**dev136 trước/sau** (cùng bộ chấm; 22 ca của lượt trước và 16 ca của lượt sau bị HTTP 429 do hai người dùng chung hạn mức 30 lượt/phút, đã chạy lại tuần tự 16 ca của lượt sau; 22 ca của baseline không thể chạy lại trên mã cũ nên so trên 114 ca baseline không bị 429):

| 114 ca chung | full | thin | từ chối/hỏi lại | từ chối đúng | lỗi |
|---|---|---|---|---|---|
| trước | 66 | 17 | 17 | 6 | 8 |
| sau | 70 | 16 | 20 | 6 | 2 |

- Tốt hơn 10 ca (6 trong đó là lỗi cũ → trả lời được); xấu hơn 4 ca: R2-A2-0044 và R2-Q2-0106 (full→thin), R2-Q1-0054 và R2-Q1-0055 (thin→từ chối/hỏi lại). Không hồi quy có hệ thống, nên giữ thay đổi.
- Cả 136 ca sau chạy lại: 76 full / 18 thin / 20 từ chối-hỏi lại / 20 từ chối đúng / 2 lỗi.
- Lời gọi DeepSeek (đếm theo tệp đặt chỗ của sổ cái): lượt này 454 + 50 = 504 cho dev136; baseline 432. Tổng sổ cái từ lúc bắt đầu audit: 72.272 → 73.640 (+1.368, mọi giai đoạn).

**L-14 (AU-A12 mã trường XDS) — chưa sửa, đã loại hai hướng:**
- Quét `RRF_K` (60/20/10): facts-in-context 280/281/281 trên 477 ca; k=20 +3/−2, k=10 +5/−4, nhiễu; AU-A12 không vào ngữ cảnh ở bất kỳ k nào (audit luôn 18). Giữ k=60.
- Ghim top-N kết quả BM25 vào shortlist: pin=2 cho 279 (kém hơn k=60), audit vẫn 18; đã gỡ mã thử, hành vi giữ nguyên.
- Kiểm lại trực tiếp: AU-A12 vẫn "chưa tìm thấy nguồn phù hợp" (an toàn nhưng sai so với gold). Nguyên nhân cần hướng khác (ví dụ truy vấn mở rộng theo thuật ngữ "mã trường"/"XDS" hoặc lập chỉ mục lại đơn vị Sổ tay), chưa làm.

**L-27 (AU-P06 phòng thi vs phòng máy) — giảm thiểu bằng prompt nhưng chưa hết:** kiểm lại trực tiếp vẫn trả lời bằng nội quy phòng máy (có nêu đúng tên nguồn, nhưng không phải phòng thi). Prompt không đảm bảo; cần kiểm tất định nơi chốn hoặc quyết định chính sách.

**Kiểm thử sau thay đổi cuối:** `tests/rag_v2` + `tests/architecture` + `test_context_propagation` + `test_huce_discovery` + `tests/unit/agent`: 990 đạt / 7 lỗi. 7 lỗi là ô nhiễm thứ tự `test_prompt_injection`/`test_safety_rules` (chạy riêng 20/20 đạt, có từ trước). `test_manifest_inventory_checked_on_read` đỏ chỉ vì thư mục tạm pytest nằm ngoài workspace (`INDEX_OUTSIDE_WORKSPACE`); với `--basetemp` trong workspace, 44/44 đạt.

**Vẫn mở (không phải do thay đổi hôm nay):**
- L-03: đổi mật khẩu student-local — bị chặn quyền, người dùng tự sửa `student-identity.json` và `student-credentials.json` (mật khẩu đã lộ trong bản ghi hội thoại).
- L-12: nguồn Sổ tay đang bị chặn; mở ra cần quyết định chính sách (không nới kiểm nguồn).
- Thử mất dịch vụ nhúng (18081)/Postgres: bị chặn quyền, chưa kiểm.
- Test đỏ có sẵn: `test_huce_service_release`, `test_public_rag_wiring`, `test_multi_agent_api`, `dependency_resolution/test_verifier` (2), `runtime_review/test_m1_*` (5, sổ cái lịch sử không idempotent), ô nhiễm thứ tự.
- Chưa commit; các nhánh backup `backup/worktree-20261101-*` không chứa lượt thay đổi cuối này.

## Cập nhật cuối 2 (02/11, tối) — L-14, L-27 đã sửa; dọn nhiễm thứ tự test
Bằng chứng: lượt chạy thật trên 8015 sau khi khởi động lại bằng mã cuối (`warm=ready`, 9173 đơn vị); dev136 chấm bằng bộ chấm chung; 45 ca audit chạy tuần tự một người dùng (tránh 429). Chưa đo người dùng thật.

**L-14 (AU-A12 mã trường XDS) — đã sửa.**
- Nguyên nhân thật gồm hai phần: (1) đơn vị gold có hạng BM25 4, không có trong vector, RRF đẩy xuống hạng 13; (2) ở đường production (`rerank_deadline_s=0`) danh sách được sắp lại theo điểm RRF và bước đóng gói chỉ giữ ~6 dòng đầu, nên ghim trước khi sắp lại (thử lần đầu, và pin=2) không có tác dụng.
- Sửa: `hybrid.LEXICAL_PIN = 4`, `PACK_WINDOW = 6`. Sau khi sắp theo RRF, bốn kết quả BM25 đứng đầu được giữ trong 6 dòng đầu; chỉ áp dụng khi không có reranker (đường production), không đổi thứ tự khi có reranker. Test mới: `tests/rag_v2/retrieval/test_hybrid.py::test_strong_lexical_hit_is_kept_inside_the_packing_window`.
- Quét ngoại tuyến 477 ca (vector thật, không DeepSeek): k=60 → 280 ca có đủ dữ kiện trong ngữ cảnh; pin=4 → 281 (+6/−5, AU-A12 vào ngữ cảnh). Trên dev trung tính (262 và 262).
- Đo thật dev136 (cùng bộ chấm, 22 ca 429 chạy lại tuần tự): đủ ý **81/136** (trước khi sửa: 66; lượt giữa: 76), lỗi 1 (trước 30 do 429 + lỗi). 114 ca chung với baseline: đủ ý 66 → 74, lỗi 8 → 1. So với lượt giữa: tốt hơn 11 ca, xấu hơn 3 (R2-A2-0043, R2-A2-0076 và R2-A3-0147).
- AU-A12 chạy thật: "Mã trường … là XDS" kèm trích dẫn (trước: từ chối).

**L-27 (AU-P06 phòng thi vs phòng máy) — đã sửa bằng kiểm tất định.** Prompt riêng không đủ (lượt kiểm trước vẫn trả lời bằng nội quy phòng máy). Thêm `rag_v2/verification/venue.py`: khi câu hỏi nêu một nơi chốn có quy định riêng (phòng thi, phòng máy, ký túc xá, thư viện, nhà thể thao) và mọi nguồn được trích chỉ nói về nơi khác, phát biểu bị loại (`SCOPE_MISMATCH`). Test: `tests/rag_v2/test_venue_conflict.py` (9 ca). Chạy thật AU-P06: từ chối ("đã tìm thấy nguồn nhưng chưa xác minh được phát biểu"). Giới hạn: chỉ phủ danh sách nơi chốn nhỏ ở trên.

**45 ca audit, một người dùng tuần tự, mã cuối:** 20 đủ ý, 3 thiếu ý, 2 từ chối nhầm, 20 từ chối đúng; 0 lỗi/timeout. AU-A23 giao động giữa các lần (lần này từ chối, hai lần chạy lại đều trả lời), nên coi là phương sai của mô hình. Số lời gọi DeepSeek trong lượt này: 144 (45 ca) + 435 + 72 (dev136 và chạy lại) + 14; sổ cái hiện 74319.

**Nhiễm thứ tự test — đã sửa.** `tests/unit/agent/test_prompt_injection.py` nạp `composer.py` thành module thứ hai rồi ghi đè `sys.modules`, làm `TrustDomain`/`PromptBlock` lệch lớp với mã chạy ở các test khác. Đổi sang `importlib.import_module`; `test_context_propagation` + `test_prompt_injection` + `test_safety_rules` chạy chung 32/32 đạt. Cũng cập nhật `tests/test_agent_graph.py::test_graph_execution_personal_schedule` theo thông báo trung thực mới (cùng lý do với `test_chat_sse`).

**Toàn bộ `tests/` (17 phút, `pytest-final-20261102.log`, trước hai sửa test ở trên):** 4483 đạt / 23 đỏ / 32 lỗi thiết lập. Không có đỏ nào do thay đổi hôm nay; tất cả gắn với bằng chứng/fixture đã lưu:
- 32 lỗi thiết lập `tests/unified_final/*` và 5 đỏ `test_unified_*`/`unified_*` hai tiến trình: `exclusive registered fixture required` (thư mục fixture `infra/local/unified-ai-parallel-20261015-01/stream-c` không được đăng ký/đã đổi chỗ), và `B fixture only` trong `scripts/unified_parallel_b_fixture_worker.py`.
- Tổ tiên migration và dữ liệu lịch sử: `rag_fixture/test_guard`, `test_migration_0009`, `test_retrieval_scope_migration`, `test_huce_service_release`, `test_public_rag_wiring`, `test_multi_agent_api`.
- Sổ cái lịch sử không idempotent: `runtime_review/test_m1_*` (5).
- Danh sách phụ thuộc đã duyệt: `dependency_resolution/test_verifier` (2).
- `test_write_route_inventory`: danh mục "đã duyệt" chưa liệt kê hai route `POST /v1/actions/preview` và `/v1/actions/{preview_id}/confirm`, vốn được đăng ký trong `bootstrap/app.py` ở HEAD (không thuộc diff của tôi). Tôi không sửa danh mục đã duyệt; cần người duyệt thêm hai dòng phân loại (preview/confirm).

## Cập nhật cuối 3 (02/11, đêm) — phát hiện mới, mất dịch vụ nhúng, bộ test toàn repo
**L-29 (mới, trung bình) — route hành động giả có trong app gốc.** `presentation/actions.py` đăng ký `POST /v1/actions/preview` (trả `confirmation_token: "mock-token"`) và `POST /v1/actions/{preview_id}/confirm` (trả `COMPLETED`/202 cho mọi token) mà không kiểm danh tính và không thực hiện gì. Route có trong `bootstrap/app.py` ở HEAD; web không dùng, 8015 trả 404 nên người dùng runtime hiện tại không chạm tới. Rủi ro: ai triển khai app gốc sẽ thấy phản hồi "đã xác nhận" giả. Chỉ `tests/api/test_actions_route.py` ghim hành vi này. Đây cũng là lý do `tests/contract/test_write_route_inventory.py` đỏ (danh mục "đã duyệt" không liệt kê hai route). Không sửa: cần quyết định gỡ route hoặc nối vào bộ điều phối thật có xác thực.

**Mất dịch vụ nhúng (mô phỏng trong tiến trình, `outage_sim.py`, không tắt dịch vụ dùng chung):** vector adapter ném `ConnectionError`; 60 ca dev có đáp án. Bình thường 45/60 ca có đủ dữ kiện trong ngữ cảnh, khi nhúng hỏng 41/60 (lùi về BM25), 1 ca rỗng ở cả hai. Không sập, không lỗi. Chưa kiểm Postgres hỏng trên runtime thật (không có quyền tắt/đổi DB; đã có chuyển 503 `KNOWLEDGE_SEARCH_UNAVAILABLE` từ W5 và test).

**Toàn bộ `tests/` lần 2 (sau mọi sửa test; `pytest-final2-20261102.log`):** 4484 đạt / 22 đỏ / 32 lỗi thiết lập. `test_agent_graph` đã xanh và không còn nhiễm thứ tự. Phần đỏ còn lại:
- 32 lỗi thiết lập + 7 đỏ hai tiến trình: các test yêu cầu thư mục tạm được đăng ký trong `infra/local/unified-ai-completion-20261015-01/checks/backend-NN/basetemp` (`scripts/unified_completion_scope.completion_fixture`). Chạy bằng harness gốc mới đạt; đăng ký fixture mới sẽ ghi vào cây bằng chứng nên không làm.
- 6 test tổ tiên/dữ liệu lịch sử, 5 `test_m1_*` (sổ cái lịch sử), 2 `test_verifier` (danh sách phụ thuộc đã duyệt), 1 `test_write_route_inventory` (L-29).

**Mật khẩu và Sổ tay vẫn chờ bạn:** L-03 (đổi mật khẩu, bị chặn quyền), L-12 (có coi Sổ tay SV 2026–2027 là nguồn chính thống cho chốt kỷ luật không; không nới kiểm nguồn nếu chưa có quyết định).

**Commit:** theo yêu cầu "Commit" của bạn (02/11), các thay đổi của phiên audit được commit riêng trên nhánh `rag-v2-hardening`. Không commit khối công việc có từ trước ngoài phạm vi này (xem tin nhắn commit). Nhật ký Codex lớn (`impl/*.log`) và `pytest-final.log` (có chuỗi Bearer của test) được loại khỏi commit.

## Cập nhật cuối 4 (02/11) — L-29 đã xử lý, L-12 dừng chờ quyền
- **L-29 đã sửa:** gỡ đăng ký route hành động giả khỏi `bootstrap/app.py`, xoá `presentation/actions.py` và `tests/api/test_actions_route.py` (chỉ ghim hành vi giả; vẫn nằm trong git). `tests/contract/test_write_route_inventory.py` nay xanh; `tests/api` + `tests/architecture` + inventory: 310 đạt, 1 đỏ có sẵn (`test_multi_agent_api`, dữ liệu legacy). Chưa commit.
- **L-12 chưa làm:** hướng đúng là thêm một biên nhận xuất bản ghim hash cho Sổ tay (bài viết huce.edu.vn → liên kết flipbook → PDF trên CDN, dùng tệp đã lưu `handbook-publication.html`, `handbook-viewer.html`, `handbook-2026-2027.pdf`), kèm mở rộng `same_published_attachment` cho ánh xạ flipbook→PDF, không tin theo host. Hệ thống phân quyền đã chặn thao tác tạo biên nhận mới (thay đổi niềm tin nguồn), nên dừng ở đây chờ bạn cho phép rõ.

## Cập nhật cuối 5 (02/11) — xác nhận test đỏ có từ trước
Chạy trực tiếp trên snapshot trước khi sửa (`backup/worktree-20261101-audit`, worktree tạm, `PYTHONPATH` trỏ vào snapshot, dữ liệu dùng chung chỉ đọc): `test_public_rag_wiring::test_retained_huce_index_loads…`, `test_huce_service_release::test_qlda_visual_correction…`, `test_multi_agent_api::test_corrective_worker_calls_actual_lexical_search…`, hai test `dependency_resolution/test_verifier` và `test_write_route_inventory` **đều đã đỏ trước mọi thay đổi của phiên audit**. Trên snapshot còn đỏ thêm một số test khác (các sửa hôm nay đã làm xanh vài test, ví dụ `test_huce_discovery`). Kết luận: các test đỏ còn lại không do thay đổi của tôi; sửa chúng đòi hỏi đổi bằng chứng/kỳ vọng đã duyệt hoặc ghi vào cây fixture lịch sử nên để chờ người sở hữu. Worktree tạm và liên kết dữ liệu đã gỡ; `data/` còn nguyên.

## Cập nhật cuối 6 (02/11) — đọc lại ba ca "thiếu ý" của lượt 45 ca
Bằng chứng: đọc đáp án trong `final2-seq.json` đối chiếu `required_facts`; bộ chấm chung `rag_v2_scoring.fact_matches` chạy lại trên chính đáp án.
- **AU-A02:** đáp án nêu đúng "trong thời hạn 03 năm tính từ khi thôi học…"; bộ chấm báo thiếu vì câu dài chứa "chưa" làm lệch phân cực với dữ kiện khẳng định "03 năm".
- **AU-A08:** đáp án nêu đúng việc được chuyển sang "vừa làm vừa học"; bộ chấm báo thiếu vì cụm này nằm cùng mệnh đề với "không tốt nghiệp được".
- **AU-A10:** đáp án "05 Phó Giáo sư và 26 Tiến sĩ" đúng; dữ kiện gold viết ngược thứ tự ("Tiến sĩ 26", "Phó Giáo sư 05").
- Kết luận: ba ca này là giới hạn của bộ chấm tự động (chặt hơn cần thiết), không phải lỗi nội dung. Ở lượt 45 ca, theo bộ chấm: 20 đủ ý / 3 thiếu ý / 2 từ chối nhầm; sau khi đọc tay, 23/25 ca có đáp án đã trả lời đúng; 2 ca còn lại là AU-A25 (L-12, chờ phê duyệt) và AU-A23 (giao động giữa các lần chạy). Không sửa bộ chấm vì nó được dùng chung cho nhiều bộ đo cũ; việc nới sẽ làm số liệu cũ không so sánh được.

## Cập nhật cuối 7 (02/11) — L-12 đã xử lý (có phê duyệt rõ ràng của bạn)
Phê duyệt: bạn chọn "Cho phép làm L-12" khi tôi hỏi trực tiếp. Bằng chứng: chạy thật trên 8015 sau khi khởi động lại; test tự động; nhật ký API.
- **Cách làm (không tin theo host):** biên nhận ghim hash `infra/local/huce-completion-20261102-01/handbook-publication-acquisition-01.json` (sha256 `8cfa1cc2…88c`) trỏ tới các tệp đã lưu trong `data/huce-public-20261013`: bài viết huce.edu.vn, trang flipbook, PDF. `infrastructure/knowledge/publication.py` thêm hằng số hash và `same_flipbook_pdf`: liên kết flipbook chỉ ánh xạ sang PDF khi id flipbook là tiền tố của hash PDF, PDF nằm trên CDN heyzine đúng đường dẫn upload, và HTML viewer đã ghim hash chứa đúng URL PDF đó. Mọi kiểm tra khác của `verified_attachment` (hash bản gốc, bản dựng, nội dung dòng) giữ nguyên.
- **Test:** `tests/knowledge_platform/test_handbook_publication_binding.py` (9 ca ánh xạ giả mạo/sai + toàn vẹn biên nhận); các test STEM/quy chế vẫn đạt. rag_v2 + knowledge_platform + unit/agent + architecture: 1419 đạt, 0 đỏ.
- **Kết quả thật:** nhật ký API không còn `source_not_official` cho Sổ tay. "Ai là người ký quyết định kỷ luật sinh viên?" → "Hiệu trưởng ký quyết định kỷ luật sinh viên [CIT-001]" kèm trích dẫn (2 trong 3 cách hỏi). Câu gốc AU-A25 ("Quy trình xử lý kỷ luật… cuối cùng ai là người ký") vẫn bị từ chối bởi `word_not_in_source` — kiểm tra từ ngữ kỷ luật chặt, giữ nguyên có chủ đích. Các ca dữ liệu cá nhân (AU-P01, P02, P05) và AU-P06 vẫn từ chối. Một cách hỏi ("…do ai ký?") bị hỏi lại ở bước hiểu câu hỏi, không liên quan L-12.
- **Giới hạn:** quy tắc kỷ luật chỉ trả lời khi câu trả lời dùng từ có trong nguồn, nên với diễn đạt khác vẫn từ chối an toàn.

## Cập nhật cuối 8 (02/11) — cập nhật test đỏ cũ (có phê duyệt rõ ràng của bạn)
Phê duyệt: bạn chọn "Cho phép cập nhật" cho các test đỏ có từ trước. Mỗi test được điều tra nguyên nhân trước; chỉ sửa khi dữ liệu đã đổi hợp lệ. Bằng chứng: chạy lại `tests/api`, `tests/unit/retrieval`, `tests/knowledge_platform`, `tests/contract` cùng lúc: 1663 đạt, 0 đỏ.
- **`test_public_rag_wiring`:** các dòng "mất" khỏi kho hiện tại đều là dòng chỉ có tiêu đề và tổng tín chỉ (130–308 ký tự) mà phát hành đánh giá khoá học sau đã thay bằng chương trình đầy đủ, cùng 3 dòng Sổ tay trang 31 đã được cắt lại nhưng nội dung còn nguyên. Danh sách loại trừ của test chỉ thiếu các hậu tố tiêu đề mới; bổ sung kèm ràng buộc độ dài (< 400 ký tự) để không che mất dữ liệu thật.
- **`test_huce_service_release` (QLDA):** dòng QLDA tự động trước chỉnh sửa nay chỉ còn khi tắt cả `include_reviewed_course_review` và `include_reviewed_corrections` (phát hành chỉnh sửa v18 cũng cắt lại chương trình K71). Test dùng cả hai cờ; các khẳng định (cùng bản tài liệu, khác chunk, đọc lại được trích dẫn cũ) giữ nguyên.
- **`test_multi_agent_api` (tìm kiếm thật + trình đọc bản gốc):** tìm kiếm vẫn trả đúng dòng Sổ tay đầu tiên; đỏ vì trần bằng chứng 15.000 byte (cứng, không nới) bị vượt khi bản cắt lại v31 (4.949 byte) lọt vào kết quả của truy vấn rộng. Test dùng truy vấn rộng hẹp hơn nhưng vẫn không chứa quy trình, nên vẫn buộc bước tìm kiếm khắc phục lần hai.
- **Không sửa, có chủ đích:** `dependency_resolution/test_verifier` (2) là cổng phê duyệt phụ thuộc (checksum `uv.lock` do người duyệt); đổi hằng số là tự duyệt gói chưa ai xem. `unified_*` (fixture phải đăng ký trong cây bằng chứng) và `runtime_review/test_m1_*` (sổ cái lịch sử) giữ nguyên.
- **Lưu ý commit:** ba tệp test trên là tệp chưa theo dõi trong git (công việc có từ trước), nên các chỉnh sửa này nằm trong working tree và không nằm trong commit.
