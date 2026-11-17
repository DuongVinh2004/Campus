# A2 — Hiểu câu hỏi và truy xuất: khả năng tổng quát sang tài liệu mới

## Tóm tắt

- Hoàn tất kiểm định chỉ đọc; không sửa/tạo tệp, gọi mạng, đọc bí mật hay khởi động runtime.
- Xác nhận 10 phát hiện về hiểu câu hỏi, phạm vi, nhánh neo mã, độ phủ, phiên bản, reranker và tính ổn định.
- Đã chạy 15 câu hỏi tự viết, probe trên 9.071 unit/114 tài liệu, mô phỏng tăng kho trong RAM và 165 test đạt.
- BM25 top-40 chứa gold chunk ở 428/449 câu dev; mô phỏng nhân ba kho còn 410/449.
- Chưa đo recall hybrid bằng embedding câu hỏi thật, reranker thật hoặc độ trễ runtime có cơ sở dữ liệu.
- Bằng chứng gồm đọc mã, probe xác định và đối chiếu gold chunk dev bằng mã; không đọc nội dung holdout, chưa đo khả dụng với người dùng thật.

## Phát hiện

### A2-01 [HIGH][confirmed] Luật từ khóa vẫn chặn câu hỏi về chủ đề mới trước khi xem nguồn

- Vị trí: [analyze.py:87](</C:/Users/Duong Vinh/Vinh/services/api/src/campus247/rag_v2/understanding/analyze.py:87>), [analyze.py:128](</C:/Users/Duong Vinh/Vinh/services/api/src/campus247/rag_v2/understanding/analyze.py:128>), [analyze.py:137](</C:/Users/Duong Vinh/Vinh/services/api/src/campus247/rag_v2/understanding/analyze.py:137>), [service.py:154](</C:/Users/Duong Vinh/Vinh/services/api/src/campus247/rag_v2/service.py:154>).
- Bằng chứng: probe 15 câu bên dưới cho 3 `oos`, 4 `clarify`. “Phòng máy có được dùng FPT AI để nghiên cứu không?” bị `oos`; thêm “HUCE” thì thành `condition`. “Mượn thiết bị?” bị `unclear` vì `muon` thuộc từ dừng, còn hai từ chủ thể. Service trả ngay khi có `clarify_prompt` hoặc `out_of_scope`.
- Tác động tài liệu mới: tài liệu phòng thí nghiệm thời tiết, nghiên cứu tỷ giá hoặc công cụ FPT không thể cứu câu hỏi bị chặn, dù chứa đáp án. Một mức phí xưởng có nhắc “học phí” bị buộc khai khóa/ngành trước khi kiểm nguồn.
- Tác động ổn định/vận hành: quyết định phụ thuộc cách diễn đạt và việc có thêm tên trường; mô hình quyết định ở §13 không được tiếp cận những câu này.
- Đề xuất thiết kế: dùng phạm vi sản phẩm và tập nguồn được cấp quyền để phân biệt đối tượng; cho câu ngắn có chủ thể thực hiện tìm kiếm trước; chỉ hỏi phạm vi khi nguồn thực sự có nhiều đáp án khác nhau.
- Kiểm chứng: ma trận câu hỏi tương đương, thêm/bớt tên trường, chủ đề mới và phí không thuộc học phí; kiểm xác định rằng nguồn hợp lệ được tiếp cận. Có thể kiểm cổng bằng fake, 0 lời gọi thật.

### A2-02 [MEDIUM][confirmed] Chuẩn hóa viết tắt thay nghĩa và lịch sử phụ thuộc bảng chủ đề

- Vị trí: [normalize.py:35](</C:/Users/Duong Vinh/Vinh/services/api/src/campus247/rag_v2/understanding/normalize.py:35>), [analyze.py:69](</C:/Users/Duong Vinh/Vinh/services/api/src/campus247/rag_v2/understanding/analyze.py:69>).
- Bằng chứng: probe cho `TC ISO 17025` → `tín chỉ iso 17025`; `nghiên cứu RL` → `nghiên cứu rèn luyện`; `phòng nghiên cứu DC` → `phòng nghiên cứu được`. Với lịch sử học phí CNTT K64, câu mới “Còn nghiên cứu khoa học cần nộp đề cương ở đâu?” bị ghép câu học phí cũ, mang theo `hoc_phi`, K64 và 7480201. Ngược lại, lịch sử mượn máy ảnh không có topic khiến “Còn K72?” mất chủ thể.
- Tác động tài liệu mới: từ viết tắt khoa học, tiêu chuẩn và đơn vị mới bị thay nghĩa; chủ đề ngoài bảng không được kế thừa hội thoại đúng cách.
- Tác động ổn định/vận hành: đường dự phòng khi rewrite thất bại có hành vi khác đường rewrite thành công; có thể kéo bộ lọc khóa/ngành cũ vào câu hỏi mới.
- Đề xuất thiết kế: giữ nguyên truy vấn gốc, mở rộng thành các phương án có ngữ cảnh; phân giải chuyển chủ đề theo thực thể/ý định thay vì topic cố định; ghi rõ xuất xứ của phạm vi kế thừa.
- Kiểm chứng: test viết tắt đa nghĩa và chuyển chủ đề hai chiều; giả lập rewrite thành công/thất bại, 0 lời gọi thật.

