# Đề xuất nâng cấp trợ lý AI Campus 24/7

Ngày: 14/10/2026. Trạng thái: đề xuất triển khai, chưa triển khai hoặc nghiệm thu.

## 1. Mục tiêu và phạm vi

Xử lý ba trải nghiệm người dùng: hội thoại có thể mở lại đáng tin cậy; câu trả lời dễ đọc và hỗ trợ hành động; trợ lý có cấu hình riêng cho từng tài khoản và chỉ sử dụng dữ liệu/công cụ trong phạm vi được cấp.

Phân biệt bốn lớp:

1. Lịch sử hội thoại: nội dung được lưu và có thể mở lại.
2. Ngữ cảnh hội thoại: các lượt trước được sử dụng khi trả lời tiếp trong cùng cuộc trò chuyện.
3. Bộ nhớ cá nhân: sở thích hoặc thông tin được người dùng cho phép sử dụng giữa nhiều cuộc trò chuyện.
4. Quyền thực hiện: điều kiện để đọc một nguồn hoặc chạy một thao tác; nội dung chat và bộ nhớ không tạo ra quyền.

Đợt phân tích này chỉ đọc mã nguồn và tạo tài liệu đề xuất. Chưa kiểm tra giao diện đang chạy, cấu hình triển khai, cơ sở dữ liệu thực tế hoặc tài khoản người dùng; chưa chạy bộ kiểm thử. Các nhận định dưới đây là quan sát từ mã nguồn, không phải kết luận về bản triển khai đang phục vụ người dùng.

## 2. Những gì đã có và khoảng trống

| Quan sát từ mã nguồn | Ý nghĩa đối với đề xuất |
| --- | --- |
| `apps/web/src/lib/student-chat.ts` lưu các thread vào localStorage, đọc lại và giữ dữ liệu cũ nếu không giải mã được. | Đã có lưu trên thiết bị, nhưng chưa đáp ứng lịch sử theo tài khoản và đồng bộ thiết bị. Khóa lưu chứa mode và user ID; đổi mode hoặc danh tính có thể tạo một tập lịch sử khác. Đây là giả thuyết cần tái hiện, không phải nguyên nhân đã xác nhận. |
| `apps/web/src/lib/assistant-context.tsx` khởi tạo store theo mode/user, mặc định dùng guidanceAdapter; yêu cầu respond gồm câu hỏi và ngữ cảnh trang, không có danh sách lượt chat trước. | Lịch sử hiển thị và ngữ cảnh trả lời chưa nối thành một luồng trong trợ lý sinh viên mặc định. Cần adapter API dùng conversation ID và đọc lịch sử phía máy chủ. |
| `apps/web/src/components/student/StudentRuntime.tsx` có điều hướng `/chat` sang `/student/assistant` khi StudentRuntime áp dụng cho tài khoản sinh viên. | Có thể người dùng đang dùng luồng sinh viên thay vì ChatPage có kết nối streaming. Cần xác định đúng bản frontend và route đang chạy trước khi sửa. |
| `apps/web/src/components/student/AssistantWorkspace.tsx` có danh sách hội thoại; đoạn mô tả nói dữ liệu được đồng bộ bảo mật theo phiên. | Không nên diễn đạt như đã có đồng bộ máy chủ nếu đường lưu thực tế mới là localStorage. UI cần phản ánh đúng mức bảo đảm lưu trữ. |
| `apps/web/src/components/student/AssistantConversation.tsx` hiển thị reply.text bằng một thẻ p có whitespace-pre-wrap. | Xuống dòng có thể được giữ nhưng heading, bảng, danh sách Markdown chưa có cấu trúc hiển thị tương ứng. |
| `apps/web/src/features/chat/ChatPanel.tsx` đã dùng ReactMarkdown và remark-gfm; package.json đã có hai thư viện. | Tái sử dụng bộ hiển thị và phụ thuộc hiện có, bổ sung một renderer chung cho các bề mặt trợ lý. |
| `apps/web/src/app/chat/page.tsx` tạo conversation, lưu ID vào URL và khôi phục messages theo ID. | Đã có nền tảng tiếp tục một cuộc chat cụ thể; chưa thấy endpoint liệt kê toàn bộ conversation của tài khoản trong phần presentation đã kiểm tra. URL riêng lẻ chưa thay thế lịch sử có thể tìm và mở lại. |
| `ConversationMessageService` mặc định dùng InMemoryConversationRepository khi không được inject repository. `main.py` gọi create_app() không truyền repository. | Entry point mặc định có nguy cơ mất lịch sử khi process restart. Không được suy ra mọi launcher đều như vậy. |
| Có SQLiteConversationRepository; các launcher public/advanced/multi-agent inject SQLite. Có PostgresConversationRepository nhưng phải cấp pool rõ ràng. | Có cơ chế lưu bền vững để mở rộng; cần kiểm tra launcher thực tế, wiring và storage trước khi lựa chọn. |
| ConversationRecord có retention_expires_at; create_conversation mặc định 30 ngày; list_owned_page kiểm tra hết hạn. | Lịch sử có thể trở nên không đọc được do chính sách hết hạn ngay cả khi dữ liệu còn trên storage. Cần thống nhất thời hạn, hiển thị cho người dùng và kiểm tra luồng lưu trữ thực tế. Không tự đổi thành lưu vô thời hạn. |
| PrivacyConsentService có OPTIONAL_PERSONALIZATION nhưng consent hiện lưu trong danh sách bộ nhớ của service; trang privacy đang gửi QUALITY_FEEDBACK và có fallback/demo. | Có khái niệm consent, nhưng chưa đủ để xem là cài đặt trợ lý bền vững hoặc grant công cụ. Cần persist, đọc lại, thu hồi và kiểm tra thực thi. |

