# Kế hoạch hoàn thiện RAG theo mọi tiêu chí (2026-10-28)

Nguyên tắc: không đổi ngưỡng gate hay kỳ vọng để cho qua; gate thiếu bằng chứng giữ `not_verified`; mỗi thay đổi đo trước/sau trên cùng bộ ca; không commit khi chưa được bảo; không gọi dịch vụ trả phí ngoài runtime đã được cho phép.

Cách đọc: mỗi luồng ghi **Tiêu chí**, **Hiện trạng** (biết / chưa biết), **Việc**, **Bằng chứng xong**.

## Luồng A. Kho tri thức (độ phủ, độ mới, trích xuất)
- Tiêu chí: đoạn đúng tồn tại cho câu hỏi sinh viên hay hỏi; văn bản đúng hiệu lực và phiên bản; bảng/PDF trích xuất đúng.
- Hiện trạng: chưa kiểm độ phủ; đã thấy nhãn nội bộ lộ ra tên nguồn và trích dẫn bị cắt 500 ký tự.
- Việc: kiểm kê văn bản, phiên bản, ngày hiệu lực, số đoạn; lập danh sách chủ đề sinh viên hay hỏi và đối chiếu có/không có đoạn trả lời; kiểm mẫu trích xuất bảng; sửa tên nguồn hiển thị; kiểm lô tái nạp.
- Bằng chứng xong: bảng chủ đề × có/thiếu/lỗi trích xuất, danh sách thiếu để người dùng bổ sung nguồn.

## Luồng B. Hiểu câu hỏi
- Tiêu chí: không dấu, viết tắt, lóng, năm học viết tắt, sai chính tả vẫn được hiểu.
- Việc: từ điển chuẩn hóa xác định cho truy xuất (giữ câu gốc để hiển thị); nhận diện năm "26-27"; sau cùng mới xét viết lại bằng LLM với bộ kiểm xác định (không thêm số, mã môn, tên văn bản).
- Bằng chứng: nhóm `typo_slang`, `without_diacritics`, `vague` trong bộ ca tăng, ca "phải từ chối" không bị trả lời bậy.

## Luồng C. Truy xuất
- Tiêu chí: đoạn đúng nằm trong ứng viên và sau rerank, không phụ thuộc cụm "Theo QĐ/Quy chế <số>".
- Việc: log `_search` (ứng viên mỗi nhánh, điểm rerank, văn bản bị lọc); đoán tập văn bản từ chủ đề; thử tăng ứng viên (hiện 20/nhánh) và RRF; kiểm lọc hiệu lực/phiên bản; không hạ ngưỡng rerank để lấy câu trả lời.
- Bằng chứng: bảng nguyên nhân rơi theo ca, recall@k trước/sau trên bộ ca có gold đoạn.

## Luồng D. Sinh câu trả lời và trích dẫn
- Tiêu chí: đúng, đủ, bám nguồn, trích dẫn kiểm được, trình bày dễ đọc.
- Hiện trạng: mẫu 40 câu, 28 trả lời, mình chấm 8 trượt. Lỗi: thiếu Có/Không cho câu tiên quyết, bản sao thô, claim không kiểm được do trích dẫn cắt.
- Việc: sửa mẫu trả lời Có/Không; chống sao chép thô; nâng giới hạn trích dẫn lưu kiểm nếu là nguyên nhân; điều tra vì sao bộ kiểm nguồn chặn b08 (không nới kiểm nguồn).
- Bằng chứng: chấm lại cùng mẫu + mẫu mới, kiểm xác định bằng `knowledge_claims`.

## Luồng E. Từ chối, hỏi lại, abstention
- Tiêu chí: từ chối đúng lúc, nêu đúng lý do, hỏi lại có gợi ý.
- Việc: tách thông báo (thiếu tài liệu / quá mơ hồ / bị kiểm nguồn chặn); hỏi lại kèm 2-3 lựa chọn; ca abstention đủ định mức 100.
- Bằng chứng: bộ ca abstention, đo từ chối nhầm và trả lời nhầm.

