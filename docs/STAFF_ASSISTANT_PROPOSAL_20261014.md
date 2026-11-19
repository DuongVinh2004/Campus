# Đề xuất trợ lý AI dành cho cán bộ — Campus 24/7

Ngày: 14/10/2026. Trạng thái: đề xuất thiết kế, chưa triển khai, chưa nghiệm thu bản chạy.

Liên quan: [kế hoạch trợ lý tổng thể](ASSISTANT_IMPLEMENTATION_PLAN_20261014.md), đặc biệt AI-021. Phạm vi cán bộ cần được tách thành nhánh triển khai đủ sâu khi chốt kế hoạch tiếp theo; tài liệu này chưa tự thay đổi backlog hoặc cho phép chạy tác vụ nghiệp vụ.

Yêu cầu nâng cấp bổ sung: tối ưu toàn bộ quy trình để tiết kiệm tối đa thời gian/công sức và bảo đảm độ chính xác, tin cậy. Phần 9–11 cụ thể hóa thiết kế quy trình, thứ tự đầu tư và điều kiện kiểm chứng; vẫn là đề xuất chưa triển khai.

## 1. Mục tiêu

Giảm thời gian đọc, tìm nguồn, đối chiếu, nhập liệu, soạn nội dung và chuyển giao giữa cán bộ. Trợ lý chuẩn bị một bộ hồ sơ làm việc có căn cứ, chỉ rõ những điểm cần cán bộ chú ý, đưa đề xuất có thể kiểm tra và nối thao tác đến kết quả được backend xác nhận.

Tiết kiệm công sức chỉ được coi là đạt khi không tăng lỗi nghiệp vụ, bỏ kiểm tra bắt buộc, nhầm sinh viên/hồ sơ, lộ dữ liệu hoặc tạo quyết định không có căn cứ. Quyền, phạm vi hàng đợi, người đang phụ trách, xác nhận và thẩm quyền phê duyệt vẫn theo quy trình hiện hành.

## 2. Hiện trạng quan sát từ mã nguồn

- StaffTicketWorkspace có bản khai/tệp, checklist, dữ liệu đối chiếu, nguồn, bản nháp phản hồi, proposal apply/undo và kiểm tra snapshot trước gửi.
- staff-policy có reviewReadiness kiểm tra kết quả thiếu/chưa kiểm tra/lỗi thời; actionBlock chặn hoàn tất nếu checklist hoặc dữ liệu thay đổi chưa được xử lý. Đây là nền tảng cần giữ.
- Service/certificate APIs có ownership/queue, assigned officer, version, preview/confirm/idempotency và audit tùy luồng. Cần xác định luồng đang phục vụ cán bộ thực tế trước tích hợp.
- StaffTicketQueue.tsx có INTAKE_CHECKLIST_GATES ghi cứng confidence 99.8%, 97.4% và các nhận định danh tính, con dấu/chữ ký, SLA 24h. Không được coi những constants này là độ chính xác đo được hoặc kết quả xác minh hồ sơ thật. Cần thay phần hiển thị bằng evidence thực tế khi triển khai capability tương ứng; chưa có evidence thì hiển thị chưa xác minh, phân biệt demo rõ.
- Chưa chạy UI/tests trong đợt đề xuất; sự tồn tại các thành phần không chứng minh bản triển khai đã hoạt động hoặc đầy đủ.

## 3. Chín năng lực ưu tiên

### 3.1. Hàng đợi hỗ trợ chọn việc

Mỗi hồ sơ có tóm tắt mục đích, loại thủ tục, cán bộ/đơn vị phụ trách, thời điểm nhận, hạn có nguồn, phần đang chờ và đề xuất bước tiếp theo. Lọc theo việc có thể xử lý, cần xem xét, thiếu dữ liệu và chờ sinh viên/cán bộ khác.

