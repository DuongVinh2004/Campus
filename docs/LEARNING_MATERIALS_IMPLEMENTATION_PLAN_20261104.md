# Kế hoạch thiết kế và triển khai học liệu theo buổi học

**Sản phẩm:** Campus 24/7  
**Ngày lập:** 04/11/2026 theo múi giờ Asia/Bangkok  
**Phiên bản:** 1.0  
**Người sử dụng tài liệu:** chủ sản phẩm, người thiết kế giao diện, lập trình viên và người kiểm thử  
**Trạng thái:** thiết kế đề xuất để bắt đầu triển khai; chưa phải báo cáo tính năng đã hoạt động

Tài liệu chuyển ý tưởng giảng viên đăng bài giảng và sinh viên đọc trực tiếp theo buổi học thành phạm vi sản phẩm, thiết kế kỹ thuật, danh sách công việc và điều kiện nghiệm thu. Bản đầu phải hoàn thành được vòng sử dụng từ tổ chức lớp, công bố tài liệu đến đọc trên máy tính và điện thoại, cập nhật phiên bản và đọc tiếp. Các phần ghi chú, hỏi đáp theo trang, PowerPoint, hướng dẫn đọc, đồng bộ trang giảng và AI có lộ trình riêng bên dưới.

Đây là kế hoạch thực hiện, không tạo thêm quy trình duyệt tài liệu trước mỗi công việc. Khi triển khai, tiếp tục các phần độc lập trong phạm vi được giao; một tích hợp chưa có dữ liệu thật chỉ chặn phần phụ thuộc trực tiếp vào tích hợp đó. Kế hoạch không cấp quyền truy cập dữ liệu thật, thay đổi môi trường sản xuất hoặc thực hiện thao tác phá hủy.

## 1 Mục tiêu và kết quả cần đạt

Tên tính năng trong menu là **Học liệu**. Tên đầy đủ trong tài liệu là **Học liệu theo buổi học**.

Giảng viên có một nơi tổ chức bài giảng theo lớp học phần và buổi học. Sinh viên tìm đúng bài của buổi, mở ngay trong Campus 24/7, thay đổi cách xem như một trình đọc PDF và quay lại vị trí đang đọc. Khi tài liệu được sửa, người học nhận biết phiên bản mới mà các ghi chú hoặc liên kết cũ vẫn giữ đúng nguồn.

| Mã mục tiêu | Kết quả mong muốn | Cách đánh giá |
|---|---|---|
| OBJ01 | Giảng viên tự đăng và công bố đúng bài cho đúng lớp | Hoàn thành tác vụ từ chọn lớp đến sinh viên mở được bài |
| OBJ02 | Sinh viên tìm đúng tài liệu theo buổi học | Đo tỷ lệ hoàn thành và thời gian tìm bài trong thử nghiệm |
| OBJ03 | Đọc thuận tiện trên máy tính và điện thoại | Kiểm tra cuộn dọc, ngang, thu phóng, tìm trang và đọc tiếp |
| OBJ04 | Hạn chế nhầm phiên bản và nhầm phạm vi chia sẻ | Kiểm thử cập nhật file, liên kết cũ và truy cập khác lớp |
| OBJ05 | Có nền tảng mở rộng tương tác học thuật | Ghi chú và câu hỏi có thể gắn đúng phiên bản và vị trí |

Các vấn đề tài liệu phân tán, khó tìm bài và nhầm phiên bản hiện là giả thuyết sản phẩm cần đo với người dùng. Tính hữu ích không được kết luận chỉ từ số lượt mở file. Hoạt động đọc cũng không chứng minh người học đã hiểu bài.

## 2 Căn cứ hiện trạng và những phần cần bổ sung

Đã đối chiếu mã nguồn theo hình thức chỉ đọc ngày 04/11/2026. Những nhận xét sau là bằng chứng từ mã và cấu hình, chưa phải kiểm chứng runtime hoặc thử nghiệm người dùng.

| Hiện trạng quan sát | Hệ quả đối với thiết kế |
|---|---|
| Frontend khai báo Next.js 16.3.8 và React 19.3.0 | Tích hợp vào ứng dụng hiện tại; kiểm tra tài liệu đúng phiên bản khi viết mã |
| API dùng FastAPI, có PostgreSQL và các kho SQLite cho từng nhóm chức năng | Cần khai báo rõ kho dữ liệu học liệu; không tự suy ra mọi dữ liệu hiện có cùng một database |
| IdentityRole hiện có STUDENT, SUPPORT_OFFICER, KNOWLEDGE_ADMIN và SYSTEM_ADMIN | Bổ sung LECTURER và quyền theo lớp; không dùng vai trò cán bộ hỗ trợ thay giảng viên |
| AppShell chưa có vai trò giao diện giảng viên hoặc mục Học liệu | Thêm menu theo capability thực tế; giữ các mục đang sử dụng |
| local-attachments lưu Blob trong IndexedDB theo thiết bị | Cần kho tệp trên máy chủ để chia sẻ giữa tài khoản và thiết bị; không chuyển các tệp cá nhân cũ một cách ngầm định |
| Frontend gọi API qua cùng điểm vào, có rewrite cho /v1 | Tải lên và đọc từng phần của PDF phải đi qua điểm vào này và được kiểm thử thực tế |
| Chưa thấy dependency trình đọc PDF trong package frontend đã đọc | Thực hiện spike PDF.js và chốt phiên bản phù hợp trước khi thêm vào lockfile |

Các tệp đã đối chiếu được liệt kê tại phần 20. Không dùng tài liệu lịch sử để tuyên bố đã có kết nối lớp học, danh sách sinh viên hoặc lịch giảng chính thức.

## 3 Phạm vi các đợt phát hành

| Đợt | Phạm vi | Kết quả nghiệm thu riêng |
|---|---|---|
| R1 | Lớp học phần, thành viên, buổi học, tải PDF, công bố, trình đọc, đọc tiếp, đánh dấu trang, quản lý phiên bản | Một giảng viên và sinh viên của lớp hoàn thành toàn bộ vòng sử dụng, dữ liệu bền vững |
| R2 | Ghi chú riêng và hỏi đáp theo trang hoặc vùng tài liệu | Đọc, ghi chú, hỏi và nhận trả lời gắn đúng phiên bản; bảo toàn riêng tư |
| R3 | Xem trước PPTX và chỉ dẫn đọc trước trong sau buổi | Giảng viên dùng file trình chiếu phổ biến và giao phạm vi đọc cụ thể |
| R4 | Tự nguyện theo trang giảng viên và hỗ trợ AI trên nội dung được chọn | Đồng bộ trang có thể rời và nhập lại; câu trả lời AI truy ngược đúng nguồn |

R1 là bản đầu được đề xuất. R2 đến R4 là phạm vi mở rộng đã có thiết kế định hướng, chưa được tính là đã triển khai hoặc đã được người dùng chủ động hoãn. Hoàn thành R1 không đồng nghĩa hoàn thành toàn bộ lộ trình.

Trong R1, hỗ trợ PDF có văn bản và PDF scan để xem hình trang. Tìm kiếm và chọn văn bản chỉ có khi tệp có lớp chữ. Chưa nhận PPTX, DOCX, video, ZIP hoặc URL nhập từ Internet vào luồng công bố R1. Giao diện phải giải thích định dạng được hỗ trợ trước khi tải lên.

Chưa nằm trong sản phẩm này: soạn và sửa nội dung PDF, chữ ký số, chấm điểm chính thức, điểm danh bằng việc mở tài liệu, hệ thống chống sao chép tuyệt đối, kho tài liệu công khai hoặc tự động thay thế LMS của trường. Đây là giới hạn thiết kế đề xuất, không phải thao tác loại bỏ chức năng đang có.

## 4 Người dùng và phân quyền

Một môn học có thể có nhiều lớp học phần, nhiều học kỳ và nhiều giảng viên. Mọi quyền đọc và quản lý phải được xét trên lớp học phần cụ thể.

**Vai trò toàn hệ thống:** bổ sung LECTURER vào định danh đáng tin cậy. SYSTEM_ADMIN quản lý việc cấp vai trò thông qua cơ chế quản trị hiện hành. Không lấy vai trò hoặc actor_id do frontend tự gửi làm căn cứ cấp quyền.

**Vai trò trong lớp:** INSTRUCTOR là giảng viên được phân công; STUDENT là sinh viên được ghi danh. Quyền toàn hệ thống LECTURER không tự cấp quyền vào mọi lớp. Một người có thể đồng thời là sinh viên ở lớp này và giảng viên ở lớp khác nếu được phân công hợp lệ.

| Hành động | Sinh viên của lớp | Giảng viên của lớp | Quản trị hệ thống | Người ngoài lớp |
|---|---|---|---|---|
| Xem thông tin và tài liệu đã công bố | Có | Có | Chỉ khi có phân công truy cập lớp | Không |
| Xem tài liệu nháp và kết quả xử lý | Không | Có | Chỉ khi được phân công | Không |
| Tạo buổi và quản lý học liệu | Không | Có | Chỉ khi được phân công | Không |
| Tạo lớp và quản lý thành viên | Không | Không ở R1 | Có qua màn hình quản trị | Không |
| Lưu vị trí đọc và đánh dấu trang của mình | Có | Có | Khi có quyền đọc lớp | Không |
| Xem vị trí đọc và ghi chú riêng của người khác | Không | Không | Không qua chức năng thông thường | Không |
| Xem câu hỏi chia sẻ với lớp ở R2 | Có | Có | Khi có quyền đọc lớp | Không |

