# Campus 24/7 — Kế hoạch triển khai quản trị tri thức RAG

Ngày: 23/10/2026. Spec: [KNOWLEDGE_PLATFORM_SPEC_20261023.md](KNOWLEDGE_PLATFORM_SPEC_20261023.md).

Đây là kế hoạch công việc, chưa phải báo cáo đã triển khai. Không yêu cầu duyệt tài liệu trước khi làm. Phạm vi yêu cầu hiện tại là viết spec/kế hoạch; không tự coi tài liệu này là bằng chứng code đã chạy hoặc quyền phá hủy dữ liệu.

## 1. Cách triển khai và báo tiến độ

- Thực hiện theo lát chức năng: sớm có một tài liệu đi từ UI tới câu trả lời có nguồn, rồi mở rộng định dạng và tự động hóa. Không chờ hoàn thiện mọi parser hoặc benchmark lớn mới nối runtime.
- Người thực hiện tự quyết định chi tiết và điều chỉnh bước dựa mã nguồn/đo đạc. Đổi kỹ thuật đáng kể thì ghi ngắn lý do, tác động, kết quả; không tạo thêm approval packet.
- Mỗi bước kết thúc bằng code chạy được, kiểm chứng đúng rủi ro của bước và bản ghi ngắn: đã làm, cách thử, kết quả, hạn chế, việc kế tiếp. Không tạo task JSON hoặc cập nhật sổ governance nếu không giúp thực thi.
- Bảo toàn mọi thay đổi có sẵn. Chỉ sửa file cần cho mục tiêu; không chạy reset/clean/downgrade hoặc chỉnh dữ liệu cũ để test xanh.
- Chỉ báo cần quyết định khi thực sự nguy hiểm hoặc thiếu quyền: phá hủy dữ liệu, production/ngoài workspace, rò rỉ dữ liệu, đổi bảo vệ, chi phí ngoài ngân sách. Không hỏi lại các lựa chọn kỹ thuật thông thường đã được giao.
- Quyền linh hoạt kỹ thuật không bỏ luồng xác nhận/phân quyền của ứng dụng. Xung đột với bảo vệ hiện hữu phải giữ bảo vệ và nêu đúng blocker.

## 2. Các mốc bàn giao

| Mốc | Sau bước | Người dùng nhận được |
|---|---|---|
| M1 — Luồng thật đầu tiên | 01–07 | Một tài liệu thật upload → xử lý → duyệt → kích hoạt → chatbot trả lời có nguồn |
| M2 — Quản trị đầy đủ | 08–09 | Định dạng đa dạng, xử lý ngoại lệ, so phiên bản và thao tác qua UI |
| M3 — Kho HUCE thống nhất | 10 | Catalog thật và corpus chatbot thống nhất, dữ liệu lịch sử giữ nguyên |
| M4 — Tự động hóa | 11–12 | Đồng bộ theo lịch, đánh giá ứng viên, phát hành theo chính sách hợp lệ |
| M5 — Chạy ổn trên máy | 13–14 | Số đo RAM/tốc độ, phục hồi lỗi, runbook và demo hoàn chỉnh |

Đây là thứ tự phụ thuộc, không phải cổng xin phép. Có thể đo tài nguyên/viết test sớm hơn và gộp bước. BGE cùng CPU/RAM giới hạn được giữ xuyên suốt; không mở nhánh đổi model trong chiến dịch này.

## 3. Bước 01 — Chụp hiện trạng và chọn runtime đích

**Thực hiện**

1. Đọc trạng thái Git, resolve workspace và vùng file sẽ sửa. Không gộp/ghi đè thay đổi có sẵn.
2. Xác định process/API/frontend đang phục vụ, catalog nào UI đang gọi, corpus/profile/index nào chat đang đọc. Chỉ đọc metadata cần thiết, không in token hoặc chuỗi kết nối có mật khẩu.
3. Kiểm schema PostgreSQL thực tế, migrations hiện có và DB SQLite demo; không suy ra DB đang dùng từ giá trị mặc định trong script.
4. Liệt kê file, ID, hashes, ready/withdrawn markers, FAQ và nguồn chưa rõ quyền/hiệu lực. Ghi inventory mới có phiên bản, không sửa kho đầu vào.
5. Đo baseline API idle, BGE/model processes, một lượt chat và một job hiện có nếu phù hợp. Kiểm phiên bản Python/Node/PostgreSQL/runtime BGE; chỉ cài phần còn thiếu.