Ưu tiên theo quy tắc được tổ chức xác định, thời hạn có căn cứ và trạng thái; nêu lý do thay vì điểm khẩn cấp tùy ý do model tạo. Hồ sơ có dấu hiệu trùng chỉ gắn cờ ứng viên để kiểm tra, không tự gộp/xóa/từ chối. Chỉ xem trong scope của cán bộ.

### 3.2. Bộ hồ sơ làm việc được chuẩn bị sẵn

Khi cán bộ mở hồ sơ, trợ lý chuẩn bị: người yêu cầu và mục đích; nội dung/tài liệu đã nộp; trạng thái hiện tại; timeline; dữ liệu hệ thống đối chiếu; phần thiếu/xung đột; checklist theo phiên bản quy trình; nguồn liên quan và bản nháp bước tiếp theo.

Mỗi nội dung quan trọng dẫn tới trường nguồn/tài liệu/trang/phiên bản. Cán bộ mở được bản gốc từ từng nhận định, không chỉ đọc một bản tóm tắt khó xác minh. Chuẩn bị trên dữ liệu được phép, có version/freshness; snapshot thay đổi làm kết quả liên quan stale.

### 3.3. Kiểm tra tiêu chí có bằng chứng

| Thành phần | Vai trò |
| --- | --- |
| Dữ liệu hệ thống có thẩm quyền | Danh tính, trạng thái, dữ liệu học vụ hiện hành và biên nhận theo nguồn được cấp |
| Quy tắc xác định | Required fields, định dạng, thời hạn, version, trạng thái và điều kiện được cấu hình |
| AI | Trích xuất, tóm tắt, tìm đoạn liên quan, so sánh nội dung và đề xuất nhận định |
| Cán bộ/quy trình phê duyệt | Kiểm tra bắt buộc, xử lý ngoại lệ và quyết định thuộc thẩm quyền |

Kết quả mỗi tiêu chí gồm: dữ liệu, quy tắc/nguồn hiệu lực, evidence, loại kiểm tra, thời điểm và trạng thái được xác minh. Dùng trạng thái rõ như có căn cứ hệ thống, đề xuất cần cán bộ kiểm tra, thiếu căn cứ, mâu thuẫn hoặc nguồn lỗi thời. Không biến confidence của model thành kết luận hợp lệ; OCR/nhận diện hình ảnh không tự xác thực con dấu hoặc chữ ký.

### 3.4. Xử lý tập trung vào điểm cần chú ý

Đưa danh sách vấn đề lên trước: phần thiếu, thông tin không khớp, tài liệu khó đọc, nguồn hết hiệu lực và lựa chọn cần quyết định. Những phần có nguồn hệ thống và rule checks được trình bày gọn, mở chi tiết khi cần.

Cán bộ vẫn thực hiện kiểm tra/xác nhận bắt buộc. Không tự tick thay hoặc bypass readiness. Khi hồ sơ được bổ sung, so sánh trước/sau và làm lại kiểm tra bị ảnh hưởng; không yêu cầu đọc lại toàn bộ nếu kết quả không đổi và còn hiệu lực theo policy.

### 3.5. Soạn nội dung và văn bản theo đúng hồ sơ

Chuẩn bị yêu cầu bổ sung, phản hồi, ghi chú nội bộ, dự thảo kết quả và bản bàn giao từ dữ liệu đã kiểm tra, template đang hiệu lực và những lựa chọn cán bộ nêu rõ. Yêu cầu bổ sung liệt kê chính xác mục cần cung cấp, lý do/căn cứ và bước thực hiện; tránh yêu cầu sinh viên nộp lại tài liệu đã đủ.

Gửi sinh viên và ghi chú nội bộ là hai kênh riêng. Cá nhân hóa giọng văn không thay điều kiện, căn cứ hoặc tiết lộ nội dung nội bộ. Cán bộ có thể yêu cầu sửa đúng đoạn; manual edits và template quy định được giữ. Preview có recipient, hồ sơ, payload và version trước gửi.

