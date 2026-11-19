# Đề xuất trợ lý cá nhân nâng cao — Campus 24/7

Ngày: 14/10/2026. Trạng thái: đề xuất, chưa triển khai và chưa nghiệm thu.

Tài liệu này bổ sung cho ASSISTANT_PERSONALIZATION_PROPOSAL_20261014.md. Những yêu cầu nền tảng về lịch sử, renderer, identity, retention và quyền vẫn phải đạt trước khi mở rộng mức chủ động.

## 1. Định hướng sản phẩm

Trợ lý hỗ trợ từng người hoàn thành mục tiêu trong Campus 24/7: mở lại đúng công việc, biết bước tiếp theo, giải thích căn cứ và chuẩn bị thao tác trong phạm vi được phép. Đánh giá bằng việc người dùng hoàn thành tác vụ, độ chính xác, quyền riêng tư, thời gian và chi phí.

Ba chiều mở rộng: chiều sâu cá nhân hóa, khả năng duy trì công việc qua nhiều phiên và mức chủ động có kiểm soát. Không mặc định tăng cả ba cho mọi tài khoản.

Yêu cầu bổ sung trực tiếp của người dùng: AI xuất hiện ở mọi nơi để hỗ trợ mọi thao tác và yêu cầu, "hỗ trợ tận răng"; tự động hỗ trợ thủ tục tốt nhất để người dùng nhàn nhất có thể, đồng thời bảo đảm độ chính xác và hiểu mục đích. Yêu cầu này trở thành nguyên tắc thiết kế xuyên suốt mọi đợt triển khai. Phần 8 cụ thể hóa trải nghiệm, phạm vi tự động và tiêu chí nghiệm thu.

## 2. Tám nâng cấp tạo khác biệt

### 2.1. Hồ sơ trợ lý do người dùng kiểm soát

Ngoài cách xưng hô và độ dài, cho người dùng khai báo mục tiêu, cách muốn nhận hướng dẫn và hoàn cảnh liên quan trực tiếp đến tác vụ. Ví dụ: muốn hoàn thành hồ sơ theo từng bước, ưu tiên bản điện tử hoặc chỉ nhận gợi ý khi mở ứng dụng.

Phân biệt thông tin tự khai, sở thích, thông tin được nguồn học vụ xác nhận và giả thuyết chưa xác minh. Không tự suy diễn tình trạng sức khỏe, tài chính hoặc năng lực cá nhân từ lịch sử chat. Không coi thông tin trong hồ sơ cá nhân là nguồn có thẩm quyền về quyền lợi học vụ.

Onboarding ngắn và có thể bỏ qua; chỉ hỏi bổ sung khi cần cho công việc. Tùy chọn trả lời có thể override riêng trong từng chat mà không đổi thiết lập dài hạn.

### 2.2. Bộ nhớ có thời gian, nguồn và cơ chế sửa sai

| Loại | Ví dụ | Cách quản lý |
| --- | --- | --- |
| Sở thích | Thích câu trả lời ngắn, có checklist | Người dùng xem/sửa, áp dụng khi được phép |
| Mục tiêu | Đang chuẩn bị hồ sơ xin cấp giấy | Có trạng thái, phạm vi, thời hạn; kết thúc khi hoàn thành hoặc người dùng dừng |
| Ngữ cảnh công việc | Bản nháp nào đang làm, phần nào còn thiếu | Liên kết ID và phiên bản tài nguyên; đọc lại trạng thái hiện hành |
| Thông tin do người dùng xác nhận | Mục đích sử dụng giấy tờ | Có nguồn, phạm vi và ngày xác nhận; hỏi lại khi mâu thuẫn |

Một memory có tối thiểu: owner/tenant, loại, nội dung tối thiểu, source reference, thời điểm ghi, khoảng hiệu lực nếu có, trạng thái xác nhận và phạm vi sử dụng. Nhận định của mô hình không tự trở thành thông tin đã xác nhận.

Các cơ chế bắt buộc:

