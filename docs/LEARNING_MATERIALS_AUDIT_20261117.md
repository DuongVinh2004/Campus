# Kiểm định luồng giảng viên đăng tài liệu và sinh viên xem

Ngày 17/11/2026 · dữ liệu tổng hợp, bản diễn tập biệt lập, runtime 8015 không chạy và không bị đụng tới.

## Lỗi tìm thấy và đã sửa

| Lỗi | Hậu quả | Sửa | Bằng chứng |
|---|---|---|---|
| Khi tab nhận focus, kiểm tra phiên làm effect kiểm tra phiên bản bị dọn dẹp và hủy yêu cầu vừa gửi; khi phiên về `ready` không có yêu cầu bù. | Sinh viên đang đọc bản cũ không thấy banner "đã có bản hiện hành mới"; đang đọc bản bị thu hồi không bị đưa ra cho tới khi tải lại. | `LearningWorkspace.tsx`: nhớ yêu cầu bị cắt ngang và chạy lại khi effect dựng lại. | Tái hiện bằng trình duyệt (banner không xuất hiện sau 10 s dù API trả đúng bản hiện hành). Test `LearningWorkspace.session.test.tsx` thất bại khi bỏ bản sửa, đạt khi có. |
| Tải bản gốc luôn đặt tên `lecture.pdf`. | Sinh viên tải nhiều tài liệu nhận cùng một tên. | `presentation/learning.py`: tên theo tiêu đề tài liệu, `filename*` UTF-8 và bản ASCII dự phòng, lọc ký tự nguy hiểm. | `test_material_lifecycle_audit.py`. |
| Trang `/learning` lồng hai thẻ `<main>`. | Hai landmark chính, không hợp lệ cho trình đọc màn hình. | Thẻ trong của workspace đổi thành `div`. | `tsc` và vitest. |
| Form tải lên hiện dung lượng bằng byte thô. | Khó đọc. | Hiện KB/MB và mức tối đa. | Vitest form tải lên. |

| Kiểm tra tài khoản định kỳ 30 giây ẩn nội dung rồi hiện lại. | Khi sinh viên đang gõ bài nộp, focus nhảy khỏi ô nhập và các ký tự gõ tiếp bị mất ("tiếp tục gõ" thành "ếp tục gõ"); hộp thoại báo vướng bị giật focus về tiêu đề. | `learning-session.tsx`: chu kỳ định kỳ kiểm tra âm thầm khi tài khoản còn `ready`; focus, blur và visibility vẫn ẩn trước. Đổi tài khoản hoặc hết phiên vẫn ẩn nội dung. | Tái hiện bằng Chrome (34 giây gõ liên tục). Test hook thất bại với hành vi cũ, đạt với bản sửa; Chrome sau sửa giữ focus và đủ ký tự. |
| Nhãn "Bản N" của bản chữ hỗ trợ đánh số theo vị trí trong danh sách. | Cùng một bản bị đổi số khi có bản nháp mới. | `AccessibleTextReview.tsx`: đánh số theo thứ tự id (tăng theo thời gian). | Test `AccessibleTextReview.test.tsx`; Chrome. |
| Hộp thoại xem trước mở báo vướng hiện nhãn "Thông tin" và chuỗi ISO thô. | Khó đọc, lệch múi giờ lớp. | `LearningWorkspace.tsx`: nhãn "Giờ chốt"/"Giờ công bố", giờ theo múi giờ của lớp. | Chrome ("Giờ chốt 2026-11-17 16:44 (Asia/Bangkok)"). |

## Tính năng còn lại: kết quả

