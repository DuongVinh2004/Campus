# RAG v2 — kiểm định độc lập và kế hoạch hoàn thiện (2026-10-31)

> Trạng thái: **chỉ là kế hoạch, chưa sửa mã.** Theo yêu cầu, đến đây tôi dừng để bạn đọc. Bạn duyệt xong thì mới bắt đầu thực hiện.
> Thư mục: `evals/results/rag-v2-audit-20261031/`. Brief giao Codex nằm ở `briefs/`, báo cáo gốc của Codex ở `out/A1…A5-*.md` (log thô ở `out/*.log`).

---

## 0. Kết luận kiểm định

**RAG v2 hiện chưa đạt "chạy tốt, ổn định, không phải sửa nữa", và chưa sẵn sàng cho tài liệu mới.** Lý do không chỉ là các con số A1–A9 còn trượt (REPORT-v2 §18–§19). Kiểm định lần này tìm ra những lỗi cấu trúc mà các bộ đo trước không bắt được:

1. **Tài liệu mới không tự đến được v2.** Chỉ mục v2 là bộ tệp tĩnh, nạp một lần lúc khởi động. Ủy quyền chỉ xét các chunk có sẵn trong bộ tệp đó. Một tài liệu đã duyệt và phát hành trong DB sẽ không được v2 thấy cho tới khi có người dựng lại chỉ mục và khởi động lại runtime. Hệ thống cũng không cảnh báo: người dùng chỉ nhận "chưa tìm thấy nguồn" (A1-01, A4-04).
2. **Có những đường hiển thị nội dung chưa qua kiểm ngữ nghĩa.** Gồm nhánh dữ kiện bỏ mất điều kiện áp dụng, câu hỏi làm rõ do mô hình tự viết, và ngoại lệ "kỷ luật" nhận nhầm phát biểu về cá nhân (A1-02, A3-01, A3-02, A3-03, A4-01).
3. **Một số luật viết tay theo kho hiện tại sẽ từ chối hoặc hỏi lại nhầm câu hỏi về chủ đề mới** ngay trước khi tra cứu (A2-01).
4. **Bộ đo đang báo đẹp hơn thực tế.** A1 chấp nhận câu sai điều kiện hoặc sai đối tượng. A2 = 0 chỉ có nghĩa "có trích dẫn", chưa chứng minh mọi phát biểu đều có nguồn. Phép thử newdoc tính lỗi hệ thống là "từ chối đúng". Kiểm routing của bộ safety bị bỏ qua ở cả 610/610 ca (A5-01, A5-02, A5-07, A5-10).
5. **Toàn bộ mã v2 chưa nằm trong git** (61 tệp `??`), nên chưa tái tạo hay rollback được bằng commit (A4-14).

Điểm tốt đã xác nhận:
- `tests/rag_v2`: **416/416 đạt** (tôi chạy ngày 2026-10-31, 125 s).
- Ủy quyền SQL giữ release seal, review, hiệu lực và checksum. Không thấy rò canary. Trace thông thường không ghi nội dung.
- Module miền v2 không import ngược `agent/`, `infrastructure/`, `presentation/`.
- Kiến trúc chung (truy xuất lai → sinh ràng buộc theo ID → kiểm xác định + ngữ nghĩa → kết quả có kiểu) là đúng hướng và nên giữ. **Kế hoạch dưới đây không viết lại v2.** Nó thay các luật vá theo kho bằng cơ chế tổng quát và bịt các đường lọt.

Vì sao 416 test đạt mà vẫn có BLOCKER: test hiện có chủ yếu kiểm luồng đúng và các ca từng gặp. Chưa có test biến hình (đổi vị trí điều kiện, đổi cột bảng, đổi mã trong câu viết lại, thu hồi giữa lượt). Mỗi BLOCKER dưới đây sẽ trở thành một test như vậy trước khi sửa.

## 1. Cách kiểm định đã làm

- 5 phiên Codex (`gpt-6.1-sol`, mức high, sandbox **chỉ đọc**, không mạng, không gọi mô hình trả phí), mỗi phiên một lát cắt:
  - A1: nạp tài liệu và vòng đời chỉ mục
  - A2: hiểu câu hỏi và truy xuất
  - A3: sinh, kiểm chứng, kết quả
  - A4: tích hợp, an toàn, vận hành
  - A5: phương pháp đo
- Mỗi phát hiện kèm vị trí mã và probe tái hiện chạy trong bộ nhớ (gateway giả, dữ liệu tổng hợp, kho thật đọc chỉ đọc). Tổng 53 phát hiện thô, gộp trùng còn 38 mục ở §3.
- Tôi tự đối chiếu lại trên mã các phát hiện then chốt:
  - chỉ mục tĩnh và ủy quyền theo ID của chỉ mục (`bootstrap/rag_v2.py:19–35`)
  - nhánh dữ kiện đặt `semantic_required=False` (`service.py:171–195`)
  - `clarify_question` chỉ lọc độ dài, URL và chuỗi số dài (`generation/generate.py:39–42`)
  - viết lại câu hỏi không kiểm bảo toàn mã/số (`generation/rewrite.py:43–49`)
  - `AuthorizedIndex` không có nhánh `anchored`, nên `hybrid.py:124` bỏ qua nhánh neo mã trên runtime
  - `coverage` mặc định 1.0 và không bao giờ được truyền (`outcome/compose.py:33,78`)
  - luật "kỷ luật" theo từ khóa (`discipline.py:44–64`)
  - bộ safety chỉ kiểm route khi phản hồi có trường route (`rag_v2_suite.py:151–153`)
- Bằng chứng là gì: đọc mã cộng probe xác định do Codex và tôi chạy với dữ liệu tổng hợp, đáp án kiểm bằng mã; 0 lời gọi DeepSeek. Các rủi ro "mô hình thật sẽ làm X bao nhiêu lần" **chưa đo** và được ghi là cần đo ở giai đoạn tương ứng.

## 2. Định nghĩa "xong" (để không phải sửa nữa)

"Không còn phải sửa gì nữa" không thể hứa tuyệt đối với một hệ có mô hình ngôn ngữ. Điều làm được là: **khi nạp tài liệu mới thì không phải sửa mã, và mọi suy giảm đều bị cổng tự động bắt trước khi tới người dùng.** v2 được coi là xong khi đạt đủ các điều kiện sau.

