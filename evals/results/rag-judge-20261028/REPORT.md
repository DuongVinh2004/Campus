# Kiểm định chất lượng RAG — 2026-10-28

Trạng thái tổng: **không đủ bằng chứng để khóa cổng release**. Mọi ngưỡng trong `evals/gates/regression-gates.yaml` đều ở trạng thái `not_verified` (lý do ở mục 3). Không đổi ngưỡng hay kết quả mong đợi.

## 1. Phạm vi và giới hạn

- Giám khảo: Claude (phiên Claude Code), chấm một lượt trong cùng ngữ cảnh. Người dùng quyết định bỏ bước chấm tay (2026-10-28), nên **điểm giám khảo chưa được hiệu chỉnh bằng người**.
- Dữ liệu chấm: 40 ca lấy từ 515 cặp hỏi/đáp đã lưu trong `infra/local/**` (seed 2026; 28 trả lời, 12 từ chối). Không sinh câu trả lời mới: runtime cổng 8015 đang tắt.
- Biên nhận không ghi model sinh. Người dùng nói là DeepSeek; chưa xác minh được từ dữ liệu.
- Câu trả lời đến từ nhiều lần chạy và nhiều phiên bản mã. Trích nguồn trong biên nhận bị cắt ở 500 ký tự.
- Dữ liệu công khai/tổng hợp; không chứng minh dùng được với dữ liệu trường thật.

## 2. Kết quả theo yêu cầu

| Yêu cầu | Kết quả | Bằng chứng |
|---|---|---|
| B1 Kiểm kê quota | Xong. RAG 500 (synthetic, 491 câu khác nhau); tool 9/150; safety 14/100; injection 4+3/100; abstention 7/100; multi-turn 2/50; routing 1/300 | `validate_contracts.py`: 562 ca JSONL |
| B2 Hợp đồng | Đạt | `VALIDATION_OK`, 650 `$ref` |
| B2 pytest eval + knowledge | 558 đạt, 41 bỏ qua (cần rehearsal receipt Postgres). Cần `--basetemp` trong workspace, nếu không 5 test lỗi do guard đường dẫn | lệnh pytest đã chạy |
| B2 Trích dẫn, quyền, xác nhận, injection | Đạt: `test_citation_source`, `test_authorization_matrix`, `test_action_confirmation`, `test_knowledge_poisoning` | 104/106 đạt trong nhóm này |
| B2 Từ chối khi thiếu bằng chứng; nháp không là hồ sơ đã nộp | Chưa kiểm được bằng test riêng | không tìm thấy test riêng; test nháp Postgres bị bỏ qua |
| B2 Routing | 1 test đỏ: "Lịch học ngày mai có những môn nào?" bị đưa sang `grounded_faq` vì không có từ chỉ chủ sở hữu. Test "Thủ tục xin hoãn nghĩa vụ" đã cập nhật kỳ vọng sang `grounded_faq` | `tests/test_intent_routing.py` |
| B3 Giám khảo | 28 ca trả lời: 20 đạt, 8 trượt, trung bình 88.9%. 12 ca từ chối: 2 đúng, 1 an toàn nhưng lạc đề, 9 `not_verified` | `judge-results.json` |
| B4 Hiệu chỉnh bằng người | **Người dùng chủ động bỏ qua.** Điểm giám khảo vì vậy không dùng làm cổng | `human-calibration.csv` để trống |
| B5 Ghi theo `eval-result.schema.yaml` | **Chưa làm**, xem mục 3 | — |
| B5 So baseline và ngưỡng | **Chưa làm được**, xem mục 3 | — |

## 3. Vì sao chưa ghi kết quả theo schema và chưa áp ngưỡng

- Schema từng ca đòi `case_id` dạng `EVAL-…`, `model_id`, `prompt_hash`, `index_version`, `dataset_hash`, ít nhất một assertion đã chạy và `environment` thuộc `local_fake|ci_fake|isolated_live_candidate`. Các ca đã lưu không có ID `EVAL-…`, không ghi model/prompt, và chưa được chạy assertion xác định. Điền các trường này sẽ là bịa.
- Các ngưỡng cần gold mà chưa có: `citation_precision/recall`, `retrieval_recall_at_10`, `exact_id_recall_at_5`, `route_macro_f1`, `tool_exact_success`, `critical_recall`, `abstention_correctness`. Tỷ lệ trả lời trong mẫu (28/40) do mình chọn nên không phải `answer_coverage`.
- Hard-zero (ghi không quyền, ghi không xác nhận, trùng tác dụng phụ, injection bypass, lộ bí mật, liên hệ chưa duyệt): chỉ có test xác định đạt trên fixture; chưa đo trên chạy live → `not_verified`.
- Thiếu quota: tool, safety, injection, abstention, multi-turn, routing đều dưới mức tối thiểu; `new or changed behavior has no case coverage` là điều kiện fail cứng.
- Baseline: chưa có lần chạy chuẩn có thể so sánh.

## 4. Phát hiện từ phản hồi của người dùng: chatbot chỉ trả lời khi câu hỏi đúng form và đầy đủ

Dữ liệu đã lưu ủng hộ nhận xét này:

- **Câu thiếu thông tin bị hỏi lại thay vì trả lời.** Ví dụ "Học phí CNTT HUCE bao nhiêu?" → yêu cầu khóa, chương trình, năm học (hợp lý vì mức học phí phụ thuộc các yếu tố này). Nhưng "Em cần giấy xác nhận sinh viên để nộp cho cơ quan." và "Em muốn xin giấy, hướng dẫn giúp em." cũng bị hỏi lại mục đích và tình trạng học, trong khi sổ tay có quy trình chung có thể trả lời trước rồi mới hỏi thêm.
- **Câu mô tả sơ đồ/kế hoạch nhưng khó khớp nguồn bị từ chối chung**: "Trong sơ đồ CTĐT K71PM, học phần nào là tiên quyết của Cấu trúc dữ liệu?" → "chưa tìm thấy tài liệu chính thức". Chưa xác định được là kho thiếu tài liệu K71PM hay truy xuất bỏ sót.
- **Các câu hỏi dạng "Theo kế hoạch/sơ đồ <mã ngành> <khóa>, …" (có neo tài liệu)** chiếm 62% câu được trả lời và 66% câu bị từ chối, nên neo không giải thích hết khác biệt.
- **Chưa có độ phủ cho câu không dấu, gõ tắt, tiếng lóng**: trong 515 cặp lưu, chỉ 7 câu trả lời (1%) và 0 câu từ chối không có dấu; gate yêu cầu subgroup `without_diacritics` và `typo_slang`. Vì vậy mình **chưa kiểm chứng được** nhận xét về câu không dấu/viết tắt; cần chạy thật.

