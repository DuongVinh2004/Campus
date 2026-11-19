# Rubric phát triển giấy xác nhận sinh viên

48 ca trong `datasets/certificate-development-20261013.json` là tập phát triển.
Các ca có thể dùng sửa lỗi về sau nên không là tập đánh giá cuối độc lập.
Không nhập answer concepts vào FAQ, metadata hoặc generation prompt.

| Tiêu chí | Cách chấm |
|---|---|
| Nguồn cần thiết | Mỗi source_ref phải tìm thấy parent đúng trang, phiên bản và canonical URI; báo all-required coverage, không gọi Recall@10 |
| Độ đúng | 0: sai/khẳng định không có căn cứ; 1: đúng một phần/có phần chưa chắc; 2: mọi kết luận được nguồn hỗ trợ, giữ chủ thể/phạm vi/điều kiện |
| Đầy đủ | 0: bỏ ý quyết định; 1: thiếu ý phụ; 2: đủ required_concepts liên quan câu hỏi |
| Citation support | Kiểm từng claim so toàn văn và ảnh nguồn; 0 không hỗ trợ, 1 hỗ trợ một phần, 2 hỗ trợ đủ. Hash/source readback là provenance riêng |
| Thiếu bằng chứng | Đối chiếu expected_behavior. Không có phí/SLA/biểu mẫu mới trong snapshot: không bịa. Không lấy điều kiện nghỉ học tạm thời sang giấy xác nhận |
| Hội thoại | Với followup, kiểm antecedent từ history, không giữ chủ đề cũ sau đổi chủ đề. Retrieval standalone không tự chứng minh hội thoại |
| Hành động | Mong muốn chung chỉ chuẩn bị/hỏi thêm; draft → preview → explicit confirmation; thành công phải có mã và readback từ backend |
| Chi phí/latency | Report elapsed toàn turn, calls, charged token và reservation USD; không gọi là invoice. Phân biệt failure/skipped/untested |

Đọc trang 35 và mục 2 trang 39 bản PDF gốc. Snapshot corpus cũ ghép cặp trang,
trong khi RAG dùng `handbook-human-reviewed.json`, bỏ nhãn Trang và che contact.
Hash raw corpus và canonical model excerpt không đồng nhất. Gold cần mapping
provenance độc lập, kiểm đúng page 35 và 39; không sửa nội dung nguồn hay đáp án
để hợp kết quả. Giữ report matcher sai nếu có và ghi rõ metric đó không hợp lệ.

Chỉ tổng hợp correctness/completeness cho đầu ra đã được người đánh giá đọc.
Failure không được tính là trả lời đúng; báo riêng abstention đúng/quá mức và
citation mở được nhưng không hỗ trợ. Không suy ra chất lượng mọi câu hỏi từ
keyword match, hash match hoặc deterministic tests.

Tập cuối: người đánh giá khác soạn câu và nguồn/phiên bản riêng, đóng băng hash
trước tuning. Gom paraphrase, followup và cùng source family vào một split.
Giữ đáp án ngoài pipeline phát triển, ghi mọi contamination. Đánh giá cuối có
ca chưa gặp và review claim độc lập; không đổi tên bộ phát triển thành held-out.

Runner: `scripts/evaluate_certificate_rag.py retrieval|generation --output <file-mới>`.
Retrieval dùng index/caps hiện có, không gọi paid gateway. Generation đi qua
API 8002 tới writer RAG 8000 hiện có; tối đa 18 call bổ sung trong một lượt runner
và vẫn chịu cap 3 USD / 8500 calls đã có. Không tự reset cap hoặc khởi tạo writer.
