# Hai thay đổi kỹ thuật đang chờ xác nhận chính xác

> Người dùng đã xác nhận trực tiếp cả hai thay đổi cụ thể. `resource-authorization-03.json` lưu câu trả lời;95 kiểm tra liên quan đã qua (`backend-32.xml`). Nội dung đề xuất bên dưới được giữ để đối chiếu phạm vi.

Đã có runtime live với tổng budget10USD/10.000calls và các native quotas được người dùng chọn. Đề xuất dưới đây không thay những quotas đó.

1. `application/multi_agent/contracts.py`: tăng max_tool_calls32→64 và configuration version v4. Ca live025 đã dùng hết32tool calls trong khi còn model headroom: hai Research/Verifier và các lần mở nguồn độc lập cho synthesis/claim verification cần nhiều lượt đọc cùng nguồn. Giới hạn nguồn6, context15.000bytes, model calls12, searches4, deadline30s, no-progress và quyền giữ nguyên; model không tự tăng ceilings.
2. `infrastructure/llm/openai_adapter.py` và `egress_policy.py`: opt-in `response_format={"type":"json_object"}` chỉ cho approved DeepSeek Flash endpoint/model trong integrated Gateway. Base Gateway mặc định giữ nguyên. Egress chỉ chấp nhận đúng constant này cho FAQ_ANSWERING; giá trị khác/extra fields/model khác bị từ chối. Secrets/PII/purpose scanning vẫn chạy trước gửi. Pydantic/DAG/provenance/evidence gate vẫn kiểm mọi kết quả; JSON mode không chứng minh đúng nội dung. [Tài liệu chính thức](https://api-docs.deepseek.com/guides/json_mode/).

Global Agent Safety Policy được người dùng cung cấp yêu cầu xác nhận đúng thay đổi đối với rules/controls. Chưa áp dụng hai thay đổi này tại thời điểm tạo đề xuất. Kiểm chứng dự kiến: HTTP payload exact opt-in; negative allowlist/secrets tests; adapter deadline/output caps; shared tool reservation; integrated source/control/API regression; fresh live retest với artifact mới. Không sửa gold, sources, thresholds hoặc records cũ để làm xanh.