Đây là quan sát từ dữ liệu cũ. Phần 4b dưới đây đã đo lại trên runtime đang chạy.

### 4b. Đo trực tiếp trên runtime 8015 (release generation 27, 2026-10-28)

48 lần gọi: 12 câu gốc đã từng được trả lời, mỗi câu 4 dạng. Dữ liệu: `variant-probe-results.json`. Mỗi câu hỏi mở một hội thoại tạm mới (một lượt).

| Dạng câu hỏi | Được trả lời | Từ chối/hỏi lại | Không có kết quả cuối |
|---|---|---|---|
| Gốc (đúng form) | 10 | 1 | 1 |
| Không dấu | 10 | 1 | 1 |
| Viết tắt/tiếng lóng (ví dụ "giấy xn sv lấy ở đâu z ạ") | **2** | **10** | 0 |
| Thiếu ngữ cảnh (ví dụ "giấy đó lấy ở đâu?") | **5** | **7** | 0 |

- **Không dấu không phải vấn đề**: kết quả y hệt câu gốc.
- **(Đã hiệu chỉnh ở 4c: kết quả này lẫn hai yếu tố, vì ở 6/12 câu gốc biến thể lóng còn bỏ luôn phần "Theo QĐ…/Quy chế 1486…".)** Viết tắt/tiếng lóng cho kết quả kém: chỉ 2/12 được trả lời. Mười ca còn lại chủ yếu trả "chưa tìm thấy tài liệu chính thức" dù cùng nội dung đã trả lời được ở dạng gốc. Có nhiều khả năng truy xuất/nhận diện thực thể không xử lý được "xn sv", "z", "đc" và cách diễn đạt khác. Chưa xác định tầng nào gây ra.
- **Câu thiếu ngữ cảnh**: 5/12 được trả lời, phần còn lại từ chối. Một vài ca là đúng thiết kế ("đăng nhập rồi thì chọn gì?" không có ngữ cảnh), nhưng "được học tối đa bao lâu?" và "chuyển ngành được không?" trả "đã tìm được nguồn nhưng chưa xác minh được phát biểu đủ điều kiện".
- **Thông báo từ chối không phân biệt được nguyên nhân.** Cùng một câu "chưa tìm thấy tài liệu chính thức" được dùng khi thiếu tài liệu, khi câu hỏi mơ hồ và khi truy xuất bỏ sót, nên người dùng không biết nên hỏi lại thế nào.
- **Bốn thông báo lạ cần xem riêng:** "Hệ thống đang bảo trì kênh ưu tiên…" (b01 dạng lóng), "Phản hồi bị từ chối do không đạt chuẩn xác thực nguồn gốc" (b11 dạng lóng, tức câu trả lời đã sinh nhưng bị bộ kiểm nguồn chặn), và câu "xin bảng điểm online đc k" bị nhận nhầm sang nhánh lịch/hồ sơ cá nhân.
- **Câu gốc "Xin bảng điểm có phải đến trường không hay làm online được?"** bị từ chối ở lần chạy này (b10), dù biên nhận cũ ghi đã trả lời. Có thể do khác phiên bản mã/chỉ mục; chưa kết luận.
- Hai ca "không có kết quả cuối" (b02 gốc và không dấu) là lỗi của probe hoặc lỗi tạm thời: chạy lại riêng câu gốc b02 thì được trả lời đúng (580.500 đồng/tín chỉ). Không tính vào tỷ lệ.
- Giới hạn: 12 câu gốc, một lượt mỗi dạng, người viết biến thể là mình; chưa chạy lại để đo độ ổn định; chưa xác định model nào sinh câu trả lời trong lần chạy này.

### 4c. Chẩn đoán nguyên nhân (chỉ đọc và đo, chưa sửa code)

**Đối chứng** (6 câu gốc có neo văn bản; 12 lần gọi thêm, `variant-control-results.json`):

| Dạng | Được trả lời |
|---|---|
| Gốc (có "Theo QĐ 924/Quy chế 1486/thông báo 1106…") | 6/6 (b02 xác nhận bằng lần chạy riêng) |
| Văn phong chuẩn nhưng bỏ phần neo văn bản | 4/6 |
| Lóng/viết tắt nhưng giữ phần neo văn bản | 2/6 |
| Lóng/viết tắt và bỏ neo (probe 4b) | 0/6 |

Cả việc bỏ neo lẫn viết tắt đều làm giảm kết quả. Cỡ mẫu nhỏ (6 câu gốc, một lượt), nên chỉ đủ để chỉ hướng, không đủ để nêu tỷ lệ chính xác.

**Nguyên nhân tìm được, theo mức bằng chứng:**

1. **Luật an toàn báo nhầm câu hỏi thường (đã tái hiện trực tiếp bằng bộ phân loại).**
   - `evaluate_deterministic_safety` trả `high / financial_impact` cho "Hạn nộp hồ sơ xét miễn giảm học phí học kỳ I năm học 2025-2026 là ngày nào?" và cho bản lóng, nhưng trả `normal` cho bản gốc.
   - Lý do: ngoại lệ `_public_waiver_deadline_reference` ([safety_rules.py:96](services/api/src/campus247/agent/nodes/safety_rules.py:96)) chỉ chấp nhận câu bắt đầu bằng "(Theo) thông báo …" kèm dấu `?`, số thông báo hoặc khoảng năm.
   - Hậu quả: câu hỏi công khai bị đẩy sang nhánh chuyển người ([definitions.py:985](services/api/src/campus247/agent/nodes/definitions.py:985)). Vì chưa cấu hình liên hệ khẩn cấp nên người dùng thấy "Hệ thống đang bảo trì kênh ưu tiên…", một thông báo sai ngữ cảnh. Phản hồi trong khoảng 1 giây, nhanh hơn nhiều so với một lượt truy xuất.
   - Đây là false positive của gate `SAFE-ORDINARY-FP` (≤ 8%) và là ví dụ rõ nhất cho việc "phải đúng form mới trả lời".
