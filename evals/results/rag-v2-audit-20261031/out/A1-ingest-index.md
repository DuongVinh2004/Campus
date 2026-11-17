# A1 — Nạp tài liệu, dựng chỉ mục và vòng đời chỉ mục

## Tóm tắt

- Chưa đủ cơ sở kết luận v2 phục vụ ổn định khi thêm hoặc thay thế tài liệu.
- Xác nhận 8 phát hiện, trong đó 2 `BLOCKER`: snapshot không đồng bộ với phát hành và nhánh dữ kiện bỏ điều kiện áp dụng.
- Kho ngoại tuyến: 2.019 chunk, 114 tài liệu, 9.071 unit; độ phủ ký tự hiện tại đạt 100%.
- Đã chạy 6 mẫu cấu trúc mới, probe dịch vụ/cache/bootstrap và phép đo bộ nhớ ×3–×5.
- 101 kiểm thử liên quan đạt; mọi probe dùng dữ liệu trong bộ nhớ hoặc HTTP giả lập, 0 lời gọi mô hình thật.
- Không sửa/tạo/xóa tệp, không gọi mạng, không khởi động runtime, không đọc bí mật hoặc nội dung holdout.
- Bằng chứng là mã nguồn đã đọc, số đo ngoại tuyến và đầu vào tổng hợp có kết quả kiểm bằng mã; trải nghiệm người dùng thật chưa đo.

## Phát hiện

### A1-01 [BLOCKER][confirmed] Release mới có thể được xác nhận phục vụ trong khi snapshot v2 chưa chứa tài liệu mới

- Vị trí: `services/api/src/campus247/application/knowledge/platform.py:534`; `services/api/src/campus247/infrastructure/knowledge/runtime.py:133`; `services/api/src/campus247/bootstrap/rag_v2.py:19`; `services/api/src/campus247/infrastructure/knowledge/runtime.py:238`.
- Bằng chứng: xác nhận phát hành cập nhật pointer/generation và phát `knowledge.release.changed` tại `platform.py:540`. Runtime chuẩn bị release bằng cách đếm `embedding_rag_v1`; bootstrap v2 chỉ đọc snapshot một lần. Closure ủy quyền tại `bootstrap/rag_v2.py:35` chỉ gửi các chunk ID có trong snapshot đó; SQL tiếp tục giới hạn `c.id=ANY(...)`.
- Bằng chứng hành vi: probe với snapshot không còn unit đủ điều kiện trả `refuse/no_source`, không gọi mô hình. Không có phép so `corpus_sha256`, release hoặc generation của **snapshot v2** với DB trong bootstrap hay đường lượt hỏi đã kiểm. Log unit bị loại chỉ thấy nguồn cũ mất quyền; không phát hiện chunk mới hoàn toàn vắng khỏi snapshot.
- Tác động tài liệu mới: tài liệu đã phát hành vẫn không vào tập truy hồi. Khi thay thế văn bản, bản cũ có thể bị loại đúng nhưng bản mới chưa được lập chỉ mục, tạo khoảng trống trả lời. Nếu còn nguồn gần giống, mô hình vẫn có thể nhận các nguồn đó; không phải mọi trường hợp đều trả `no_source`.
- Tác động ổn định/vận hành: trạng thái release/ack không chứng minh v2 đã sẵn sàng. Hệ thống không phân biệt “kho không có thông tin” với “chỉ mục chưa theo kịp kho”.
- Đề xuất thiết kế: ràng buộc snapshot v2 vào release, generation, policy generation và danh mục chunk/hash; chỉ xác nhận phục vụ khi artifact tương ứng đã được kiểm và nạp. Phát hiện lệch phải thành trạng thái vận hành rõ ràng.
- Kiểm chứng: test tích hợp phát hành D1 → thêm D2 → thay D1 → thu hồi → hết hiệu lực; xác nhận D2 xuất hiện và nguồn mất hiệu lực biến mất mà không sửa mã/khởi động tay. Dùng DB giả và embedding giả: 0 lời gọi thật; kiểm đầu–cuối thêm khoảng 6–10 câu hỏi.