**Đầu ra:** một bản ghi baseline/inventory, sơ đồ binding UI → API → corpus, danh sách file cần sửa và môi trường phát triển đích. Chọn đích dữ liệu mới bổ sung trong workspace, không tự tác động production.

**Kiểm chứng:** có thể truy vết một citation đang hoạt động về source/version/hash. Nếu runtime hiện không chạy, báo chưa đo live và dùng cấu hình đã đọc để tiếp tục phần độc lập; không bịa baseline.

## 4. Bước 02 — Bổ sung schema và lớp lưu trữ

**Thực hiện**

1. Đối chiếu entities trong spec với các bảng `knowledge_*`, manifest/pointer, audit/outbox hiện có.
2. Tạo migration bổ sung cần thiết cho artifact, jobs/checkpoints, review binding, release membership và runtime ack; chọn revision sau kiểm migration heads, không đoán số kế tiếp.
3. Khai báo unique keys, tenant scope, expected revision/generation, idempotency và fencing token.
4. Xây storage port + filesystem adapter: stream, checksum, key do server tạo, exclusive artifact writes, resolved path trong storage root hợp lệ.
5. Quy định thứ tự file/DB commit và reconciliation khi artifact đã ghi nhưng transaction thất bại; không tự dọn orphan.

**Vùng code dự kiến:** `services/api/migrations/versions/`, `domain/`, `ports/`, `infrastructure/repositories/`, adapter storage mới theo convention dự án.

**Kiểm chứng:** chạy migration trong DB phát triển mới có tên rõ, kiểm schema trước/sau, giữ nguyên bảng/row cũ; round-trip artifact, chặn traversal/reparse, kiểm unique keys. Không test bằng reset DB chưa được xác định disposable và cấp quyền.

**Xong khi:** nguồn, version, job và artifact có thể lưu/đọc qua repository thật; không cần parser hoàn chỉnh.

## 5. Bước 03 — Tiếp nhận tài liệu qua API và UI tối thiểu

**Thực hiện**

1. Bổ sung API tạo nguồn, multipart version upload, đọc version/job/artifact có kiểm quyền.
2. Nhận PDF/TXT trước. Kiểm MIME, bytes, metadata tối thiểu và quota; trả `202` với job/version ID.
3. Dùng idempotency key để submit lại cùng request không sinh version lặp. Dedup byte không tự hợp nhất hai nguồn nghiệp vụ hoặc tenant khác.
4. Thêm form upload thật và danh sách job tối thiểu vào trang quản trị hiện có. Chỉ gắn nhãn demo cho phần còn dùng demo.
5. Giữ read API tương thích nơi cần; không tạo catalog thứ ba khác nguồn runtime đích.

**Vùng code:** `presentation/knowledge.py`/router phù hợp, `application/knowledge/`, `apps/web/src/lib/data/api/`, `apps/web/src/features/knowledge/` và routes hiện có.

**Kiểm chứng:** admin upload được, student bị từ chối, upload trùng request trả cùng kết quả, file quá giới hạn/MIME sai có lỗi rõ; viewer không lộ đường dẫn nội bộ.

**Xong khi:** thấy original + version + job `QUEUED` từ giao diện, không xử lý OCR ngay trong HTTP request. Bao phủ AC-01 một phần, AC-05 đầu vào.

## 6. Bước 04 — Worker bền vững và checkpoint

**Thực hiện**

1. Mở rộng `services/worker/src/campus247_worker/main.py` thành vòng poll thực tế có shutdown an toàn.
2. Nhận job bằng `SKIP LOCKED`, lease, heartbeat và fencing token; commit transaction nhận việc trước khi thực thi.
3. Dispatch từng stage; adapter parser ban đầu xử lý TXT/PDF có chữ bằng thư viện đã có.
4. Checkpoint chứa input/config/output hashes; stage thành công được reuse, stage lỗi retry có backoff giới hạn.
5. Chạy parser trong process con thuộc job, timeout và thu thập peak working set; cancel tại ranh giới phù hợp, không dừng process khác.
6. Hiển thị lỗi nghiệp vụ khác lỗi tạm thời; `RESOURCE_WAIT` có thể là lý do chờ trong job, không làm mất job.

**Kiểm chứng:** restart worker sau artifact write và sau DB commit; process A lease hết hạn, B nhận lại, A trả muộn không được commit. Thử retry/cancel và crash trong bước extraction; kết quả không trùng.

**Xong khi:** hàng đợi chạy qua restart mà không cần admin sửa DB. Bao phủ AC-02/03.

