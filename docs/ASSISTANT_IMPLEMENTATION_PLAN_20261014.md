# Kế hoạch triển khai trợ lý AI xuyên suốt Campus 24/7

Ngày lập: 14/10/2026, múi giờ Asia/Bangkok. Trạng thái: **đã lập kế hoạch, chưa triển khai chức năng**.

Điểm bắt đầu khi thực hiện sau: **AI-001**, rồi AI-002. Danh sách trạng thái và phụ thuộc: [ASSISTANT_IMPLEMENTATION_BACKLOG_20261014.json](ASSISTANT_IMPLEMENTATION_BACKLOG_20261014.json).

Tài liệu này hợp nhất yêu cầu trong cuộc chat và hai đề xuất [cá nhân hóa](ASSISTANT_PERSONALIZATION_PROPOSAL_20261014.md), [nâng cao và hỗ trợ mọi thao tác](ASSISTANT_ADVANCED_PROPOSAL_20261014.md). Hai tài liệu trước được giữ nguyên làm nguồn tham chiếu. Đây là kế hoạch kỹ thuật để tiếp tục công việc, không tạo thêm quy trình phê duyệt tài liệu hoặc thay đổi chính sách an toàn.

## 1. Kết quả sản phẩm cần đạt

Người dùng có thể nêu mục đích ở bất kỳ bề mặt phù hợp trong ứng dụng. Trợ lý hiểu yêu cầu, sử dụng dữ liệu được phép, tự chuẩn bị phần việc có đủ căn cứ, hướng dẫn đúng phần còn thiếu và tiếp tục tới kết quả được hệ thống nghiệp vụ xác nhận. Người dùng không phải nhập lại thông tin đã có hoặc kể lại tình huống khi chuyển trang.

Trợ lý hỗ trợ xuyên ứng dụng trong đúng chức năng và vai trò: trang chat, điều hướng, dịch vụ, biểu mẫu, từng trường, tài liệu, lỗi, hồ sơ, lịch, thông báo, cài đặt và giao diện cán bộ/quản trị. Sự hiện diện thể hiện bằng hỗ trợ hữu ích thực sự; không chỉ đặt một nút chat trên mọi trang.

Lưu lịch sử, sử dụng ngữ cảnh cùng cuộc chat, ghi nhớ giữa các cuộc chat và quyền thực hiện là bốn chức năng riêng. Thực hiện tối đa phần đã được cấp và đã rõ; hỏi khi thiếu dữ liệu làm thay đổi quyết định; giữ xác nhận đối với hành động theo quy trình hiện có.

## 2. Yêu cầu và truy vết

R01–R08 là yêu cầu trực tiếp của người dùng. R09–R13 là phần mở rộng trong thiết kế đã trao đổi, triển khai sau nền tảng và không lấn ưu tiên các yêu cầu trực tiếp.

| ID | Yêu cầu | Đầu ra người dùng thấy | Công việc chính |
| --- | --- | --- | --- |
| R01 | Lưu, tìm và tiếp tục hội thoại | Lịch sử theo tài khoản, khôi phục và trạng thái lưu rõ | AI-004, 007, 008, 009 |
| R02 | Trả lời dễ đọc, trực quan | Nội dung ngắn phù hợp; bước, bảng, thẻ và nguồn | AI-010, 011 |
| R03 | Cá nhân hóa theo từng người | Settings bền vững, cách trả lời và override trong chat | AI-012, 014 |
| R04 | Người dùng cấp/thu hồi quyền cho trợ lý | Quyền theo nguồn, tài nguyên, thời hạn; thực thi ở server | AI-013, 014 |
| R05 | AI hỗ trợ ở mọi nơi và mọi thao tác trong ứng dụng | Runtime/context chung; ma trận hỗ trợ theo màn hình/vai trò | AI-005, 006, 017, 020, 021 |
| R06 | Tự động chuẩn bị tối đa, giảm công sức | Chọn luồng, điền sẵn, kiểm tra, preview, tiếp tục công việc | AI-016, 017, 018, 019 |
| R07 | Hiểu đúng mục đích | Bản mục đích có cấu trúc, hỏi làm rõ đúng điểm, sửa được | AI-002, 015, 016 |
| R08 | Đúng dữ liệu, nghiệp vụ, hành động và kết quả | Giá trị có nguồn; validation; version; biên nhận; chống trùng | AI-003, 011, 017, 018, 026 |
| R09 | Bộ nhớ cá nhân có kiểm soát | Xem/sửa/quên, cập nhật theo thời gian, không lẫn tài khoản | AI-022, 023 |
| R10 | Công việc nhiều bước qua nhiều phiên | Tiếp tục đúng bản nháp/hồ sơ, biết bước tiếp theo | AI-019 |
| R11 | Chủ động trong phạm vi người dùng chọn | Theo dõi thay đổi, giờ yên lặng, tắt theo dõi | AI-024, 025 |
| R12 | Minh bạch và bàn giao cho cán bộ | Vì sao gợi ý, nguồn; bản tóm tắt có preview trước gửi | AI-011, 025 |
| R13 | Chất lượng và vận hành được kiểm chứng | Đánh giá thực tế, chi phí, lỗi và cách mở rộng có kiểm soát | AI-001, 002, 026–030 |

## 3. Hiện trạng và điều cần xác minh

Quan sát mã nguồn ngày 14/10/2026, chưa phải xác nhận bản chạy thực tế:

