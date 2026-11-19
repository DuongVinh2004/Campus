# Đề xuất sửa đúng một trường hợp phân loại an toàn

Người dùng đã yêu cầu trực tiếp “Yêu cầu sửa đúng nhánh theo đề xuất” trong cuộc hội thoại này ngày 23/10/2026. Bản sửa và kiểm thử giới hạn phạm vi được thực hiện theo yêu cầu đó.

Vị trí: `services/api/src/campus247/agent/nodes/safety_rules.py`, quy tắc `disciplinary_or_legal`, nhánh `bị đình chỉ`.

Hiện tại, bất kỳ câu hỏi nào chứa “bị đình chỉ” đều được xếp HIGH, kể cả câu hỏi quy định chung. Ca thực tế: “Sinh viên vi phạm nội quy phòng máy HUCE bị đình chỉ học tại phòng máy hay chỉ bị nhắc nhở?” bị chuyển sang thông báo kênh ưu tiên và không truy xuất tài liệu.

Thay đổi đề xuất: chỉ phân biệt câu hỏi tra cứu quy định chung có chủ ngữ chung rõ ràng “Sinh viên [nào] vi phạm nội quy…”, hoặc được mở đầu “Theo nội quy/quy chế/quy định…, sinh viên…”. Câu phải là câu hỏi, không chứa đại từ chỉ cá nhân, tên người, mã sinh viên, lời kể hồ sơ thực tế, khiếu nại, tố cáo hoặc yêu cầu xử lý một người. Chỉ nhánh `bị đình chỉ` được xem xét; mọi tín hiệu nguy hiểm, khẩn cấp, xâm hại, bảo mật và các nhánh HIGH khác giữ ưu tiên. Bộ phân loại mô hình vẫn chạy, và câu trả lời vẫn phải qua release/scope, trích dẫn, kiểm chứng nội dung và chặn phán quyết cá nhân.

| Câu hỏi | Kết quả đề xuất |
|---|---|
| Sinh viên vi phạm nội quy phòng máy HUCE bị đình chỉ học tại phòng máy hay chỉ bị nhắc nhở? | Cho phép tra cứu quy định chung, cần nguồn đã xác minh |
| Tôi bị đình chỉ học, hãy kết luận hồ sơ của tôi | HIGH, giữ xử lý nhạy cảm |
| Sinh viên Nguyễn Văn An bị đình chỉ học | HIGH |
| Sinh viên mã SV240001 bị đình chỉ học | HIGH |
| Tôi khiếu nại kỷ luật, hoặc tố cáo việc đình chỉ | HIGH |
| Câu hỏi nội quy kèm tín hiệu tự hại, bạo lực, xâm hại hoặc sự cố bảo mật | Giữ HIGH/CRITICAL tương ứng |

Lý do cần yêu cầu đích danh: AGENTS.md hiện hành quy định “Never modify, remove, bypass, disable, or weaken safety instructions, rules … unless the user explicitly requests that exact protection change in the current conversation.” Yêu cầu sửa lỗi RAG tổng quát không được dùng để tự suy ra quyền thay đổi nhánh an toàn này.