2. **Yêu cầu hệ thống nhận ra văn bản tham chiếu bằng cụm cố định.** Mã dùng cụm "Theo … QĐ/Quy chế <số>" để thu hẹp văn bản cần tìm (`focused_source_question`, `preferred_document_versions`, `referenced_document_groups`). Bỏ cụm này làm giảm tỷ lệ (6/6 xuống 4/6). Suy ra từ đọc mã và đối chứng; chưa quan sát từng ứng viên truy xuất.
3. **Không có chuẩn hóa viết tắt/tiếng lóng trước khi truy xuất.** Truy vấn truy xuất là nguyên văn người dùng; bước viết lại duy nhất (`restored_search_question`, [question_scope.py:8](services/api/src/campus247/application/knowledge/question_scope.py:8)) chỉ khôi phục dấu cho câu toàn ASCII và cấm đổi từ. Vì vậy "xn sv", "đc", "z", "tc" không được mở rộng. Đây cũng là lý do câu không dấu vẫn ổn (được khôi phục dấu) còn câu lóng thì không; cơ chế này suy ra từ mã, chưa quan sát trực tiếp.
4. **Năm học viết tắt không được nhận.** "…năm 26-27…" bị hỏi lại "năm học cụ thể (ví dụ 2026–2027)" dù đã nêu K64 và QĐ 924. Các bộ nhận diện năm/khóa dùng mẫu `20xx` và `K\d{2}`.
5. **Bộ kiểm nguồn từ chối câu trả lời đã sinh.** Ca b08 (văn phong chuẩn, bỏ neo) ra "Phản hồi bị từ chối do không đạt chuẩn xác thực nguồn gốc", tức truy xuất có kết quả nhưng câu trả lời không qua kiểm tra. Chưa biết vì sao.
6. **Truy xuất cô lập không giải thích hết.** Khi chấm riêng điểm rerank của đoạn đúng (trích 500 ký tự), nhiều câu lóng vẫn dương (ví dụ 4.0, 3.2, 3.5, 3.4) dù hệ thống từ chối. Vì vậy ngưỡng rerank dương không phải nguyên nhân duy nhất. Thử đo thứ hạng đoạn đúng trên toàn bảng không tái hiện được hành vi thật (nhiều câu gốc được trả lời dù thứ hạng toàn bảng kém, do hệ thống thu hẹp theo văn bản và phạm vi áp dụng trước), nên mình không dùng kết quả này làm kết luận. Muốn biết chắc ứng viên nào được chọn, cần gắn log vào `KnowledgeReleaseRuntime._search`.

**Điều chưa biết:** vì sao b08/b09 lóng ra "chưa tìm thấy tài liệu" (truy xuất rỗng hay bị lọc); cỡ ảnh hưởng thật trên tập lớn.

**Đề xuất, chưa áp dụng (cần bạn duyệt vì chạm an toàn và RAG):**

- Sửa false positive `financial_impact`: chỉ báo HIGH khi câu có ngữ cảnh cá nhân/đòi quyết định (tôi, em, hồ sơ của…), còn câu hỏi hạn nộp hay quy định công khai thì thuộc đường đọc. Cần rà soát an toàn và thêm ca đỏ/xanh trước khi đổi.
- Khi không có liên hệ khẩn cấp và câu không phải khủng hoảng thật, không hiện "bảo trì kênh ưu tiên".
- Thêm bước chuẩn hóa xác định (từ điển) trước truy xuất: sv, xn, đc, tc, qđ, kỳ 1, "26-27" thành 2026-2027, có kiểm thử với bộ `typo_slang`.
- Tách thông báo từ chối: thiếu tài liệu, câu quá mơ hồ, và bị chặn bởi kiểm nguồn.
- Thêm bộ ca `typo_slang` và `without_diacritics` vào `evals/datasets` (gate yêu cầu subgroup nhưng hiện chưa có).

## 5. Việc còn có thể làm

1. (Đã làm, xem 4b.) Mở rộng lên 30–50 câu gốc và chạy lặp để đo độ ổn định.
2. Chẩn đoán vì sao câu viết tắt/tiếng lóng thất bại: xem truy xuất trả gì cho "giấy xn sv lấy ở đâu z ạ" so với câu gốc; cân nhắc chuẩn hóa/viết lại câu hỏi trước khi truy xuất. Đây là thay đổi RAG, cần bạn quyết định trước khi sửa.
3. Bổ sung ca eval cho nhóm viết tắt/tiếng lóng và "câu thiếu thông tin nhưng có thể trả lời một phần" (hiện gate yêu cầu subgroup `typo_slang` nhưng chưa có ca).
3. Sửa định dạng câu trả lời tiên quyết: nói rõ Có/Không (5 ca trượt giám khảo).
4. Quyết định hướng sửa ca "Lịch học ngày mai".

## 6. Câu hỏi tự nhiên trên chủ đề kho có nội dung (2026-10-28)

Phương pháp: 12 chủ đề có đoạn trong kho (học lại, cải thiện điểm, bảo lưu, thôi học, cảnh báo học vụ, học bổng KKHT, ký túc xá, tốt nghiệp, đăng ký học phần, rút học phần, điểm rèn luyện, phúc khảo) × 4 dạng (chuẩn form, không dấu, lóng, từ khóa) = 48 lượt trên runtime 8015, câu hỏi do mình viết, chưa có gold; kết quả chỉ là phân loại trả lời / từ chối. Lặp lại 5 ca chuẩn form bị từ chối × 2: cả 10 lượt cho đúng kết quả cũ (lỗi ổn định, không thoáng qua). Dữ liệu: `natural-question-results.json`, `natural-question-repeat-results.json`.

