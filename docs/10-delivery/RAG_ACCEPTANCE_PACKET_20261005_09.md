---
document_id: "DOC-DELIVERY-RAG-ACCEPTANCE-20261005-09"
version: "0.1.0"
status: "draft"
owner: "Implementation executor"
approvers: ["Security Owner", "Knowledge Owner", "AI Quality Lead", "Release Owner"]
last_updated: "2026-10-05"
---

# Hồ sơ kiểm chứng và nghiệm thu Campus 24/7

Người dùng xác nhận “oke làm như thế đi”: giao thực thi kiểm thử, thu thập bằng chứng,
sửa lỗi trong phạm vi đã duyệt và chuẩn bị hồ sơ nghiệm thu. Hồ sơ này là kết quả
thực thi và đề nghị review, không thay requirements, ngưỡng đạt hoặc quyền phát hành.
Không dùng chức danh reviewer giả, tự xác nhận review độc lập hoặc tự publish corpus.

## Phiên bản và phạm vi

Run ID: `acceptance-20261005-09`. [Baseline](../../infra/local/rag-fixture/acceptance-20261005-09-baseline.json)
ghi commit HEAD, dirty state và hash 739 file nguồn/requirements/contracts/tests/evidence
được chọn. HEAD đơn lẻ không xác định phiên bản vì workspace có nhiều thay đổi sẵn có.
Không đọc `frontend/`, sealed evaluation content hoặc credentials trong lượt này.

Lần chụp toàn trình bị chặn bởi thay đổi frontend đồng thời. Không sửa hoặc phục hồi
các file đó. [Baseline backend riêng](../../infra/local/rag-fixture/acceptance-20261005-09-backend-baseline.json)
chốt nguồn backend, tests và đầu vào normative; frontend và pnpm nằm ngoài phạm vi
chứng nhận backend. Script mới được chỉnh để tách hai phạm vi; phiên bản script trước
và sau có hash riêng, bằng chứng cũ không bị ghi đè.

Mỗi lệnh có cwd, exit code, output và bằng chứng hash; artifact tạo bằng exclusive
create, failed runs được giữ nguyên. [Final scope](../../infra/local/rag-fixture/acceptance-20261005-09-final.json)
đối chiếu nguồn trước/sau, tách drift bên ngoài và liệt kê các artifact mới. Không có
product edit, task promotion, dependency install, DB/index write hoặc deployment trong lượt này.

## Bằng chứng kiểm tra lại

| Kiểm tra | Bằng chứng | Giới hạn |
|---|---|---|
| Dependency → catalog → OpenAPI | [Preflight](../../infra/local/rag-fixture/acceptance-20261005-09-preflight.json) | Cả ba exit 0; dependency verifier Python không chứng nhận frontend/pnpm |
| Adapter limits, gateway, SSE, egress, retrieval, runtime parsers và gold validator | [Lần chạy có giới hạn](../../infra/local/rag-fixture/acceptance-20261005-09-tests-03.json) | `not_verified`: process timeout exit 124 sau 150 giây; backend source drift rỗng; chưa có case outcomes để nghiệm thu |
| Lần tests khởi tạo lỗi | [Failed run](../../infra/local/rag-fixture/acceptance-20261005-09-tests.json) | Pytest exit 3 trước tests: default log sink ngoài workspace bị safety guard chặn; giữ nguyên failure |
| Lần tests không hoàn tất | [Interrupted run](../../infra/local/rag-fixture/acceptance-20261005-09-tests-02-interrupted.json) | Executor ngắt chính lệnh đang chờ; không có case outcomes để nghiệm thu |
| Corpus 15 nguồn | [Input verification](../../infra/local/rag-fixture/acceptance-20261005-09-inputs.json) | Hash nội dung, unique IDs, simulation label và quarantine; chưa independent review/publish |
| Runtime 202 finding | [Input verification](../../infra/local/rag-fixture/acceptance-20261005-09-inputs.json) | Rehash supporting evidence/license; không biến static inventory thành compiled SBOM/provenance |

