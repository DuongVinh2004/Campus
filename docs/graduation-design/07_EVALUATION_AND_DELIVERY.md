# Chặng 7 — Đánh giá độc lập và bàn giao đồ án

Ngày: 13/10/2026. Trạng thái: thiết kế. Ước lượng: **16–32 giờ Codex hoạt động**, trước dự phòng; thời gian reviewer/người dùng thử chờ bên ngoài báo riêng. [Điều hướng](README.md).

## 1. Mục tiêu

Kiểm chứng mức đạt mục tiêu, chất lượng, lỗi, chi phí/độ trễ và giới hạn thực tế của hệ thống multi-agent được chọn. Bàn giao hệ thống, dữ liệu, runner và báo cáo có thể tái lập. Theo yêu cầu trực tiếp ngày 13/10/2026, không còn benchmark so sánh kiến trúc hoặc ablation; chặng 2–3–4 đã gộp tại [Multi-agent tích hợp](02_MULTI_AGENT_INTEGRATED.md).

Đầu vào: cấu hình multi-agent đã được kiểm chức năng, nguồn/corpus snapshot, usage controls, schema dữ liệu và evidence trước đó. Chưa hoàn thành toàn hệ thống thì chỉ kết luận đúng phạm vi đã đo.

## 2. Dataset và tránh leakage

Mục tiêu quy mô theo kế hoạch: khoảng 300 câu hỏi, 40 kịch bản hội thoại nhiều lượt và 60 tình huống công cụ/lỗi nghiệp vụ. Dataset chặng 1 được đăng ký là development/regression, không dùng làm held-out test chỉ bằng cách đổi tên.

Mỗi case gồm ID/category, query/history, audience/as-of khi cần, gold source/version/locator, required facts/conditions, expected terminal behavior và rubric. Gold source phải được kiểm toàn văn, không chỉ lấy FAQ hoặc đáp án do cùng model tự sinh.

Tách dev/validation/held-out theo nhóm paraphrase/chủ đề/nguồn khi phù hợp; không để cùng câu đổi vài từ rơi vào cả dev và test. Đóng băng test trước lượt cuối; không đưa answer labels vào contextual index hoặc prompt.

Codex có thể đề xuất câu và candidate labels; source-check và kiểm tra độc lập phải được ghi provenance. Nếu chưa có đánh giá độc lập của người ở nhóm nghiệp vụ quan trọng, báo rõ giới hạn và không tuyên bố independent correctness đã đạt. Tiếp tục các phép đo khác đủ điều kiện.

## 3. Thiết kế đánh giá

| Cấu hình | Vai trò |
|---|---|
| Multi-agent tích hợp | Coordinator/Research/Verifier, coverage/tìm bổ sung và phục hồi |
| Multi-agent có graph | Kiểm nguồn, hiệu lực và điều kiện của graph-assisted retrieval khi chặng 5 đã tích hợp |

Đóng băng cấu hình đang phục vụ trước đánh giá cuối. Đo chất lượng theo rubric và nguồn thật; ghi calls/tokens/cost, p50/p95 và lỗi. Evidence các đường RAG cũ được giữ nguyên, không phải đối chứng bắt buộc chạy lại.

Ghi generator/model revision, corpus snapshot, gold, rubric, embedding/reranker/prompt/config cho từng lượt. Thay cấu hình sau khi xem tập cuối cần được báo rõ; không coi dataset đã dùng tuning là held-out.

Kiểm tra timeout, malformed output, source withdrawn và lỗi worker bằng doubles/namespace riêng. Không giảm verification, authorization hoặc confirmation của ứng dụng đang phục vụ để tạo kịch bản kiểm thử.

## 4. Metrics và reporting

| Nhóm | Cách đo |
|---|---|
| Retrieval | Recall@k trên source relevance labels; MRR/nDCG nếu nhãn hỗ trợ; coverage đủ nguồn cần thiết |
| Answer | Correctness, completeness và material-condition preservation theo rubric |
| Citation | Citation precision/support, missing citation, locator/hash validity |
| Refusal | Từ chối đúng ở unanswerable và từ chối quá mức ở answerable |
| Agent | Task completion, redundant work, useful retrieval steps, errors và stopping |
| Business | Transition correctness, confirmation binding, duplicate effects và observed unauthorized access |
| Resources | Calls/tokens/cost, queue/inference/end-to-end time, p50/p95, errors/timeouts |

Phân biệt đầy đủ, partial, abstained và failed. Không loại timeout khỏi denominator để làm quality/latency đẹp. Report theo nhóm, sample size, failed IDs và raw results. Chọn interval/statistical method phù hợp; lặp một subset khi model variance đáng kể và ngân sách cho phép.

