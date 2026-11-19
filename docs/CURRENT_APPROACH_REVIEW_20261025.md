# Phản biện cách làm Campus 24/7 — 25/10/2026

## Kết luận

Hướng nền tảng phù hợp với mục tiêu tra cứu nguồn HUCE công khai: dùng tài liệu thật, bảo toàn original, giữ phạm vi khóa/năm/chương trình, đối chiếu cấu trúc và kiểm chứng nguồn. Thu hẹp sang 24 nguồn CNTT và 22 nguồn dùng chung là quyết định đúng.

Cách triển khai và chứng minh chất lượng hiện tại chưa tối ưu. Công việc đang thiên về sửa từng ca rồi chạy lại các câu đã biết. Cần ưu tiên chất lượng bộ chấm, khả năng trả lời câu hỏi mới và chi phí đường xử lý. Không có bằng chứng trong đợt rà soát này buộc phải thay BGE hoặc PostgreSQL/pgvector.

## Phạm vi kiểm định

- Đọc code runtime, chọn tài liệu, xử lý câu trả lời, parser, bộ tạo ca kiểm và bộ chấm; đối chiếu báo cáo và receipt generation 27.
- Kiểm runtime hiện hữu bằng `scripts/knowledge_platform_runtime.py status`: DB schema 0018, release `01a172fe-1822-7679-a515-335e063dd1fa`, generation 27, policy generation 3, live ack và frontend đạt tại thời điểm kiểm.
- Truy vấn PostgreSQL trong transaction chỉ đọc: 114 thành viên; 111 dùng processor source-bound-snapshot, ba dùng processor khác.
- Thử nghiệm các hàm chọn tài liệu và chấm điểm trong bộ nhớ; không thay đổi receipt hoặc code ứng dụng.
- Không chạy một chiến dịch hỏi đáp mô hình mới. Replay bộ chấm là kiểm chứng bộ chấm, không phải chạy lại chatbot. Số thời gian dưới đây lấy từ receipt đã có, không phải phép đo tải mới.

## 1. P1 — Số ca đạt đang mạnh hơn điều bộ chấm thực sự chứng minh

`scripts/assess_huce_public_details_live_second.py:58` kiểm trạng thái, sự hiện diện của các từ/cụm cần có, đúng nguồn và trang ở một số ca. `scripts/report_huce_evidence_20261025.py:66` kiểm hash, quyền đọc và thành viên release. Những kiểm tra này hữu ích nhưng không bảo đảm toàn bộ câu trả lời đúng hoặc không có chi tiết thừa sai.

Thử nghiệm độc lập:

1. Nạp receipt của `live-verdict-224-01.json`, thực thi lại nhánh chấm trong `assess_huce_public_details_live_second.py` trong bộ nhớ và giữ nguyên đánh giá nhánh hồi quy cũ được hàm `assess` riêng xử lý; tổng vẫn đúng 223/224. Đây không phải replay lại toàn bộ các bộ chấm lịch sử.
2. Trong bản sao nằm trong bộ nhớ, thêm câu “Học kỳ này còn bắt buộc học môn 999999, 99 tín chỉ.” vào câu trả lời `cs_semester_1`.
3. Chấm lại: ca này vẫn `passed=true`, không có lỗi. Receipt gốc không bị sửa.

Đây là lỗ hổng của bộ chấm; không phải bằng chứng chatbot đã tạo câu bịa đó hoặc runtime bỏ qua mọi kiểm chứng. Runtime còn EvidenceGate và kiểm chứng ngữ nghĩa, nhưng nghiệm thu độc lập cần phát hiện được khi những lớp này lọt lỗi.

Nguồn tạo câu và đáp án kỳ vọng cũng có liên hệ chặt: `scripts/probe_huce_bound_curriculum_second.py:24` tạo câu theo học kỳ/đường nối từ chính hồ sơ đối chiếu; `scripts/prepare_huce_it_common_live_second.py:45` lấy kỳ vọng từ probe để tạo bộ API. Đây là hồi quy tốt, chưa phải một tập câu mới độc lập với quá trình sửa.

**Ưu tiên:** giữ bộ hồi quy; bổ sung bộ kiểm riêng chưa dùng để sửa code. Với bảng/môn/quan hệ, so sánh tập kết quả có cấu trúc, kiểm cả phần thiếu, phần thừa, chiều quan hệ, đơn vị và điều kiện. Với văn bản, chấm phủ định, ngoại lệ, tính liên quan và khả năng giải quyết yêu cầu. Không dùng tỷ lệ từ khóa làm chỉ số duy nhất của tính đúng.

## 2. P1 — Thu hẹp tài liệu có thể loại mất nguồn cần thiết

