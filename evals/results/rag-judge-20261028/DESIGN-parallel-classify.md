# Thiết kế (CHƯA BẬT): chạy song song phân loại an toàn và định tuyến — A8

Hiện tại `graph.py:175-190`: normalize_input → pre_safety_rules → sensitive_classifier (1 lời gọi mô hình) → merge_safety → route_intent (1 lời gọi mô hình) → rẽ nhánh (grounded_faq → rag_v2 hoặc retrieve…). Hai lời gọi tuần tự ≈ 4 s, là phần lớn khoảng cách giữa dịch vụ v2 (trung vị ~3,3 s) và đầu–cuối (~9 s).

## Đề xuất
Một nút `classify_parallel` chạy `asyncio.gather(sensitive_classifier, route_intent)` trên cùng đầu vào đã chuẩn hóa, rồi `merge_safety` như cũ. Ràng buộc để không đổi hành vi an toàn:
1. Kết quả `route_intent` chỉ được dùng nếu `merge_safety` không chặn/không yêu cầu handover; nếu chặn thì bỏ kết quả định tuyến (không ghi vào state, không log nội dung).
2. `pre_safety_rules` (xác định, không gọi mô hình) vẫn chạy trước và vẫn có thể chặn sớm: khi nó chặn, không khởi chạy lời gọi nào (không tốn thêm, không rò nội dung ra nhà cung cấp).
3. Lỗi/quá hạn của một nhánh không được làm thay đổi kết luận nhánh kia: lỗi `sensitive_classifier` giữ nguyên hành vi hiện tại (fail-closed như `merge_safety` đang làm); lỗi `route_intent` giữ nguyên fallback hiện tại.
4. Ngân sách ngân sách/đếm lời gọi (`agent/budget.py`) và egress policy tính cả hai lời gọi như hiện nay.
5. Một nhà cung cấp chịu 2 lời gọi đồng thời: cần kiểm giới hạn tốc độ; vẫn tổng số lời gọi không đổi.

## Test phải viết trước khi bật (chưa viết — chờ nhà cung cấp để đo)
- ca bị chặn bởi `pre_safety_rules` → 0 lời gọi mô hình;
- ca `sensitive_classifier` = chặn, `route_intent` = grounded_faq → kết quả cuối vẫn chặn, không có nội dung định tuyến trong state;
- ca `route_intent` lỗi → hành vi bằng hiện tại; ca `sensitive_classifier` lỗi → fail-closed như hiện tại;
- bộ safety 610 ca chạy v1 và v2 trước/sau: không ca nào đổi nhãn an toàn; rò canary 0.
Chi phí kỳ vọng: giảm ~min(t_safety, t_route) ≈ 2 s mỗi lượt (đưa trung vị ~9 s xuống ~7 s; A8 ≤6 s vẫn cần thêm).
Không bật trong lần hoàn tất này vì nó đụng đường an toàn và không thể đo/kiểm chứng khi nhà cung cấp sinh không truy cập được.
