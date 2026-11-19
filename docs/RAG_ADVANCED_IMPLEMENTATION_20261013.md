# Nâng cấp RAG Campus 24/7 — kế hoạch và bằng chứng thực hiện

Ngày: 13/10/2026. Phạm vi: mã nguồn hiện tại, kho HUCE công khai, chat có nguồn.
Thẩm quyền: yêu cầu trực tiếp của người dùng trong chat này. Tài liệu cũ chỉ là tài liệu tham khảo.

## Mục tiêu

Advanced + Conversational RAG dùng được trong pilot: hiểu câu tự nhiên và câu nối tiếp,
tìm bằng chứng đủ điều kiện/ngoại lệ, trả lời có nguồn mở được, phân biệt thiếu nguồn và lỗi.
Bổ sung truy hồi nhiều bước có giới hạn khi câu hỏi cần nhiều nguồn.
Không tuyên bố production readiness từ unit test hoặc một ví dụ tổng hợp.

Đã hoàn tất triển khai và kiểm chứng sáu chặng trong phạm vi pilot local trên
kho HUCE công khai. Bản sửa cuối qua 274 test Python; điểm D trả lời đúng phạm
vi, khoảng 4,0–4,9 và có nguồn hợp lệ ở focused10. Retrieval đã đo coverage nguồn
top3 16/16 so với baseline 13/16; mười lượt dialogue03 qua regression live.
Mức hiện tại là Advanced + Conversational RAG pilot. Các chỉ tiêu chất lượng
độc lập và hạ tầng enterprise thuộc bước đánh giá/rollout tiếp theo.

## Hiện trạng đã đọc

- Nhánh public HUCE dùng BM25 và FAQ aliases; bộ canonical hybrid/reranker nằm ở nhánh riêng.
- Ingestion giữ section nhưng cắt section dài theo ký tự.
- Câu nối tiếp có xử lý tham chiếu văn bản, chưa bao quát câu hỏi ngắn về đối tượng/điều kiện.
- EvidenceGate kiểm citation và overlap từ; chưa kiểm chặt số, đơn vị, phủ định, ngưỡng.
- Có một lần tái tạo generation trong cùng deadline và ngân sách, lịch sử và citation readback.
- Workspace có nhiều thay đổi từ trước; mọi chỉnh sửa giữ nguyên các thay đổi và nguồn cũ.

## Các chặng

| Chặng | Công việc | Đầu ra và kiểm chứng |
|---|---|---|
| 1 — baseline | Đọc wiring/runtime, chạy regression hiện có, tạo bộ câu hỏi độc lập với FAQ | Kết quả trước thay đổi; các lỗi được phân loại |
| 2 — câu hỏi | Giới thiệu khả năng, hỏi làm rõ, đọc/ghi đúng intent; giải tham chiếu từ user goals | Câu nối tiếp giữ điều kiện mới; chuyển chủ đề không kéo nguồn cũ; không dùng lịch sử cấp quyền |
| 3 — tri thức | Chia theo câu/đoạn/điều khoản và bảng; contextual index; child → parent evidence | Nội dung, hash và locator truy ngược nguồn; ngoại lệ không mất; không ghi đè snapshot |
| 4 — retrieval | BM25 + embedding thật → RRF → reranker thật; metadata/authorization trước xếp hạng | So sánh cùng corpus/câu hỏi; runtime thiếu hoặc mismatch có lỗi rõ ràng, không giả vector/rerank |
| 5 — trả lời | Kiểm số/đơn vị/ngưỡng/phủ định; kiểm chứng ý nghĩa qua cổng có giới hạn; phân tách câu hỏi nhiều phần để tìm đủ nguồn | Không chấp nhận câu đảo điều kiện; mọi claim gắn citation; gọi model và retrieval có deadline/call cap |
| 6 — tích hợp | API/SSE, lịch sử, citation, lỗi và browser; đo chất lượng/latency/cost | Báo cáo tái lập, kết quả từng nhóm và giới hạn thực tế |

## Thiết kế thực hiện