## 7. Bước 05 — Chunk, BGE và chỉ mục ứng viên PostgreSQL

**Thực hiện**

1. Tái sử dụng parser/chunker/indexer hiện có; thêm locator cho page/block và parent context.
2. Tạo index text/hash riêng với evidence. Cache vector theo toàn input và profile, không chỉ theo số thứ tự chunk.
3. Gọi dịch vụ BGE dùng chung, batch 1 khởi đầu; giữ revision, vector dimension và normalization đã kiểm chứng.
4. Tạo release membership bao gồm nguồn mới và nguồn giữ lại; ghi chunk/vector theo manifest ứng viên.
5. Dùng adapter PostgreSQL lexical/vector; bổ sung filter release membership, quyền, campus/tenant và hiệu lực. Đo recall khi dùng ANN + filter.
6. Hợp nhất RRF, BGE rerank ứng viên có giới hạn; không đổi embedding model để sửa một ca retrieval chưa hiểu nguyên nhân.

**Vùng code:** worker ingestion, `application/retrieval/`, `infrastructure/retrieval/postgres_lexical.py`, `postgres_vector.py`, manifest domain, runtime config.

**Kiểm chứng:** exact locator, model mismatch bị từ chối, job lặp không sinh chunk/vector lặp; cả lexical và vector không trả nguồn ngoài release/quyền. Test offline dùng fake có nhãn chỉ để kiểm contract; chạy smoke BGE thật trước khi kết luận retrieval hoạt động.

**Xong khi:** search-preview trên release ứng viên tìm được đoạn từ tài liệu upload và chỉ rõ nguồn. Bao phủ AC-05/09 một phần.

## 8. Bước 06 — Review, release và serving acknowledgement

**Thực hiện**

1. Gắn review với hash rendition + metadata quan trọng; giữ reviewer độc lập và preview/confirmation đang có.
2. Tạo preview release: nguồn thêm/giữ/thay/thu hồi, lỗi chất lượng, profile, expected generation và test summary.
3. Xác nhận bằng transaction đổi desired pointer + audit + outbox. Retry cùng key không tạo activation lặp.
4. Runtime preflight/prepare candidate, chuyển snapshot và ack instance/boot/generation sau khi sẵn sàng phục vụ.
5. UI đọc desired/serving riêng; ack hết hạn hoặc load lỗi không báo đang dùng.
6. Thêm revocation độc lập với build; rollback kích hoạt lại release cũ nhưng giữ quyền/revocation hiện tại.

**Kiểm chứng:** race hai activation chỉ một expected generation thắng; lỗi trước/sau pointer commit, ack cũ, restart runtime và load lỗi đều có trạng thái đúng. Kiểm rollback không làm tài liệu thu hồi xuất hiện lại.

**Xong khi:** admin thấy chính xác release nào đang phục vụ và có thể khôi phục bản trước bằng luồng có xác nhận. Bao phủ AC-06/07/08.

## 9. Bước 07 — Nối chat thật: hoàn thành lát chức năng M1

**Thực hiện**

1. Bổ sung binding adapter/release trong bootstrap app; lựa chọn runtime explicit bằng cấu hình, không âm thầm đổi mọi launch script.
2. Dùng cùng snapshot cho lexical/vector/parent/citation trong một lượt hỏi.
3. Nối evidence gate, claim checks và citation source reader hiện có; response/history lưu release ID và source version.
4. Kiểm quyền/revocation trước khi compose/stream và lúc mở citation. Khi dữ liệu đổi giữa lượt hỏi, regenerate hoặc trả thông báo giới hạn.
5. Tạo vài câu hỏi có locator kiểm chứng cho tài liệu vừa upload và một ca không có đáp án.

**Kiểm chứng:** E2E admin upload → xử lý → người có quyền duyệt → activate → runtime ack → chat có nguồn đúng → mở đúng trang/mục. Sau thu hồi, chat/citation mới không dùng nguồn đó. Không gọi script thủ công để hoàn tất nạp.

**Xong khi:** demo M1 chạy từ UI. Ghi rõ đây là số ít tài liệu, chưa phải toàn kho hoặc nghiệm thu chất lượng tổng thể. Bao phủ AC-01/05/06/07/08/13 cho lát đầu tiên.

## 10. Bước 08 — Docling, Tesseract và đối chiếu trang khó

**Thực hiện**