Sửa lỗi runner bằng cách chuyển log pytest tới file workspace mới. Không bỏ safety
guard, network deny, retention hoặc giảm assertions. Không sửa product/expected results
để làm tests đạt. Output, log và temp artifacts của các lần được giữ. Lần cuối tắt
optional external LangSmith tracking plugin cho offline suite và đặt process timeout
150 giây; không thay safety hooks hoặc assertions. Nếu chưa hoàn tất, ghi `not_verified`.

Trace cuối dừng trong Windows `_fallback_socketpair`/`accept` khi test đầu tiên
khởi tạo asyncio. [Diagnostic IPC riêng](../../infra/local/rag-fixture/acceptance-20261005-09-ipc-diagnostic.json)
chạy bounded socketpair với một và hai network guards: cả hai timeout 4 giây.
Do đó không có bằng chứng quy lỗi chỉ cho duplicate guard hoặc LangSmith plugin.
Không nhận timeout là product assertion failure hoặc suy ra nguyên nhân OS/sandbox
đã được xác định. Hai repair attempts của runner đã dùng; dừng tại đây theo
`AGENTS.md`: “Retry a failing implementation at most twice.”

Hướng xử lý cụ thể cho scope runtime kế tiếp: kiểm chứng localhost IPC dưới execution
permission phù hợp bằng bounded probe, giữ nguyên network/secret/filesystem guards;
chỉ chạy lại suites sau khi probe hoàn tất. Nếu không hoàn tất, giữ blocker và trace,
không bỏ protection hoặc tăng timeout vô hạn. Lượt này không yêu cầu hoặc dùng
permission escalation và không có auto-review rejection.

Bằng chứng lịch sử được rehash trong input receipt: browser 21/21 thuộc bundle đã
test trước đó; DeepSeek actual adapter đã gọi thành công với 22 input/1 output token,
843 ms. Không gọi lại provider chỉ để lặp bằng chứng kết nối; không dùng hai receipts
này chứng nhận frontend hiện tại hoặc full real RAG.

## Ma trận nghiệm thu và việc cần hoàn tất

| ID | Tiêu chí | Trạng thái hiện tại | Bằng chứng cần để đóng |
|---|---|---|---|
| AC-01 | Phiên bản kiểm chứng xác định được | Backend có baseline riêng; toàn trình `not_verified` | Backend không drift trong run; frontend ổn định rồi có fresh verification |
| AC-02 | Dependencies/contracts/catalog hợp lệ | `passed` trong scope preflight | Ba commands exit 0 ở receipt; không suy ra acceptance mọi task |
| AC-03 | Offline contracts/regression | `not_verified` do IPC timeout | Exit 0, số passed/skipped/failed rõ, source drift rỗng |
| AC-04 | Browser streaming client | Historical `passed`; current `not_verified` | Fresh current bundle hash + assertions/network/screenshot evidence |
| AC-05 | Provider connectivity | Historical `passed` | Existing direct-adapter receipt; immutable resolved model/cost chưa đủ cho release |
| AC-06 | Runtime dùng được an toàn | `not_verified` | Exact compiled SBOM, verified signer/issuer/provenance, license closure, independent finding dispositions |
| AC-07 | Corpus dùng cho retrieval | Integrity `passed`; publication `not_verified` | Scan/provenance/scope/locator review, independent publish approval, index manifest |
| AC-08 | Trusted identity/scope/citation authorization | `not_verified` toàn trình | Institution/issuer/resolver binding và cross-scope zero-leakage actual integration |
| AC-09 | M1 chạy thật xuyên suốt | `not_verified` | Browser → actual authenticated API → DB/index → real embedding/hybrid/reranker → real LLM → gate/citations/UI, chung run ID |
| AC-10 | M1 hỏi tiếp/refresh/lỗi | `not_verified` | Actual history/persistence, source reauthorization, no-source/outage/injection/terminal cases |
| AC-11 | M2 chất lượng | `not_verified` | Reviewed gold/corpus/splits, actual model/index/profile tuple, đủ denominators/subgroups và repeats |
| AC-12 | M3 hiệu năng/chi phí/resilience | `not_verified` | Measured stage latency/load/hardware/usage/pricing, fault drills, quality regression |
| AC-13 | Pilot và release | `not_verified` | Approved pilot/cohort/baselines, measured outcomes và riêng signed go/no-go |