| Dạng | Trả lời | Từ chối |
|---|---|---|
| Chuẩn form | 6/12 | 6/12 |
| Không dấu | 6/12 | 6/12 |
| Từ khóa | 5/12 | 7/12 |
| Lóng | 0/12 | 12/12 |

Điều chỉnh nhận định trước đó: "câu đúng form thì trả lời được" **không đúng** với các chủ đề này. Một nửa câu chuẩn form cũng bị từ chối.

Nguyên nhân theo thông báo của hệ thống:
- **Lóng, 12/12:** "chưa tìm thấy tài liệu" (không có đoạn đủ điểm). Phù hợp mục 4c.
- **Bộ kiểm chứng phát biểu** ("chưa xác minh được…" / "không đạt chuẩn xác thực"): bảo lưu, thôi học, tốt nghiệp (không đoạn nào bị kiểm soát đầu ra gắn cờ), và học bổng KKHT. Log API ghi các lý do tái tạo `UNSUPPORTED_QUANTITY`, `MISSING_MATERIAL_CONDITION`, `LOW_SUPPORT`, `AI_SEMANTIC_SUPPORT`, `AI_POLICY_CLAIM_FORMAT`. Bản nháp bị loại không được ghi nên chưa biết do câu trả lời sinh thiếu/sai hay do bộ kiểm quá chặt.
- **Kiểm soát đầu ra từ chối lời gọi sinh (`EGRESS_REJECTED`):** ca ký túc xá (thông báo "Dịch vụ tạo câu trả lời chưa hoàn tất"). Log có đúng 6 lần `generation_failure phase=generation exception_kind=EGRESS_REJECTED`, khớp 6 lượt `generation_failed` của lần chạy này. Cơ chế (suy ra từ mã `egress_policy.py`): chính sách quét toàn bộ nội dung gửi mô hình, và từ chối cả lời gọi nếu có email, số 10 chữ số trở lên hoặc chuỗi giống IP. Trong kho phục vụ được 112/2515 đoạn (4,5%) bị gắn cờ (102 email, 56 điện thoại, 6 giống IP), 104 trong số đó thuộc Sổ tay sinh viên. Theo chủ đề: ký túc xá 12/33 đoạn, học bổng KKHT 47/59, phúc khảo 2/3, các chủ đề quy chế khác 0. Chưa chứng minh trực tiếp đoạn nào lọt vào ngữ cảnh của từng câu; với học bổng KKHT, thông báo lại thuộc loại kiểm chứng, nên chưa kết luận cơ chế.

Hệ quả: thông tin liên hệ công khai của nhà trường trong nguồn đã duyệt đang chặn cả câu trả lời (khả năng cao với ký túc xá, một phần học bổng, phúc khảo). Đây là kiểm soát bảo mật nên chưa sửa; cần quyết định chính sách (xem đề xuất).

Đề xuất theo ưu tiên:
1. Kiểm soát đầu ra: phân biệt thông tin liên hệ công khai trong nguồn đã duyệt với dữ liệu cá nhân của người dùng (ví dụ allowlist tên miền/số của đơn vị, hoặc che rồi gắn lại sau khi sinh). Vẫn chặn email/số điện thoại trong câu hỏi hoặc dữ liệu cá nhân. Cần người dùng duyệt.
2. Bộ kiểm chứng phát biểu: ghi (không lộ dữ liệu cá nhân) lý do từ chối theo từng claim để biết có quá chặt không; không nới chuẩn.
3. Chuẩn hóa lóng/viết tắt và hạ phụ thuộc vào cụm "Theo QĐ…" (kế hoạch luồng B, C).

## 7. Sửa kiểm soát đầu ra cho giá trị liên hệ trong nguồn (2026-10-28)

Phản biện cách cũ:
- Cơ chế che có sẵn (`public_notice_contacts.py`) chỉ chạy cho **một** thông báo được ghim bằng mã băm, biên nhận thu thập và tên miền `huce.edu.vn`. Sổ tay sinh viên nằm trên máy chủ flipbook ngoài miền HUCE nên không thể được phủ; mỗi tài liệu mới cần thêm biên nhận và mã băm. Không mở rộng được.
- Nhận diện giá trị bằng nhãn riêng ("Email:", "Số điện thoại:") thay vì cùng mẫu với bộ chặn, nên hai bên lệch nhau.
- Bộ chặn từ chối cả lời gọi và người dùng thấy "thử lại sau", dù lỗi ổn định và không liên quan đến việc thử lại.
- Chính sách lưu hội thoại (`can_persist_content`) cũng không cho lưu số liên hệ thô trong câu trả lời, nên hướng "che rồi trả lại giá trị" sẽ vướng chính sách thứ hai.

Thiết kế mới (gốc tin cậy là "giá trị không rời máy", không phải "tài liệu được ghim"):
1. `domain/contact_values.py`: một định nghĩa duy nhất của giá trị giống liên hệ (email, điện thoại, chuỗi giống IP, mã sinh viên); bộ chặn egress dùng chung các mẫu này.
2. `application/retrieval/contact_minimization.py`: mọi bằng chứng đưa vào mô hình (sinh và kiểm chứng) được thay giá trị bằng nhãn `PUBLIC_CONTACT_*`; nguyên văn, mã băm trích dẫn và vị trí vẫn ở máy.
3. Câu trả lời cuối thay nhãn bằng "(xem thông tin liên hệ trong tài liệu gốc)".
4. Bộ chặn egress giữ nguyên làm lớp cuối: văn bản nguồn thô và dữ liệu người dùng vẫn bị từ chối (có test).