## 3. Trải nghiệm sản phẩm đề xuất

### 3.1. Hội thoại đáng tin cậy

- Lịch sử truy cập dễ thấy trên desktop; drawer trên mobile. Có Trò chuyện mới, tìm kiếm theo tiêu đề, đổi tên, ghim, lưu trữ và tiếp tục.
- Phân nhóm theo thời gian từ timestamp máy chủ. Tin nhắn và danh sách đều phân trang; không tải toàn bộ lịch sử trước khi mở cuộc chat.
- Hiển thị trạng thái: Đang gửi, Đã lưu, Chưa lưu được, Đang trả lời, Hoàn tất, Đã dừng, Phản hồi bị gián đoạn. Chỉ báo Đã lưu sau xác nhận ghi bền vững.
- Tải lại, rời trang, hết phiên và restart server không làm mất các lượt đã được xác nhận lưu trong thời hạn chính sách.
- Một cuộc chat được mở trên thiết bị khác sau đăng nhập cùng tài khoản; các tài khoản hoặc tenant khác không truy cập được.
- Có lựa chọn chat tạm thời: không xuất hiện trong lịch sử dài hạn và không tạo/sử dụng memory cá nhân. UI phải mô tả trung thực phần lưu vận hành tối thiểu và thời hạn nếu có.
- Lưu trữ chỉ ẩn khỏi danh sách chính. Xuất dữ liệu và yêu cầu xóa là luồng riêng có phạm vi, xác nhận và trạng thái xử lý; tắt memory hoặc bắt đầu chat mới không xóa lịch sử.

### 3.2. Trả lời dễ đọc, phù hợp câu hỏi

Quy tắc trình bày mặc định:

- Câu hỏi đơn giản: trả lời trực tiếp trong vài câu.
- Hướng dẫn: kết luận ngắn, các bước có thứ tự, điều kiện hoặc lưu ý và nguồn tương ứng khi cần.
- So sánh: bảng ngắn, có cách đọc trên mobile.
- Theo dõi hồ sơ: thẻ trạng thái, thời điểm cập nhật, phần việc tiếp theo và nút dẫn đúng hồ sơ.
- Hỗ trợ điền biểu mẫu: thẻ đề xuất có trước/sau và nút Áp dụng; nút này dùng payload đã được backend kiểm tra.
- Trả lời dài: tóm tắt trước và phần chi tiết có thể mở rộng; không ép mọi câu trả lời vào cùng một mẫu nhiều mục.

Ví dụ minh họa bố cục, không phải hướng dẫn nghiệp vụ đã xác minh:

> **Bạn có thể chuẩn bị hồ sơ theo các bước dưới đây.**
>
> 1. Chọn loại yêu cầu.
> 2. Kiểm tra các thông tin và tài liệu cần bổ sung.
> 3. Xem bản nháp rồi xác nhận nộp.
>
> **Cần kiểm tra:** điều kiện và thời hạn theo thông báo đang có hiệu lực.
>
> Nguồn liên quan được gắn vào từng nội dung có căn cứ. Nút hành động: Mở biểu mẫu.

Hai phần cần làm đồng thời: backend/adapter tạo nội dung có cấu trúc; frontend render và áp dụng typography. Markdown renderer không tự biến một đoạn văn thành nội dung được tổ chức tốt.

Tái sử dụng react-markdown + remark-gfm, không bật HTML thô hoặc cho mô hình tạo mã thực thi. Link, ảnh và component tùy chỉnh phải theo chính sách cho phép. CTA, trạng thái hồ sơ và proposal dùng dữ liệu có schema, không suy đoán quyền hay hành động từ từ khóa trong văn bản.

MVP dùng Markdown có kiểm soát và metadata nguồn/hành động riêng. Bổ sung response blocks như summary, steps, table, notice, source và action khi có nhu cầu nghiệp vụ; version hóa schema và giữ fallback cho tin nhắn cũ. Không cần tạo hệ thống block phức tạp trước khi cải thiện renderer hiện có.

### 3.3. Cài đặt trợ lý theo tài khoản

Nút Cài đặt trợ lý ở header mở panel gồm bốn vùng:

| Vùng | Cấu hình |
| --- | --- |
| Cách trả lời | Ngôn ngữ, tên muốn được gọi, cách xưng hô, mức độ ngắn/chi tiết, ưu tiên các bước/bảng, hướng dẫn cá nhân. Có xem trước trước khi lưu. |
| Bộ nhớ | Cho phép ghi nhớ hoặc tắt; xem các mục đã nhớ, sửa/quên từng mục; mỗi mục có nguồn, ngày ghi và phạm vi. |
| Dữ liệu và công cụ | Xem danh mục capability được triển khai; nguồn/phạm vi được phép, thời hạn grant, trạng thái kết nối, thu hồi. Capability chưa có backend không được hiển thị như đang dùng được. |
| Lịch sử và riêng tư | Chế độ lưu chat mới, chat tạm thời, thời hạn lưu, xuất dữ liệu, yêu cầu xóa và trạng thái xử lý. |

Thiết lập mặc định đề xuất: tiếng Việt, trả lời ngắn và có cấu trúc; không ghi nhớ giữa các cuộc chat cho đến khi người dùng bật; nguồn dữ liệu riêng và công cụ thao tác chưa được cấp mặc định. Lưu lịch sử thông thường theo lựa chọn được thông báo rõ cho người dùng và chính sách của trường; không coi lựa chọn lưu lịch sử là đồng ý dùng dữ liệu cho memory hoặc cải thiện mô hình.

Tùy chỉnh chỉ ảnh hưởng cách trình bày và các lựa chọn hợp lệ. Các chỉ dẫn cá nhân không thay đổi quy định học vụ, quyền truy cập, cơ chế kiểm chứng nguồn hoặc yêu cầu xác nhận hành động.