- `student-chat.ts` có lịch sử localStorage theo mode/user. `assistant-context.tsx` mặc định dùng guidanceAdapter; respond chưa chứa các lượt trước. Không thể coi lưu ở browser là đồng bộ máy chủ hoặc có memory.
- `StudentRuntime.tsx` có điều hướng `/chat` sang `/student/assistant` khi áp dụng cho sinh viên. `AssistantConversation.tsx` dùng đoạn văn; `ChatPanel.tsx` đã dùng react-markdown/remark-gfm.
- ConversationMessageService mặc định dùng in-memory khi không inject repository; main.py gọi create_app() mặc định. Có SQLite/PostgreSQL repository và launcher đã inject SQLite. Phải xác minh đúng entry point trước khi sửa storage.
- API chat có tạo conversation, đọc messages và streaming; cần kiểm tra/bổ sung API danh sách và metadata hội thoại. Chính sách đọc có retention; mặc định tạo chat là 30 ngày.
- Có consent OPTIONAL_PERSONALIZATION, nhưng service đang có trạng thái bộ nhớ; trang privacy có hành vi demo/fallback. Không dùng UI demo làm bằng chứng consent đã persist.
- Có draft/preview/confirm, version và idempotency trong certificate/service gateways. Có agent-run read/resume/cancel, kiểm tra ownership và source scope. Tái sử dụng sau kiểm chứng, không xây đường ghi bỏ qua các cơ chế này.
- Một số launcher tạo bản frontend riêng dưới infra/local; chỉnh apps/web chưa chứng minh bản đang phục vụ người dùng đã thay đổi.
- Working tree có nhiều thay đổi, file chưa theo dõi và tài liệu đã bị xóa từ trước. Mọi lần triển khai phải ghi nhận lại trạng thái và giữ nguyên phần không thuộc phạm vi.

Đầu ra AI-001 phải xác định: URL/build/frontend path, launcher/API, mode, subject/tenant/role, repository/storage thực tế, retention, quyền nguồn, các capability thật, test runtime và mức hoàn thiện từng workflow. Không đọc credential hoặc dump dữ liệu thật để khảo sát.

## 4. Thiết kế trải nghiệm và mức tự động

### 4.1. Một trợ lý, nhiều bề mặt

Một runtime dùng chung conversation, mục đích, task/draft references, settings và grants. Bề mặt gồm điểm truy cập chung, panel theo ngữ cảnh, trợ giúp từng trường, thẻ kiểm tra và vùng tiếp tục công việc. Mobile ưu tiên một vùng; bàn phím/focus và chế độ sáng/tối phải hoạt động. Người dùng thu gọn được trợ lý mà không mất ngữ cảnh.

Không thu toàn bộ DOM hoặc màn hình ngoài ứng dụng. Context bridge chỉ nhận trường dữ liệu theo schema: route/capability, resource ID/version, field đang hỏi, lỗi được xác nhận và dữ liệu tối thiểu đã được phép. Không tin subject/tenant/role do browser khai báo; server xác lập danh tính và quyền.

### 4.2. Cách hiểu mục đích

Bản mục đích gồm: kết quả mong muốn; mục đích sử dụng; đối tượng/hồ sơ; ràng buộc đã nêu; thông tin đã có kèm nguồn; phần thiếu; các cách hiểu còn khả dĩ; workflow đề xuất. Điểm tự tin của mô hình không đủ để cho phép thực hiện.

Chỉ hỏi khi thiếu/xung đột làm thay đổi thủ tục, thông tin quan trọng, nơi nhận, chi phí hoặc hành động. Gộp phần thiếu có liên quan; không hỏi lại dữ liệu có nguồn còn hiệu lực và được phép dùng. Chuẩn bị phần chắc chắn trong lúc chờ; không dùng giá trị mặc định để lấp trường quan trọng chưa rõ. Người dùng đổi mục đích thì đánh giá lại, giữ bản nháp cũ và đề xuất phần thay đổi.

### 4.3. Chuẩn bị và xác nhận

| Loại việc | Hành vi |
| --- | --- |
| Đọc/giải thích trong phạm vi đã cấp | Thực hiện khi cần, không hỏi lại quyền đã có |
| Chuẩn bị bản nháp mới từ yêu cầu rõ và dữ liệu hợp lệ | Điền sẵn, hiển thị nguồn và cho sửa |
| Dữ liệu suy luận, OCR, thiếu, xung đột hoặc nguồn cũ | Đề xuất/làm rõ đúng phần; không coi là đã xác nhận |
| Đổi trường người dùng đã sửa trong bản nháp hiện có | Diff và Áp dụng theo cơ chế hiện hành, gộp thay đổi liên quan |
| Nộp/gửi/đặt dịch vụ/thanh toán/quyền/phê duyệt | Preview, xác nhận đúng thao tác, kiểm tra server và biên nhận |

Mục tiêu giảm thao tác không làm thay đổi authentication, authorization, confirmation, source verification hoặc data protection. Một xác nhận gắn với payload, mục tiêu, version và thời hạn cụ thể; không dùng làm grant vô hạn. Retry giữ cùng khóa idempotency, đổi payload cần chu kỳ preview/xác nhận phù hợp.

### 4.4. Cách trả lời

Câu đơn giản trả lời ngắn; thủ tục có các bước; so sánh dùng bảng; hồ sơ có thẻ trạng thái; cập nhật bản nháp có diff; trả lời dài có tóm tắt và mở rộng. Tái sử dụng Markdown hiện có, giới hạn HTML/URL/component. CTA và status có schema và bindings được server kiểm tra; không suy ra hành động từ từ khóa prose. Nguồn gắn với claim và thời điểm hiệu lực. Giải thích căn cứ cá nhân hóa không hiển thị suy nghĩ nội bộ.

## 5. Kiến trúc, dữ liệu và hợp đồng

### 5.1. Trách nhiệm module

- Frontend: runtime/context bridge, registry, conversation UI, renderer, settings, field assist và task UI. Không đặt quy tắc học vụ hoặc cấp quyền trong component.
- Application/domain: conversation, intent/clarification, workflow/draft preparation, grants/consent, memory, task state, confirmation và kết quả.
- Infrastructure: repositories, model/source gateways, worker/outbox và telemetry. Không dùng model output hoặc checkpoint để tự tạo quyền ghi.
- Presentation: nhận payload có schema, xác thực, gọi service, trả response/status; giữ routes mỏng.