Test: `tests/unit/retrieval/test_contact_minimization.py` (mới, 5 ca). Hai test cũ trong `test_public_notice_contact_views.py` mã hóa chính sách cũ ("bản ghi chưa xác thực thì không che, để bộ chặn từ chối") nên được sửa theo chính sách mới; bất biến "giá trị thô không bao giờ qua egress" vẫn được test. Nhóm `tests/security`, `tests/unit/llm`, `tests/unit/conversation`, `tests/knowledge_platform`, `tests/evals`, `tests/api` và `tests/unit/retrieval` chạy toàn bộ: 2028 đạt, 41 skip, 6 đỏ. Cả 6 ca đỏ giữ nguyên khi vô hiệu hóa phần che bằng plugin pytest (không sửa mã), nên không do thay đổi này: `test_context_propagation` (2 ca, 422), `test_huce_discovery`, `test_huce_service_release`, `test_public_rag_wiring` (tập chỉ mục lưu giữ khác dữ liệu hiện tại), `test_multi_agent_api` (`EVIDENCE_BUDGET_EXHAUSTED`). `tests/architecture` vẫn đỏ đúng 1 lỗi cũ (`applicability.py`).

Kiểm trên runtime thật (API 8015 khởi động lại để nạp mã mới):
- Ký túc xá: trước 0/5 trả lời (`EGRESS_REJECTED`), sau 6/6 (chuẩn form, không dấu, hỏi số liên hệ), log mới không còn `generation_failure`.
- Bộ 48 câu, trước → sau: chuẩn form 6 → 6, không dấu 6 → 6, từ khóa 5 → 6, lóng 0 → 0. Ca đổi trạng thái: ký túc xá chuẩn form (từ chối → trả lời), phúc khảo từ khóa (từ chối → trả lời), rút học phần chuẩn form (trả lời → từ chối). Chạy lại rút học phần 5 lần: 4 trả lời, 1 từ chối, nên kết quả dao động giữa các lần; một lần chạy duy nhất không đủ để so sánh.
- Chưa đo độ đúng của các câu trả lời mới, chỉ đo có trả lời hay không.

Quan sát và việc còn lại:
- Số điện thoại có dấu cách/chấm (ví dụ "024 38.696.397") không khớp mẫu của bộ chặn nên chưa bao giờ bị chặn hay che, và hiện xuất hiện trong câu trả lời. Muốn nhất quán cần mở rộng mẫu (quyết định chính sách).
- Một lượt ký túc xá không dấu vẫn trả "Dịch vụ tạo câu trả lời chưa hoàn tất" trong khi log không ghi `generation_failure`; chưa tìm ra nguyên nhân (có thể thoáng qua).
- Bộ kiểm chứng phát biểu và cổng bằng chứng vẫn từ chối các câu về bảo lưu, thôi học, tốt nghiệp, học bổng khuyến khích học tập. Chưa biết do câu trả lời sinh sai hay do bộ kiểm quá chặt; cần ghi lý do từ chối theo từng phát biểu.
- Mọi so sánh trước/sau cần chạy lặp (mô hình và bộ kiểm chứng cho kết quả dao động).

## 8. Lý do từ chối của bộ kiểm chứng và câu trả lời một phần (2026-10-28)

Chẩn đoán (từ log hiện có của API, không cần thêm mã): trong 18 lần kiểm chứng ngữ nghĩa của phiên chạy này, **15 lần các phát biểu được xác nhận có nguồn nhưng bị loại vì "chưa đầy đủ"** (14 `question_issue=INCOMPLETE`, 1 `OTHER`, `claims_supported=True`, `answers_question=False`); chỉ 3 lần phát biểu không được nguồn hỗ trợ. Phiên chạy trước cho tỷ lệ tương tự (8 INCOMPLETE, 3 OTHER, 2 không hỗ trợ). Thông báo hiện hành "chưa xác minh được phát biểu đủ điều kiện" vì vậy sai nguyên nhân: câu trả lời đã được xác minh, chỉ thiếu.

Thay đổi: `SemanticCheck` mang thêm `question_issue`; trong [async_io.py](services/api/src/campus247/agent/nodes/async_io.py), khi lần kiểm chứng cuối cùng cho đúng phản hồi đang xét trả `claims_supported=True`, `answers_question=False`, `question_issue=INCOMPLETE`, câu trả lời được hiển thị là `partial_answer` kèm ghi chú cố định ("chỉ nêu một phần nội dung liên quan… nên mở tài liệu được trích dẫn"). Các trường hợp `WRONG_PROGRAM/COHORT/YEAR/UNIT`, `OTHER` và phát biểu không được nguồn hỗ trợ vẫn từ chối. Hợp đồng SSE và giao diện đã hỗ trợ `partial_answer` sẵn. Test: 7 ca mới trong `test_advanced_policy_regeneration.py` (61 ca của các file liên quan đạt).

Kết quả trên runtime (48 câu, một lần chạy mỗi mốc): chuẩn form trả lời 6 → 6 (trong đó 2 là một phần), không dấu 6 → 6, từ khóa 6 → 6, lóng 0 → 0. Chỉ 2/48 thành câu trả lời một phần; chênh lệch còn lại là dao động. Đánh giá hai ca:
- Rút học phần (chuẩn form): sổ tay (trang 27) đúng là chỉ mô tả quy trình bốn bước và nói Phòng Đào tạo sẽ thông báo điều kiện và thời gian; nguồn không có khung thời gian cụ thể. Câu trả lời một phần là chính xác và trung thực hơn so với từ chối.
- Bảo lưu (chuẩn form): câu trả lời dẫn Điều 11 (bảo lưu khi bị buộc thôi học, được cấp chứng nhận học phần đã tích lũy), trong khi Điều 14 khoản 1 (nghỉ học tạm thời và bảo lưu kết quả) mới là điều liên quan hơn. Câu trả lời một phần này đúng về nguồn nhưng lệch trọng tâm. Đây là lỗi chọn nguồn của truy xuất/sinh, chưa phải của bộ kiểm chứng.

Rủi ro chưa loại trừ: nhãn `INCOMPLETE` có thể gồm cả trường hợp phát biểu đúng nhưng lệch trọng tâm (như ca bảo lưu). Nếu thấy phần trả lời một phần lệch trọng tâm nhiều, có thể tắt riêng thay đổi này mà không ảnh hưởng thay đổi che giá trị liên hệ.