| # | Điều kiện | Kiểm bằng |
|---|---|---|
| D1 | Tài liệu mới được phát hành đi tới v2 tự động: dựng snapshot, kiểm, đổi con trỏ nguyên tử. Readiness báo đúng release/generation đang phục vụ. Không cần sửa mã hay khởi động tay. | Test tích hợp D1→D2→thay thế→thu hồi→hết hiệu lực (fake DB/embedding) + một lần diễn tập trên runtime thật |
| D2 | Không còn đường nào hiển thị khẳng định thực tế chưa qua kiểm, kể cả nhánh dữ kiện, câu hỏi làm rõ, ngoại lệ và thông báo. | Test biến hình cho từng đường + bộ chấm A2 mức phát biểu |
| D3 | Không còn luật gắn với nội dung kho trong đường quyết định. Từ vựng, viết tắt, mã và phạm vi lấy từ metadata/kho lúc dựng snapshot. Luật sản phẩm (phạm vi trường) nằm trong cấu hình có phiên bản. | Quét mã (danh sách hằng tiếng Việt trong `rag_v2/` = chỉ còn luật sản phẩm đã khai báo) + bộ câu hỏi chủ đề mới |
| D4 | Bộ đo đúng: A1 chấm theo quan hệ và điều kiện (kèm bộ chấm ngữ nghĩa độc lập), A2 theo phát biểu, campaign có manifest khóa. Probe ngoại tuyến dùng đúng đường runtime. | Mutation test cho bộ chấm, 0 lời gọi |
| D5 | Trên **bộ tài liệu mới** (≥ 7 loại tài liệu, chưa từng có trong kho, câu hỏi do mô hình/prompt khác viết, đi qua đường nạp và phát hành thật), cận tin cậy 95% của A1–A5 đạt ngưỡng SPEC, với **0 dòng mã sửa riêng cho tài liệu**. | Campaign cuối §5-P8 |
| D6 | Ca cũ không suy giảm (so cặp trước/sau trên cùng snapshot). | Campaign cuối |
| D7 | Ổn định: A6 ≥ 95%, A7 < 1% tính cả lượt thử đầu, A8 ≤ 6/12/2 s, chạy ngâm 2–4 giờ ở độ đồng thời 1/2/4/8 không suy giảm. | Campaign ổn định |
| D8 | A9: rò 0, ghi trái phép 0, injection qua **tài liệu** (không chỉ qua câu hỏi) bị chặn, routing được đo thật. | Bộ safety mở rộng |
| D9 | Vận hành: mã nằm trong git, numpy cài chính thức, debug không ghi nội dung, rollback v1 đã diễn tập. | Checklist A4 |

Chỉ khi D1–D9 đạt mới chuyển `CAMPUS247_RAG_ENGINE` sang v2. Nếu một mục không đạt vì giới hạn ngoài mã (nhà cung cấp chậm, phần cứng), sẽ ghi là bị chặn kèm số đo, không tính là đạt.

## 3. Danh mục phát hiện (gộp, xếp theo chủ đề)

Mã gốc trong ngoặc dẫn tới báo cáo Codex ở `out/`. B = BLOCKER, H = HIGH, M = MEDIUM. "✔" = tôi đã đối chiếu trực tiếp trên mã.

### F-A. Đường lọt nội dung chưa kiểm (an toàn nội dung)
| ID | Mức | Phát hiện | Gốc |
|---|---|---|---|
| F-A1 | B ✔ | Nhánh dữ kiện trả dòng giá trị mà bỏ điều kiện đứng trước bảng, trong tiêu đề cột, cách xa hơn 600 ký tự, hoặc diễn đạt khác ("Mức này dành cho…"). Phát biểu không qua kiểm ngữ nghĩa, 0 lời gọi mô hình. | A1-02, A3-01 |
| F-A2 | B | Đoạn cha bị chặn vì injection (hoặc quá dài) bị coi như "không có đoạn cha", nên nhánh dữ kiện vẫn trả lời thiếu điều kiện. | A4-01 |
| F-A3 | B ✔ | `clarify_question` do mô hình viết được hiển thị nguyên văn, có thể chứa tiền đề thực tế sai ("phải nộp 999 hồ sơ…"). | A3-03 |
| F-A4 | B ✔ | Ngoại lệ "kỷ luật" nhận phát biểu về một cá nhân có tên ("Sinh viên Nguyễn Văn An bị kỷ luật", hoặc thêm "khi…"). Luật dựa trên cụm từ và danh sách đại từ. | A3-02 |
| F-A5 | B ✔ | Bước viết lại câu hỏi được phép đổi mã khóa/năm/số của câu mới (K64→K65, 2026-2027→2027-2028); chỉ có prompt yêu cầu giữ nguyên, không có mã kiểm. | A3-08, A4-03 |
| F-A6 | B | Thu hồi nguồn giữa lượt: lời gọi kiểm ngữ nghĩa vẫn gửi nội dung đã thu hồi; còn khe hở trước sự kiện SSE cuối (`citation.added`/`message.completed` vẫn phát). | A4-02 |
| F-A7 | H | Debug capture vẫn ghi câu hỏi, lịch sử và câu viết lại nguyên văn (sửa ở §9 chưa đủ). | A3-10, A4-05 |
| F-A8 | H | Đường v2 làm rơi `applicability_note`, `_verified_publication`, `_verified_curriculum`; thiếu bước `verified_attachment()` như v1. | A4-09 |

### F-B. Vòng đời chỉ mục và tài liệu mới
| ID | Mức | Phát hiện | Gốc |
|---|---|---|---|
| F-B1 | B ✔ | Snapshot v2 không gắn với release/generation. Phát hành mới không kích hoạt dựng lại. Không có so khớp DB↔chỉ mục, readiness không kiểm v2. | A1-01, A4-04 |
| F-B2 | H | Bootstrap chấp nhận snapshot `pending`, sai mô hình hoặc sai chiều vector. Lỗi chiều bị xử lý như sự cố vector có thể dự phòng. | A1-07 |
| F-B3 | H | Khóa embed-cache chỉ là hash văn bản. Đổi revision mô hình nhúng thì dùng lại vector cũ mà manifest ghi revision mới. | A1-05 |
| F-B4 | H | Lỗi 503 làm builder âm thầm cắt văn bản còn 300 ký tự rồi gắn vector vào unit đầy đủ. | A1-06 |
| F-B5 | H | Tách bảng chỉ nhận header qua "STT/mã học phần/chương trình đào tạo". Header lạ, header nhiều tầng, ô gộp hoặc đổi thứ tự cột làm sai quan hệ đối tượng–giá trị–đơn vị (ví dụ fact `subject="700.000"`, `basis` lấy từ hàng thay vì header). | A1-03 |
| F-B6 | M | Cổng coverage 98% ký tự chữ/số chấp nhận mất một từ phủ định hoặc giá trị ngắn. | A1-04 |
| F-B7 | M | `corpus_export.py` cứng đường dẫn và số lượng lịch sử (2515/151/123), nên tài liệu mới hợp lệ bị báo lệch. | A1-08 |
| F-B8 | M | Bộ nhớ/khởi động tuyến tính: ×5 kho ≈ 682 MiB, khởi tạo ≈ 16 s. Thêm một tài liệu phải dựng lại toàn bộ. Batch có cache miss nhúng lại cả batch. | A1 (đo) |

