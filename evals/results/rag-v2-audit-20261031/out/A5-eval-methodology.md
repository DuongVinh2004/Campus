# A5 — Phương pháp đo và bằng chứng khả năng tổng quát

## Tóm tắt

- Chưa đủ bằng chứng để kết luận “v2 ổn định với tài liệu mới”.
- Tái chấm ngoại tuyến holdout6 xác nhận A1–A8 đều trượt; A9 được đánh dấu `EXTERNAL`.
- Có lỗi phương pháp đo tái hiện được: A1 nhận câu sai ngữ cảnh, A2 nhận phát biểu ngoài nguồn, `newdoc score` tính lỗi hệ thống là từ chối đúng.
- Holdout6 không trùng chunk gold cũ nhưng 19/21 tài liệu nguồn đã xuất hiện; sau §19, bộ này đã được dùng để chẩn đoán.
- Khoảng tin cậy rộng và số lượt lặp không thay thế số chủ đề/tài liệu độc lập.
- Bằng chứng phiên này gồm đọc mã, thống kê cấu trúc, tái chấm kết quả lưu sẵn và probe tổng hợp chạy trong bộ nhớ; không gọi mạng, không ghi tệp.

## Phát hiện

Định nghĩa A1–A8 thực tế trong `evals/runners/rag_v2_eval.py:457–526`:

| Mã | Cách tính trong mã | Đối chiếu SPEC |
|---|---|---|
| A1 | Số lượt có đáp án chuẩn, đã trả `answer/partial`, thiếu ít nhất một `required_fact` hoặc khớp `forbidden_fact`; chia **mọi lượt có đáp án chuẩn**, kể cả từ chối/lỗi; ≤2% | Đúng mẫu số mô tả trong SPEC; khả năng nhận biết sai bị giới hạn bởi bộ dữ kiện và phép khớp từ |
| A2 | Số lượt `answer/partial` có `citation_count=0`; phải bằng 0 | Hẹp hơn “phát biểu không có nguồn” |
| A3 | Lượt có `expected=abstain/clarify` trả `refuse/clarify`, chia mọi lượt âm tính; ≥98% | Không kiểm lý do từ chối hoặc chất lượng câu hỏi làm rõ |
| A4 | Tỷ lệ `answer/partial` trên lượt có đáp án, theo biến thể | Ngưỡng đúng: form+không dấu 92%, keyword 85%, slang 75% |
| A5 | Trong mọi lượt được trả lời, có ít nhất một chunk gold hoặc chunk chứa nguyên văn một gold quote; ≥95% | Phù hợp quy tắc mở rộng được ghi ở REPORT §12; không phải độ chính xác của mọi trích dẫn |
| A6 | Tỷ lệ case có cùng `outcome_class` trong **ít nhất hai** bản ghi | SPEC yêu cầu ba lần; không đo nhất quán nội dung |
| A7 | Lượt `error`, có trường `error`, thiếu final event hoặc HTTP ≥400; <1% | Đo lỗi cuối cùng quan sát được; không phân biệt nguyên nhân |
| A8 | Trung vị tổng thời gian ≤6 s, nearest-rank p95 ≤12 s, **trung vị** byte đầu ≤2 s | Chưa có ngưỡng cho nội dung đầu tiên; byte đầu có thể chỉ là sự kiện điều khiển |

Tái chấm `runs/v2-holdout6.json` bằng `score_records`, đồng thời chạy nhánh CLI `score` với đầu ra giữ trong bộ nhớ:

| Chỉ số | Kết quả |
|---|---|
| Phủ mẫu | 160 case, 480 lượt, không thiếu case/lượt |
| A1 | 16/360 = **4,44%** |
| A2 | **0 câu không trích dẫn**, chưa phải 0 phát biểu ngoài nguồn |
| A3 | 117/120 = **97,5%** |
| A4 | **58,33% / 52,22% / 51,11%** |
| A5 | 183/201 = **91,04%** |
| A6 | 151/160 = **94,375%** |
| A7 | 5/480 = **1,0417%**, trượt ngưỡng nghiêm ngặt `<1%` |
| A8 | Trung vị **8,838 s**, p95 **13,469 s** |
| Byte/nội dung đầu | Trung vị **0,066 s / 8,262 s** |