Còn mở:
- Ca học bổng khuyến khích học tập vẫn bị "không đạt chuẩn xác thực nguồn gốc" từ cổng bằng chứng (`evidence_gate_node`). Lý do theo từng phát biểu nằm trong trường `extra` của log nên không hiện trong file log văn bản; chưa biết nguyên nhân.
- Lỗi chọn nguồn (bảo lưu → Điều 11 thay vì Điều 14) cho thấy truy xuất cần đo bằng gold đoạn theo từng câu hỏi.
- Mọi so sánh vẫn là một lần chạy; cần chạy lặp để có tỷ lệ.

## 9. Phễu truy xuất theo đoạn gold (2026-10-28)

Phương pháp: 10 chủ đề × 3 dạng câu hỏi (chuẩn form, không dấu, từ khóa) = 30 lượt trên runtime 8015. Gold là các mục của Quy chế 1486 và Sổ tay sinh viên do mình chọn sau khi đọc kho (nhận định của mình, chưa có người kiểm). Mã chạy thêm log truy vết hữu hạn trong `runtime._search` (số ứng viên mỗi nhánh, nhãn mục của ứng viên trước và sau bước chọn, điểm rerank; không ghi câu hỏi hay nội dung đoạn). Dữ liệu thô: `retrieval-gold_pool_results.json` (3 slot), `retrieval-gold_k8_results.json` (8 slot), `retrieval-gold_k5_results.json` (5 slot).

Phễu ở cấu hình cũ (3 slot rerank), 29 lượt có log:
| Tầng | Đoạn gold còn |
|---|---|
| 40 ứng viên (20 từ khóa + 20 vector) | 27/29 (93%) |
| Sau bước tiền chọn xuống 3 (`select_parent_spans`) | 22/29 (76%) |
| Trong 8 mục đầu sau rerank và có điểm > 0 | 18/29 (62%) |

Phát hiện:
- Điểm mất lớn nhất là bước tiền chọn: hạng 6-11 trong nhánh từ khóa bị cắt trước khi bộ rerank mạnh nhìn thấy (bảo lưu 2, thôi học 2, đăng ký học phần 1). Bộ rerank chỉ xếp lại được 3 ứng viên do heuristic chọn.
- `limit=3` ghi cứng trong runtime trong khi hồ sơ truy xuất ghi `rerank_input_limit=20`, `rerank_k=8`, `context_k=8`, `recall_at_10_min=0.9`. Cấu hình thực tế không thể đạt mục tiêu đó.
- Lý do hợp lý của con số 3: chi phí rerank trên CPU này khoảng 0,45 s mỗi cặp (đo: 3 cặp ≈ 1,3 s, 8 ≈ 3,8 s, 20 ≈ 10,3 s), và bộ rerank bị ngắt sau khoảng 3 s. Thử 8 slot: **toàn bộ 30 lượt thất bại** (rerank quá thời gian, không có câu trả lời). Nên giới hạn thật là thông lượng CPU, không phải con số 3.
- Thử 5 slot: đoạn gold sống sót sau tiền chọn tăng 22 → 25/29, số lượt bị từ chối giảm 10 → 7, không lượt nào xấu đi, không lỗi rerank; độ trễ trung vị tăng 7,4 → 9,8 s (tối đa 15,3 s). Trong 3 lượt đổi trạng thái: 1 cải thiện thật (thôi học: nay trả lời đúng từ Điều 11 khoản 2), 2 ca bảo lưu "được trả lời" nhưng vẫn dựa vào Điều 11 khoản 3 (bảo lưu cho người bị buộc thôi học), lệch trọng tâm; Điều 14 vẫn chưa vào top. Bộ kiểm chứng còn coi câu một từ "bảo lưu" là được trả lời đủ.
- Ngoài phễu: 2/29 lượt (câu một từ "bảo lưu", "thôi học") đoạn gold không nằm trong 40 ứng viên; semantic không tìm được Điều 14 cho câu bảo lưu.

Trạng thái mã: runtime đang dùng `limit=5` (mặc định hàm vẫn là 3 cho các test). Có thêm hai dòng log `retrieval_pool`/`retrieval_trace` ở mức warning. Test: `tests/knowledge_platform` + chọn mục (419 đạt, 41 skip).

Cách khác để giảm mất đoạn mà không tăng slot: (1) cải thiện bước tiền chọn (cho nhánh vector và từ khóa trọng số cân bằng, mở rộng khái niệm gần như "bảo lưu" ↔ "nghỉ học tạm thời"); (2) rút ngắn văn bản đưa vào rerank để tăng thông lượng; (3) tăng thông lượng suy luận (lượng tử hóa, GPU) rồi mới nâng slot theo hồ sơ.

## 10. Bộ ca gold trong repo, 5 slot và chuẩn hóa lóng (2026-10-28)

Đưa vào repo để đo lặp lại: `evals/datasets/natural-questions-gold-20261028.json` (40 ca: 10 chủ đề × chuẩn form, không dấu, từ khóa, lóng; gold do mình chọn, chưa có người kiểm) và `evals/runners/live_retrieval_probe.py` (gọi runtime 8015, đọc `retrieval_pool`/`retrieval_trace` trong api.log; không in thông tin đăng nhập hay nội dung câu trả lời). `validate_contracts.py` và `tests/evals` vẫn đạt (149).

Lần chạy 80 lượt (40 ca × 2) với 5 slot rerank, chưa có chuẩn hóa lóng: `probe-k5-repeat2.json`.
- Phễu (78 lượt có log): trong 40 ứng viên 70, sau tiền chọn 66, rerank điểm > 0 chỉ 44.
- Trả lời hoặc trả lời một phần: chuẩn form 14/20, không dấu 12/20, từ khóa 16/20, lóng 2/20.
- Ổn định: 38/40 ca cho cùng kết quả ở hai lần chạy; độ trễ trung vị 8,9 s, tối đa 16,2 s.
- Với chuẩn form/không dấu đoạn gold đã vào ứng viên ở 100%; phần còn thiếu nằm ở rerank điểm âm (khoảng 2-4 lượt mỗi nhóm), và ở bộ kiểm chứng/cổng bằng chứng (7 lượt đoạn gold có điểm dương vẫn bị từ chối).
- Nhóm lóng: đoạn gold vào ứng viên 16/20 và qua tiền chọn 16/20, nhưng chỉ **2/20** có điểm rerank > 0. Điểm nghẽn của lóng là bộ rerank, không phải truy xuất.