### A2-03 [HIGH][confirmed] Phạm vi câu hỏi chỉ giữ một khóa và một ngành, làm mất nhánh so sánh

- Vị trí: [analyze.py:51](</C:/Users/Duong Vinh/Vinh/services/api/src/campus247/rag_v2/understanding/analyze.py:51>), [hybrid.py:23](</C:/Users/Duong Vinh/Vinh/services/api/src/campus247/rag_v2/retrieval/hybrid.py:23>), [types.py:52](</C:/Users/Duong Vinh/Vinh/services/api/src/campus247/rag_v2/types.py:52>).
- Bằng chứng: “So sánh quy định mượn thiết bị K70 và K71” tạo `cohort=K70`; bộ lọc nhận unit K70 và loại unit K71. Câu so sánh CNTT và ATTT tạo `program=7480201`, loại unit 7480202. Ngành được chọn theo thứ tự `_PROGRAMS`, không phải một tập ngành được hỏi.
- Tác động tài liệu mới: các nguồn áp dụng riêng từng khóa/ngành không cùng đến được ngữ cảnh so sánh. Ngành cơ khí bằng tên không tạo phạm vi; mã `7520103` thì có.
- Tác động ổn định/vận hành: **sửa ở §19 chưa đủ vì** `any_requested=True` ở source snapshot chỉ mở cổng đầu; bộ lọc hybrid phía sau vẫn dùng trường đơn trị.
- Đề xuất thiết kế: biểu diễn câu hỏi thành các ý với tập phạm vi tương ứng; dùng chung biểu diễn này xuyên suốt cấp quyền, truy xuất và kiểm chứng.
- Kiểm chứng: test xuyên hai tầng với hai khóa, hai ngành, khoảng khóa, phạm vi phủ định và tên/mã tương đương; 0 lời gọi thật.

### A2-04 [HIGH][confirmed] Phạm vi mở và mã mới bị diễn giải khác nhau giữa các tầng

- Vị trí: [units.py:33](</C:/Users/Duong Vinh/Vinh/services/api/src/campus247/rag_v2/ingest/units.py:33>), [source_snapshot.py:95](</C:/Users/Duong Vinh/Vinh/services/api/src/campus247/application/knowledge/source_snapshot.py:95>), [types.py:14](</C:/Users/Duong Vinh/Vinh/services/api/src/campus247/rag_v2/types.py:14>).
- Bằng chứng: `extract_scope("Áp dụng từ K70")` chỉ tạo `{K70}`, nên hybrid loại câu K71. “Các khóa tuyển sinh từ 2024”, “Áp dụng từ khóa 70” và “Áp dụng K100” đều tạo phạm vi rỗng, được hybrid cho qua như áp dụng chung. Khoảng đóng K70–K72 được mở rộng đúng.
- Bằng chứng bổ sung: snapshot `COHORT_SNAPSHOT` không khai khóa loại câu K71; `INFORMATION_SNAPSHOT` không khai khóa cho qua. Câu K72XX vẫn được cho qua snapshot chỉ có chương trình 72YY, vì regex chương trình chỉ nhận `6\d` hoặc `70/71`. Câu K100 cũng không được nhận diện như khóa tại tầng này.
- Tác động tài liệu mới: nguồn “từ khóa…” có thể bị loại mất hoặc áp dụng quá rộng; mã chương trình K72 trở đi không được kiểm giống K70/K71.
- Tác động ổn định/vận hành: cùng sự thiếu metadata mang nghĩa “mọi đối tượng” ở `Scope`, nhưng “chưa xác định” ở một số snapshot. Hành vi phụ thuộc loại nguồn.
- Đề xuất thiết kế: thống nhất `ALL`, `UNKNOWN`, tập giá trị và khoảng mở/đóng; ánh xạ năm tuyển sinh sang khóa bằng danh mục có căn cứ; giữ nguồn chứng minh từng ràng buộc.
- Kiểm chứng: test hợp đồng chung cho ingest/snapshot/hybrid với khóa 2–3 chữ số, mã mới, phạm vi mở, thiếu metadata và năm tuyển sinh; 0 lời gọi thật.

### A2-05 [HIGH][confirmed] Runtime mất nhánh neo mã; ngưỡng 200 còn làm nhánh này biến mất khi kho lớn lên

