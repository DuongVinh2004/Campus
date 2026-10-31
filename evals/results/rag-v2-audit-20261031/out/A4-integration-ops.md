# A4 — Tích hợp, an toàn, vận hành và ổn định runtime

## Tóm tắt

**Chưa đủ điều kiện bật v2 mặc định.** Có các lỗ hổng về bảo toàn điều kiện nguồn, thu hồi, viết lại câu hỏi và đồng bộ chỉ mục.
Phát hiện 14 vấn đề dưới đây bằng đọc mã và probe ngoại tuyến; không gọi nhà cung cấp, khởi động runtime, sửa hoặc tạo tệp.
Kiểm thử: **184 đạt**, hai ca bị chặn vì cần ghi SQLite, một ca kiến trúc thất bại tại vi phạm đã được REPORT ghi nhận.
Bằng chứng gồm kiểm thử hiện có và dữ liệu tổng hợp đối chiếu bằng mã; chưa đo người dùng thật.
Không đọc nội dung ca trong các thư mục holdout.

## Phát hiện

### A4-01 [BLOCKER][confirmed] Đoạn cha bị chặn injection vẫn cho phép trả dữ kiện thiếu điều kiện

- Vị trí: [adapters/runtime.py:35](<C:/Users/Duong Vinh/Vinh/services/api/src/campus247/rag_v2/adapters/runtime.py:35>), [service.py:69](<C:/Users/Duong Vinh/Vinh/services/api/src/campus247/rag_v2/service.py:69>), [service.py:171](<C:/Users/Duong Vinh/Vinh/services/api/src/campus247/rag_v2/service.py:171>).
- Bằng chứng: probe dùng dòng học phí và điều kiện ở dòng kế “chỉ áp dụng cho học phần học lại”. Thêm injection vào đoạn cha: kết quả `grounded_answer`, không có điều kiện học lại, **0 lời gọi v2**. Đoạn cha dài trên 12.000 ký tự cũng làm nhánh dữ kiện bỏ qua hai lời gọi sinh/kiểm.
- Tác động tài liệu mới: tài liệu dài hoặc chứa chỉ dẫn độc hại có thể làm mất điều kiện áp dụng của dữ kiện.
- Tác động ổn định/vận hành: sửa ở §9.3 chưa đủ vì `chunk_unit()` trả `None` khi chặn, nhưng `_self_contained()` coi đó như không có đoạn cha để kiểm.
- Đề xuất thiết kế: phân biệt rõ đoạn cha không tồn tại với đoạn cha bị từ chối; trạng thái từ chối phải loại mọi unit/fact phụ thuộc.
- Kiểm chứng: test xác định cho injection ở tiêu đề, đường dẫn, bảng và phần kế tiếp; thêm đoạn cha quá dài. Không cần mô hình thật.

### A4-02 [BLOCKER][confirmed] Thu hồi chưa chặn lần gửi mô hình kế tiếp và còn khe hở trước terminal SSE

- Vị trí: [nodes/rag_v2.py:101](<C:/Users/Duong Vinh/Vinh/services/api/src/campus247/agent/nodes/rag_v2.py:101>), [nodes/rag_v2.py:156](<C:/Users/Duong Vinh/Vinh/services/api/src/campus247/agent/nodes/rag_v2.py:156>), [chat.py:325](<C:/Users/Duong Vinh/Vinh/services/api/src/campus247/presentation/chat.py:325>).
- Bằng chứng: probe thu hồi sau bước sinh cho `semantic_after_revoke=True`; chỉ cuối lượt mới thành `system_error`. Probe ASGI thu hồi tại `is_disconnected()` sau lần kiểm cuối vẫn nhận `citation.added` và `message.completed`, không có `message.failed`.
- Tác động tài liệu mới: khi tài liệu bị thu hồi hoặc thay thế giữa lượt, nội dung cũ vẫn có thể được gửi tiếp tới bộ kiểm ngữ nghĩa hoặc phát trích dẫn cuối.
- Tác động ổn định/vận hành: sửa cache ở §3 bảo vệ nhiều đường trả lời nhưng chưa chứng minh cửa sổ thu hồi bằng không. `GuardedGateway` kiểm lịch sử/actor, không kiểm lại quyền nguồn.
- Đề xuất thiết kế: kiểm epoch/quyền nguồn trước mỗi dispatch; xác định điểm công bố terminal và ràng buộc thu hồi với điểm đó. Đặt kiểm cuối sau các bước `await` chuẩn bị phát.
- Kiểm chứng: test điều phối thu hồi tại từng ranh giới generation, semantic, delta, citation và completed; dùng barrier/fake, 0 lời gọi thật.