### 3.6. Thao tác gộp có kiểm soát

Cho phép lọc/gom các hồ sơ trong scope theo cùng loại việc để chuẩn bị hàng loạt: tóm tắt, kiểm tra rule, draft thông báo hoặc tài liệu. Mỗi hồ sơ vẫn có dữ liệu, evidence, người nhận, trạng thái và điều kiện riêng; không sao chép một quyết định cho mọi hồ sơ chỉ vì giống tiêu đề.

Nếu workflow và quyền hỗ trợ thao tác gộp, cán bộ xem exact target list, preview từng nội dung cần thiết và xác nhận phạm vi cụ thể. Server kiểm tra từng item, version, nguồn, quyền và idempotency khi thực hiện. Item thay đổi/bị chặn được báo riêng; báo kết quả từng item và phục hồi retry không gửi hai lần. Chưa có policy/capability thì chỉ chuẩn bị hàng loạt, không phê duyệt/gửi hàng loạt.

### 3.7. Trợ lý hiểu ý định cán bộ tại thao tác

Hỗ trợ câu như: "Tóm tắt phần khác biệt sau bổ sung", "Chuẩn bị yêu cầu bổ sung cho các mục chưa đủ căn cứ", "Tìm quy định đang áp dụng cho hồ sơ này" hoặc "Soạn bàn giao phần chưa xử lý".

Liên kết yêu cầu với case IDs, action, constraints và scope. Khi có nhiều hồ sơ/mục đích có thể hiểu khác, làm rõ trước ghi. Trợ lý xuất hiện ở queue, detail, checklist, soạn thảo, lỗi và bàn giao; không buộc cán bộ sao chép hồ sơ sang chat. Gợi ý dùng context tối thiểu, không đọc tất cả hồ sơ ngoài scope.

### 3.8. Bàn giao và theo dõi việc đang chờ

Tóm tắt đã làm/chưa làm, chứng cứ, nguồn phiên bản, lý do chuyển, thời hạn có căn cứ và next action. Giữ lịch sử, owner và internal/public boundaries. Chuyển đơn vị hoặc gửi cần kiểm tra quyền và xác nhận theo workflow.

Theo dõi hồ sơ được cấp, cảnh báo nguồn/hồ sơ thay đổi, công việc gần hạn và vấn đề bị chặn. Không nhắc khi trạng thái không đổi; hạn không có nguồn thì báo chưa xác minh, không tự hứa SLA.

### 3.9. Cá nhân hóa môi trường làm việc

Cán bộ chọn đơn vị/phạm vi được cấp, loại việc ưu tiên, bố cục, cách xem bằng chứng, template hợp lệ, độ dài gợi ý và mức chủ động. Có danh sách công việc đang dở và nhớ lựa chọn trình bày khi được phép.

Không tự học quy định chung từ một lần cán bộ sửa câu trả lời. Sửa cá nhân chỉ ảnh hưởng nháp/sở thích phù hợp; knowledge/template/policy dùng chung đi qua quy trình ứng dụng hiện hành. Memory không chứa hồ sơ sinh viên để tái dùng cho người khác.

## 4. Trải nghiệm xử lý một hồ sơ

1. Mở hồ sơ từ queue: xem mục đích, trạng thái và vấn đề cần chú ý.
2. Trợ lý chuẩn bị checklist cùng evidence từ nguồn hiện hành.
3. Cán bộ xem các điểm cần kiểm tra/ngoại lệ và thực hiện những xác nhận bắt buộc.
4. Chọn hành động hoặc nêu yêu cầu; trợ lý chuẩn bị đúng bản nháp phản hồi/kết quả.
5. Cán bộ sửa nếu cần, xem preview và xác nhận hành động cụ thể.
6. Server kiểm tra lại quyền, assigned officer, nguồn, version và idempotency; trả receipt/state đã commit.
7. Mở hồ sơ tiếp theo với vị trí queue được giữ; hồ sơ đang chờ có next step rõ.