### F-C. Hiểu câu hỏi và truy xuất không tổng quát
| ID | Mức | Phát hiện | Gốc |
|---|---|---|---|
| F-C1 | H | Luật từ khóa chặn trước truy xuất: "thời tiết/tỷ giá/FPT…" gây ngoài phạm vi; câu ngắn bị "không rõ"; câu có "học phí" bị đòi khóa/ngành. Probe 15 câu chủ đề mới: 3 ngoài phạm vi nhầm, 4 hỏi lại. | A2-01 |
| F-C2 | M | Bảng viết tắt thay nghĩa ("TC ISO 17025"→"tín chỉ…", "RL"→"rèn luyện", "DC"→"được"). Kế thừa ngữ cảnh hội thoại dựa vào 10 topic cố định. | A2-02 |
| F-C3 | H | Câu hỏi chỉ giữ một khóa và một ngành, nên câu so sánh K70/K71 hoặc CNTT/ATTT mất một vế ở bộ lọc hybrid (sửa §19 mới mở cổng đầu). | A2-03 |
| F-C4 | H | Phạm vi mở ("áp dụng từ K70", "các khóa tuyển sinh từ 2024", K100, mã chương trình ≥ 72) bị hiểu khác nhau giữa ingest/snapshot/hybrid. Chưa phân biệt `ALL` với `UNKNOWN`. | A2-04, A3-09 |
| F-C5 | H ✔ | Nhánh neo mã mất trên runtime vì `AuthorizedIndex` không chuyển tiếp. Ngưỡng 200 unit còn làm nhánh tự tắt khi kho lớn. Probe ngoại tuyến vì thế đo tốt hơn runtime. | A2-05, A4-10, A5-08 |
| F-C6 | H | Chưa có cơ chế tổng quát chống "một tài liệu dài chiếm hết ứng viên": 24/40 chỗ BM25 cho một tài liệu; thêm 50 unit lặp tiêu đề đẩy nguồn ngắn từ hạng 1 xuống hạng 51; kho ×3 làm gold@40 giảm 428→410/449. | A2-06 |
| F-C7 | H | Chọn phiên bản tài liệu theo `query=None`, nên giữ cả bản cũ lẫn bản thay thế; phạm vi edition không đi vào ngữ cảnh. | A2-07 |
| F-C8 | M | Reranker "tắt" và "lỗi" cho kết quả khác nhau; trạng thái tắt bị ghi là `RRF_TIMEOUT`. | A2-08 |
| F-C9 | M | BM25 cộng điểm theo thứ tự `set`, nên thứ tự đổi theo `PYTHONHASHSEED` (ảnh hưởng A6 giữa các tiến trình). | A2-09 |
| F-C10 | H | Vòng binding và injection đồng bộ trên 9.071 unit chặn event loop 2,4 s mỗi lượt; cache ủy quyền theo phạm vi không có trần. | A2-10, A4-11 |

### F-D. Sinh, kiểm chứng, kết quả
| ID | Mức | Phát hiện | Gốc |
|---|---|---|---|
| F-D1 | B ✔ | Không đo độ phủ từng ý: câu nhiều ý thiếu một ý vẫn là `answer`. `coverage` mặc định 1.0. Đây là nút thắt A1 lặp lại trong REPORT §15–§19. | A3-05 |
| F-D2 | H | Kiểm xác định so **tập số** độc lập, không kiểm quan hệ: đổi USD→EUR, kg→tấn, lấy số hàng khác, La Mã II→IV, "ba"→"năm", bỏ điều kiện đều PASS; `0.125`≡`125`. | A3-06 |
| F-D3 | H | Kiểm xác định chặn nhầm câu đúng: ngày ISO/dấu chấm, phủ định kép, "50 phần trăm"≡"50%", câu hợp hai nguồn K64+K65 (`SCOPE_MISMATCH`). | A3-07 |
| F-D4 | H | Đóng gói ngữ cảnh: 19 KB là tổng; đoạn cha 60 KB bị bỏ nguyên khối mà vẫn `answer`, không ghi chú. Khi không đoạn cha nào vừa thì quay về unit con và vượt trần 28 KB (probe 41 KB). 9–12 nguồn thì kiểm ngữ nghĩa từ chối (>8). | A3-04 |
| F-D5 | M | Prompt mang giả định của kho ("K70_and_earlier", "nguồn không nêu khóa thì áp dụng chung", "KS/KTS"). | A3-09 |
| F-D6 | M | Lần sửa bị timeout bị báo là `unverified` thay vì `transient_error`. | A3-11 |
| F-D7 | H | Lỗi hạ tầng bị báo thành nội dung: vector timeout + lexical rỗng → `no_source`; JSON hỏng → `unverified`; `PlatformError 503` → 500 `INTERNAL_ERROR`. Làm A7 thấp giả. | A4-06 |
| F-D8 | M | `outcome_kind`/lý do không đi tới SSE và lịch sử (SPEC yêu cầu). | A4-07 |
| F-D9 | H | Tái kiểm nguồn dùng câu gốc trong khi truy xuất dùng câu viết lại, nên lượt nối tiếp có phạm vi năm học bị `system_error`. | A4-08 |
| F-D10 | H | Ngân sách lượt (`RunBudget`) không áp vào v2: đặt 1 lời gọi vẫn chạy 7. | A4-12 |

### F-E. Bộ đo và bằng chứng
| ID | Mức | Phát hiện | Gốc |
|---|---|---|---|
| F-E1 | B | A1 nhận câu trả lời đảo phủ định, đổi đối tượng, gắn số sai ngữ cảnh, thêm phát biểu sai; đồng thời chấm sai câu đúng diễn đạt khác ("miễn phí"↔"không thu phí", "1 nghìn"↔"1000"). | A5-01 |
| F-E2 | B | A2 = 0 chỉ là "không có câu trả lời thiếu trích dẫn", chưa chứng minh mọi phát biểu có nguồn. | A5-02 |
| F-E3 | H | Không có manifest campaign: trộn 3 lượt từ build/corpus khác vẫn được tính "đủ ×3"; `compare` không đòi cùng bộ ca. | A5-03 |
| F-E4 | H | Cỡ mẫu: A1 16/360 có CI95 2,75–7,10% (bootstrap theo chủ đề 1,39–8,06%); A3 117/120 có CI 92,9–99,2%. Lặp ×3 không thay được số chủ đề/tài liệu độc lập. | A5-04 |
| F-E5 | H | Holdout chỉ tách theo chunk: holdout6 có 19/21 tài liệu đã xuất hiện ở bộ trước và đã bị dùng để chẩn đoán (§19). Mọi bộ do cùng một mô hình viết. | A5-05 |
| F-E6 | H | Newdoc: một tài liệu, đi đường nạp riêng, gọi thẳng service (bỏ safety/routing/phát hành/ủy quyền). Bộ chấm newdoc tính `transient_error` là từ chối đúng và chấp nhận quote rỗng. | A5-06, A5-07 |
| F-E7 | H | Bộ safety: 0/610 ca có `route_any`; route vắng thì bỏ kiểm, nên con số "routing 237/300" không đo routing. Không có fixture hai người dùng hay kiểm side effect. | A5-10 ✔ |
| F-E8 | H | A7 gộp mọi loại lỗi; `run-suite-e.sh` bỏ lượt lỗi rồi chạy lại, nên đo "thành công sau nhiều lần thử" chứ không phải lượt đầu. | A5-09 |
| F-E9 | H | Ba công cụ chấm cho nhãn khác nhau trên cùng dữ liệu (`gate_compare` báo `full` khi có forbidden fact). `score` không trả exit code thất bại. Bộ gốc chỉ có 15,8% ca không đáp án (SPEC ≥ 20%). `forbidden_facts` rỗng ở mọi holdout. | A5-11 |