### A1-02 [BLOCKER][confirmed] Nhánh dữ kiện vẫn bỏ điều kiện trước bảng hoặc trong tiêu đề cột

- Vị trí: `services/api/src/campus247/rag_v2/service.py:58`, `:73`, `:178`, `:185`; `services/api/src/campus247/rag_v2/facts/extract.py:53`.
- Bằng chứng: **sửa ở §9–§10 chưa đủ vì** `_self_contained` kiểm phần ngoài quote trong body và tối đa 600 ký tự **sau** quote ở chunk cha; không kiểm điều kiện đứng trước bảng hoặc trong context tiêu đề. Nhánh này tạo Statement từ `fact.quote` và đặt `semantic_required=False`.
- Đầu vào tái hiện: tiêu đề tài liệu `Bảng học phí theo Quyết định 999`; nội dung `Chỉ áp dụng cho học phần học lại.\nSTT | Chương trình đào tạo | Học phí (đồng/tín chỉ)\n1 | Alpha | 700.000`.
- Kết quả: hỏi `Học phí Alpha theo Quyết định 999 bao nhiêu?` nhận `answer`, Statement duy nhất `1 | Alpha | 700.000`, **0 lời gọi mô hình**. Chuyển điều kiện vào tiêu đề cột cũng cho cùng kết quả.
- Tác động tài liệu mới: chỉ cần tài liệu đặt điều kiện ở lời dẫn, header hoặc chú thích khác vị trí dự kiến, mức tiền được trả mà thiếu điều kiện quyết định đối tượng áp dụng.
- Tác động ổn định/vận hành: dữ kiện có quote nguyên văn vẫn có thể trở thành câu trả lời thiếu nghĩa; kiểm provenance hiện tại không chặn được.
- Đề xuất thiết kế: chỉ cho nhánh nhanh dùng fact có cấu trúc đầy đủ gồm đối tượng, đơn vị, thời gian và toàn bộ điều kiện được liên kết bằng span nguồn. Chưa chứng minh đủ các thành phần thì chuyển sang sinh và kiểm ngữ nghĩa.
- Kiểm chứng: test hoán vị điều kiện trước/sau bảng, trong header, chú thích xa và trang kế; không vị trí nào được trả mức tiền vô điều kiện. Test xác định: 0 lời gọi thật; sau sửa đo thêm khoảng 12–20 lượt mô hình.

### A1-03 [HIGH][confirmed] Tách bảng giữ chữ nhưng không bảo toàn lược đồ và quan hệ hàng/cột

- Vị trí: `services/api/src/campus247/rag_v2/ingest/units.py:83`, `:95`, `:112`, `:144`; `services/api/src/campus247/rag_v2/facts/extract.py:55`, `:61`, `:67`.
- Bằng chứng: header bảng chỉ được nhận từ các dấu hiệu `STT`, `mã học phần`, `chương trình đào tạo`; mỗi dòng có `|` trở thành `table_row`. Không có biểu diễn header nhiều tầng, ô gộp hoặc quan hệ kế thừa ô.
- Probe: bảng `Ngành | Đơn giá mỗi tín chỉ | Nhóm áp dụng` cho context của hàng dữ liệu chỉ là tiêu đề tài liệu. Bảng header hai tầng vẫn qua kiểm nhưng không trích được fee. Đổi thứ tự thành `STT | Học phí (đồng/tín chỉ) | Chương trình đào tạo` làm fact có `subject="700.000"` thay vì `Alpha`.
- Probe bổ sung: header `Học phí (đồng/ĐVHT)` với hàng `1 | Alpha | 700.000` tạo `basis="tín chỉ"`; mã suy basis từ hàng dữ liệu thay vì header.
- Tác động tài liệu mới: đổi tên/thứ tự cột, dùng header nhiều tầng hoặc ô gộp có thể làm mất liên kết giá trị–đối tượng–đơn vị, dù toàn bộ chữ vẫn còn. Chunk cha giúp đường sinh đọc lại bảng nhưng không khôi phục lược đồ có kiểm chứng cho nhánh fact.
- Tác động ổn định/vận hành: kết quả phụ thuộc hình thức trình bày; manifest 100% coverage không báo các suy giảm này.
- Đề xuất thiết kế: dùng cấu trúc bảng từ bộ phân tích layout với span hàng/cột/header và liên kết ô; ánh xạ fact theo vai trò ngữ nghĩa đã xác minh. Bảng chưa xác định được lược đồ phải giữ nguyên nguồn và không phát hành fact suy đoán.
- Kiểm chứng: bộ test biến hình đổi tên/thứ tự cột, header nhiều tầng, ô gộp, xuống dòng và đơn vị; so đối tượng–giá trị–đơn vị với gold có span. Kiểm xác định: 0 lời gọi thật.