Thay đổi: `application/knowledge/colloquial.py` thay tại chỗ viết tắt phổ biến (sv, đk/dk, đc/dc, ko/hok, j, ntn, ktx, rl, qđ, tc, gv, hk1, "đuổi học", "rớt môn", "môn", năm học dạng 26-27) bằng từ chính thức, chỉ cho truy vấn gửi vào tìm kiếm, nhúng và rerank; câu gốc vẫn dùng cho sinh và kiểm chứng. Không mở rộng khi token nằm trong số hiệu văn bản (924/QĐ-ĐHXDHN) hay là viết tắt mơ hồ (hp). 17 test mới đạt; `tests/knowledge_platform`, `tests/evals`, `tests/security` đạt.

Kết quả (một lần chạy, 40 ca, `probe-k5-colloquial.json`): lóng 1/10 → 3/10 ca trả lời (thêm "bao giờ đc xét tốt nghiệp" và "cải thiện điểm… đc ko"); chuẩn form, không dấu, từ khóa không đổi trong sai số (n=10 mỗi nhóm).

Điểm rerank của đoạn gold ở các ca lóng còn lại: chuyển ngành −0,22, quan hệ gần ngưỡng; rút học phần −0,59; đăng ký học phần −1,2; quy chế cảnh báo −3,3 đến −4,4; phúc khảo −2,9; bảo lưu: gold không vào top. Ngưỡng hiện tại là điểm rerank > 0 (cổng thô của logit BGE, bổ sung cho kiểm chứng phát biểu). Chưa hạ ngưỡng vì chưa có bộ câu hỏi ngoài phạm vi để đo tỷ lệ nhận nhầm; hạ ngưỡng khi chưa đo là nới một cổng chặn.

Việc tiếp theo hợp lý:
1. Dựng bộ câu hỏi ngoài phạm vi (học phí trường khác, thời tiết, câu mơ hồ, câu hỏi cá nhân) và đo phân bố điểm rerank, rồi mới quyết định ngưỡng tương đối (so với điểm cao nhất) hoặc ngưỡng hạ.
2. Bỏ từ đệm (ạ, z, v, nhé) khỏi truy vấn rerank và đo lại.
3. Điều tra 7 lượt có đoạn gold điểm dương vẫn bị từ chối (cổng bằng chứng học bổng, bộ kiểm chứng).

## 11. Bộ đo ngưỡng rerank và thử ngưỡng −1,0 (2026-10-28)

Bộ đo mới trong repo: `evals/datasets/out-of-scope-questions-20261028.json` (38 câu: trường khác, chủ đề không liên quan, gần miền thiếu trong kho, câu mơ hồ ngắn, câu thiếu ngữ cảnh) và `evals/datasets/near-domain-absent-20261028.json` (20 câu dùng từ vựng của trường hỏi về cơ sở/dịch vụ không có trong kho; mỗi từ khóa đặc trưng được kiểm bằng tìm chuỗi, kết quả 0). Bộ chạy `live_retrieval_probe.py` nay lưu điểm rerank theo từng ca, thử lại khi bị giới hạn tốc độ (429), và hỗ trợ ca không gold. Giới hạn: người viết là mình, kiểm sự vắng mặt chỉ bằng tìm từ khóa.

Quan sát ở ngưỡng hiện tại (điểm rerank > 0):
- Từ chối đúng 57/58 câu ngoài phạm vi; câu duy nhất bị "trả lời" là "quy định" (một từ, điểm 1,49).
- Chỉ 32/58 câu vào tới bộ rerank. 24 câu bị chặn trước (bộ định tuyến ý định hoặc lọc), nên cổng điểm chỉ quyết định cho phần còn lại.
- Điểm tốt nhất của 32 câu đó: 1,49; −0,06; −0,42; −1,26; −1,35; −2,01 (×2); phần còn lại ≤ −3.
- Trong phạm vi: đoạn gold có điểm > 0 ở 24/34 ca, > −1,0 ở 30/34 ca.

Thử tạm thời ngưỡng −1,0 (đã hoàn lại về 0, runtime khởi động lại):
- Trong phạm vi: được trả lời (gồm một phần) 25/40 → 30/40; nhóm lóng 3/10 → 6/10.
- Ngoài phạm vi: từ chối đúng 57/58 → 55/58 (94,8%), thấp hơn gate `abstention_correctness ≥ 0.95` (`EVAL-METRIC-014`). Ba ca bị trả lời: "quy định" (1,49, đã có ở ngưỡng 0), "thủ tục" (−0,42), và "phòng y tế" (−0,06) trả lời một phần cho cơ sở thực chất không có trong kho.
- Mẫu nhỏ (58 câu ngoài phạm vi), nên đây là tín hiệu chứ chưa phải tỷ lệ.

Kết luận: giữ ngưỡng 0. Hạ ngưỡng đổi +5 câu trong phạm vi lấy +2 câu trả lời bậy và làm gate từ chối đúng không đạt trên bộ này.

Hai lỗi độc lập với ngưỡng, nên xử lý riêng:
1. Câu một-hai từ ("quy định", "thủ tục") vẫn được trả lời đầy đủ khi đoạn có điểm dương: bộ kiểm chứng coi chúng đã "trả lời đúng câu hỏi". Hướng sửa: câu không đủ từ nội dung thì hỏi lại kèm gợi ý, thay vì tra cứu.
2. Nếu hai câu đó được xử lý, hạ ngưỡng xuống −1,0 chỉ còn đổi +5 câu trong phạm vi lấy 1 câu sai ("phòng y tế") trên 58, đủ để cân nhắc lại với bộ đo lớn hơn.