- Vị trí: [runtime.py:46](</C:/Users/Duong Vinh/Vinh/services/api/src/campus247/rag_v2/adapters/runtime.py:46>), [hybrid.py:124](</C:/Users/Duong Vinh/Vinh/services/api/src/campus247/rag_v2/retrieval/hybrid.py:124>), [bm25.py:52](</C:/Users/Duong Vinh/Vinh/services/api/src/campus247/rag_v2/retrieval/bm25.py:52>), [ports.py:9](</C:/Users/Duong Vinh/Vinh/services/api/src/campus247/rag_v2/ports.py:9>).
- Bằng chứng: `MemoryIndex` có `anchored`; `AuthorizedIndex` chỉ chuyển tiếp lexical/vector, còn protocol không yêu cầu nhánh neo. Probe cùng ba unit, `lexical_k=vector_k=1`: index gốc trả `noise,target`; sau khi bọc chỉ trả `noise`.
- Bằng chứng bổ sung: 200 unit chứa K72LAB cho 40 kết quả neo; thêm unit thứ 201 thì nhánh neo trả 0. Ngưỡng đếm unit trước khi giao với `allowed`.
- Tác động tài liệu mới: mã môn, mã chương trình hoặc mã thiết bị mới mất lợi ích neo tại runtime; nguồn dài có mã lặp có thể vượt ngưỡng và làm tắt nhánh.
- Tác động ổn định/vận hành: probe dùng `MemoryIndex` có thể đánh giá tốt hơn runtime được cấp quyền; một unit thêm vào gây thay đổi rời rạc về thuật toán.
- Đề xuất thiết kế: đưa nhánh neo vào hợp đồng index và chuyển tiếp qua bộ lọc quyền; đánh giá độ phân biệt theo tài liệu/phạm vi được phép, không dùng ngưỡng unit cố định để tắt toàn bộ.
- Kiểm chứng: test tương đương `MemoryIndex`/`AuthorizedIndex` với cùng quyền; test biên 199/200/201 và mã lặp trong tài liệu dài; 0 lời gọi thật.

### A2-06 [HIGH][confirmed] Chưa có cơ chế tổng quát ngăn tài liệu dài chiếm hết ứng viên

- Vị trí: [memory_index.py:76](</C:/Users/Duong Vinh/Vinh/services/api/src/campus247/rag_v2/adapters/memory_index.py:76>), [hybrid.py:116](</C:/Users/Duong Vinh/Vinh/services/api/src/campus247/rag_v2/retrieval/hybrid.py:116>), [hybrid.py:138](</C:/Users/Duong Vinh/Vinh/services/api/src/campus247/rag_v2/retrieval/hybrid.py:138>), [service.py:202](</C:/Users/Duong Vinh/Vinh/services/api/src/campus247/rag_v2/service.py:202>).
- Bằng chứng: trên kho thật, truy vấn không dấu “quy dinh muon thiet bi” có một tài liệu giữ 24/40 vị trí BM25; “hoc phi 2026-2027” là 21/40; “ky tuc xa” là 21/40 và top-12 chỉ có một tài liệu.
- Bằng chứng tăng kho: sao ba lần toàn bộ unit trong RAM, giữ gold tương đương theo unit gốc, làm số câu dev chứa gold chunk trong BM25 top-40 giảm **428→410/449**, mất 18, không thêm câu đạt. Nhóm gold thuộc tài liệu ≤30 unit: **60→59/60**. Đây là thử sức chịu mật độ lặp, không phải dự báo cho mọi kho mới.
- Bằng chứng tài liệu dài mới: thêm một nguồn ngắn thì nó hạng 1; thêm 50 unit nhiễu lặp tiêu đề thì nguồn ngắn hạng 51, tài liệu dài giữ 40/40 vị trí.
- Tác động tài liệu mới: tài liệu ngắn chứa đáp án có thể bị loại trước fusion; đa dạng hóa sau đó không khôi phục được ứng viên đã mất.
- Tác động ổn định/vận hành: **sửa ở §16 chưa đủ vì** giữ trực tiếp RRF bảo toàn các khoản cùng tài liệu nhưng bỏ đa dạng khi reranker tắt. §18.2 đã thử và gỡ quota 10; mã hiện tại chưa có cơ chế thay thế tổng quát.
- Đề xuất thiết kế: truy xuất phân cấp tài liệu→đoạn, tách trọng số tiêu đề khỏi nội dung và điều chỉnh ngân sách theo ý hỏi; giữ các đoạn bổ trợ cùng tài liệu, đồng thời bảo vệ nguồn độc lập.
- Kiểm chứng: cổng recall gold chunk, đủ dữ kiện và kết quả đầu–cuối theo độ dài tài liệu, mức lặp tiêu đề và tăng kho 1×/3×. Phần BM25 dùng 0 lời gọi; kiểm hybrid cần một embedding/câu, đầu–cuối dự kiến 2–4 lượt sinh/kiểm mỗi câu.

### A2-07 [HIGH][confirmed] Đường đọc theo ID hợp các phân vùng phiên bản, làm mất lựa chọn theo câu hỏi