1. Đánh giá dependency/license/version và Windows CPU runtime trên mẫu nhỏ; tách môi trường parser nếu xung đột với API.
2. Thêm Docling adapter cho bảng/bố cục phức tạp, DOCX/HTML; không OCR lại PDF có text tốt.
3. Cài adapter Tesseract cùng dữ liệu `vie`/`eng`, render theo trang có giới hạn pixel.
4. Thêm kiểm tra trang thiếu, số/ngày/đơn vị, hàng/cột, header/footer và dấu tiếng Việt; lưu confidence như tín hiệu.
5. Tạo issue theo page/bbox, màn hình ảnh–text; sửa OCR tạo rendition mới và invalidate review/index tương ứng.
6. Với DOCX, dẫn paragraph/table/cell; chỉ dùng trang khi có rendition phân trang đã xác minh.

**Kiểm chứng:** bộ nhỏ đa dạng gồm trang text, scan mờ, nhiều cột, bảng dài, DOCX; so nội dung quan trọng với nguồn. Tài liệu ngoài khả năng phải vào `NEEDS_REVIEW`, không lặng lẽ mất trang.

**Xong khi:** upload các định dạng hỗ trợ qua cùng pipeline và admin giải quyết được lỗi; chưa có GPU vẫn vận hành được hàng chờ. Bao phủ AC-04.

## 11. Bước 09 — Hoàn thiện trải nghiệm quản trị

**Thực hiện**

1. Thư viện tìm/lọc theo nguồn, đơn vị, hiệu lực, trạng thái phục vụ, lỗi và quyền.
2. Batch upload có kết quả từng file; tiến độ từng công đoạn, retry/cancel, polling backoff và khôi phục màn hình khi reload.
3. Xem original, rendition, chunks và trích dẫn; diff cũ–mới, cảnh báo thay đổi số liệu/hiệu lực.
4. Review/preview/confirm dùng phiên thật; không bật nút chỉ dựa role frontend.
5. Trang chất lượng có search-preview, release membership, desired/serving và lịch sử audit.
6. Rà đường dẫn, menu, trạng thái trống/lỗi và responsive; phần demo được phân biệt, không che lỗi backend bằng mock.

**Kiểm chứng:** test UI các trạng thái lỗi/race, kiểm API auth; browser E2E luồng chính, keyboard, reload và mạng gián đoạn. Không cần snapshot test cho mọi chi tiết trang.

**Xong khi:** người dùng quản trị được tài liệu mà không biết đường dẫn file hoặc câu lệnh. Hoàn thành M2, AC-13.

## 12. Bước 10 — Nhập toàn kho HUCE và chuyển runtime có đối chứng

**Thực hiện**

1. Viết importer dùng inventory bước 01, chỉ đọc nguồn cũ và ghi namespace/bảng bổ sung; dry-run trước để báo lượng nguồn/version/chunk và vấn đề.
2. Mapping source/version/chunk/FAQ/locators, hash và review provenance; không giả định toàn bộ marker là human approval.
3. Giữ withdrawal/supersession có bằng chứng; nguồn chưa xác minh bị loại khỏi serving hoặc chuyển review rõ ràng.
4. Reuse vector chỉ khi đủ input/profile hash; thiếu điều kiện thì queue rebuild. Không ép model version từ dimension.
5. Đối chiếu counts theo nguồn, hashes, citation locators và câu hỏi baseline. FAQ dẫn về evidence thật, không tự nâng câu trả lời tổng hợp thành văn bản ban hành.
6. Build release đầy đủ, chạy shadow queries trên tập được phép; giữ runtime cũ để quay lại, không trộn kết quả hai snapshot.
7. Cutover local qua cấu hình explicit; verify runtime ack và catalog. Việc production nếu phát sinh phải báo riêng.

**Kiểm chứng:** importer chạy lại không lặp dữ liệu; sai checksum bị chặn; file cũ giữ nguyên; sample mỗi nhóm nguồn và toàn bộ ca thu hồi/quyền quan trọng được kiểm. Báo danh sách chưa nhập/chưa phục vụ, không che bằng tổng số.

**Xong khi:** UI và chatbot cùng nhìn một kho thật; không bắt buộc nhập cả tài liệu chưa đủ bằng chứng vào serving. Hoàn thành M3, AC-11.

## 13. Bước 11 — Đồng bộ nguồn tự động

**Thực hiện**