Mở rộng module hiện có; chưa cần tách microservice, đổi framework hay thêm một hệ multi-agent mới. Chọn single-agent/controller/workflow hiện có sau AI-001 dựa trên nhu cầu thật và kết quả test. Model hỗ trợ hiểu và diễn đạt; code kiểm tra và thực hiện.

### 5.2. Dữ liệu cần có

| Thực thể | Thuộc tính chính | Bảo đảm |
| --- | --- | --- |
| Conversation/Message | owner/tenant, title, sequence, timestamps, mode, retention, final status, citations, client request ID | Ownership, phân trang, durable commit, không nhân đôi |
| AssistantPreferences | user/tenant, locale, cách xưng hô, verbosity, format, custom instructions, version | Persist, override theo chat, CAS/ETag, không vượt policy |
| Consent/Grant | purpose/capability, source/resource scope, expiry, granted/revoked, version | Server enforcement, thu hồi, consent tách quyền thao tác |
| Intent/Task | goal, facts+provenance, missing/conflict, workflow, resource/version, state, next action | Không đoán mục đích quan trọng; tiếp tục đúng tài nguyên |
| DraftFieldProposal | field, before/after, source, freshness, xác nhận, base version | Không ghi đè chỉnh sửa; schema/domain validation |
| Memory | loại, nội dung tối thiểu, nguồn, validity, confirmation, usage scope | Opt-in, cập nhật, quên có hiệu lực, isolation |
| Subscription/Event/Receipt | nguồn, resource, trigger, channel, quiet hours, dedup key, delivery status | Chỉ theo dõi được cấp; không thông báo trùng |

SQLite phục vụ local đã có; PostgreSQL cho triển khai nhiều người dùng sau khi wiring và môi trường được xác minh. Dữ liệu chính ở server; cache browser có giới hạn/thời hạn phù hợp, tránh lưu toàn bộ dữ liệu riêng trên thiết bị dùng chung. In-memory chỉ cho fake/demo chỉ rõ; storage lỗi không chuyển âm thầm sang in-memory.

Message phải phân biệt pending/committed/streaming/completed/interrupted/failed. Chỉ báo Đã lưu sau commit. Kết quả cuối giữ citation map, trạng thái và schema version; không báo Hoàn tất chỉ dựa vào text. Có index danh sách theo tenant/owner/time và phân trang message; server lọc quyền trước truy xuất.

### 5.3. API đề xuất, chưa phải API đã triển khai

- Mở rộng `POST /v1/conversations`; bổ sung `GET /v1/conversations` và metadata PATCH cho title/pin/archive, cursor và version.
- Giữ `GET /v1/conversations/{id}/messages`, streaming và agent-run read/resume/cancel; mở rộng theo nhu cầu thực, tương thích backward.
- `GET/PATCH /v1/me/assistant/preferences`; `GET /v1/me/assistant/capabilities` trả capability thật, scope và lý do bị khóa.
- API cấp/thu hồi grant và quản lý memory theo danh tính server; tham chiếu resource được kiểm tra, không cho browser tự chọn owner.
- API chuẩn bị trợ giúp/thủ tục nhận goal, context reference và expected_version; trả interpretation, missing/conflicts, typed proposal và allowed next actions. Nối vào draft/preview/confirm hiện có.
- API task/subscription chỉ thêm khi chưa có tương đương; bàn giao tận dụng service/handover sau kiểm tra contract.
- 401 cho phiên không hợp lệ; concealment cho tài nguyên không được phép theo convention hiện hành; 409 cho stale version; 422 cho payload; dependency failure không giả thành empty success.
- PATCH preferences/metadata có kiểm soát version. Requests tạo mới/thao tác có idempotency phù hợp, bounded payload, no-store cho dữ liệu riêng và audit metadata tối thiểu.

Chỉ mở rộng schema theo cách bổ sung sau khi đọc contract hiện tại. Các đường dẫn mới và migration sẽ được chốt trong AI-003/004; không tự chọn số migration nếu đã có số trùng.

### 5.4. Bảo toàn và chuyển dữ liệu

Không xóa/ghi đè localStorage, DB, build snapshot hoặc tài liệu cũ. Import chỉ sau xác minh sở hữu; khóa localStorage chứa user ID không đủ chứng minh identity server. Giữ provenance và chống trùng; demo không nhập như dữ liệu thật. Chưa xác minh được thì giữ dữ liệu cục bộ và cung cấp export/luồng chuyển có xác nhận.

Schema thay đổi bổ sung, diễn tập trên fixture mới được xác định, bảo toàn source gốc. Chuyển feature bằng cấu hình phát hành riêng, không sửa safety controls. Tắt feature nâng cao vẫn đọc được lịch sử, bản nháp và kết quả. Không rollback bằng reset/drop database hoặc hủy working tree.

## 6. Giai đoạn, phụ thuộc và mốc bàn giao

Ước lượng sơ bộ cho toàn bộ phạm vi: **39–59 ngày công kỹ thuật**, không phải cam kết lịch. Với một kỹ sư toàn thời gian, tương đương khoảng 8–12 tuần làm việc, chưa tính phụ thuộc bên ngoài/QA riêng. Phạm vi rộng hơn hai đề xuất ban đầu vì đã bổ sung AI xuyên ứng dụng, tự chuẩn bị thủ tục, cán bộ, memory và event delivery. AI-001/002 cập nhật dự báo có lý do; không tự đổi tiêu chí để đạt deadline.