- Chọn những memory liên quan đến câu hỏi trong ngân sách context; không gửi cả kho nhớ mỗi lượt.
- Khi người dùng cập nhật một sở thích, mục mới thay thế hiệu lực mục cũ và giữ dấu vết thay đổi phù hợp.
- Khi nguồn thay đổi, đánh dấu thông tin cần kiểm tra; lấy trạng thái học vụ từ hệ thống hiện hành.
- Người dùng có thể xem "Thông tin đang được dùng" và sửa hoặc yêu cầu quên ngay từ câu trả lời.
- Quên một mục phải loại nó khỏi context, chỉ mục truy xuất và summary dẫn xuất trong phạm vi đã chọn; không tự tái tạo từ lịch sử cũ. Phân biệt rõ quên memory với xóa bản chat gốc.
- Tắt memory cá nhân và chat tạm thời phải được kiểm tra ở server.

LongMemEval cung cấp các nhóm đánh giá hữu ích: trích xuất thông tin, suy luận qua nhiều phiên, thời gian, cập nhật và biết từ chối khi thiếu thông tin. Dùng để thiết kế ca kiểm thử riêng của Campus 24/7; không lấy điểm benchmark chung làm bằng chứng sản phẩm đã hoạt động tốt.

### 2.3. Mục tiêu và công việc có trạng thái bền vững

Biến yêu cầu nhiều bước thành một mục công việc người dùng nhìn thấy được. Ví dụ: chuẩn bị yêu cầu tài liệu, bổ sung hồ sơ hoặc theo dõi phản hồi.

Mỗi mục có objective, owner, resource references, các bước, trạng thái, blockers, version, next action, hạn có nguồn nếu có và trạng thái đồng ý theo dõi. Trạng thái gợi ý: đang chuẩn bị, cần người dùng bổ sung, chờ xác nhận, đã gửi, chờ cán bộ, hoàn tất, tạm dừng.

Danh sách "Tiếp tục công việc" đưa người dùng trở lại đúng bản nháp hoặc hồ sơ và nêu bước tiếp theo. Tiếp tục không chạy lại những thao tác đã hoàn tất. "Đã gửi" và "Hoàn tất" cần biên nhận hoặc trạng thái từ hệ thống nghiệp vụ; văn bản của mô hình không xác lập thành công.

Tận dụng cơ chế agent run/resume, confirmation và idempotency hiện có sau khi kiểm tra phạm vi hỗ trợ. Với quy trình đã biết, workflow xác định xử lý chuyển trạng thái; mô hình hỗ trợ hiểu yêu cầu và diễn đạt. Chỉ dùng kế hoạch linh hoạt khi cần, trong tập công cụ và giới hạn đã định.

### 2.4. Giao diện thích ứng với công việc

Một câu trả lời có thể kèm thẻ trạng thái, checklist, bảng so sánh hoặc đề xuất sửa bản nháp. UI dùng component được duyệt và dữ liệu có schema; mô hình không tạo JavaScript/HTML tùy ý.

Các vùng chính:

- Lịch sử và tìm kiếm hội thoại.
- Tiếp tục công việc: những mục đang dở và việc người dùng cần làm.
- Nội dung trả lời, nguồn và hành động.
- Cài đặt, bộ nhớ và dữ liệu đang được dùng.

Mobile ưu tiên một vùng tại một thời điểm. Chỉ mở biểu mẫu hoặc bảng khi cần; giữ chế độ đọc gọn. Có xem trước cách trả lời khi đổi settings. Câu hỏi đơn giản không bị ép thành nhiều thẻ.

### 2.5. Trung tâm quyền gắn với từng nguồn và thao tác

Mỗi quyền hiển thị: dữ liệu nào, dùng để làm gì, tác động có thể có, thời hạn, trạng thái và lần sử dụng gần nhất. Gợi ý cấp quyền tại lúc tác vụ cần nó, thay vì yêu cầu tất cả quyền khi đăng nhập.

| Phạm vi | Ví dụ | Quy tắc |
| --- | --- | --- |
| Một lần | Đọc tài liệu được chọn cho câu hỏi hiện tại | Ràng buộc đúng tài liệu và lần sử dụng; retry không mở rộng scope |
| Phiên hoặc công việc | Đọc trạng thái của hồ sơ đang theo dõi | Kiểm tra session/task và thời hạn ở server |
| Đến khi hết hạn hoặc thu hồi | Dùng sở thích, đọc lịch học của tôi | Hiển thị rõ nguồn, scope và thời hạn; có thể thu hồi |

