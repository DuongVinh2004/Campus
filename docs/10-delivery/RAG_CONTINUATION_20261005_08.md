---
document_id: "DOC-DELIVERY-RAG-CONTINUATION-20261005-08"
version: "0.1.0"
status: "not_verified"
owner: "Implementation executor"
last_updated: "2026-10-05"
---

# Browser đã kiểm chứng, DeepSeek thật đã gọi được; runtime chưa đủ clearance

## Thẩm quyền và scope

Người dùng trực tiếp phê duyệt đề xuất P-FE-BROWSER-007, giao quyền xử lý runtime/corpus từ tài nguyên sẵn có, cho phép đọc `.env` đã thêm khóa API và không yêu cầu chờ quyết định ngân sách trong lượt này. Receipt nguyên văn ở `infra/local/rag-fixture/chat-stream-20261005-08-approval.json`. Quyền đó được dùng để thực thi, không hỏi lại engineering approval chung; không tạo bằng chứng độc lập giả hoặc thay controls/acceptance thresholds.

Thực hiện tuần tự: browser007 → adapter request limits/LLM connectivity → corpus curation/runtime evidence reconciliation. Không subagent/chat khác, commit/push/deploy, reset/cleanup/deletion, DB write, index activation hay thay dependency pins. `.env` chỉ đọc riêng trong memory, không ghi đè hoặc lưu giá trị secret trong evidence.

## 1. Browser007 — passed trong scope streaming client integration

Đã xác minh Chrome for Testing153.0.8010.12, revision1243 phù hợp approved Playwright1.63.0. Browser cache không có Authenticode signature. Để xác minh nguồn bằng bytes, lấy exact-version metadata chính thức và đối chiếu **308/308 files** cache với archive HTTPS chính thức, không missing/mismatch/extra. Archive205.123.748 bytes được giữ trong ignored workspace path `downloads/campus247-browser-20261005-08/chrome-win64.zip`; không install, giải nén hay ghi vào cache ngoài workspace. Đây là official HTTPS content binding, không gọi là signed attestation.

Nguồn: `https://googlechromelabs.github.io/chrome-for-testing/153.0.8010.12.json`; artifact `https://storage.googleapis.com/chrome-for-testing-public/153.0.8010.12/win64/chrome-win64.zip`. Full hashes ở `chat-stream-20261005-08-browser-origin.json` (SHA256 `dee9dede61208068bde1d7d93e15c04f5ff4f7605cefd2b5f2ad9fb0d391d734`).

Guard03 chỉ đổi prefix output sang fresh07; runner03 chỉ đổi exact browser version assertion. Node24.19.0 và23.026 frontend dependency-file hashes được kiểm tra lại. Giữ sandbox, CDP pipe, fresh workspace profile, loopback3107/3108, proxy/renderer deny và21 assertions. **Một attempt đạt21/21 cases**, zero page/unhandled errors; positive receipt và exit0. Browser đóng bình thường; không còn tiến trình profile thử nghiệm hoặc listener3107/3108.

Phạm vi pass: success/abstention/guard rejection, failure/timeout, CRLF/CR/multiline, malformed/unknown events/status/classes/invalidUTF8/EOF, foreign IDs/wrong request, duplicate terminals, cancellation/loading/late callbacks, message citation isolation và external-request denial. Screenshot được giữ trong `chat-stream-20261005-07-run-browser-01/`.

Đây là actual ChatPage/ChatPanel/SSE client bundle với synthetic transport. Không tính là full Next production/SSR build, real retrieval hay M1. Visual inspection `citations.png` còn thấy source-status SYNTHETIC được page map thành badge active; tiêu chí validity/issuer/simulation đầy đủ của G5 còn phải xử lý trong đúng objective, không được suy ra từ21 stream assertions.

## 2. Adapter limits và LLM thật