| Giai đoạn | Công việc | Ngày công | Mốc |
| --- | --- | --- | --- |
| P0 | AI-001–002: khảo sát, baseline, ca nghiệm thu | 2–3 | M0: biết đúng đường chạy và tiêu chí |
| P1 | AI-003–006: contract, storage, runtime/context/registry | 4–6 | Nền tảng dùng chung |
| P2 | AI-007–009: lịch sử server, UX, chuyển dữ liệu | 4–6 | M1: lịch sử đáng tin cậy |
| P3 | AI-010–011: renderer và nội dung có cấu trúc | 2–3 | Trả lời trực quan |
| P4 | AI-012–014: settings, consent và quyền | 4–6 | Quyền có hiệu lực thật |
| P5 | AI-015–018: hiểu mục đích, chuẩn bị thủ tục, xác nhận | 6–9 | M2: pilot ba tác vụ |
| P6 | AI-019–021: tiếp tục công việc và phủ toàn ứng dụng | 5–8 | M3: độ phủ từng vai trò |
| P7 | AI-022–023: memory có kiểm soát | 4–6 | Cá nhân hóa dài hạn |
| P8 | AI-024–025: sự kiện, nhắc việc, bàn giao | 4–6 | M4: hỗ trợ chủ động |
| P9 | AI-026–030: kiểm chứng, vận hành, diễn tập và bàn giao | 4–6 | M5: đủ bằng chứng để xem xét phát hành |

Thứ tự mặc định P0 → P1 → P2 → P3 → P4 → P5 → P6 → P7 → P8 → P9. Theo backlog để biết phụ thuộc chính xác. Test/telemetry bắt đầu trong từng task, không đợi P9. M2 chỉ đạt khi bộ acceptance pilot tương ứng đã chạy qua UI thật; không cần bật memory hoặc notification chưa hoàn thiện.

Các mốc là điều kiện kỹ thuật, không thêm vòng xin phê duyệt tài liệu. Chưa triển khai, commit, push, tự động chạy sau hoặc mở production theo yêu cầu hiện tại.

## 7. Danh sách công việc chi tiết

Mỗi task có status trong backlog; toàn bộ hiện là planned. “Phạm vi” là khu vực dự kiến để đọc/sửa khi bắt đầu, không phải quyền sửa mọi file trong thư mục. Chốt exact paths, đọc file và kiểm tra dirty state trước mỗi thay đổi. Tên component/service mới chỉ là đề xuất; tận dụng equivalent hiện có.

### AI-001 — Khảo sát đường chạy và độ phủ

- Phạm vi: scripts launch/prepare, bootstrap/main, AppShell/StudentRuntime, data config/gateway; read-only đối với runtime/snapshot/user data.
- Làm: inventory route/thao tác/vai trò và capability thật; xác định build/API/storage/identity/retention; tái hiện lỗi lịch sử và trình bày.
- Đầu ra: runtime map, registry inventory và findings có evidence; đạt khi phân biệt thiếu lưu, thiếu discovery, thiếu context và sai bản chạy. Kiểm tra AC01, AC02, AC28.

### AI-002 — Baseline mục đích, công sức và bộ ca kiểm chứng

- Phạm vi: fixtures/evals mới, E2E acceptance dự kiến; không lấy dữ liệu thật chưa được phép.
- Làm: tối thiểu 60 ca pilot chia đều thủ tục/câu mơ hồ/đổi mục đích; 30 ca quyền/lỗi; kịch bản mobile/desktop. Đặt expected workflow/facts/actions theo nguồn và review nghiệp vụ phù hợp.
- Đầu ra: dataset có ID/source/expected result, baseline nhập tay/hỏi lại/thời gian, ngưỡng pilot. Không dùng câu trả lời của chính model làm gold. AC12–19, AC27–30.

### AI-003 — Hợp đồng dữ liệu và lỗi

- Phạm vi: contracts/openapi và schemas chat/actions/privacy; types frontend và application models liên quan.
- Làm: thiết kế intent/context/proposal/preferences/grant/task/memory; schema version, pagination, idempotency, errors và bảo mật nguồn; giữ tương thích stream/citations.
- Đầu ra: schemas/API delta và contract tests; unknown fields/IDs/version sai bị từ chối. AC03, AC07, AC09–11, AC18.

### AI-004 — Storage bền vững và wiring

- Phạm vi: conversation repositories, bootstrap/app/settings, consent repository, migrations bổ sung.
- Làm: inject storage rõ theo môi trường; transaction cho message/final metadata; ownership/index/version; persist preferences/consents/grants. Migration fixture mới và kiểm tra không ghi đè dữ liệu.
- Đầu ra: restart không mất bản ghi đã commit; DB lỗi báo đúng; không fallback in-memory trong bản API. AC01, AC03–05, AC09.

### AI-005 — Runtime và adapter chung

- Phạm vi: assistant-context/adapter, StudentRuntime, ChatPage và SSE/history client.
- Làm: thống nhất conversation/task state; adapter API theo config; demo phân biệt rõ; abort/switch user/route an toàn; nối context cùng cuộc chat phía server.
- Đầu ra: chat/panel/form dùng cùng cuộc chat phù hợp; identity đổi không lộ nội dung cũ; API lỗi không giả trả lời demo. AC04, AC20, AC21, AC29.

### AI-006 — Registry và context bridge xuyên ứng dụng

- Phạm vi: module assistant/registry/context dự kiến và các bề mặt hiện có.
- Làm: capability ID, role, resource/version, field/errors schema, hỗ trợ explain/prepare/execute/unsupported; truyền dữ liệu tối thiểu được phép.
- Đầu ra: ma trận route/action có trạng thái hỗ trợ và handler thật; không dựa toàn DOM hoặc nút inert. AC21, AC22.

### AI-007 — API lịch sử, metadata và retry

- Phạm vi: conversation application/presentation/repositories và stream result.
- Làm: list owned conversations, metadata CAS, cursor messages, client request IDs, durable ack, final result và retention states.
- Đầu ra: phân trang không thiếu/trùng, retry đúng, expired/error không giả empty success. AC01–04.

### AI-008 — UX lịch sử và khôi phục