### F-F. Vận hành và quản lý mã
| ID | Mức | Phát hiện | Gốc |
|---|---|---|---|
| F-F1 | H ✔ | 61 tệp v2 (lõi, test, runner, builder) chưa được git theo dõi. | A4-14 |
| F-F2 | M | numpy cho venv fixture nằm ở `data/rag_v2_vendor` qua `PYTHONPATH` sao chép tay. | A4 |
| F-F3 | M | Test kiến trúc chưa có luật cho `rag_v2/` (hiện 0 vi phạm, nhưng chưa có hàng rào). | A4-13 |
| F-F4 | M | Khởi động lạnh 25–35 s; readiness không chờ warm-up. | A4 |

### Ngoài lõi v2, nhưng chặn cổng A9 (đã ghi ở REPORT §17.4, cần bạn quyết)
Gồm: nút khẩn cấp "đang bảo trì" (41 ca), kênh bàn giao chưa có consumer (31), lời chào có dấu bị `UNSUPPORTED` (18), yêu cầu ghi trả dạng FAQ (14), che giá trị liên hệ trong `history_presentation` (xung đột kỳ vọng, 24 lượt holdout6). Đây là các nút dùng chung với v1; trước đây bạn dặn không đụng v1.

## 4. Nguyên tắc thiết kế cho mọi sửa đổi

1. **Không thêm luật cho một tài liệu, một cụm từ hay một ca.** Mọi sửa phải có test biến hình chứng minh nó đúng với cấu trúc/văn phong khác. Lỗi cùng nhãn xuất hiện lần hai phải sửa ở tầng thiết kế (SPEC).
2. **Mô hình đề xuất, mã quyết định.** `decision`, câu viết lại, câu hỏi làm rõ đều là đề xuất có kiểu. Máy chủ kiểm rồi mới dùng.
3. **Một kiểu phạm vi chung** `Scope{ALL | UNKNOWN | tập giá trị | khoảng mở/đóng, căn cứ nguồn}` dùng xuyên ingest → snapshot → truy xuất → kiểm chứng → prompt.
4. **Đơn vị nguồn giữ cấu trúc:** mỗi unit có span nguồn; bảng giữ header, hàng, cột và ô gộp; điều kiện/ngoại lệ/chú thích được liên kết với các dòng chúng chi phối.
5. **Đóng an toàn:** thiếu bằng chứng cho bao đóng điều kiện, thiếu verdict hoặc nguồn bị từ chối thì claim liên quan bị chặn. Lỗi hạ tầng phải là `transient_error`, không được thành "không có nguồn".
6. **Probe = runtime:** công cụ đo ngoại tuyến gọi đúng hàm ủy quyền, đóng gói và snapshot của runtime, với cache embedding bất biến. Probe dùng `MemoryIndex` trực tiếp không còn được coi là bằng chứng.
7. **Không sửa theo bộ nghiệm thu.** Chỉ chỉnh mã theo bộ phát triển. Bộ nghiệm thu khóa hash và ghi nhật ký mỗi lần mở.

## 5. Kế hoạch theo giai đoạn

Ký hiệu chi phí: **C** = số phiên Codex, **L** = số lời gọi DeepSeek ước tính. Mọi giai đoạn trước P8 dùng fake provider làm mặc định.

### P0 — Nền móng (làm trước, ngắn)
- **P0.1 Đưa v2 vào git** (F-F1): một nhánh riêng, commit theo lớp: ports/types → lõi + test → điểm gắn graph/bootstrap/settings → builder/runner/runbook. Không đụng thay đổi khác đang dở trong cây làm việc. **Cần bạn cho phép commit** (quy tắc kho).
- **P0.2** Cài numpy chính thức vào venv fixture, bỏ phụ thuộc `PYTHONPATH=data\rag_v2_vendor` (F-F2). Không xóa thư mục vendor nếu bạn chưa cho phép.
- **P0.3** Thêm luật kiến trúc cho `rag_v2/` vào `tests/architecture` (F-F3).
- **P0.4** Khóa bộ đo: tạo thư mục `evals/datasets/rag-v2/acceptance/` (rỗng, sẽ có ở P6) với quy tắc "chỉ mở ở P8". Đánh dấu holdout2–6 là **bộ hồi quy đã mở**.
- Cổng: `tests/rag_v2` + `tests/architecture` xanh; checkout sạch từ nhánh chạy được test. C ≈ 1, L = 0.

### P1 — Bịt đường lọt nội dung (BLOCKER an toàn, 0 lời gọi)
Viết test biến hình trước, rồi sửa.
- **P1.1 Nhánh dữ kiện** (F-A1, F-A2): fact chỉ được trả trực tiếp khi có **bao đóng điều kiện đã chứng minh**: liên kết span tới tiêu đề bảng, header cột, chú thích, đoạn dẫn trước/sau và mọi câu điều kiện trong cùng đơn vị cấu trúc. Đoạn cha bị từ chối (injection hoặc quá dài) thì loại mọi fact phụ thuộc. Không chứng minh được thì đi đường sinh + kiểm ngữ nghĩa. Bỏ việc dò điều kiện bằng danh sách cụm từ và cửa sổ 600 ký tự. Test: điều kiện trước/sau/xa/trong header/chú thích/trang kế, diễn đạt tương đương, injection trong cha.
- **P1.2 Câu hỏi làm rõ** (F-A3): mô hình chỉ trả `missing_slots` (danh mục có kiểu: khóa, năm học, ngành, hệ, văn bản, học kỳ, đối tượng). Máy chủ dựng câu hỏi từ nhãn slot. Không hiển thị văn bản tự do của mô hình.
- **P1.3 Viết lại câu hỏi** (F-A5, F-D9): bước viết lại trả **thao tác có span** (thay đại từ X bằng Y, bổ sung slot Z từ lượt k), không trả câu tự do. Mã kiểm: mọi mã, số, năm, khóa, tên riêng và phủ định của câu mới phải còn nguyên; vi phạm thì dùng câu gốc. Tạo một đối tượng `ResolvedQuestion` (câu gốc, câu đã giải quyết, phạm vi kèm xuất xứ) dùng chung cho ủy quyền, truy xuất, sinh và **tái kiểm nguồn**.
- **P1.4 Ngoại lệ "kỷ luật"** (F-A4): tách thành chính sách chung "phát biểu về cá nhân/thực thể có tên" độc lập với từ khóa. Claim phải ở dạng quy tắc có biến đối tượng; câu nêu sự kiện về người có tên thì bị chặn. Giữ nguyên kiểm nguồn/publication. Đánh giá việc bỏ hẳn `discipline.py` khỏi lõi khi chính sách chung bao phủ được.
- **P1.5 Thu hồi giữa lượt** (F-A6): kiểm epoch quyền nguồn **trước mỗi dispatch** (sinh, sửa, kiểm ngữ nghĩa) và ngay trước khi phát terminal SSE (sau mọi `await` chuẩn bị). Test barrier tại từng ranh giới.
- **P1.6 Debug capture** (F-A7): mặc định chỉ ghi mã, đếm, hash. Chế độ ghi nội dung chỉ bật cho runner tổng hợp, có canary test.
- **P1.7 Metadata thẩm quyền** (F-A8): DTO evidence dùng chung v1/v2, giữ `applicability_note` và attestation; nối `verified_attachment()`.
- Cổng: mọi probe tái hiện ở `out/A1,A3,A4` thành test và đều xanh; `tests/rag_v2` không đỏ mới. C ≈ 3–4 (P1.1+P1.4 · P1.2+P1.3 · P1.5+P1.6+P1.7, tệp rời nhau), L = 0. Sau P1 chạy một **cổng nhanh** (P5.5) ~100 L để chắc không tụt độ phủ.

