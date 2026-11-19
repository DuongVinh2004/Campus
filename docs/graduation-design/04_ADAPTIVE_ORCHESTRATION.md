# Chặng 4 — Điều phối thích ứng theo chất lượng và ngân sách

> **Tham khảo thiết kế cũ:** Scope và acceptance hiện hành theo [chặng 2–3–4 gộp](02_MULTI_AGENT_INTEGRATED.md). Điều phối thích ứng chọn số task, mức đồng thời và tìm bổ sung trong hệ thống multi-agent. Không còn yêu cầu router giữa Advanced/single/multi hoặc benchmark so sánh các đường xử lý. Admission, cache, ledger và observability vẫn cần được kiểm chứng.

Ngày: 13/10/2026. Trạng thái: thiết kế. Ước lượng: **8–16 giờ Codex hoạt động**, trước dự phòng. [Kiến trúc chung](00_SHARED_ARCHITECTURE.md).

## 1. Mục tiêu và phân biệt với chặng 2

Chặng 2 chọn hành động trong một agent run. Chặng 4 chọn đường xử lý toàn yêu cầu: nội dung hệ thống, Advanced RAG, single-agent, multi-agent, clarification hoặc service flow. Lựa chọn dựa trên độ khó, coverage dự kiến, chi phí và trạng thái tài nguyên.

Cần các đường xử lý có contract tương thích, baseline phát triển, resource ledger và telemetry. Chưa có evidence đủ cho một đường thì không chọn đường đó như đã sẵn sàng.

## 2. Router thiết kế

| Đặc điểm yêu cầu | Đường ứng viên |
|---|---|
| Giới thiệu hoặc thao tác giao diện | Nội dung server định nghĩa |
| Quy định cụ thể một nguồn | Advanced RAG |
| Câu nối tiếp, cần đọc thêm điều kiện | Single-agent |
| Nhiều vấn đề độc lập, cần kiểm tra giao thoa | Multi-agent |
| Thiếu thông tin quyết định phạm vi áp dụng | Clarification |
| Nộp/theo dõi hồ sơ | Service flow với auth/confirmation |

Features đề xuất: số mục tiêu, ambiguity, temporal constraints, nhu cầu thông tin cá nhân, số nguồn/phạm vi cần phối hợp, kết quả retrieval sơ bộ và nguồn lực còn lại. Không dùng số từ làm proxy duy nhất cho độ khó. Đọc thông tin cá nhân phải qua công cụ có quyền; router không tạo personal facts.

Mặc định heuristic có cấu trúc để giải thích và đo lỗi. Có thể dùng classifier nhỏ hoặc model router nếu dữ liệu dev cho thấy cải thiện. Không huấn luyện trên test cuối. Route score chưa hiệu chuẩn được báo là score, không là xác suất đúng.

## 3. Progressive execution

Bắt đầu bằng đường đủ khả năng giải quyết. Nếu evidence coverage thật chưa đủ, nâng từ Advanced sang single-agent hoặc multi-agent khi còn tài nguyên. Handoff tái sử dụng evidence typed cùng snapshot; không gọi lại tất cả bước vì đổi topology.

Early exit chỉ khi các phần cần trả lời đã được hỗ trợ và claim checks qua. Budget thấp có thể giới hạn số phần hoặc chuyển hỗ trợ, nhưng không làm tiêu chí đúng trở nên thấp hơn.

Router v1 dùng tiêu chí xác định và corpus/question categories. Route tối ưu về chất lượng/chi phí được tìm trên dev, đóng băng trước đánh giá cuối.

## 4. Admission control và budget

Trước khi chạy, server tạo budget envelope từ giới hạn hiện hành. Một reservation cho model/tool gồm số calls, token dự kiến và thời gian. Sau response reconcile usage thật; kết quả uncertain giữ reservation theo quy tắc ledger đang có.