## Luồng F. An toàn, bảo mật, quyền riêng tư
- Tiêu chí: false positive thấp (SAFE-ORDINARY-FP ≤ 8%), không bỏ sót ca nguy cơ thật, chống prompt injection, không rò dữ liệu, phân quyền đúng.
- Hiện trạng: đã sửa false positive `financial_impact` cho câu hạn nộp có ràng buộc; chưa đo tỷ lệ trên bộ ca.
- Việc: bộ ca safety 100 + injection 100; rà các luật HIGH khác tìm false positive tương tự (`academic_rights_impact`, `disciplinary_or_legal`…); red-team cơ bản; kiểm đầu ra không lộ bí mật/prompt; kiểm quyền với dữ liệu cá nhân.
- Bằng chứng: tỷ lệ false positive/negative đo được, test xanh/đỏ.

## Luồng G. Routing và hành động ghi
- Tiêu chí: 300 ca routing đúng; hành động ghi giữ xác thực, xem trước, xác nhận, idempotency, audit.
- Hiện trạng: ca "Lịch học ngày mai có những môn nào?" đang đỏ (cần bạn chọn sửa mã hay đổi kỳ vọng).
- Việc: lấp định mức routing và tool (150); kiểm đường ghi.

## Luồng H. Hội thoại nhiều lượt
- Tiêu chí: câu nối tiếp ("còn K65 thì sao?") được giải đúng ngữ cảnh.
- Việc: 50 ca multi-turn; viết lại theo lịch sử; kiểm không rò ngữ cảnh giữa người dùng.

## Luồng I. Hiệu năng, chi phí, độ tin cậy
- Tiêu chí: độ trễ p50/p95, chi phí mỗi lượt, hành vi khi model/DB chậm hoặc lỗi, giới hạn đồng thời.
- Việc: đo từ log runtime; thử timeout và fallback; ghi chi phí gọi nhà cung cấp.
- Bằng chứng: số đo có ngày giờ, không suy đoán.

## Luồng J. Trải nghiệm giao diện
- Tiêu chí: trích dẫn, từ chối, hỏi lại dễ hiểu; truy cập được.
- Việc: kiểm trên trình duyệt các trạng thái; test vitest/Playwright liên quan.

## Luồng K. Đánh giá và gate
- Tiêu chí: bộ ca đủ định mức (500 RAG, 150 tool, 100 safety, 100 injection, 100 abstention, 50 multi-turn, 300 routing) và các nhóm con bắt buộc.
- Hiện trạng: ca RAG tổng hợp (491 câu khác nhau), thiếu nhóm `typo_slang`/`without_diacritics`, mọi gate `not_verified`. Người dùng đã bỏ bước chấm người; mình chấm.
- Việc: dựng ca còn thiếu có gold lấy từ nguồn; chấm; ghi kết quả theo schema chỉ khi đủ trường thật; ghi rõ giới hạn của người chấm là mô hình.
- Bằng chứng: bảng yêu cầu ↔ kết quả ↔ chứng cứ, tách xong / chờ người dùng / bị chặn.

## Luồng L. Vận hành và vòng phản hồi
- Việc: log truy vấn/đoạn/câu trả lời (không dữ liệu nhạy cảm); thu phản hồi người dùng; quy trình tái nạp và phát hiện văn bản lỗi thời; cảnh báo khi tỷ lệ từ chối tăng.

## Luồng M. Nợ kỹ thuật
- Vi phạm kiến trúc cũ ở `applicability.py` (qua `ports`); 41 test Postgres skip thiếu biên nhận rehearsal.

## Thứ tự
1. Đo và kiểm kê (A, C log, K bộ ca biến thể, phân loại nguyên nhân trượt trên 50-100 câu đa dạng).
2. Sửa theo nhóm nguyên nhân chiếm nhiều nhất: B, C, D, E.
3. F, G, H, I (đo và lấp định mức).
4. J, L, M.
5. K: ghi kết quả, áp gate, báo cáo.