Đã đọc `.env` theo chỉ thị trực tiếp. Provider chính là DeepSeek tại `https://api.deepseek.com`, model cấu hình `deepseek-chat`; khóa có cấu hình và **authentication probe HTTP200**. Không in khóa, token, DATABASE_URL/REDIS_URL hoặc provider reasoning. `DEMO_MODE=true` vẫn giữ nguyên; smoke không dùng factory/fallback để tránh fake success.

Bug đã sửa ở `services/api/src/campus247/infrastructure/llm/openai_adapter.py`:

- Provider payload giữ `request.max_output_tokens`, thay vì nâng các request nhỏ lên tối thiểu1024.
- HTTP timeout dùng hạn ngắn hơn; `asyncio.timeout` bao toàn bộ generate/stream provider operation, hủy và đóng client khi hết request deadline.

Thêm10 deterministic HTTP-boundary cases ở `tests/contract/ai/test_openai_adapter_limits.py`: caps16/128/2048 cho generate/stream, shorter provider timeout và cancellation/cleanup khi total deadline hết. Không thay interface, route policy, security policy hoặc price/budget controls.

**Live smoke đúng một generation qua actual adapter/provider đạt**: output chuẩn OK, provider request ID có, finish stop;22 input tokens,1 output token,843ms. Request chỉ có synthetic constant, cap16 output tokens, deadline4500ms, không retry/fallback/PII/history/corpus/DB. API key chỉ nằm trong Authorization header đến exact HTTPS provider đã cấu hình. Secret values không persist.

`/models` trả `deepseek-flash` và `deepseek-v4-pro`, không liệt kê `deepseek-chat`, nhưng generation với alias đã cấu hình thành công. Không đổi model/.env ngầm; provider alias availability không phải immutable model-version evidence hoặc quality release tuple.

Receipt: `rag-llm-20261005-08-live-smoke.json`, SHA256 `0a918c988277100d3c886947396485de416e00e9e34b89eb37ec8d26523264b2`. Connectivity pass không chứng minh app đã nối canonical real RAG, source/evidence/history/persistence hay M2/M3. Không tính estimated cost khi thiếu exact price/model binding; existing application caps không bị bỏ.

## 3. Corpus hiện có — chuẩn bị15 nguồn gốc mô phỏng

Chọn15 project-original topics trong `packages/synthetic/src/knowledge.py`, seed2026. Không dùng imported course topics vì provenance/reuse và applicability chưa được xác lập. Source generator không sửa; rerun trong memory khớp semantically.

Snapshot ở ignored `downloads/campus247-corpus-20261005-08/corpus.json`: unique source/version IDs, full content hashes, fictitious issuer/document numbers/dates, explicit synthetic disclaimer trong text, owner/audience/FIT metadata, canonical synthetic URI và expected-question/gold-citation bindings. Không có real student data hoặc official university claims.

Source lifecycle giữ **quarantined**, không fabricated `approved_by`, không publish/index/DB writes. Delegated executor curation chưa thay independent gold review hoặc Knowledge Admin approval. Bộ này dùng chuẩn bị kiểm thử cô lập, không nhận là reviewed institutional production corpus/M2 dataset. Manifest: `rag-inputs-20261005-08-corpus.json` (SHA256 `3aad18b0e129dc3bd859efecd4961849f010f068b0084884571337dbabaddf4e`).

## 4. Runtime — exact evidence đã đối chiếu, chưa launch

Rehash toàn bộ evidence references của existing independent-review-input; bind lại license04 (9/9 MKL-library byte matches là existing evidence), exact image/source/model manifests. Chuẩn bị matrix **192 Debian +10 Cargo findings** cho đúng versions và evidence refs ở `rag-inputs-20261005-08-runtime-clearance.json`, SHA256 `f79e639ff6aa1aa1286ad737a4b4734dadb5af7ccfafd66c5fcb57bc22253fe2`.