- Đặt logic hiểu câu hỏi và đánh giá bằng chứng ở lớp application, ngoài UI/routes.
- Tái sử dụng identity, scope, source provenance, budget ledger và adapter hiện có.
- Cấu hình nhánh public nâng cấp riêng, không sửa các hằng số profile cũ để ép pass.
- Metadata dùng để tìm kiếm tách khỏi excerpt nguồn: summary/FAQ không trở thành chứng cứ.
- Index mới dùng namespace mới, fingerprint corpus/model/chunking và publish sau khi build thành công.
- Mọi lượt tìm bổ sung áp dụng lại scope và hiệu lực. Không cache câu trả lời dùng chung giữa actor.
- Giới thiệu và câu làm rõ được server dựng; dữ kiện nghiệp vụ phải qua evidence gate.
- Tái tạo đầu ra có giới hạn, giữ ngân sách và deadline; UI nhận đúng trạng thái.

## Bộ kiểm tra

Các nhóm: giới thiệu; học bổng; học phí; thủ tục; thư viện; câu thiếu dấu;
câu diễn đạt khác FAQ; nối tiếp về năm học/điều kiện; đổi chủ đề;
nhiều phần; thiếu nguồn; nguồn sai phiên bản; scope sai; model lỗi và output sai.

Đo retrieval recall và precision; claim support/correctness/completeness;
tỷ lệ trả lời, từ chối đúng và từ chối quá mức; lỗi; p50/p95; provider calls/cost.
Mục tiêu pilot: Recall@10 ≥90%, citation precision ≥95%, grounded correctness ≥90%
trên bộ đánh giá có đáp án nguồn được kiểm tra; không có lộ nguồn ngoài quyền.
Chỉ số đó là mục tiêu, không phải kết quả mặc định. Báo riêng deterministic test,
real-source retrieval và live generation. Chỉ dùng provider trong ngân sách hiện có.

## Dữ liệu và phạm vi vận hành

Không xóa/reindex đè corpus, lịch sử hoặc bằng chứng cũ. Không reset database,
không đổi cơ chế bảo vệ, không commit/push/deploy production. Runtime kiểm tra
chỉ bind loopback, dữ liệu phát sinh giữ trong workspace và có thể kiểm tra lại.
Nếu dịch vụ đang chạy, dùng port và namespace riêng; không dừng tiến trình không sở hữu.

## Tiến độ

- [x] Chặng 1: đọc wiring, lập kế hoạch và baseline cùng corpus/dataset.
- [x] Chặng 2: hiểu câu hỏi, làm rõ, câu nối tiếp và đổi chủ đề; kiểm live bằng dialogue03.
- [x] Chặng 3: structured chunking, contextual index, parent–child; build manifest mới.
- [x] Chặng 4: hybrid và reranker thật; scope/model/hash trước xếp hạng; retrieval08 hoàn tất.
- [x] Chặng 5: factual/semantic support, điều kiện vật chất, scope D/F/D+, tái tạo có giới hạn và truy vấn nhiều phần; focused10/regression06 qua sau review nguồn.
- [x] Chặng 6: API/SSE, persisted history, source readback, frontend build/test, browser và báo cáo cuối đã kiểm; xuất ảnh qua CUA vẫn bị EPERM.

Đánh dấu hoàn tất ở đây chỉ áp dụng cho phạm vi triển khai pilot local. Bộ đánh
giá độc lập lớn, chất lượng OCR/hiệu lực nguồn, tải đồng thời và rollout enterprise
vẫn là các bước tiếp theo bên dưới.

## Phần đã thực hiện