### A4-03 [BLOCKER][confirmed] Viết lại được phép đổi mã khóa và năm đã nêu rõ

- Vị trí: [rewrite.py:43](<C:/Users/Duong Vinh/Vinh/services/api/src/campus247/rag_v2/generation/rewrite.py:43>), [nodes/rag_v2.py:116](<C:/Users/Duong Vinh/Vinh/services/api/src/campus247/agent/nodes/rag_v2.py:116>).
- Bằng chứng: đưa câu mới chứa `K64`, `2026-2027`; fake trả bản viết lại chứa `K65`, `2027-2028`. Hàm chấp nhận. Kiểm sau mô hình chỉ giới hạn độ dài và URL/email.
- Tác động tài liệu mới: nhiều phiên bản có cấu trúc tương tự làm hệ thống trả lời đúng nguồn cho sai khóa/năm.
- Tác động ổn định/vận hành: sửa prompt ở §17.2 chưa đủ vì yêu cầu giữ nguyên mã không được mã xác định kiểm tra.
- Đề xuất thiết kế: viết lại thành các slot có provenance; bảo toàn mã, số, tên và phủ định đã nêu rõ. Chỉ bổ sung slot thiếu từ lịch sử hợp lệ.
- Kiểm chứng: test sửa/xóa/thêm mã, năm, đơn vị và từ phủ định; bản vi phạm phải quay về câu gốc. Sau sửa có thể đo thêm 20–30 lượt mô hình thật.

### A4-04 [BLOCKER][confirmed] Chỉ mục lệch release vẫn được nạp và readiness không phát hiện

- Vị trí: [bootstrap/rag_v2.py:19](<C:/Users/Duong Vinh/Vinh/services/api/src/campus247/bootstrap/rag_v2.py:19>), [bootstrap/rag_v2.py:35](<C:/Users/Duong Vinh/Vinh/services/api/src/campus247/bootstrap/rag_v2.py:35>), [health.py:93](<C:/Users/Duong Vinh/Vinh/services/api/src/campus247/presentation/health.py:93>).
- Bằng chứng: loader nhận snapshot `OLD_RELEASE/generation=1` trong khi runtime khai `NEW_RELEASE/generation=2`; **0 lần đọc trạng thái runtime**. Health không kiểm v2, chỉ kiểm database và trả Redis disabled.
- Tác động tài liệu mới: chunk mới không nằm trong danh sách ID đóng tại startup, nên không được truy xuất cho tới khi dựng và nạp lại chỉ mục.
- Tác động ổn định/vận hành: release DB có thể được báo phục vụ trong khi chỉ mục v2 thiếu nguồn mới; hệ thống từ chối thay vì báo lệch release.
- Đề xuất thiết kế: activation ràng buộc manifest, release, generation, fingerprint và embedding identity; readiness kiểm binding này cùng trạng thái warm-up.
- Kiểm chứng: test startup và đổi release với thêm, thay thế, bỏ chunk; readiness phải phản ánh trạng thái chuyển tiếp. Không cần mô hình thật.

### A4-05 [HIGH][confirmed] Debug vẫn ghi nguyên câu hỏi, lịch sử và nội dung nguồn