LLM judge hỗ trợ semantic scoring; kiểm schema/auth/effect/hash bằng deterministic checks. Chấm người trên tập được chọn có thiết kế, báo agreement/adjudication nếu có; không chỉ chọn những ca AI đã chấm đúng.

## 5. Benchmark, tải và fault tests

Tách offline doubles, real retrieval và live generation. Benchmark ghi warm/cold, cache mode, concurrency, phần cứng và version. Chạy tải nhỏ tăng dần trong giới hạn được phép; ví dụ các mức 1/2/5 concurrent nếu resource profile cho phép, không tự nâng cap để đạt tải mục tiêu.

Fault scenarios: vector/reranker unavailable, malformed provider output, HTTP disconnect, deadline, budget exhaustion, source withdrawn, database/audit failure, queue conflict, invalid confirmation, crash/resume và reconnect SSE.

Không shutdown tiến trình không sở hữu hoặc phá database đang có dữ liệu. Dùng fault doubles hoặc service namespace riêng được xác minh. Build thêm infrastructure chỉ khi thuộc phạm vi/ngân sách đã có.

## 6. Trải nghiệm và ứng dụng thực tế

User tasks: tìm quy định, hiểu ngoại lệ, gửi xin xác nhận, bổ sung hồ sơ, cán bộ xử lý, đề nghị phúc khảo và nhận kết quả. Đo hoàn thành, lỗi và phản hồi; ghi số người/role/cách tuyển và môi trường mô phỏng.

Peer testing hỗ trợ usability, không thay xác nhận nghiệp vụ của cán bộ trường. Dữ liệu mô phỏng và tài liệu công khai vẫn là phạm vi; một demo trơn tru không chứng minh production readiness.

## 7. Reproducibility bundle

- Source revision nếu có cùng working-tree patch/hash snapshot đủ xác định implementation; không tự commit để có revision sạch.
- Corpus/source/index/graph/model/prompt/config fingerprints.
- Dataset và split registry, gold provenance, rubric và runner commands.
- Usage/budget records, environment/hardware và thời gian.
- Raw results, failed/uncertain cases, thống kê và hình xuất phục vụ báo cáo.
- Hướng dẫn chạy, migrations additive, sample actors, nguồn cấu hình và phục hồi.

Secrets/PII không nằm trong bundle. Output mới có tên/version mới; không ghi đè evidence của lượt thất bại.

## 8. Work packages và thời gian

| Gói | Công việc | Giờ Codex |
|---|---|---:|
| S7-01 | Dataset registry, kiểm nguồn và tách tập cuối | 4–8 |
| S7-02 | Runner, đánh giá chất lượng và failure analysis | 5–10 |
| S7-03 | Fault/load/UI testing và sửa lỗi cần thiết | 4–8 |
| S7-04 | Bundle, báo cáo, figures và kịch bản demo | 3–6 |

Phần người review, dùng thử và thiếu compute/provider budget tách khỏi giờ Codex; nếu phát sinh sửa lớn, cập nhật estimate theo record quan sát được.

## 9. Tiêu chí bàn giao

- Sản phẩm đạt mục tiêu nghiệp vụ và giới hạn đã chốt, có minh chứng quyền/xác nhận/persistence.
- Cấu hình multi-agent đang phục vụ có kết quả theo acceptance hiện hành và giải thích cụ thể phần chưa đo; không gọi chưa đo là hoàn tất.
- Có đánh giá từng nhóm, chi phí/độ trễ và failure analysis, không chỉ một tổng score.
- Evidence được đọc lại và tái lập ít nhất một lượt phù hợp từ hướng dẫn.
- Demo gồm thành công, thiếu nguồn, nguồn/điều kiện mâu thuẫn và lỗi có thể phục hồi.
- Báo cáo học thuật phân biệt đóng góp ứng dụng, phương pháp có sẵn, kết quả đo và hướng mở rộng.
- Nếu một chỉ tiêu chưa đạt, ghi phần chưa hoàn thành và việc cần làm; không đổi gold/threshold để nghiệm thu.

## 10. Liên kết với kế hoạch

Chặng này kết thúc bằng báo cáo rõ mức đạt mục tiêu, thời gian Codex thực tế, phần chờ bên ngoài và phạm vi vận hành được kiểm chứng. Sáu tháng học kỳ là bối cảnh tổ chức của người thực hiện; lịch implementation được điều phối theo giờ Codex và đầu ra thực tế trong [README](README.md).