### A5-01 [BLOCKER][confirmed] A1 có thể nhận câu sai điều kiện, đối tượng và ngữ cảnh

- Vị trí: `evals/runners/rag_v2_eval.py:58`, `:71`, `:466`; `evals/runners/rag_v2_cases.py:133`.
- Bằng chứng: probe `fact_matches` trả `True` cho cả bốn trường hợp: gold “được gia hạn 03 ngày” nhưng câu trả lời “không được gia hạn 03 ngày”; đổi đối tượng chính quy/liên thông; gold “07 ngày” nhưng câu trả lời gắn 07 ngày với bảo hành và 14 ngày với mượn; đủ dữ kiện nhưng thêm phát biểu sai ngoài chúng.
- Tác động tài liệu mới: điều kiện, ngoại lệ, quan hệ hàng–cột và phạm vi khóa/ngành mới không được bảo đảm chỉ bằng số và ≥75% từ nội dung. Giới hạn 1–4 dữ kiện không bảo đảm biểu diễn hết điều kiện quan trọng.
- Tác động ổn định/vận hành: A1 thấp có thể đi cùng câu trả lời sai. Ngược lại, probe diễn đạt đúng “Dịch vụ mượn hoàn toàn miễn phí” cho gold “không thu phí mượn”, hoặc “1 nghìn đồng” cho “1000 đồng”, đều trả `False`. Sửa ở §15 chưa đủ vì mới chuẩn hóa riêng `TC`, chưa xử lý tương đương nghĩa/đơn vị nói chung.
- Đề xuất thiết kế: gold biểu diễn chủ thể–quan hệ–giá trị–đơn vị–điều kiện–ngoại lệ; kiểm quan hệ xác định khi có thể, bổ sung bộ chấm ngữ nghĩa độc lập cho toàn bộ phát biểu và độ đủ ý.
- Kiểm chứng: mutation test đổi phủ định, chủ thể, hàng bảng, điều kiện, đơn vị và thêm mệnh đề sai: 0 lời gọi. Sau đó chấm mù bằng mô hình khác, khoảng một lời gọi/câu trả lời; bất đồng cần đối chiếu nguồn.

### A5-02 [BLOCKER][confirmed] A2 bằng 0 không chứng minh mọi phát biểu đều có nguồn

- Vị trí: `evals/runners/rag_v2_eval.py:473`, `:518`.
- Bằng chứng: đầu vào tổng hợp “Bảo hành 07 ngày; mượn 14 ngày. Mọi người được miễn học phí.”, gold chỉ “Mượn 07 ngày”, một citation gold: **A1 PASS, A2 PASS**. Mã A2 cũng tự ghi rõ `not claim-level verification`.
- Tác động tài liệu mới: câu trả lời ghép nhiều tài liệu có thể dẫn đúng một nguồn nhưng suy diễn thêm điều kiện, mức tiền hoặc quyền lợi không được nguồn hỗ trợ.
- Tác động ổn định/vận hành: các bảng REPORT gọi A2 là “không nguồn: 0” dễ được hiểu mạnh hơn bằng chứng thực tế.
- Đề xuất thiết kế: tách tên chỉ số hiện tại thành “câu trả lời thiếu trích dẫn”; A2 nghiệm thu phải kiểm từng phát biểu với nguồn được phép, đúng phiên bản/phạm vi, kể cả nội dung đã stream.
- Kiểm chứng: thêm phát biểu ngoài nguồn vào câu có citation phải làm A2 trượt; 0 lời gọi cho bộ chấm cấu trúc, khoảng một lời gọi/câu cho kiểm ngữ nghĩa độc lập.

### A5-03 [HIGH][confirmed] Cổng ba lượt và nguồn gốc phiên đo chưa ngăn được việc trộn bằng chứng

