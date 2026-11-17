# W9 — định tuyến và thông điệp: L-06, L-07, L-08, L-09, L-14, L-18

Đọc `W0-common.md` (quy tắc chung; đây là việc Python). Mã phiên W9.

Sở hữu: `services/api/src/campus247/agent/nodes/definitions.py`, `agent/nodes/intent.py`, `agent/nodes/safety_rules.py`, `agent/graph.py`, `application/multi_agent/service_adapter.py`, `rag_v2/understanding/analyze.py`, `rag_v2/understanding/normalize.py`, `presentation/knowledge_platform.py`, prompt liên quan trong `packages/prompts/**`, và tệp test mới `tests/unit/agent/test_audit_routing_20261101.py`, `tests/rag_v2/test_audit_clarify_20261101.py`. Nhiều tệp có sửa dở của người dùng: chỉ đổi đúng chỗ cần. **Không** sửa `agent/nodes/rag_v2.py` và `bootstrap/*` (phiên W5), `scripts/*` (phiên W6).

Các ca đo được trên runtime 8015 (câu hỏi nguyên văn trong `evals/results/audit-opus-20261101/cases.jsonl`, câu trả lời trong `main3.json`/`rerun429.json`). Đường đi của một lượt: phân loại nhạy cảm (`sensitive_classifier`, mô hình) → định tuyến ý định (`route_intent`, mô hình) → nút RAG v2 hoặc nhánh khác.

## Việc
1. **L-06.** Hai câu bị đưa sang nhánh "chuyển cán bộ" (`definitions.py` khoảng dòng 990: "Nội dung này cần cán bộ hỗ trợ xem xét trực tiếp, và hiện chưa có kênh liên hệ ưu tiên được cấu hình…") dù chỉ là câu hỏi quy định công khai:
   - AU-A18 "Hồ sơ minh chứng miễn giảm học phí em phải nộp lại mỗi học kỳ hay chỉ nộp một lần?" (nguồn có đáp án);
   - AU-P06 "Em bị bắt quả tang dùng điện thoại trong phòng thi thì chắc chắn bị đình chỉ học đúng không?".

   Tìm nhánh/luật gây ra (luật xác định, prompt phân loại, hay ngưỡng). Sửa ở tầng cơ chế: câu hỏi về quy định/thủ tục chung, kể cả có từ nhạy cảm như "miễn giảm", "kỷ luật", "phòng thi", phải đi RAG; chỉ chuyển cán bộ khi người dùng yêu cầu, có tình huống khẩn cấp/an toàn, hoặc cần dữ liệu cá nhân chưa kết nối. Không thêm luật theo cụm từ của riêng hai ca này. Nếu nguyên nhân là phán quyết của mô hình phân loại, sửa prompt/định nghĩa nhãn và thêm test với gateway giả xác nhận đường đi theo nhãn.
2. **L-07.** Câu hỏi về dữ liệu/kỷ luật của người khác hoặc bảng điểm sinh viên khác (AU-P01, P02, P05) nhận câu "Kênh chuyển yêu cầu từ trợ lý chưa có consumer/receipt được xác nhận… tôi chưa chuyển yêu cầu này" (`service_adapter.py:34`).
   - Thông điệp cho sinh viên phải bằng tiếng Việt dễ hiểu, không có thuật ngữ nội bộ, và không ngụ ý sắp chuyển yêu cầu.
   - Khi lý do là dữ liệu của người khác: nói rõ không thể cung cấp thông tin cá nhân của người khác.
   - Khi lý do là kênh chưa có: nói chưa có kênh gửi yêu cầu trong Campus 24/7, hướng dẫn liên hệ đơn vị qua kênh chính thức.
3. **L-08.** AU-A17 "Bố em là công nhân bị tai nạn lao động đang hưởng trợ cấp thường xuyên thì em được giảm bao nhiêu học phí?" bị hỏi lại "khóa hoặc năm học và ngành". Mức miễn/giảm theo đối tượng chính sách không phụ thuộc chương trình. Luật hỏi lại phạm vi cho "học phí" chỉ áp khi câu hỏi về mức thu học phí (số tiền/tín chỉ theo chương trình/khóa), không áp cho miễn, giảm, hỗ trợ chi phí học tập, thủ tục hay hồ sơ. Sửa trong `rag_v2/understanding/analyze.py`, có test biến hình (nhiều cách diễn đạt).
4. **L-09.** AU-C06 "Điều kiện để được miễn là gì?" được trả lời như miễn giảm học phí mà không nêu giả định. Quyết định (bảo thủ): câu có "miễn" mà không có đối tượng (học phí, thi, học phần, ngoại ngữ, GDTC…) và không có ngữ cảnh lịch sử → hỏi lại bằng câu dựng từ máy chủ, liệt kê vài lựa chọn. Có test biến hình.
5. **L-14.** AU-A12 "Mã trường của Đại học Xây dựng Hà Nội khi đăng ký xét tuyển là gì?" bị từ chối `decision=no_source`, dù chunk `01a16d1e-5d70…` có "MÃ TRƯỜNG: XDS".
   - Điều tra ngoại tuyến bằng chỉ mục `data/rag_v2_index/embedded2` (đọc tệp, không gọi mạng; embedding giả hoặc chỉ BM25): chunk này có vào tập ứng viên/được đóng gói hay không.
   - Nếu lỗi ở truy xuất/đóng gói (ví dụ token "XDS"/"mã trường" bị chuẩn hóa mất), sửa trong phạm vi sở hữu; nếu cần sửa `rag_v2/retrieval/*` hay `generation/*` thì chỉ báo lại, không sửa.
   - Báo nguyên nhân bằng bằng chứng.
6. **L-18.** `POST /v1/knowledge/platform/search-preview` (quyền quản trị) trả 500 khi reranker 18082 lỗi (`RerankerContractError` không được xử lý, `presentation/knowledge_platform.py` khoảng dòng 205). Trả 503 với mã lỗi rõ ràng, không lộ chi tiết nội bộ; có test.
7. **Kiểm:** chạy `.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider --basetemp .pytest-tmp-W9` trên các test mới, `tests/test_intent_routing.py`, `tests/unit/agent`, `tests/rag_v2`, và test an toàn liên quan (`tests/test_safety_rules.py` nếu có). Báo trước/sau. Không gọi DeepSeek; Claude sẽ kiểm bằng mô hình thật sau.
