# Chặng 5 — Đồ thị quy định có bằng chứng và hiệu lực

Ngày: 13/10/2026. Trạng thái: thiết kế. Ước lượng: **12–24 giờ Codex hoạt động**, trước dự phòng. [Kiến trúc chung](00_SHARED_ARCHITECTURE.md).

## 1. Phạm vi và mục tiêu

Đồ thị phục vụ quan hệ giữa thủ tục, hồ sơ, đơn vị, đối tượng, điều kiện và ngoại lệ. Ưu tiên xin xác nhận/phúc khảo và nhóm quy định học vụ liên quan đã có nguồn. Kho tri thức rộng hơn vẫn truy hồi bằng hybrid search.

Graph-assisted RAG là phần cam kết. Graph execution của agent khác với graph tri thức. Microsoft GraphRAG community/global search là nhánh mở rộng; chỉ thử khi có câu hỏi tổng hợp toàn corpus và nguồn lực phù hợp.

## 2. Schema tri thức đề xuất

| Thực thể | Thuộc tính quan trọng |
|---|---|
| PolicyDocument/Clause | Source/version, locator, tên, checksum |
| Procedure/Form | Mã thủ tục/biểu mẫu, tên, version |
| OrganizationUnit | Đơn vị và nguồn xác minh |
| Audience | Khóa, chương trình, loại đối tượng |
| ConditionGroup/Condition | Biểu thức ALL/ANY, ngưỡng, đối tượng và qualifiers |
| Exception | Trường hợp ngoại lệ và quan hệ tới điều kiện |
| EffectiveInterval | Bắt đầu/kết thúc cùng căn cứ nguồn |

Edges: requires, applies_to, handled_by, defined_by, has_exception, supersedes. Mỗi edge có source ID/version/locator/hash, review status, scope và thời gian hiệu lực.

Lưu trong PostgreSQL qua node/edge tables hoặc relational schema tương đương. Dùng recursive query có depth/node/cycle bounds. Chỉ thêm graph database riêng khi truy vấn/benchmark thực cho thấy nhu cầu, không bổ sung stack chỉ để có thêm công nghệ.

## 3. Điều kiện và ngoại lệ

Biểu diễn nhóm điều kiện để giữ sự khác biệt ALL với ANY. Ví dụ “đủ các điều kiện a–d” là một group ALL; tìm được a không chứng minh eligibility. Giá trị, đơn vị, dấu so sánh và ngoại lệ gắn source riêng.

Quan hệ trích xuất bằng LLM là candidate, có thể thiếu hoặc sai. Không tự biến graph thành rule engine phê duyệt. Một số kiểm tra định lượng được chuyển thành rule backend chỉ sau khi đã đối chiếu toàn văn và được kiểm tra phù hợp.

## 4. Xây và kiểm duyệt graph

1. Chọn source versions đã đủ điều kiện, snapshot/fingerprint rõ.
2. Trích xuất candidate entities/edges với schema và source refs.
3. Chuẩn hóa alias có kiểm tra; entity trùng tên không tự merge nếu khác trường/đơn vị/đối tượng.
4. Check locator/hash, dangling edge, quantifier và temporal conflicts.
5. Review quan hệ quan trọng trong UI; giữ raw proposal và verdict.
6. Xuất bản graph version mới cùng mapping về source/index snapshot.

Giữ graph/index trước đó. Không ghi đè hoặc tự xóa namespace cũ khi build thất bại. Reviewed relation vẫn phải kiểm eligibility của nguồn khi đọc.

## 5. Temporal và provenance

Phân biệt ngày ban hành, ngày hiệu lực và ngày thu nhận. Chọn interval semantics thống nhất trong schema rồi map từ quy định nguồn có ghi nhận; không tự diễn giải thời điểm kết thúc khi nguồn chưa rõ.

Quan hệ supersedes có thể chỉ thay một điều khoản hoặc một nhóm đối tượng. Không suy ra văn bản mới hơn thay toàn bộ văn bản cũ. Nếu chưa xác định được, giữ conflict/unknown và hỏi/chuyển hỗ trợ.

Current mode giữ publication/eligibility controls hiện có. Câu hỏi về quá khứ dùng historical mode riêng có quyền, snapshot và nhãn thời điểm; không âm thầm cho nguồn superseded tham gia current mode.

## 6. Graph-assisted retrieval

Hybrid search tìm entity/clause ứng viên → graph mở rộng một số quan hệ có bounds → source reader lấy điều khoản gốc → rerank/context assembly → coverage/claim verification.

Chỉ expose graph tool sau authorization filter. Dữ liệu ngoài scope không xuất hiện trong neighbor count, suggestion hoặc error payload. Nếu traversal không tìm được, quay lại search đủ điều kiện; nếu graph service lỗi phải phân biệt với không có quan hệ.

Graph path giúp giải thích vị trí tìm evidence. Citation cuối dẫn tới văn bản gốc. Graph summary không tự là bằng chứng kết luận.

## 7. API/UI và module

- Graph builder trong ingestion/application knowledge, execution qua worker.
- Repository/query service riêng, được bind cùng RetrievalContext.
- Admin review UI hiển thị edge, đoạn nguồn, condition group, hiệu lực và verdict.
- Research Agent được cấp `search_policy_relations` trong scope; Coordinator vẫn giới hạn calls/depth/context.

UI có thể hiển thị “thủ tục → biểu mẫu → căn cứ” cho người dùng; chỉ hiển thị quan hệ đã đủ điều kiện và quyền.

## 8. Work packages và thời gian

| Gói | Công việc | Giờ Codex |
|---|---|---:|
| S5-01 | Schema, source mapping và graph versioning | 2–4 |
| S5-02 | Candidate extraction, review và temporal/condition checks | 4–8 |
| S5-03 | Bounded traversal và tích hợp retrieval | 3–6 |
| S5-04 | Review UI, test và kiểm chứng graph-assisted retrieval | 3–6 |

## 9. Acceptance và đánh giá chất lượng

- Mỗi published edge truy ngược được source/locator/hash; edge chưa review không trở thành fact.
- Giữ đủ ALL/ANY, ngoại lệ và scope; sai quantifier bị phát hiện trong test.
- Supersedes theo phạm vi, câu hỏi sai thời điểm, cycle và duplicate aliases được xử lý.
- Zero observed graph leakage trong các ca quyền đã chạy.
- Graph version/index/source mismatch bị từ chối hoặc xử lý rõ.
- Kiểm độ đúng/đầy đủ và provenance trên câu quan hệ, điều kiện và nhiều nguồn; báo lỗi extraction, chi phí xây graph riêng với chi phí query. Theo phạm vi cập nhật ngày 13/10/2026, không yêu cầu so sánh graph-on/off hoặc ablation.

Kết luận chất lượng theo nhóm đã đo; không dùng một demo để khẳng định toàn pipeline tốt hơn kiến trúc khác.

## 10. Chuyển tiếp và tham khảo

Graph version là cấu hình tùy chọn ban đầu; giữ đường hybrid có thể phục hồi. Không chỉnh bytes nguồn để thuận tiện cho entity extraction.

[From Local to Global: A Graph RAG Approach to Query-Focused Summarization](https://graphrag.com/appendices/research/2404.16130/) là tham khảo cho graph-based retrieval; topology thủ tục và điều kiện trong tài liệu này là thiết kế ứng dụng của Campus 24/7.