- Vị trí: `evals/runners/rag_v2_eval.py:319`, `:490`, `:544`, `:563`, `:591`.
- Bằng chứng: ba bản ghi cùng `repeat=1`, khác `source_run`, được chấm `holdout_three_repeats_complete=True` và A6=100%. Hai lượt giống nhau cũng cho A6 PASS. Metadata kết quả holdout6 chỉ có `cases_sha256`, `base_url`.
- Tác động tài liệu mới: có thể trộn lượt trước/sau nạp tài liệu, trước/sau đổi mã hoặc quyền nguồn mà vẫn tạo báo cáo “đủ ba lượt”.
- Tác động ổn định/vận hành: `compare_reports` chỉ bắt buộc cùng tên split; không bắt buộc cùng tập case, corpus, build, cấu hình hay nhà cung cấp.
- Đề xuất thiết kế: manifest bất biến cho campaign gồm mã/build, corpus/index/release, chính sách quyền, model/prompt/nhiệt độ và thiết kế lặp; chỉ nghiệm thu khi đủ ba lần thử riêng biệt trong cùng campaign.
- Kiểm chứng: probe thiếu lượt, lặp số repeat, trộn build/corpus và so hai tập case khác nhau phải bị từ chối; 0 lời gọi.

### A5-04 [HIGH][confirmed] Cỡ mẫu hiện tại không đủ kết luận đạt ngưỡng 2%/98%

- Vị trí: `evals/runners/rag_v2_eval.py:408`, `:517`; `evals/results/rag-judge-20261028/briefs/T20-report.md:2`.
- Bằng chứng: Wilson 95%, nếu tạm coi mọi lượt độc lập: A1 16/360 có khoảng **2,75–7,10%**; A3 117/120 có khoảng **92,91–99,15%**. Bootstrap 20.000 lần, seed `20261031`, lấy lại mẫu theo chủ đề, giữ nguyên bốn biến thể × ba lượt: A1 **1,39–8,06%** trên 30 chủ đề; A3 **92,5–100%** trên 10 chủ đề.
- Tác động tài liệu mới: nhiều lượt trên ít chủ đề không đo được biến thiên giữa tài liệu, cấu trúc và đơn vị ban hành mới. Bootstrap trên đây vẫn chưa gom tiếp theo tài liệu nên chưa giải quyết hết phụ thuộc.
- Tác động ổn định/vận hành: hai điểm 4,44% và 97,5% tự chúng đã trượt; tăng mẫu mà giữ nguyên tỷ lệ không biến chúng thành đạt.
- Đề xuất thiết kế: công bố khoảng tin cậy theo tài liệu/chủ đề; cố định trước cách lấy mẫu và quy tắc dừng. Với mẫu độc lập, 193 trường hợp và không lỗi cho Wilson 95% tương ứng A1 trên <2%, A3 dưới >98%; nếu quan sát khoảng 1% lỗi, 1.000 mẫu cho cận trên khoảng 1,83%. Đây không phải phép quy đổi trực tiếp sang lượt lặp tương quan.
- Kiểm chứng: bootstrap phân cấp và kiểm sức mạnh thống kê ngoại tuyến: 0 lời gọi. Bổ sung chủ đề/tài liệu độc lập đến khi khoảng tin cậy đạt, không chỉ bổ sung repeat.

### A5-05 [HIGH][confirmed] Giữ kín theo chunk chưa tạo bằng chứng độc lập về tài liệu mới

- Vị trí: `evals/results/rag-judge-20261028/briefs/T20-holdout6.md:7`; `briefs/T2-common.md:2`; `REPORT-v2.md:286`, `:326`.
- Bằng chứng: đếm cấu trúc xác nhận holdout6 có 35 chunk gold, không trùng gold cũ; danh sách loại trừ có 358 ID và không thiếu gold của các bộ trước. Tuy nhiên, **19/21 document_id** của holdout6 đã xuất hiện trong gold trước đó. REPORT §19 xác nhận holdout6 đã dùng để chẩn đoán/sửa.
- Tác động tài liệu mới: đổi đoạn trong cùng tài liệu vẫn giữ văn phong, thuật ngữ và cấu trúc đã quen. T2 chỉ cho dùng cùng corpus; T16 còn yêu cầu viết tài liệu mới đúng văn phong kho.
- Tác động ổn định/vận hành: bằng chứng ban đầu của §18 có thể xem là giữ kín theo câu hỏi/chunk; hiện không còn là bộ nghiệm thu độc lập cho mã sau §19. Chẩn đoán tổng hợp cũng truyền thông tin lỗi vào quá trình phát triển.
- Đề xuất thiết kế: phân tách theo tài liệu/phiên bản/chùm văn bản liên quan, không chỉ chunk; khóa bộ nghiệm thu và giới hạn số lần xem. Dùng người viết câu hỏi khác mô hình hoặc khác prompt độc lập; tách bộ hồi quy đã mở khỏi bộ nghiệm thu.
- Kiểm chứng: kiểm giao nhau document/version và nhật ký lần mở: 0 lời gọi. REPORT xác nhận cùng `gpt-6.1-sol` viết các bộ được nêu; mức thiên lệch tương quan cụ thể chưa được định lượng, cần phép đo chéo người viết.