### A1-04 [MEDIUM][confirmed] Cổng coverage vẫn chấp nhận mất nội dung có ý nghĩa

- Vị trí: `services/api/src/campus247/rag_v2/ingest/checks.py:46`, `:53`, `:57`; `scripts/rag_v2_build_index.py:122`.
- Bằng chứng: ngưỡng theo từng chunk là **98% ký tự chữ/số**; dấu câu và ký hiệu không được tính. Mỗi body còn đánh dấu tất cả lần xuất hiện giống nhau, không chứng minh từng vị trí nguồn đã được biểu diễn.
- Probe: nguồn `Nội dung ` + 500 ký tự `x` + ` KHÔNG`; bỏ phần cuối ` KHÔNG` khỏi unit. `check_units` trả `[]`, coverage `507/512 = 99,0234%`.
- Tác động tài liệu mới: một ngoại lệ, từ phủ định hoặc giá trị ngắn có thể nằm trong phần mất được cho phép. Cổng cũng không đánh giá chất lượng OCR, quan hệ bảng hoặc nội dung đã mất trước lúc xuất corpus.
- Tác động ổn định/vận hành: dựng có mất một phần vẫn được chấp nhận nếu chưa vượt ngưỡng; “coverage đạt” dễ bị hiểu thành bảo toàn nghĩa.
- Đề xuất thiết kế: đối chiếu khoảng ký tự nguồn tường minh cho từng unit; yêu cầu phủ đủ nội dung nguồn sau chuẩn hóa được định nghĩa rõ. Tách cổng bảo toàn ký tự khỏi cổng chất lượng OCR/layout và tính đầy đủ của fact.
- Kiểm chứng: cố ý bỏ phủ định, số tiền, đơn vị, chú thích và một lần xuất hiện lặp; mỗi trường hợp phải bị phát hiện hoặc có ngoại lệ chuẩn hóa được khai báo. 0 lời gọi thật.

### A1-05 [HIGH][confirmed] Embed-cache không ràng buộc revision hoặc cấu hình nhúng