KNOWLEDGE_ADMIN và SUPPORT_OFFICER không mặc nhiên có quyền học liệu. Giảng viên có thể đồng giảng một lớp; việc phân công phải có bản ghi có thể kiểm tra.

R1 cung cấp màn hình quản trị tối thiểu để tạo lớp, chọn tài khoản đã có và phân công thành viên. Môi trường local sử dụng tài khoản tổng hợp riêng, không đổi vai trò của tài khoản cũ để tiện kiểm thử. Chưa có SSO hay danh sách chính thức không cản trở triển khai local bằng dữ liệu tổng hợp.

## 5 Cấu trúc nội dung và quy tắc nghiệp vụ

Cấu trúc chính: **Học kỳ → Môn học → Lớp học phần → Buổi học → Học liệu → Phiên bản → Trang**.

- Học kỳ có tên, ngày bắt đầu và kết thúc; lớp có mã hiển thị, môn, học kỳ và múi giờ.
- Buổi có thứ tự, tiêu đề, mô tả và thời điểm dự kiến tùy chọn. Không bắt buộc có lịch trường để tạo buổi.
- Một buổi có nhiều học liệu. Một học liệu trong cùng lớp có thể liên kết với nhiều buổi qua SessionMaterial; không sao chép file khi chỉ dùng lại bài.
- Không chia sẻ cùng bản ghi học liệu giữa hai lớp ở R1. Sao chép sang lớp khác là một luồng riêng ở giai đoạn sau, phải có quyền ở cả hai đầu.
- Tiêu đề hiển thị khác tên file gốc; tên file gốc chỉ là metadata và phải được escape khi hiển thị.
- Mỗi học liệu có chuỗi phiên bản bất biến. Chỉnh tiêu đề không làm thay đổi byte của phiên bản; tải file mới luôn tạo phiên bản mới.
- Lớp ACTIVE cho phép quản lý theo quyền. Lớp ARCHIVED cho phép thành viên hiện hành đọc nội dung đã công bố, không tạo hoặc công bố bài mới.
- R1 không có API xóa vĩnh viễn tệp hoặc bản ghi. Ẩn học liệu, hủy lịch công bố hoặc lưu trữ lớp là các chuyển trạng thái giữ nguyên dữ liệu, có xem trước và xác nhận.

## 6 Luồng sử dụng và màn hình

### 6.1 Giảng viên đăng bài

1. Mở Học liệu và chọn một lớp được phân công.
2. Chọn buổi hoặc tạo buổi với tiêu đề và thứ tự. Có thể điều chỉnh ngày mà không làm mất liên kết học liệu.
3. Chọn Tải tài liệu, đặt tiêu đề, loại tài liệu chính hoặc bổ sung và chọn PDF.
4. Hiển thị dung lượng, trạng thái tải và lỗi có hướng khắc phục. Có thể hủy trước khi công bố; dữ liệu nhận dở không được hiển thị cho sinh viên.
5. Khi xử lý xong, giảng viên xem trước bằng chính trình đọc sẽ cung cấp cho sinh viên.
6. Lưu nháp, công bố ngay hoặc đặt lịch. Công bố có bản xem trước nêu lớp, buổi, tên bài, phiên bản và thời điểm rồi xác nhận một lần.
7. Kết quả chỉ báo thành công sau khi server xác nhận. Mở lại trang hoặc từ thiết bị khác phải thấy đúng trạng thái đã lưu.

### 6.2 Sinh viên đọc bài

1. Học liệu hiển thị các lớp được tham gia, học kỳ và buổi gần nhất có bài được công bố.
2. Mở buổi sẽ thấy tài liệu chính trước, tài liệu bổ sung sau; có nhãn mới hoặc cập nhật và thời gian công bố.
3. Chọn tài liệu sẽ mở trình đọc trong cùng ứng dụng. Hiển thị ngay ngữ cảnh lớp, buổi, tên bài và phiên bản.
4. Đọc dọc, ngang hoặc từng trang; điều hướng, tìm văn bản, thu phóng và đánh dấu trang.
5. Rời trang rồi quay lại sẽ khôi phục vị trí đọc đã lưu cho đúng phiên bản; một vị trí có thể xuất hiện ở nhiều buổi nhưng vẫn thuộc cùng học liệu.

### 6.3 Cập nhật bài giảng

Giảng viên tải phiên bản tiếp theo, chờ kiểm tra, xem trước rồi chọn công bố. Trong lúc đó sinh viên vẫn xem phiên bản đang công bố. Chỉ đổi current_published_version_id sau khi giao dịch công bố thành công. Sinh viên đang đọc nhận thông báo có bản mới và tự chọn mở; không tự thay trang đang xem.

Liên kết, đánh dấu và ghi chú cũ vẫn tham chiếu bản cũ nếu phiên bản đó còn được công bố trong lịch sử và người đọc còn quyền vào lớp. Bản bị thu hồi không còn được đọc kể cả qua liên kết cũ. Không tự chuyển ghi chú sang bản mới dựa vào số trang.

### 6.4 Bố cục đề xuất

| Màn hình | Nội dung và hành động chính |
|---|---|
| Danh sách lớp | Lớp, học kỳ, vai trò trong lớp; chọn lớp, tìm lớp trong phạm vi được truy cập |
| Chi tiết lớp | Danh sách buổi theo thứ tự; tìm tài liệu; giảng viên có thao tác tạo buổi |
| Chi tiết buổi | Chủ đề, ngày dự kiến, danh sách học liệu, trạng thái công bố theo quyền |
| Đăng và cập nhật học liệu | Tiêu đề, file, buổi liên kết, tiến trình, xem trước, nháp và công bố |
| Trình đọc | Tài liệu ở giữa, điều hướng bên trái có thể thu gọn; R2 mở ghi chú hoặc hỏi đáp bên phải |
| Quản trị lớp | Tạo lớp, tìm tài khoản hợp lệ, phân công giảng viên, thêm và ngưng ghi danh sinh viên |

Desktop từ 1024px có thể bố trí danh sách buổi và ảnh trang bên trái. Tablet thu gọn điều hướng mặc định. Điện thoại 360px trở lên ưu tiên bề rộng tài liệu, dùng bảng mở tạm cho danh sách trang và ghi chú; không làm cả trang web bị cuộn ngang. Phần nội dung PDF được phép cuộn ngang khi chọn chế độ ngang hoặc phóng lớn.

Trạng thái bắt buộc: chưa có lớp, lớp chưa có buổi, buổi chưa có tài liệu, chưa công bố, đang tải, đang kiểm tra, xử lý thất bại, mất mạng, phiên đăng nhập hết hạn, đã mất quyền và có phiên bản mới. Mỗi trạng thái có thông báo và hành động phù hợp, không thay bằng dữ liệu mẫu như thể là dữ liệu thật.

## 7 Đặc tả trình đọc R1

| Mã | Yêu cầu | Điều kiện nghiệm thu |
|---|---|---|
| VIEW01 | Cuộn dọc liên tục | Các trang xếp theo chiều dọc; chỉ render vùng cần thiết; đi được từ đầu tới cuối |
| VIEW02 | Cuộn ngang liên tục | Các trang xếp theo chiều ngang; thao tác chạm và thanh cuộn hoạt động; đổi chế độ giữ trang hiện hành |
| VIEW03 | Xem từng trang | Có nút trước sau và nhập số trang; không vượt trang đầu hoặc cuối |
| VIEW04 | Thu phóng | Nút tăng giảm, các mức 50 đến 300 phần trăm, vừa trang và vừa chiều rộng; phóng lớn có thể kéo để xem |
| VIEW05 | Điều hướng nhanh | Ảnh thu nhỏ, số trang trên tổng trang, mục lục PDF nếu có; số trang hợp lệ là 1 đến page_count |
| VIEW06 | Chữ và tìm kiếm | Có text layer để chọn và sao chép; tìm và chuyển giữa kết quả khi PDF có văn bản |
| VIEW07 | Đọc tập trung | Thu gọn các vùng bên; fullscreen khi trình duyệt hỗ trợ, có chế độ tập trung dự phòng |
| VIEW08 | Cảm ứng | Pinch zoom trong trình đọc trên thiết bị hỗ trợ; giữ browser zoom và các nút tương đương; không chặn phóng to toàn trình duyệt |
| VIEW09 | Đọc tiếp | Lưu trang, vị trí tương đối, hướng cuộn, zoom và góc xoay riêng cho tài khoản và phiên bản |
| VIEW10 | Đánh dấu trang | Đặt nhãn tùy chọn, mở lại đúng phiên bản và số trang; đánh dấu của người khác không xuất hiện |
| VIEW11 | Xoay trang xem | Xoay 0, 90, 180 hoặc 270 độ ở lớp hiển thị; không sửa byte của file gốc |
| VIEW12 | Tải bản gốc | Có khi lớp cho phép; không coi việc ẩn nút tải là cơ chế chống sao chép tuyệt đối |

Mặc định lần mở đầu: cuộn dọc và vừa chiều rộng; PDF trình chiếu có thể được người đọc đổi sang từng trang và vừa trang. Giữ lựa chọn theo phiên bản đã đọc, không ép đổi theo lựa chọn của người khác.