- Vị trí: [knowledge/runtime.py:225](</C:/Users/Duong Vinh/Vinh/services/api/src/campus247/infrastructure/knowledge/runtime.py:225>), [knowledge/runtime.py:570](</C:/Users/Duong Vinh/Vinh/services/api/src/campus247/infrastructure/knowledge/runtime.py:570>), [edition_release.py:214](</C:/Users/Duong Vinh/Vinh/services/api/src/campus247/application/knowledge/edition_release.py:214>), [knowledge/runtime.py:634](</C:/Users/Duong Vinh/Vinh/services/api/src/campus247/infrastructure/knowledge/runtime.py:634>).
- Bằng chứng: `rag_v2_sources` gọi chọn edition với `query=None`; `_rows` cũng dùng `None` khi đọc theo ID. Probe quan hệ thay thế có căn cứ: bản cũ áp dụng K70/K71, bản mới thay thế cho K71. `resolved_versions(None)` giữ **cả cũ và mới**; hỏi K71 chỉ giữ mới; hỏi K70 chỉ giữ cũ.
- Bằng chứng bổ sung: output của `rag_v2_sources` không chuyển tiếp `applicability_note`/`snapshot_scope` sang index. Bộ lọc đơn giản không thay thế đầy đủ phạm vi nghiệp vụ của resolver.
- Tác động tài liệu mới: khi thay thế riêng một phạm vi, nguồn cũ còn đúng cho phạm vi khác vẫn có thể vào ứng viên của câu hỏi hiện tại nếu các cổng phía sau không loại được.
- Tác động ổn định/vận hành: xếp hạng tương đồng có thể quyết định nguồn giữa hai bản khác nhau theo phạm vi. Đã xác nhận đường mã và lựa chọn resolver; chưa chạy đầu–cuối qua PostgreSQL.
- Đề xuất thiết kế: cache tập nguồn có quyền độc lập với câu hỏi, rồi áp resolver theo câu hỏi trên từng lượt trước ranking; giữ ràng buộc edition/phạm vi trong toàn bộ ngữ cảnh và khi revalidate.
- Kiểm chứng: test tích hợp thay thế theo một phần phạm vi, nguồn không có cohort trong tiêu đề, cache nóng/lạnh và revalidation; 0 lời gọi mô hình để kiểm tập nguồn.

### A2-08 [MEDIUM][confirmed] Bật reranker rồi lỗi không tương đương với chủ động tắt reranker

- Vị trí: [hybrid.py:138](</C:/Users/Duong Vinh/Vinh/services/api/src/campus247/rag_v2/retrieval/hybrid.py:138>), [hybrid.py:158](</C:/Users/Duong Vinh/Vinh/services/api/src/campus247/rag_v2/retrieval/hybrid.py:158>), [service.py:202](</C:/Users/Duong Vinh/Vinh/services/api/src/campus247/rag_v2/service.py:202>).
- Bằng chứng: cùng 22 unit và `final_limit=12`, tắt reranker trả 12 unit của một tài liệu; bật rồi giả lập timeout trả 10 unit của 10 tài liệu. Fallback chỉ sắp lại shortlist đa dạng đã chọn, không khôi phục toàn bộ RRF. Tắt có chủ đích vẫn ghi `fallback_used=True`, `RRF_TIMEOUT`.
- Tác động tài liệu mới: các khoản bổ trợ cùng văn bản có thể biến mất khi bật reranker nhưng dịch vụ lỗi; nếu thành công, cửa sổ 320 ký tự và ngưỡng logit −1 còn tạo lựa chọn khác.
- Tác động ổn định/vận hành: trạng thái tắt bị thống kê như timeout. Service hiện cố định deadline bằng 0, nên biến môi trường đơn thuần không bật lại đường này; rủi ro xuất hiện khi caller/cấu hình gọi hàm khác nhau.
- Đề xuất thiết kế: định nghĩa rõ ba chế độ tắt/thành công/lỗi; giữ danh sách fusion gốc cho fallback; ràng buộc ngân sách tiền chọn với `final_limit`; ghi trạng thái `DISABLED` riêng.
- Kiểm chứng: so sánh tập/rank khi tắt, timeout, HTTP lỗi, điểm sai định dạng và thành công; 0 mạng bằng MockTransport. Hiệu quả reranker thật cần một lượt rerank/câu.

### A2-09 [MEDIUM][confirmed] Hòa điểm BM25 chưa ổn định giữa các tiến trình

- Vị trí: [bm25.py:42](</C:/Users/Duong Vinh/Vinh/services/api/src/campus247/rag_v2/retrieval/bm25.py:42>), [bm25.py:49](</C:/Users/Duong Vinh/Vinh/services/api/src/campus247/rag_v2/retrieval/bm25.py:49>), [hybrid.py:132](</C:/Users/Duong Vinh/Vinh/services/api/src/campus247/rag_v2/retrieval/hybrid.py:132>).
- Bằng chứng: BM25 cộng số thực theo `set(features(query))`. Probe năm tài liệu có tổng điểm toán học bằng nhau, hoán vị tần suất năm từ; chạy `PYTHONHASHSEED=1..8` cho thứ tự khác nhau. Top-1 lần lượt có thể là unit `1`, `2` hoặc `0`; sai khác điểm khoảng 10⁻¹⁶.
- Tác động tài liệu mới: bảng và biểu mẫu có nhiều hàng gần giống nhau dễ hòa điểm; thứ tự nhỏ ở nhánh BM25 trở thành chênh lệch rank hữu hạn khi qua RRF.
- Tác động ổn định/vận hành: khóa phụ `unit_id` chỉ xử lý điểm float bằng hẳn nhau; restart hoặc nhiều worker có thể chọn ngữ cảnh khác. Chưa đo mức thay đổi loại outcome A6 đầu–cuối.
- Đề xuất thiết kế: cố định thứ tự duyệt feature và phép cộng; định nghĩa quy tắc hòa điểm số học trước khi dùng khóa ID.
- Kiểm chứng: chạy nhiều hash seed và hoán vị thứ tự nạp, yêu cầu rank/score tái lập; sau đó kiểm A6 nhiều worker. Probe xác định dùng 0 lời gọi thật.