- Vị trí: `scripts/rag_v2_build_index.py:30`, `:73`, `:80`, `:99`.
- Bằng chứng: khóa cache chỉ là SHA-256 của `unit.text`; `/info` được kiểm tên model, loại và `auto_truncate`, nhưng không yêu cầu revision tin cậy. Metadata đầu ra lấy revision của server hiện tại kể cả khi vector lấy hoàn toàn từ cache cũ.
- Probe HTTP giả lập: cache chứa `[1,0]`; server công bố `NEW_REVISION` và sẽ trả `[0,1]`. Kết quả có **0 lần `/embed`**, vector `[1,0]`, nhưng metadata ghi `embedding_revision="NEW_REVISION"`.
- Kiểm cache thật chỉ đọc: 10.037 dòng, 8.269 khóa; các khóa hiện dùng đều có vector 1.024 chiều. Đây **không** phải bằng chứng revision đúng vì cache không lưu trường đó.
- Tác động tài liệu mới: khi revision thay đổi, tài liệu mới được nhúng bằng model mới còn tài liệu cũ dùng vector cache cũ; cùng chiều vẫn không bảo đảm cùng không gian vector.
- Tác động ổn định/vận hành: thay model có thể gây suy giảm truy hồi âm thầm; manifest mô tả sai nguồn gốc vector.
- Đề xuất thiết kế: khóa cache gồm model, revision/artifact, tokenizer, pooling, chuẩn hóa và hash đầu vào thực sự. Mỗi vector cần receipt có schema và dimension; cache khác cấu hình không được tái sử dụng.
- Kiểm chứng: cùng text nhưng đổi từng thành phần cấu hình phải cache miss; giữ cấu hình phải hit; phát hiện cache trộn revision. 0 lời gọi thật bằng MockTransport.

### A1-06 [HIGH][confirmed] Lỗi 503 có thể tạo chỉ mục “complete” từ embedding của tiền tố

- Vị trí: `scripts/rag_v2_build_index.py:44`, `:57`, `:83`; `services/api/src/campus247/rag_v2/adapters/index_store.py:86`.
- Bằng chứng: sau 8 lần 503 cho một text, builder tự rút ngắn text xuống 60%, tối thiểu 300 ký tự; kết quả vẫn gắn vào unit đầy đủ. Khi CLI bật cache, khóa vẫn là hash text đầy đủ.
- Probe HTTP giả lập, thay sleep bằng hàm trong bộ nhớ: unit dài 940 ký tự, server trả 503 nếu đầu vào dài hơn 300. Sau 25 yêu cầu giả lập, builder nhận vector từ **300 ký tự**, trả matrix hợp lệ mà metadata không ghi thiếu phần đuôi.
- Tác động tài liệu mới: nội dung quan trọng ở cuối unit không tham gia embedding; OCR hoặc token hóa bất lợi có thể kích hoạt đường này.
- Tác động ổn định/vận hành: 503 do lỗi tạm thời cũng bị suy diễn thành vượt token. Với lịch sleep hiện tại, ví dụ trên có thêm 300 giây chờ chủ động cho một unit; chất lượng sai tiếp tục được lưu trong cache.
- Đề xuất thiết kế: phân biệt lỗi quá token với lỗi dịch vụ bằng mã lỗi rõ ràng; chia theo token trước khi nhúng và giữ mapping span. Không đổi đầu vào âm thầm; thất bại phải giữ artifact ở trạng thái chưa đủ điều kiện kích hoạt.
- Kiểm chứng: giả lập quá token, 503 tạm thời và 503 kéo dài; yêu cầu hash receipt khớp chính xác đầu vào thực tế và phủ đủ nguồn. 0 lời gọi thật.

### A1-07 [HIGH][confirmed] Bootstrap chấp nhận snapshot pending hoặc khác model/chiều của query adapter

