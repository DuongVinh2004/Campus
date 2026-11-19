# Chặng 5 — Policy Graph RAG, bàn giao local và kiểm chứng live

Ngày 14/10/2026, Asia/Bangkok. Trạng thái: **đã triển khai và bàn giao trong phạm vi local/development, API8003 đang chạy graph, kiểm chứng 12 câu live và 2 extraction**. Người dùng duyệt trần 12,192 calls/tổng10USD, bàn giao đúng API8003 và KA002 kiểm review local. Authorization05 giữ charge và 14 unknown reservations. 11 câu trả lời có nguồn, một câu từ chối an toàn; hai ứng viên extraction còn lỗi, đã lưu verdict `conflicting` và chưa xuất bản. Không kết luận extraction tự động đạt chất lượng production hoặc đã có đánh giá độc lập bởi con người. [Runbook](POLICY_GRAPH_STAGE5_RUNBOOK_20261014.md).

## Implementation

`domain/policy_graph.py` định nghĩa Procedure, Form, PolicyDocument/Clause, OrganizationUnit, Audience, ConditionGroup ALL/ANY, Condition/predicate, Exception và EffectiveInterval. Edges requires/applies_to/handled_by/defined_by/has_exception/supersedes mang source/version/chunk/locator/hash/quote, scope và interval. Supersedes cần extent clause/audience rõ; không suy ra thay toàn văn từ ngày mới hơn. Interval là `[start,end)`; ngày pháp lý thiếu căn cứ giữ `unknown`, khác ngày acquisition và eligibility của source reader hiện có.

SQLite relational repository riêng lưu proposal nguyên bản, node/edge, toàn bộ lịch sử verdict, publication bất biến và extraction output/usage. Không ghi đè graph/version/index cũ. Source mapping được authored rõ ràng, không phải bằng chứng chất lượng LLM extraction. Candidate LLM dùng span IDs server cấp; application bind source/scope/author/snapshot, kiểm schema và giữ raw model bytes kể cả output invalid. Extraction không tự review hay publish. Dùng cùng Gateway của application, output 900 tokens/deadline tối đa 5s và per-run admission hiện có; không mở writer thứ hai.

Review/publish kiểm quyền KNOWLEDGE_ADMIN/SYSTEM_ADMIN, source readback và hash/quote/locator, cấm tác giả tự review/publish, CAS revision, preview và xác nhận gắn publisher/session/scope/proposal/verdict. Kiểm dangling/cycle, alias trùng trong cùng scope, nhóm thiếu member/span, ALL/ANY, predicate, scope, xung đột temporal và source/index mismatch. Không có rule engine tự cấp quyền hay duyệt hồ sơ từ graph.

Traversal giới hạn depth/node/edge/source reads, visited set chặn vòng lặp; lọc scope và nguồn trước neighbor/count/suggestion. Chỉ trả nguồn CURRENT/SYNTHETIC đủ quyền và interval phù hợp. Không có chế độ historical ngầm. Graph lỗi/unpublished/empty có trạng thái riêng; Research ghi event `search_policy_relations` và giữ hybrid fallback. Verifier không được cấp graph search.

Hybrid mở rộng từ anchors trong pool lexical/vector, đọc lại nguồn trước cross encoder. Chỉ bytes trùng source/version/chunk/hash/text của index mới vào pool; graph dùng tối đa một nửa pool rerank hiện có, không tăng fusion/native pair budget. Research/Verifier/context/coverage/claim gates và citation source reader tiếp tục kiểm nguồn nguyên gốc. Graph path/summary không thay citation. Graph publication/index/source fingerprints được đưa vào run snapshot và cache/resume binding.

UI tại `/knowledge/policy-graph` hiển thị edge/entity, quote, source/version/hash, ALL/ANY/members, scope, interval unknown và verdict. Ghi review, preview/confirm publish và extraction candidate đều qua API; lỗi không giả thành thành công. Runtime có graph được cấu hình mới expose aliases KA001/KA002 cho **hai knowledge admin synthetic đã tồn tại**, không cấp role mới. Sinh viên vẫn không được review; admin không được thao tác hồ sơ sinh viên. Luồng giấy xác nhận giữ preview/confirmation/idempotency. Không mở nghiệp vụ phúc khảo chặng 6.

## Graph phát triển và nguồn