### P2 — Vòng đời chỉ mục: tài liệu mới tự đến v2 (D1)
- **P2.1 Snapshot gắn release** (F-B1): manifest có `release_id`, `generation`, `policy_generation`, inventory chunk (ID + hash), phiên bản bộ tách, embedding identity (model, revision, chiều, pooling). Bootstrap và readiness so khớp với DB. Lệch thì `/health/ready` báo `rag_v2_snapshot_stale` kèm số chunk thiếu/thừa, và câu trả lời phân biệt "chỉ mục đang cập nhật" với "không có nguồn".
- **P2.2 Dựng theo sự kiện**: worker nhận `knowledge.release.changed`, dựng snapshot mới vào thư mục bất biến `data/rag_v2_index/<release>-<generation>/` (idempotent, tiếp tục được sau lỗi). Snapshot cũ giữ lại để rollback; không xóa.
- **P2.3 Kích hoạt nguyên tử**: nạp snapshot mới ngoài đường yêu cầu, chạy cổng nạp (P2.5), đổi con trỏ phục vụ trong tiến trình (không khởi động lại), warm-up cache ủy quyền trước khi báo ready.
- **P2.4 Embedding đáng tin** (F-B2, F-B3, F-B4): khóa cache = model + revision + cấu hình + hash đầu vào thực; cache khác cấu hình không được dùng lại; không cắt văn bản âm thầm (chia theo token trước, giữ ánh xạ span; quá token hay 503 là lỗi có kiểu). Bootstrap từ chối snapshot `pending`/sai mô hình/sai chiều.
- **P2.5 Cổng chất lượng khi nạp** (F-B5, F-B6): (a) bảo toàn theo span: mọi ký tự nội dung của chunk nằm trong ≥ 1 unit, không chấp nhận mất phủ định hay số; (b) bảng: lược đồ header/hàng/cột/ô gộp xác định được, nếu không thì giữ nguyên khối và không sinh fact; (c) fact có đủ đối tượng–giá trị–đơn vị–phạm vi–điều kiện; (d) **smoke test tự động trên tài liệu mới**: sinh câu hỏi xác định từ cấu trúc (tiêu đề điều, ô bảng) rồi kiểm truy xuất đưa đúng unit vào ngữ cảnh (0 lời gọi sinh); (e) chạy lại cổng ngữ cảnh trên bộ hồi quy cũ để bảo đảm không suy giảm. Không đạt thì không kích hoạt.
- **P2.6 Tách bảng tổng quát** (F-B5): nhận header bằng cấu trúc (dòng đầu khối bảng, dòng không số, độ giống giữa các hàng) thay vì "STT/mã học phần"; header nhiều tầng ghép thành đường dẫn cột; mỗi `table_row` mang header của nó trong ngữ cảnh. Fact học phí lấy cột theo vai trò từ header (không theo vị trí), lấy `basis` từ header.
- **P2.7** `corpus_export.py` nhận thư mục đích và đối chiếu với inventory DB của chính giao dịch, không dùng số cứng (F-B7). Dựng tăng dần theo shard tài liệu, chỉ nhúng phần thay đổi (F-B8).
- Cổng: test tích hợp D1→thêm D2→thay D1→thu hồi→hết hiệu lực trên fake DB/embedding (D2 xuất hiện, nguồn mất hiệu lực biến mất, không sửa mã, không khởi động lại); ma trận khởi động pending/sai mô hình/sai chiều/sai revision bị chặn; một lần diễn tập thật trên runtime 8015 với tài liệu tổng hợp (DB local giữ nguyên, tài liệu thử có thể thu hồi sau). C ≈ 3 (P2.1–P2.3 · P2.4+P2.7 · P2.5+P2.6), L ≈ 0 (nhúng dùng máy chủ local 18081).