1. Xây source config: URL/domain, phạm vi follow links, lịch, giới hạn fetch, loại tài liệu và owner.
2. Fetch HTTP trước, Crawl4AI khi cần JavaScript; giới hạn browser/concurrency, URL depth, bytes và timeouts.
3. Kiểm DNS/IP/redirect để chặn internal/private/link-local/metadata; mock network để test, không dò mạng nội bộ thật.
4. Lưu ETag/Last-Modified và body/file fingerprint; thay nội dung mới tạo version, lỗi nguồn chỉ tạo sync issue.
5. Scheduler nhận lịch bằng khóa DB, chống hai lần chạy cùng cửa sổ; backoff khi website lỗi và giữ thông tin lần thành công gần nhất.
6. Tự đưa version mới qua pipeline; thông báo chỉ khi có thay đổi, lỗi cần xử lý hoặc hoàn thành đáng chú ý.

**Kiểm chứng:** unchanged, changed, redirect nguy hiểm, timeout, 404, attachment đổi, hai scheduler và restart; không nhân version hoặc thu hồi vô căn cứ.

**Xong khi:** admin đăng ký nguồn, lần đồng bộ sau tự tạo ứng viên khi nội dung thật sự đổi. Bao phủ AC-12.

## 14. Bước 12 — Kiểm thử chất lượng và tự xuất bản có điều kiện

**Thực hiện**

1. Tập khởi đầu khoảng 40–60 câu hỏi đa dạng, mở rộng theo lỗi thực tế; tách tuning và holdout. Mỗi đáp án chuẩn có source/version/locator được kiểm chứng.
2. Nhóm case: có/không đáp án; điều kiện/ngoại lệ; số tiền/ngày/mã học phần; không dấu; bảng; nhiều tài liệu; lịch sử/hiệu lực; mâu thuẫn; quyền/thu hồi; nội dung có chỉ dẫn độc hại.
3. Đo Recall@k/ranking, correctness từng claim quan trọng, citation support, abstention khi thiếu bằng chứng, latency và RAM. Chọn ngưỡng trước khi so release trên holdout.
4. Tích hợp Ragas chọn lọc để phân tích; giữ kiểm tra bằng mã và đáp án người kiểm chứng. LLM judge/synthetic questions không tự trở thành ground truth.
5. Release check chạy phần bị ảnh hưởng và một regression core; không cần chạy mọi benchmark lịch sử sau mỗi sửa nhỏ.
6. Triển khai policy auto-publish dưới feature flag mặc định tắt. Chỉ bật khi cấu hình quyền hiện hành cho phép, loại nguồn ít rủi ro, metadata rõ, không có issue và checks đạt. Nếu cần đổi bảo vệ hiện có thì báo, không tự bỏ reviewer.

**Kiểm chứng:** cố ý làm sai số/ngày/locator trong fixture thì checks bắt được; release fail không đổi pointer; auto-publish ghi service actor/policy/hash và vẫn có audit. Không dùng tự động hóa để vượt confirmation cần có của sản phẩm.

**Xong khi:** có báo cáo chất lượng tái lập và pipeline tự dừng ứng viên lỗi. Hoàn thành M4, AC-09.

## 15. Bước 13 — Đo RAM, điều chỉnh và phục hồi vận hành

**Thực hiện**

1. Đo working set cây process, RAM khả dụng, model residency và queue age trong idle, chat, nạp, nạp kèm chat. Không tính tổng file weights thành RAM thực tế.
2. Giữ heavy concurrency 1, CPU thread cap và batch nhỏ; giảm top rerank/context có cơ sở, kiểm lại chất lượng sau điều chỉnh.
3. Chọn thời điểm chạy embedding nền; dành ưu tiên chat giữa các batch. Nếu thiếu RAM thường trực, tách model service hoặc giảm dịch vụ resident rồi đo lại.
4. Đặt RAM low-watermark khởi đầu khoảng 2 GB, heartbeat/resource sampling và timeout; đây là backpressure, không phải giới hạn cứng của toàn Windows.
5. Ghi health/metrics cho worker, parser/model endpoints, database, desired/serving và revocation. Error message có hướng xử lý, không lộ nội dung nhạy cảm.
6. Kiểm backup/restore trong đích mới, restart giữa activation, model endpoint chết, thiếu RAM và artifact chưa commit. Không cố gây cạn ổ thật hoặc giết dịch vụ của người khác.

**Kiểm chứng:** phiên thử tải có thời lượng công bố, bộ tài liệu/câu hỏi cố định và job hoàn tất hoặc báo lỗi có thể phục hồi; không OOM/mất job trong các phiên đó. Báo p50/p95 và peak, không tuyên bố ổn mọi tải chỉ từ smoke test.