- Phạm vi: AssistantWorkspace/Conversation, ChatPage và history client.
- Làm: list/search tiêu đề, new/rename/pin/archive, restore, saved/pending/interrupted states; phân trang vừa đủ; desktop sidebar/mobile drawer.
- Đầu ra: mở lại được từ UI và thiết bị khác trên cùng môi trường/tài khoản thử; giữ nguồn/trạng thái; lỗi đọc không cho ghi đè lịch sử. AC01–03, AC06, AC29.

### AI-009 — Chuyển dữ liệu cũ có bảo toàn

- Phạm vi: student-chat compatibility/import/export, server import service nếu cần.
- Làm: inspect legacy schema, ownership verification, preview import, provenance, dedup và receipt; bảo toàn dữ liệu gốc.
- Đầu ra: import replay không trùng, demo không trộn thật, không xác minh được thì không gắn owner tùy ý. AC04, AC05.

### AI-010 — Bộ hiển thị câu trả lời dùng chung

- Phạm vi: ChatPanel renderer, AssistantConversation và styles component liên quan.
- Làm: Markdown/GFM, headings/lists/tables, safe links/components, streaming incomplete input, copy, focus và responsive; không thêm HTML thực thi.
- Đầu ra: nội dung hiện tại và tin cũ đọc được trên mobile/dark; bảng không tràn toàn trang; unsafe content không thực thi. AC06–08.

### AI-011 — Nội dung theo mục đích, nguồn và thẻ hành động

- Phạm vi: generation output/policy/compose, response schema, citations/action rendering.
- Làm: chọn short/steps/table/status/proposal; evidence bindings/freshness; CTA dựa payload checked, chưa có capability thì không tạo action giả.
- Đầu ra: đơn giản vẫn gọn; claim có nguồn phù hợp; status/CTA không suy từ prose. AC07, AC08, AC27.

### AI-012 — Preferences và consent bền vững

- Phạm vi: privacy/consent, preferences service/repository/routes, pipeline context.
- Làm: locale/name/tone/verbosity/format/custom instructions, current state readback, version; chat override; optional personalization tách feedback/history.
- Đầu ra: reload/multi-device không mất settings; save lỗi không báo thành công; instructions cá nhân không vượt policy. AC09, AC11, AC24.

### AI-013 — Grant và kiểm tra quyền mọi đường thực thi

- Phạm vi: identity/authorization, source/context factories, tool executor, confirmation/run resume và grant service.
- Làm: scope resource/source, một lần/phiên/thời hạn phù hợp capability; revoke/version; revalidate trước read và execute; one-time grant consumption chống race/retry.
- Đầu ra: direct API, resume và pending proposal đều không vượt quyền; read không cấp write; revoke chặn hành động chưa chạy. AC04, AC10, AC11, AC18.

### AI-014 — Panel cài đặt và trung tâm quyền

- Phạm vi: assistant settings UI, PrivacyCenter integration, capability API client.
- Làm: bốn vùng reply/memory/tools/history; preview, effective permissions, source/resource/expiry/last-used; loading/error/locked reasons.
- Đầu ra: lựa chọn có hiệu lực trong trả lời; capability chưa có không báo dùng được; permissions minh bạch và thu hồi được. AC09–11, AC24.

### AI-015 — Hiểu mục đích và hỏi làm rõ

- Phạm vi: conversation understanding/followup, document_request assistant và controller/contracts hiện có.
- Làm: goal/facts/provenance/missing/conflict/workflow; phân biệt đề xuất với fact; clarify điểm ảnh hưởng quyết định; chỉnh interpretation theo yêu cầu mới.
- Đầu ra: đúng workflow với ca rõ; ca mơ hồ hỏi đúng điểm trước action; không hỏi lại dữ liệu hợp lệ; đổi mục đích không mất việc cũ. AC12, AC13, AC27.

### AI-016 — Tự chuẩn bị bản nháp thủ tục

- Phạm vi: certificate/service assistant/application, gateways, form stores và field proposal contract.
- Làm: pilot xin cấp giấy, bổ sung hồ sơ, theo dõi phản hồi; đọc dữ liệu được phép, tạo/mở đúng draft, điền sẵn dữ liệu có căn cứ; đề xuất thay đổi bản nháp đang có.
- Đầu ra: user không nhập lại field có nguồn; manual edit được giữ; nhiều draft/goal chưa rõ không chọn bừa. AC12–15, AC20.

### AI-017 — Trợ giúp trường, tài liệu và lỗi

- Phạm vi: VinUniForm/CertificateWorkspace/ServiceWorkspace, attachments, validations, registry handlers.
- Làm: help đúng field, đề xuất định dạng, gom missing fields; file format/size/content suggestions; OCR nếu có runtime được phép thì coi output là candidate; giải thích lỗi có căn cứ.
- Đầu ra: sửa đúng chỗ, không giả xác thực tài liệu; schema/required/domain checks ở server; state được giữ khi lỗi. AC15–17, AC29.

### AI-018 — Preview, confirm, receipt và phục hồi lỗi ghi

- Phạm vi: action confirmation/idempotency, certificate/service preview/confirm và UI tương ứng.
- Làm: bind exact payload/version/destination/expiry; stale/revoke checks; retries dùng stable idempotency; timeout tra trạng thái trước gửi lại; tách generated/committed/submitted.
- Đầu ra: user xác nhận thao tác đã chuẩn bị; không duplicate sau crash; chỉ báo thành công theo receipt. AC10, AC18, AC19, AC29.

### AI-019 — Công việc nhiều bước và tiếp tục

- Phạm vi: agent runs/workflow stores, task application và StudentWorkspaceHub/Requests/detail.
- Làm: bind task với conversation/draft/request/version; next step và blockers; pause/resume/cancel đúng nghĩa; link từ history/notification.
- Đầu ra: nhiều phiên/restart vẫn mở đúng bước; hoàn tất phản ánh trạng thái nghiệp vụ; resume không chạy lại action. AC19–21.