Chạy bằng `apps/web/e2e/learning-features.mjs` trên bản diễn tập biệt lập (`scripts/learning_features_rehearsal.py`), 8/8 đạt, không có lỗi trang: phiếu ra lớp (tạo, công bố, nộp, nộp lại, đóng, rà bài, công bố lời giải), báo vướng theo trang (bàn phím, lưu, trả focus), lời giải chung theo buổi, thẻ ý tưởng (nguồn theo trang, chia sẻ bản chụp, rút chia sẻ), bản chữ hỗ trợ (yêu cầu, duyệt, đối chiếu khối rủi ro, công bố một trang, sinh viên tìm chữ), bản mới có mô tả thay đổi và banner cho người đang đọc bản cũ, và giữ focus khi gõ qua chu kỳ kiểm tra 30 giây.

OCR native (bổ sung cùng ngày): runtime Tesseract 5 + Poppler dựng lại trong `.tooling/learning-ocr-native-20261117-01` (25 gói Ubuntu resolute, metadata có chữ ký, sha256 từng gói, giải nén không chạy script cài đặt, `pins.json`). Test `test_accessible_text_requires_review_and_retains_the_original[offline-sandbox]` đạt trong sandbox WSL/bubblewrap (đặt `LEARNING_OCR_NATIVE_HTTP=1`, `LEARNING_OCR_RUNTIME_DIR`, `LEARNING_OCR_FIXTURE_PDF=.tooling/learning-ocr-fixture-20261117-01/pdfs/synthetic-6.pdf`); trên PDF quét tổng hợp 6 trang, OCR đọc đúng từng chữ có dấu (độ tin cậy từ 92 đến 97). `learning-features.mjs` với `serve --ocr-runtime <bundle>` và `LEARNING_FEATURES_REAL_OCR=1` đạt 8/8 trên giao diện. Chữ tổng hợp chỉ kiểm tính đúng trên chữ in rõ; chữ viết tay, ảnh chụp nghiêng hoặc công thức chưa đo.

Giới hạn: chế độ mặc định của `learning-features.mjs` vẫn dùng OCR thay thế có kết quả cố định. PPTX: chuyển đổi LibreOffice thật trong sandbox WSL chạy được với bản PPTX tự dựng (3 trang, đủ chữ có dấu) nhưng chưa qua giao diện tải lên. Giải thích bằng AI (`/explain`) tắt mặc định vì cần nhà cung cấp trả phí, không chạy.

## Bộ kiểm tra bổ sung

`tests/learning_entry/test_material_lifecycle_audit.py` (HTTP thật, PDF tổng hợp): PDF hỏng, có mật khẩu, quá 500 trang; khai sai dung lượng, đuôi sai, tệp rỗng hoặc quá lớn; quyền của sinh viên và người ngoài lớp; nhiều phiên bản, thu hồi và quay về bản cũ; ẩn/hiện tài liệu và xung đột revision; thông báo khi công bố; tên tệp tải về.

## Cách chạy lại

- Python: đặt `LEARNING_TEST_ROOT` tới một thư mục có sẵn trong repo và `PYTHONPATH=services/worker/src`, rồi `pytest tests/learning_entry tests/unit/learning tests/learning_review`. Thiếu `LEARNING_TEST_ROOT` làm 35 test của `test_learning_backend.py` lỗi cấu hình (không phải lỗi code).
- Trình duyệt: tạo bản diễn tập bằng `scripts/learning_local_setup.py` (thêm hash hai PDF của kịch bản vào `synthetic_fixture_sha256`), dựng snapshot bằng `scripts/knowledge_platform_frontend.py build`, chạy `scripts/learning_test_host.py` (cổng 8025, frontend 3025), rồi `node apps/web/e2e/learning-integrated.mjs`. Đặt `LEARNING_TEST_VERSION_HISTORY=1` và `LEARNING_TEST_READER_SYNC=1` để chạy cả nhóm phiên bản/hẹn giờ/thu hồi và đồng bộ vị trí đọc; mặc định hai nhóm này bị bỏ qua.

Phạm vi: bằng chứng là test tự động và Chrome trên tài khoản, PDF tổng hợp. Mức dùng được với người dùng thật và công nghệ hỗ trợ (NVDA, VoiceOver, TalkBack) chưa đo.