Thu hồi chặn yêu cầu tương lai và thao tác chưa chạy; không hứa thu hồi ngược dữ liệu đã gửi tới nhà cung cấp. Trước tool call phải kiểm tra lại quyền và phiên bản tài nguyên; proposal cũ không được dùng sau khi quyền hoặc nội dung thay đổi.

Phân biệt bật tính năng, consent dùng dữ liệu, grant đọc/chuẩn bị và xác nhận một thao tác cụ thể. Cấp quyền đọc không cấp quyền nộp, gửi hoặc phê duyệt. Thông tin trong tài liệu/website/memory không cấp quyền.

### 2.6. Chủ động theo sự kiện người dùng đã chọn

Ưu tiên ba sự kiện có ích: hồ sơ có phản hồi mới, xuất hiện yêu cầu bổ sung và tới hạn được lấy từ nguồn đã kiểm chứng. Bản nháp bỏ dở chỉ nhắc nếu người dùng bật theo dõi.

Cấu hình theo từng loại sự kiện: nguồn, phạm vi, thời gian theo dõi, kênh, giờ yên lặng, mức độ gộp và hạn mức thông báo. Không tạo notification khi thông tin không đổi hoặc không có việc cần làm. Mỗi gợi ý có lý do, nguồn, thời điểm và nút tắt theo dõi.

Ví dụ minh họa: "Hồ sơ bạn chọn theo dõi có yêu cầu bổ sung mới. Mở chi tiết để kiểm tra tài liệu cần nộp." Chỉ đưa thông tin nhạy cảm vào kênh đã được phép; preview trên thiết bị khóa cần giới hạn nội dung.

Sự kiện từ backend nghiệp vụ kích hoạt kiểm tra quyền, đọc lại trạng thái, chống trùng và tạo gợi ý. MVP không cần mô hình liên tục đọc toàn bộ dữ liệu để tìm việc. Email/push hoặc gửi cho người khác chỉ kích hoạt sau khi có kết nối và lựa chọn tương ứng; không suy ra từ quyền chat.

### 2.7. Minh bạch căn cứ và bàn giao cho cán bộ

Mỗi gợi ý cá nhân quan trọng có "Vì sao gợi ý này?": thông tin người dùng đã khai báo, nguồn đang được dùng, ngày cập nhật và giới hạn còn chưa xác minh. Đây là giải thích căn cứ, không hiển thị chuỗi suy nghĩ nội bộ.

Khi cần cán bộ: tạo bản tóm tắt người dùng xem trước gồm vấn đề, hồ sơ liên quan, phần đã thử, nguồn và câu hỏi còn mở. Người dùng chọn nội dung chia sẻ và xác nhận gửi. Không tự chia sẻ toàn bộ lịch sử hoặc memory.

Khi nguồn mâu thuẫn/hết hiệu lực, nêu rõ điểm chưa chắc và bước xác minh. Không hứa thời gian phản hồi của cán bộ khi chưa có căn cứ.

### 2.8. Chất lượng được kiểm chứng qua thời gian

Đo đúng các lớp: lịch sử bền vững, memory chính xác và cập nhật được, quyền thực thi, độ đúng nghiệp vụ, khả năng hoàn thành tác vụ, UX, latency và chi phí. Phản hồi "không đúng", "quá dài", "nhớ sai" và "gợi ý không liên quan" giúp xác định lỗi ở lớp nào.

Người dùng có thể sửa sở thích ngay, nhưng phản hồi cá nhân không tự cập nhật quy định trường hoặc câu trả lời chung cho người khác. Thay đổi knowledge/prompt/policy được kiểm tra và theo dõi phiên bản. Dùng số liệu tổng hợp và log tối thiểu; không mặc định thu nội dung chat cho huấn luyện hoặc đánh giá.

## 3. Hành trình minh họa

Người dùng hỏi: "Tôi muốn hoàn thành hồ sơ xin giấy đang làm dở."

1. Kiểm tra tài khoản và quyền đọc bản nháp/hồ sơ.
2. Tìm đúng mục công việc; nếu có nhiều bản nháp, hỏi chọn thay vì đoán.
3. Đọc phiên bản hiện tại và memory có liên quan được phép dùng.
4. Hiển thị phần đã có, phần còn thiếu và bước tiếp theo từ workflow hiện hành.
5. Chuẩn bị đề xuất thông tin; người dùng kiểm tra rồi áp dụng.
6. Hiển thị preview khi nộp; xác nhận và kiểm tra lại quyền/phiên bản trước khi thực hiện.
7. Chỉ hiển thị đã gửi khi có biên nhận.
8. Nếu người dùng bật theo dõi, thông báo khi có thay đổi cần xử lý; mở lại trở về đúng hồ sơ.