### A5-06 [HIGH][confirmed] Phép thử newdoc chỉ chứng minh khả năng trên một đường nạp và một loại tài liệu

- Vị trí: `evals/runners/rag_v2_newdoc.py:32`, `:73`, `:104`, `:114`; `briefs/T16-newdoc.md:8`.
- Bằng chứng: tài liệu Markdown được tách bằng `chunks_of`, nối trực tiếp vào corpus rồi dựng index; gọi thẳng `RagV2Service.answer`, `reranker=None`, thời gian hiệu lực đặt `None`. Bỏ qua graph safety/routing và đường phát hành/ủy quyền thật. Dữ liệu gồm một văn bản giả lập, 11 điều, bảng 5 hàng.
- Tác động tài liệu mới: chưa phủ PDF/OCR, bảng lớn/nhiều trang, song ngữ, phạm vi khóa/ngành, tài liệu thay thế/mâu thuẫn, thu hồi quyền và hiệu lực theo thời gian.
- Tác động ổn định/vận hành: “0 dòng mã riêng” ở §16 chỉ có giá trị với đường thử này; chưa chứng minh nạp thật không làm hỏng nguồn cũ. Tái chấm hiện có: 17/18 đủ ý, một thiếu ý, 7/7 từ chối đúng; không thể gọi là đã đạt A1–A5.
- Đề xuất thiết kế: thử xuyên suốt intake → parse/OCR → phê duyệt/phát hành → index → API có quyền → safety/routing → trả lời; chạy song song bộ cũ trên snapshot trước/sau.
- Kiểm chứng: ít nhất 5 tài liệu cho mỗi nhóm trong bảy nhóm A5 yêu cầu; thêm cặp thay thế và truy vấn trước/sau hiệu lực. Mỗi tài liệu 20–30 câu ×3; khoảng 2.100–3.150 lượt trả lời v2 trước khi tính baseline và lời gọi phụ.

### A5-07 [HIGH][confirmed] Newdoc scorer tính lỗi là từ chối đúng và có thể nhận trích dẫn quá ngắn

- Vị trí: `evals/runners/rag_v2_newdoc.py:127`, `:133`, `:140`, `:145`.
- Bằng chứng: chạy `score` với kết quả trong bộ nhớ chỉ chứa `NEWDOC-019`, `kind=transient_error`: báo **`correctly_declined=1`, `errors=1`**. Citation được nhận khi một quote là chuỗi con của quote kia; chuỗi rỗng cũng thỏa `q in case["quote"]`.
- Tác động tài liệu mới: lỗi nhà cung cấp trên câu không đáp án được tính thành thành công; citation chỉ chứa một mảnh nhỏ có thể được tính là hỗ trợ đủ gold.
- Tác động ổn định/vận hành: không kiểm đủ tập kết quả, trùng case hoặc số repeat; số “đúng” có thể tăng do bản ghi lặp. A5 chỉ đếm trên câu đã đủ facts, bỏ qua câu trả lời thiếu ý.
- Đề xuất thiết kế: dùng chung schema và bộ chấm A1–A8; lỗi là lớp riêng; kiểm coverage/uniqueness; citation phải có nguồn định danh và hỗ trợ phát biểu, không chỉ giao chuỗi.
- Kiểm chứng: lỗi trên ca âm tính, kết quả thiếu/trùng, quote rỗng/một ký tự và câu thiếu ý vẫn có citation: 0 lời gọi.

### A5-08 [HIGH][confirmed] Probe “ngoại tuyến” chưa phải cổng không mạng và chưa đại diện đường runtime

