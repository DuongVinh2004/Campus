# Mẫu báo cáo Antigravity → chat chỉ đạo

Báo cáo tối đa khoảng 450 từ, không chép toàn log hoặc suy luận dài. Viết đủ để người review không phải đoán. Chỉ dùng số đo/ảnh thực.

ĐỢT: 01 / 02 / 03 / 04 / 05
TRẠNG THÁI: READY_FOR_REVIEW / NEEDS_FIX / BLOCKED

ĐÃ THAY:
- 3–6 bullet, nêu file → thay đổi → tác dụng cho người dùng.

SOURCE/RUNTIME:
- Workspace/source, URL và mode/flags công khai liên quan.
- Có chạy đúng code vừa sửa không; variant chưa chạy ghi rõ.

KIỂM TRA:
| Lệnh hoặc thao tác | PASS/FAIL/NOT_VERIFIED | Exit code / evidence path |
| --- | --- | --- |
| ... | ... | ... |

ẢNH THẬT:
- Desktop:
- Mobile:
- Dark:
- State/flow quan trọng:
Ghi URL/viewport và local path; đã tự mở xem ảnh trước khi báo.

REGRESSION VÀ GIỚI HẠN:
- Lỗi mới còn lại:
- Lỗi tồn tại/môi trường và bằng chứng đối chiếu:
- Chưa kiểm:
- Không ghi “không có” nếu chưa kiểm.

TIẾP THEO:
- Một đoạn ngắn: phần nào sẵn sàng review, phần nào cần thông tin hoặc sửa.

Nếu đợt 04/05: đính kèm ma trận route ở tệp riêng; báo cáo chỉ link tệp.
Không gửi token, credential, dữ liệu cá nhân hay full environment.

## Prompt sửa sau review — mẫu cho người chỉ đạo
Tiếp tục đúng đợt [N] theo MASTER. Chỉ sửa các finding dưới đây:
1. [file/component]: [lỗi quan sát] → [hành vi đích] → [cách xác minh].
2. ...
Giữ thiết kế đã chốt và các phần đã pass. Không thêm feature hoặc thay backend.
Chạy kiểm tra ảnh hưởng, mở browser xác minh lại đúng lỗi; trả báo cáo và ảnh cập nhật. Không rerun toàn bộ suite nếu thay đổi không cần.