### A2-10 [MEDIUM][confirmed] Chi phí mỗi lượt vẫn quét toàn kho, timeout không chặn được phần CPU đồng bộ

- Vị trí: [agent/nodes/rag_v2.py:125](</C:/Users/Duong Vinh/Vinh/services/api/src/campus247/agent/nodes/rag_v2.py:125>), [hybrid.py:113](</C:/Users/Duong Vinh/Vinh/services/api/src/campus247/rag_v2/retrieval/hybrid.py:113>), [memory_index.py:101](</C:/Users/Duong Vinh/Vinh/services/api/src/campus247/rag_v2/adapters/memory_index.py:101>), [service.py:171](</C:/Users/Duong Vinh/Vinh/services/api/src/campus247/rag_v2/service.py:171>).
- Bằng chứng: mỗi lượt node duyệt mọi unit để kiểm binding; hybrid duyệt lại để tạo `allowed`. Vector tính tích vô hướng toàn ma trận rồi mới lọc/sắp xếp. Facts lookup quét toàn bộ facts.
- Bằng chứng đo: trung vị 11 lần BM25 top-40 ở N=9.071→27.213: “an toan thong tin” **5,99→22,11 ms**; “hoc phi 2026-2027” **12,92→45,11 ms**; “ky tuc xa” **6,78→25,82 ms**. Không gồm embedding, SQL, generation hoặc reranker.
- Tác động tài liệu mới: tăng số unit, chiều dài nguồn và facts làm tăng cả chi phí duyệt, hash và ranking; lọc quyền nhỏ chưa làm vector tính ít đi.
- Tác động ổn định/vận hành: vector có timeout 1 giây nhưng phần CPU không `await` có thể giữ event loop vượt hạn; tải đồng thời dễ làm đổi sang lexical fallback.
- Đề xuất thiết kế: lập chỉ mục phạm vi và binding theo snapshot bất biến có generation; chọn hàng vector đủ điều kiện trước phép tính; dùng top-k từng phần, worker CPU và ngân sách theo giai đoạn.
- Kiểm chứng: benchmark 1×/3×/10×, tải đồng thời, độ trễ event loop và tỷ lệ fallback; kiểm quyền/thu hồi vẫn cập nhật đúng. 0 lời gọi thật cho CPU; độ trễ thực cần phép đo riêng có SQL và embedding.

## Kiểm kê đầy đủ luật viết tay trong hiểu câu hỏi

Các vị trí dưới đây thuộc `services/api/src/campus247/rag_v2/understanding/`, trừ nơi ghi khác.