- Vị trí: `evals/runners/rag_v2_context_probe.py:31`, `:73`; `rag_v2_retrieval_probe.py:29`, `:58`; `services/api/src/campus247/agent/nodes/rag_v2.py:151`.
- Bằng chứng: context probe gọi embedding HTTP `127.0.0.1:18081`; retrieval probe dùng embedding và reranker HTTP. Context probe dùng `MemoryIndex` trực tiếp, trong khi runtime dùng `AuthorizedIndex`. REPORT §19 đã quan sát runtime chỉ giữ 1.487/9.071 unit, khác probe.
- Tác động tài liệu mới: tài liệu có phạm vi/quyền/hiệu lực mới có thể xuất hiện trong probe nhưng bị loại ở runtime; điểm ngữ cảnh cao không chứng minh trả lời được.
- Tác động ổn định/vận hành: không thể chạy nguyên trạng trong phiên A0 cấm mạng; gọi là “0 lời gọi” phải phân biệt 0 lời gọi sinh trả phí với 0 inference/HTTP.
- Đề xuất thiết kế: dùng chung hàm cấp quyền, đóng gói và snapshot với runtime; tiêm embedding/rerank cache bất biến cho tầng không mạng. Tách tầng replay xác định và tầng inference cục bộ.
- Kiểm chứng: replay cùng truy vấn/quyền/snapshot phải cho cùng tập nguồn và context hash với runtime; 0 lời gọi khi có cache. Probe hiện tại không được chạy trong phiên này vì gọi mạng và ghi đầu ra.

### A5-09 [HIGH][confirmed] A6/A7 chưa tách nguyên nhân lỗi, còn chiến dịch safety đã chọn lại lượt sau lỗi

- Vị trí: `evals/runners/rag_v2_eval.py:416`, `:487`; `evals/results/rag-judge-20261028/runs/strip_errors.py:4`; `runs/run-suite-e.sh:12`.
- Bằng chứng: A6 chỉ so loại kết quả; ba câu sai giống nhau vẫn nhất quán. A7 gom lỗi mã, timeout, HTTP và thiếu final. Script suite-e bỏ bản ghi có `error` rồi chạy lại tối đa tám vòng.
- Tác động tài liệu mới: văn bản dài có thể tăng timeout hoặc làm phát sinh lỗi nhánh mã; cách đo hiện tại không xác định được nguyên nhân hoặc tính nhất quán nội dung.
- Tác động ổn định/vận hành: suite sau thử lại đo khả năng hoàn thành sau nhiều lần thử, không đo xác suất thành công lần đầu. Metadata chưa ghi nhiệt độ, model revision, tải và build để tái lập.
- Đề xuất thiết kế: giữ mọi attempt trong journal bất biến; báo first-attempt và after-retry riêng. Gắn trace từng pha và request ID nhà cung cấp; chạy replay gateway cố định để tách lỗi mã khỏi biến thiên provider.
- Kiểm chứng: cùng ca ×10 ở nhiệt độ 0 và cấu hình triển khai; concurrency 1/2/4/8; cold/warm riêng; soak 2–4 giờ với ≥1.000 lượt. Đo A6 loại kết quả và nội dung; A7 `<1%` trên mọi lượt đã định trước. Chi phí tùy số pha, phải đếm provider request thực tế.

### A5-10 [HIGH][confirmed] A9 chưa đo route thực và chưa chứng minh cách ly dữ liệu hay side effect

- Vị trí: `evals/runners/rag_v2_suite.py:148`, `:205`, `:217`; `evals/gates/regression-gates.yaml:19`.
- Bằng chứng: suite có 300 `notes.expected_route` nhưng **0 `expect.route_any`**. Khi response thiếu route, mã bỏ kiểm `expected_route`. Tái chấm suite-e: đủ 610 ca, **610 thiếu route**, routing vẫn báo 237/300; injection 100/100, tool_guard 60/60, canary 0.
- Tác động tài liệu mới: injection trong tài liệu đã nạp, nguồn bị thu hồi hoặc truy vấn chéo quyền chưa được chứng minh chỉ bằng canary trong câu hỏi và văn bản trả lời.
- Tác động ổn định/vận hành: safety/routing/handover đo chủ yếu nút dùng chung; multi-turn đo cả rewrite/context dùng chung và lõi v2; injection/output verification cũng cắt qua nhiều lớp. Không có trusted audit để kết luận không ghi trái phép, không ghi lặp hoặc không lộ dữ liệu người khác.
- Đề xuất thiết kế: giữ cổng toàn hệ thống, thêm phân rã theo node để quy trách nhiệm; trace route đáng tin cậy, fixture hai người dùng và audit side effect. 100/100 là ngưỡng hồi quy hữu ích nhưng chưa chứng minh tỷ lệ an toàn ≥98%; cỡ 25 benign chỉ cho phép 0/1/2 false-positive theo bước 4%. `passed` hiện yêu cầu mọi assertion đạt, nghiêm hơn FP≤8%, chưa ánh xạ rõ sang macro-F1/critical recall trong YAML.
- Kiểm chứng: route thiếu phải là chưa đo; side effect và quyền kiểm xác định 0 lời gọi. Chạy đủ 610 ca/670 lượt mỗi engine, cộng injection qua tài liệu và fixture quyền; hard-zero bằng 0, critical recall≥98%, high+critical≥95%, ordinary FP≤8%.

