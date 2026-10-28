---
name: campus247
description: Quy ước, kiến trúc, lệnh chạy và quy tắc an toàn AI của repo Campus 24/7 (chatbot RAG học vụ HUCE, web Next.js + API FastAPI/LangGraph). Dùng mỗi khi sửa hoặc thêm code web/API/AI/eval, chạy runtime 8015, kiểm thử, hoặc đụng dữ liệu local, tài khoản, backup, evidence trong repo này.
---

# Campus 24/7

Repo gồm web (`apps/web`, Next.js 16, React 19, Tailwind 4), API (`services/api/src/campus247`, FastAPI + LangGraph + Postgres/pgvector + Redis), eval (`evals/`, `packages/evals`), hợp đồng (`contracts/`). Ngôn ngữ giao diện và dữ liệu là tiếng Việt (`vi-VN`).

Skill này thay thế mọi quy trình cũ (governance, task catalog, DEC-023): các tài liệu đó chỉ là tư liệu tham khảo, không phải cổng phê duyệt.

## Làm việc

1. Chạy `git status --short` trước khi sửa. Không ghi đè việc đang dở của người dùng.
2. Đọc code liên quan rồi làm thay đổi nhỏ, đúng phạm vi yêu cầu.
3. Chọn mức kiểm tra theo loại thay đổi (xem [references/verification.md](references/verification.md)); chỉ chạy thứ liên quan, không chạy cả bộ để cho chắc.
4. Báo cáo ngắn, trung thực: đã làm gì, bằng chứng, phần chưa kiểm hoặc chưa xong. Kết quả `not_verified` không được kể là thành công.

### Làm đến cùng

- Bám đúng mục tiêu người dùng giao. Không tự thu hẹp "hoàn tất kế hoạch" thành "xong một gói", "chạy được" hay "test đạt"; đó chỉ là mốc trung gian.
- Không dừng chỉ vì vừa đạt một mốc tốt hay đã tốn nhiều công. Không chờ nhắc "tiếp tục", không thay hành động bằng kế hoạch hay lời xin lỗi.
- Một mục bị chặn (thiếu đầu vào, cần đối chiếu độc lập) chỉ chặn phần phụ thuộc trực tiếp vào nó; vẫn làm các phần độc lập.
- Chỉ dừng khi có trở ngại đã kiểm chứng (thiếu thông tin hoặc quyền, ranh giới an toàn, giới hạn công cụ). Nêu mục bị chặn, bằng chứng, phần còn làm được, đầu vào tối thiểu cần bổ sung.
- Trước khi báo xong, đối chiếu từng kết quả được yêu cầu với bằng chứng. Phân biệt rõ: đã xong, người dùng chủ động hoãn, thật sự bị chặn.
- Hỏi tiến độ giữa chừng thì trả lời ngắn rồi làm tiếp, trừ khi người dùng bảo dừng hay đổi mục tiêu. "Làm đến cùng" không phải quyền xóa dữ liệu hay bỏ bảo vệ.

## Quy tắc cứng

Mục tiêu là an toàn vừa đủ, không rườm rà:

- **Bí mật:** không in khóa, token, mật khẩu ra chat/log/commit. Được dùng tài khoản test local để đăng nhập kiểm thử, nhưng không đổi, xóa hay tạo lại tài khoản admin/`student-local` và khóa.
- **Dữ liệu:** không xóa hoặc ghi đè build cũ, backup, evidence, dữ liệu trong DB local (cổng 5433). Test migration và test phá hủy dùng DB tạm. Việc xóa cần được người dùng nói rõ.
- **Git:** `git status` trước khi sửa. Commit/push/deploy chỉ khi người dùng yêu cầu. Không `reset --hard`, `clean -fd`, ghi lại lịch sử khi chưa được bảo.
- **Chi phí:** không gọi API trả phí hay production nếu chưa được cho phép; test mặc định dùng fake provider.
- **Trung thực với dữ liệu:** chưa có kết nối HUCE thật (SSO, bảng điểm, lịch cá nhân, tiếp nhận hồ sơ, đặt phòng). Không dùng fixture thay dữ liệu trường rồi nói như thật.
- **Bảo vệ ứng dụng:** không nới xác thực, phân quyền, xác nhận hành động hay kiểm nguồn chỉ để test qua.

## Chạy

Runtime chính thức duy nhất là **cổng 8015** (frontend 3015 là nội bộ). Chi tiết lệnh: [references/verification.md](references/verification.md). Các runtime cũ (3115, kho tri thức riêng, 8017/8018, 3018) là lịch sử, không hướng dẫn chạy.

## Đọc tiếp khi cần

- Kiến trúc, ranh giới lớp, quy ước web: [references/architecture.md](references/architecture.md)
- RAG, trích dẫn, từ chối, prompt injection, hành động ghi: [references/rag-and-ai-safety.md](references/rag-and-ai-safety.md)
- Lệnh chạy và bảng kiểm tra theo loại thay đổi: [references/verification.md](references/verification.md)