| Phần | Thay đổi cụ thể | Ràng buộc được giữ |
|---|---|---|
| Hiểu câu hỏi | Câu giới thiệu/làm rõ do server dựng; alias tiếng Việt; câu nối tiếp dựa vào mục tiêu user trước đó; chuyển chủ đề không tự kéo chủ đề cũ | Lịch sử assistant không là chứng cứ hay quyền truy cập; yêu cầu dữ liệu cá nhân vẫn cần identity và nguồn được cấp quyền |
| Ingestion | Chunk theo đoạn/câu, overlap bằng văn bản nguồn, giữ offset; child nhỏ để tìm, parent đầy đủ để trả lời | Không sửa chữ OCR, nội dung nguồn, hash hoặc locator; dòng bảng quá dài vẫn cần parser chuyên dụng hơn |
| Contextual index | Title, section và câu hỏi alias đã gắn nguồn chỉ bổ sung vào văn bản tìm kiếm | FAQ answer/metadata không trở thành bằng chứng sinh câu trả lời |
| Retrieval | BM25 + BGE-M3 1024 chiều → RRF → BGE-reranker-v2-m3; phân tách truy vấn có giới hạn | Lọc authorization, campus, trạng thái CURRENT và ngày hiệu lực trước xếp hạng; áp dụng lại mỗi subquery; không dùng giả vector/rerank khi lỗi |
| Context | Ghép child về parent, tối đa bốn parent, giữ bằng chứng đầy đủ và source readback | Ngân sách context, giới hạn ứng viên, queue/deadline 12 giây và cache query vector có giới hạn; không cache câu trả lời dùng chung actor |
| Grounding | Kiểm số, đơn vị, so sánh, phủ định và điều kiện trong ngoặc; phân biệt D/F/D+ và đọc comparator OCR thiếu khoảng trắng; semantic verifier yêu cầu verdict đầy đủ và đúng câu hỏi | Không sửa nguồn/hash; giữ EvidenceGate và OutputGuard, một lần tái tạo trong tổng thời hạn generation 5 giây/tổng output 1000 token. Tái tạo giữ phạm vi single_fact; chỉ thêm phát biểu kỷ luật nếu liên quan |
| API/UI | Phân biệt làm rõ, thiếu chứng cứ và lỗi generation; giữ SSE, lịch sử hội thoại, mở source qua API và kiểm hash | Nhánh Advanced có namespace riêng, không reset dữ liệu; không dừng dịch vụ cũ ở 8000/3000 |

Đây là truy hồi theo truy vấn con xác định trước, tối đa ba phần. Vòng agent tự tạo
truy vấn mới sau khi tự chấm bằng chứng, GraphRAG, graph entity/relationship,
fine-tuning và bộ parser đa phương thức đầy đủ chưa được triển khai. Chất lượng
không được suy ra chỉ từ số lượng kỹ thuật được gắn vào pipeline.

## Kết quả chốt trong phạm vi pilot

Report04 dưới đây là bằng chứng lịch sử. Sau khi đọc lại toàn văn nguồn, gold đã
được siết về parent chứa quy định trực tiếp: học bổng 100; chuyển ngành 124; hoãn
thi 118; phúc khảo 54; học cải thiện/điểm D 118 và 99; tín chỉ 112; nghỉ học tạm
thời 123; hai chương trình 126 và 102. Câu hỏi và answer terms được giữ nguyên.
Retrieval-comparison05 đã chạy lại trên gold này. Sau lượt06 bị lỗi runtime và
điều chỉnh microbatch/ứng viên, retrieval-comparison08 là report dùng cho cấu
hình hiện tại. Report04/05 không được dùng thay cho phép đo08.
Dataset SHA-256 của report05/06/08:
`ae1ced0856c8a381522e27d1025cde2d26baf3f3ed9a93b952e813de262dc18e`.