Không đặt mục tiêu mọi hồ sơ xử lý bằng một click. Mục tiêu là bỏ việc tìm kiếm, sao chép, nhập lại và đọc lại không cần thiết, đồng thời giữ những quyết định có tác động và kiểm tra bắt buộc.

## 5. Độ tin cậy và thiết kế dữ liệu

Mỗi finding cần case/resource version, criterion ID, rule/source version, evidence locator/hash khi phù hợp, dữ liệu đối chiếu, loại automated check/AI proposal/officer review, actor/timestamp và trạng thái. Draft action cần exact payload, target, base version và trạng thái confirmation/receipt.

Không dùng chữ "AI đã xác minh" cho một nhận định chưa có check tương ứng. Cần audit metadata đủ xác định ai đã kiểm tra/sửa/chốt gì và phiên bản nguồn nào; không dump toàn bộ nội dung nhạy cảm vào telemetry. Phân quyền theo hàng đợi, tài nguyên và assignment; scoped tool authorization kiểm tra ngoài model ở thời điểm execution.

Tài liệu sinh viên, OCR, hồ sơ cũ và nội dung truy xuất đều là dữ liệu, không phải chỉ dẫn cấp quyền hoặc đổi workflow. Dùng test injection, source change, wrong recipient và stale approval, ngoài unit tests của summarization.

## 6. Thứ tự đề xuất triển khai

| Đợt | Phạm vi | Giá trị và điều kiện |
| --- | --- | --- |
| 0 | Xác định staff route/build; phân biệt demo; kiểm tra integrity của evidence/confidence/status | Tránh tin vào UI giả hoặc sửa sai runtime |
| 1 | Bộ hồ sơ làm việc, summary có nguồn, checklist rule-driven, draft yêu cầu bổ sung/phản hồi | Giảm đọc/tìm/soạn; cán bộ xác minh trực tiếp được |
| 2 | Diff sau bổ sung, đề xuất next action, intent/context trong mọi thao tác, bàn giao | Giảm đọc lại và việc kể lại ngữ cảnh |
| 3 | Chuẩn bị gộp, thực thi gộp nếu policy/capability cho phép, cảnh báo workload và nguồn thay đổi | Tăng throughput mà giữ kiểm tra từng hồ sơ |

Pilot ưu tiên xin cấp giấy, yêu cầu bổ sung và phản hồi hỗ trợ. Hồ sơ có đánh giá học thuật/phúc khảo chỉ mở mức đề xuất sau khi có dữ liệu/nguồn/quy tắc và tiêu chí nghiệp vụ được xác minh. Chưa chốt số ngày, phần trăm tiết kiệm hoặc tỷ lệ đúng trước baseline.

## 7. Nghiệm thu

- Đo thời gian cán bộ thao tác, tìm nguồn, đọc lại, soạn; số trường phải nhập lại; số hồ sơ có kết quả hợp lệ; correction/reopen/wrong-recipient/duplicate rates. Tách thời gian sinh viên chờ bổ sung hoặc đơn vị khác xử lý.
- So sánh cùng loại việc/độ phức tạp; tách hồ sơ thường và ngoại lệ; cán bộ tham gia đánh giá usefulness, khả năng kiểm tra căn cứ và thao tác thật.
- Các ca: source hết hiệu lực, thiếu evidence, OCR sai, hồ sơ bổ sung đổi version, hai cán bộ cùng xử lý, assignment thay đổi, permission revoke, confirmation payload changed, batch partial failure/retry và nội dung công khai lẫn note nội bộ.
- Không giảm thời gian bằng cách bỏ kiểm tra bắt buộc hoặc biến "đã tick đủ checklist" thành "đúng 100%". Quyền, dữ liệu, nguồn và chống trùng phải đạt trước khi mở capability tương ứng.
- Độ tin cậy phải đo trên từng criterion/action, không chỉ average accuracy hoặc model confidence; báo những capability/source còn chưa xác minh.