| Luật/từ vựng | Nội dung và quyết định bị ảnh hưởng |
|---|---|
| `analyze.py:10` — 10 topic | `hoc_phi`: hoc phi/muc thu/dong tien hoc; `hoc_bong`: hoc bong; `hoc_phan`: hoc phan/dang ky/rut mon/tin chi; `quy_che`: quy che/quy dinh/buoc thoi hoc/canh bao hoc/bao luu/nghi hoc; `tot_nghiep`: tot nghiep; `ky_tuc_xa`: ky tuc xa; `thu_vien`: thu vien; `chuong_trinh`: chuong trinh/nganh/tien quyet/song hanh; `thu_tuc`: thu tuc/ho so/bang diem/giay xac nhan; `lich`: lich thi/lich hoc/nghi tet/khai giang. Ảnh hưởng hỏi lại, lịch sử, chọn fact; không trực tiếp giới hạn tài liệu theo topic. |
| `analyze.py:21` — ngành | 7480201=CNTT; 7480202=ATTT; 7580201=kỹ thuật xây dựng; 7580101=kiến trúc; 7580301=kinh tế xây dựng; 7580302=quản lý xây dựng. Dùng nhận ngành và chuẩn hóa tên/mã để lọc. Ngành khác chỉ nhận mã `7\d{6}`, không nhận tên tương đương. |
| `analyze.py:29` — hệ/chương trình | chất lượng cao, tiên tiến, vừa làm vừa học, liên thông, đại trà, chính quy. Dùng làm phạm vi và điều kiện đủ cho câu học phí. |
| `analyze.py:31` — 86 từ dừng | `la gi nao the sao ai dau o bao nhieu may khi luc co khong duoc chua nhe a da di voi oi vay thi va cua ve cho toi em minh ban anh chi thay xin hoi biet giup can muon hay nay do kia cai viec chuyen lam nhu mot nhung cac rat qua chut nua roi se phai nen tu den vi tai bi ma neu thu tuc quy dinh thong tin van de huong dan noi dung truong huce sinh vien nha`. Dùng đếm chủ thể để hỏi lại. |
| `analyze.py:36` — `_SUGGEST` | “Bạn muốn hỏi về học phí, học bổng, đăng ký học phần, bảo lưu, tốt nghiệp hay ký túc xá?” Định hướng câu hỏi lại về sáu nhóm hiện có. |
| `analyze.py:39` — khớp cụm | Ranh giới từ, không khớp chuỗi con tùy ý; áp dụng cho topic và phần lớn từ khóa quyết định. |
| `analyze.py:51` — hình thức phạm vi | Khóa `k` + 2–3 chữ số; năm dạng `20xx-20xx`; học kỳ 1/2/3 hoặc I/II/III. Chỉ lấy khóa/năm đầu và ngành đầu theo bảng. |
| `analyze.py:69` — nối tiếp | Dạng rút gọn Kxx/năm/học kỳ/bao nhiêu/khi nào/bao giờ; hoặc đầu câu “còn”, “thế còn”, “vậy”. Duyệt tối đa bốn lượt trước có topic, không OOS; topic mới không giao thì dừng. Có thể kế thừa phạm vi và ghép truy vấn. |
| `analyze.py:87` — trường khác | Bách khoa, Ngoại thương, Kinh tế quốc dân, FPT, VinUni, HUST, HCMUT, Harvard, Stanford; `NEU` viết hoa được kiểm riêng. Gây OOS nếu không có tên trường mình. |
| `analyze.py:91` — tên sau tiền tố trường/đại học/đh/học viện/cao đẳng | Y Hà Nội, Y dược, Luật, Thương mại, Sư phạm, Thủy lợi, Giao thông vận tải/Giao thông, Công nghiệp, Hàng hải, Nông nghiệp, Mỏ địa chất, Tài nguyên, Kiến trúc Hà Nội/TP, Quốc gia, Phenikaa, Văn Lang, Duy Tân, Hoa Sen, RMIT, FPT, Bách khoa, Ngoại thương, Kinh tế quốc dân, Công nghệ, Tài chính, Ngân hàng, Báo chí, Điện lực, Thăng Long, Hòa Bình. Cùng luật đầu câu/“của trường khác”: gây OOS. |
| `analyze.py:96` — `own_school` | huce/xay dung ha noi/dhxdhn: vô hiệu hóa OOS do tên trường khác; không vô hiệu hóa nhóm từ khóa OOS tiếp theo. |
| `analyze.py:99` — OOS theo chủ đề | thoi tiet, du bao mua, gia bitcoin, ty gia, ket qua bong da, nau an, tu vi. Từ chối trước truy xuất dù câu có HUCE. |
| `analyze.py:101` — thứ tự loại câu hỏi | OOS → deadline: han nop/han dong/han cuoi/bao gio/khi nao/ngay nao → compare: so sanh/khac nhau → contact: lien he/email/dien thoai/o dau → procedure: thu tuc/ho so/cach/nhu the nao → condition: dieu kien/duoc khong/co duoc/tien quyet → number: bao nhieu/may tien/muc thu/don gia → smalltalk nếu toàn câu là xin chao/chao/hello/hi/cam on; còn lại lookup. Ảnh hưởng slot và fact lookup. |
| `analyze.py:122` — miễn hỏi phạm vi vì có phần trả lời chung | quy dinh/quy che/dieu kien/thu tuc/cach/lien he/la gi/nguyen tac/gom nhung/cau truc/phuong thuc/mien giam/chinh sach/doi tuong. |
| `analyze.py:126` — văn bản/bậc đào tạo | quyet dinh/thong bao/van ban/nghi dinh/cong van + số: bỏ yêu cầu slot; cu nhan/ky su/kien truc su/ks/kts: thay thế slot ngành ở câu số tiền học phí. |
| `analyze.py:128` — thiếu phạm vi | Học phí + number cần khóa hoặc năm, cùng ngành/hệ/bậc; deadline học phí/miễn giảm/học bổng cần học kỳ hoặc năm. Sinh câu hỏi lại bằng ba nhãn slot cố định. |
| `analyze.py:137` — mơ hồ | Không topic: hỏi lại nếu không còn chủ thể, chủ thể đơn thuộc diem/thi/hoc/phi/lop/mon, hoặc ≤2 từ không có số. Thêm luật đại từ do/nay/kia/no khi không lịch sử và ≤4 từ chủ thể. |
| `normalize.py:15` — 48 cụm | Các cụm đầu vào: hoc phi, hoc bong, hoc phan, hoc ky, ky 1, ky 2, ky 3, nam hoc, tin chi, dang ky, han nop, han dong, bao nhieu, khi nao, bao gio, dieu kien, thu tuc, quy che, quy dinh, tot nghiep, bao luu, thoi hoc, buoc thoi hoc, duoi hoc, rot mon, truot mon, no mon, ky tuc xa, thu vien, lien he, ren luyen, cong nghe thong tin, an toan thong tin, ky thuat xay dung, kien truc, kinh te xay dung, quan ly xay dung, dai tra, chinh quy, chat luong cao, tien tien, lien thong, vua lam vua hoc, chuong trinh, nganh, he dao tao, xin chao, thoi tiet. Phần lớn phục hồi dấu; ky 1/2/3→học kỳ 1/2/3; duoi hoc→buộc thôi học; rot/truot mon→không đạt học phần; no mon→học phần chưa đạt. Đổi truy vấn và có thể đổi topic. |
| `normalize.py:35` — 17 viết tắt | sv→sinh viên; đk/dk→đăng ký; đc/dc→được; ko/hok→không; j→gì; ntn→như thế nào; ktx→ký túc xá; rl→rèn luyện; qđ/qd→quyết định; tc→tín chỉ; gv→giảng viên; cntt→công nghệ thông tin; attt→an toàn thông tin. Không thay bên trong mã có ký tự chữ/số hoặc `/.-` liền kề. |
| `normalize.py:43` — dạng chữ/năm | NFC, gộp khoảng trắng, viết thường; hk1/2/3→học kỳ; năm ngắn chỉ mở thành 20xx khi đầu 20–40 và hai năm liên tiếp; chuẩn hóa dấu phân cách năm dài và K có 2–3 chữ số. Định hướng truy xuất/nhận phạm vi; 41–42 chưa được mở. |