## Giới hạn nói trước
- Dữ liệu là dữ liệu trường đã nạp/tổng hợp, chưa có kết nối HUCE thật; chưa có câu hỏi thật của sinh viên. Kết quả tốt trên bộ ca không chứng minh dùng được thật.
- Người chấm là mô hình, không phải người; không thay cho nghiệm thu của người dùng.
- "Hoàn thiện nhất có thể" chỉ tuyên bố được cho gate nào có bằng chứng; phần còn lại giữ `not_verified`.

## Kết quả kiểm kê luồng A (2026-10-28, chỉ đọc DB local, giao dịch readonly)

Số liệu từ `knowledge_source`, `document_version`, `knowledge_chunk` của runtime local. Chưa đối chiếu với câu hỏi sinh viên thật.

| Mục | Giá trị |
|---|---|
| Nguồn | 176 (125 APPROVED, 51 DRAFT), tất cả `OFFICIAL_DOCUMENT`, phạm vi HUCE |
| Phiên bản | 394 (151 PUBLISHED, 240 DRAFT, 3 ARCHIVED) |
| Có thể phục vụ người dùng (PUBLISHED + nguồn APPROVED + đã duyệt áp dụng) | 151 phiên bản, 123 nguồn, 2515 trong 6095 đoạn |
| Độ dài đoạn (toàn bộ) | trung vị ~2400 ký tự, p95 ~4800, tối đa ~12500; 131 đoạn dưới 80 ký tự |
| Đoạn thiếu số trang | 155 |
| Thành phần nguồn phục vụ được | ~45 chương trình/kế hoạch giảng dạy, 31 nguồn nhãn "K70_and_earlier_verify_individual_row", 13 nguồn "K71 — …", 34 nguồn khác |

Phát hiện:
1. **Kho nghiêng mạnh về chương trình đào tạo** (khoảng 89 trong 123 nguồn là chương trình/kế hoạch giảng dạy). Văn bản hành chính phục vụ phục vụ được rất ít: Quy chế đào tạo 1486, QĐ 924 học phí, QĐ 94 chuẩn ngoại ngữ, quy trình điểm rèn luyện, quy chế ATTT 2114, mẫu đơn miễn giảm, hướng dẫn thư viện/Office 365, nội quy phòng máy, học bổng STEM, kế hoạch nhập học K71. Chưa kiểm được các chủ đề sinh viên hay hỏi (thi, phúc khảo, bảo lưu, thôi học, học bổng khuyến khích, ký túc xá, BHYT, tốt nghiệp, thủ tục xác nhận) nằm trong Quy chế 1486 hay thiếu hẳn; cần đối chiếu từng chủ đề.
2. **31 nguồn mang nhãn nội bộ** `K70_and_earlier_verify_individual_row` trong tiêu đề, người dùng nhìn thấy trong trích dẫn.
3. **Có nguồn thử nghiệm "Synthetic queue contract"** (nhiều bản ghi, vài bản PUBLISHED, mỗi bản 1 đoạn "no institutional facts") nằm cùng nguồn thật và `is_synthetic=false`. Đoạn rất ngắn nên ít khi lọt top, nhưng không nên nằm trong kho phục vụ. Chưa xóa hay sửa (cần người dùng nói rõ).
4. **240 phiên bản DRAFT** không được phục vụ; chưa biết có nội dung thật cần duyệt hay chỉ là bản nháp lặp.
5. **Đoạn dài** (trung vị ~2100 ký tự trong phần phục vụ được) có thể làm loãng điểm embedding/rerank; cần thử đo, chưa kết luận.
6. Cấu hình truy xuất của lô phát hành mới nhất: lexical_k 30, semantic_k 30, rerank_input_limit 20, context_k 8, `evidence_support_threshold` 0.78, `recall_at_10_min` 0.9. Mục tiêu này chưa có số đo thực.

Việc tiếp theo cho luồng A: đối chiếu chủ đề × có/thiếu trong Quy chế 1486 và các văn bản khác; kiểm mẫu trích xuất bảng; đề xuất danh sách văn bản cần bổ sung; xác định đoạn tiny/không trang.