## 4. Thiết kế quyền có hiệu lực thật

Quyền thực tế là phần giao của quyền tài khoản, chính sách trường/tenant, grant còn hiệu lực của người dùng, quyền trên tài nguyên và điều kiện của thao tác.

| Capability dự kiến | Cách cấp và thực thi |
| --- | --- |
| Tra cứu nguồn công khai đã duyệt | Theo policy hệ thống; không truy cập dữ liệu riêng chỉ vì công cụ có thể truy cập. |
| Đọc lịch học hoặc trạng thái hồ sơ của tôi | Cấp theo nguồn và scope bản thân; hỗ trợ một lần, trong phiên hoặc đến khi thu hồi tùy capability. |
| Đọc tài liệu tôi chọn | Giới hạn theo tài liệu/ngữ cảnh được chọn; không tự mở rộng sang cả kho tài liệu. |
| Đề xuất cập nhật bản nháp | Grant cho phép chuẩn bị; người dùng xem thay đổi và chọn Áp dụng. |
| Nộp hồ sơ, gửi trao đổi, đặt phòng | Grant cho phép chuẩn bị; luôn xem preview và xác nhận thao tác cụ thể. |
| Truy cập thông tin của người khác hoặc phê duyệt nghiệp vụ | Do quyền và policy của tổ chức quyết định; người dùng không tự mở bằng settings. |

Backend kiểm tra quyền khi đọc context, khi truy xuất nguồn và ngay trước khi chạy tool. Không chỉ ẩn nút trên frontend. Grant bị thu hồi hoặc hết hạn phải chặn thao tác đang chờ trước khi thực thi; không đưa thêm dữ liệu từ nguồn đã thu hồi vào yêu cầu mô hình tiếp theo. Dữ liệu đã gửi ra nhà cung cấp trước khi thu hồi không thể được coi là đã thu hồi ngược.

Grant lưu scope, resource/source ID, thời hạn, thời điểm cấp/thu hồi, phiên bản và lý do. Thực thi có idempotency và audit ở mức metadata cần thiết, không ghi toàn bộ nội dung nhạy cảm. Consent xử lý dữ liệu và grant thao tác là hai bản ghi riêng; cùng dùng chính sách có kiểm soát để tránh hai tập trạng thái mâu thuẫn.

## 5. Kiến trúc và dữ liệu

### 5.1. Một runtime cho các bề mặt trợ lý

Trang trợ lý, drawer trong dịch vụ và panel biểu mẫu dùng cùng ConversationService, SettingsService và renderer. Adapter demo được đánh dấu rõ và chỉ dùng trong demo; bản API không âm thầm fallback sang hướng dẫn cục bộ khi mất backend.

Pipeline đề xuất:

1. Xác thực danh tính và tenant.
2. Đọc conversation thuộc người dùng, settings và grants còn hiệu lực.
3. Lưu lượt người dùng theo client message ID để retry không nhân đôi.
4. Xây context giới hạn từ lịch sử cùng cuộc chat, tóm tắt có provenance và memory được cho phép.
5. Lấy nguồn dữ liệu cần thiết sau kiểm tra quyền.
6. Sinh trả lời, kiểm chứng nguồn và kiểm tra output.
7. Nếu có thao tác: tạo proposal được backend kiểm tra; chạy sau xác nhận và kiểm tra lại quyền.
8. Lưu phản hồi cuối cùng, citation map, trạng thái và schema version; phát xác nhận cuối sau commit.

Memory, lịch sử và dữ liệu nguồn được coi là dữ liệu ngữ cảnh không đáng tin cậy để cấp quyền. Hồ sơ học vụ hiện hành đọc từ hệ thống được phân quyền; không dùng memory để khẳng định điểm, học phí hoặc trạng thái xét duyệt.

### 5.2. Lưu trữ