- Vị trí: `services/api/src/campus247/bootstrap/rag_v2.py:19`, `:31`; `services/api/src/campus247/rag_v2/adapters/memory_index.py:65`, `:96`; `services/api/src/campus247/rag_v2/retrieval/hybrid.py:118`.
- Bằng chứng: bootstrap không so trạng thái embedding/model/revision/dimension với adapter hiện hành. Probe thay `read_index` bằng snapshot trong bộ nhớ: cả snapshot `pending (1,0)` và snapshot `OTHER_MODEL/OLD (1,2)` đều được `load_rag_v2` chấp nhận.
- Probe truy hồi: matrix 2 chiều, query 3 chiều; kết quả vẫn giữ ứng viên lexical, trace `vector_failed=true`, `vector=0`. Lỗi tương thích bị xử lý giống sự cố vector có thể dự phòng.
- Tác động tài liệu mới: snapshot dựng chưa nhúng hoặc dựng bằng cấu hình khác có thể đi vào phục vụ; truy hồi ngữ nghĩa không hoạt động như dự kiến.
- Tác động ổn định/vận hành: ứng dụng khởi động thành công nhưng suy giảm chức năng. Đổi revision cùng chiều còn khó phát hiện hơn vì không gây lỗi shape.
- Đề xuất thiết kế: kiểm tương thích snapshot–query adapter trước khi cấp trạng thái ready; yêu cầu embedding complete, model/revision/artifact/dimension khớp. Phân biệt lỗi cấu hình với sự cố dịch vụ tạm thời.
- Kiểm chứng: ma trận khởi động cho pending, sai model, sai revision, sai dimension và snapshot đúng; bốn trường hợp đầu phải bị chặn rõ ràng. 0 lời gọi thật.

### A1-08 [MEDIUM][confirmed] Công cụ xuất corpus cố định đường dẫn và số lượng của một kho lịch sử

- Vị trí: `evals/runners/corpus_export.py:19`, `:20`, `:126`, `:175`.
- Bằng chứng: exporter không có tham số thư mục đích; từ chối khi corpus/manifest đã tồn tại. Sau khi xuất, trả exit code 2 nếu số lượng khác hằng `2515 chunk / 151 version / 123 document`.
- Probe chỉ đọc với corpus hiện có: `2019 / 114 / 114`, `matches_expected_counts=false`. Không chạy thao tác xuất ghi tệp.
- Tác động tài liệu mới: thêm tài liệu hợp lệ làm thay đổi số lượng nhưng vẫn bị đánh dấu lệch baseline; lần xuất kế tiếp không có đường CLI chuẩn để chọn snapshot mới.
- Tác động ổn định/vận hành: quy trình dựng lại trong runbook cần can thiệp ngoài giao diện công cụ; khó tự động hóa và phân biệt tăng trưởng hợp lệ với thiếu dữ liệu.
- Đề xuất thiết kế: xuất vào đích snapshot bất biến có tham số; đối chiếu số lượng/hash với inventory của chính giao dịch DB đó. Baseline lịch sử chỉ là số đo, không là điều kiện thành công chung.
- Kiểm chứng: xuất hai generation với tài liệu mới, thay thế và thu hồi; mỗi snapshot riêng được xác minh theo DB tương ứng, không sửa hằng số. Test filesystem giả: 0 lời gọi thật.

## Phần đã kiểm và thấy ổn

- **Đường đi đã lần theo:** worker tạo chunk/vector và manifest DB `READY` tại `services/worker/src/campus247_worker/knowledge.py:470`; review ràng buộc rendition/metadata và tách người duyệt tại `application/knowledge/platform.py:290`; build/seal release tại `:349`; preview/confirm xuất bản và tăng generation tại `:484`. Sau đó v2 còn cần xuất corpus → dựng snapshot có nhúng → cấu hình thư mục → nạp lại tiến trình. Trong đường mã đã kiểm, bước cuối chưa tự động nối với phát hành.
- **Thu hồi/hết hiệu lực/thay thế:** SQL giữ kiểm review, seal, quyền, hiệu lực và edition. Cache nguồn đổi theo release/generation/policy; `rag_v2_sources` lọc hết hạn mỗi lượt tại `infrastructure/knowledge/runtime.py:626`; nguồn được dẫn đọc lại tại `:647`; đổi pointer trong lượt bị chặn tại `:207`. Các bảo vệ này không bổ sung tài liệu mới vào snapshot.
- **Family không phải danh sách cho phép:** family chủ yếu đổi nhãn section thành `handbook_section` cho `so_tay`; không chặn family lạ. Kho hiện có 4.898 unit mang family `khac`, trong khi nhận diện course/table vẫn chạy. Điểm yếu chính là cấu trúc/regex, không phải yêu cầu thêm family vào mã.

