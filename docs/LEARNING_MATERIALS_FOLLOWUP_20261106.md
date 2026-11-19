# Hoàn thiện học liệu trước đợt dùng thử

Ngày 06/11/2026 · Campus 24/7 · dữ liệu tổng hợp trên máy local

Sinh viên cần báo vướng bằng bàn phím mà vẫn biết mình đang báo buổi và trang nào. Giảng viên cần thấy trang OCR nào cần duyệt tiếp và nhận ra chỗ cần đối chiếu kỹ. Người vận hành cần giảm tải OCR theo lớp trong khi sinh viên vẫn có thể đọc tài liệu đang công bố. Các nhu cầu này nối trực tiếp với luồng hiện có và khoảng trống trong [kế hoạch mở rộng](LEARNING_MATERIALS_EXPANSION_PLAN_20261105.md) và [bằng chứng UAT kỹ thuật](LEARNING_MATERIALS_UAT_20261105.md).

## Thứ tự và tiêu chí đợt này

| Bước | Việc triển khai | Tiêu chí và phép kiểm |
|---|---|---|
| 1 | E1 ổn định focus và thông báo trong hộp thoại báo vướng. | Mở bằng bàn phím, đọc được ngữ cảnh đã chụp, chọn lý do, nhận trạng thái và đóng về đúng nút mở. Kiểm lỗi mất biên nhận và giữ khóa lần gửi lại. Vitest và Chrome desktop/viewport hẹp. |
| 2 | E5 làm rõ tiến độ duyệt theo trang và đường đối chiếu ảnh. | Tìm được trang cần duyệt tiếp bằng bàn phím, nhận ra nhóm OCR cần đối chiếu, lưu rõ trạng thái thành công hoặc lỗi. Vẫn dùng revision đang xem và xác nhận công bố hiện có. Kiểm thành phần và Chrome với fixture tổng hợp. |
| 3 | E5 thêm công tắc tạm dừng nhận và lấy job OCR theo lớp. Ghi quy trình điều khiển năm tính năng theo lớp. | Kiểm cấu hình mặc định và từ chối cấu hình sai. Lớp tạm dừng chặn yêu cầu mới, thử lại và nhận lease mới. Giữ đường duyệt, bản đã công bố, PDF và lớp khác. Bật lại xử lý hàng đợi cũ. Kiểm quyền, replay và byte nguồn. |
| 4 | Chạy bộ đo nhiều job OCR và tải hỗn hợp local. | Tối thiểu 5 job native, báo số trang, queue và xử lý, p95 thực nghiệm, đối chiếu hash PDF. Chạy lượt ghi E3 đồng thời có gửi lại và kiểm byte Range. So với mốc 750 ms và 1% lỗi nếu cấu hình đo tương đương. Ghi rõ hệ lưu trữ, cỡ mẫu và phạm vi đo CPU/RAM hoặc trang đầu thực tế. |
| 5 | Chạy hồi quy và chuẩn bị buổi dùng thử. | Chạy Python và frontend, kiểm trình duyệt qua điểm vào Campus tổng hợp có cùng đường `/learning` và `/v1/learning`, kiểm các tính năng đã có bằng bộ hồi quy hiện hành. Bổ sung phiếu thao tác, phép đo duyệt, cách xác định điểm vào thiết bị và điều kiện dừng. Kết quả kỹ thuật và kết quả với người dùng được ghi riêng. |

Các bước 1, 2 và chuẩn bị bộ đo thực hiện song song trên các đường ghi riêng. Dùng lại điểm vào diễn tập Campus và tạo trạng thái tổng hợp mới. Mọi thao tác mở hoặc tạm dừng áp dụng cho bản diễn tập.

## Backlog có điều kiện

- **Gợi ý ghép trang P60.** Giữ đối chiếu thủ công. Corpus hiện chỉ tìm đúng 16 trong 48 cặp gold, độ chính xác cho ứng viên thêm và bỏ đều 20%. Chỉ xem xét lại sau khi có corpus độc lập đủ ca trang chỉnh sửa, trùng và đổi thứ tự.
- **Tự động hiểu bảng, cột và công thức.** Holdout có CER 50,31% ở hai cột, khớp 8/12 token bảng và 0/6 token công thức. Thử có kiểm duyệt với trang chữ rõ. Với nội dung cấu trúc, dùng ảnh nguồn và đối chiếu từng khối trước khi mở rộng.
- **Gom đầu việc của buổi cho sinh viên và giảng viên.** Chờ quan sát người tham gia tìm phiếu ra lớp, bản mới và lời giải. Sau đó mới chọn đưa trạng thái nào vào danh sách buổi để tránh tạo thêm đường đọc dư thừa hoặc lộ nội dung riêng.
- **Mở rộng thí điểm.** Còn cần phép đo trên thiết bị, người tham gia và điểm vào được cấp. Các phép đo đối chứng phần cứng và năng lực tải dài hạn được thực hiện trước quyết định tăng quy mô.