- Dùng database làm nguồn chính. SQLite cho môi trường local đã có launcher; PostgreSQL cho môi trường nhiều người dùng sau khi wiring, migration và cấu hình được kiểm chứng.
- In-memory chỉ dùng cho kiểm thử/demo được chỉ rõ; bản dùng thật không tự chuyển sang in-memory khi storage lỗi.
- Mở rộng conversation/message hiện có: title, timestamps, archived/pinned và metadata cần thiết; giữ thứ tự, trạng thái hoàn tất, citations và ownership hiện có.
- Thêm assistant_preferences, assistant_memory, assistant_grants và persistent consent nếu phù hợp schema sau khảo sát.
- Có tenant/user isolation, index cho danh sách theo thời gian và cursor phân trang; không chỉ lọc sau khi đã tải dữ liệu của nhiều tài khoản.
- Local cache chỉ là phụ trợ, giới hạn dữ liệu nhạy cảm và thời hạn; không mặc định lưu toàn bộ hồ sơ riêng trên thiết bị dùng chung.
- Summary và memory có source, version, updated_at, expiry khi phù hợp; cập nhật bằng kiểm soát phiên bản để tránh ghi đè do nhiều tab.

### 5.3. API cần bổ sung hoặc mở rộng

- `GET /v1/conversations`: danh sách hội thoại của danh tính hiện tại, lọc archived và phân trang; không lấy user ID do browser gửi làm chủ sở hữu.
- Mở rộng API tạo conversation cho chế độ history/temporary theo policy.
- Giữ API đọc messages và streaming hiện có; mở rộng retry/idempotency, metadata trình bày tương thích ngược nếu cần.
- Endpoint metadata conversation cho đổi tên, ghim, lưu trữ; dùng version/ETag tránh lost update.
- `GET/PATCH /v1/me/assistant/preferences`.
- `GET /v1/me/assistant/capabilities`: capability thực sự có, policy, trạng thái hiệu lực và lý do bị khóa.
- API cấp/thu hồi grants có scope và thời hạn; API quản lý memory.
- Tận dụng luồng privacy/export/erasure hiện có sau khi kiểm chứng persistence và xử lý thực; không trả trạng thái hoàn tất giả.

Đây là API đề xuất, chưa được coi là contract đã triển khai.

### 5.4. Bảo toàn lịch sử hiện có

Không xóa hoặc ghi đè localStorage/database cũ. Đọc và kiểm tra schema cũ; chỉ import vào tài khoản đã xác minh sở hữu. Khóa browser có user ID không đủ chứng minh sở hữu ở server. Nếu chưa xác minh được, giữ nguyên bản cục bộ và cung cấp export/luồng chuyển có xác nhận.

Import phải giữ dấu vết nguồn và ID chống trùng; chỉ báo hoàn tất sau khi backend xác nhận. Dữ liệu demo không được tự nhập như dữ liệu thật. Thay đổi schema theo cách bổ sung và tương thích trước khi chuyển luồng đọc/ghi. Không rollback bằng reset/drop database hoặc xóa dữ liệu.

## 6. Kế hoạch triển khai

Ước lượng sơ bộ 16–24 ngày công kỹ thuật, khoảng 4–5 tuần với một kỹ sư full-stack và QA tham gia các mốc. Chưa gồm tích hợp SSO/connector mới hoặc mở production; hiệu chỉnh sau bước 0.