Namespace mới: `infra/local/policy-graph-stage5-20261014-01/`. Graph `huce-policy-development-v1` có **25 nodes/22 edges**, 47 verdict development source review, source map từ sổ tay trang 35/39/61 và quy chế Điều 13/15. Source corpus 131 parents giữ nguyên. Index fingerprint `903531eb92b01e4ebb71ef6413b40fcba7b626e3480ddc6e3e580cfe634249fb`; source fingerprint `3fb343660e5811ab19ef9e0e0bf68446b9541918c9906e094475596e6915fe7b`.

Publication này là **Codex development source review**, không independent human assessment. Mã/phiên bản mẫu xác nhận chi tiết và hiệu lực pháp lý chưa xác minh. Sơ đồ phúc khảo OCR nhiều cột được giữ nguyên toàn đoạn. Khi review live, PDF trang61 đã được render và xem trực tiếp: kênh đăng ký, đóng lệ phí và ngoại lệ vấn đáp/thực hành khớp câu trả lời; trang này không ghi mức tiền. Không sửa OCR/source/index hay chuyển sơ đồ thành rule thực thi. Graph hỗ trợ discovery, không quyết định eligibility.

## Kết quả và bằng chứng

| Kiểm chứng | Kết quả | Bằng chứng |
|---|---|---|
| Backend graph + multi-agent + certificate regression | 137 passed, 33.05s | `tests-04.xml` |
| Bootstrap/proxy/real source/admin/student wiring | 10 passed, 3.69s; 1 bài mới, 9 bài lặp | `tests-05.xml` |
| Backend distinct cases trong reports04–07 | **174 passed**, 0 failed | identity `(classname,name)`; không cộng lặp; 3 runner tests terminal qua riêng |
| UI graph/knowledge/certificate | **17 passed**, 2.14s | `frontend-tests-04.xml` |
| Scoped TypeScript graph route/component | exit 0 | `tsconfig.policy-graph-20261014.json` |
| Real retained source traversal/readback | **10/10 passed**, 0 issues/hash mismatch | `source-verification-03.json` |
| Source traversal latency, 9 câu có traversal | median 12ms, range 11–29ms | local readback, không native/LLM latency |
| Provider/native delta của source verification | 0 calls / 0 inference / 0 HTTP / 0 tokens; conservative cost delta 0 USD | before/after ledger trong report |
| Fresh live graph-assisted answers | **12 ca, 0 system errors, 11 grounded + 1 safe refusal** | `live-case-001-01.json` đến012; graph traversal ở cả12 |
| Live history/citation readback | **12 history khớp, 12 citations đúng hash** | per-case reports; 11 câu có factual citations |
| Codex/source review live | correctness2: **12/12**, completeness2: **11/12**, entailment2: **11/11** câu có citation | `live-quality-review-02.json`; ca007 safe refusal còn chung chung |
| LLM extraction | **2 HTTP200, 2 cần sửa, 0 auto publication** | raw giữ trong DB; duplicate alias/quan hệ sai chiều/thiếu căn cứ span; verdict `conflicting` qua UI KA002 |
| Frontend graph production build trong namespace mới | **passed**, guard hash giữ nguyên | `frontend-build-01.json`; frontend3004, build ID `lE8nXBam0_hMdbfzXf6qx` |
| Browser QA, API đang phục vụ graph | **passed trong phạm vi kiểm tra** | `browser-verification-01.json`: ALL4/ANY2/source/verdict, ghi2 reviews, xuất bản khóa |
| Retained stage1/history/citation sau restart | **passed, 0 paid/native delta** | `stage5-after-live-readback-01.json` ở namespace multi-agent; READY5audit/HTML hash giữ |
| Independent human assessment, production readiness | **not_verified** | không suy từ synthetic tests |

Ba lượt chạy nhóm UI trước đó còn failed ở `localStorage.clear()` trên Node 26 (một lượt chỉ có terminal output; hai report `frontend-tests-02.xml`/`03.xml` giữ nguyên). Harness riêng dùng Storage thật của jsdom origin mới; không sửa expected result/test nghiệp vụ. Full-project TypeScript còn bốn lỗi có sẵn `ByRoleOptions.exact` ở `AppShell.test.tsx`; scoped graph check qua, không gọi đây là full frontend clean build. Hai lượt shell sandbox mặc định ban đầu bị ngắt sau khi không hoàn thành; không dùng làm bằng chứng pass. Các lượt kiểm chứng sau được chạy với quyền thực thi local cho exact namespace fixture/report, không thay nguồn hoặc database cũ.

## Ngân sách và runtime