`preferred_document_versions` trong `services/api/src/campus247/application/knowledge/document_reference.py:7` có nhánh chọn riêng tài liệu học phí. Runtime tại `services/api/src/campus247/infrastructure/knowledge/runtime.py:350` dùng kết quả này thay toàn bộ danh sách phiên bản được tìm.

Thử bằng hai tiêu đề có thật và câu hỏi:

> Đối chiếu QĐ 924 và Quy chế 1486: mức học phí K71 và giới hạn khối lượng đăng ký học kỳ là gì?

Hàm chỉ chọn tài liệu học phí, bỏ Quy chế 1486. Thử nghiệm xác nhận hành vi của bộ chọn; chưa đo câu trả lời cuối bằng mô hình. Dù bước sau có từ chối an toàn, nó vẫn không nhận đủ nguồn để giải quyết cả hai yêu cầu.

**Ưu tiên:** phân biệt ưu tiên xếp hạng với giới hạn phạm vi cứng. Nhận diện nhiều văn bản và nhiều ý hỏi; lấy hợp các nguồn cần thiết hoặc tách câu hỏi. Chỉ giới hạn cứng khi có căn cứ rõ người dùng yêu cầu đúng một phạm vi. Giữ nguyên lọc quyền và hiệu lực nguồn.

## 3. P2 — Có dấu hiệu phụ thuộc cách viết câu kiểm thử

`named_notice_rerank_question` tại `document_reference.py:50` yêu cầu tiền tố cụ thể và dấu phẩy. Ba câu cùng mục tiêu đã kiểm:

- “Theo thông báo học bổng STEM Quỹ Châu Á năm học 2025-2026, số văn bản và ngày ban hành là gì?”: nhận diện.
- “Thông báo học bổng STEM Quỹ Châu Á năm học 2025-2026 có số và ngày nào?”: không nhận diện.
- Câu đầu đổi dấu phẩy thành dấu hai chấm: không nhận diện.

Điều này chỉ chứng minh nhánh xử lý riêng không ổn định theo diễn đạt; chưa chứng minh cả hai câu sau thất bại toàn tuyến. Cùng với chuỗi năm bộ xử lý trình bày riêng tại `agent/nodes/async_io.py:90`, nó cho thấy rủi ro tăng ngoại lệ theo câu hỏi.

**Ưu tiên:** dùng nhận diện ý hỏi/văn bản dùng chung, dữ liệu nguồn có cấu trúc và các biến thể ngôn ngữ để kiểm. Tận dụng schema `curriculum_geometry` và các pipeline đang có. Đưa dữ kiện từng tài liệu vào dữ liệu được quản lý phiên bản; giới hạn code ở quy tắc tổng quát. Không cần viết lại toàn bộ hệ thống hoặc bỏ kiểm chứng ảnh.

## 4. P2 — Đường tìm kiếm có chi phí lặp rõ ràng

Mỗi `_search` tại `infrastructure/knowledge/runtime.py:320` đọc danh sách thành viên, gọi `repo.version` cho từng thành viên và `read_snapshot` cho từng phiên bản. `application/knowledge/source_snapshot.py:123` đọc hai bản ghi artifact, hai file, kiểm hash và dựng lại phạm vi với mỗi source-bound-snapshot.

Với release hiện có, riêng vòng tiền xử lý này tương ứng 1 + 114 + 2×111 = **337 lượt SELECT metadata và 222 lần đọc artifact**, theo đường code thành công; chưa tính tìm kiếm, hậu xử lý và các kiểm tra khác. Đây là đếm thao tác từ code và phân bố processor trong DB, chưa phải trace profiler.

Receipt 224 câu có thời gian hoàn tất trung vị **6,86 giây**, p95 theo thứ tự mẫu khoảng **9,48 giây**, tối đa **10,93 giây**. Không dùng p95 toàn tuyến này để so trực tiếp với ngưỡng chỉ dành cho retrieval. Chưa đo được tỷ trọng thời gian của DB, file, BGE, tạo câu trả lời và kiểm chứng ngữ nghĩa.

**Ưu tiên:** đo từng giai đoạn; batch metadata và chuẩn bị snapshot bất biến theo release/version/hash. Cache phải có ranh giới tenant/phạm vi phù hợp, vô hiệu hóa theo generation/policy và giữ kiểm thu hồi/quyền hiện tại. Không giảm bảo vệ để lấy tốc độ. Đo trước/sau trên cùng bộ câu và tải; chưa có căn cứ đổi mô hình hay bỏ semantic verifier.

## 5. P2 — Độ phủ và tiêu chí hoàn thành còn lệch về số tài liệu/số ca

Trong bộ 224: **167 answered, 57 abstained; 218 ca không nối tiếp, sáu ca nối tiếp**. Câu trả lời có nguồn đọc lại đến từ **16 mã nguồn khác nhau**. Điều này không chứng minh 30 nguồn còn lại chưa từng được kiểm ở nơi khác; nó giới hạn kết luận có thể rút ra từ chính lượt 224.