| Bước | Ưu tiên / ước lượng | Đầu ra và điều kiện chuyển bước |
| --- | --- | --- |
| 0. Tái hiện và chốt đường chạy | P0 / 1 ngày | Xác định build, launcher, route, mode, identity, storage và retention đang dùng. Tái hiện tải lại, rời trang, restart, đổi tài khoản. Có bằng chứng phân biệt thiếu lưu, thiếu tìm lịch sử và thiếu context. |
| 1. Thống nhất runtime và lưu bền vững | P0 / 4–6 ngày | Adapter API cho trợ lý sinh viên; storage được inject rõ, API danh sách/metadata, khôi phục, phân trang, retry/idempotency, trạng thái Đã lưu. Các lượt đã xác nhận còn sau restart; tài khoản khác không đọc được. |
| 2. Chuẩn hóa trả lời và renderer | P1 / 2–3 ngày | Renderer chung, hướng dẫn trình bày theo intent, nguồn và CTA có schema, bố cục mobile/accessibility. Tin cũ vẫn đọc được; trả lời ngắn không bị ép nhiều mục. |
| 3. Cài đặt và quyền thực thi | P1 / 4–6 ngày | Preferences theo tài khoản, grant/consent bền vững, panel cài đặt, server checks và thu hồi. Tải lại không mất settings; gọi API trực tiếp không vượt được quyền. |
| 4. Bộ nhớ cá nhân có kiểm soát | P2 / 3–5 ngày | Context cùng cuộc chat, memory opt-in có provenance, xem/sửa/quên, temporary chat và kiểm soát context budget. Dữ liệu cá nhân không lọt sang tài khoản khác. |
| 5. Nghiệm thu trải nghiệm | P0 trước phát hành / 2–3 ngày | Kiểm thử qua giao diện thật trên desktop/mobile, kiểm thử lỗi và bảo toàn dữ liệu; quan sát theo cohort được cho phép. Bản local đạt không tự động đồng nghĩa production đã đạt. |

Ngữ cảnh cùng cuộc chat nên nối ngay ở bước 1 nếu tận dụng được ConversationHistoryService/BoundedContextBuilder; bước 4 tập trung memory giữa các cuộc chat. Có thể đưa renderer đơn giản ra sớm sau bước 0, nhưng không bỏ điều kiện hoàn tất của lịch sử.

Đợt đầu nên hoàn thành lịch sử theo tài khoản, trả lời có cấu trúc và preferences/quyền cơ bản. Memory tự động, tích hợp ngoài và các quyền nâng cao theo sau khi đã kiểm chứng nền tảng.

## 7. Tiêu chí nghiệm thu

### Lịch sử và độ bền

- Tạo ít nhất ba cuộc chat, đổi tên/ghim/lưu trữ, tải lại, đăng xuất/đăng nhập, restart backend và mở trên thiết bị khác: các lượt đã được xác nhận lưu còn đúng thứ tự trong thời hạn chính sách.
- Browser không còn localStorage vẫn đọc được lịch sử máy chủ; localStorage bị lỗi không làm dữ liệu máy chủ mất hoặc bị ghi đè.
- Mất kết nối trước/sau commit và retry không tạo lượt trùng; streaming bị dừng được thể hiện đúng, không biến thành phản hồi hoàn tất.
- Hết phiên hoặc lỗi DB báo đúng trạng thái, không trả lịch sử trống như thành công; không hiển thị dữ liệu tài khoản trước sau đổi tài khoản.
- Khôi phục phản hồi giữ đúng citation map và trạng thái; phân trang nhiều hơn một trang không thiếu/nhân đôi messages.
- Chuyển dữ liệu cũ không thay đổi bản gốc hoặc gộp dữ liệu demo vào dữ liệu thật.

### Trình bày

- Bộ mẫu bao gồm câu ngắn, thủ tục, so sánh, trạng thái hồ sơ, không đủ căn cứ và đề xuất thao tác; kiểm tra cả nội dung và render.
- Desktop/mobile, sáng/tối và bàn phím: danh sách, bảng, nguồn và nút đọc được, không gây tràn ngang toàn trang. Bảng dài có container hoặc cách đọc phù hợp.
- Markdown dở dang trong streaming không làm vỡ UI; câu trả lời đã hoàn tất không bị format lại thành thông tin chưa được kiểm chứng.
- HTML/script và URL không được phép không thực thi; các nút thao tác không được sinh chỉ từ văn bản của mô hình.
- Người thử dùng xác định được việc cần làm tiếp và nguồn căn cứ; mục tiêu đo lường đề xuất ít nhất 80% hoàn thành tác vụ mẫu không cần hướng dẫn thêm, hiệu chỉnh sau baseline.

