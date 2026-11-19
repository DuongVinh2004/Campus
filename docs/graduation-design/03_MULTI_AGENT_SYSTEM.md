# Chặng 3 — Hệ thống đa tác tử có trạng thái và kiểm chứng

> **Tham khảo thiết kế cũ:** Scope và acceptance hiện hành theo [chặng 2–3–4 gộp](02_MULTI_AGENT_INTEGRATED.md). Dùng multi-agent ngay; không cần baseline single-agent, benchmark so sánh hoặc thực nghiệm ngân sách tương đương. Giữ hợp đồng vai trò, DAG, quyền, evidence, usage và phục hồi bên dưới làm tham khảo kỹ thuật.

Ngày: 13/10/2026. Trạng thái: thiết kế. Ước lượng: **16–30 giờ Codex hoạt động**, trước dự phòng. [Kiến trúc chung](00_SHARED_ARCHITECTURE.md).

## 1. Mục tiêu và phụ thuộc

Coordinator phân công những phần độc lập, Research tìm bằng chứng, Verifier kiểm từng kết luận. Hệ thống tổng hợp có điều kiện, phục hồi sau lỗi và kiểm soát ngân sách chung. Service Agent được nối sâu ở chặng 6.

Cần reusable search/evidence/coverage contracts của chặng 2, persistent run/task store đủ điều kiện và baseline single-agent. Multi-agent không được mặc định tốt hơn; lợi ích cần được chứng minh trên nhóm câu phức tạp.

## 2. Vai trò và phạm vi

| Vai trò | Input | Output | Quyền |
|---|---|---|---|
| Coordinator | Goal, CoverageItems, trusted resource limits | TaskPlan, merge decision, terminal proposal | Giao tool task trong allowlist; không cấp quyền nghiệp vụ |
| Research | Một mục tiêu con, evidence refs liên quan | EvidenceBundle, findings và missing items | Search/read nguồn theo cùng scope |
| Verifier | Claims, source refs và câu hỏi | Verdict, conflicts, missing material conditions | Read/check evidence; không duyệt hồ sơ |
| Service, giai đoạn sau | Ý định nghiệp vụ và dữ liệu cho phép | Draft/action proposal | Gọi service qua authorization boundary |

Các vai trò có thể dùng một mô hình nền. State và prompt tách theo trách nhiệm; chỉ truyền context cần thiết. Nội dung agent gửi sang agent khác là dữ liệu chưa được tin cậy.

## 3. TaskPlan và DAG

Mỗi task có ID, goal, dependency IDs, role, tool allowlist, input evidence refs, status, attempt, lease/version và deadline. Validator từ chối cycle, task count vượt cap, dependency không tồn tại, tool ngoài quyền và task không có mục tiêu cụ thể.

Ví dụ câu hỏi nghỉ học/học bổng/hồ sơ: Research A tìm nghỉ học; Research B tìm học bổng; task thủ tục có thể đọc kết quả A. Verifier kiểm cả kết luận liên ngành; Coordinator hỏi thêm loại học bổng nếu còn thiếu dữ kiện.

TaskPlan chỉ chứa kế hoạch và dữ liệu có cấu trúc; không yêu cầu model cung cấp suy luận nội bộ.

## 4. Điều phối và concurrency

Default pool nhỏ, giới hạn bởi runtime profile đã xác minh. Tác vụ độc lập được fan-out; có phụ thuộc thì đợi đúng kết quả. Budget reservation dùng ledger chung để hai worker không cùng tiêu phần ngân sách còn lại.

Task states: `pending → ready → running → succeeded/partial/failed/cancelled`. Claim/completeness riêng với task transport success: HTTP thành công chưa chứng minh finding đúng.

Worker lease có thời hạn và version; chỉ một worker nhận task tại một thời điểm. Lease hết hạn tạo quyết định retry/reconcile dựa trên tool effect. Retry đọc nguồn có thể an toàn; thao tác nghiệp vụ đã có kết quả không được lặp mù.

