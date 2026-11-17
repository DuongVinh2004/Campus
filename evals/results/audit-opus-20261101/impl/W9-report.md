W9 — báo cáo thực hiện

1. Đã sửa và nguyên nhân

- L-06: hai luật từ khóa `miễn giảm học phí` và `bị đình chỉ` đẩy câu hỏi quy định lên mức cao trước RAG. Đã phân biệt tra cứu quy định/thủ tục với xử lý hồ sơ riêng, bổ sung định nghĩa nhãn trong prompt; giữ ưu tiên khủng hoảng và nhãn an toàn cao.
- L-07: thay thông điệp kỹ thuật bằng từ chối rõ dữ liệu người khác, hoặc thông báo Campus 24/7 chưa có kênh gửi yêu cầu và hướng dẫn liên hệ chính thức. Kiểm cả nhánh tuần tự/song song và guard đầu ra.
- L-08: câu hỏi mức miễn/giảm, hỗ trợ và hồ sơ không còn bị hỏi khóa/ngành như mức thu học phí.
- L-09: “miễn” thiếu đối tượng và thiếu ngữ cảnh phù hợp nhận câu hỏi lại cố định từ máy chủ; có phân biệt “thi” với “thì”.
- L-18: bắt lỗi hợp đồng/timeout của reranker, trả 503 `KNOWLEDGE_SEARCH_UNAVAILABLE`, không đưa chi tiết nội bộ vào phản hồi; giữ kiểm quyền trước lời gọi tìm kiếm.
- Sửa lỗi định tuyến nền đã tái hiện: lịch cá nhân có thời điểm/danh sách môn không bị dấu hỏi đẩy sang RAG; yêu cầu gặp cán bộ rõ ràng được giữ đúng ý định.

2. Tệp và test

Tệp sản phẩm đã đổi (tiền tố `services/api/src/campus247/`): `agent/nodes/definitions.py`, `agent/nodes/intent.py`, `agent/nodes/safety_rules.py`, `application/multi_agent/service_adapter.py`, `rag_v2/understanding/analyze.py`, `presentation/knowledge_platform.py`.

Thêm [test_audit_routing_20261101.py](<C:/Users/Duong Vinh/Vinh/tests/unit/agent/test_audit_routing_20261101.py>) và [test_audit_clarify_20261101.py](<C:/Users/Duong Vinh/Vinh/tests/rag_v2/test_audit_clarify_20261101.py>): 110 ca, gồm biến hình, gateway giả, toàn luồng và HTTP ASGI.
Các test chính:

- `test_public_questions_reach_rag_after_normal_classifier`
- `test_public_questions_reach_v2_in_sequential_and_parallel_graphs`
- `test_privacy_refusal_is_independent_of_model_route`
- `test_privacy_message_survives_complete_graph`
- `test_benefit_amount_does_not_require_tuition_rate_scope`
- `test_unspecified_exemption_returns_server_clarification_without_model`
- `test_school_code_offline_bm25_reaches_packed_parent_context`
- `test_search_preview_reranker_unavailable_is_safe_503`

3. Lệnh và kết quả trước/sau

- Test mới ban đầu: 17 đạt / 36 đỏ trên mã cũ. Những ca bổ sung cũng được chạy đỏ trước các sửa tương ứng; các ca bảo vệ kiểm hành vi cần giữ.
- `.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider tests/unit/agent/test_audit_routing_20261101.py tests/rag_v2/test_audit_clarify_20261101.py --tb=short`: cuối cùng **110 đạt / 0 đỏ**.
- Bộ nền trước sửa: 753 đạt, 1 đỏ ở câu “Lịch học ngày mai có những môn nào?”, 53 lỗi setup do tôi chọn thư mục tạm con khi thư mục cha chưa tồn tại.
- `.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider --basetemp .pytest-tmp-W9/final-latest tests/test_intent_routing.py tests/unit/agent tests/rag_v2 tests/test_safety_rules.py --tb=short`: **925 đạt / 0 đỏ**, 2 cảnh báo cache nhúng cũ. Bộ rộng chạy trước tinh chỉnh nhận diện hồ sơ cuối; tinh chỉnh này được kiểm riêng bằng 110 ca W9 ở trên.
- Kiểm bổ sung `tests/knowledge_platform/test_public_financial_deadlines.py tests/knowledge_platform/test_public_rule_safety_scope.py`: **31 đạt / 5 đỏ**, chi tiết phối hợp ở mục 5.
- Từ `apps/web`, `npx.cmd --no-install vitest run src/features/chat` (npm offline): **132 đạt / 3 đỏ**; đúng 2 ca `ChatPanel.test.tsx` và 1 ca `history.test.ts` đã nêu trong L-17. W9 không sửa web.
- `npx.cmd --no-install tsc --noEmit --incremental false`: đạt, mã thoát 0; không ghi lại tsbuildinfo. `git diff --check`: đạt.

4. Thiết kế và bằng chứng

Phân biệt mục đích tra cứu với dữ liệu/hành động cá nhân; không dùng riêng cụm từ của AU-A18/AU-P06 làm ngoại lệ. Nhãn an toàn cao của bộ phân loại vẫn thắng định tuyến. Không nới xác thực, quyền, guard đầu ra hay kiểm nguồn.
Bằng chứng là ca tổng hợp dùng JSON phân loại và lỗi reranker đúng hợp đồng, kiểm đường đi bằng mã, cùng đoạn gold kiểm trực tiếp trên chỉ mục và nguồn đã xuất. Mức dùng được với người dùng thật chưa đo.

5. Cần phối hợp / rủi ro

- L-14 đã điều tra ngoại tuyến trên `data/rag_v2_index/embedded2` (9.173 đơn vị): đơn vị `7ff59bb14e67f51f`, chứa chunk `01a16d1e-5d70-7dd9-9dd7-5d8ba801f70a` và hai chunk gold còn lại, có BM25 hạng 9 trong 12 ứng viên. Đóng gói với dòng nguồn cha vẫn chứa “MÃ TRƯỜNG: XDS” (8 nguồn, 12.502 byte). Test `school_code` tái hiện được kiểm này.
- Chưa xác định nguyên nhân `no_source` của lượt runtime AU-A12: bằng chứng BM25 loại trừ mất từ/mã ở chuẩn hóa, nhưng không tái hiện thứ hạng vector và quyết định mô hình thật. Cần trace ứng viên/ngữ cảnh của lượt thật để phân biệt truy xuất hybrid với bước sinh; không sửa `retrieval/*` hoặc `generation/*` ngoài sở hữu.
- 5 ca đỏ bổ sung thuộc hai nhóm `test_individual_cases_extensions_and_unbounded_notices_stay_protected` và `test_unprefixed_individual_extension_money_or_unbounded_stay_high` trong `test_public_financial_deadlines.py`: kỳ vọng `high` chỉ vì câu hỏi thời hạn miễn giảm dùng em/tôi hoặc thiếu số thông báo. Cần đồng bộ kỳ vọng với W9; tôi giữ nguyên tệp ngoài sở hữu.
- Chưa kiểm lại bằng mô hình thật theo phân công trong brief. Không gọi mạng/DeepSeek, không build hoặc khởi động 8015; không commit, xóa hay sửa tệp ngoài sở hữu.

Báo cáo lưu tại [W9-report.md](<C:/Users/Duong Vinh/Vinh/evals/results/audit-opus-20261101/impl/W9-report.md>).