Luật liên quan ở phía truy xuất/fact lookup cũng còn viết tay:

- `retrieval/hybrid.py:32`: hai chiều track cố định `{chính quy, liên thông, vừa làm vừa học}` và `{đại trà, chất lượng cao, tiên tiến}`.
- `retrieval/hybrid.py:47`: từ dừng chọn cửa sổ rerank: `em toi minh cho hoi la gi co duoc khong va cua ve bao nhieu nam hoc ky nao the`; `_article` nhận “Điều + số” để đa dạng điều.
- `service.py:43`: deadline/contact đi fact tương ứng; “tiên quyết” đi prerequisite; `hoc_phi` + number/lookup đi fee.
- `service.py:53–111`: từ chỉ điều kiện/ngoại lệ, chủ thể đầy đủ, phạm vi, học kỳ 1–3 và email/điện thoại quyết định có được trả fact trực tiếp; dấu `;`, phẩy, xuống dòng hoặc “và/đồng thời/ngoài ra” chuyển sang đường sinh.
- Chủ đề ngoài bảng, nếu không trúng cổng chặn, vẫn đi lexical/vector; không có danh sách topic bắt buộc để được truy xuất. “Ký túc xá” vốn đã nằm trong bảng; các probe dưới đây dùng chủ đề khác.

### Kết quả 15 câu hỏi tự viết chạy `analyze` ngoại tuyến

| # | Câu hỏi | Kết quả chính |
|---|---|---|
| 1 | Mượn thiết bị? | `unclear`, hỏi lại |
| 2 | Cấp VPN? | `unclear`, hỏi lại |
| 3 | Gia hạn VPN? | `lookup`, đi tiếp |
| 4 | Nghiên cứu khoa học cần nộp đề cương ở đâu? | `contact`, đi tiếp |
| 5 | Câu lạc bộ robot có thể đặt xưởng chế tạo vào cuối tuần không? | `lookup`, đi tiếp |
| 6 | Mượn máy ảnh của trung tâm truyền thông cần đặt cọc bao nhiêu? | `number`, đi tiếp |
| 7 | Phòng thí nghiệm mô phỏng thời tiết mở cửa lúc nào? | `oos`, từ chối |
| 8 | Dự án nghiên cứu tỷ giá được tài trợ tối đa bao nhiêu? | `oos`, từ chối |
| 9 | Phòng máy có được dùng FPT AI để nghiên cứu không? | `oos`, từ chối |
| 10 | Phòng máy HUCE có được dùng FPT AI để nghiên cứu không? | `condition`, đi tiếp |
| 11 | Chi phí bồi thường thiết bị hỏng bao nhiêu? | `number`, đi tiếp |
| 12 | Nộp đề xuất sáng chế cần chữ ký của ai? | `lookup`, đi tiếp |
| 13 | Phí sử dụng xưởng nghiên cứu đã bao gồm học phí bao nhiêu? | `number`, hỏi khóa/năm và ngành |
| 14 | Trung tâm nghiên cứu cấp tài khoản HPC trong bao lâu? | `lookup`, đi tiếp |
| 15 | Gia hạn chứng thư số này? | `unclear`, hỏi lại |

Đây là kết quả cổng hiểu câu hỏi, chưa phải đánh giá câu trả lời trên nguồn mới. Câu 13 cố ý kiểm giao thoa với từ khóa học phí; câu 15 kiểm luật đại từ.

## Phần đã kiểm và thấy ổn