### AI-020 — Phủ thao tác phía sinh viên

- Phạm vi: điều hướng/dịch vụ/form/request/schedule/room/privacy và registry.
- Làm: nối từng handler với context và capability đã kiểm chứng; hỗ trợ cùng mục đích qua route; giới hạn nguồn/thao tác chưa có; mobile UX.
- Đầu ra: mọi thao tác của inventory sinh viên có mức hỗ trợ thật và next step; full execution chỉ khi backend hỗ trợ đúng. AC06, AC21, AC22, AC29.

### AI-021 — Phủ thao tác cán bộ và quản trị

- Phạm vi: staff queue/detail/response, knowledge/admin surfaces và policies tương ứng.
- Làm: tổng hợp có nguồn, draft reply, kiểm tra thiếu, preparation theo đúng capability; preserve review/approval/confirmation.
- Đầu ra: vai trò sinh viên không gọi được staff/admin handler; không tự chốt quyết định; mọi action trong inventory có mức hỗ trợ/trạng thái thiếu rõ. AC04, AC18, AC22, AC27.

### AI-022 — Memory cá nhân và truy xuất liên quan

- Phạm vi: memory service/repository/context; preferences/consent integration.
- Làm: preferences/goals/confirmed facts, timestamps/source/validity, relevance và context budget; không lấy memory thay trạng thái học vụ.
- Đầu ra: opt-in, đúng người, cập nhật thông tin theo thời gian; missing/contradiction không biến thành fact. AC11, AC23, AC27, AC30.

### AI-023 — Xem, sửa, quên và chat tạm thời

- Phạm vi: memory UI/API, context/index/summary invalidation, temporary conversation mode.
- Làm: forget suppression không tái tạo từ history, sửa version; không dùng/tạo personal memory trong temporary; retention/operational storage disclosure chính xác.
- Đầu ra: tắt memory không xóa history; quên có hiệu lực ở context tương lai; export/erasure theo luồng hiện có và quyền tương ứng. AC23, AC24.

### AI-024 — Theo dõi sự kiện và delivery bền vững

- Phạm vi: business event/worker/outbox và subscription service; chỉ sources/channels đã được phép.
- Làm: phản hồi mới/bổ sung/hạn có nguồn; dedup, retry, quiet hours, scope revalidation trước delivery, no-change suppression.
- Đầu ra: không đổi thì im lặng; revoke/unsubscribe chặn delivery tiếp; restart không nhân notification; không kích hoạt write từ notification. AC10, AC25, AC30.

### AI-025 — Thông báo hữu ích và bàn giao có preview

- Phạm vi: task notification UI, HandoverPanel và service/handover API hiện có.
- Làm: reason/source/updated_at/next action, stop tracking; summary có phạm vi người dùng chọn, preview và confirmation trước gửi; không tự chia sẻ memory/history toàn bộ.
- Đầu ra: mở đúng hồ sơ; nội dung đúng channel/privacy; cán bộ nhận phần đã xác nhận chia sẻ và câu hỏi còn mở. AC25–27.

### AI-026 — Kiểm chứng chất lượng và đối kháng

- Phạm vi: dataset từ AI-002, unit/API/integration/security suites liên quan.
- Làm: benchmark intent+workflow/facts, memory update/forget, stale resources, cross-account, injection qua documents/tools/memory, granted/revoked race và confirmation bypass.
- Đầu ra: report theo từng nhóm, command/exit/evidence; không dùng overall score che lỗi quyền/nghiệp vụ; không đổi gold/threshold chỉ để pass. AC03–05, AC07, AC10–19, AC23–27.

### AI-027 — Quan sát, giới hạn và hiệu năng

- Phạm vi: telemetry/budget/gateway/context/worker, instrumentation client tối thiểu.
- Làm: storage/restore/render/schema errors, p95 latency, workflow success, cost per completed task; context/tool/retry/time ceilings; metadata không chứa secrets/raw private chat.
- Đầu ra: giới hạn có hiệu lực, failure có next step, số liệu tái hiện được; thresholds latency/cost theo AI-002 và môi trường đã xác minh. AC29, AC30.

### AI-028 — Nghiệm thu qua giao diện thực

- Phạm vi: E2E pilot/coverage/mobile và user task scripts trong môi trường được phép.
- Làm: ít nhất 8–12 phiên thử có người thực hiện khi có người tham gia; desktop/mobile/keyboard/dark; real browser đúng build; so baseline công sức/chất lượng.
- Đầu ra: evidence tác vụ, lỗi, completion/corrections và limits. Nếu chưa có người tham gia, báo chưa nghiệm thu người dùng; không dùng synthetic pass thay thế. AC01–30 theo coverage.

### AI-029 — Diễn tập chuyển luồng và phương án phục hồi

- Phạm vi: fixture data mới, runtime/build configuration cho candidate, non-destructive compatibility checks.
- Làm: import/schema/wiring rehearsal, feature activation theo capability, compatibility old reads, recovery khi storage/model/integration lỗi; giữ build/data cũ.
- Đầu ra: checklist deploy-ready có exact environment/targets; không production deploy trong task này; không stop process đang dùng hoặc xóa dữ liệu để test. AC01, AC05, AC19, AC28, AC29.

### AI-030 — Bàn giao và trạng thái cuối

- Phạm vi: tài liệu hướng dẫn/runbook và backlog này.
- Làm: cập nhật thực tế capability/remaining gaps, lệnh run/verify đã chứng minh, settings/retention/permissions, cách tiếp tục và evidence links.
- Đầu ra: chỉ đánh dấu verified sau acceptance; chỉ gọi toàn bộ kế hoạch hoàn tất khi R01–R13 trong phạm vi chốt đều đạt hoặc scope thay đổi do người dùng trực tiếp. Chưa phát hành không gọi là đã phục vụ production.

