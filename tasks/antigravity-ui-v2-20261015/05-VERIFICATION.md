# Đợt 05 — Kiểm tra tích hợp và hoàn thiện

Áp dụng MASTER. Đích: mọi route có trải nghiệm nhất quán và các vấn đề mới do redesign được sửa bằng bằng chứng.

## 1. Rà scope và môi trường
Kiểm Git status/diff, so với snapshot và manifest trước tác vụ. Không revert thay đổi của người khác hoặc “làm sạch” repo.
Xác định source apps/web, URL, flags không bí mật, process/build đang kiểm. Không dùng ảnh candidate cũ trong infra/local làm bằng chứng bản mới.
Không thay source/runtime đang phục vụ production; chỉ chạy local đã xác định.

## 2. Kiểm kỹ thuật
Từ apps/web:
- node node_modules/typescript/bin/tsc --noEmit --incremental false
- node node_modules/vitest/vitest.mjs run --reporter=dot --maxWorkers=2 --minWorkers=1
- Production build bằng script build hiện có, chỉ sau khi kiểm output/cache target không ghi đè work đang phục vụ. Nếu cần output riêng, dùng cấu hình Next được phiên bản cài hỗ trợ và target mới trong workspace; không xóa .next cũ.
Lưu log trong thư mục evidence mới đã canonical-check, không đè evidence cũ. Sửa regression trong scope; phân biệt lỗi source/test môi trường/pre-existing có evidence. Không bật ignoreBuildErrors, skip, nới threshold hoặc xóa test để có màu xanh.
Test lỗi text/layout cũ có thể cập nhật đúng UX mới, nhưng security/privacy/confirmation/API assertions phải giữ.
Chỉ rerun affected checks sau sửa, rồi một lần kết thúc khi có thay đổi liên quan.

## 3. Kiểm trình duyệt thật
Các route: /, /login, /chat, /tickets, /services, /schedule, /rooms, /staff, /knowledge, /knowledge/sources, /knowledge/policy-graph, /admin, /privacy, /memory, /notifications.
Kiểm nhánh reachable đang serve; variants chưa thể chạy phải ghi lý do. Chọn viewport 390, 768, 1024, 1440px; reflow 320 CSS px, light/dark.
- Không scroll ngang toàn trang; bảng/code scroll trong container.
- Không chữ bị cắt, button/link giả, controls tràn, vùng click chồng nhau, nested main hoặc heading hierarchy sai.
- Menu/dialog: focus trap, Escape, focus return, backdrop; skip link tới nội dung. Theme control và đăng nhập không bị menu che.
- Form: lỗi theo trường, draft giữ khi lỗi, preview và explicit confirm; mutation chỉ trên fixture được xác định.
- Chat: composer, IME, streaming stop, lịch sử, sources; nội dung dài.
- Staff/admin: nav role đúng, không lộ thông tin nội bộ, không làm quyền chỉ bằng ẩn nút.
- Loading/error/empty/unavailable phải có layout hoàn chỉnh, không che lỗi bằng success giả.
Kiểm contrast text thường >=4.5:1, text lớn >=3:1, UI/focus có tương phản phù hợp; automated scan không thay keyboard/manual review.

## 4. Vòng chỉnh cuối
Xem trực tiếp ảnh thật của trang chủ, chat, form, staff và mobile. Ghi tối đa 10 lỗi cụ thể, sửa theo mức tác động. Không làm lại hướng thiết kế đã chốt hoặc tạo biến thể mới.
Nếu còn blocker ngoài UI, hoàn thành mọi phần độc lập và báo exact blocker; không gọi toàn bộ sản phẩm hoàn tất.

## Đầu ra
Báo cáo theo REPORT-TEMPLATE.md, kèm:
- Ma trận route: implementation/variant, viewport/theme đã kiểm, trạng thái PASS/FAIL/NOT_VERIFIED.
- Các lệnh, exit code và log path; tổng test thật.
- Khoảng 6 ảnh đại diện đã tự xem, không screenshot còn loading trừ khi minh họa loading.
- Danh sách giới hạn có căn cứ; chưa usability test với người thật thì ghi rõ.
- Diff chỉ những thay đổi nhiệm vụ này; các dữ liệu/dirty state khác được giữ.
Không tự chấm “UX/UI 10 điểm”. Hoàn thành nghĩa là đã kiểm những gì nêu và không còn regression do redesign chưa xử lý, không có nghĩa đã chứng minh mọi tiêu chí sản phẩm.