- Ceiling của toàn run được chia cho worker, verifier và synthesis; không nhân cap theo số agent.
- Dùng thời gian monotonic cho deadline trong process; persisted timestamps/cursor cho resume.
- Hết call cap vẫn dừng dù cost USD còn; không tự tăng/reset ledger.
- Chỉ parallelize khi CPU/model queue/provider/concurrency budget cho phép.
- Xử lý queue deadline tách khỏi inference duration, nhưng báo cả hai ở trải nghiệm user.
- Hủy hoặc timeout kiểm tra tool effect trước quyết định retry.

Khi profile tài nguyên hiện tại không đủ cho benchmark, chuẩn bị runner/dataset/cấu hình offline, ghi nhu cầu và chờ nguồn lực còn thiếu. Không tạo cấu hình bỏ guard để chạy cho xong.

## 5. Cache và state

Cache truy vấn/evidence gồm scope hash, corpus/index/model/config version và thời điểm hiệu lực. Cache hit kiểm lại source state và quyền hiện tại. Không dùng answer cache chung cho dữ liệu cá nhân.

Có thể cache model-independent parse, query embedding hoặc source excerpts theo version. Không coi cached agent output là nguồn sự thật. Khi nguồn/role/policy đổi, fail eligibility hoặc tạo query theo snapshot phù hợp.

## 6. Vận hành và lựa chọn khi lỗi

| Lỗi | Hành vi mong muốn |
|---|---|
| Router output sai | Validate và chọn đường fallback đã kiểm chứng hoặc báo lỗi |
| Model/router unavailable | Heuristic đủ điều kiện hoặc clarification; không trả quy định từ memory |
| Reranker/vector failure | Chỉ dùng đường degraded riêng đã đánh giá; nếu chưa có thì lỗi rõ |
| Worker overload | Queue có thời hạn, giới hạn concurrent hoặc từ chối admission |
| Sources thay đổi giữa lượt | Giữ snapshot có eligibility, hoặc revalidate/restart có kiểm soát |
| Budget exhausted | Terminal partial/refusal với nguyên nhân tài nguyên phù hợp |

Dashboard: route distribution, route changes, quality theo route, cost/calls/tokens, queue time, p50/p95, timeout và ratio no-progress. Thiếu telemetry là unknown; không hiển thị xanh mặc định.

## 7. Work packages và thời gian

| Gói | Công việc | Giờ Codex |
|---|---|---:|
| S4-01 | Features, heuristic router và route contracts | 2–4 |
| S4-02 | Global budget admission, progressive handoff và early exit | 3–6 |
| S4-03 | Cache/observability và benchmark cố định/thích ứng | 3–6 |

## 8. Acceptance và thực nghiệm

- Đường xử lý phù hợp trên các nhóm dev đã gán nhãn; ghi confusion và lỗi route.
- Câu đơn giản không bị fan-out vô ích; câu khó có cơ chế nâng đường dựa vào thiếu bằng chứng thực.
- Parallel reservations không vượt cap; retry/verifier thuộc budget chung.
- Cache chéo user/scope/version không lộ dữ liệu; expired source bị loại cả khi hit.
- Handoff giữ nguồn/hash/history và terminal UI contract.
- So sánh always-Advanced, always-single, always-multi và adaptive trên cùng model/corpus/questions; báo chất lượng và resource use, không chỉ tốc độ.
- Giữ floor chất lượng và safety checks; nếu tiết kiệm chi phí nhưng làm giảm materially correctness thì chưa đủ căn cứ chọn làm mặc định.

Tư tưởng chọn độ phức tạp xử lý có thể tham khảo [Adaptive-RAG](https://aclanthology.org/2024.naacl-long.389/). Cơ chế budget-aware progressive handoff ở đây là thiết kế ứng dụng đề xuất, cần đo tại Campus 24/7.

## 9. Chuyển tiếp

Router config có version. Đổi lựa chọn mặc định tại namespace local được xác minh, ghi previous config và kết quả canary; giữ đường cố định để ablation/phục hồi. Không đổi giới hạn an toàn vì cấu hình adaptive chưa đủ nhanh.