- Vị trí: [generate.py:76](<C:/Users/Duong Vinh/Vinh/services/api/src/campus247/rag_v2/generation/generate.py:76>), [rewrite.py:50](<C:/Users/Duong Vinh/Vinh/services/api/src/campus247/rag_v2/generation/rewrite.py:50>).
- Bằng chứng: chặn ghi bằng bộ đệm RAM; `generation.jsonl` có câu hỏi nguyên văn trong `content`, dù có `question_sha`. `rewrite.jsonl` chứa `previous`, `question`, `rewritten` nguyên văn.
- Tác động tài liệu mới: nội dung nguồn hoặc câu hỏi có dữ liệu cá nhân có thể được lưu ngoài đường tối thiểu hóa thông thường.
- Tác động ổn định/vận hành: sửa ở §9.4 chưa đủ vì payload vẫn chứa câu hỏi; chú thích “synthetic only” không phải kiểm soát thực thi.
- Đề xuất thiết kế: debug mặc định chỉ ghi schema/mã/đếm/hash; capture nội dung phải có chế độ tổng hợp được xác minh, giới hạn kích thước và vòng đời.
- Kiểm chứng: canary tổng hợp trong câu hỏi, lịch sử, nguồn và đầu ra phải không xuất hiện trong capture vận hành; test hoàn toàn trong RAM.

### A4-06 [HIGH][confirmed] Một số lỗi hạ tầng bị báo thành thiếu nguồn hoặc không kiểm chứng được

- Vị trí: [hybrid.py:117](<C:/Users/Duong Vinh/Vinh/services/api/src/campus247/rag_v2/retrieval/hybrid.py:117>), [service.py:224](<C:/Users/Duong Vinh/Vinh/services/api/src/campus247/rag_v2/service.py:224>), [generate.py:91](<C:/Users/Duong Vinh/Vinh/services/api/src/campus247/rag_v2/generation/generate.py:91>), [chat.py:348](<C:/Users/Duong Vinh/Vinh/services/api/src/campus247/presentation/chat.py:348>).
- Bằng chứng: vector timeout + lexical rỗng → `refuse/no_source`; đầu ra sinh không phải JSON → `refuse/unverified`, `safe_refusal`. `PlatformError(503, KNOWLEDGE_RUNTIME_UNAVAILABLE)` trước node → SSE `message.failed`, `INTERNAL_ERROR`, status 500.
- Tác động tài liệu mới: câu cần nhánh vector hoặc cấu trúc sinh mới có thể bị kết luận kho thiếu dù nguyên nhân là dịch vụ lỗi.
- Tác động ổn định/vận hành: làm thấp giả số lỗi A7 và chỉ sai hướng xử lý cho người dùng/quản trị.
- Đề xuất thiết kế: truyền trạng thái từng nhánh và lỗi parse có kiểu; phân biệt “đã tìm thành công nhưng rỗng” với “không tìm được vì lỗi”.
- Kiểm chứng: ma trận lỗi embedding, generation, semantic, snapshot, authorization và transport; xác nhận cả thông báo lẫn nhãn đo. Không cần gọi thật.

### A4-07 [MEDIUM][confirmed] `outcome_kind` không đi tới SSE và lịch sử

- Vị trí: [stream_result.py:79](<C:/Users/Duong Vinh/Vinh/services/api/src/campus247/application/conversation/stream_result.py:79>), [read.py:47](<C:/Users/Duong Vinh/Vinh/services/api/src/campus247/application/conversation/read.py:47>).
- Bằng chứng: `FinalChatResult` chỉ có `status`, `response_class`, `content`, `citations`, `agent_run_id`; `final_payload()` không phát `outcome_kind`. Lý do `no_source/out_of_scope/unverified/unsafe` chỉ còn trong state.
- Tác động tài liệu mới: không thể phân tích đáng tin các kiểu từ chối khi nạp kho mới qua hợp đồng API.
- Tác động ổn định/vận hành: hợp đồng bổ sung trong SPEC chưa hoàn thành; `response_class` vẫn phân biệt system error nhưng không thay thế đầy đủ outcome có kiểu.
- Đề xuất thiết kế: bảo toàn outcome/reason qua DTO cuối, persistence, GET lịch sử và SSE bằng trường tương thích ngược.
- Kiểm chứng: contract test round-trip toàn bộ outcome/reason, kể cả thay thế do history policy và stream guard.

### A4-08 [HIGH][confirmed] Tái kiểm nguồn dùng câu gốc trong khi truy xuất dùng câu đã viết lại