| Kiểm chứng | Kết quả quan sát | Ý nghĩa và giới hạn |
|---|---|---|
| Coverage nguồn, report08 | Baseline top3 13/16; Advanced top1 15/16, top3 16/16, top4 16/16; không failure | Top1/top3/top4 được suy ra từ chunk IDs của selected_sources khớp expected_sources trong report08, không phải lần benchmark mới. So top3 cùng K; đây là question coverage trên bộ đã tuning, không phải Recall@10 hoặc answer correctness |
| Latency retrieval, report08 | p50 4.391 ms, p95 5.875 ms; min 1.172 ms, max 5.875 ms | Nearest-rank trên 16 lượt tuần tự CPU local sau microbatch một cặp/fusion sáu ứng viên; không là SLO hoặc kiểm tải đồng thời |
| Hội thoại live, dialogue03 | 10/10 qua class/terms/gold/hash/history và kiểm điều kiện bằng; p50 7.547 ms, p95 9.984 ms | Bộ mười câu đã dùng tìm lỗi qua các lượt 01/02 nên là regression, không held-out. Agent chính đã đọc mười đầu ra: năm I giữ quan hệ bằng số tối đa, năm 2030 từ chối rõ thiếu nguồn, đổi chủ đề/nhiều nguồn đúng phạm vi. Đo trước guard/prompt cuối; chưa chạy lại cả benchmark sau sửa điểm D, không chứng minh correctness phổ quát |
| Source và lịch sử, dialogue03 | 9/9 source readback khớp canonical/hash; 10/10 persisted final bằng SSE final | Giữ citation/source thật và hội thoại có thể tải lại; source hash đơn thuần chưa chứng minh semantic support |
| Focused10 — điểm D và giới thiệu sau bản sửa cuối | 2/2 qua: điểm D grounded 6.500 ms, một citation/hash hợp lệ; giới thiệu làm rõ 563 ms | Đầu ra: “Điểm chữ D (từ 4,0 đến 4,9) thuộc loại đạt có phân mức, áp dụng cho các học phần được tính vào điểm trung bình học tập.” Nguồn Điều 9, Quyết định 1486 ngày 06/11/2023. Review range/source đúng; một fact, không thêm lựa chọn học đổi thiếu điều kiện |
| Proof read-only sau focused10 | Source điểm D 1/1 khớp chính xác corpus canonical/hash; cả hai persisted final bằng SSE final; provider_calls 0 | Kiểm bổ sung qua HTTP đọc source và history cuối, không phát sinh generation hay thay nguồn |
| Nghỉ học tạm thời, focused08 | Grounded 12.266 ms; hash 1/1; giữ đầy đủ các trường hợp và điều kiện cho lý do cá nhân | Đã review nguồn đầy đủ, gồm tối thiểu một học kỳ và không thuộc diện xem xét buộc thôi học/kỷ luật. Ca điểm D của cùng report08 vẫn thất bại và được giữ trong bảng lịch sử |
| Regression và UI | 274 Python test qua, không failure/error/skipped, 15,411 giây trong regression06; 68 frontend test qua; frontend3 build exit 0 | Suite cuối bao phủ factual support/OCR scope/regen. Lint các file cuối material_support, generation_policy và hai test file liên quan qua; không tuyên bố toàn repo sạch: definitions có sáu lỗi I001/TRY004 cũ, globals.css có EOF whitespace từ trước |
| Browser cuối | Hội thoại hai chương trình: bốn message, citation[1]/nguồn Điều17 đúng. Hội thoại điểm D từ focused10: hai message, mở citation[2]/nguồn Điều9 thấy D4,0–4,9, F dưới4,0 và đầy đủ điều kiện học đổi trong source; tab được đánh dấu deliverable | Xác minh trực tiếp giao diện/source drawer sau bản sửa cuối. Xuất ảnh qua CUA bị EPERM nên không có file ảnh được giao |

Bằng chứng lỗi trước khi sửa vẫn được giữ nguyên:

| Lượt | Kết quả đã quan sát | Sửa và giới hạn diễn giải |
|---|---|---|
| Retrieval05/06 | Lượt05 coverage16/16, p50/p95 6.375/7.500 ms; median6.492 ms. Lượt06 0/16 với ba timeout và 13 contract error | Runtime dưới tải làm lộ lỗi; điều chỉnh microbatch/ứng viên rồi chạy08. Không loại failure khỏi kết quả lịch sử |
| Chat02/04/05/06/07 | Chat02 15/17, 18/18 hash; p50/p95 8.281/10.843 ms. Lượt04 điểm D qua nhưng nghỉ tạm thời INTERNAL_ERROR; lượt05 2/3, điểm D timeout; điểm D lượt06 vẫn timeout; focused07 automatic3/3 nhưng review phát hiện thiếu điều kiện | OutputPolicyReject điều kiện kỷ luật, modal polarity, latency và omission học đổi được xử lý; focused10 mới là kiểm điểm D sau bản sửa cuối. Refusal do lỗi chưa bao giờ tính là answer pass |
| Focused07/08/09 | Lượt07 automatic 3/3 nhưng claim học đổi bỏ điều kiện tương đương/thay thế môn bắt buộc. Lượt08 điểm D timeout 15.219 ms sau tái tạo do MISSING_MATERIAL_CONDITION; lượt09 từ chối 6.375 ms sau lỗi comparator OCR và điều kiện | Nguồn Điều 9 ghi dải D với OCR thiếu khoảng trắng, parser trước chỉ đọc ngưỡng F nên reject sai câu D. Sửa parser/comparator và scope hàng điểm D khác D+; giữ nguyên source/hash, đơn giản phạm vi trả lời, kiểm lại bằng focused10 |
| Dialogue01/02 | Lượt01 tự động10/10 nhưng manual review thấy sai quan hệ bằng và năm2030 trả lỗi dịch vụ chung. Lượt02 4/10 với sáu DEPENDENCY_UNAVAILABLE; thiếu nguồn và hai chương trình đã đúng | Siết check equality/no-source, giữ bound prompt/message, rồi sửa runtime. Dialogue03 đạt tiêu chí đã siết; bộ này không còn là held-out |

