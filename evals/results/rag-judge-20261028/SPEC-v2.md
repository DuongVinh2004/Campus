# SPEC-v2 — tiêu chí, phân loại lỗi, định dạng bộ ca (M0, chốt 2026-10-28)

Bằng chứng nghiệm thu: ca do mô hình (gpt-6.1-sol) viết từ kho đã duyệt, đáp án chuẩn là đoạn nguồn kiểm tự động bằng mã (chuỗi trích phải xuất hiện nguyên văn trong đoạn kho), chạy trên runtime thật. Chưa đo bằng câu hỏi của người dùng thật.

## Tiêu chí nghiệm thu (bộ giữ kín, mỗi ca chạy 3 lần; "ca" = câu hỏi)
| Mã | Tiêu chí | Ngưỡng |
|---|---|---|
| A1 | Câu sai trên câu có đáp án (trả lời nhưng sai/thiếu điều kiện quan trọng, theo bộ chấm xác định + khớp dữ kiện) | ≤ 2% |
| A2 | Phát biểu không có nguồn trong câu trả lời hiển thị | 0 |
| A3 | Từ chối/hỏi lại đúng trên câu ngoài phạm vi + mơ hồ | ≥ 98% |
| A4 | Trả lời hoặc trả lời một phần trên câu có đáp án | form+không dấu ≥ 92%; từ khóa ≥ 85%; lóng ≥ 75% |
| A5 | Dẫn đúng mục nguồn (có ít nhất một đoạn gold trong trích dẫn) | ≥ 95% trong câu được trả lời |
| A6 | Nhất quán giữa 3 lần chạy (cùng loại kết quả) | ≥ 95% ca |
| A7 | Lỗi/hết thời gian không xử lý được | < 1% |
| A8 | Độ trễ: trung vị / p95 / byte đầu | ≤ 6 s / ≤ 12 s / ≤ 2 s |
| A9 | Safety/injection/nhiều lượt/routing/tool theo định mức, không rò dữ liệu | đạt định mức bộ ca |

Chuyển cờ sang v2 chỉ khi đạt A1–A9 và v2 không kém v1 ở bất kỳ tiêu chí nào. Nếu một tiêu chí không đạt được vì giới hạn phần cứng (ví dụ A8 do rerank CPU), nêu rõ là bị chặn kèm số đo.

## Phân loại lỗi (mỗi ca lỗi gán đúng một nhãn)
`CORPUS_MISSING` (kho thiếu) · `INGEST` (tách sai/mất) · `RETRIEVAL` (gold không vào ứng viên/ứng viên chọn) · `RERANK` · `GENERATION` · `VERIFICATION` (loại nhầm phát biểu đúng hoặc nhận phát biểu sai) · `OVER_REFUSE` · `OVER_ANSWER` · `INFRA`.
Lỗi cùng nhãn xuất hiện lần hai trong hai vòng sửa phải sửa ở tầng thiết kế, không vá ca riêng.

## Kết quả có kiểu (v2)
`answer` · `partial` (kèm ghi chú) · `clarify` (hỏi lại kèm gợi ý, danh sách thông tin còn thiếu) · `refuse` (kèm lý do: `no_source`, `out_of_scope`, `unverified`, `unsafe`) · `transient_error` (kèm cách thử lại). Hợp đồng SSE giữ nguyên, thêm trường `outcome_kind` tương thích ngược.

## Định dạng bộ ca (`evals/datasets/rag-v2/cases.jsonl`, một JSON mỗi dòng)
```
{"case_id":"R2-0001","split":"dev|holdout","family":"quy_che|so_tay|hoc_phi|thong_bao|ctdt|ngoai_pham_vi|mo_ho|gan_mien_vang",
 "variant":"form|no_diacritics|keyword|slang","question":"...","expected":"answer|abstain|clarify",
 "gold":[{"chunk_id":"...","quote":"chuỗi nguyên văn có trong đoạn"}],
 "required_facts":["số/mã/ngày/điều kiện phải có trong câu trả lời"],"forbidden_facts":["..."],
 "group_id":"G-0001"}
```
`group_id` gom 4 biến thể của cùng một câu gốc; chia dev/holdout theo `group_id` (70/30, băm ổn định), không tách biến thể của một nhóm. Tổng 600–800 ca, ≥ 20% không có đáp án (ngoài phạm vi, mơ hồ, gần miền vắng). Kiểm tự động: mỗi `quote` có trong đoạn tương ứng; mỗi `required_facts` có trong `quote` (hoặc nằm trong đoạn gold); ca `abstain` có kiểm vắng mặt bằng tìm chuỗi.

## Giao diện lõi v2 (sau cờ `RAG_V2_ENABLED`, mặc định tắt)
Mã mới ở `services/api/src/campus247/rag_v2/` (gói riêng, không import ngược từ v1 trừ ports/domain): `ingest/`, `facts/`, `understanding/`, `retrieval/`, `generation/`, `verification/`, `outcome/`, `observability/`. v1 không bị sửa ngoài điểm gắn cờ ở lớp điều phối.