## Vận hành bản diễn tập

Chọn đúng bundle tổng hợp và kiểm `synthetic_rehearsal` tại `/health/entry`, tên DB, revision schema và UUID lớp trước khi chỉnh cấu hình. Giữ bản cấu hình trước chỉnh trong bundle theo một tên mới. Các danh sách dưới đây nhận UUID chuẩn, mặc định rỗng và được đọc khi khởi động API. Đưa lớp vào danh sách để mở tính năng. Muốn thu hẹp, đưa lớp ra khỏi danh sách và kiểm lại bằng phiên mới của giảng viên, sinh viên có quyền và tài khoản ngoài lớp. Trên Campus diễn tập, đường dẫn cấu hình là `learning/config.json` cạnh `rehearsal.json`.

| Cấu hình | Kiểm sau khi áp dụng trên bản diễn tập |
|---|---|
| `page_feedback_offerings` | Nút báo vướng và đường báo cáo theo buổi có ở lớp bật. Dùng dữ liệu dưới ngưỡng để kiểm báo cáo ẩn đúng. |
| `version_change_offerings` | Mô tả thay đổi và đường quay lại đúng bản/trang xuất hiện theo quyền. Mở lại link PDF cũ để kiểm phiên bản đã ghim. |
| `exit_ticket_offerings` | Kiểm danh sách phiếu, biên nhận theo chủ và 404 của tài khoản khác. Khi tắt cả tính năng, đường đọc biên nhận của lớp cũng tạm mất. Tránh dùng việc tắt toàn bộ trong lúc đang nhận bài để xử lý riêng vấn đề tải. |
| `idea_card_offerings` | Kiểm tạo phiếu theo lớp, dẫn nguồn và người nhận. Khi một lớp tắt, nguồn và quyền đọc qua chia sẻ của lớp đó bị ẩn. Nếu còn lớp bật, kho cá nhân vẫn có thể hiện phần tự viết với nguồn không khả dụng. |
| `accessible_text_offerings` | Kiểm bản chữ công bố, tìm kiếm, quyền quản lý và PDF gốc. Đưa lớp ra khỏi danh sách khi cần dừng cả việc đọc bản chữ. Nếu lớp cũng nằm trong danh sách tạm dừng OCR thì đưa lớp ra khỏi cả hai để cấu hình hợp lệ. |
| `accessible_text_ocr_paused_offerings` | Để giảm tải OCR, giữ lớp trong `accessible_text_offerings` và thêm lớp vào danh sách này. Yêu cầu mới và thử lại trả 503 `OCR_PROCESSING_PAUSED`. Job đang chờ giữ revision và quota đã đặt, worker bỏ qua khi lấy lease mới. Giảng viên vẫn xem, duyệt, công bố hoặc thu hồi bản chữ đủ quyền và có thể hủy job. Sinh viên đọc bản chữ đã công bố và PDF theo quyền hiện tại. |

Tạm dừng xử lý có hiệu lực khi tất cả tiến trình API và worker của bản diễn tập đã dùng cấu hình mới. Nếu một trang còn lease từ tiến trình trước, đợi xử lý kết thúc hoặc lease hết hạn. Khi mở lại, bỏ UUID khỏi danh sách tạm dừng, dùng cùng profile OCR đã ghim và kiểm job cũ tiếp tục theo trạng thái, lease và quyền của nguồn. Kiểm lại số lượng job, quota, một lượt đọc bản chữ và byte Range trước khi tăng số lớp. Dừng lượt thử nếu có lộ quyền, nhầm revision hoặc lệch hash. Ghi mã lỗi, lớp tổng hợp, khoảng thời gian, p95 và số mẫu. Giữ bài nộp, nội dung riêng và thông tin đăng nhập ngoài log.

## Kịch bản cho người tham gia và thiết bị

Kế thừa [phân vai, cách đo và phiếu quan sát](LEARNING_MATERIALS_UAT_20261105.md). Dùng hồ sơ và tài liệu tổng hợp mới mỗi lượt. Chạy thử địa chỉ đã cấp từ chính thiết bị, kiểm đăng nhập và mở PDF lớp được giao qua cùng origin, rồi kiểm tài khoản ngoài lớp nhận từ chối. Máy chủ giữ DB và frontend nội bộ trên loopback. Người điều phối cần cung cấp địa chỉ thử truy cập được từ thiết bị trước buổi đo. Lượt này dùng `127.0.0.1:8034` và dừng các tiến trình diễn tập sau khi kiểm.