Trước live, `live-preflight-01.json`: 11,994/12,000 provider calls, còn 6, dưới admission 12/run. Conservative charge 4.4043015/10 USD, invoice unknown, 14 unknown reservations được giữ. Native 7,976 HTTP / 4,630 inference / 797,145 tokens trên caps 20,000/10,000/5,000,000; conservative HTTP floor cũ giữ nguyên.

Người dùng đã xác nhận **192 provider calls** bổ sung, trần **12,192**, vẫn tổng **10 USD**. `resource-authorization-05.json` liên kết authorization04 và giữ nguyên before/pending records; tests chuyển cap qua. `live-preflight-03.json` admission true, còn198 calls và5.5956985USD, không đề xuất tăng cap thêm. Chuẩn bị 12 query runs + 2 extraction runs + 2 repair envelopes, mỗi envelope admission12 calls/150,000 reserved tokens, conservative reservation tổng2.88USD. Đây là upper bound theo policy hiện có, không invoice/giá thực tế. Report preflight02 có nhãn proposed cap không đúng sau extension; giữ nguyên evidence và sửa nhãn ở report03, **không có cap12384 được áp dụng**. Không hạ admission hoặc refund/reset.

Sau xác nhận trực tiếp `Cho phép bàn giao đúng API8003`, helper reverify parent/creation/command/listener và quiet state rồi dừng đúng worker10336/wrapper13108, khởi động lại cùng DB/history/ledger. Receipt `20261014T003326234065-live-launch.json`: API wrapper1888/worker5480, graph `huce-policy-development-v1`, frontend3004. `runtime-active-01.json` xác minh nguyên native21908/proxy13460/frontend3003 worker23056/frontend3004 worker18312 và cả6 listeners. Backups business/history/runs giữ nguyên. Guard frontend mới byte-for-byte (`8f0886...af2eae6`). Rejection trước đó và receipt kết quả handoff được giữ; không bypass. KA002 chỉ tiếp tục sign-in sau phép trực tiếp và lưu hai verdict mâu thuẫn. API là paid writer duy nhất, không writer song song. Không commit/push/deploy/delete/reset/cleanup.

Campaign dùng **111 provider calls**, 243,937 input tokens/11,770 output tokens theo ledger, conservative charge mới **0.0873051USD**. Ledger cuối **12,105/12,192 calls**, **4.4916066/10USD**, còn87calls/5.5083934USD; actual invoice unknown, nguyên14unknown reservations. Native delta64HTTP/65inference/8,654tokens; cuối8,040/4,695/805,799 trên caps không đổi. Hai repair envelopes không dùng. Latency từ dispatch đến kết thúc stream: **p50 16,563ms, p95 24,250ms**; pacing/readback tách riêng trong từng report, graph readback không được gọi là latency LLM. Nguồn/index/publication v1 và stage1 business giữ nguyên; history/run stores append12conversations/evidence, graph store append2raw candidates/usage/2review verdicts.

Chất lượng extraction chưa đạt auto-publication: ứng viên xác nhận tạo PolicyDocument/Clause trùng label, đảo `defined_by`, thiếu Form và quan hệ lấy dấu cần chỉnh; ứng viên phúc khảo chỉ lấy một fragment lệ phí, hướng/types `defined_by` và audience heading-only cần thêm căn cứ. Cả hai chỉ là candidates, không tham gia active retrieval. Đây là giới hạn quan sát được của hai mẫu hẹp, không chứng minh extraction ALL/ANY đầy đủ. Ca007 không bịa số tiền nhưng refusal chưa chỉ rõ nguồn thiếu mức tiền; ca009 đúng đủ bốn điều kiện, cách nói “không” trực tiếp sẽ rõ hơn. Traversal có thể mở rộng cả anchors thứ cấp của hybrid; nguồn gốc, rerank, coverage và claim gates vẫn là điều kiện bắt buộc.

Boundary source bổ sung: legacy citation bytes vẫn được giữ để đọc lịch sử, nhưng graph của current source/index snapshot không nhận ref ngoài current rows chỉ vì hash/quote hợp lệ. Test mới và `source-verification-03.json` qua 10/10, zero provider/native delta. `tests-06.xml` 47passed kiểm cap chain/API; `tests-07.xml` 37passed kiểm graph/source/current-vs-legacy và wiring, các ca có lặp không cộng thành fresh unique runs.

Thời gian thực thi có đo cho tests/source readback được ghi riêng phía trên. Codex active time, external wait và tổng calendar time chưa có telemetry liên tục, ghi **unknown**; không suy từ ước lượng thiết kế 12–24 giờ hoặc gộp latency source readback thành thời gian hoàn thành chặng.