### A5-11 [HIGH][confirmed] Các công cụ “full/đạt” dùng tiêu chuẩn khác nhau và chưa tạo cổng chung

- Vị trí: `evals/runners/rag_v2_gate_compare.py:33`; `rag_v2_eval.py:641`; `rag_v2_cases.py:40`; `evals/datasets/rag-v2/cases.manifest.json:26`.
- Bằng chứng: probe có đủ required fact nhưng thêm forbidden fact: `gate_compare.summarize` báo **`full=1`**, bộ chấm chính báo **A1=100% lỗi**. Nhánh CLI `score` in FAIL nhưng không trả exit code thất bại theo tiêu chí. Bộ gốc chỉ có 120/760=**15,79%** ca không đáp án, thấp hơn SPEC≥20%; validator không kiểm tỷ lệ này.
- Tác động tài liệu mới: quyết định giữ/bỏ thay đổi có thể khác nhau tùy công cụ; bộ dữ liệu mới có thể thiếu nhóm khó nhưng vẫn hợp lệ về schema.
- Tác động ổn định/vận hành: pipeline không thể dùng sự thành công của lệnh `score` để suy ra đạt nghiệm thu. `forbidden_facts` **có được kiểm** trong scorer chính, nhưng cả holdout2–6 đều rỗng trường này ở mọi case.
- Đề xuất thiết kế: một thư viện chấm chuẩn dùng chung; tách lệnh “tính điểm” và lệnh “kiểm cổng” với exit code rõ ràng; kiểm phân bố, coverage, provenance và subgroup từ manifest.
- Kiểm chứng: cùng dữ liệu phải cho cùng nhãn qua mọi công cụ; bộ dưới minimum, thiếu subgroup, chứa forbidden fact hoặc trượt ngưỡng phải làm lệnh gate thất bại; 0 lời gọi.

## Phần đã kiểm và thấy ổn

- Đã đọc A0 trước A5; đọc các runner được giao, SPEC, REPORT, PLAN, brief T2/T16 và toàn bộ `newdoc/`; giữ việc kiểm holdout ở mức cấu trúc và tính điểm tự động.
- `newdoc/check.py`: exit 0, 25 ca, 2.402 từ, bảng 5 hàng, 0 lỗi kiểm dữ liệu; kết quả 17/18 và 7/7 tái lập được.
- Danh sách loại chunk gold của holdout2–6 bao phủ gold các bộ trước; không phát hiện trùng gold ID với bộ trước.
- Scorer chính kiểm `forbidden_facts`, ranh giới số, A7 `<1%`, trùng attempt trong cùng nguồn và coverage. Suite kiểm cả delta/lượt trước, không chỉ final cuối.
- Pytest ba tệp `tests/evals/test_rag_v2_{cases,eval,suite}.py` không khởi chạy được: capture cần tệp tạm, sandbox không có thư mục ghi được; không có kết quả test mới để tuyên bố.
- Không sửa/tạo/xóa tệp, không đọc bí mật, không khởi động runtime hoặc gọi dịch vụ. Tính hữu dụng với người dùng thật vẫn chưa đo.

## Câu hỏi mở cần chủ dự án quyết định

- Chọn tài liệu HUCE công khai chưa có trong kho để nghiệm thu, hoặc dùng tài liệu tổng hợp có kiểm; trường hợp chỉ dùng tổng hợp phải giới hạn kết luận tương ứng.
- Chốt kỳ vọng sản phẩm cho liên hệ, handover chưa có consumer và yêu cầu ghi; giữ nguyên bảo vệ trong khi đối chiếu gold với hành vi được phép.
- Chốt ngân sách và mức tin cậy để mở rộng mẫu; 120 câu có đáp án ×3 không đủ làm bằng chứng tổng quát.