Toàn bộ ví dụ là trải nghiệm đề xuất, không khẳng định hệ thống hiện tại đã thực hiện được.

## 4. Kiến trúc mở rộng vừa đủ

Mở rộng nền tảng đã có thành các trách nhiệm: conversation/context, preferences/memory, task state/workflow, authorization/consent, nguồn/công cụ, response rendering, event delivery và evaluation. Đây là module logic, chưa cần tách thành microservice.

PostgreSQL có thể lưu dữ liệu chính, version, sự kiện cần xử lý và delivery receipts. Dùng outbox/worker với retry và idempotency khi cần theo dõi sự kiện bền vững; không thêm hạ tầng phân tán trước khi tải và yêu cầu thực tế chứng minh nhu cầu. Vector index chỉ hỗ trợ tìm memory sau lọc quyền; không thay dữ liệu có cấu trúc và kiểm tra ownership.

Giới hạn mỗi lượt/run: context, tool calls, thời gian, retry và chi phí. Khi không thể tiếp tục, trả trạng thái rõ và giữ công việc để mở lại. Không loop vô hạn hoặc tự mở thêm nguồn/công cụ ngoài grant.

Bộ lọc prompt injection là lớp phụ trợ. Quyền công cụ và đối tượng thao tác phải do code xác định và kiểm tra. OWASP nêu cả tool abuse, memory poisoning và data exfiltration; AgentDojo cung cấp cách kiểm thử agent dùng công cụ với dữ liệu không đáng tin cậy.

## 5. Lộ trình sau nền tảng

| Đợt | Phạm vi | Điều kiện mở rộng |
| --- | --- | --- |
| A. Cá nhân hóa có kiểm chứng | Hồ sơ trợ lý, memory rõ nguồn, cách trả lời thích ứng, override theo chat | Lịch sử/quyền nền tảng đạt; nhớ đúng, sửa được và cách ly tài khoản |
| B. Tiếp tục và hoàn thành công việc | Task state, checklist, resume, biên nhận, bàn giao có preview | Retry/restart không mất hoặc nhân đôi thao tác; trạng thái nghiệp vụ đúng |
| C. Chủ động có kiểm soát | Theo dõi sự kiện được chọn, giờ yên lặng, dedup, nguồn và tắt theo dõi | Event source đáng tin cậy; grant thu hồi có hiệu lực; thông báo phù hợp |

Ưu tiên pilot với ba tác vụ đã gần hệ thống: xin cấp giấy, bổ sung hồ sơ, theo dõi phản hồi. Mục tiêu tốt nghiệp hoặc tích hợp lịch/email là mở rộng sau khi có nguồn chính xác và kết nối được phép. Chưa chốt thời gian tăng thêm trước khi biết độ hoàn thiện của nền tảng và workflow hiện có.

## 6. Nghiệm thu mức nâng cao

- Memory: nhớ đúng; cập nhật thay thế sở thích cũ; xử lý thông tin mâu thuẫn; biết nói không có thông tin; mục bị quên không tái xuất hiện trong context tương lai.
- Task: mở lại sau nhiều phiên/restart; chọn đúng tài nguyên; phiên bản thay đổi làm proposal cũ không dùng được; retry sau lỗi không nộp/gửi hai lần.
- Quyền: cross-account/tenant, grant một lần/hết hạn/thu hồi; mọi đường tool/API đều kiểm tra; instruction trong nguồn hoặc memory không vượt scope.
- Chủ động: chỉ trigger được cấp; không thông báo trùng/không đổi; giờ yên lặng và tắt theo dõi có hiệu lực; nội dung đi đúng kênh/phạm vi.
- UX: người dùng tìm được việc đang dở, biết bước tiếp theo, hiểu vì sao được gợi ý và sửa được personalization.
- Kết quả: đo tỷ lệ hoàn thành tác vụ có biên nhận, số bước/thời gian đến hoàn tất, tỷ lệ hỏi lại, gợi ý hữu ích, sự cố quyền và chi phí mỗi tác vụ hoàn tất. Chốt ngưỡng sau baseline; không cam kết con số chưa đo.
- Release: ca giới hạn quyền và bảo toàn dữ liệu phải pass trong tập kiểm thử xác định; kết quả đó không chứng minh không còn lỗi ngoài tập thử. Mở rộng theo cohort được cho phép và có cách tắt tính năng nâng cao mà giữ dữ liệu/công việc.