Báo cáo nguồn:

- [Retrieval comparison08 — cấu hình hiện tại](<C:/Users/Duong Vinh/Vinh/infra/local/rag-advanced-20261013/retrieval-comparison-08.json>)
- [Hội thoại regression03 — kiểm đã siết và đầu ra cuối](<C:/Users/Duong Vinh/Vinh/infra/local/rag-advanced-20261013/dialogue-validation-03.json>)
- [Focused chat10 — điểm D và giới thiệu cuối](<C:/Users/Duong Vinh/Vinh/infra/local/rag-advanced-20261013/chat-focused-10.json>)
- [Proof source/history focused10 — read-only](<C:/Users/Duong Vinh/Vinh/infra/local/rag-advanced-20261013/chat-focused-10-source-review.json>)
- [Regression tích hợp06 — 274 test cuối](<C:/Users/Duong Vinh/Vinh/infra/local/rag-advanced-20261013/regression-final-06.xml>)
- [Focused chat08 — nghỉ tạm thời đúng, điểm D timeout](<C:/Users/Duong Vinh/Vinh/infra/local/rag-advanced-20261013/chat-focused-08.json>)
- [Focused chat09 — giữ bằng chứng reject comparator/điều kiện](<C:/Users/Duong Vinh/Vinh/infra/local/rag-advanced-20261013/chat-focused-09.json>)
- [Focused chat07 — automatic pass và đầu ra có omission khi review](<C:/Users/Duong Vinh/Vinh/infra/local/rag-advanced-20261013/chat-focused-07.json>)
- [Retrieval comparison06 — giữ bằng chứng lỗi runtime](<C:/Users/Duong Vinh/Vinh/infra/local/rag-advanced-20261013/retrieval-comparison-06.json>)
- [Retrieval comparison05 — lịch sử gold mới trước sửa runtime](<C:/Users/Duong Vinh/Vinh/infra/local/rag-advanced-20261013/retrieval-comparison-05.json>)
- [Retrieval comparison04 — lịch sử gold cũ](<C:/Users/Duong Vinh/Vinh/infra/local/rag-advanced-20261013/retrieval-comparison-04.json>)
- [Live chat02](<C:/Users/Duong Vinh/Vinh/infra/local/rag-advanced-20261013/chat-validation-02.json>)
- [Focused chat04](<C:/Users/Duong Vinh/Vinh/infra/local/rag-advanced-20261013/chat-focused-04.json>)
- [Focused chat05 — sau bản sửa](<C:/Users/Duong Vinh/Vinh/infra/local/rag-advanced-20261013/chat-focused-05.json>)
- [Điểm D lần06](<C:/Users/Duong Vinh/Vinh/infra/local/rag-advanced-20261013/chat-grade-06.json>)
- [Hội thoại độc lập01 — kiểm tự động và đầu ra để review](<C:/Users/Duong Vinh/Vinh/infra/local/rag-advanced-20261013/dialogue-validation-01.json>)
- [Hội thoại độc lập02 — kết quả domain mới và lỗi runtime](<C:/Users/Duong Vinh/Vinh/infra/local/rag-advanced-20261013/dialogue-validation-02.json>)
- [Regression tích hợp02](<C:/Users/Duong Vinh/Vinh/infra/local/rag-advanced-20261013/regression-final-02.xml>)
- [Regression tích hợp03](<C:/Users/Duong Vinh/Vinh/infra/local/rag-advanced-20261013/regression-final-03.xml>)
- [Frontend3 build](<C:/Users/Duong Vinh/Vinh/infra/local/rag-advanced-20261013/frontend3-build.json>)
- [Bộ 16 câu hỏi](<C:/Users/Duong Vinh/Vinh/evals/datasets/advanced-public-rag-20261013.json>)

## Runtime và tái lập

Corpus public giữ nguyên 131 parent, index mới gồm 261 child. Namespace ứng dụng:
`C:\Users\Duong Vinh\Vinh\infra\local\rag-advanced-20261013`. Namespace model
hiện tại: `infra/local/rag-advanced-models-20261013-05`, kế thừa namespace04 và các reservation
cũ kể cả lượt không thành công. Lịch sử và idempotency dùng database mới của
namespace Advanced; paid ledger tiếp tục dùng lịch sử đã được cấp ngân sách.