- **Tham số truy xuất:** BM25 `k1=1,5`, `b=0,75`; feature gồm từ đơn/cặp từ có dấu và bỏ dấu. Mặc định lexical/vector/neo tối đa 40 mỗi nhánh, union tối đa 120; RRF cộng `1/(60+rank)`, không phụ thuộc thang điểm nhánh. Điểm RRF hòa được sắp theo `unit_id`.
- **Giới hạn thực tế:** service lấy top-12, tắt reranker; đường bật mặc định tiền chọn ít nhất 10, cuối 8, deadline 4,5 giây, logit phải >−1, cửa sổ ≤320 ký tự. Context runtime tối đa 6 parent chunk và 19.000 byte JSON. Neighbor expansion mặc định 6 seed, 4 sibling/seed, cap 16 nhưng service hiện không gọi nó.
- **Hiệu lực/thay thế:** SQL giữ `effective_from ≤ thời điểm hỏi < effective_until`; bản hết hạn bị loại. Resolver có `REPLACES`, phát hiện `EDITION_CONFLICT`, chu trình và thiếu căn cứ; không tự chọn theo lần tải mới nhất. Probe xác nhận bản hết hạn nhận `EXPIRED_FOR_QUERY`, hai bản chồng lấn không có quan hệ nhận `NEEDS_INFORMATION`. Giới hạn còn lại là A2-07 và thành viên legacy chưa mapping vẫn dùng hợp đồng cũ.
- **Reranker HTTP:** cố định loopback, không chuyển hướng, giới hạn response 1 MiB, kiểm đủ index/score hữu hạn, hủy batch còn lại khi lỗi; test dùng MockTransport, không gọi mạng.
- **Độ phức tạp:** với N unit, d chiều vector, M ứng viên có điểm và P posting được duyệt: lọc O(N); BM25 O(P + M log M); vector O(Nd + A log A), A là số unit đủ điều kiện; fusion nhỏ theo tổng kích thước nhánh. Kiểm binding còn phụ thuộc tổng lượng văn bản, facts lookup O(F).
- **Test đã chạy:** `.venv/Scripts/python.exe -B -m pytest tests/rag_v2/understanding/test_analyze.py tests/rag_v2/retrieval tests/knowledge_platform/test_source_snapshot.py -q -s -p no:cacheprovider` → **145 passed**.
- **Test phiên bản:** cùng cách chạy cho `tests/knowledge_platform/test_version_resolver.py` và `test_edition_question_scope.py` → **20 passed**.
- Lệnh pytest ban đầu không có `-s` bị chặn vì không tạo được tệp tạm; chạy lại không capture đã đạt. Hai runner probe được đọc nhưng không chạy nguyên bản vì chúng gọi endpoint mô hình và ghi output. Các probe audit dùng Python `-B` qua stdin, xử lý hoàn toàn trong RAM.

## Câu hỏi mở cần chủ dự án quyết định

- Cần chốt phạm vi sản phẩm đối với nghiên cứu khoa học, phòng thí nghiệm và các dịch vụ mới để kiểm OOS theo chính sách có phiên bản.
- Cần chốt hành vi khi phạm vi nguồn là `UNKNOWN`: hỏi thêm, chỉ trình bày điều nguồn nêu, hay không kết luận áp dụng. Hiện các tầng đang xử lý khác nhau.

## Thiết kế đề xuất cho hiểu câu hỏi + truy xuất không phụ thuộc kho

- Giữ truy vấn gốc; sinh danh mục thực thể, ngành, mã và viết tắt từ metadata/nguồn được duyệt lúc dựng chỉ mục.
- Viết tắt đa nghĩa tạo phương án tìm kiếm; không thay nghĩa trực tiếp nếu thiếu căn cứ ngữ cảnh.
- Tách phạm vi sản phẩm khỏi danh sách từ khóa nội dung; quyết định OOS dựa trên đối tượng và nguồn đủ quyền.
- Dùng một kiểu phạm vi chung: `ALL/UNKNOWN`, tập giá trị, khoảng mở/đóng, thời gian và căn cứ nguồn.
- Biểu diễn câu hỏi nhiều ý thành các ý và phạm vi riêng; giữ ánh xạ ấy đến kiểm chứng đầu ra.
- Cache quyền và dữ liệu bất biến theo generation; áp phạm vi câu hỏi và resolver phiên bản trước mọi giới hạn ranking.
- Đưa lexical/vector/neo vào cùng hợp đồng index; mọi adapter cấp quyền phải giữ đủ nhánh.
- Truy xuất phân cấp tài liệu→đoạn; tách điểm tiêu đề khỏi thân bài, bảo vệ nguồn độc lập và các khoản bổ trợ.
- Giữ fusion gốc cho fallback; phân biệt reranker tắt, lỗi và thành công bằng trace rõ ràng.
- Cố định phép cộng/hòa điểm; tối ưu tập đủ điều kiện và top-k, đưa CPU nặng khỏi event loop.
- Cổng ngoại tuyến: chủ đề mới, viết tắt đa nghĩa, chuyển chủ đề, nhiều phạm vi, mã mới và văn bản thay thế.
- Cổng tăng kho: 1×/3×/10×, tiêu đề lặp, tài liệu ngắn/dài; đo gold chunk, đủ dữ kiện, độ đa dạng và độ trễ.
- Chỉ chấp nhận cải thiện recall khi kiểm đầu–cuối cũng giữ độ đúng, từ chối đúng và nhất quán; không dùng riêng ceiling context để quyết định như giới hạn đã thấy ở §18.2.