## 7. Nguồn đối chiếu

- LongMemEval: https://arxiv.org/abs/2410.10813 — các năng lực memory cần đánh giá.
- AgentDojo: https://arxiv.org/abs/2406.13352 — kiểm thử agent dùng công cụ dưới tác động của dữ liệu không đáng tin cậy.
- OWASP AI Agent Security: https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html — nguyên tắc giảm quyền, bảo vệ memory và kiểm soát thao tác.

## 8. Yêu cầu xuyên suốt: AI hỗ trợ mọi thao tác, tối thiểu hóa công sức người dùng

### 8.1. Mục tiêu sản phẩm

Người dùng diễn đạt mục tiêu bằng ngôn ngữ tự nhiên hoặc bắt đầu thao tác trên UI; trợ lý chuẩn bị và dẫn công việc đến kết quả trong phạm vi chức năng và quyền của tài khoản. Không buộc người dùng chuyển sang trang chat rồi kể lại tình huống. Mỗi capability phải có đường thực hiện, kiểm tra kết quả và tiếp tục sau lỗi; nếu chưa hỗ trợ, thông báo đúng giới hạn và cung cấp bước tiếp theo cụ thể.

Đồng thời giảm nhập liệu, tìm kiếm, chuyển trang và việc phải giải thích lại. Không tối ưu số lần bấm bằng cách bỏ xác minh mục đích, bỏ kiểm tra dữ liệu hoặc bỏ xác nhận hành động hiện có.

### 8.2. AI hiện diện theo ngữ cảnh

| Bề mặt | Hỗ trợ đề xuất |
| --- | --- |
| Điều hướng và tìm kiếm toàn ứng dụng | Nhận mục tiêu, mở đúng dịch vụ/hồ sơ, tiếp tục công việc; truy cập từ một điểm trợ lý chung |
| Trang dịch vụ | Giải thích lựa chọn, giúp chọn thủ tục phù hợp mục đích, chuẩn bị bản nháp khi có đủ dữ liệu |
| Biểu mẫu | Điền sẵn dữ liệu có căn cứ, trình bày phần còn thiếu, kiểm tra nhất quán, chuẩn bị xem trước |
| Từng trường | Giải thích ngắn, gợi ý giá trị có nguồn, sửa định dạng trong phạm vi hợp lệ, hỏi đúng trường chưa rõ |
| Tài liệu đính kèm | Hướng dẫn yêu cầu, kiểm tra định dạng/dung lượng, đề xuất ánh xạ dữ liệu trích xuất để kiểm tra; không mặc định xác nhận tính xác thực |
| Lỗi và tình huống bị chặn | Giải thích nguyên nhân được hệ thống xác nhận, đưa cách khắc phục hoặc tiếp tục; giữ bản nháp |
| Hồ sơ, lịch và thông báo | Đọc trạng thái được phép, giải thích thay đổi, chuẩn bị bước tiếp theo, tránh xử lý trùng |
| Cài đặt và quyền riêng tư | Giải thích tác động, chuẩn bị lựa chọn; không tự tăng quyền hoặc thay đổi consent |
| Giao diện cán bộ/quản trị | Hỗ trợ tổng hợp, tìm nguồn, kiểm tra thiếu sót và soạn phản hồi trong đúng vai trò; quyết định/phê duyệt theo quy trình hiện hành |

Hiện diện không có nghĩa luôn mở panel, bật popup hoặc đưa ra lời gợi ý liên tục. Một runtime chung có thể xuất hiện dưới dạng nút trợ lý, gợi ý trong trường, thẻ hành động hoặc panel phù hợp ngữ cảnh. Người dùng có thể thu gọn hoặc chọn mức chủ động; công việc và ngữ cảnh vẫn được giữ.

### 8.3. Hiểu mục đích trước khi chọn và thực hiện thủ tục