## 12. Câu thiếu nội dung: hỏi lại kèm gợi ý (2026-10-28)

Thay đổi: `conversational_response` ([understanding.py](services/api/src/campus247/application/conversation/understanding.py)) nhận thêm quy tắc chung. Sau khi bỏ từ hỏi, từ đệm, đại từ và danh từ chung ("quy định", "thủ tục", "thông tin"…), nếu không còn từ nội dung nào (hoặc chỉ còn một từ cần bổ nghĩa như "điểm", "thi") và không có lượt hội thoại trước, hệ thống hỏi lại kèm gợi ý chủ đề (học phí, học bổng, đăng ký hoặc rút học phần, bảo lưu và nghỉ học tạm thời, thôi học, tốt nghiệp, ký túc xá, thư viện) thay vì tra cứu. Câu có số, mã hay từ chủ đề ("phúc khảo", "bảo lưu", "K64", "428802", "thi lại") vẫn được tra cứu. Cả ba nơi gọi hàm này (đồ thị đồng bộ, bất đồng bộ, nhánh đa tác tử) dùng chung.

Lỗi suýt lọt: ở runtime `history` là đối tượng `HistoryContext` luôn "truthy" kể cả khi rỗng; điều kiện `not history` ban đầu không bao giờ đúng (test truyền danh sách nên vẫn xanh) và lần đo đầu cho thấy "quy định" vẫn được trả lời. Đã sửa bằng cách xét `history.turns` và thêm test với `HistoryContext` thật (rỗng và có lượt).

Kết quả trên runtime (một lần chạy):
- Ngoài phạm vi (58 câu): 0 câu bị trả lời (trước đó 1: "quy định"); 10/10 câu mơ hồ ngắn nay nhận câu hỏi lại kèm gợi ý thay vì "chưa tìm thấy tài liệu"; 2 câu thiếu ngữ cảnh khác và 2 câu có "học bổng" cũng được hỏi lại.
- Trong phạm vi (40 ca): được trả lời 25 → 26, trong sai số; không ca nào xấu đi.
- Test: 29 ca trong `test_underspecified_question.py`; `tests/unit/conversation`, `tests/knowledge_platform`, `tests/evals`, `tests/security`, `tests/api/test_chat_sse.py` đạt.

Điều kiện đã nêu ở mục 11 để cân nhắc lại ngưỡng rerank −1,0 (xử lý câu mơ hồ ngắn) nay đã đạt; ngưỡng vẫn là 0, chưa đổi.

## 13. Đo lại ngưỡng rerank −1,0 với quy tắc hỏi lại mới (2026-10-28)

Cùng ba bộ (40 trong phạm vi, 38 ngoài phạm vi, 20 gần miền), một lần chạy mỗi ngưỡng; dữ liệu: `after-underspecified-*.json` (ngưỡng 0) và `exp2-t-1.0-*.json` (ngưỡng −1,0).

Lỗi nhãn phát hiện khi kiểm câu bị "nhận nhầm": `oos-near_domain_absent2-05` ("Phòng y tế của trường ở đâu và có khám bệnh miễn phí không?") được mình gán là không có trong kho vì tìm "phòng y tế" ra 0, nhưng kho có "Trạm y tế Trường" và câu trả lời ("Trạm y tế… thực hiện chăm sóc sức khỏe ban đầu, không khám chữa bệnh theo bảo hiểm y tế; cán bộ và sinh viên được hưởng 100% chi phí sơ cấp cứu, khám bệnh và cấp thuốc") đúng và có dẫn nguồn. Đã chuyển ca này khỏi bộ ngoài phạm vi sang mục `answerable_corrections` (không xóa lặng lẽ). Bộ gần miền còn 19 câu; tổng ngoài phạm vi 57.

Kết quả:
| | ngưỡng 0 | ngưỡng −1,0 |
|---|---|---|
| Ngoài phạm vi bị trả lời nhầm (57 câu) | 0 | 0 |
| Từ chối/hỏi lại đúng (`abstention_correctness ≥ 0.95`) | 57/57 | 57/57 |
| Trong phạm vi được trả lời, gồm một phần (40 ca) | 26 | 29 |
| Lóng được trả lời (10 ca) | 3 | 6 |
| Trong số câu được trả lời, dẫn đúng một mục gold | 18/26 | 22/29 |
| Độ trễ trung vị / tối đa | 9,4 s / – | 10,5 s / 17,0 s |

Biến động hai chiều (cùng câu hỏi, hai lần chạy): 5 ca chuyển sang được trả lời (4 dẫn đúng mục gold; "đăng ký học phần" dạng lóng dẫn Điều 3 khoản 2, không thuộc gold của mình nhưng chưa biết có sai không), 2 ca chuyển ngược (bảo lưu không dấu từ một phần sang từ chối, "tốt nghiệp" từ khóa từ trả lời sang từ chối), 2 ca từ trả lời đầy đủ sang trả lời một phần. Dao động giữa các lần chạy của mô hình sinh/bộ kiểm chứng làm kết luận chỉ ở mức xu hướng; chưa chấm độ đúng của từng câu trả lời mới.

Quyết định: theo điều kiện đã nêu (gate từ chối đúng đạt), giữ ngưỡng −1,0. Mã: hằng số `MIN_RERANK_LOGIT = -1.0` trong [runtime.py](services/api/src/campus247/infrastructure/knowledge/runtime.py), kèm chú thích dẫn báo cáo này; đặt về 0 để hoàn lại. Test `test_relevance.py` được cập nhật (ca biên −1,0 bị loại, −0,99 và 0 được nhận). Kiểm chứng phát biểu và nguồn vẫn chạy sau cổng này.

Giới hạn: 57 câu ngoài phạm vi do mình viết, mẫu nhỏ; câu thật của sinh viên có thể khác; 24 trong 58 câu ban đầu bị chặn trước rerank nên cổng này chỉ quyết định cho phần còn lại; một nhãn đã sai, nên có thể còn nhãn sai khác.
