# Mẫu brief cho worker

Brief càng chặt, worker càng ít sai và càng ít phải giao lại. Viết 5–15 dòng, tiếng Việt hoặc tiếng Anh đều được.

```
MỤC TIÊU: <một câu, kết quả cụ thể>
FILE ĐƯỢC GHI: <đúng các path trong --allow; ghi "tạo mới" nếu là file mới>
GIỮ NGUYÊN: <props/exports/data-testid/hành vi không được đổi>
YÊU CẦU:
- <yêu cầu 1, đo được>
- <yêu cầu 2>
KHÔNG LÀM: <phạm vi bị loại trừ: không thêm dependency, không đổi logic gọi API, ...>
NGHIỆM THU: <Claude sẽ kiểm gì: tsc sạch, test X pass, có data-testid Y, hiển thị ở 375px>
```

## Mẹo

- Đưa vào `--context` một file mẫu cùng loại (component hoặc test gần giống) để worker bắt chước style.
- Nêu tên hàm, prop, endpoint có thật. Worker được dặn không bịa, nhưng có tên sẵn thì nhanh hơn.
- Sửa file có sẵn thì dùng `--mode edit`. Gửi cả file trong `--context` để worker chép SEARCH cho đúng; file rất dài thì gửi kèm `path:START-END` quanh vùng cần sửa.
- Việc lớn thì chia thành nhiều job theo file và chạy fan-out. Không giao một job sửa 10 file.
- Khi giao lại sau lần bị chặn: dán nguyên văn dòng BLOCK hoặc lỗi tsc vào brief mới, kèm "sửa đúng lỗi này, không đổi gì khác".
