# HUCE — khôi phục runtime và kiểm chứng toàn tuyến ngày 24/10/2026

## Kết quả

**VERIFIED_LOCAL_HUCE_RELEASE** trong phạm vi release ba tài liệu đã đối chiếu.
PostgreSQL, API, frontend và worker đã chạy lại. Không còn tái hiện lỗi chặn
`postgres.exe` trong phiên này. Đã dùng nguyên executable và cluster cũ, qua
`pg_ctl start` bình thường; không thay executable, sửa Device Guard hoặc đổi
chính sách Windows. Chưa xác định nguyên nhân môi trường khiến lần trước bị
chặn; việc khởi động thành công không chứng minh chính sách máy đã thay đổi.

PostgreSQL tự recovery WAL và báo sẵn sàng. Database vẫn là
`campus247_knowledge_local_20261023`, cổng 55437, schema 0017. Không chạy
bootstrap, migration, reset hoặc chuyển sang bản sao database.

## Đường mở và khởi động lại

- Chat: <http://127.0.0.1:8015/chat>.
- Đăng nhập quản trị: <http://127.0.0.1:8015/login>.
- Tài khoản chủ hệ thống đã có giữ tại
  `infra/local/knowledge-platform-20261023/owner-credentials.json`; không ghi
  mật khẩu hoặc token vào báo cáo.
- Frontend v11 chạy ở 3015; người dùng đi qua proxy cùng origin ở 8015.
- BGE embedding/reranker giữ ở 18081/18082 với đúng revision và kế toán kế thừa.

Từ repository root trên Windows:

```powershell
& 'infra/local/rag-fixture/.venv/Scripts/python.exe' -B scripts/knowledge_platform_runtime.py start
& 'infra/local/rag-fixture/.venv/Scripts/python.exe' -B scripts/knowledge_platform_runtime.py status
```

Launcher mới kiểm database/schema, model/revision, frontend, desired/serving
release và ack còn hạn. Nó tái sử dụng các tiến trình được nhận diện, hoặc mở
thành phần còn thiếu trong nền với log và receipt mới. Không tự tắt tiến trình,
đổi cổng, khởi tạo DB, thay model hoặc thay đổi chính sách bảo vệ. Hai dịch vụ
model phải đang sẵn sàng; launcher báo lỗi nếu thiếu hoặc sai danh tính.

Hai lần chạy `start` khi hệ thống đã sẵn sàng đều báo `ready=true`,
`started={}` và giữ nguyên PID hiện hữu. Danh sách PID Python có cả venv
redirector và interpreter con, không phải hai worker xử lý độc lập.
Các nhánh process matching/failure được kiểm bằng unit tests; chưa chủ động
dừng từng dịch vụ để thử mọi thứ tự khởi động, cũng chưa kiểm sau reboot máy.

## Kiểm chứng thực tế

| Kiểm tra | Kết quả |
|---|---|
| Bộ 17 câu chính qua API thật | 17/17 đạt nội dung, điều kiện và citation |
| 17 biến thể: không dấu, follow-up, sai giá/đơn vị, hồ sơ cá nhân và injection | 17/17 đạt kỳ vọng |
| Bốn cặp đồng thời, gồm ba cặp học phí khó | 8/8 trả lời đúng, không timeout trong đợt này |
| Auth/citation/session/Origin | 14 kiểm tra đạt |
| Lỗi embedding, reranker và nội dung nguồn bị thay trong bộ nhớ audit | 3 kiểm tra đạt; từ chối an toàn, không đổi dịch vụ hoặc dữ liệu nguồn |
| Trình duyệt Chrome thật | Đăng nhập, thư viện nguồn, gửi chat, đọc lại kết quả đã lưu, mở đoạn nguồn gốc đều đạt |
| Mobile 390px | Không tràn ngang ở trang chat đã kiểm; chưa phải audit accessibility đầy đủ |
| Launcher mới | 7/7 unit tests đạt; Ruff đạt trên hai file mới |
| Bảo toàn mã và bằng chứng trước phiên | Toàn bộ 33 hash trong manifest trước vẫn khớp |

Đã kiểm lại original/rendition/metadata, acquisition receipt, ảnh scan và 49
đoạn có locator của hai tài liệu PDF; tất cả khớp. Release vẫn là
`01a168c6-dce3-7b72-bcbd-b5797b9452b8`, generation 12, policy generation 3;
catalog vẫn 117 nguồn, 126 phiên bản, 122 phiên bản chờ duyệt. Không duyệt hoặc
kích hoạt hàng loạt để giảm số chờ. Không đổi nội dung trả lời hoặc điều kiện
kiểm chứng để làm bộ kiểm đạt.

Các câu được trả lời đều có source readback HTTP 200, anonymous 401 và hash
đúng release/version. Những câu ngoài phạm vi hoặc yêu cầu phán quyết cá nhân
được từ chối; câu học phí thiếu điều kiện được hỏi làm rõ. Lượt chính có hai
phản hồi rate limit và harness đợi theo Retry-After; không bỏ rate limit.
Các lượt đồng thời quan sát thời gian toàn tuyến khoảng 6,27–11,21 giây.
Giới hạn 5.000 ms chỉ áp dụng pha sinh/xác minh, không phải toàn bộ truy xuất
và HTTP. Giữ nguyên giới hạn pha, token envelope và kiểm chứng ngữ nghĩa.

Hai lần browser harness đầu chưa đạt: lần đầu tìm sai tên heading; lần hai
đọc body SSE bằng DevTools sau khi UI đã nhận final và hủy reader. Ảnh và log
thất bại vẫn được giữ. Lần ba dùng readback kết quả đã lưu như E2E hiện hữu,
đồng thời kiểm câu trả lời hiển thị và mở nguồn thực tế. Báo cáo giữ cả các
request bị abort; không có pageerror trong lần đạt. Browser profiles chứa
phiên đăng nhập được giữ local và bị loại khỏi Git bằng ignore riêng.

## Bằng chứng và phạm vi còn lại

Báo cáo máy: `infra/local/blocker-resolution-20261024-01/final-verification-01.json`.
Script đánh giá: `infra/local/blocker-resolution-20261024-01/verify-results.py`.
Trong đó có verdict từng ca và hash từng receipt. Bộ hồi quy 274 ca trong
báo cáo trước được giữ nguyên; phiên này không chạy lại bộ đó vì mã ứng dụng
không đổi, và không cộng 7 test launcher thành coverage ứng dụng mới.

Namespace này giữ ảnh desktop/mobile, báo cáo browser, test XML, log khởi động
và receipt; các báo cáo audit mới nằm trong
`infra/local/knowledge-platform-20261023/independent-*-20261024*.json`.
Không xóa dữ liệu, reset kế toán, sửa protection, commit, push hoặc deploy.

Chưa thể coi toàn project hoặc production đã hoàn tất: chỉ ba tài liệu đang
phục vụ được xác minh, không phải toàn catalog; chưa có SSO/API học vụ, dữ liệu
cá nhân hay pilot người dùng thật. Những tích hợp này cần hệ thống và thông tin
thật của đơn vị, không thể thay bằng hồ sơ giả hoặc tắt xác thực. Tám lượt đồng
thời đạt không chứng minh đã loại trừ mọi timeout về sau hoặc đạt SLO tải dài.