## 8. Bộ acceptance scenarios

| ID | Kịch bản phải kiểm chứng |
| --- | --- |
| AC01 | Tạo chat → reload/relogin/server restart/thiết bị khác → lượt đã commit còn đúng trong retention |
| AC02 | Tìm/open/rename/pin/archive; phân trang nhiều trang không mất/trùng dữ liệu |
| AC03 | Retry, stream ngắt, timeout quanh commit; final status/citations/sequence chính xác |
| AC04 | Tài khoản/tenant/vai trò khác không đọc/chỉnh/resume tài nguyên trái quyền |
| AC05 | Legacy corrupt/ownership unknown/import replay/demo; giữ nguồn gốc và dữ liệu gốc |
| AC06 | Markdown/lists/tables/cards, streaming, mobile/dark/keyboard; không vỡ toàn trang |
| AC07 | HTML/script/URL/tool-text injection không tạo executable UI hoặc CTA trái quyền |
| AC08 | Câu ngắn không bị ép dài; câu thủ tục/so sánh/status có bố cục phù hợp |
| AC09 | Save/reload/concurrent tabs/chat override preferences; failure không báo saved |
| AC10 | Grant denied/expired/revoked, one-time races; pending proposal/resume/direct API không vượt scope |
| AC11 | Consent khác grant; read khác write; custom instructions không cấp quyền; source scope refresh |
| AC12 | Yêu cầu rõ, mơ hồ, thiếu facts; hiểu đúng goal và hỏi đúng thông tin làm đổi quyết định |
| AC13 | Người dùng đổi mục đích hoặc constraints; sửa interpretation, giữ dữ liệu cũ, không action sai |
| AC14 | Tạo draft tự điền từ nguồn hợp lệ; field provenance; không hỏi lại thông tin đã có |
| AC15 | Manual edits/stale draft/multiple drafts/conflicting source; không chọn bừa hoặc ghi đè |
| AC16 | File không hợp lệ/OCR sai/source injection; không coi trích xuất là xác thực |
| AC17 | Required fields/enum/date/business conditions; server validation không phụ thuộc model |
| AC18 | Preview/confirm bị đổi payload/target/version/expiry; thao tác chưa xác nhận không chạy |
| AC19 | Timeout/crash quanh business commit; readback và retry không nộp/gửi/đặt hai lần |
| AC20 | Task qua nhiều phiên; next step/resource/version đúng; complete dựa receipt/status |
| AC21 | Chuyển route/panel/form/hai tab và đổi tài khoản; context không lẫn hoặc mất |
| AC22 | Inventory mọi thao tác từng vai trò có handler/mức hỗ trợ thật hoặc next step rõ |
| AC23 | Memory cập nhật theo thời gian/mâu thuẫn/forget; không tái xuất hiện trái lựa chọn |
| AC24 | Memory off/temporary/history/export choices có hiệu lực đúng và disclosure chính xác |
| AC25 | Event mới/không đổi/trùng/restart/quiet hours/stop tracking; delivery đúng scope và kênh |
| AC26 | Handover preview/chọn nội dung/confirm; không tự gửi toàn bộ chat hoặc memory |
| AC27 | Fact/source freshness/status/deadline chưa xác minh; không khẳng định quá căn cứ |
| AC28 | UI dùng đúng build/API được báo; code pass ở snapshot khác không tính đã nghiệm thu |
| AC29 | Offline/DB/model/integration lỗi; giữ nháp/history, phân biệt chưa lưu, có cách tiếp tục |
| AC30 | Context/tool/retry/cost/time bounds, metrics privacy, latency/cost report theo baseline |

## 9. Tiêu chí thành công và cách kiểm tra

Điều kiện bắt buộc: các ca quyền, identity, bảo toàn dữ liệu, confirmation và chống trùng trong phạm vi triển khai đều pass; không còn lỗi nghiêm trọng đã biết chưa xử lý. Kết quả này chỉ áp dụng cho tập thử/môi trường đã kiểm chứng, không chứng minh độ chính xác 100% ngoài thực tế.

Các mục tiêu UX đề xuất để AI-002 chốt trước pilot: giảm ít nhất 40% trường nhập tay ở tác vụ có nguồn hợp lệ; giảm ít nhất 30% thời gian thao tác người dùng; ít nhất 90% phiên pilot hoàn tất tác vụ được hỗ trợ không cần người hướng dẫn. So sánh cùng tác vụ/dữ liệu/điều kiện, tách thời gian cán bộ xử lý; báo mẫu thử và confidence/limitations. Không coi đạt giảm thao tác là thành công nếu sai mục đích, điền sai hoặc vi phạm quyền. Chưa có baseline thì chưa khẳng định đạt.

Intent dataset phải đo riêng đúng workflow, đúng facts, phân biệt user intent với inference và chất lượng clarify. Memory đo extraction/update/temporal/abstention, không chỉ retrieval hit. Automation đo business outcome có receipt, manual corrections, duplicate attempts và unsupported handling. Theo dõi tỷ lệ dismiss gợi ý để tránh trợ lý gây phiền.

### Lệnh kiểm tra tham chiếu khi triển khai sau

Các lệnh dưới đây dựa trên scripts/package/test paths đã đọc, **chưa chạy trong lần lập kế hoạch**. Trước chạy: đọc test/runner để xác định side effects, dùng runtime đã có, xác minh output paths ở workspace; không tạo/reset DB thật hoặc ghi ngoài scope. Không tự install/update dependencies chỉ để chạy lệnh.

