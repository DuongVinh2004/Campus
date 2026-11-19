# Kịch bản dùng thử học liệu theo buổi học

Ngày 05/11/2026 đã chuẩn bị lớp, tài khoản và kịch bản dùng thử. Phiếu quan sát đang trống và sẽ được điền trong các buổi có người tham gia.

Đợt kỹ thuật ngày 06/11/2026 bổ sung kịch bản BV-KB, BC-DUYET và BC-AT, cùng kết quả Chrome qua Campus, diễn tập tạm dừng OCR theo lớp và đo tải nhiều job. Dùng phiếu bên dưới để ghi kết quả với từng người và thiết bị. [Kế hoạch và bằng chứng đợt tiếp theo](LEARNING_MATERIALS_FOLLOWUP_20261106.md)

## Chuẩn bị

- Nhóm khởi đầu: 2 giảng viên, 8–12 sinh viên; có người dùng điện thoại Android và iPhone, desktop và trình duyệt quen dùng.
- Dùng lớp và học liệu tổng hợp trước. Nội dung thật cần người có thẩm quyền cung cấp quyền sử dụng và phân công lớp; không tự nhập danh sách sinh viên thật.
- Dùng [Campus học liệu cho nhóm thử](http://127.0.0.1:8029/learning) trên máy chủ local. Môi trường này có PostgreSQL riêng và hai lớp Cơ sở dữ liệu. Bài PDF mẫu đã công bố ở Buổi 1 của mỗi lớp. Giảng viên có thể tạo buổi và đăng phiên bản mới trong lớp được giao.
- Tài khoản tổng hợp nằm trong `.tooling/learning-campus-rehearsal-20261105-02/learning/credentials.json`. Phân công G01 cho lớp A, G02 cho lớp B, S01–S05 cho A và S05–S10 cho B. S05 đọc được cả hai lớp. S10 từng được ghi danh vào A và hiện đã bị ngưng ở lớp này. Người điều phối giữ tài khoản quản trị.
- Để thử từ điện thoại thật, cần một điểm vào thử truy cập được từ thiết bị. Địa chỉ loopback chỉ mở trên máy chủ. Xem [hướng dẫn chạy](LEARNING_MATERIALS_DELIVERY_20261105.md) và [kết quả kiểm quyền của hai lớp](../.tooling/learning-campus-rehearsal-20261105-02/pilot-seed-report.json).
- Người điều phối mô tả mục tiêu tác vụ, không hướng dẫn vị trí nút trước khi đo. Dừng nếu có lộ tài liệu sai lớp, mất dữ liệu hoặc nhầm phiên bản.
- Ghi người tham gia bằng mã G01/G02/S01…, không ghi mật khẩu, token hoặc nội dung riêng trong phiếu. Ghi thiết bị, OS, trình duyệt, kích thước màn hình và chất lượng mạng.
- Trước tác vụ, ghi cách tìm bài hiện tại và thời gian thực hiện trên cùng bài để có baseline. Không suy diễn mức tiết kiệm khi chưa có phép đo này.

## Tác vụ giảng viên

| Mã | Đề bài đưa cho người tham gia | Điều kiện thành công cần quan sát |
|---|---|---|
| G1 | Tạo buổi học, đặt tên và thời điểm | Buổi xuất hiện đúng lớp và đúng thứ tự |
| G2 | Đưa bài giảng PDF vào buổi, mở kiểm tra trước khi công bố | Sinh viên chưa đọc được nháp; giảng viên xem đúng đủ trang |
| G3 | Công bố bài cho lớp và kiểm tra kết quả | Kiểm đúng bản, lớp và xác nhận; tài khoản sinh viên thấy bài |
| G4 | Đưa bản cập nhật lên, công bố và kiểm tra bản cũ | Bản gốc cũ giữ nguyên; bản hiện hành đúng; ghi chú cũ không bị gán sang bản mới |
| G5 | Thu hồi bài có lỗi và kiểm tra tài khoản sinh viên | Xác nhận tác động; request content/Range sau thu hồi bị từ chối |
| G6 | Giao đọc trang 1–2 với một mục đích và câu hỏi | Sinh viên mở đúng phạm vi và phiên bản |
| G7 | Trả lời câu hỏi riêng của sinh viên và xác nhận trả lời hữu ích | Người ngoài phạm vi không thấy; nhãn xác nhận có tác giả |
| G8 | Bắt đầu trình bày, chuyển trang rồi kết thúc | Sinh viên chỉ theo khi chọn; người đang tự đọc không bị ép chuyển |
| G9 | Đăng PPTX có bảng, biểu đồ và công thức | Kiểm PDF xem trước cạnh bản gốc; slide, chữ và các giá trị cần dạy khớp; bản gốc tải lại nguyên vẹn |

## Tác vụ sinh viên

| Mã | Đề bài đưa cho người tham gia | Điều kiện thành công cần quan sát |
|---|---|---|
| S1 | Tìm bài của một buổi cụ thể trong lớp được giao | Đúng môn, lớp, buổi, bài và phiên bản |
| S2 | Đọc trang 2 theo chiều ngang rồi trở về chiều dọc | Giữ được trang đang đọc, thao tác cuộn dễ hiểu |
| S3 | Phóng to công thức, thu nhỏ, vừa trang và vừa rộng | Chữ rõ; pan xem được vùng phóng lớn; không mất điều hướng |
| S4 | Trên điện thoại, dùng hai ngón để zoom và quay về đọc bình thường | Zoom trong PDF hoạt động; browser zoom ngoài viewer vẫn dùng được |
| S5 | Tìm một cụm chữ có dấu, đi tới kết quả và dùng ảnh trang/mục lục | Đúng kết quả; thông báo rõ nếu PDF scan không có chữ |
| S6 | Đánh dấu trang và mở lại ở phiên/thiết bị khác | Đúng tài khoản, bản, trang; không thấy dấu của người khác |
| S7 | Đọc tiếp ở thiết bị thứ hai trong khi thiết bị đầu thay đổi vị trí | Thông báo xung đột có lựa chọn rõ, không âm thầm ghi đè |
| S8 | Ghi chú một đoạn chữ và một vùng sau khi xoay trang | Anchor khớp vị trí khi zoom/xoay; ghi chú riêng không hiện cho giảng viên |
| S9 | Đặt câu hỏi riêng theo một trang rồi xem trả lời | Nhận biết phạm vi chia sẻ; mở lại đúng vị trí nguồn |
| S10 | Theo giảng viên, tạm rời để tự đọc, quay lại và kết thúc | Vị trí cá nhân được giữ; thay đổi phiên bản được báo rõ |
| S11 | Mất mạng khi đang đọc rồi kết nối lại | Nội dung đã có vẫn có thể xem; lỗi đồng bộ không báo thành công giả |
| S12 | Đăng xuất hoặc bị ngưng ghi danh rồi mở liên kết cũ | Không mở thêm tài liệu hoặc byte mới; không chuyển sang tài khoản khác |
| S13 | Chuyển câu hỏi riêng thành câu hỏi cho lớp, sau đó nhờ bạn mở từ thông báo | Xem trước đúng nội dung, chọn xác nhận; bạn thấy câu hỏi và mở đúng trang, phản hồi riêng trước đó không xuất hiện |
| S14 | Sao chép liên kết một trang, mở bằng phiên thứ hai, kiểm trước và sau khi bản cũ bị thu hồi | Đúng phiên bản và trang khi còn quyền; bản bị thu hồi không tự chuyển sang bản mới |
| S15 | Với PDF tổng hợp đã cho phép AI, hỏi một câu có nguồn và một câu cần thông tin ở trang khác | Câu trả lời đủ căn cứ và mở đúng trang; câu thiếu nguồn được từ chối |

PPTX đã có converter và sandbox trên bản dùng thử. Chọn bản gốc tổng hợp có quyền dùng và ghi rõ cấu hình cùng các đặc điểm cần đối chiếu. Bản dùng thử đang tắt AI. S15 cần cấu hình có gateway và phạm vi egress được cấp, với nguồn tổng hợp khớp mã băm đã duyệt.

## Phiếu ghi kết quả

Mỗi hàng là một người thực hiện một tác vụ. Để trống kết quả đến lúc đo, không điền số giả định.

| Người | Thiết bị/OS/trình duyệt | Tác vụ | Bắt đầu | Kết thúc | Giây | Tự hoàn thành | Lần cần trợ giúp | Lỗi/cản trở quan sát được | Ý kiến ngắn |
|---|---|---|---|---|---|---|---|---|---|
| Chưa thu thập | | | | | | | | | |

Đánh dấu tự hoàn thành chỉ khi đạt điều kiện mà không được chỉ vị trí nút hoặc làm hộ. Ghi cả thất bại và bỏ cuộc. Với từng tác vụ, báo tử số/mẫu số người tự hoàn thành, thời gian và từng lỗi; mục tiêu đề xuất ≥80% tự hoàn thành. Mẫu nhỏ dùng để tìm vấn đề thao tác, không kết luận thống kê cho toàn trường.

## Kết thúc một đợt

1. Tổng hợp riêng desktop, Android, iPhone và người cần hỗ trợ tiếp cận; không che nhóm gặp lỗi bằng trung bình chung.
2. Mỗi lỗi có bước tái hiện, bản đang dùng, mức ảnh hưởng và kiểm tra lại sau sửa. Không đưa dữ liệu riêng vào log.
3. Đối chiếu thời gian tìm bài với baseline cùng tác vụ; phân biệt hiệu quả thao tác với hiệu quả học tập.
4. Nghiệm thu riêng PDF, ghi chú/hỏi đáp, PPTX, trình bày và AI. Mục chưa chạy giữ trạng thái chưa đo; không gán kết quả của PDF cho toàn bộ kế hoạch.

## Kịch bản bổ sung E1 và E2

Dùng lớp và nội dung tổng hợp đã bật flag cho từng tính năng. Cho người tham gia tự thực hiện trước khi giải thích cách dùng. Chuẩn bị một bài được dùng lại ở hai buổi, liên kết cũ chỉ chứa phiên bản và trang, hai bản PDF, một bản xem PowerPoint và một ghi chú riêng trên bản trước. Dữ liệu kiểm ngưỡng gồm một lớp có 9 sinh viên và một lớp có ít nhất 10 sinh viên. Để kiểm ngưỡng, dùng tài khoản tổng hợp riêng cho từng lượt báo.

| Mã | Đề bài cho người tham gia | Bằng chứng cần ghi |
|---|---|---|
| BV-01/02 | Mở liên kết cũ của bài dùng lại, báo vướng cho buổi chỉ định. Mở cùng trang từ buổi kia, sửa rồi rút. | Ghi trang và buổi quan sát được, số lần cần trợ giúp và thời gian từ mở nút đến máy chủ xác nhận. Lần mở từ buổi kia vẫn hiển thị buổi đã gắn ban đầu. |
| BV-03 | Hai giảng viên xem trước/sau giờ chốt ở lớp dưới ngưỡng và lớp đủ ngưỡng. Sau giờ chốt, một sinh viên sửa hoặc rút báo vướng. | Ghi dạng thông báo ở trang có 0/4 lượt và dải ở trang đủ ngưỡng. Mở lại sau thay đổi và kiểm dải đã chốt. Phiếu quan sát dùng mã tình huống, không ghi danh tính người báo. |
| BV-04 | Giảng viên mở trang từ dải, soạn một ví dụ hoặc lời giải chung, kiểm tra bản xem trước rồi công bố. Sinh viên khác mở từ thông báo. Thử thêm một lời giải ở lớp dưới ngưỡng. | Ghi buổi, phiên bản, trang, nội dung giảng dạy đã thực hiện và quyền đọc khi nguồn còn hiệu lực. Tiêu đề thông báo trung tính. Sau thu hồi hoặc gỡ link, tải lại và kiểm lời giải cùng thông báo. |
| TD-01/02 | Công bố bản mới với một trang được chuyển, một trang mới thêm và một trang cũ bị bỏ. Với bản xem PowerPoint, chọn cặp trang PDF và slide khác số. | Ghi phiên bản và trang thực tế của từng nút. Mở lại liên kết và ghi chú riêng của bản trước khi bản trước còn quyền. |
| TD-03 | Tạo bản xem trước hoặc hẹn giờ, rồi chỉnh mô tả trước khi công bố. Sau khi công bố đúng revision, thu hồi bản trước. | Ghi trạng thái hẹn giờ, phiên bản hiện hành và đường đọc lại. Sau thu hồi, kiểm chỉ dẫn độc lập của bản mới và kiểm các trường so sánh bản trước qua API. |

Đo BV trên ít nhất 6 tình huống trang–buổi đủ điều kiện, phân bố qua ít nhất 4 buổi tổng hợp và hai giảng viên. Đánh dấu một hành động đạt khi ví dụ, lời giải hoặc đính chính đã công bố, hoặc khi quan sát được việc giảng lại trong buổi sau. Ghi loại hành động, mã tình huống và đường dẫn bằng chứng vào phiếu dùng thử. Mục tiêu thí điểm là ít nhất 3/6 tình huống có hành động trong 7 ngày.

Đo TD với cùng tác vụ đọc lại, đổi thứ tự sử dụng cách hiện tại và cách mới giữa các người tham gia. Ghi tỷ lệ chọn đúng và thời gian của cả hai cách. Mục tiêu đề xuất là ít nhất 80% tự chọn đúng và trung vị giảm ít nhất 25%. Các mục này chờ số liệu từ người tham gia và thiết bị thật.

## Kịch bản bổ sung E3–E5

Dùng lớp diễn tập đã bật từng tính năng. Chuẩn bị một sinh viên có quyền nguồn, một bạn cùng lớp và một người ngoài lớp. Dùng một bản PDF scan có chữ Việt, một trang bảng và một trang công thức với giá trị đối chiếu. Cài giờ thiết bị khác giờ lớp cho ít nhất một lượt.

| Mã | Đề bài cho người tham gia | Bằng chứng cần ghi |
|---|---|---|
| RL-01/02 | Giảng viên giao phiếu gắn trang nguồn. Sinh viên mở đúng trang, trả lời rồi kiểm tra biên nhận khi mất kết nối sau lúc gửi. Mở cùng phiếu từ tab thứ hai và thử sửa. | Giờ lớp và giờ thiết bị, thời điểm mở/đóng, revision biên nhận, số lần gửi và lựa chọn khi xung đột. Lặp lại ca đi qua hạn trong lúc mất kết nối. |
| RL-03/04 | Giảng viên xem bài đã đóng, ghi nhận lỗi và soạn lời giải chung. Ở phiếu khác, gia hạn hoặc hủy khi đã có bài. Sau đó thu hồi nguồn và cho sinh viên tìm lại biên nhận. | Phạm vi đọc của từng tài khoản, tác động trong bản xem trước, lỗi phát hiện có bài làm hỗ trợ và một điều chỉnh cho buổi sau. Phiếu quan sát không ghi nguyên văn câu trả lời riêng. |
| YT-01/02 | Lưu một đoạn chữ, một vùng hình hoặc công thức và một phiếu dẫn cả trang. Nhóm theo đề tài, mở lại nguồn và chia sẻ một revision cho đúng một người. | Trang và phiên bản thực tế, khả năng nhận ra trích dẫn và ý kiến riêng, revision người nhận thấy sau khi chủ phiếu sửa bản riêng. Ghi số người tự hoàn thành và thời gian. |
| YT-03 | Giữ hai tab mở. Rút chia sẻ hoặc ngưng quyền nguồn trong khi người nhận đang xem, rồi thử lại đường dẫn trước và sau khi cấp lại quyền. | Quyền qua URL, thông báo và tab cũ. Chủ phiếu vẫn thấy phần tự viết và có thể rút chia sẻ khi nguồn đã mất quyền. |
| BC-01/02 | Giảng viên tạo OCR, đối chiếu chữ, bảng và công thức, công bố một phần. Sinh viên dùng bàn phím và trình đọc màn hình để tìm cụm có dấu, đọc heading/bảng, chọn chữ và trở về ảnh nguồn. | Số phút duyệt theo nhóm, giá trị/đơn vị/dấu/chỉ số khớp gold, trang tìm được, thứ tự đọc, focus và kết quả quay về ảnh. Kiểm PDF ở mức phóng lớn và tại 360 px. |
| BC-04 | Sau khi đã mở bản chữ, ngưng ghi danh hoặc thu hồi nguồn. Trong lượt riêng, tắt flag bản chữ và mở lại PDF bằng tài khoản còn quyền. | Thời điểm mất quyền, nội dung còn xuất hiện ở tab cũ, kết quả tìm/tải lại, trạng thái PDF gốc và phản hồi hỗ trợ tiếp cận. |

Chạy BC bằng NVDA trên Windows, VoiceOver trên iPhone và TalkBack trên Android. Ghi tên, phiên bản công nghệ hỗ trợ, OS và trình duyệt cùng kết quả của từng tổ hợp. Đối chiếu ngưỡng ở mục 10 của [kế hoạch mở rộng](LEARNING_MATERIALS_EXPANSION_PLAN_20261105.md). Điền phiếu quan sát riêng cho từng người và tác vụ.

## Bằng chứng kỹ thuật ngày 06/11/2026

Tài khoản, lớp, bài nộp, bản PDF và gold đều là dữ liệu tổng hợp. Bộ đo OCR đối chiếu SHA-256 của từng PDF và ảnh trước khi chạy worker. Chrome dùng viewport desktop và viewport mô phỏng điện thoại, với phiên đăng nhập riêng cho từng vai trò.

| Hạng mục | Kết quả và phạm vi |
|---|---|
| E1 qua Chrome | Giảng viên xác nhận mở cửa sổ báo vướng. Sinh viên báo và rút ở đúng buổi gắn với trang đang đọc. Trong khi cửa sổ còn mở, giảng viên thấy trạng thái chờ chốt. [Báo cáo Chrome](../.tooling/learning-expansion-browser-20261106-01/exit-ideas-15/report.json) |
| E2 qua Chrome | Giảng viên xem cặp trang 2 → 3 trong bản xem trước rồi công bố. Từ bản mới, sinh viên quay lại đúng trang 2 của bản trước còn quyền. [Báo cáo Chrome](../.tooling/learning-expansion-browser-20261106-01/exit-ideas-13/report.json) |
| E3 và E4 qua Chrome | Giảng viên công bố phiếu theo giờ Bangkok trong Chrome đặt UTC. Sinh viên tìm lại biên nhận lần 1 sau khi máy chủ đã ghi nhưng trình duyệt mất ACK. Bạn cùng lớp không thấy bài nộp. Người được chọn mở đúng trang của Phiếu ý tưởng, rồi mất quyền đọc sau khi chủ phiếu rút chia sẻ. [Báo cáo Chrome](../.tooling/learning-expansion-browser-20261106-01/exit-ideas-07/report.json) |
| E5 qua Chrome | Giảng viên mở ứng viên OCR thật, đối chiếu khối trên ảnh và xác nhận công bố một trang. Sinh viên trên viewport 390 px không đọc được bản nháp, tìm được cụm tiếng Việt có dấu, focus vào heading rồi quay lại đúng vùng ảnh trên PDF. Khi bản chữ bị thu hồi, tab đang mở bỏ nội dung và PDF vẫn trả Range 206 theo quyền. [Đọc và công bố](../.tooling/learning-expansion-browser-20261106-01/ocr-05-report.json), [thu hồi](../.tooling/learning-expansion-browser-20261106-01/ocr-06-report.json) |
| PostgreSQL 0030 | Bản chia sẻ giữ revision đã duyệt. Cấp lại ghi danh không mở lại grant đã đình chỉ. Trigger chặn sửa liên kết nguồn và phục hồi grant bằng SQL. Phục hồi vào DB tổng hợp riêng giữ các hàng E4, audit và biên nhận. [Bản dump](../.tooling/learning-idea-cards-pg-20261106-01/learning-schema.dump) |
| PostgreSQL 0031 và OCR thật | Hai lượt tick đồng thời tạo một ứng viên cho trang được yêu cầu. Ứng viên còn riêng trước khi duyệt. Chỉ một trang được công bố và tìm được theo tiếng Việt có dấu. Ẩn rồi hiện nguồn không mở lại bản chữ cũ. Hash PDF gốc khớp. [Báo cáo vòng đời](../.tooling/learning-ocr-postgres-20261106-01/rehearsal-03/lifecycle-report.json) |
| Phục hồi E5 | Dump schema học liệu vào DB tổng hợp mới và phục hồi file PDF vào kho mới. Metadata OCR, con trỏ bản công bố, audit, biên nhận và outbox khớp từng hàng. SHA-256 PDF khớp và bản chữ từng mất quyền vẫn không khả dụng. [Báo cáo phục hồi](../.tooling/learning-ocr-postgres-20261106-01/recovery-01/report.json) |
| LOAD-01 phần Phiếu ra lớp | 300 lượt ghi thành công trong 10 đợt ở hai lớp, 30 người mỗi đợt, 30 lượt gửi lại khớp revision và 100 phản hồi Range 64 KiB khớp từng byte. p95 ghi 584,4 ms sau khi giới hạn truy vấn giao dịch theo phiếu và người nộp, so với 2.186,0 ms trước thay đổi. p95 Range 472,8 ms. Job OCR 20 trang chạy cùng đợt và kết thúc sau 59,1 giây. Mẫu một job chỉ đo được thời gian của job này. [Trước sửa](../.tooling/learning-ocr-postgres-20261106-01/mixed-load-02/report.json), [sau sửa](../.tooling/learning-ocr-postgres-20261106-01/mixed-load-03/report.json) |
| P53 holdout OCR native | 20 trang mất 59,9 giây, trung vị 2,75 giây/trang. Chữ rõ đạt CER 0,10%, WER 0,46%, thứ tự 95% và 23/24 cụm chữ xuất hiện. Scan khó đạt CER 0,29% nhưng thứ tự 80% và 21/24 cụm xuất hiện. Hai cột CER 50,31%. Bảng khớp 8/12 token, công thức 0/6. [Báo cáo holdout](../.tooling/learning-ocr-postgres-20261106-01/native-holdout-01/report.json) |
| P60 sau MVP | 8 cặp phiên bản tổng hợp với PDF có chữ, scan, đổi thứ tự, chỉnh sửa, thêm/bỏ và trang trùng. Ghép đúng 16/16 cặp đã gợi ý trên 48 cặp gold. Recall 33,3%, precision của ứng viên thêm và bỏ đều 20%, chưa có gợi ý khớp cho trang đã chỉnh. Giữ luồng chọn cặp thủ công. [Báo cáo spike](../.tooling/learning-expansion-browser-20261106-01/version-spike-01/report.json) |

Phạm vi diễn tập OCR ưu tiên chữ rõ và chỉ công bố trang đã đối chiếu. Với scan khó, nhiều cột, bảng và công thức, kiểm thủ công từng khối hoặc giữ đường về ảnh nguồn. Các phép đo cụm chữ trong holdout là đối chiếu chữ thô. Cần ghi riêng thời gian duyệt của giảng viên và kết quả tìm, đọc, quay về ảnh trên từng công nghệ hỗ trợ.

Phiếu dùng thử còn chờ người tham gia, thiết bị thật và điểm vào dành cho thiết bị. Chưa có số đo thời gian duyệt, p95 OCR qua nhiều job, CPU/RAM WSL, hoặc thời gian hiển thị trang đầu trong cùng phép đo tải hỗn hợp. Các flag mở theo lớp diễn tập và mặc định tắt.

Để chạy lại bài kiểm tra kỹ thuật qua Chrome, dùng cấu hình tổng hợp [features.json](../.tooling/learning-expansion-browser-runtime-20261106-02/features.json) và kho SQLite đi kèm qua `scripts/learning_test_host.py`. Giao diện Next dùng `NEXT_PUBLIC_KNOWLEDGE_PLATFORM=true`. Cấu hình mẫu ghi mã lớp diễn tập cho `page_feedback_offerings`, `version_change_offerings`, `exit_ticket_offerings`, `idea_card_offerings` và `accessible_text_offerings`. Khi bật OCR, dùng manifest mã băm và đường dẫn runtime/scratch đã kiểm của môi trường cục bộ. Với PostgreSQL, dùng bản sao diễn tập được xác minh đến 0031. Kho dùng cho các bài thử Chrome đã có giao dịch công bố, nộp và thu hồi nên mỗi lượt đo độc lập cần một fixture mới.