Các facts còn nguyên: reviewer null, compiled SBOM/compiled feature graph chưa verified, provenance signature chưa verified, gate open. Không gọi source lock/ELF inventory là complete compiled SBOM. Không biến hash thành publisher signature hoặc tự ký independent review. Không promote DEPS/runtime dependencies hoặc load/launch model trong khi gate chưa đóng.

Root approval đã ghi, nhưng approved `docs/06-security/12_SECURITY_CONTROLS.md` (`DOC-SEC-007`) quy định `SEC-CTRL-029`: “Control owner MUST not be sole verifier for high-risk control.” Vì vậy executor được ủy quyền không thể đồng thời tạo independent acceptance. Cần actual finding-level reviewer disposition, compiled artifact/SBOM/provenance và license acceptance; hoặc exact vetted replacement artifact có bằng chứng tương đương. Đây là thiếu evidence bên ngoài, không phải thiếu approval engineering chung.

Exact local envelope đã chuẩn bị trong matrix: một model mỗi lần,4CPU/5GiB, loopback18081/18082, read-only model mounts, internal network, inputs<=128 tokens/item, không DB/PII/externalLLM. Envelope không thay clearance và không được dùng để miễn gate.

## Verification

Mọi Python command dùng fixture3.12.14 `-B`; tests giữ artifacts, deny outbound/DNS và không đọc key để gọi provider. Live tool riêng được người dùng authorize và chỉ persist sanitized receipt.

| Command/label | Exit | Kết quả |
|---|---:|---|
| `chat_stream_20261005_08.py baseline` | 0 | Fresh preservation baseline và direct human receipt |
| `chat_stream_20261005_08.py preflight` | 0 | Dependency → catalog241 → OpenAPI34, mỗi command0 |
| `chat_stream_20261005_08.py verify-browser` | 0 |308 cache files khớp official HTTPS archive; no cache writes |
| `chat_stream_20261005_08.py browser` | 0 |21/21, no skipped/page/unhandled failures |
| `chat_stream_20261005_08.py browser-final-preservation` | 0 | Existing baseline unchanged khi kết thúc browser objective |
| `rag_llm_20261005_08.py baseline` | 0 | Exact adapter mutation scope; private env metadata |
| `rag_llm_20261005_08.py models` | 0 | Auth HTTP200; zero paid generations |
| `delegated_verify.py llm-limits-20261005-08-01 ...` | 0 |28 passed;10 new contract cases + existing LLM contract/gateway/fallback/chaos |
| `rag_llm_20261005_08.py smoke` | 0 | Actual DeepSeek output/usage/provider request evidence, no fallback |
| `rag_inputs_20261005_08.py corpus` | 0 |15 staged synthetic sources, deterministic integrity checks, no DB/index writes |
| `rag_inputs_20261005_08.py runtime` | 0 | Exact evidence bindings và202 finding rows; clearance vẫn open |
| `delegated_verify.py llm-stream-regression-20261005-08-02 ...` | 0 |54 passed: terminal SSE/result, egress và fake contract regressions |
| `chat_stream_20261005_08.py final-verification` | 0 |Dependency/catalog/OpenAPI mỗi command0 |
| `git diff --check` | 0 | Existing CRLF warnings giữ nguyên |

Read-only discovery failures được giữ trong chat: probe import ở cwd sai, missing optional search directories/document paths và success-receipt inspector ban đầu giả định failure key luôn có. Đã sửa invocation/inspection; không dùng các failures này làm pass hoặc đổi expected results. Có thay đổi `AppShell.test.tsx` xuất hiện trong Git status cuối; final scope phải tách mọi drift ngoài adapter khỏi own mutations và giữ nguyên, không restore.

Full source/task status, exact diffs/hashes và any external drift ở `infra/local/rag-fixture/chat-stream-20261005-08-final-scope.json`. **Whole RAG/M1/M2/M3 remains not_verified.** Streaming client assertions và standalone LLM connectivity là hai scope đã có reproducible success.