Ngưỡng approved `RAG_PIPELINE` v1.1.0 giữ nguyên: Recall@10 ≥0.90, critical subgroup
≥0.85, exact-ID Recall@5 ≥0.98, grounded correctness ≥0.90, citation precision ≥0.95,
conflict handling ≥0.98, invalid-source leakage =0; retrieval p95 ≤1800 ms,
p99 ≤3000 ms, error <1%. Chưa có measurements toàn trình nên không ghi các metric này
đạt hoặc ghi giá trị 0 thay cho dữ liệu thiếu.

`EVALUATION_PLAN` hiện reviewed: bộ RAG 500 cases, các negative/multi-turn suites,
split và reviewer requirements là kế hoạch chuẩn bị; owner phải xác nhận authority
trước release promotion. Không đọc sealed cases hoặc dùng model judge làm sole safety gate.

## Hồ sơ đưa cho reviewer

[Phiếu review có cấu trúc](../../infra/local/rag-fixture/acceptance-20261005-09-review-form.json)
có đúng image digest, 202 finding theo component/version/advisory, evidence refs và
15 source/version/content hashes. Các ô decision/reviewer/signature còn null là
chưa quyết định, không phải approved.

| Người xác minh | Việc cần thực hiện và quyết định cụ thể |
|---|---|
| Security/Platform reviewer độc lập | Kiểm đúng subject digest; bổ sung compiled Rust/native/OS SBOM và build features, xác minh chữ ký/provenance với trust root; đối chiếu đủ 192 Debian + 10 Cargo findings, ghi disposition/justification/evidence cho từng finding |
| License reviewer | Đối chiếu MKL controlling license/redist/notices và native/static-link closure; kết quả byte match chín libraries chỉ là đầu vào review |
| Knowledge reviewer | Đọc 15 nguồn mô phỏng đã hash, xác nhận provenance/scope/locator và scan malware/PII/injection; ghi review/publication decision, không nhận là quy định chính thức của trường |
| Identity/Institution Owner | Cung cấp verified institution/issuer/resolver binding cho actor grants/role validity/revocation; không tự default grants |
| AI Quality/Product Owner | Xác nhận evaluation authority, reviewed gold/critical reviewers; review metric report M2 sau actual runs |
| Release Owner | Sau M1/M2/M3 và pilot, quyết định riêng go/no-go với exact release tuple; không suy từ engineering delegation |

Reviewer ghi rõ danh tính/vai trò, thời điểm, phạm vi hash, kết luận, evidence refs,
residual risks và signed decision reference. Không phê duyệt gộp khi artifacts còn
thiếu. Nếu upstream không cung cấp provenance phù hợp, đưa exact replacement hoặc
remediated build qua cùng gate; không tự tạo “publisher signature” hoặc bỏ gate.

`SEC-CTRL-012` yêu cầu independent publish approval; `SEC-CTRL-019` yêu cầu
pin/scan/sign/provenance; `SEC-CTRL-029` cấm control owner là sole verifier của
high-risk control; `SEC-CTRL-030` yêu cầu underlying reproducible results.
Các quy định này nằm trong [security controls approved](../06-security/12_SECURITY_CONTROLS.md).

## Thứ tự tiếp tục

1. Giải quyết localhost IPC bằng scope runtime riêng trước fresh regression; giữ guards
   và giới hạn retry. Reviewer hoàn tất artifact-specific runtime/corpus dispositions từ phiếu đã chuẩn bị;
   công việc kỹ thuật không cần xin lại ủy quyền chung.
2. Chốt current frontend snapshot trước fresh browser verification; giữ các edits đang có.
3. Sau runtime/input/dependency gates, actual inference/index/canonical API integration;
   chốt exact live envelope trước launch theo required artifact packet.
4. Nghiệm thu M1 bằng positive/negative/multi-turn actual traces; tiếp M2/M3 theo
   baseline có thẩm quyền rồi đưa concrete release result cho người duyệt.

Hồ sơ chuẩn bị nghiệm thu không đồng nghĩa ứng dụng đã đủ M1–M3. Không thay đổi
trạng thái task catalog hoặc normative document để hợp thức hóa thiếu evidence.