### Cá nhân hóa và quyền

- Hai tài khoản có cấu hình khác nhau; reload, nhiều tab và thiết bị không làm lẫn hoặc ghi đè âm thầm settings.
- Đổi độ dài/xưng hô ảnh hưởng trải nghiệm nhưng không thay đổi kết luận nghiệp vụ đã kiểm chứng.
- Từ chối, hết hạn hoặc thu hồi grant chặn tool ở server, kể cả gọi API trực tiếp hoặc đang có proposal chờ xác nhận.
- Grant cho đọc không cho phép ghi; grant cho một tài liệu không cho phép đọc tài liệu khác.
- Prompt trong chat, nguồn hoặc memory không tự tạo quyền và không bỏ xác nhận nộp/gửi.
- Tắt memory không xóa lịch sử; chat tạm thời không tạo/sử dụng memory cá nhân; quên một memory khiến nó bị loại khỏi context tương lai theo đúng phạm vi.
- Trang cài đặt chỉ hiển thị đã lưu sau xác nhận máy chủ; offline/lỗi lưu không báo thành công.

### Quan sát vận hành

Theo dõi tỷ lệ ghi/khôi phục thành công, thời gian mở danh sách, thời gian phản hồi, lỗi render/schema, tỷ lệ phải hỏi lại và tỷ lệ hoàn thành tác vụ. Log dùng metadata tối thiểu, không sao chép nguyên nội dung chat để đo lường. Chốt ngưỡng latency/cost sau baseline trên môi trường được phép.

## 8. Rủi ro và quyết định cần chốt trong triển khai

- Sai bản chạy: sửa source chính nhưng frontend đang chạy một bản snapshot khác. Bước 0 phải xác minh build thực tế.
- Sai danh tính: chuyển tài khoản demo/SSO làm lịch sử gắn vào chủ sở hữu khác. Xác minh subject ID và tenant trước import.
- Retention mâu thuẫn: UI hứa lưu nhưng read policy đã hết hạn. Hiển thị và thi hành cùng một chính sách.
- Memory suy diễn sai hoặc lỗi thời: ưu tiên sở thích do người dùng khai báo, cho xác nhận trước khi lưu, giữ provenance; thông tin học vụ lấy từ nguồn hiện hành.
- Settings hình thức: lưu preference nhưng không truyền vào context, hoặc frontend ẩn nút nhưng backend cho phép. Nghiệm thu từ hành vi thật và gọi API trực tiếp.
- Tăng chi phí: giới hạn context, memory theo liên quan và summary có provenance; không gửi toàn bộ lịch sử mỗi lượt.
- Cần thống nhất thời hạn lưu và dữ liệu cho phép ghi nhớ với policy hiện hành của đơn vị. Tài liệu này không xác lập kết luận pháp lý hoặc tự thay đổi chính sách dữ liệu.

## 9. Nguồn đối chiếu

- Mã nguồn trong workspace tại thời điểm phân tích, gồm các đường dẫn nêu ở bảng hiện trạng và các bài kiểm thử history/SQLite hiện có. Việc tồn tại test không chứng minh test đang pass trong bản triển khai.
- OpenAI Docs: https://learn.chatgpt.com/docs/developer-settings — tham khảo việc tổ chức personalization, memories và các nhóm settings; không coi là yêu cầu sao chép mọi tính năng.
- react-markdown: https://github.com/remarkjs/react-markdown — renderer React, GFM plugins và giới hạn an toàn khi tùy chỉnh/plugins.
- OWASP Authorization Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html — kiểm tra quyền từng request, least privilege và deny by default.