**Xong khi:** cấu hình local được chọn bằng số đo, có giới hạn tải trung thực. Bao phủ AC-10 và phục hồi AC-02/07.

## 16. Bước 14 — Bàn giao và chạy thử hoàn chỉnh

**Thực hiện**

1. Viết runbook ngắn: khởi động, tài khoản/role hợp lệ, upload, xử lý lỗi, duyệt, xuất bản, hỏi thử, thu hồi, rollback và phục hồi job.
2. Đưa dependency/model versions, cấu hình tài nguyên, storage root, cổng dịch vụ vào cấu hình tập trung; không đưa secret vào tài liệu.
3. Chạy E2E một vòng quản trị và một vòng đồng bộ; so nguồn trên UI với release/citation runtime.
4. Tổng hợp AC-01…AC-13 theo bằng chứng đã chạy: đạt/chưa đạt/chưa kiểm chứng; ghi giới hạn và backlog thực tế.
5. Kiểm exact diff và Git status; không dọn artifact hoặc thay đổi không liên quan để có trạng thái sạch.

**Xong khi:** người dùng thao tác từ UI, có hướng phục hồi và biết rõ giới hạn. M5 chỉ hoàn thành khi các AC áp dụng đã có kết quả thực, không dựa trên sự tồn tại tài liệu này.

## 17. Kiểm chứng theo mức thay đổi

Các lệnh dưới đây là cách chạy kiểm tra hiện có hoặc mẫu dự kiến; phải chọn đúng runtime/dependencies đã cài và DB đích trước khi chạy. Chưa chạy chúng trong công việc viết tài liệu này.

| Khi nào | Kiểm tra |
|---|---|
| Parser/chunker thay đổi | Unit ingestion và locator, fixture đa định dạng có kiểm nguồn |
| Schema/queue thay đổi | Integration DB mới, transaction/race/lease/restart và preservation |
| Retrieval thay đổi | Filter tests + real BGE smoke + tập HUCE bị ảnh hưởng |
| Release/auth thay đổi | Race activation, ack, review binding, revoke, rollback, cache |
| API contract thay đổi | API/contract checks tương ứng, cập nhật OpenAPI cùng implementation |
| UI thay đổi | Vitest file liên quan, typecheck, browser E2E luồng thật |
| Trước cutover | Regression core, đối chiếu import, dữ liệu quyền/thu hồi và RAM thực đo |

Ví dụ backend hiện có, chạy từ root với runtime đã được xác minh:

```powershell
python -B -m pytest tests/unit/ingestion -q -p no:cacheprovider
python -B -m pytest tests/integration/retrieval -q -p no:cacheprovider
```

Integration tests có thể cần DB/fixture; đọc setup trước, không coi mọi database là disposable. Các test queue/release mới được thêm vào nhóm tương ứng khi implement, không giả vờ đường dẫn test chưa tồn tại.

Frontend, từ `apps/web`:

```powershell
pnpm test -- src/features/knowledge
pnpm lint
```

Typecheck/test có thể ghi cache/artifact; kiểm cấu hình và giữ output cần thiết trong workspace, không overwrite evidence cũ. Build/browser dùng cấu hình bảo toàn build hiện có; không mặc định `next build` đè build của runtime đang chạy.

## 18. Quyết định có thể tự điều chỉnh và điểm báo rủi ro

| Tự xử lý trong mục tiêu đã giao | Báo khi gặp |
|---|---|
| Tên bảng/module, chọn adapter, dependency tương thích, batch/thread, retry/timeouts, cách bố trí UI | Tác động production/nguồn ngoài phạm vi, thay đổi quyền hoặc bảo vệ |
| Gộp bước, thêm test phát hiện lỗi thật, sửa bug, cập nhật cấu hình local có thể phục hồi | Xóa/ghi đè dữ liệu cũ, migration phá hủy, không chứng minh được phục hồi |
| Import bổ sung vào đích local rõ ràng, tái sử dụng vector hợp lệ, quay cấu hình về release trước | Dữ liệu nhạy cảm phải gửi ra ngoài hoặc chi phí chưa được cho phép |
| Ghi ngắn kết quả và chọn công cụ khác nếu đo được tốt hơn trong cùng kiến trúc | Tình huống không xác định được ownership/path hoặc ghi đè công việc sẵn có |

Không cần chờ phản hồi để làm các phần độc lập khi một nhánh bị chặn. Báo đúng phần nguy hiểm, tác động và phương án có thể phục hồi; không biến toàn bộ kế hoạch thành chuỗi xin phép.