### P3 — Hiểu câu hỏi và truy xuất không phụ thuộc kho (D3)
- **P3.1 Bỏ các cổng chặn trước truy xuất** (F-C1): luật ngoài phạm vi theo từ khóa chủ đề và luật "câu ngắn = không rõ" chuyển sang **tra cứu trước, quyết định sau**: nếu truy xuất có nguồn liên quan thì để bước sinh quyết định. Chỉ giữ chặn sớm cho phạm vi sản phẩm khai báo trong cấu hình có phiên bản (trường khác, chủ đề ngoài sản phẩm). Hỏi phạm vi học phí chỉ khi nguồn được truy xuất thực sự có nhiều đáp án khác phạm vi (phát hiện bằng metadata scope của các unit), không phải khi câu có chữ "học phí".
- **P3.2 Từ vựng sinh từ kho** (F-C2, D3): lúc dựng snapshot, sinh danh mục mã (khóa, chương trình, học phần, văn bản), tên ngành↔mã, viết tắt có trong kho kèm dạng đầy đủ. Viết tắt đa nghĩa tạo **thêm phương án truy vấn**, không thay câu gốc. Bảng tay trong `normalize.py` chỉ còn viết tắt chat thuần (ko, dc, sv…) kèm test không đổi nghĩa mã.
- **P3.3 Phạm vi đa trị và kiểu `Scope` chung** (F-C3, F-C4): câu hỏi giữ tập khóa/ngành/năm; hiểu "từ Kxx", "các khóa tuyển sinh từ năm …" (ánh xạ năm↔khóa chỉ khi kho có căn cứ), khóa 3 chữ số, mã chương trình mới; `UNKNOWN` khác `ALL` và được nêu trong câu trả lời ("nguồn không nêu rõ phạm vi áp dụng"). Một test hợp đồng chung cho ingest/snapshot/hybrid/kiểm chứng.
- **P3.4 Nhánh neo mã trong port** (F-C5): thêm `anchored` vào `ports.py` và `AuthorizedIndex`; bỏ ngưỡng 200 cố định, thay bằng độ phân biệt (IDF) tính trên tập được phép. Test tương đương `MemoryIndex`↔`AuthorizedIndex`.
- **P3.5 Đa dạng tài liệu tổng quát** (F-C6): truy xuất hai tầng tài liệu → đoạn. Điểm tiêu đề tài liệu tách khỏi thân (tiêu đề tính một lần cho mỗi tài liệu chứ không lặp ở mọi unit). Ngân sách mỗi tài liệu thích ứng theo độ chênh điểm, giữ được các khoản bổ trợ cùng tài liệu. Lưu ý §18.2: hạn mức cứng 10/tài liệu từng làm hỏng bảng chương trình, nên cổng phải là đầu–cuối, không chỉ trần ngữ cảnh.
- **P3.6 Chọn phiên bản theo câu hỏi** (F-C7): cache tập nguồn có quyền độc lập câu hỏi, rồi áp resolver edition theo `ResolvedQuestion` trước khi xếp hạng; truyền phạm vi edition vào ngữ cảnh kiểm chứng. Mâu thuẫn giữa hai nguồn cùng hiệu lực thì `clarify`/nêu cả hai, không chọn ngẫu nhiên.
- **P3.7 Xác định và hiệu năng** (F-C8, F-C9, F-C10): BM25 duyệt feature theo thứ tự cố định, hòa điểm theo luật số học rồi mới tới `unit_id`; reranker có 3 trạng thái `DISABLED/OK/FAILED`, fallback dùng danh sách fusion gốc. Tiền tính binding/injection theo checksum snapshot (không quét 9.071 unit mỗi lượt); phần CPU còn lại chạy executor; cache ủy quyền có trần entry/byte.
- Cổng (0 lời gọi sinh): (a) bộ câu hỏi chủ đề mới/viết tắt đa nghĩa/chuyển chủ đề/so sánh nhiều phạm vi/mã mới/văn bản thay thế; (b) cổng recall theo `AuthorizedIndex` (P5.4) trên dev ×1 và kho nhân ×3 với tiêu đề lặp: gold@12 không giảm, tài liệu ≤ 30 unit không mất; (c) độ trễ event loop < 50 ms mỗi lượt cho phần CPU; (d) chạy `PYTHONHASHSEED` 1..8 cho cùng thứ hạng. Rồi cổng nhanh ~100–150 L. C ≈ 3–4 (P3.1+P3.2 · P3.3+P3.6 · P3.4+P3.5 · P3.7).

### P4 — Sinh và kiểm chứng ổn định trên văn phong mới
- **P4.1 Ý hỏi có kiểu và độ phủ** (F-D1, nút thắt A1): tách câu hỏi thành facet (ID, đối tượng, thuộc tính được hỏi, phạm vi). Lời gọi sinh trả claim gắn `facet_id` + `unit_ids`. Máy chủ tính `answer` chỉ khi mọi facet bắt buộc có ≥ 1 claim đã qua kiểm; facet thiếu thì `partial` liệt kê ý chưa có căn cứ; danh sách trong nguồn (đếm mục từ cấu trúc unit) phải đủ mục khi câu hỏi là "gồm những gì". Việc tách facet do lời gọi sinh đề xuất và mã kiểm (không thêm lời gọi). REPORT §15 từng thử trường `asked` không có lợi; khác biệt lần này là độ phủ được **mã tính và quyết định kết quả**, không chỉ là gợi ý cho mô hình.
- **P4.2 Kiểm xác định theo quan hệ** (F-D2, F-D3): bộ trích giá trị có kiểu (số, tiền tệ, đơn vị khối lượng/thời gian, phần trăm, ngày ở mọi dạng gồm ISO/dấu chấm/"ngày … tháng … năm …", số La Mã, số viết bằng chữ). Claim được so theo bộ (đối tượng–thuộc tính–giá trị–đơn vị) với **cùng hàng/câu nguồn**, không so tập số rời. Phủ định/ngoại lệ theo mệnh đề. `SCOPE_MISMATCH` xét theo từng claim con–nguồn. Chính sách quy đổi tương đương (1 kg = 1000 g?) cần bạn chốt (§7).
- **P4.3 Bộ đóng gói dùng chung** (F-D4): ngân sách theo **byte payload thực sau serialize** của từng lời gọi (sinh, sửa, ngữ nghĩa); trần nguồn thống nhất (≤ 8). Đoạn cha lớn được cắt theo cấu trúc (hàng + header + chú thích + điều kiện liên quan), không bỏ nguyên khối. Phần bị loại được ghi lại; claim cần phần đó bị chặn, kết quả là `partial` có ghi chú.
- **P4.4 Prompt trung tính** (F-D5): bỏ ví dụ "K70_and_earlier", "KS/KTS"; phạm vi đi qua trường có kiểu (`scope: ALL|UNKNOWN|…`).
- **P4.5 Máy trạng thái lượt** (F-D6, F-D7, F-D10): mỗi attempt có trạng thái `ok/unsupported/malformed/timeout/provider_error`; kết thúc vòng không dùng lại verdict cũ. Truy xuất báo "rỗng thật" khác "lỗi nhánh". Mọi dispatch đi qua `RunBudget` chung (deadline, số lời gọi, token).
- **P4.6 Hợp đồng kết quả** (F-D8): `outcome_kind` + `reason` đi qua DTO cuối, persistence, GET lịch sử, SSE (tương thích ngược); contract test round-trip.
- Cổng: bộ 20 cặp nguồn–phát biểu của A3 + bộ biến hình mở rộng (≥ 150 cặp, sinh tự động bằng phép đổi đơn vị/hàng/phủ định/ngày) đều đúng nhãn; phát lại đầu ra sinh đã lưu (`runs/ver_why.py`) cho thấy loại nhầm do phủ định không tăng. Sau đó dev gate 197 ca ×1 (~600–800 L): đủ ý ≥ mốc §19 (89/116), thiếu ý ≤ 5, không đáp án bị trả lời nhầm không tăng. C ≈ 3 (P4.1 · P4.2 · P4.3+P4.4+P4.5+P4.6).