Kết quả 6 mẫu trong bộ nhớ; tất cả qua `check_units`:

| Mẫu đầu vào | Unit nhận được | Điều quan sát |
|---|---:|---|
| Family lạ, header `Ngành / Đơn giá / Nhóm áp dụng` | 2 `table_row` | Header không được truyền vào context hàng |
| Header nhiều tầng, hàng mô phỏng ô gộp | 4 `table_row` | Không dựng quan hệ header/ô gộp; không có fee fact |
| Chương/Mục/Khoản, a), b), i., rồi Điều 2 | 1 `page`, 1 `article`, 3 `clause` | Phần trước Điều 2 bị gom; sau Điều 2 nhận khoản/điểm |
| Văn xuôi không xuống dòng, 3.690 ký tự | 4 `page` | Giữ nội dung, unit dài nhất 1.194 ký tự |
| OCR lỗi `Ðiều l`, `S TT`, `7OO.OOO` | 1 `page`, 1 `notice` | Giữ chữ lỗi, không nhận đúng cấu trúc |
| Header học phí dùng ĐVHT | 2 `table_row` | Có fee fact nhưng basis bị gán tín chỉ |

- **Bảo toàn hiện tại:** 2.019 chunk → 9.071 unit; cả sáu family có min coverage 100%, không có issue. Đảo thứ tự chunk cho kết quả unit bằng nhau; ID được sắp ổn định.
- **Facts không chỉ học phí:** hiện có 108 `contact`, 16 `deadline`, 13 `fee`; extractor còn hỗ trợ `prerequisite`, nhưng corpus hiện tại không sinh fact loại này. Service chọn loại tại `rag_v2/service.py:43`, dùng nhánh nhanh tại `:169`; còn lại đi qua truy hồi/sinh/kiểm ngữ nghĩa.
- **Toàn vẹn tệp:** `read_index` kiểm checksum ba tệp dữ liệu, số lượng, trạng thái matrix và provenance quote/value. NPY kiểm header so kích thước trước cấp phát. Build dừng khi `check_units` có issue; tệp thiếu do I/O không trở thành snapshot đọc được.
- **Manifest chưa ký:** giới hạn đã ghi ở REPORT §10 mục 5 vẫn tồn tại; checksum không xác thực người tạo. Không tính lại thành phát hiện mới. Kiểm nguồn DB mỗi lượt vẫn cần giữ.
- **Phép thử newdoc:** `rag_v2_newdoc.py:32` có bộ chia Markdown riêng; `:108` tạo AuthorizedIndex từ corpus sao chép rồi gọi service trực tiếp. Phép thử này không kiểm chứng đường review → release → DB → tự cập nhật snapshot; phù hợp giới hạn đã ghi ở REPORT §16.

**Chi phí dựng lại khi thêm một tài liệu**

- V2 chưa có cập nhật tăng dần ở cấp snapshot: vẫn tách/kiểm toàn corpus và ghi lại bộ artifact.
- Cache hiện phủ đủ 8.221 text duy nhất của 9.071 unit. Với cùng cấu hình và không có cache miss, phần cũ không cần gọi `/embed`; rủi ro receipt/revision nằm ở A1-05.
- Một batch có bất kỳ cache miss nào sẽ nhúng lại **toàn batch**, tối đa 20 text. Vì vậy thêm Δ unit có thể nhúng lại cả unit cũ xen cùng batch.
- Dựng lạnh hiện cần ít nhất 454 batch `/embed` và một `/info`, chưa tính retry/chia batch.
- Đã đo riêng: tách unit 3,61 giây; quét cache 227,5 MB mất 5,75 giây. Chưa đo thời gian dựng đầy đủ hoặc tốc độ server nhúng vì phiên này chỉ đọc, không gọi dịch vụ.

**Bộ nhớ và khởi động**