- Vị trí: [nodes/rag_v2.py:121](<C:/Users/Duong Vinh/Vinh/services/api/src/campus247/agent/nodes/rag_v2.py:121>), [nodes/rag_v2.py:156](<C:/Users/Duong Vinh/Vinh/services/api/src/campus247/agent/nodes/rag_v2.py:156>), [runtime.py:624](<C:/Users/Duong Vinh/Vinh/services/api/src/campus247/infrastructure/knowledge/runtime.py:624>).
- Bằng chứng: snapshot yêu cầu năm học; câu viết lại có `2026-2027` được phép, câu gốc thiếu năm bị loại. Probe qua workflow: service tạo `answer`, sau revalidate thành `system_error`; callback nhận đúng câu gốc.
- Tác động tài liệu mới: hội thoại nối tiếp trên thông báo có phạm vi năm học sẽ lỗi dù đã tìm đúng nguồn.
- Tác động ổn định/vận hành: gây từ chối không ổn định theo cấu trúc metadata nguồn và tăng A7.
- Đề xuất thiết kế: tạo một đối tượng câu hỏi đã giải quyết phạm vi, dùng nhất quán cho authorization, generation và revalidation, kèm ràng buộc ở A4-03.
- Kiểm chứng: test nhiều lượt với năm, khóa, chương trình và edition; 0 lời gọi thật.

### A4-09 [HIGH][confirmed] Đường v2 làm mất metadata thẩm quyền và giới hạn sử dụng nguồn

- Vị trí: [runtime.py:305](<C:/Users/Duong Vinh/Vinh/services/api/src/campus247/infrastructure/knowledge/runtime.py:305>), [runtime.py:634](<C:/Users/Duong Vinh/Vinh/services/api/src/campus247/infrastructure/knowledge/runtime.py:634>), [discipline.py:100](<C:/Users/Duong Vinh/Vinh/services/api/src/campus247/rag_v2/discipline.py:100>).
- Bằng chứng: projection `rag_v2_sources()` bỏ `applicability_note`, `_verified_publication`, `_verified_curriculum`; probe xác nhận cả ba mất. V1 có bước gọi `verified_attachment()`, v2 không có bước tương đương.
- Tác động tài liệu mới: bản chụp lưu trữ mất cảnh báo phạm vi; tệp đính kèm ngoài miền HUCE không được hưởng attestation hợp lệ như đường v1.
- Tác động ổn định/vận hành: đề xuất ở §17.4.5 chưa đủ vì còn thiếu dây nối runtime. Test attestation hiện chèn trực tiếp giá trị vào row nên không bắt được khoảng trống này.
- Đề xuất thiết kế: dùng DTO evidence chung, giữ các attestation phía server và đưa giới hạn áp dụng thích hợp vào ngữ cảnh kiểm chứng.
- Kiểm chứng: test xuyên từ source reader tới node, output guard và history presentation; bao gồm snapshot lưu trữ và attachment đã xác thực.

### A4-10 [HIGH][confirmed] Lớp ủy quyền làm mất nhánh truy hồi theo mã định danh

- Vị trí: [adapters/runtime.py:49](<C:/Users/Duong Vinh/Vinh/services/api/src/campus247/rag_v2/adapters/runtime.py:49>), [hybrid.py:124](<C:/Users/Duong Vinh/Vinh/services/api/src/campus247/rag_v2/retrieval/hybrid.py:124>).
- Bằng chứng: `MemoryIndex` có `anchored()`, `AuthorizedIndex` không có. Probe 51 unit, vector lỗi: gold xuất hiện trong top-12 khi gọi index trực tiếp, biến mất khi bọc lớp ủy quyền.
- Tác động tài liệu mới: mã chương trình/học phần hiếm dễ bị nguồn có nhiều từ chung lấn chỗ.
- Tác động ổn định/vận hành: sửa neo mã ở §10 không được giữ nguyên trên đường runtime; phép thăm dò trực tiếp có thể đánh giá tốt hơn đường phục vụ.
- Đề xuất thiết kế: mở rộng port và adapter ủy quyền cho nhánh anchored, áp cùng tập `allowed` trước ranking.
- Kiểm chứng: chạy cùng fixture qua index trực tiếp và facade; kết quả phải tương đương trong cùng phạm vi quyền.

### A4-11 [HIGH][confirmed] Quét đồng bộ chặn event loop; cache theo phạm vi không có giới hạn dung lượng

