# Duyệt output của worker theo mức rủi ro

Guard đã lo phần cơ học (đường dẫn, lệnh nguy hiểm, bí mật, file bị cắt cụt). Claude chỉ dành quota cho phần guard không thấy được: đúng ý, đúng logic, không phá hành vi.

| Mức | Ví dụ | Claude làm |
|---|---|---|
| Thấp | Chữ UI, style/class, file test mới, docstring, file mới độc lập | Đọc dòng `files` trong tóm tắt, NOTES và cảnh báo; liếc diff qua `--path` nếu > 80 dòng; rồi `apply` và chạy tsc/test |
| Vừa | Sửa component đang dùng (thêm state, props, handler), sửa test có sẵn | Đọc toàn bộ diff của file đó; kiểm tra props, exports, `data-testid` và luồng sự kiện còn nguyên; rồi `apply`, tsc, vitest, trình duyệt nếu có thay đổi hiển thị |
| Cao | Bất cứ thứ gì đụng gọi API, quyền, dữ liệu hay xác nhận hành động | Không giao. Nếu worker lỡ chạm tới thì bỏ output đó và Claude tự làm |

## Dấu hiệu bỏ output

Gặp một trong những dấu hiệu sau thì bỏ output, `revert` nếu đã áp dụng, rồi giao lại một lần hoặc Claude tự làm:

- Import, hàm hay prop không tồn tại (tsc sẽ báo).
- Đổi hành vi không được yêu cầu: gỡ handler, đổi điều kiện, đổi thứ tự gọi.
- Xóa test, làm test dễ hơn, hoặc `skip`/`only`.
- Chữ UI không phải tiếng Việt, hoặc có lỗi dấu.
- NOTES nói "chưa chắc" ở đúng chỗ là logic.

## Báo cáo cho người dùng

Ghi rõ phần nào do worker làm, phần nào Claude làm, và bằng chứng kiểm tra (tsc, test, ảnh chụp). Kết quả guard hoặc test pass không thay được việc kiểm tra theo yêu cầu gốc.