Mỗi yêu cầu được chuyển thành một bản mục đích có cấu trúc: kết quả mong muốn, mục đích sử dụng, đối tượng/hồ sơ liên quan, các ràng buộc do người dùng nêu, thông tin đã biết và những điểm còn thiếu. Mỗi giá trị được phân biệt là người dùng nói rõ, nguồn xác nhận hoặc suy luận cần kiểm tra.

Chính sách hỏi:

- Không hỏi lại thông tin đã có, còn hiệu lực, được phép dùng và khớp yêu cầu hiện tại.
- Khi các cách hiểu dẫn đến thủ tục, tài liệu, chi phí, người nhận hoặc hành động khác nhau, hỏi câu phân biệt ngắn trước khi lựa chọn.
- Gộp các thông tin còn thiếu có liên quan thành một câu hỏi hoặc một vùng bổ sung; không đưa nguyên biểu mẫu dài vào chat.
- Có thể chuẩn bị phần đã chắc chắn trong lúc chờ phần còn thiếu; không tự chọn giá trị quan trọng chỉ để hoàn thành form.
- Tóm tắt cách hiểu trong thẻ công việc để người dùng sửa ngay; chỉ yêu cầu xác nhận cách hiểu riêng khi sự mơ hồ có tác động thực tế.
- Khi người dùng đổi mục đích, đánh giá lại thủ tục và bản nháp; giữ phần nhập trước, chỉ đề xuất thay đổi cần thiết.

Không dùng điểm tự tin do mô hình tự khai làm bằng chứng hiểu đúng. Dùng sự đầy đủ của các thông tin bắt buộc, tính nhất quán với câu người dùng nói, khả năng ánh xạ vào workflow và các dữ liệu nguồn đã xác minh.

### 8.4. Phạm vi tự động hóa

| Trường hợp | Hành vi |
| --- | --- |
| Người dùng bắt đầu một thủ tục; dữ liệu tài khoản được phép đọc và nguồn còn hiệu lực | Tạo bản nháp mới với các trường xác định được điền sẵn; hiển thị nguồn và cho sửa |
| Thông tin người dùng đã nói rõ trong yêu cầu hiện tại | Ánh xạ vào trường hợp lệ sau kiểm tra schema/kiểu dữ liệu |
| Có dữ liệu nhạy cảm, xung đột, tài liệu trích xuất chưa xác minh hoặc nhiều cách hiểu quan trọng | Giữ phần chắc chắn, hỏi/đề xuất đúng phần cần làm rõ |
| Bản nháp đã có chỉnh sửa thủ công | Không ghi đè âm thầm; hiển thị đề xuất và dùng cơ chế Áp dụng hiện hành; gộp thay đổi liên quan để giảm thao tác |
| Nộp hồ sơ, gửi nội dung, thanh toán, đặt dịch vụ, thay đổi quyền hoặc quyết định nghiệp vụ | Giữ preview/xác nhận và kiểm tra quyền theo quy trình; không suy ra ủy quyền từ mong muốn "nhàn nhất" |

AI chuẩn bị tối đa phần việc có đủ căn cứ và được phép. Một xác nhận cuối có thể bao phủ một thao tác xác định với nội dung, nơi nhận và các ảnh hưởng rõ ràng; không dùng như quyền vô hạn cho các thao tác khác. Không thêm bước xác nhận cho việc đọc/chuẩn bị vốn đã được cấp nếu quy trình không yêu cầu.

### 8.5. Luồng thủ tục hỗ trợ trọn vẹn

Ví dụ mục đích: "Tôi cần giấy để nộp cho công ty tuần sau." Đây là tình huống thiết kế, không phải dữ liệu hay điều kiện nghiệp vụ đã xác minh.

1. Nhận mục đích, kiểm tra nguồn/quyền; nếu chưa rõ loại giấy công ty yêu cầu, hỏi đúng điểm này.
2. Chọn workflow theo quy tắc nghiệp vụ hiện hành; tạo hoặc mở bản nháp phù hợp, không tự tạo bản trùng.
3. Điền sẵn dữ liệu có căn cứ; trình bày phần trợ lý đã chuẩn bị và những thông tin người dùng còn cần bổ sung.
4. Hướng dẫn tài liệu đính kèm và kiểm tra dữ liệu bằng schema/quy tắc; dữ liệu OCR chỉ là đề xuất cho đến khi được xác minh phù hợp.
5. Giải quyết lỗi ngay tại trường; giữ bản nháp và đưa người dùng tới đúng phần cần sửa.
6. Chuẩn bị preview gọn: loại yêu cầu, mục đích, thông tin gửi, người nhận, tài liệu và chi phí/thời hạn nếu có nguồn. Không hứa đáp ứng "tuần sau" nếu hệ thống chưa có căn cứ.
7. Người dùng xác nhận nộp; backend kiểm tra lại quyền, phiên bản, dữ liệu và idempotency rồi thực hiện.
8. Hiển thị biên nhận và bước tiếp theo; theo dõi phản hồi nếu được người dùng lựa chọn. Khi cần bổ sung, mở lại đúng hồ sơ và chuẩn bị nội dung bổ sung để kiểm tra.