- Vị trí: [nodes/rag_v2.py:125](<C:/Users/Duong Vinh/Vinh/services/api/src/campus247/agent/nodes/rag_v2.py:125>), [runtime.py:588](<C:/Users/Duong Vinh/Vinh/services/api/src/campus247/infrastructure/knowledge/runtime.py:588>).
- Bằng chứng: vòng binding + injection trên 9.071 unit từ bản xuất kho mất **2,396 giây**, ticker trên cùng loop cũng bị ngắt **2,396 giây**. Probe 21 phạm vi tạo 21 entry; cache chỉ loại epoch khác, không có LRU/trần byte.
- Tác động tài liệu mới: số unit và số phạm vi tăng làm chi phí mỗi lượt và bộ nhớ tăng theo.
- Tác động ổn định/vận hành: ảnh hưởng request khác; `asyncio.timeout` không ngắt vòng CPU đồng bộ. Ma trận hiện tại riêng đã chiếm 37.154.816 byte, chưa tính BM25, chuỗi và cache.
- Đề xuất thiết kế: tiền tính phần bất biến theo checksum; chuyển CPU cần thiết sang executor có giới hạn; giới hạn cache theo byte/entry và quản lý tác vụ nền.
- Kiểm chứng: probe ticker và tải nhiều phạm vi trên kho tăng kích thước; đo RSS, cache size, p95 và khả năng hủy. Không cần mô hình thật.

### A4-12 [HIGH][confirmed] Giới hạn lời gọi và token của lượt không được áp dụng xuyên v2

- Vị trí: [graph.py:473](<C:/Users/Duong Vinh/Vinh/services/api/src/campus247/agent/graph.py:473>), [budget.py:15](<C:/Users/Duong Vinh/Vinh/services/api/src/campus247/agent/budget.py:15>), [service.py:230](<C:/Users/Duong Vinh/Vinh/services/api/src/campus247/rag_v2/service.py:230>), [service.py:264](<C:/Users/Duong Vinh/Vinh/services/api/src/campus247/rag_v2/service.py:264>).
- Bằng chứng: đặt `RunBudget(max_provider_calls=1, max_total_tokens=1)` vẫn có **7 lời gọi fake** và trả `grounded_answer`: phân loại/định tuyến 2, viết lại 1, sinh 2, ngữ nghĩa 2.
- Tác động tài liệu mới: nguồn khó làm tăng sửa và retry, khiến chi phí/độ trễ khác xa lượt thông thường.
- Tác động ổn định/vận hành: thông thường 4 lời gọi, có lịch sử 5; tối đa đường hiện tại 6/7. Giới hạn kế toán và egress của gateway vẫn còn, nhưng không thay thế ngân sách mỗi lượt.
- Đề xuất thiết kế: mọi dispatch dùng chung tracker cho deadline, số lời gọi, retry và usage token thực tế.
- Kiểm chứng: fake gateway kiểm chặn trước dispatch khi hết từng ngân sách, kể cả hai lời gọi phân loại đồng thời.

### A4-13 [MEDIUM][confirmed] Test kiến trúc chưa thực thi ranh giới miền v2

- Vị trí: [layers.yaml:5](<C:/Users/Duong Vinh/Vinh/tests/architecture/layers.yaml:5>), [test_import_boundaries.py:37](<C:/Users/Duong Vinh/Vinh/tests/architecture/test_import_boundaries.py:37>).
- Bằng chứng: cấu hình chỉ duyệt `domain`, `application`, `presentation`, `infrastructure`; không có luật cho `rag_v2`. AST scan các thư mục miền v2 hiện cho **0 import** vào `agent`, `infrastructure`, `presentation`.
- Tác động tài liệu mới: việc mở rộng xử lý nguồn có thể thêm phụ thuộc bị DESIGN cấm mà CI không bắt.
- Tác động ổn định/vận hành: kiến trúc hiện chưa có vi phạm này, nhưng không có hàng rào hồi quy.
- Đề xuất thiết kế: thêm luật cho từng thư mục miền v2, ngoại lệ adapter rõ ràng và kiểm import tương đối.
- Kiểm chứng: negative test cố ý thêm import bị cấm vào mã trong bộ nhớ; validator phải phát hiện.