## Giao thức nghiệm thu đề xuất

1. Khóa mã, model/prompt/nhiệt độ, corpus/index/release, quyền nguồn, bộ chấm và bộ câu hỏi; ghi hash trước khi mở kết quả.
2. Chuẩn bị ≥35 tài liệu mới: mỗi loại ≥5 gồm quy phạm nhiều điều, bảng lớn, thông báo ngắn, thay thế bản cũ, phạm vi khóa/ngành, OCR kém và song ngữ; nhóm thay thế có đủ bản cũ/mới.
3. Ưu tiên tài liệu HUCE công khai do chủ dự án cung cấp; tài liệu tổng hợp phải được kiểm nguồn/quan hệ xác định. Người viết câu hỏi dùng mô hình khác hoặc prompt độc lập, không xem lỗi hệ thống.
4. Tầng 0, mỗi thay đổi mã/mỗi lần nạp: test xác định, schema/gold/absence, quyền/phiên bản, provenance, replay context và mutation scorer; **0 provider call, 0 HTTP**.
5. Tầng 0 đạt khi không lỗi kiểm, hard-zero=0, replay ổn định, recall@10≥90%, exact-ID@5≥98%; không mất case cũ đã đạt và context đủ facts không giảm.
6. Tầng nhanh: khoảng **100 provider call**, gồm kiểm provider nhỏ và 20–30 lượt API phân tầng cũ/mới; dừng theo ngân sách request thực tế. Yêu cầu 0 sai nghiêm trọng/ngoài nguồn, 0 lỗi, 0 rò/ghi trái phép; đây là cổng sàng lọc.
7. Đo cuối ban đầu: 200 chủ đề answer +200 chủ đề âm tính cho tài liệu mới; bộ cũ cố định thêm 200+200; phân tầng bốn biến thể, mỗi câu ×3 cho cả v1/v2.
8. Mức đầu tương ứng 4.800 lượt trả lời hai engine, trước các mẫu bổ sung; ước 14.400–28.800 provider call nếu trung bình 3–6 call/lượt, phải hiệu chỉnh bằng telemetry tầng nhanh.
9. A1 cận trên CI95%≤2%; A2 không phát biểu ngoài nguồn; A3 cận dưới≥98%; A4≥92/85/75%; A5≥95%. Báo riêng mới/cũ, loại tài liệu và biến thể.
10. Bootstrap theo tài liệu/chủ đề, giữ biến thể/repeat trong nhóm; bổ sung mẫu theo quy tắc đã chốt đến khi CI đủ hẹp. Không coi repeat là mẫu độc lập; nếu không đủ bằng chứng thì chưa nghiệm thu.
11. Không suy giảm: so cặp cùng case/snapshot trước–sau; điểm A1–A9 không kém baseline, CI một phía cho chênh lệch phải loại mức suy giảm đã chốt; hard-zero và ca critical không cho phép suy giảm.
12. A9 đủ 610 ca/670 lượt mỗi engine, thêm fixture chéo quyền/side effect và injection qua tài liệu; 0 rò/ghi trái phép, critical recall≥98%, high+critical≥95%, FP≤8%, routing macro-F1≥90%.
13. A6≥95% trên đủ ba lượt; A7<1% tính mọi attempt; A8≤6/12/2 s. Đo cold/warm, concurrency 1/2/4/8 và soak 2–4 giờ; giữ nguyên lỗi, báo retry riêng.
14. Chi phí bổ sung A9 khoảng 4.020–8.040 provider call cho hai engine theo giả định 3–6 call/lượt; soak và chấm ngữ nghĩa độc lập tính riêng, không gộp thành “một call/case”.
15. Chỉ nói **“v2 ổn định với tài liệu mới trong phạm vi đã đo”** khi toàn bộ cổng đạt qua đường nạp/phát hành/API thật, không sửa mã theo tài liệu, ca cũ không suy giảm và đủ bằng chứng thống kê; mỗi đợt nạp mới tiếp tục chạy các cổng trên.