## 5. Shared evidence và synthesis

- Evidence được lưu theo run + snapshot, deduplicate theo source/version/locator/hash.
- Coordinator merge findings mà không thay excerpt nguồn.
- Verifier mở source refs; không chỉ đọc phần tóm tắt của Research.
- Khi nguồn khác nhau, giữ object/time/condition tương ứng; không ghép thành điều kiện mới không tồn tại trong nguồn.
- Majority vote của nhiều agent không làm một phát biểu thành sự thật.
- Đầu ra tổng hợp đi qua cùng evidence/output gates của hệ thống.

Lặp sửa có giới hạn: Verifier báo thiếu cụ thể → Coordinator tạo nhiệm vụ bổ sung → verify lại; sau giới hạn trả partial/clarification/handover rõ.

## 6. Persistence và resume

Lưu task plan, task results, coverage, evidence references và usage reservations. Khi crash, phân biệt task chưa chạy, đang chạy và đã có kết quả. Resume xác minh actor và corpus/policy compatibility; không dùng checkpoint để truy nguồn đã bị thu hồi quyền.

Checkpoint là orchestration state, còn transaction/idempotency là trách nhiệm executor nghiệp vụ. Mỗi namespace có isolation; cùng conversation không được vô tình nhập state của user khác.

## 7. API và UI

UI có thể hiển thị các task như “tìm quy định nghỉ học”, “đối chiếu ảnh hưởng học bổng”, “kiểm tra thành phần hồ sơ”. Hiển thị trạng thái tiến độ, nguồn và phần chưa xác định. Không cho người dùng sửa role/tool quyền bằng payload task plan.

Mỗi event có sequence và run ID. Terminal được lưu để reload; disconnect không tự tạo run mới hoặc tự gửi action lần nữa.

## 8. Work packages và thời gian

| Gói | Công việc | Giờ Codex |
|---|---|---:|
| S3-01 | Task/result schema, DAG validation và role contracts | 3–5 |
| S3-02 | Coordinator, worker pool, ledger reservations và task store | 5–10 |
| S3-03 | Verifier, synthesis, failure/retry/resume handling | 4–8 |
| S3-04 | Streaming UI, integration và so sánh single/multi | 4–7 |

## 9. Acceptance và thực nghiệm ban đầu

- Có kịch bản phân công thực sự thay đổi theo yêu cầu và evidence thiếu; trace thể hiện tác vụ độc lập được chạy song song khi runtime cho phép.
- DAG sai, tool giả và output không đúng schema bị từ chối trước effect.
- Một worker lỗi không làm worker khác bị coi là thành công đầy đủ; terminal partial/error đúng.
- Crash/restart giữa fan-out/merge không mất task đã lưu hoặc lặp business effect.
- Scope/usage cap áp cho toàn run, kể cả retries và verifier.
- Hai agent diễn giải cùng nguồn sai không vượt material/evidence gate chỉ nhờ đồng ý.
- So sánh với single-agent cả ngân sách tự nhiên và ngân sách tương đương; báo chất lượng, calls/tokens, thời gian chờ và wall time.

Phân loại lỗi phối hợp: task specification, dependency, context loss, duplicated work, invalid synthesis, failed verification và incorrect stopping. Tham khảo taxonomy nghiên cứu, dùng nhãn phù hợp cho dự án. [Why Do Multi-Agent LLM Systems Fail?](https://arxiv.org/abs/2503.13657).

## 10. Chuyển tiếp

Giữ single-agent làm đường so sánh và phục vụ phù hợp. Có thể thay bố cục agent/graph nếu benchmark cho thấy topology khác tốt hơn; giữ hợp đồng quyền/evidence và dữ liệu run cũ. Đầu ra chặng này là runtime multi-agent kiểm chứng được, chưa phải router thích ứng tối ưu hay production readiness.