```powershell
# Chạy từ workspace root; lựa chọn subset phù hợp thay đổi.
pnpm --filter web lint
pnpm --filter web test -- src/features/chat/history.test.ts src/features/chat/sse.test.ts src/features/chat/ChatPanel.test.tsx src/app/chat/page.history.test.tsx src/app/chat/page.resume.test.tsx
python -m pytest tests/unit/conversation/test_sqlite_local_history.py tests/unit/conversation/test_context.py tests/api/test_chat_sse.py
python -m pytest tests/api/test_privacy_notice_consent.py tests/api/test_privacy_authorization.py tests/unit/action/test_confirmation.py tests/security/test_action_confirmation.py
python -m pytest tests/api/test_certificate_stage1.py tests/api/test_service_stage6.py tests/api/test_multi_agent_api.py
```

Nếu test cần temp/cache/base directory, chỉ dùng thư mục mới đúng workspace sau preflight; không cleanup tự động. Build/E2E chọn runtime candidate được bảo toàn theo launcher đã đọc; không chạy build lên snapshot đang dùng hoặc các script chưa kiểm tra. Unit/API tests là bằng chứng kỹ thuật; vẫn cần real browser và phiên thử người dùng theo AI-028.

## 10. Rủi ro, quyết định và rollout

| Điểm cần chốt | Mặc định đề xuất | Khi chốt |
| --- | --- | --- |
| Bản chạy và entry point | Xác minh trước thay đổi, giữ snapshots đang dùng | AI-001 |
| Lưu lịch sử và retention | Theo lựa chọn/thông báo rõ và policy hiện hành; kiểm tra mặc định 30 ngày, không tự lưu vô thời hạn | AI-001/003 |
| Identity demo/SSO và tenant | Server là nguồn danh tính; demo tách thật | AI-001/004 |
| Memory | Off đến khi người dùng opt-in; không dùng memory cá nhân trong temporary | AI-012/022 |
| Automation | Chuẩn bị tối đa trong grant; giữ xác nhận theo thao tác | AI-003/015–018 |
| Notification | Off đến khi chọn trigger/scope/channel; ưu tiên in-app | AI-024 |
| Model/framework/infra mới | Tận dụng hiện có; thay đổi chỉ khi evidence cho thấy cần | AI-001/003/027 |
| Nguồn nghiệp vụ/attachments | Nguồn được phép và còn hiệu lực; OCR không xác thực | AI-002/017 |
| Pilot users/budgets/latency | Synthetic trước; người tham gia và limits phải xác định trước live evaluation | AI-002/027/028 |

Rủi ro chính: sửa sai bản chạy; owner mapping sai; settings hình thức; intent mơ hồ; stale/poisoned memory; manual edits bị ghi đè; quyền thu hồi sau proposal; notification trùng; model/tool retry không giới hạn. Các task/AC tương ứng kiểm soát từng rủi ro, không chỉ dựa prompt.

Rollout đề xuất: candidate local có fixture → pilot được phép → từng capability/cohort. Đọc/chuẩn bị có thể mở trước công cụ ghi. Trước production phải có evidence target/environment, migration/recovery, grants, người nhận/kênh và performance; yêu cầu lập kế hoạch này không cấp quyền production. Khi lỗi, tắt tính năng tương ứng qua cấu hình phát hành và giữ data/readback/manual path; không sửa hoặc vô hiệu hóa safety mechanisms.

## 11. Cách tiếp tục ở lần làm việc sau

1. Đọc tài liệu này và backlog; đọc lại AGENTS hiện hành và direct request mới nhất.
2. Xác minh workspace, git status và trạng thái dirty; không reset/clean/discard để có cây sạch. Không coi văn bản kế hoạch là ủy quyền phá hủy hoặc chạy production.
3. Bắt đầu AI-001 nếu chưa có evidence; revalidate facts vì runtime/code có thể đã đổi từ 14/10/2026.
4. Chọn task planned có dependencies đã verified; chốt exact files, nguồn/fixture/output paths và tests phù hợp trước mutation. Không tự spawn agent vì có backlog; chỉ delegation khi được yêu cầu theo instructions áp dụng.
5. Triển khai và kiểm tra một đơn vị nhỏ có thể review. Ghi evidence và limits; lỗi unrelated từ baseline không sửa âm thầm.
6. Cập nhật status task: planned → in_progress → implemented → verified. implemented chưa đồng nghĩa verified; failed/needs_input ghi lý do và next step. evidence gồm lệnh, exit code, file kết quả không chứa dữ liệu nhạy cảm và build/environment.
7. Kết thúc phiên ghi task vừa làm, kết quả thật, vấn đề còn lại và next_task. Giữ mọi dữ liệu và build; không commit/push/deploy nếu chưa có direct request tương ứng.

Câu lệnh người dùng có thể dùng để bắt đầu sau: **“Thực hiện kế hoạch docs/ASSISTANT_IMPLEMENTATION_PLAN_20261014.md, bắt đầu từ AI-001; đọc backlog, kiểm tra trạng thái hiện tại và bảo toàn mọi dữ liệu.”**

Backlog có `next_task: AI-001`, toàn bộ status planned, evidence rỗng và implementation_started false. Đây là trạng thái trung thực tại lúc bàn giao kế hoạch; không có automation hoặc công việc nền được tạo.

## 12. Nguồn tham chiếu

- Yêu cầu trực tiếp trong cuộc chat và hai tài liệu đề xuất nội bộ nêu đầu trang.
- Mã nguồn tại các khu vực nêu trong phần hiện trạng/task; sự tồn tại code/test không chứng minh bản chạy đã đạt.
- [react-markdown](https://github.com/remarkjs/react-markdown): render Markdown và giới hạn khi tùy chỉnh/plugins.
- [OWASP Authorization](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html), [AI Agent Security](https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html): quyền từng request, tool/memory/source boundaries.
- [LongMemEval](https://arxiv.org/abs/2410.10813), [AgentDojo](https://arxiv.org/abs/2406.13352): thiết kế các nhóm kiểm chứng memory và agent dùng công cụ. Không phải yêu cầu mua/chạy model hoặc bằng chứng chất lượng Campus 24/7.