### P5 — Sửa bộ đo (làm song song P1–P2, 0 lời gọi)
- **P5.1 Thư viện chấm chung** `evals/runners/rag_v2_scoring.py` dùng cho eval/newdoc/gate_compare (F-E9). Tách lệnh `score` và `gate` (exit code ≠ 0 khi trượt). Kiểm phân bố bộ ca (≥ 20% không đáp án, đủ biến thể/nhóm).
- **P5.2 A1/A2 đúng nghĩa** (F-E1, F-E2): gold có cấu trúc (đối tượng–quan hệ–giá trị–đơn vị–điều kiện–ngoại lệ) + `forbidden_facts` cho mọi ca có đáp án (sinh từ hàng/khoản lân cận dễ nhầm). Bộ chấm ngữ nghĩa **độc lập** (mô hình khác bộ sinh; đề xuất dùng Codex/ChatGPT local qua `codex exec`, không tốn DeepSeek) chấm từng phát biểu: được nguồn hỗ trợ / sai / thừa. Hiệu chỉnh bằng mutation set (đảo phủ định, đổi đối tượng, đổi hàng, thêm phát biểu sai, diễn đạt tương đương), yêu cầu ≥ 95% đúng nhãn trên mutation set trước khi dùng.
- **P5.3 Manifest campaign** (F-E3, F-E8): hash mã, snapshot/release, cấu hình, prompt, model, nhiệt độ, bộ ca; `score` từ chối dữ liệu trộn. Journal giữ mọi attempt; báo **lượt đầu** và **sau thử lại** riêng; lỗi phân loại theo pha (trace + request ID).
- **P5.4 Probe dùng đường runtime** (F-C5, A5-08): context/retrieval probe gọi `AuthorizedIndex` + bộ đóng gói thật trên snapshot với cache embedding câu hỏi bất biến (một lần nhúng, sau đó 0 HTTP). Kiểm: context hash của probe = của runtime trên cùng câu hỏi.
- **P5.5 Cổng nhanh chuẩn** (~100 L): 25 ca cũ phân tầng + 25 ca tài liệu mới dev, ×1, ngưỡng: 0 lỗi mã, 0 claim sai (chấm độc lập), không đáp án trả lời nhầm 0, đủ ý không kém mốc. Dùng sau mỗi giai đoạn.
- **P5.6 Newdoc và safety** (F-E6, F-E7): newdoc dùng thư viện chấm chung, `transient_error` là lỗi, quote rỗng/ngắn bị loại. Phản hồi API trả route trong trace kiểm thử (chỉ khi bật chế độ eval). Route vắng = "chưa đo". Thêm fixture hai người dùng + kiểm side effect qua audit log; thêm injection **trong tài liệu nạp**.
- **P5.7 Thống kê** (F-E4): báo CI95 bootstrap theo tài liệu/chủ đề cho A1/A3/A5; tính cỡ mẫu cần cho mỗi ngưỡng; quy tắc dừng chốt trước.
- Cổng: mutation test của bộ chấm xanh; tái chấm holdout6 bằng thư viện mới cho cùng số (hoặc giải thích từng chênh). C ≈ 2–3.

### P6 — Bộ tài liệu mới và bộ nghiệm thu (chuẩn bị song song từ đầu, không ai mở)
- **P6.1 Tài liệu**: ≥ 35 tài liệu chưa có trong kho, 7 loại × 5:
  1. quy phạm nhiều chương/điều/khoản
  2. bảng lớn hoặc nhiều trang (≥ 100 hàng, header nhiều tầng)
  3. thông báo ngắn có hạn và mốc
  4. văn bản **thay thế** bản cũ (có cả bản cũ, quan hệ REPLACES, hiệu lực chồng lấn)
  5. văn bản có phạm vi khóa/ngành, gồm phạm vi mở ("từ K70")
  6. PDF scan/OCR kém
  7. song ngữ Anh–Việt
  
  **Nguồn tài liệu cần bạn quyết** (§7): tốt nhất là tài liệu HUCE công khai thật chưa có trong kho; nếu chỉ dùng tài liệu tổng hợp thì kết luận chỉ là "ổn định trên tài liệu tổng hợp". Tài liệu tổng hợp do Codex viết **khác văn phong kho** (không theo T16) và được kiểm bằng mã.
- **P6.2 Câu hỏi**: do phiên Codex khác (`gpt-6.1-terra`, prompt khác, không xem mã/kết quả) viết. Mỗi tài liệu 12–15 câu có đáp án (≥ 40% nhiều ý, ≥ 25% có điều kiện/ngoại lệ, câu so sánh nhiều phạm vi, câu hỏi bản cũ/bản mới) + 4–5 câu không đáp án (gần miền vắng, giả định sai, mơ hồ, ngoài phạm vi) × 4 biến thể. Gold có cấu trúc (P5.2), `forbidden_facts`, kiểm bằng mã.
- **P6.3 Chia**: theo **tài liệu**: 40% tài liệu cho dev (được chỉnh mã), 60% tài liệu cho nghiệm thu (khóa hash, không mở tới P8). Thêm bộ cũ cố định 200 chủ đề từ kho hiện tại (lấy từ holdout chưa dùng để chẩn đoán sâu + ca mới) để đo "không suy giảm".
- **P6.4 Nạp thật**: tài liệu nghiệm thu đi qua đường intake → parse/OCR → review → phát hành → P2 tự dựng snapshot. Nạp vào DB local với namespace/tenant thử để có thể thu hồi; không ghi đè dữ liệu hiện có (cần bạn xác nhận cách nạp, §7).
- C ≈ 3–4 (tài liệu · câu hỏi · kiểm), L = 0.

### P7 — Ổn định và hiệu năng (D7)
- Đếm lời gọi mô hình mỗi lượt (hiện 4–7): song song hóa phân loại (đã có cờ), gộp viết lại vào phân loại khi có lịch sử, bỏ kiểm ngữ nghĩa khi mọi claim là trích nguyên văn đã có bao đóng điều kiện (chỉ khi P1.1 chứng minh được). Mục tiêu trung vị ≤ 6 s.
- Readiness chờ warm-up. Đo cold/warm riêng.
- Chiến dịch ổn định: cùng 50 ca ×10 ở nhiệt độ 0; độ đồng thời 1/2/4/8; ngâm 2–4 giờ ≥ 1.000 lượt; theo dõi RSS, p95, lỗi lượt đầu, độ trễ event loop.
- Cổng: A6 ≥ 95% (loại kết quả, và nội dung claim ổn định ≥ 90%), A7 < 1% lượt đầu, A8 ≤ 6/12/2 s; nếu A8 trượt chỉ vì độ trễ nhà cung cấp thì ghi "bị chặn bởi nhà cung cấp" kèm số đo tách pha. L ≈ 3.000–5.000.

### P8 — Đo cuối, diễn tập và quyết định cờ
1. Khóa manifest campaign. Bộ nghiệm thu tài liệu mới + bộ cũ cố định, v2 ×3, v1 ×1.
2. A9: bộ safety 610 ca + phần mở rộng (injection qua tài liệu, hai người dùng, side effect), v2 và v1.
3. Chấm bằng thư viện P5; CI95 theo tài liệu/chủ đề; so cặp không suy giảm.
4. Diễn tập: nạp thêm 1 tài liệu → tự phục vụ; thu hồi → biến mất; rollback v1 bằng cờ.
5. Chuyển cờ sang v2 chỉ khi D1–D9 đạt. Nếu không đạt thì ghi tiêu chí chặn, giữ v1 và quay lại giai đoạn tương ứng (sửa ở tầng thiết kế).
- L: phụ thuộc cỡ mẫu (§6).