Các nút có nhãn hỗ trợ đọc màn hình, trạng thái focus rõ và cách dùng bàn phím. Khi focus trong trường nhập hoặc trình soạn ghi chú, phím tắt của trình đọc không giành thao tác nhập. Khả năng thao tác bằng bàn phím theo định hướng của [W3C WCAG 2.2 mục Keyboard](https://www.w3.org/WAI/WCAG22/Understanding/keyboard.html).

page_no là thứ tự vật lý 1-based của trang trong file. Nếu PDF có nhãn trang riêng như số La Mã hoặc số trang in khác thứ tự vật lý, UI có thể hiển thị thêm nhãn nhưng link, anchor và kiểm tra phạm vi vẫn dùng page_no. Tìm kiếm tiếng Việt, chữ có dấu và từ ngắt dòng phải được kiểm trên bộ PDF đại diện; không khẳng định hỗ trợ mọi kiểu mã hóa font.

PDF scan vẫn xem được nhưng hiển thị thông báo không có văn bản để tìm hoặc chọn. Khả năng đọc màn hình còn phụ thuộc cấu trúc PDF nguồn; không tuyên bố mọi tài liệu scan hoặc canvas đều đã hỗ trợ đầy đủ. R1 không cam kết OCR; có thể cung cấp tài liệu chữ bổ sung khi cần.

## 8 Yêu cầu nghiệp vụ và tiêu chí chấp nhận

| Mã | Yêu cầu | Bằng chứng tối thiểu |
|---|---|---|
| FR01 | Quản trị tạo học kỳ, môn và lớp | Tạo, đọc lại và kiểm tra dữ liệu hợp lệ sau restart |
| FR02 | Phân công giảng viên và ghi danh sinh viên | Ma trận quyền, tài khoản khác lớp bị chặn ở API |
| FR03 | Giảng viên quản lý thứ tự và thông tin buổi | Đổi thứ tự không đổi ID và không làm mất học liệu |
| FR04 | Một buổi nhiều bài và dùng lại bài trong cùng lớp | Không nhân bản blob khi thêm liên kết buổi |
| FR05 | Tải và xử lý PDF có giới hạn | Tệp hợp lệ READY, tệp lỗi không thể công bố |
| FR06 | Nháp, xem trước, công bố và hẹn giờ | Sinh viên không đọc được byte trước thời điểm công bố |
| FR07 | Thu hồi hoặc ẩn có xác nhận và lưu lịch sử | Liên kết cũ bị từ chối khi không còn quyền công bố |
| FR08 | Đầy đủ VIEW01 đến VIEW12 | Ca trình duyệt và thiết bị thật phù hợp |
| FR09 | Đọc tiếp và đánh dấu theo người và phiên bản | Đọc lại trên phiên mới và thiết bị khác |
| FR10 | Tải phiên bản mới không ghi đè cũ | Hash cũ giữ nguyên, publication chuyển một lần |
| FR11 | Thông báo bản mới trong ứng dụng | Lưu thông báo bền vững, không cần email hoặc push ngoài hệ thống |
| FR12 | Hành động quản lý có nhật ký | Ai làm gì trên lớp và phiên bản nào; không chứa token hoặc nội dung bài |
| FR13 | Trạng thái lỗi và khả năng thử lại | Mất mạng, retry, restart không tạo bản công bố trùng |
| FR14 | Không làm mất chức năng hiện hành | Kiểm tra đăng nhập, chat, dịch vụ và trang học liệu cùng điểm vào |

FR và VIEW là tiêu chí của R1. Các yêu cầu mở rộng có mã EXT ở phần 15. Mọi báo cáo phải nêu rõ phạm vi mã đã được kiểm chứng.

## 9 Kiến trúc tích hợp

Luồng dữ liệu: trình duyệt → điểm vào Campus hiện hành → API học liệu → service nghiệp vụ → repository metadata và kho blob riêng. Worker nhận công việc kiểm tra tệp và tạo metadata. Trình đọc tải PDF từ API được bảo vệ, không đọc trực tiếp đường dẫn lưu trữ.

**Frontend:** dùng PDF.js làm nền tảng. Ưu tiên tái sử dụng các thành phần viewer và tùy biến phù hợp ứng dụng, tránh tự viết lại bộ giải mã PDF. Spike phải xác nhận tương thích Next.js, worker, font, text layer, hướng cuộn, mobile và CSP. Pin dependency và worker cùng phiên bản; không dùng URL CDN latest. Quyết định dùng wrapper chỉ được đưa ra khi chứng minh nó không cản VIEW01 đến VIEW12. [PDF.js Getting Started](https://mozilla.github.io/pdf.js/getting_started/).

**Backend:** thêm module learning theo các lớp domain, application, ports, infrastructure và presentation. Route chỉ xử lý HTTP, chuyển identity đáng tin cậy và gọi service. Quyền, vòng đời công bố, quota và bất biến phiên bản nằm trong service hoặc domain.

**Metadata:** đề xuất PostgreSQL cho module học liệu, với schema learning và migration bổ sung. Giữ nguyên các kho SQLite hiện hành của những chức năng khác. Module nhận repository qua composition; không lặng lẽ fallback sang bộ nhớ hoặc tạo một kho mới khi kho cấu hình lỗi. Trước migration phải xác minh đúng database local và đọc schema thực tế.

**Blob R1:** dùng thư mục riêng trong workspace triển khai đã được xác minh, nằm ngoài thư mục public của frontend. Khóa blob do server tạo bằng ID bất biến; file ghi mới, không thay file cũ. Tách port để sau này dùng object storage mà không đổi mô hình nghiệp vụ. Không đưa byte PDF vào bảng metadata hoặc localStorage.

**Worker và lịch:** dùng hàng đợi bền vững hoặc bảng job với khóa nhận việc và lease; tận dụng worker hiện có sau khi kiểm tra cách khởi động. Job phải idempotent, có attempt, deadline, lỗi cuối và khả năng retry được giới hạn. Lịch công bố chạy theo UTC, giao diện hiển thị múi giờ lớp. Quyền giảng viên và tình trạng lớp được kiểm lại tại thời điểm job công bố.

**Thông báo:** ghi outbox cùng transaction công bố; worker tạo thông báo cho thành viên lớp theo khóa chống trùng. R1 hiển thị inbox trong học liệu và badge khi mở danh sách; không gửi email, tin nhắn hay thông báo dịch vụ ngoài.

**RAG:** học liệu riêng không tự nhập vào kho tri thức công khai hoặc release học vụ hiện có. R4 dùng tập truy hồi theo lớp và phiên bản, kiểm quyền tại mỗi lần hỏi và mở nguồn.

## 10 Mô hình dữ liệu đề xuất

Các ID là UUID theo quy ước hiện hành của ứng dụng; timestamp lưu UTC. Mọi bảng nghiệp vụ có created_at, updated_at và revision khi có chỉnh sửa. Các quan hệ không được vượt qua institution_id và course_offering_id. Không tạo khóa ngoại đến bảng người dùng chưa xác minh; actor_subject_id tham chiếu chủ thể của hệ thống danh tính hiện hành.

| Thực thể | Trường chính ngoài ID | Bất biến hoặc chỉ mục quan trọng |
|---|---|---|
| AcademicTerm | institution_id, name, start_date, end_date, timezone | Ngày kết thúc không trước ngày bắt đầu |
| Course | institution_id, code, name | Unique institution_id và code |
| CourseOffering | course_id, term_id, section_code, status, download_allowed | Unique môn học kỳ mã lớp; ACTIVE hoặc ARCHIVED |
| OfferingMember | offering_id, actor_subject_id, role, status, assigned_by | Unique lớp chủ thể vai trò; trạng thái ACTIVE hoặc INACTIVE |
| ClassSession | offering_id, sequence_no, title, description, starts_at | Unique lớp và thứ tự; ID không đổi khi sắp xếp |
| LearningMaterial | offering_id, title, description, current_published_version_id, visibility | Pointer chỉ tới phiên bản READY đã công bố thuộc chính học liệu |
| SessionMaterial | session_id, material_id, sort_order, kind | Cùng lớp; unique buổi và học liệu; kind PRIMARY hoặc SUPPLEMENT |
| MaterialVersion | material_id, version_no, blob_id, processing_state, publication_state, published_at | Unique học liệu và version_no; byte và hash bất biến |
| BlobObject | storage_key, sha256, byte_size, detected_mime, page_count, scan_status | Key do server tạo; không lộ path; checksum kiểm từ server |
| UploadIntent | actor_id, offering_id, material_id, declared_size, state, expires_at | Có idempotency key; chỉ chủ intent có quyền tải tiếp |
| ReaderState | actor_id, version_id, page_no, offset_x, offset_y, zoom_mode, zoom_value, rotation, scroll_mode | Unique chủ thể và phiên bản; vị trí chuẩn hóa 0 đến 1 |
| Bookmark | actor_id, version_id, page_no, label, status | Thuộc người tạo; status ACTIVE hoặc ARCHIVED |
| ScheduledPublication | version_id, scheduled_at, requested_by, state, revision | Một lịch hoạt động trên phiên bản; hủy lịch giữ bản ghi |
| LearningJob | type, resource_id, state, attempt, lease_until, last_error_code | Khóa chống xử lý trùng và khôi phục sau restart |
| OutboxEvent | event_type, aggregate_id, revision, payload_allowlist, delivered_at | Unique aggregate revision event_type |
| LearningNotification | recipient_id, event_id, offering_id, material_id, read_at | Unique recipient và event; chỉ người nhận đọc được |
| LearningAuditEvent | actor_id, action, offering_id, resource_id, outcome, request_id | Append only; không lưu token hoặc toàn văn tài liệu |

R2 bổ sung Annotation, QuestionThread và QuestionReply. Annotation có owner_id, version_id, page_no, anchor, body và revision. Anchor gồm loại PAGE hoặc TEXT hoặc REGION, tọa độ chuẩn hóa, góc xoay chuẩn và text_quote với prefix, suffix nếu có; giới hạn chiều dài trích dẫn. Thread có visibility CLASS hoặc PRIVATE_TO_INSTRUCTORS; reply có tác giả, revision và trạng thái giảng viên xác nhận nếu tác giả có quyền hiện hành.

Việc lọc theo lớp phải được thực hiện ngay trong truy vấn repository, không tải toàn bộ rồi lọc tại UI. Composite foreign key hoặc kiểm tra transaction phải ngăn SessionMaterial và current_published_version_id trỏ sang lớp khác. Đổi thứ tự nhiều buổi dùng một transaction để không vi phạm unique trung gian.

Không deduplicate blob giữa các lớp ở R1. Hash dùng để kiểm toàn vẹn và phát hiện việc tải trùng trong phạm vi được phép, không trả thông tin file đã tồn tại ở lớp khác.

## 11 Vòng đời xử lý và công bố

Tách trạng thái xử lý khỏi trạng thái công bố để tránh hiểu READY là sinh viên đã xem được.

| Nhóm | Trạng thái | Ý nghĩa |
|---|---|---|
| Upload | CREATED, RECEIVING, RECEIVED, ABORTED, EXPIRED | Intent và lượng byte đã nhận; ABORTED hoặc EXPIRED không đồng nghĩa xóa tệp |
| Xử lý phiên bản | QUEUED, VALIDATING, SCANNING, EXTRACTING, READY, REJECTED, FAILED | Chỉ READY được xét công bố |
| Công bố | DRAFT, SCHEDULED, PUBLISHED, RETRACTED | Chỉ PUBLISHED được sinh viên có quyền lớp đọc |
| Hiển thị học liệu | VISIBLE, HIDDEN | HIDDEN chặn đọc cho sinh viên, giữ lịch sử và file |

Đường đi bình thường: tạo intent → nhận byte → hoàn tất upload → tạo version và job → kiểm file → READY và DRAFT → preview → xác nhận công bố → PUBLISHED. Preview cho giảng viên vẫn phải kiểm quyền lớp.

Khi công bố bản mới: khóa hoặc kiểm revision của LearningMaterial, kiểm READY và quyền hiện hành, đặt bản mới thành PUBLISHED, chuyển current pointer và ghi outbox cùng transaction. Bản trước vẫn là PUBLISHED trong lịch sử, trừ khi giảng viên thu hồi riêng. Không dùng SUPERSEDED như một quyền đọc ngầm định.

Khi thu hồi bản hiện hành: hiển thị xem trước tác động và cho phép chọn một bản PUBLISHED khác làm hiện hành hoặc để học liệu tạm không có bản hiện hành. Bản RETRACTED bị chặn tại mọi endpoint đọc, preview cho giảng viên có quyền vẫn được phép để xử lý. Bản được công bố trở lại phải đi qua luồng xác nhận và nhật ký mới.

Nếu tiến trình chết giữa ghi blob và commit metadata, giữ blob tại trạng thái chưa gắn đủ metadata và ghi nhận để đối soát; không tự dọn hoặc xóa. Worker có thể tiếp tục từ checksum đã xác minh; job không phát hành lại thông báo cho cùng revision.

## 12 API đề xuất

Tiền tố chức năng là /v1/learning. Đây là hợp đồng đề xuất, chưa tồn tại chỉ vì xuất hiện trong tài liệu. Hợp đồng triển khai phải bổ sung vào OpenAPI hiện có và giữ tương thích các route cũ.

JSON dùng snake_case, từ chối thuộc tính lạ; lỗi dạng application/problem+json và có request_id. Danh sách phân trang bằng opaque cursor, limit mặc định 20, tối đa 100. Request đọc không làm thay đổi trạng thái công bố.

| Phương thức và đường dẫn dưới /v1/learning | Mục đích | Quyền |
|---|---|---|
| GET /capabilities | Khả năng khả dụng và giới hạn được phép hiển thị | Tài khoản hợp lệ |
| GET /offerings | Danh sách lớp của mình | Thành viên hiện hành |
| GET và POST /terms; GET và POST /courses | Đọc danh mục để quản trị hoặc tạo học kỳ và môn | SYSTEM_ADMIN |
| GET /admin/offerings | Liệt kê lớp để quản trị, chỉ metadata | SYSTEM_ADMIN, không cấp quyền đọc file |
| GET /admin/eligible-actors | Tìm tài khoản đã có để phân công, dữ liệu tối thiểu và phân trang | SYSTEM_ADMIN |
| POST /action-previews | Tóm tắt thao tác quản trị, thay đổi metadata hoặc quyền trước khi xác nhận | Người có quyền thực hiện thao tác |
| POST /offerings | Tạo lớp học phần | SYSTEM_ADMIN |
| GET /offerings/{offering_id} | Chi tiết lớp và quyền của mình | Thành viên lớp |
| GET /offerings/{offering_id}/members | Danh sách thành viên để quản trị | SYSTEM_ADMIN hoặc giảng viên của lớp theo dữ liệu tối thiểu |
| POST /offerings/{offering_id}/members | Thêm hoặc phân công tài khoản đã có | SYSTEM_ADMIN |
| PATCH /offerings/{offering_id}/members/{member_id} | Ngưng hoặc khôi phục phân công | SYSTEM_ADMIN và xác nhận tác động |
| POST /offerings/{offering_id}/archive | Lưu trữ lớp có xem trước và xác nhận | SYSTEM_ADMIN |
| GET và POST /offerings/{offering_id}/sessions | Đọc danh sách và tạo buổi | Đọc là thành viên; tạo là giảng viên lớp |
| PATCH /sessions/{session_id} | Đổi chủ đề hoặc ngày | Giảng viên lớp |
| PUT /offerings/{offering_id}/session-order | Cập nhật thứ tự toàn bộ buổi bằng danh sách ID | Giảng viên lớp |
| GET /sessions/{session_id}/materials | Học liệu theo quyền và trạng thái | Thành viên lớp |
| POST /offerings/{offering_id}/materials | Tạo metadata học liệu nháp | Giảng viên lớp |
| GET /materials/{material_id} | Metadata học liệu và phiên bản hiện hành theo quyền | Thành viên được phép đọc học liệu |
| PATCH /materials/{material_id} | Sửa metadata hoặc ẩn bằng xác nhận | Giảng viên lớp |
| PUT /sessions/{session_id}/material-links | Thêm hoặc sắp xếp liên kết trong cùng lớp | Giảng viên lớp |
| POST /materials/{material_id}/upload-intents | Tạo intent cho một phiên bản mới | Giảng viên lớp |
| PUT /upload-intents/{upload_id}/content | Stream một file vào intent | Chủ intent còn quyền giảng viên lớp |
| POST /upload-intents/{upload_id}/complete | Kiểm byte nhận và xếp job | Chủ intent |
| POST /upload-intents/{upload_id}/abort | Dừng nhận mà giữ dấu vết | Chủ intent |
| GET /upload-intents/{upload_id} | Tiến trình và lỗi an toàn | Chủ intent hoặc giảng viên được phép |
| GET /materials/{material_id}/versions | Lịch sử được phép xem | Giảng viên thấy đủ; sinh viên chỉ thấy bản công bố |
| GET /versions/{version_id} | Metadata viewer và capability | Thành viên được phép đọc phiên bản |
| POST /versions/{version_id}/publication-preview | Lấy nội dung xem trước và token xác nhận | Giảng viên lớp |
| POST /versions/{version_id}/publish | Công bố ngay hoặc hẹn giờ | Giảng viên lớp, token xác nhận còn hiệu lực |
| POST /versions/{version_id}/cancel-publication | Hủy lịch và giữ bản nháp | Giảng viên lớp, xác nhận |
| POST /versions/{version_id}/retract | Thu hồi và xử lý current pointer | Giảng viên lớp, xác nhận |
| GET và HEAD /versions/{version_id}/content | Đọc PDF hoặc preview nháp theo quyền | Quyền đọc được kiểm lại mỗi request |
| GET /versions/{version_id}/download | Tải bản gốc khi được phép | Quyền đọc và download_allowed |
| GET và PUT /me/reader-state/{version_id} | Đọc và lưu trạng thái của mình | Chính người đọc có quyền phiên bản |
| GET và POST /me/bookmarks | Đọc hoặc thêm đánh dấu của mình | Chính người đọc, lọc quyền phiên bản |
| PATCH /me/bookmarks/{bookmark_id} | Sửa nhãn hoặc lưu trữ đánh dấu | Chủ đánh dấu |
| GET /me/notifications và PATCH /me/notifications/{id} | Danh sách và đánh dấu đã xem | Chính người nhận |

Quản trị tạo và phân công lớp có bản tóm tắt trước khi ghi; tận dụng cơ chế xác nhận hiện hành nếu tương thích. Những thay đổi có tác động như ẩn bài, ngưng ghi danh, lưu trữ và thu hồi cần nêu rõ ai mất quyền xem. action-previews nhận action, target và payload đề xuất, kiểm quyền rồi trả diff tối thiểu cùng token ràng buộc revision; không nhận actor đáng tin từ client. Người dùng sửa payload sau preview phải tạo preview mới.

POST tạo tài nguyên, hoàn tất upload và công bố dùng Idempotency-Key theo actor và operation. Cùng key cùng payload trả kết quả đã có; cùng key khác payload trả 409. PATCH hoặc PUT có thay đổi cạnh tranh dùng revision hoặc If-Match; sai revision trả 409. Token xác nhận gắn actor, phạm vi, version nếu có, action, payload hash và thời hạn; backend kiểm lại quyền tại bước ghi. Với xác thực bằng cookie, các request ghi phải qua kiểm Origin và cơ chế CSRF phù hợp của ứng dụng; không coi token xác nhận nghiệp vụ là biện pháp thay thế CSRF.

Kết quả danh sách, tìm kiếm, số lượng, thông báo và capability đều phải được lọc theo quyền hiện hành. Thông báo của lớp đã mất quyền có thể giữ trong kho nhật ký nhưng không trả tiêu đề hoặc trích đoạn tài liệu cho tài khoản đó. Không dùng admin/eligible-actors để mở danh bạ ngoài nhu cầu phân công lớp.

Ví dụ cấu trúc metadata reader:

```json
{
  "material_id": "<uuid>",
  "version_id": "<uuid>",
  "version_no": 2,
  "title": "Buổi 3 Phép nối trong SQL",
  "page_count": 48,
  "has_text_layer": true,
  "content_path": "/v1/learning/versions/<uuid>/content",
  "capabilities": {
    "read": true,
    "download": false,
    "manage": false
  },
  "revision": 3
}
```

Các giá trị <uuid> chỉ minh họa, không phải fixture hợp lệ. Không trả storage_key, đường dẫn máy chủ hoặc URL chứa token. Nội dung response phải được lọc theo quyền hiện hành, không chỉ theo capability do lần đọc trước trả về.

Mã lỗi cần đặc tả: 401 chưa đăng nhập; 404 tài nguyên không tồn tại hoặc bị che do ngoài phạm vi; 403 thao tác không được phép trên lớp đã được quyền biết; 409 xung đột revision hoặc trạng thái; 413 vượt dung lượng; 415 loại file không hỗ trợ; 422 metadata hoặc PDF không hợp lệ; 429 vượt hạn mức; 503 kho dữ liệu, scanner hoặc storage chưa sẵn sàng. UI giữ bản nhập chưa gửi khi có thể, không tự báo thành công khi kết quả chưa rõ.

### 12.1 Truyền PDF và Range

Endpoint content hỗ trợ GET, HEAD và một byte range hợp lệ trên GET, trả 206 với Content-Range và Content-Length đúng. Request GET không có Range trả 200. Range không thỏa mãn trả 416 với Content-Range dạng bytes */total. Range nhiều đoạn có thể được bỏ qua và trả toàn bộ 200 theo hợp đồng R1, không tự triển khai ghép multipart tùy tiện. Kiểm ETag theo blob bất biến; If-Range không khớp trả toàn bộ 200. HEAD trả metadata toàn tài liệu, không có body và bỏ qua Range.

Gửi Accept-Ranges: bytes, Content-Type: application/pdf, X-Content-Type-Options: nosniff và Content-Disposition được mã hóa an toàn. R1 dùng Cache-Control: private, no-store; không dùng shared cache hoặc service worker lưu tệp riêng. Vẫn kiểm quyền với từng Range; khi mất quyền, dừng cấp byte mới và xóa trang khỏi viewer sau khi phát hiện, dù không thể thu hồi byte đã được tải trước đó.

Phải kiểm bằng đường vào thực tế của Campus, vì proxy có thể làm mất Range, HEAD, cookie hoặc header. Không coi việc endpoint chạy trực tiếp trên backend là đã đạt nghiệm thu tích hợp.

## 13 Tệp tải lên và tính toàn vẹn

| Tham số R1 đề xuất | Giá trị khởi đầu | Cách xử lý |
|---|---|---|
| Định dạng nhận | PDF | Kiểm phần mở rộng, MIME phát hiện, chữ ký và khả năng parse |
| Dung lượng mỗi file | 50 MiB | Stream và đếm byte thực; chặn trước và trong upload |
| Số trang | 500 | Tính sau parse; vượt giới hạn thì không công bố |
| Tổng dung lượng mỗi lớp | 2 GiB | Kiểm quota phía server, tính cả phiên bản được giữ |
| Intent chưa hoàn tất | 30 phút | Hết hạn nghiệp vụ, giữ file nhận dở để đối soát |
| Upload đồng thời mỗi giảng viên | 2 | Giới hạn bộ nhớ, I/O và quota đang được giữ chỗ |
| Thời hạn xử lý một job | 120 giây | Timeout có mã lỗi; retry có giới hạn và lease |
| Tốc độ lưu trạng thái đọc | Tối đa một lần mỗi 5 giây mỗi tab | Flush khi rời trang nếu có thể; UI nêu khi chưa đồng bộ |

Đây là giới hạn sản phẩm đề xuất, không phải giới hạn cố định của PDF.js. Spike đo lại bằng bộ tài liệu đại diện và ghi rõ nếu điều chỉnh. Hạn mức tổng dung lượng host phải được cấu hình trước khi bật tải lên; không tự xóa dữ liệu để lấy chỗ.

R1 không cam kết tiếp tục upload từ một byte offset sau mất mạng. Mỗi intent chỉ nhận một lượt stream độc quyền. Nếu kết quả request chưa rõ, client hỏi trạng thái intent trước; nếu stream đã hỏng thì tạo intent mới và tải lại, không ghi đè tệp nhận dở. Byte thực của file dở, bị từ chối và phiên bản cũ vẫn được tính vào sức chứa host; quota giữ chỗ và quota đã dùng phải tránh giải phóng giả khi dữ liệu vẫn còn trên đĩa.

Pipeline phải xác minh quyền trước khi nhận byte, tạo tên lưu do server quyết định, kiểm dung lượng thực, kiểm tra PDF, quét nội dung bằng scanner đã cấu hình và cô lập phần parse. Không tin filename, Content-Type từ client hoặc checksum do client khai báo. Các nguyên tắc tải tệp này tham khảo [OWASP File Upload Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html); cách áp dụng cụ thể do service học liệu kiểm soát.

PDF có mật khẩu hoặc mã hóa, file hỏng, tệp sai định dạng và file bị scanner từ chối không được công bố. Không thực thi PDF JavaScript, tự mở tệp nhúng, launch action hoặc tự truy cập URL bên ngoài. Liên kết web có thể hiển thị để người dùng chủ động mở với cảnh báo điều hướng phù hợp; không dùng liên kết trong file làm lệnh cho worker hoặc AI.

Scanner lỗi hoặc chưa có kết quả thì phiên bản chưa READY. Kiểm thử tổng hợp có thể dùng fake scanner để xác minh state machine, nhưng phải ghi rõ bằng chứng đó không xác nhận phát hiện mã độc thật. Tiếp nhận tệp ngoài fixture cần scanner thực hoạt động; việc thiếu scanner không chặn xây UI, model, API hoặc kiểm thử độc lập.

Kho blob phải kiểm canonical path, không theo reparse point chưa xác minh, không dùng filename client làm đường dẫn. Tệp nhận mới dùng thao tác tạo không ghi đè; hash được tính khi stream và kiểm lại khi hoàn tất. Không phát sinh API xóa hoặc job dọn rác trong phạm vi này. Quota đầy thì dừng nhận thêm và báo quản trị.

## 14 Lưu vị trí đọc và phiên bản

ReaderState lưu riêng theo actor và version, không theo buổi để tránh ghi hai vị trí khác nhau cho cùng tài liệu dùng lại. Trạng thái gồm trang 1-based, offset chuẩn hóa, scroll_mode, zoom_mode hoặc zoom_value và rotation. Các giá trị phải được giới hạn theo metadata server.

Lưu có debounce, có session/tab ID và sequence. Backend dùng revision để tránh request cũ tới chậm ghi đè request mới. Khi hai thiết bị cùng đọc, client nhận conflict và hỏi chọn vị trí trên thiết bị hoặc vị trí đã đồng bộ; không giả định trang lớn hơn là vị trí đúng hơn.

Khi mạng mất, giữ vị trí trong bộ nhớ của tab và báo Chưa đồng bộ. Có thể lưu metadata vị trí tạm theo tài khoản trên thiết bị nếu phù hợp cơ chế hiện hành, nhưng không lưu byte PDF hoặc trích đoạn riêng trong cache chung. Khi đổi tài khoản phải tách hoặc xóa khỏi bộ nhớ UI các trạng thái tài khoản cũ, không được hiển thị chéo.

Liên kết sâu chứa version_id, page_no và anchor tùy chọn; mỗi lần mở đều kiểm quyền. Nếu bản cũ còn được công bố thì hiển thị nhãn phiên bản cũ và đường chuyển bản mới. Nếu bản bị thu hồi thì nêu tài liệu không còn được cung cấp, không tự mở một bản khác như thể cùng nguồn.

## 15 Thiết kế các mở rộng

### 15.1 EXT01 Ghi chú và bôi sáng riêng

Đợt R2. Cho phép ghi chú trang, bôi sáng văn bản và ghi chú vùng đối với hình hoặc công thức. Ghi chú riêng chỉ chủ sở hữu đọc được; chia sẻ một ghi chú phải là hành động riêng có xem trước. Lưu anchor theo hệ tọa độ chuẩn của trang và version_id; khi xoay hoặc zoom, viewer biến đổi tọa độ để vẽ lại.

API định hướng: GET và POST /me/annotations, PATCH /me/annotations/{id}; trường status dùng ARCHIVED để giữ dữ liệu. Sửa dùng revision. Tiêu chí đạt: ghi chú còn đúng sau đổi zoom, xoay, chuyển thiết bị và thêm phiên bản; người khác không đọc được cả qua API; không sửa byte PDF gốc.

### 15.2 EXT02 Hỏi đáp tại trang hoặc vùng

Đợt R2. Người học chọn trang, đoạn hoặc vùng rồi đặt câu hỏi. CLASS cho thành viên lớp xem; PRIVATE_TO_INSTRUCTORS chỉ người hỏi và giảng viên hiện hành của lớp đọc. Giảng viên không mặc nhiên xem ghi chú riêng. Chuyển câu hỏi riêng thành câu hỏi chung cần chính người hỏi xác nhận và xem trước nội dung chia sẻ.

API định hướng: GET và POST /versions/{id}/questions; POST /questions/{id}/replies; PATCH /questions/{id}; POST /replies/{id}/endorse. Nội dung được xử lý như văn bản hoặc Markdown được sanitize; không nhận HTML chạy script. Xác nhận của giảng viên là trạng thái riêng, không tự gắn cho câu trả lời AI.

Tiêu chí đạt: mở câu hỏi đưa tới đúng nguồn; trả lời và trạng thái được lưu bền vững; mất phân công giảng viên thì mất quyền câu hỏi riêng; thông báo chỉ đến người có quyền, không chứa trích đoạn riêng ở danh sách ngoài phạm vi.

### 15.3 EXT03 Xem trước PowerPoint

Đợt R3. Nhận PPTX, lưu bản gốc và tạo PDF rendition bằng converter local đã chọn qua spike. Bản gốc và rendition là hai blob bất biến liên kết cùng MaterialVersion, có hash và phiên bản converter. Ghi chú neo vào rendition_id; tạo rendition khác không được âm thầm đổi nguồn neo.

Converter chạy cô lập, không mạng, không chạy macro hoặc tiến trình tùy ý; giới hạn dung lượng giải nén, thời gian, CPU và RAM. PPTM không thuộc phạm vi. UI báo đang chuyển đổi, thành công hoặc lỗi rõ ràng. Chưa xem trước được thì không tự coi là đã phát hành bản đọc ổn định.

Kiểm chứng font tiếng Việt, công thức, biểu đồ, hình, bảng và tỷ lệ slide bằng bộ file đại diện có quyền sử dụng. Bản xem PDF là bản tĩnh, không cam kết giữ hiệu ứng, âm thanh, video và ghi chú diễn giả. [Canvas cũng công bố giới hạn media và hiệu ứng trong bản xem PowerPoint](https://community.instructure.com/en/kb/articles/662858-what-types-of-files-can-i-preview-in-canvas).

### 15.4 EXT04 Chỉ dẫn đọc theo buổi

Đợt R3. Giảng viên tạo ReadingInstruction gồm session_id, version_id, các khoảng trang, mục đích, thời điểm gợi ý và câu hỏi tự kiểm tra. Khoảng trang phải hợp lệ và cùng lớp. Link mở đúng phạm vi đọc; sinh viên có thể tự đánh dấu đã xem, nhưng hệ thống không tự suy ra đã hiểu hoặc đã hoàn thành điểm danh.

Tiêu chí đạt: chỉ dẫn xuất hiện ở đúng buổi, mở đúng trang và phiên bản, giữ nội dung đã giao khi có bản mới; giảng viên có thể sửa bằng revision và lưu lịch sử. Không tự gắn điểm chính thức vào câu trả lời tự kiểm tra.

### 15.5 EXT05 Tự nguyện theo trang giảng viên

Đợt R4. Tạo PresentationSession cho một lớp và phiên bản đang công bố. Chỉ giảng viên được phân công phát vị trí; sinh viên chọn Theo giảng viên, Tạm rời hoặc Quay lại. Đồng bộ trang, không giành quyền điều khiển zoom hoặc ghi chú cá nhân.

Transport ưu tiên SSE cho vị trí một chiều; dùng POST có xác thực cho giảng viên phát trang. Mỗi event có sequence, version_id, page_no và thời gian; bỏ event cũ, kiểm quyền khi kết nối và khi gia hạn. Mất kết nối thì giữ chế độ tự đọc, thông báo trạng thái; không ép nhảy trang khi kết nối lại trước khi người dùng chọn theo dõi.

Tiêu chí đạt: hai sinh viên theo dõi đúng trang; một người có thể rời và nhập lại độc lập; không điều khiển được lớp khác; kết thúc phiên không thay vị trí cá nhân đã lưu trước chế độ theo giảng viên.

### 15.6 EXT06 AI giải thích nội dung đang chọn

Đợt R4 sau khi nguồn, quyền và anchor ổn định. Tác vụ ban đầu là giải thích một đoạn và gợi ý câu hỏi tự kiểm tra trong phạm vi tài liệu được chọn. Dùng gateway hiện có, giữ cơ chế cấu hình, ghi nhận sử dụng và giới hạn mỗi lượt. Thiết kế này không tự cấp quyền gọi provider trả phí hoặc gửi tài liệu thật ra ngoài.

Truy hồi và dẫn nguồn gồm offering_id, material_id, version_id, rendition_id nếu có và page_no. Mỗi lần đọc nguồn phải kiểm lại quyền và publication; không tái sử dụng quyền chỉ vì conversation cũ đã chứa citation. Phân biệt phần được nguồn hỗ trợ, phần giải thích thêm và phần chưa đủ căn cứ. Nội dung trong tài liệu là dữ liệu, không phải chỉ dẫn hệ thống.

Tiêu chí đạt: citation mở đúng phiên bản và trang, không trộn dữ liệu lớp khác, không khẳng định từ hình hoặc công thức khi parser chưa đọc được, từ chối khi nguồn không đủ; có bộ câu hỏi với gold và source span được kiểm tra bằng mã. Chất lượng học tập thực tế tiếp tục được đo riêng với người học.

## 16 Yêu cầu hiệu năng và vận hành

Các con số dưới đây là mục tiêu thử nghiệm đề xuất, chưa phải kết quả đo. Bộ đo cần ghi cấu hình máy chủ, thiết bị, trình duyệt, mạng, cache và phiên bản build để có thể tái lập.

| Mã | Mục tiêu | Điều kiện đo |
|---|---|---|
| NFR01 | Trang PDF đầu có thể đọc trong 3 giây ở p95 | PDF 10 MiB 100 trang có chữ; mạng 20 Mbps, RTT 50 ms; Range hoạt động; từ lúc viewer yêu cầu content đến trang đầu rõ chữ |
| NFR02 | Trang đã nạp chuyển trong 500 ms ở p95 | Cùng bộ file trên thiết bị desktop và điện thoại ghi rõ cấu hình |
| NFR03 | API metadata đọc trong 500 ms ở p95 | 30 người đọc đồng thời trên cấu hình local được ghi nhận, không gồm tải byte |
| NFR04 | Không render toàn bộ PDF lớn cùng lúc | Duy trì số canvas đang render có giới hạn theo viewport và pixel budget; đo bộ nhớ với PDF 500 trang |
| NFR05 | Hoạt động trên màn hình 360px | Toolbar không đè nội dung; không cuộn ngang ở shell; vùng PDF vẫn pan hợp lệ |
| NFR06 | Dữ liệu tồn tại sau restart | File, publication, reader state, bookmark và outbox đọc lại đúng |
| NFR07 | Dịch vụ lỗi không cấp quyền rộng hơn | Metadata hoặc auth storage lỗi trả 503, không mở file công khai |

Với PDF scan nặng hoặc cấu trúc không thuận lợi cho Range, phải báo riêng kết quả, không gộp để tuyên bố mọi file đạt NFR01. Giới hạn canvas và độ phân giải phải bảo đảm chữ đọc được, tránh giảm chất lượng âm thầm để đạt số liệu. PDF.js có khuyến nghị về bộ nhớ và tải từng phần tại [FAQ chính thức](https://github.com/mozilla/pdf.js/wiki/Frequently-Asked-Questions).

Ghi metric: thời gian tải trang đầu, lỗi viewer theo mã, số upload hợp lệ hoặc thất bại, độ trễ job, số lượt công bố, quota còn lại và lỗi quyền. Không ghi toàn văn bài giảng, nội dung câu hỏi riêng, token, đường dẫn lưu trữ hoặc thông tin cá nhân không cần thiết vào log.

Feature flag học liệu kiểm soát việc bật module; khi tắt hoặc dependency lỗi, hiển thị khả năng chưa sẵn sàng, giữ dữ liệu. Phương án phục hồi là tắt flag hoặc quay về build trước vẫn đọc được schema bổ sung; không dùng migration xuống để drop bảng. Bản sao phục hồi phải giữ liên kết metadata với blob và checksum, thử khôi phục vào một đích mới được xác minh, không ghi đè bản gốc.

## 17 Backlog triển khai và phụ thuộc

Ước lượng theo ngày công của một lập trình viên quen stack, bao gồm kiểm thử trong từng hạng mục, chưa tính thời gian chờ người dùng dùng thử. Đây là khoảng lập kế hoạch, không phải cam kết tiến độ. Chỉ chốt lại sau spike T01.

| Mã | Công việc và đầu ra | Phụ thuộc | Ngày công |
|---|---|---|---|
| T01 | Spike viewer, proxy Range, mobile, thư viện và bộ PDF đại diện; chốt quyết định kỹ thuật bằng kết quả | Không | 2 đến 3 |
| T02 | Bổ sung LECTURER, capability và policy thành viên lớp; ca người ngoài lớp | T01 | 2 đến 3 |
| T03 | Model, migration bổ sung, repository và transaction; seed tổng hợp riêng | T01 | 2 đến 3 |
| T04 | API và UI quản trị học kỳ môn lớp thành viên | T02 T03 | 2 đến 3 |
| T05 | Buổi học, thứ tự, liên kết và danh sách học liệu; các trạng thái trống | T02 T03 | 2 đến 3 |
| T06 | Kho blob, intent, stream upload, quota, checksum và quyền | T02 T03 | 3 đến 4 |
| T07 | Pipeline scanner parse, job bền vững, timeout và retry | T06 | 2 đến 3 |
| T08 | Preview, nháp, xác nhận công bố, lịch, thu hồi và outbox | T05 T07 | 3 đến 4 |
| T09 | Endpoint content HEAD Range download qua điểm vào thực | T06 T07 | 2 đến 3 |
| T10 | Trình đọc VIEW01 đến VIEW08 và VIEW11 VIEW12 trên desktop mobile | T01 T09 | 4 đến 5 |
| T11 | Đọc tiếp, đánh dấu, conflict nhiều thiết bị và thông báo bản mới | T08 T10 | 2 đến 3 |
| T12 | Tích hợp menu, health capability, telemetry, recovery và E2E R1 | T04 T05 T08 T09 T10 T11 | 3 đến 4 |
| T13 | Đợt dùng thử R1, ghi số liệu, sửa lỗi ảnh hưởng tác vụ và kiểm lại | T12 và người tham gia | 2 đến 3 ngày kỹ thuật cùng thời gian dùng thử |
| T14 | Ghi chú text region, anchor transform và riêng tư EXT01 | T10 T11 | 4 đến 6 |
| T15 | Thread riêng hoặc lớp, reply, xác nhận giảng viên, outbox EXT02 | T08 T14 | 4 đến 6 |
| T16 | Spike converter, rendition và kiểm fidelity PPTX EXT03 | T07 T09 T14 | 4 đến 6 |
| T17 | Chỉ dẫn đọc và liên kết phạm vi trang EXT04 | T08 T11 | 2 đến 3 |
| T18 | Phiên trình bày và SSE theo dõi tự nguyện EXT05 | T08 T10 T11 | 4 đến 6 |
| T19 | Truy hồi theo lớp phiên bản và giải thích AI có nguồn EXT06 | T14 T15 và quyền provider phù hợp | 5 đến 8 |
| T20 | E2E và dùng thử riêng R2 R3 R4; đóng các khoảng trống còn lại | T14 đến T19 theo từng đợt | 4 đến 6 |

T01 đến T12 có tổng 29 đến 41 ngày công nếu làm tuần tự. T13 thêm 2 đến 3 ngày kỹ thuật; nên dự phòng khoảng 20 phần trăm cho tích hợp và lỗi thiết bị. Với một người làm toàn thời gian, R1 dự kiến khoảng 8 đến 11 tuần có dự phòng; thời gian chờ dùng thử phải báo riêng. Không dùng ước lượng này để hạ phạm vi trình đọc đã yêu cầu.

T14 đến T20 có tổng 27 đến 41 ngày công trước dự phòng. Có thể phát hành riêng R2 rồi tiếp tục R3 và R4; những mốc này chỉ là cách chia phạm vi. Triển khai toàn lộ trình có tổng lớn hơn R1 và không được báo hoàn tất chỉ vì R1 đã đạt.

Nhánh triển khai theo quy ước codex/. Tài liệu không yêu cầu tạo agent hay chạy công việc song song. Nếu sau này được giao song song, phải tách phạm vi ghi và tránh cùng sửa migration, role, lockfile hoặc hợp đồng API.

### 17.1 Vị trí mã dự kiến

Các đường dẫn dưới đây là vị trí tương đối dự kiến bên trong repository, không phải khẳng định file đã tồn tại. Kiểm lại cấu trúc trước khi tạo; chỉ chỉnh file chung khi cần tích hợp.

- Frontend: apps/web/src/app/learning và apps/web/src/features/learning; tách reader adapter khỏi trang; client API trong apps/web/src/lib/data/api/learning-gateway.ts.
- Domain và service: services/api/src/campus247/domain/learning và application/learning.
- Port: services/api/src/campus247/ports/learning_repository.py và learning_blob_store.py.
- Repository và blob adapter: services/api/src/campus247/infrastructure/learning.
- Router: services/api/src/campus247/presentation/learning.py; composition đăng ký ở bootstrap hiện hành.
- Worker: services/worker/src/campus247_worker/learning, giữ giao thức job tách biệt với ingestion tri thức công khai.
- Migration: trong cây Alembic hiện hành của services/api, tạo revision mới sau khi đọc head thực tế; không tự gán số revision trong kế hoạch.
- Contract: bổ sung nhóm learning vào OpenAPI hiện hành và schema liên quan.
- Kiểm thử: tests/unit/learning, tests/integration/learning, tests/api/test_learning_*.py và apps/web/e2e/learning-*.spec.ts.

Tận dụng AppShell, AccessibleDialog, trạng thái tải và API base hiện có. Không nhân bản hệ thống đăng nhập hoặc tạo một ứng dụng độc lập chỉ để đưa viewer vào.

## 18 Kế hoạch kiểm thử và nghiệm thu

### 18.1 Bộ dữ liệu kiểm thử

Chuẩn bị file tổng hợp hoặc có quyền sử dụng: PDF tiếng Việt có dấu; slide ngang; tài liệu dọc; PDF trộn kích thước và góc xoay; công thức và bảng; 100 trang có chữ; 500 trang; scan có hình nhưng không chữ; file 0 byte; sai đuôi; quá dung lượng; có mật khẩu; hỏng cấu trúc; tên file chứa ký tự đường dẫn và HTML. Ghi hash và đặc điểm từng file trong manifest. Không sửa gold để che lỗi render hoặc quyền.

Tài khoản kiểm thử tối thiểu: giảng viên A của lớp A; giảng viên B của lớp B; sinh viên A của lớp A; sinh viên B của lớp B; một người học hai lớp; quản trị không được phân công đọc; chủ thể đã bị ngưng ghi danh; phiên hết hạn. Dữ liệu tổng hợp phải tách với dữ liệu đang sử dụng.

### 18.2 Ma trận các ca bắt buộc của R1

| Nhóm | Ca cần đạt |
|---|---|
| Quyền | Đổi ID sang lớp khác, tự gửi role, truy cập nháp, lấy Range bản bị thu hồi, quản trị chưa được phân công |
| Tạo lớp và buổi | Thêm đúng thành viên, ngưng phân công, sắp xếp và dùng lại tài liệu trong cùng lớp |
| Upload | File hợp lệ, lỗi định dạng, quá quota, hủy, hết hạn, hai intent cạnh tranh và retry complete |
| Worker | Scanner lỗi, parse timeout, restart khi đang xử lý, job trùng và lease hết hạn |
| Công bố | Preview chính xác, token stale, double click, lịch UTC, mất quyền trước lịch, thu hồi bản hiện hành |
| Trình đọc | Toàn bộ VIEW01 đến VIEW12, file scan, font tiếng Việt, chữ và hình, hướng trang khác nhau |
| HTTP | GET HEAD, Range thường và suffix, Range lỗi, nhiều Range, ETag If-Range, header qua proxy |
| Lưu trạng thái | Reload, restart, thiết bị khác, conflict, mạng mất, đổi tài khoản và bản mới |
| An toàn hiển thị | Filename hoặc metadata có script, link ngoài, PDF action và lỗi không lộ path |
| Phục hồi | Tắt flag, tắt dependency, chạy lại worker, đối soát hash trên bản sao phục hồi |
| Hồi quy | Đăng nhập, chat và dịch vụ hiện hành vẫn hoạt động cùng điểm vào |

Kiểm thử tự động dùng pytest cho nghiệp vụ và API, Vitest cho trạng thái giao diện, Playwright cho luồng trình duyệt. Các lệnh frontend hiện có gồm pnpm --filter web test, pnpm --filter web lint và pnpm --filter web build; kiểm lại selector và cấu hình trước khi chạy. Ca e2e dùng cấu hình runtime thực được xác minh ở thời điểm triển khai, không mặc định khởi động thêm một bản sản phẩm khác.

Không coi ảnh chụp màn hình, test mock hoặc thao tác trực tiếp backend là bằng chứng thay thế cho luồng liên tài khoản, lưu bền vững và đọc qua điểm vào thực. Kết quả tự động, synthetic, thiết bị thật và thử người dùng phải được mô tả đúng loại bằng chứng; synthetic có gold kiểm tra bằng mã là bằng chứng hợp lệ cho phạm vi đó.

### 18.3 Thử nghiệm khả dụng

Đề xuất 2 giảng viên và 8 đến 12 sinh viên, gồm người dùng điện thoại, trong một học phần tổng hợp trước; sau đó dùng nội dung thực khi đã có quyền phù hợp. Đây là quy mô khởi đầu để tìm vấn đề thao tác, không đủ kết luận thống kê cho toàn trường.

Giảng viên thực hiện: tạo buổi, tải bài, xem trước, công bố, cập nhật bản mới và thu hồi có kiểm soát. Sinh viên thực hiện: tìm bài của buổi được giao, đổi dọc sang ngang, phóng to công thức, tìm một trang, đánh dấu và mở lại ở phiên sau. Ghi thời gian, lỗi, số lần cần hướng dẫn và phản hồi ngắn sau mỗi tác vụ.

Mục tiêu đề xuất: ít nhất 80 phần trăm người tham gia hoàn thành từng tác vụ chính không cần trợ giúp; ghi cả tử số và mẫu số. Với mẫu nhỏ, một nhóm gặp lỗi không được che bằng trung bình tổng. Đối chiếu thời gian tìm bài với cách đang dùng; chưa đặt cam kết phần trăm tiết kiệm khi chưa có baseline. Chưa có người tham gia thì đánh dấu phần khả dụng chưa đo, tiếp tục hoàn thiện các kiểm thử kỹ thuật độc lập.

### 18.4 Điều kiện tuyên bố hoàn tất

R1 chỉ hoàn tất kỹ thuật khi FR01 đến FR14 và VIEW01 đến VIEW12 có bằng chứng tương ứng; lỗi quyền, mất dữ liệu, nhầm phiên bản hoặc file không mở được trên thiết bị mục tiêu phải được xử lý. NFR đạt trên cấu hình và corpus đã công bố; mọi ngoại lệ cần nêu rõ thay vì sửa ngầm tiêu chí.

Báo cáo riêng bốn trạng thái: đã thực hiện và kiểm chứng; đã thực hiện nhưng còn thiếu phép đo cụ thể; chưa thực hiện; bị chặn với nguyên nhân và phần phụ thuộc. Nghiệm thu kỹ thuật và kết quả thử người dùng là hai kết quả riêng. Không ghi hoàn tất toàn bộ kế hoạch khi R2 đến R4 vẫn chưa được thực hiện và phạm vi chưa được người dùng điều chỉnh.

## 19 Rủi ro và các quyết định cần kiểm chứng sớm

| Rủi ro | Hệ quả | Hành động cụ thể |
|---|---|---|
| PDF.js hoặc wrapper không đáp ứng hướng cuộn và cảm ứng | Sai trải nghiệm người dùng đã yêu cầu | Spike trước, thử trên thiết bị thật, chốt adapter và dependency |
| Proxy làm mất Range hoặc giới hạn upload | Chậm, lỗi file lớn dù backend chạy | Kiểm đường vào thực với file lớn và header trước khi hoàn thiện UI |
| Dùng nhầm kho đính kèm trên thiết bị | Sinh viên thiết bị khác không mở được | Blob server riêng và E2E hai tài khoản trên hai context |
| Vai trò giảng viên gán quá rộng | Lộ tài liệu hoặc sửa lớp khác | Vai trò toàn hệ thống kết hợp phân công lớp và kiểm mọi endpoint |
| Cập nhật file làm lệch ghi chú | Mất nguồn học tập và phản hồi | Version và rendition bất biến; không tự chuyển anchor |
| Scan hoặc công thức thiếu text layer | Tìm và hỏi AI không có căn cứ | Tách khả năng xem với khả năng đọc chữ; báo hạn chế, đo riêng |
| PDF lớn gây hết bộ nhớ điện thoại | Tab đóng hoặc thao tác chậm | Render theo viewport, pixel budget và kiểm bộ nhớ theo corpus |
| PPTX chuyển đổi sai font hoặc bố cục | Sinh viên đọc sai nội dung | Corpus fidelity và bản gốc; rendition có phiên bản converter |
| Scanner hoặc worker chưa có | Chưa thể tiếp nhận file thực an toàn | Làm fixture và phần độc lập, tích hợp scanner thực trước file thực |
| Thiếu người dùng thử | Chưa xác nhận khả dụng | Hoàn thành kỹ thuật, chuẩn bị kịch bản; báo riêng phần chưa đo |
| Tích lũy file và phiên bản | Hết quota hoặc storage | Đo và báo dung lượng, dừng nhận thêm; không tự cleanup |

Các mặc định đã chọn trong kế hoạch là đề xuất triển khai có thể kiểm chứng, không phải câu hỏi cần xin lại quyền ở mỗi bước. Đầu vào bên ngoài chỉ cần khi dùng dữ liệu hoặc dịch vụ thực: danh sách phân công có thẩm quyền, quyền dùng học liệu, người thử nghiệm và cấu hình môi trường đích. Không tự tạo tích hợp thật, tài khoản trường hoặc dữ liệu cá nhân để lấp khoảng trống.

Trước ngày đầu triển khai: đọc trạng thái Git và phần mã liên quan; chọn môi trường local mới hoặc đã được chỉ định; xác minh identity và kho metadata; chuẩn bị bộ PDF; chạy T01 rồi chốt dependency, giới hạn và phương án Range bằng kết quả đo. Sau đó tiếp tục T02 đến T12 theo phụ thuộc, không dừng ở bản demo chỉ xem được một file.

## 20 Tài liệu tham khảo và giới hạn bằng chứng

Nguồn mã đã đọc để xác định điểm tích hợp:

- [README và mô tả điểm vào Campus hiện hành](<C:/Users/Duong Vinh/Vinh/README.md>)
- [Dependency frontend](<C:/Users/Duong Vinh/Vinh/apps/web/package.json>)
- [AppShell và vai trò giao diện](<C:/Users/Duong Vinh/Vinh/apps/web/src/components/AppShell.tsx>)
- [Đính kèm lưu trên thiết bị](<C:/Users/Duong Vinh/Vinh/apps/web/src/lib/local-attachments.ts>)
- [API base cùng điểm vào](<C:/Users/Duong Vinh/Vinh/apps/web/src/lib/api/base-url.ts>)
- [Rewrite frontend tới backend](<C:/Users/Duong Vinh/Vinh/apps/web/next.config.ts>)
- [Dependency backend](<C:/Users/Duong Vinh/Vinh/pyproject.toml>)
- [Vai trò và định danh backend](<C:/Users/Duong Vinh/Vinh/services/api/src/campus247/ports/identity.py>)
- [Middleware định danh](<C:/Users/Duong Vinh/Vinh/services/api/src/campus247/presentation/identity.py>)
- [Composition ứng dụng](<C:/Users/Duong Vinh/Vinh/services/api/src/campus247/bootstrap/app.py>)
- [Composition kho actor](<C:/Users/Duong Vinh/Vinh/services/api/src/campus247/bootstrap/actor_storage.py>)
- [Quy ước API đang có để tham khảo tương thích](<C:/Users/Duong Vinh/Vinh/docs/04-architecture/contracts/API_CONVENTIONS.md>)

Nguồn công khai hỗ trợ đánh giá, truy cập ngày 04/11/2026:

- [Mozilla PDF.js về các lớp core display viewer](https://mozilla.github.io/pdf.js/getting_started/)
- [Mozilla PDF.js về bộ nhớ tải từng phần và trình duyệt](https://github.com/mozilla/pdf.js/wiki/Frequently-Asked-Questions)
- [Mozilla PDF.js về lựa chọn trang zoom và sidebar](https://github.com/mozilla/pdf.js/wiki/Viewer-options)
- [Mozilla PDF.js về nhãn các chế độ cuộn và xem](https://github.com/mozilla/pdf.js/blob/master/l10n/en-US/viewer.ftl)
- [Moodle về tải và nhúng file trong khóa học](https://docs.moodle.org/en/File_resource_settings)
- [Canvas về trình xem và chú thích tài liệu](https://community.instructure.com/en/kb/articles/662751-what-is-docviewer)
- [Canvas về định dạng và giới hạn xem trước](https://community.instructure.com/en/kb/articles/662858-what-types-of-files-can-i-preview-in-canvas)
- [OWASP về tải tệp](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html)
- [W3C về thao tác bằng bàn phím](https://www.w3.org/WAI/WCAG22/Understanding/keyboard.html)

Các nguồn trên chứng minh có nền tảng kỹ thuật và các chức năng tương tự trong sản phẩm khác; chúng không chứng minh hiệu năng, mức độ phù hợp hay hiệu quả học tập của tính năng Campus chưa được xây. Bằng chứng hiện tại là đối chiếu mã nguồn chỉ đọc và tài liệu kỹ thuật công khai; kiểm thử tính năng, phép đo hiệu năng và khả dụng với người dùng thực sẽ được tạo trong các hạng mục tương ứng.