| Mã | Đề bài và bằng chứng |
|---|---|
| BV-KB | Dùng bàn phím mở báo vướng, xác định buổi/trang, chọn lý do, gửi và đóng. Quan sát focus, thứ tự Tab, phản hồi đọc được và vị trí quay lại. Thử lại sau mất kết nối với cùng thao tác. |
| BC-DUYET | Hai giảng viên dùng bản tổng hợp có chữ rõ, scan khó, hai cột, bảng và công thức. Bắt đầu bấm giờ khi trang duyệt hiện đầy đủ, kết thúc khi thấy lưu thành công. Ghi phút mỗi trang, loại khối, số lần phải về ảnh và lỗi còn lại khi so với gold. Xác minh 100% giá trị, đơn vị, dấu, chỉ số bắt buộc ở khối định công bố. Dùng chỉ dẫn về ảnh cho khối chưa kiểm được. |
| BC-AT | Trên Windows/NVDA, iPhone/VoiceOver và Android/TalkBack, tìm một cụm có dấu, xác định kết quả đúng trang, đọc heading và bảng đã đối chiếu, rồi về đúng ảnh. Ghi phiên bản OS, trình duyệt, công nghệ hỗ trợ, lỗi cản trở, thời gian và lần cần trợ giúp cho mỗi người. Lặp thao tác tìm khi bản chữ bị thu hồi trong phiên. |

Mỗi dòng đo ghi mã người tham gia và tác vụ, thiết bị, thời gian đầu/cuối, tự hoàn thành, lần cần trợ giúp và lỗi tái hiện được. Báo thời gian duyệt theo loại trang và kết quả công nghệ hỗ trợ theo từng tổ hợp. Đối chiếu các ngưỡng của kế hoạch mở rộng sau khi có mẫu. Bằng chứng Chrome bên dưới dùng viewport mô phỏng và bàn phím trình duyệt.

## Số đo tải local

Hai cấu hình dùng PostgreSQL 17.11 mới với migration 0031 và OCR Tesseract/Poppler trong sandbox WSL. Mỗi cấu hình có 300/300 lượt nộp thành công, 0% 5xx, 30/30 gửi lại khớp biên nhận revision 1 và 100/100 Range 64 KiB khớp từng byte.

| Cấu hình | Kết quả |
|---|---|
| Đối chiếu, 40 request mỗi đợt và một job OCR | p95 ghi 730,9 ms, Range 611,5 ms. Job 20 trang hoàn thành sau 65,7 giây. Một trang OCR đang xử lý trong khoảng có HTTP. [Báo cáo](../.tooling/learning-followup-load-20261106-01/run-05/report.json) |
| Mở rộng, 50 request mỗi đợt, thêm 100 lượt đọc metadata và tối đa hai worker OCR | p95 ghi 1.485,0 ms, Range 1.049,8 ms, metadata 1.124,5 ms. Metadata trả đúng 100/100. Bốn lượt xử lý trang giao với tải HTTP. Vượt mốc p95 ghi 750 ms và metadata 500 ms. [Báo cáo](../.tooling/learning-followup-load-20261106-01/run-03/report.json) |

Ở lượt mở rộng, 5/5 job hoàn tất với 100/100 trang chờ duyệt và SHA-256 nguồn khớp. p95 thực nghiệm từ nhận job đến hết xử lý là 58,356 giây (n = 5, cũng là mẫu lớn nhất). p95 chờ 1,302 giây và p95 xử lý 58,250 giây. Cận trên đến khi kết quả đã ghi vào kho là 58,502 giây. Mẫu cây tiến trình OCR trong WSL ghi tổng RSS cao nhất 179,9 MiB và 61,95 giây CPU quan sát được. [Cách chạy lại và phạm vi lấy mẫu](../.tooling/learning-followup-load-20261106-01/README.md)

Giữ mức một worker OCR và mức tải của lượt đối chiếu cho bản diễn tập. Biên p95 ghi chỉ còn 19,1 ms trong mẫu này. Hai lượt thay đổi đồng thời số phiên bản, số worker và số lượt đọc metadata. Cần phép đo tách từng yếu tố trước khi tăng tải hoặc đổi phạm vi truy vấn PostgreSQL. Thời gian hiển thị trang đầu qua Next trong cùng tải hỗn hợp chưa có phép đo đối chứng.