Index fingerprint hiện tại:
`903531eb92b01e4ebb71ef6413b40fcba7b626e3480ddc6e3e580cfe634249fb`.
Manifest gắn model, revision, child IDs và nội dung tìm kiếm; thay corpus/chunking
phải build manifest mới, không ghi đè index cũ.

- Embedding: `BAAI/bge-m3`, revision `5617a9f61b028005a4858fdac845db406aefb181`, 1024 chiều; model data SHA-256 `1eebfb28493f67bba03ce0ef64bfdc7fc5a3bd9d7493f818bb1d78cd798416b4`.
- Reranker: `BAAI/bge-reranker-v2-m3`, revision `953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e`; weights SHA-256 `d9e3e081faff1eefb84019509b2f5558fd74c1a05a2c7db22f74174fcedb5286`.
- Model bind loopback `18081`/`18082`, frontend `3001`, API/UI proxy `8001`.
- Runtime ONNX giữ kiểm checksum, cấm ghi vào model, cấm outbound network/DNS; 4 CPU, 5 GiB, mỗi native inference tối đa 3 giây, token envelope 900, không truncate. Cap kỹ thuật tích lũy: 6.000 HTTP, 2.000 native inference, 750.000 token.
- Runtime hiện chạy một cặp mỗi native microbatch và rerank tối đa sáu fusion candidate. Microbatch hai cặp trước đó đo 1.900–2.654 ms, quá sát deadline native 3 giây và làm deadline TEI 10 giây dễ lỗi khi có tải; bản mới giữ nguyên cap, không thay vector hay dùng fallback giả. Chỉ dừng model04 do task sở hữu, kế thừa vào namespace05; namespace cũ được giữ. Snapshot cuối: HTTP 1.690/6.000, inference 1.422/2.000, token 325.683/750.000.
- Generation/verification giữ tổng cap 3 USD và 8.500 calls, gồm reservation chưa settle. Snapshot sau focused10: charged bảo thủ `1.6790964` USD, còn `1.3209036` USD, 8.362/8.500 calls (còn 138 calls). Số này thay đổi khi dùng tiếp; không phải hóa đơn thực tế.

Helper [launch_advanced_rag.py](<C:/Users/Duong Vinh/Vinh/scripts/launch_advanced_rag.py>)
chỉ kiểm tra và in ba lệnh runtime; không tự start/stop, không tạo/ghi đè/xóa file.
Nó xác nhận artifact, đọc metadata cap, chọn model predecessor có counter đã
ghi cao nhất, và in một namespace model mới. Nó không đọc credentials hay gọi
gateway. Kiểm tra port chỉ quan sát network namespace của tiến trình: chạy trong
cùng môi trường với dịch vụ; Codex sandbox có thể không thấy loopback bên ngoài.

```powershell
& 'C:\Users\Duong Vinh\Vinh\infra\local\rag-fixture\.venv\Scripts\python.exe' -B 'C:\Users\Duong Vinh\Vinh\scripts\launch_advanced_rag.py'
```

Ba lệnh nó in lần lượt chạy model, frontend đã build `frontend3` và API `--port
8001` bằng runtime Python phù hợp. Không chạy thêm API khi chưa xác định quyền sở
hữu writer của paid ledger; port còn trống không đủ chứng minh ledger an toàn.
Không tự dừng tiến trình đang chiếm port. API 3.12 dùng trusted runtime hiện có
vì host application control chặn SQLite DLL của môi trường Python 3.13; không
thay policy của máy để chạy thử.

Khi runtime sẵn sàng, URL kiểm tra là `http://localhost:8001/chat`.