223/224 bao gồm cả từ chối đúng; không phải 223 câu được giải đáp. Bộ này cũng chứa nhiều câu nêu sẵn mã văn bản, mã chương trình và khóa. Cần đo riêng câu đủ căn cứ nhưng bị từ chối, câu thiếu căn cứ nhưng vẫn trả lời, câu cần hỏi lại và câu nối tiếp giữ đúng bối cảnh.

Có 147 script Python mang tên HUCE, khoảng 14.727 dòng tại thời điểm kiểm. Số lượng này không tự chứng minh thiết kế sai: script thu thập và chứng cứ có giá trị. Tuy vậy, kết hợp với các helper theo tài liệu, nó cho thấy chi phí tiếp tục vận hành bằng nhiều lần sửa/chạy lệnh riêng. Parser worker hiện đọc text/PDF bằng `pypdf`; scan được gắn cờ review, còn cấu trúc phức tạp được xử lý bằng pipeline/script khác. Chưa có phép thử mới chứng minh admin đưa một tài liệu phức tạp chưa biết trước qua toàn bộ luồng mà không cần vá Python.

**Ưu tiên:** quản lý tiến độ theo việc sinh viên cần làm: hỏi học phí đúng hệ/khóa, điều kiện học vụ, tra môn/học kỳ/quan hệ, làm thủ tục và mở đúng nguồn. Chọn 30–50 câu mới cho các nhu cầu ưu tiên, có câu ngắn, thiếu thông tin, nhiều ý, nối tiếp và nguồn mâu thuẫn. Đây là quy mô khởi đầu được đề xuất, không phải ngưỡng đã được kiểm chứng.

## 6. Giới hạn vận hành và tích hợp

SSO/API HUCE thật chưa được nối; không thể suy ra lịch, điểm hay hồ sơ cá nhân từ kho công khai. Báo cáo readiness đã phân biệt đúng điều này. Công việc tra cứu công khai có thể tiến tiếp độc lập; việc có SSO không thay cho chất lượng truy hồi nguồn.

Bộ sao lưu sau lượt 224 có hash/kiểm tra riêng từng kho nhưng chưa được restore và chưa chứng minh nhất quán xuyên PostgreSQL/SQLite. Không nên suy mức sẵn sàng production từ việc runtime đang sống hoặc có backup. Bước phục hồi thử vào namespace mới và kiểm hành trình UI trên release hiện hành cần được ưu tiên trước tuyên bố vận hành ổn định. Giữ nguyên mọi backup và dữ liệu hiện có.

## Thứ tự làm được đề xuất

1. Sửa cách nghiệm thu: bộ kiểm độc lập, phần thừa sai, độ phủ ý hỏi và phân loại từ chối. Đóng băng kỳ vọng trước khi sửa runtime.
2. Sửa mất nguồn ở câu nhiều văn bản; kiểm biến thể diễn đạt và hội thoại nối tiếp.
3. Đo rồi giảm đọc metadata/artifact lặp; chưa đổi model hoặc viết lại kiến trúc.
4. Tận dụng pipeline hiện có để kiểm một tài liệu mới qua UI từ nhập đến trả lời có nguồn; đưa chỗ cần review thủ công thành hàng đợi rõ ràng.
5. Hoàn thiện phần còn thiếu theo nhu cầu người dùng và mức rủi ro, kiểm trình duyệt/phục hồi; nối dữ liệu cá nhân khi có thông tin và quyền thật.

**Tiêu chí tiến bộ:** tăng tỷ lệ giải quyết đúng câu mới có căn cứ, giữ lỗi trả lời sai và lộ quyền ở mức được kiểm rõ, giảm từ chối nhầm và thời gian/chi phí; công bố đúng phạm vi. Số file, số release, số chunk và số câu hồi quy đạt là bằng chứng hỗ trợ, chưa đủ để đại diện cho trải nghiệm sử dụng.

## Bằng chứng chính

- `infra/local/huce-completion-20261025-02/live-verdict-224-01.json` và receipt được trỏ trong đó.
- `infra/local/huce-completion-20261025-02/it-common-checkpoint-01.json`.
- `infra/local/huce-completion-20261025-02/api-code-fingerprint-20.json`: 16 tệp được pin đều còn khớp tại lúc rà soát; không phải manifest hash toàn bộ ứng dụng.
- `docs/HUCE_ACTIVE_DOCUMENT_SCOPE_20261025.md`, `docs/HUCE_EVIDENCE_GEOMETRY_PROGRESS_20261025.md`, `docs/HUCE_INTEGRATION_READINESS_20261025.md`.

Đợt này chỉ thêm báo cáo kiểm định; không thay đổi code ứng dụng, nguồn, bản phát hành hoặc cấu hình bảo vệ.