## Đối chiếu nghiệm thu kỹ thuật

| Bước | Bằng chứng |
|---|---|
| 1 · Bàn phím E1 | Chrome tại 360 và 1.440 px kiểm mở bằng Enter, hai chiều vòng Tab, chọn lý do bằng phím mũi tên, lưu, focus vùng trạng thái và Escape về nút mở. Vitest mô phỏng mất phản hồi, đọc lại và thử với cùng payload, revision và khóa. [Chrome](../.tooling/learning-followup-campus-20261106-01/chrome-04/report.json) |
| 2 · Duyệt E5 | Với OCR thật ở PostgreSQL 0031, giảng viên mở đúng khối ảnh, lưu trang 1 và focus vào tiêu đề trang 6 sau ghi thành công. Sinh viên không đọc được nháp, tìm cụm tiếng Việt ở trang đã công bố, quay về đúng ảnh ở 360 px, tải Range 206 và PDF có SHA-256 khớp. Đã tái hiện lỗi nhảy sang trang 2 trước sửa và chạy qua sau khi bỏ tính lại tỷ lệ trên vùng ảnh kích thước 0. Vitest kiểm xác nhận lại sau khi sửa bảng và giữ nguyên trang khi API báo xung đột revision. [Chrome trước sửa](../.tooling/learning-followup-campus-20261106-01/chrome-02/report.json), [Chrome sau sửa](../.tooling/learning-followup-campus-20261106-01/chrome-04/report.json) |
| 3 · Điều khiển theo lớp | Kiểm cả năm flag với sinh viên có quyền PDF ở hai lớp. Sau khởi động ở chế độ tạm dừng, yêu cầu OCR mới trả 503, đường duyệt và bản chữ công bố vẫn đọc được, Range và SHA-256 khớp. Sau mở lại, yêu cầu khớp job cũ, giữ ID và revision. Test lớp tạm dừng bỏ qua job trong hàng đợi, lớp khác vẫn nhận lease, và job cũ chạy khi mở lại. Các ca khác kiểm cấu hình sai, quyền, hủy và replay cùng khóa. [Trước pause](../.tooling/learning-followup-campus-20261106-01/switches-before.json), [pause](../.tooling/learning-followup-campus-20261106-01/switches-paused.json), [mở lại](../.tooling/learning-followup-campus-20261106-01/switches-reopened.json) |
| 4 · Tải và nhiều job | Đã thu đủ mẫu đã chọn. Lượt đối chiếu đạt mốc ghi với biên hẹp. Lượt mở rộng vượt mốc và được giữ ngoài cấu hình diễn tập. |
| 5 · Hồi quy và kịch bản | 132 ca Python và 2 subtest, gồm OCR native HTTP, phân quyền, revision, idempotency, hợp đồng và phục hồi fixture. Toàn bộ Vitest qua 493 ca, chạy lại 73 ca Học liệu và bàn phím sau sửa trình đọc. TypeScript và build Next qua. Chrome cùng origin kiểm E2 mở lại đúng bản và trang, E3 mất ACK lấy lại biên nhận và E4 người nhận mất quyền sau rút chia sẻ. Chat streaming và lịch sử, dịch vụ lưu nháp có xác nhận và đăng xuất qua cùng điểm vào đều qua. [E2](../.tooling/learning-followup-campus-20261106-01/exit-ideas-02/report.json), [E3/E4](../.tooling/learning-followup-campus-20261106-01/exit-ideas-01/report.json), [hồi quy điểm vào](../.tooling/learning-followup-campus-20261106-01/entry-regression-01.json) |

Bằng chứng gồm test tự động, tài khoản tổng hợp và PDF OCR đối chiếu hash. Chrome ghi ba lần mở trang đầu trong khoảng 1,31–1,80 giây trên hai viewport. Đây là thời gian từ điều hướng đến khi thấy canvas trong một lượt smoke. Chưa đo p95 trang đầu khi tải hỗn hợp hoặc tác động với người dùng thật.

Bản diễn tập dùng bundle mới `learning-campus-rehearsal-20261106-03`, build `frontend-knowledge-learning-followup-20261106-03` và entry loopback 8034. Script tạo bundle, bài kiểm Chrome và báo cáo nằm trong [thư mục bằng chứng Campus](../.tooling/learning-followup-campus-20261106-01/). API, frontend và cụm PostgreSQL của lượt này đã dừng. Các kết quả người tham gia, thời gian duyệt và từng tổ hợp công nghệ hỗ trợ còn để trống trong [phiếu UAT](LEARNING_MATERIALS_UAT_20261105.md).