### A4-14 [HIGH][confirmed] Mã và kiểm thử v2 chưa có trong snapshot Git tái tạo được

- Vị trí: [service.py:1](<C:/Users/Duong Vinh/Vinh/services/api/src/campus247/rag_v2/service.py:1>), [test_graph_integration.py:1](<C:/Users/Duong Vinh/Vinh/tests/rag_v2/test_graph_integration.py:1>), [rag_v2_build_index.py:1](<C:/Users/Duong Vinh/Vinh/scripts/rag_v2_build_index.py:1>).
- Bằng chứng: `git ls-files` trên lõi, test, runner và builder trả **0 tracked**; `git ls-files --others --exclude-standard` trả **61 tệp**. Các điểm gắn graph/bootstrap/settings và dependency đang là thay đổi có sẵn.
- Tác động tài liệu mới: máy khác không tái tạo được pipeline dựng/nạp nguồn mới từ HEAD.
- Tác động ổn định/vận hành: checkout, CI, triển khai và rollback chỉ dựa trên commit sẽ thiếu thành phần đang chạy.
- Đề xuất thiết kế: đưa dependency/ports/types vào trước; lõi cùng test; integration/contracts; builder, runner và runbook. Kiểm toàn bộ snapshot nhất quán trước phát hành, giữ nguyên mọi thay đổi ngoài phạm vi.
- Kiểm chứng: dựng môi trường từ snapshot Git riêng và chạy kiểm ngoại tuyến. Phiên này chỉ đề xuất, không stage/commit.

## Phần đã kiểm và thấy ổn

- **Ủy quyền:** SQL giữ release seal, review, tenant/audience, hiệu lực và checksum. Thu hồi qua API tăng `policy_generation` tại [platform.py:515](<C:/Users/Duong Vinh/Vinh/services/api/src/campus247/application/knowledge/platform.py:515>); mỗi lượt đối chiếu pointer nên không phải chờ TTL 300 giây.
- **Unit không còn trong DB:** cache lạnh không cấp row; `_binding_failure()` loại unit. Nếu row còn trong cache, bước đọc trực tiếp các chunk được dẫn sẽ chặn kết quả. Không được suy từ đó rằng không còn khe hở A4-02.
- **Hết hiệu lực:** bulk cache kiểm `effective_until` theo thời gian hiện tại mỗi lượt. **Bắt đầu hiệu lực trong cùng epoch:** có thể bị thiếu tới khi entry quá 300 giây, có lượt kích hoạt refresh và refresh hoàn tất; không có SLA cứng nếu refresh lỗi.
- **Release mới:** lượt mới refresh pointer; lượt cũ bị chặn khi epoch đổi. Riêng nguồn mới chỉ xuất hiện trong v2 sau dựng/nạp lại index như A4-04.
- **Đồng thời:** 20 lượt lạnh cùng key dùng đúng một lần đọc bulk. Shield giữ lần đọc chạy tiếp khi lượt đầu hết hạn. Ma trận numpy đặt read-only; Unit/Scope bất biến. Chưa đo tải nhiều process.
- **Các cổng:** v2 thay `evidence_gate` v1 bằng kiểm xác định/ngữ nghĩa riêng; output guard vẫn chạy. Ngoại lệ kỷ luật kiểm nguồn/attestation và các luật khác; các test liên quan đạt.
- **Trích dẫn/web:** mapping lấy metadata từ server, kiểm quote thuộc nguồn; contract test giữ kiểm ID, hash, locator, hiệu lực và hành vi v1. History policy vẫn chặn giá trị liên hệ theo quy tắc hiện hành; không coi đó là lỗi mới.
- **Log thông thường:** `TurnTrace` chỉ phát trường hữu hạn, loại nội dung/PII và giá trị không hữu hạn; hai test trace đạt. Ngoại lệ capture nội dung nằm ở A4-05.

Các đường lỗi đã đối chiếu:

| Đường lỗi | Kết quả người dùng/transport | Nhãn |
|---|---|---|
| Ngoại lệ, 402, timeout trong sinh/kiểm | Thông báo lỗi kết nối và cách thử lại; hoàn tất dạng lỗi hệ thống | Nội bộ `transient_error`, `response_class=system_error` |
| Vector lỗi, lexical rỗng | “Chưa tìm thấy nguồn” | `refuse/no_source` — A4-06 |
| JSON sinh sai | “Chưa xác minh được phát biểu” | `refuse/unverified` — A4-06 |
| Snapshot/authorization lỗi trước node | `message.failed`; PlatformError 503 bị quy thành INTERNAL_ERROR 500 | Không có completed/outcome |
| Bulk cache lạnh vượt 12 giây trong node | Lượt đầu lỗi hệ thống; lần đọc nền tiếp tục | `transient_error` |
| Index thiếu/hỏng hoặc numpy thiếu | Không khởi động ứng dụng v2 | Không có SSE |

`outcome_kind` trong bảng là nhãn nội bộ; payload công khai hiện thiếu trường này như A4-07.

Cấu hình và môi trường:

- Cờ ở [settings.py:40](<C:/Users/Duong Vinh/Vinh/services/api/src/campus247/bootstrap/settings.py:40>): engine mặc định `v1`, parallel classify mặc định tắt, đường dẫn index riêng.
- Venv chính có numpy **2.5.3**; fixture Python **3.12.14** không có numpy khi kiểm bằng `-I`. [restart_rt.ps1:6](<C:/Users/Duong Vinh/Vinh/evals/results/rag-judge-20261028/resume/restart_rt.ps1:6>) dựa vào vendor qua `PYTHONPATH`.
- Mốc lạnh 25–35 giây là bằng chứng đã ghi trong REPORT, không được đo lại ở phiên này; readiness chưa kiểm cache lạnh.
- Lui về v1 bằng đổi cờ và khởi động lại. Không có fallback âm thầm khi v2 lỗi startup.
- Tổng kiểm thử nêu trên: **184 đạt**; hai ca factory cần SQLite không chạy được trong ràng buộc chỉ đọc. Lỗi architecture là import `application/knowledge/applicability.py` → infrastructure đã có trong REPORT, không phải vi phạm miền v2 mới.
- Không thay đổi mã, cấu hình, dữ liệu hoặc trạng thái Git.

## Câu hỏi mở cần chủ dự án quyết định

- SLA cho nguồn bắt đầu hiệu lực trong cùng release: chấp nhận chậm khoảng năm phút cộng refresh, hay yêu cầu xuất hiện ngay?
- Điểm xác định “đã công bố” khi thu hồi là lúc enqueue terminal hay lúc client nhận; lịch sử đã hoàn tất cần hiển thị trạng thái thu hồi thế nào?

## Điều kiện vận hành tối thiểu để bật v2 mặc định

- [ ] Đoạn cha bị từ chối phải chặn mọi fact/unit phụ thuộc; không bỏ điều kiện nguồn.
- [ ] Viết lại bảo toàn mã, năm, đối tượng và phủ định bằng kiểm xác định.
- [ ] Authorization và revalidation dùng cùng phạm vi câu hỏi đã xác minh.
- [ ] Kiểm thu hồi trước dispatch và tại điểm công bố terminal; test race đạt.
- [ ] Manifest khớp release/generation/model; đổi release có quy trình nạp index kiểm được.
- [ ] Readiness kiểm binding v2 và warm-up, không chỉ database.
- [ ] Không lưu câu hỏi/lịch sử/nguồn thô trong debug vận hành.
- [ ] Lỗi hạ tầng không biến thành `no_source`; outcome/reason giữ qua SSE và lịch sử.
- [ ] Facade giữ đủ nhánh truy hồi và metadata thẩm quyền/phạm vi nguồn.
- [ ] Cache có trần tài nguyên; quét CPU không chặn event loop vượt ngân sách.
- [ ] Ngân sách mỗi lượt bao phủ mọi dispatch, retry và token.
- [ ] Fixture có dependency numpy được quản lý, không phụ thuộc sao chép vendor thủ công.
- [ ] Toàn bộ mã/test/builder/runner nằm trong snapshot Git tái tạo được.
- [ ] Bộ kiểm sạch đạt A1–A9 đầu–cuối, gồm nguồn mới, thay thế, thu hồi và tải đồng thời.
- [ ] Diễn tập rollback v1 thành công; giữ v1 mặc định cho tới khi các điều kiện trên đạt.