### Thứ tự và song song
```
P0 ─┬─ P1 (an toàn nội dung) ──┐
    ├─ P2 (vòng đời chỉ mục) ──┼─ P3 (hiểu+truy xuất) ─ P4 (sinh+kiểm chứng) ─ P7 ─ P8
    ├─ P5 (bộ đo) ─────────────┘
    └─ P6 (tài liệu mới, khóa kín) ─────────────────────────────────────────────┘
```
P1, P2, P5, P6 chạy song song được vì tệp ghi rời nhau (P1: `generation/`, `discipline.py`, `agent/nodes/rag_v2.py`; P2: `adapters/`, `scripts/`, `ingest/`, `bootstrap/`; P5: `evals/runners/`; P6: `evals/datasets/`). P3 và P4 đụng `service.py`/`understanding/`/`verification/` nên chạy tuần tự. Sau mỗi giai đoạn: `tests/rag_v2` + cổng nhanh + cập nhật `REPORT-v2.md`.

## 6. Cách dùng Codex để tiết kiệm quota, và ngân sách

**Phân vai.** Codex (`codex exec`, mỗi nhiệm vụ một phiên, tệp ghi rời nhau) làm phần nặng: viết test biến hình, hiện thực, sinh bộ dữ liệu, chạy cổng ngoại tuyến, chấm ngữ nghĩa độc lập. Claude chỉ: viết brief, đọc diff, chạy lại test/cổng để xác nhận, quyết định giữ/gỡ, cập nhật báo cáo.

| Loại việc | Lệnh | Ghi chú |
|---|---|---|
| Hiện thực lõi (P1–P4, P2) | `codex exec -m gpt-6.1-sol -c model_reasoning_effort="high" -s workspace-write` | brief theo mẫu `briefs/A0-common.md`: phạm vi tệp, test phải viết trước, cổng, cấm commit/xóa |
| Sinh dữ liệu (P6) | `-m gpt-6.1-terra -c model_reasoning_effort="medium" -s workspace-write` | mô hình khác người viết các bộ cũ |
| Rà soát đối kháng sau mỗi giai đoạn | `-s read-only` | như 5 phiên lần này |
| Chấm ngữ nghĩa độc lập (P5.2) | `-s read-only --output-schema` | không tốn DeepSeek; tốn quota ChatGPT |

Ước tính: **25–32 phiên Codex** tổng (P0 1 · P1 4 · P2 3 · P3 4 · P4 3 · P5 3 · P6 4 · rà soát 5 · chấm 2–4).

**DeepSeek (ước tính, chỉ ở các cổng):**

| Giai đoạn | Lời gọi |
|---|---|
| Cổng nhanh sau P1/P2/P3/P4 | 4 × ~100–150 ≈ 500 |
| Dev gate P3/P4 | 2 × ~700 ≈ 1.400 |
| P7 ổn định | 3.000–5.000 |
| P8 nghiệm thu | xem bên dưới |

P8 có hai mức:

| Mức | Cỡ mẫu | Lời gọi | Kết luận được phép |
|---|---|---|---|
| **Đầy đủ** (A5 đề xuất) | 200 chủ đề có đáp án + 200 âm tính cho tài liệu mới, cộng 200+200 bộ cũ; ×4 biến thể; v2 ×3, v1 ×1 | 14.000–28.000 | "đạt ngưỡng 2%/98% với CI95" |
| **Rút gọn** | 21 tài liệu nghiệm thu × ~13 = ~270 chủ đề có đáp án + ~100 âm tính; 2 biến thể; v2 ×3, v1 ×1 | ~6.000–9.000 | "đạt hoặc chưa đạt điểm, CI rộng hơn"; không đủ để khẳng định cận trên A1 ≤ 2% |

Lưu ý thống kê: để cận trên CI95 của A1 ≤ 2% cần khoảng 190 chủ đề độc lập với **0 lỗi**, hoặc khoảng 1.000 nếu tỷ lệ lỗi thật khoảng 1%. Lặp ×3 không thay được số chủ đề.

## 7. Cần bạn quyết định trước hoặc trong khi làm

1. **Cho phép commit** v2 vào một nhánh riêng (P0.1). Nếu không, mọi giai đoạn vẫn làm được nhưng không có mốc rollback bằng git.
2. **Nguồn tài liệu mới** (P6.1): (a) bạn cung cấp tài liệu HUCE công khai thật chưa có trong kho (càng nhiều loại càng tốt, tối thiểu 21 tài liệu cho phần nghiệm thu); hoặc (b) chỉ dùng tài liệu tổng hợp, và kết luận cuối bị giới hạn tương ứng. Có thể kết hợp a + b.
3. **Cách nạp tài liệu thử vào DB local** (P2/P6.4): nạp vào tenant/namespace thử trên DB 5433 (thu hồi được, không xóa dữ liệu cũ), hay dùng DB tạm sao chép?
4. **Ngân sách DeepSeek** cho P8: mức đầy đủ hay mức rút gọn.
5. **Nút dùng chung chặn A9** (khẩn cấp, bàn giao, lời chào, yêu cầu ghi, che liên hệ): cho phép sửa các nút này (đụng đường v1), hay giữ nguyên và chấp nhận A9 toàn hệ thống chưa đạt, chỉ báo phần của v2?
6. **Chính sách sản phẩm:**
   - Phạm vi `UNKNOWN`: nêu rõ "nguồn không ghi phạm vi" rồi vẫn trả lời (đề xuất), hay hỏi lại?
   - Có chấp nhận quy đổi tương đương (1 kg = 1000 g, "năm mươi phần trăm" = 50%, ngày ISO) trong câu trả lời không?
   - Khi chỉ trả lời được một phần: `partial` kèm danh sách ý thiếu (đề xuất)?
   - Phạm vi sản phẩm cho nghiên cứu khoa học, phòng thí nghiệm, dịch vụ mới (để cấu hình ngoài phạm vi có phiên bản).
   - Thời gian chấp nhận được từ lúc phát hành đến lúc v2 phục vụ tài liệu (đề xuất: ≤ 15 phút, trong lúc chờ báo "đang cập nhật").
7. **Xóa mã chết sau khi thay thế** (ví dụ `discipline.py` nếu chính sách chung bao phủ, luật tay trong `analyze.py`): mỗi lần xóa tôi sẽ hỏi riêng.

Những mục không phụ thuộc các quyết định trên (P1, P2.1–P2.5 trên fake, P3, P4, P5, phần tài liệu tổng hợp của P6) có thể bắt đầu ngay khi bạn duyệt kế hoạch.

## 8. Rủi ro còn lại và điều không hứa
- Không hứa tuyệt đối "không bao giờ phải sửa". Kế hoạch hướng tới: tài liệu mới không cần sửa mã, mọi suy giảm bị cổng bắt trước khi tới người dùng, và lỗi thiết kế lặp lại được sửa ở tầng thiết kế.
- P4.1 (độ phủ ý) là thay đổi lớn nhất và có rủi ro: nó có thể làm tăng `partial`. Nó được đo bằng dev gate trước khi giữ, như các lần thử trước (§15, §18.2).
- Độ trễ có thể bị chặn bởi nhà cung cấp (đã thấy mạng công ty chặn DeepSeek, HTTP 402). Khi đó ghi là bị chặn, không tính đạt.
- Bằng chứng cuối vẫn là ca do mô hình viết, đáp án kiểm bằng mã. Trải nghiệm của người dùng thật chưa đo và sẽ được ghi như vậy trong báo cáo cuối.