| Quy mô | Unit | Matrix float32 | Thời gian khởi tạo index | Working set tiến trình đo |
|---|---:|---:|---:|---:|
| Hiện tại | 9.071 | 35,4 MiB | Đọc/kiểm 0,53 s + khởi tạo 4,14 s | 185 MiB |
| ×3 | 27.213 | 106,3 MiB | 8,20 s, chưa tính đọc tệp | 455 MiB |
| ×5 | 45.355 | 177,2 MiB | 16,04 s, chưa tính đọc tệp | 682 MiB |

- ×3/×5 là bản nhân trong bộ nhớ với ID riêng, giữ phân bố văn bản hiện tại; input matrix và snapshot gốc vẫn còn trong tiến trình. Đây là phép đo phục vụ ước lượng, không phải dự báo RAM chính xác cho tài liệu đa dạng hơn.
- Với thành phần tương tự, ước thời gian đọc + dựng index khoảng 10–15 giây ở ×3, 19–25 giây ở ×5. Chưa gồm API, cache nguồn DB, mô hình và warm-up ủy quyền.
- BM25 tạo lại postings khi nạp; vector được sao chép/chuẩn hóa và truy vấn vẫn quét matrix. Kho nhiều từ vựng mới có thể tốn RAM hơn mẫu nhân.
- **Kiểm thử:** 101 passed trong 14,44 giây bằng `.venv/Scripts/python.exe -B -X utf8 -m pytest tests/rag_v2/ingest/test_units.py tests/rag_v2/facts/test_extract.py tests/rag_v2/retrieval/test_memory_index.py tests/rag_v2/test_service.py -q -s -p no:cacheprovider -p no:benchmark`. Lần chạy dùng capture mặc định không khởi động được vì cần tệp tạm; lần trên không dùng capture đó.

## Câu hỏi mở cần chủ dự án quyết định

- SLA từ lúc xác nhận phát hành đến lúc v2 phục vụ tài liệu là bao lâu? Đề xuất mặc định: chỉ báo “đã phục vụ” khi snapshot tương ứng đã sẵn sàng; trong thời gian chuẩn bị hiển thị trạng thái đang cập nhật.

## Thiết kế đề xuất cho vòng đời chỉ mục

1. Release candidate sinh inventory bất biến gồm chunk ID, version, hash nguồn và metadata phạm vi.
2. Worker nhận sự kiện đáng tin cậy, dựng snapshot theo inventory; xử lý idempotent và tiếp tục được sau lỗi.
3. Tách unit bằng span nguồn; bảng giữ header, hàng/cột và quan hệ ô gộp.
4. Cổng nạp kiểm đủ inventory, phủ nguồn, chất lượng OCR/layout và tính đầy đủ của fact.
5. Fact thiếu điều kiện/đơn vị hoặc lược đồ chắc chắn phải đi qua sinh và kiểm ngữ nghĩa.
6. Cache embedding dùng receipt ràng buộc model/revision/artifact/cấu hình/hash đầu vào thực tế.
7. Không rút ngắn nội dung âm thầm; lỗi nhúng giữ snapshot chưa sẵn sàng.
8. Manifest xác thực inventory, hash artifact, phiên bản bộ xử lý và model; đối chiếu độc lập với DB.
9. Trước kích hoạt, kiểm complete và tương thích query adapter; chạy smoke test xác định trên tài liệu mới.
10. Nạp snapshot ngoài đường yêu cầu rồi đổi con trỏ phục vụ nguyên tử; giữ snapshot cũ để phục hồi.
11. Ack và readiness phải ràng buộc đúng release/generation/snapshot v2 đang phục vụ.
12. Mỗi lượt giữ kiểm quyền, hiệu lực, edition và đọc lại nguồn trích dẫn; giám sát độ trễ DB↔index cùng chunk thiếu/thừa.
13. Dùng shard bất biến và cache hợp lệ để thêm tài liệu không cần nhúng/dựng lại toàn kho hoặc sửa mã.