## 8. Nguồn đối chiếu

- Mã nguồn staff-policy.ts, StaffTicketWorkspace.tsx, StaffTicketQueue.tsx và service/certificate application trong workspace; chưa kiểm chứng runtime.
- [OWASP AI Agent Security](https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html): scoped tools, exact action authorization, evidence và human oversight.
- [AgentDojo](https://arxiv.org/abs/2406.13352): kiểm thử agent gọi công cụ trên dữ liệu không đáng tin cậy.

## 9. Thiết kế tối ưu quy trình và kiểm chứng từng bước

### 9.1. Quy trình và quy tắc có phiên bản dùng chung

Mỗi loại thủ tục có định nghĩa rõ: mục đích hỗ trợ, trường/tài liệu bắt buộc, nguồn đối chiếu, tiêu chí, bước/trạng thái hợp lệ, thẩm quyền, mẫu kết quả và những xác nhận cần thiết. Cùng một định nghĩa phục vụ trợ lý sinh viên, trợ lý cán bộ và backend validation, tránh mỗi bề mặt tự hiểu quy trình một kiểu.

Phân biệt phiên bản nguồn mới nhất với phiên bản áp dụng cho một hồ sơ theo mốc nghiệp vụ được cấu hình. Có khoảng hiệu lực và quy tắc chọn phiên bản; không tự áp quy định mới cho hồ sơ cũ hoặc giữ quy định cũ khi không còn phù hợp. Khi không xác định được phiên bản áp dụng, chặn kết luận tương ứng và nêu phần cần xác minh. Việc thay đổi quy trình/quy tắc vẫn theo quyền và cơ chế ứng dụng hiện hành.

### 9.2. Chuẩn bị trước trong phạm vi được phép

Khi một hồ sơ được tiếp nhận hoặc bổ sung, worker có thể chuẩn bị dữ liệu/tóm tắt/checklist/draft theo capability đã cấp. Chuẩn bị không phê duyệt/gửi/thay đổi trạng thái hành chính. Chỉ xử lý hồ sơ trong phạm vi dịch vụ và sử dụng kết quả sau kiểm tra quyền tài khoản hiện tại.

Cache kết quả theo case version, document hashes, rule/source/template versions và loại tác vụ. Sự kiện mới làm hết hiệu lực phần liên quan; bản tóm tắt lỗi thời có trạng thái rõ, không được dùng như kết quả hiện hành. Hạn mức hàng đợi/chi phí/retry và ưu tiên theo policy; không chạy model liên tục cho cả kho dữ liệu hoặc tiếp cận dữ liệu ngoài scope.

### 9.3. Quan hệ giữa dữ liệu, tiêu chí và kết quả

Lưu quan hệ: dữ liệu/tài liệu nào hỗ trợ tiêu chí nào; tiêu chí nào quyết định readiness; nguồn/template nào tạo đoạn kết quả nào. Có thể dùng bảng quan hệ trong database hiện có, chưa cần graph database.

Khi sinh viên bổ sung một tài liệu, đánh dấu đúng các findings, summary segments và draft sections bị ảnh hưởng. Kiểm tra lại các phần đó; giữ các kết quả khác chỉ khi nguồn, phiên bản và điều kiện hiệu lực còn hợp lệ. Các mốc kiểm tra toàn bộ hoặc xác nhận bắt buộc của workflow vẫn được thực hiện.

Mỗi kết luận quan trọng truy ngược được đến dữ liệu, hoạt động kiểm tra và cán bộ/hệ thống tạo nó. W3C PROV là nguồn tham khảo cho các quan hệ provenance này; không bắt buộc áp dụng nguyên bộ tiêu chuẩn trong MVP.

### 9.4. Trạng thái sẵn sàng có lý do

Phân nhóm công việc theo lý do có thể hành động:

- Đủ căn cứ để cán bộ xem xét: thông tin/quy tắc đã đối chiếu; những xác nhận bắt buộc vẫn cần hoàn tất.
- Cần xác minh: có mâu thuẫn, tài liệu khó đọc hoặc nhận định chưa được xác nhận.
- Cần bổ sung: thiếu thông tin/tài liệu đã xác định theo quy trình.
- Đang chờ: chờ sinh viên, đơn vị khác hoặc điều kiện nghiệp vụ.
- Bị chặn: thiếu quyền, nguồn/version không hợp lệ hoặc lỗi hệ thống.

Trạng thái do kết quả kiểm tra và workflow xác định, không chỉ bởi model confidence. Hiển thị reason/next action; không biến việc đủ số tick thành chứng nhận độ đúng 100%. Không tự từ chối hồ sơ vì một điểm nghi ngờ hoặc thiếu evidence do hệ thống lỗi.

### 9.5. Yêu cầu bổ sung có cấu trúc, nối sang trợ lý sinh viên

Trước khi đề nghị bổ sung, kiểm tra các mục thiếu đã biết trong phạm vi workflow để gom thành một yêu cầu: mục nào, thiếu gì, căn cứ, tài liệu/định dạng chấp nhận và bước thực hiện. Không gom suy đoán thành yêu cầu thừa hoặc đòi lại tài liệu đã có.

Lưu yêu cầu theo item IDs liên kết với criterion/field. Nội dung công khai đã được cán bộ xác nhận có thể trở thành checklist hướng dẫn cho trợ lý sinh viên; ghi chú nội bộ không chuyển sang. Khi bổ sung, map đúng item, hiển thị trước/sau, giữ mục đã giải quyết và chỉ nêu mục còn thiếu.

Đây là một workflow nối hai phía; tránh cán bộ viết một đoạn chung chung khiến sinh viên tiếp tục hỏi và nộp sai nhiều lần.

### 9.6. Bộ kiểm tra trước thực hiện nằm ngoài model

Trước gửi/chốt/phát hành/chuyển hoặc các thao tác có tác động, backend kiểm tra: actor/queue/assignment, case/source/rule/template version, payload schema và giá trị trọng yếu, readiness/mandatory reviews, người nhận, phạm vi xác nhận và idempotency.

Thông tin tên/MSSV/hồ sơ/người nhận phải lấy từ nguồn đã đối chiếu và bind vào payload. Nội dung quyết định có cấu trúc: lựa chọn cán bộ, facts, căn cứ, giải thích và template; đoạn văn AI không tự xác lập outcome. Người dùng thay payload/recipient hoặc nguồn cần thiết thay đổi thì preview cũ không còn dùng được theo policy.

Confirmation, business transition, audit/receipt và delivery cần nhất quán theo transaction/outbox phù hợp. Không gửi thành công rồi mới phát hiện việc ghi trạng thái thất bại. Retry khi timeout phải đọc lại receipt, không tạo yêu cầu mới không kiểm tra. Audit log chứa metadata cần thiết; quyền đọc các evidence chi tiết vẫn được kiểm soát.

Hai model đồng ý không thay thế source/domain/authorization checks. OWASP Transaction Authorization là nguồn đối chiếu cho significant transaction data, server enforcement và kiểm tra lại quyền trước execution.

### 9.7. Lưu nháp bền vững và chống làm trùng giữa cán bộ

Trong mã hiện tại, useStaffDraft giữ bản đang soạn trong Map của phiên và có bước save riêng; StaffCaseClaimService có lock/dictionaries trong process. Không suy ra các cơ chế đó đủ cho reload/crash hoặc nhiều instance.

Đề xuất server autosave nháp theo officer/case/version, saved/pending/error rõ; debounce và giữ manual edits, kiểm soát concurrent tabs. Cảnh báo dữ liệu chưa lưu hiện có vẫn được giữ khi cần; không báo saved trước acknowledgement. Lỗi lưu cho tiếp tục soạn trong phạm vi phù hợp và chỉ rõ phần chưa persist.

Claim/assignment và thực thi phải kiểm soát cạnh tranh ở storage bền vững khi nhiều process/instance: hai cán bộ không cùng commit một bước trái quy trình. Chuyển người phụ trách hoặc quyền bị thu hồi làm nháp/proposal cũ phải kiểm tra lại trước thực thi; không xóa nháp. Giữ vị trí queue, keyboard navigation và đưa tới công việc tiếp theo sau khi receipt đã xác nhận.

### 9.8. Thao tác gộp gồm chuẩn bị, kiểm tra và thực hiện từng hồ sơ

Chọn danh sách trong scope → chuẩn bị riêng từng item → hiển thị kết quả preflight → cán bộ xem/xác nhận danh sách cụ thể nếu capability cho phép → backend revalidate từng item → trả kết quả và receipt từng item.

Định nghĩa rõ trường hợp phần thành công/phần bị chặn trước khi xác nhận. Item stale không thực hiện; không mở rộng target list sau confirmation. Retry item đã commit dùng receipt/idempotency, chỉ xử lý phần còn chưa thực hiện theo quyền/xác nhận còn hiệu lực. Không tự gộp/xóa hồ sơ hoặc hủy quyết định đã có để có kết quả batch đẹp.

### 9.9. Tìm điểm nghẽn theo trạng thái thực tế

Đo riêng thời gian cán bộ thao tác, thời gian chờ sinh viên, thời gian chờ đơn vị khác và thời gian hệ thống. Theo dõi số lần bổ sung, số lần chuyển, tuổi hồ sơ, lý do bị chặn và tỷ lệ mở lại vì sai/thiếu.

Dashboard đề xuất việc cần làm theo scope: hồ sơ gần hạn có căn cứ, yêu cầu bổ sung chưa trả lời, công việc có đủ dữ liệu sau cập nhật và những lỗi nguồn ảnh hưởng nhiều hồ sơ. Không xếp hạng cán bộ bằng số hồ sơ thô mà bỏ độ phức tạp và thời gian chờ ngoài kiểm soát.

Gợi ý cải tiến quy trình từ số liệu tổng hợp; đổi policy/template/routing dùng chung vẫn cần đường thay đổi hợp lệ của tổ chức. Không tự nới tiêu chí khi backlog cao.

## 10. Các hạng mục nâng cao để phân rã vào kế hoạch tiếp theo

Các ID dưới đây là đề xuất hạng mục, chưa phải task đã chạy hoặc phụ thuộc đã verified trong backlog tổng thể.

| ID | Đầu ra | Phụ thuộc logic | Điều kiện đạt |
| --- | --- | --- | --- |
| ST-01 | Baseline staff runtime/nguồn/thời gian và integrity của UI | Khảo sát đường chạy | Phân biệt demo và fact; đo đúng active/wait time |
| ST-02 | Workflow/rules/templates có phiên bản dùng chung | ST-01 | Cùng hồ sơ ra cùng checks giữa UI và backend; mốc hiệu lực đúng |
| ST-03 | Evidence và quan hệ với criteria/output | ST-02 | Claim truy nguồn; dữ liệu thiếu không bị xem là đã đủ |
| ST-04 | Chuẩn bị trước và recheck phần bị ảnh hưởng | ST-03 | Cache không stale; thay nguồn làm invalidation đúng; có cost bounds |
| ST-05 | Workspace readiness/ngoại lệ, context và next action | ST-02–04 | Hiển thị đúng blockers; giữ mandatory checks; nguồn mở được |
| ST-06 | Autosave/version/claim bền vững | ST-01, nền tảng storage | Reload/concurrent officers không mất hoặc ghi đè nháp, không xử lý trùng |
| ST-07 | Yêu cầu bổ sung typed và nối trợ lý sinh viên | ST-03, ST-05 | Hỏi đúng một tập missing đã biết; bổ sung map đúng item |
| ST-08 | Draft kết quả và kiểm tra trước thực hiện | ST-02, ST-03, ST-06 | Fields/recipient/source/confirmation/version bind đúng; receipt đáng tin |
| ST-09 | Batch chuẩn bị/preflight/execute per item | ST-05, ST-08 | Partial outcomes rõ; không target drift hoặc duplicate khi retry |
| ST-10 | Bàn giao và dashboard điểm nghẽn | ST-05, ST-07, ST-08 | Context đủ trong scope, internal/public đúng, metrics phản ánh wait causes |
| ST-11 | Shadow evaluation và kiểm thử lỗi/đối kháng | Các capability định đánh giá | AI chưa thực thi action; đối chiếu nguồn và người đánh giá phù hợp |
| ST-12 | Pilot cán bộ và rollout theo capability | ST-11 và hạng mục cần mở | Chất lượng đạt cùng lúc với giảm công sức; rollback feature giữ dữ liệu |

Ưu tiên chuỗi ST-01 → ST-02 → ST-03 → ST-04/ST-05 → ST-06–08; đánh giá từng phần ngay khi có. Batch/dashboard mở sau khi luồng đơn lẻ đạt. Đây là thứ tự kỹ thuật, không bổ sung approval gate tài liệu.

## 11. Kiểm chứng độ chính xác và hiệu quả nâng cao

- Chạy shadow trên fixture/môi trường được phép: AI chuẩn bị, không gửi/chốt; so với kết quả có nguồn và review nghiệp vụ. Người đánh giá làm một số ca không thấy đề xuất trước để phát hiện lệ thuộc gợi ý. Khác với cán bộ không tự đồng nghĩa AI sai hoặc đúng; đối chiếu căn cứ.
- Dataset chia hồ sơ thường, ngoại lệ, nguồn thiếu/cũ/mâu thuẫn, bổ sung nhiều lần, tài liệu khó đọc, hai cán bộ, mất mạng và batch. Có outcome/criterion/evidence mong đợi; không dùng model tự chấm làm bằng chứng duy nhất.
- Kiểm thử nguồn/quy tắc đổi hiệu lực; material facts bị OCR sai; phụ thuộc criteria invalidation; manual edits; case/recipient nhầm; grant revoke; audit/DB/delivery failure; commit timeout và retry; token/target drift; chỉ dẫn độc hại trong tài liệu/memory.
- Metrics ưu tiên: thời gian thao tác theo loại hồ sơ; thời gian tìm căn cứ; số lần đọc lại; số vòng bổ sung; first-pass completion; số sửa trọng yếu; false-ready/missed-conflict/wrong-recipient/duplicate/reopen; cost per valid completion. Báo cohort/sample và giới hạn, không hứa phần trăm trước baseline.
- Lấy mẫu chất lượng bổ sung theo policy, tăng review khi phát hiện sai có tính hệ thống; không thay kiểm tra bắt buộc bằng sampling. Không giữ capability tự động khi có lỗi quyền, sai người nhận hoặc kết luận nghiêm trọng đã biết chưa xử lý.
- Mở dần theo loại thủ tục và mức read/prepare/execute được phép. Feature lỗi được ngừng qua cấu hình phát hành riêng; giữ lịch sử, evidence, drafts, receipts, manual path và safety mechanisms.

Nguồn đối chiếu bổ sung: [W3C PROV Overview](https://www.w3.org/TR/prov-overview/) cho provenance; [OWASP Transaction Authorization](https://cheatsheetseries.owasp.org/cheatsheets/Transaction_Authorization_Cheat_Sheet.html) cho binding và execution checks. Chưa áp dụng hoặc chạy kiểm thử các thay đổi ứng dụng trong lần cập nhật tài liệu này.