Người dùng tập trung vào nêu mục đích, cung cấp thông tin/tài liệu chỉ họ biết và xác nhận thao tác cần xác nhận. Trợ lý chịu phần tìm đúng luồng, chuẩn bị, kiểm tra và nối các bước trong phạm vi được hỗ trợ.

### 8.6. Điều kiện kỹ thuật để phủ toàn ứng dụng

- Registry màn hình/thao tác: xác định route, vai trò, nguồn dữ liệu, field schema, workflow, capability hỗ trợ và những giới hạn. Kiểm tra độ phủ bằng danh sách thao tác thật, không chỉ đếm nút AI.
- Context theo kiểu dữ liệu rõ ràng: route, task/draft ID, version, trường đang hỏi, lỗi đã xác nhận và snapshot được phép. Không đọc toàn bộ DOM hoặc theo dõi màn hình ngoài phạm vi ứng dụng để có ngữ cảnh.
- Cùng một runtime, trạng thái công việc và lịch sử giữa trang chat, panel, biểu mẫu và thông báo. Không tạo cuộc chat độc lập làm mất mục đích khi chuyển trang.
- Giữ nguồn gốc giá trị tại trường: nguồn hệ thống, người dùng khai báo, trích xuất tài liệu hoặc đề xuất AI. Dữ liệu học vụ và quyền không được quyết định chỉ bởi text của mô hình.
- Xử lý version và chỉnh sửa thủ công để tránh ghi đè; validation ở server, tool payload có schema, confirm/receipt/idempotency theo thao tác.
- Khi mất mạng hoặc dịch vụ AI lỗi, giữ dữ liệu và cho tiếp tục thao tác thủ công; phân biệt phần đã lưu máy chủ và phần chưa lưu.

### 8.7. Bổ sung nghiệm thu và thứ tự triển khai

Mỗi thao tác trong registry phải có trạng thái hỗ trợ: giải thích, chuẩn bị, thực hiện sau xác nhận, hoặc chưa hỗ trợ có đường tiếp tục rõ. Không báo "hỗ trợ mọi nơi" khi một số bề mặt chỉ có nút không nối tới dữ liệu/capability thật.

Các ca bắt buộc: câu nói mơ hồ; mục đích thay đổi giữa chừng; hai bản nháp gần giống; dữ liệu nguồn cũ/mâu thuẫn; trường đã sửa tay; tài liệu OCR sai; thiếu quyền; lỗi mạng sau khi nộp; restart; khác vai trò; tài khoản/tenant khác; nguồn không đủ để hứa thời hạn. Đo việc chọn đúng workflow, sử dụng đúng dữ liệu và giữ đúng quyết định người dùng.

Đo mức giảm số trường nhập tay, số lần hỏi lại, chuyển trang, thời gian hoàn thành và lỗi phải sửa so với baseline. Đo riêng sai mục đích, điền sai dữ liệu, ghi đè chỉnh sửa và thao tác trùng; giảm công sức chỉ được coi là đạt khi chất lượng và quyền vẫn đạt. Chỉ thu số liệu tối thiểu được phép; không ghi từng ký tự/nội dung nhập để đo trải nghiệm.

Yêu cầu hỗ trợ xuyên ứng dụng được đưa ngay vào đợt nền tảng: runtime/context chung, độ phủ và renderer. Sau đó triển khai tự chuẩn bị thủ tục với ba tác vụ pilot, mở rộng theo registry đã kiểm chứng, rồi mới bật theo dõi chủ động. Không chờ một đợt chatbot riêng hoàn tất mới nghĩ đến các màn hình còn lại.