[Hội thoại điểm D đã kiểm browser](http://localhost:8001/chat?conversation_id=01a133f2-e70a-7bb9-a77b-431995fc9f0b)
được tải lại từ history cuối; citation[2] mở được toàn văn Điều9. Không cần gửi
câu hỏi mới để xem evidence này.

Tái lập so sánh retrieval không gọi generation:

```powershell
& 'C:\Users\Duong Vinh\Vinh\infra\local\rag-fixture\.venv\Scripts\python.exe' -B 'C:\Users\Duong Vinh\Vinh\scripts\evaluate_advanced_rag.py' retrieval --output 'C:\Users\Duong Vinh\Vinh\infra\local\rag-advanced-20261013\retrieval-user-check01.json'
```

Chọn tên output mới để giữ toàn bộ report trước; runner từ chối ghi nếu file đã
tồn tại. Kiểm hội thoại live sau thay đổi, tính vào cap hiện tại:

```powershell
& 'C:\Users\Duong Vinh\Vinh\infra\local\rag-fixture\.venv\Scripts\python.exe' -B 'C:\Users\Duong Vinh\Vinh\scripts\evaluate_advanced_dialogue.py' --output 'C:\Users\Duong Vinh\Vinh\infra\local\rag-advanced-20261013\dialogue-user-check01.json'
```

Không chạy lại toàn bộ paid suite khi chỉ cần kiểm phần bị ảnh hưởng. Cả hai
runner có `--only` để chọn một ca/nhóm; không tăng cap hay reset lịch sử để chạy lại.

Runner [evaluate_advanced_dialogue.py](<C:/Users/Duong Vinh/Vinh/scripts/evaluate_advanced_dialogue.py>)
gồm mười lượt ban đầu tách khỏi bộ tuning: học bổng → năm I; hai chương trình →
GPA dưới trung bình; thư viện → đổi ngành → hai chương trình; câu nhiều nguồn
thư viện và hai chương trình; lịch Tết 2030 không có nguồn; câu thiếu tham chiếu.
Runner so SSE final với persisted history, kiểm source hash và parent mục tiêu.
Lượt dialogue01 đạt 10/10 tiêu chí tự động, nhưng manual review tìm thấy hai hạn
chế vật chất nêu trong bảng; dialogue02 làm lộ lỗi runtime. Lượt dialogue03 đã
qua 10/10 tiêu chí siết và review đầu ra, nhưng bộ này giờ là regression sau sửa,
không còn held-out. Keyword/parent gold và mười câu review chưa thay thế bộ đánh
giá domain rộng hơn. Toàn bộ report trước được giữ để đối chiếu.

## Giới hạn và bước tiếp theo

Các sửa và kiểm chứng trong task pilot đã hoàn tất bằng regression06/focused10,
cùng bằng chứng retrieval08/dialogue03 trước bản sửa guard/prompt cuối. Những
việc bên dưới là bước đánh giá và rollout tiếp theo; không là approval gate cho
code hiện tại hoặc bằng chứng mặc định rằng chất lượng production đã đạt.

1. Dùng bộ câu hỏi mới chưa tham gia tuning/sửa lỗi, review từng claim/điều kiện/ngoại lệ từ nguồn; đo correctness/completeness, từ chối đúng/quá mức và citation precision độc lập. Mục tiêu Recall@10/quality ở trên chưa được phép đo hiện tại chứng minh.
2. Review nguồn OCR và hiệu lực phát hành; đối chiếu các bảng/điều khoản dài, thêm parser/OCR tốt hơn và quy trình cập nhật phiên bản. Nguồn local đang được giữ nguyên, không sửa để ép test pass.
3. Đo tải đồng thời, throughput, p95/p99, queue/cost và tình huống hết cap; những lần tuần tự cuối không phủ định lỗi đã gặp dưới tải. Tối ưu runtime theo số đo và giữ cơ chế từ chối/lỗi minh bạch.
4. Với rollout enterprise: chuyển index/lịch sử từ in-memory/SQLite sang backend bền vững, tăng quản trị tenant/ACL, source lifecycle, monitoring và quy trình vận hành; giữ provenance và các ràng buộc ứng dụng.
5. Browser cuối đã xác minh tải lại hội thoại và mở nguồn Điều17 và Điều9 sau bản sửa cuối; xuất ảnh qua CUA bị EPERM nên chưa có file ảnh để liên kết. Điều này giới hạn artifact giao diện, không thay kết quả API/source/history đã ghi. Giữ một writer của ledger trước khi mở thêm runtime.

Semantic verifier dùng model và vẫn có thể chấm sai. Kiểm deterministic giảm một
số lỗi vật chất nhưng không bao phủ mọi suy luận hoặc phép tính. Nguồn OCR hiện
có còn lỗi nhận dạng; status CURRENT của snapshot local cần xác minh theo nguồn
phát hành trước khi xem như chính sách đang áp dụng thực tế.
