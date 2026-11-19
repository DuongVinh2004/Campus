---
document_id: "DOC-DELIVERY-CHAT-STREAM-20261004-02"
version: "1.0.0"
status: "not_verified"
owner: "Campus 24/7 Engineering"
last_updated: "2026-10-04"
---

# API/UI chat streaming — implementation after scoped approval

Objective duy nhất: **API/UI phản ánh đúng kết quả chat streaming theo contracts**.
Backend và contract đã verified bằng 58 deterministic offline tests. Parser/UI
đã triển khai cùng tests nhưng frontend runtime, typecheck và browser **not_verified**.
Vì vậy toàn bộ objective chưa được nghiệm thu đầy đủ. Không tuyên bố RAG/model
inference, chất lượng grounded hoặc production readiness từ kết quả offline.

## 1. Task packet và authority

Direct request trong văn bản đính kèm; human reply **“phê duyệt”** chấp nhận
P-CONTRACT-STREAM-001 đã trình bày trong report
`RAG_CHAT_STREAM_IMPLEMENTATION_20261004.md`. Report và evidence lượt 01 được giữ
nguyên. Decision record mới:
`docs/00-governance/CHAT_STREAM_CONTRACT_DECISION_20261004.md`.

Đã reconcile DOCUMENT_CONTROL, DECISION_REGISTER, approved requirements,
API_CONVENTIONS/error/citation/persistence contracts, AI/RAG package, reality
audit và execution plan 0.2.0 trước implementation. Không thay quyền security,
thresholds, StreamGuardrail, retrieval/model/identity, migrations hoặc pins.
Đây là direct-request packet, không tự đổi trạng thái catalog task/dependency.
Approval contract không đồng nghĩa independent review hay production approval.

Contract changes được duyệt: sửa capability traceability, bind chính xác năm
SSE events, final content/status/class và citation identity mapping; khôi phục
PRD response-class reference. UUIDv7 public citation và CIT-local claim reference
là hai identity domains khác nhau, được nối bằng immutable mapping.

## 2. Trước/sau

| Trước, từ actual-router observations lượt 01 | Sau |
|---|---|
| Graph abstained/safe_failure vẫn báo completed thông thường | Application converter phân biệt answered/abstained và failure; invalid/missing output phát failed. |
| `message.error` mang raw exception | Chỉ `message.failed`, direct safe problem theo existing schema; fixed guidance, request correlation, không raw exception/rejection pattern. |
| Started ID khác ID được lưu | Reserve ID một lần; started, citations, persisted final và completed dùng cùng ID. |
| Guard reject sau khi draft đã phát | Giữ nguyên guard; validate whole runner draft trước delta; rejected draft không công bố hoặc lưu làm answer. |
| Citation metadata/ID chưa bind rõ | Typed server metadata, mapping CIT-local → UUID; thiếu/invalid provenance thì abstain; không đoán title/version/locator/confidence. |
| UI đọc data lines, bỏ terminal và nuốt lỗi | Parser event boundaries; lifecycle validates binding/status/class; terminal thay toàn bộ provisional text; malformed/unknown/EOF thu hồi nội dung và hiện hướng xử lý. |
| UI có thể coi provisional là final | Provisional label; citations/actions/feedback chỉ khả dụng sau final; abort hiện chưa xác nhận. |

Không có runner thì INTEGRATION_NOT_ENABLED; không tạo fake echo. Runner được gọi
một lần, không blind retry/regeneration. Last-Event-ID bị từ chối trước user save
và execution; alternate transcript link được trả theo binding đã duyệt.

Runner hiện trả cả draft; delta là chia nhỏ **validated whole draft**, không phải
provider token streaming. Typed result conversion nằm trong application; route
serialize và UI hiển thị. Citation mapping được lưu với final MessageRecord trong
repository hiện có; chưa có migration hay nghiệm thu durable database storage.

## 3. Exact write scope

Baseline exclusive: `infra/local/rag-fixture/chat-stream-20261004-02-baseline.json`,
1458 pre-existing covered files; mọi planned path được canonical/reparse checked.
Các tracked edits so với baseline được lưu thành incremental diffs trong final
manifest; `git diff` so với HEAD còn bao gồm user changes từ trước lượt này.

| Exact files | Mục đích |
|---|---|
| `contracts/openapi/v1/openapi.yaml` | SSE schema ref, unique capability traceability; không sửa validators. |
| `contracts/json-schema/chat/stream-event.schema.json` (new) | Năm event/payloads, valid terminal/class combinations, citations và safe problem refs. |
| `docs/04-architecture/contracts/API_CONVENTIONS.md` | Approved final replacement/IDs/citations/compatibility binding. |
| `docs/01-product/PRD.md` | Khôi phục section 6.1 response classes theo approval. |
| `docs/00-governance/CHAT_STREAM_CONTRACT_DECISION_20261004.md` (new) | Ghi approval chính xác và citation reconciliation. |
| `services/api/src/campus247/application/conversation/stream_result.py` (new) | Typed immutable final result, provenance validation, safe outcome conversion. |
| `services/api/src/campus247/application/conversation/messages.py` | Reserved IDs, final status/class và immutable citation snapshots. |
| `services/api/src/campus247/presentation/chat.py` | Approved transport events, safe problems, guard-before-publication, persistence consistency. |
| `apps/web/src/features/chat/sse.ts` (new) | UTF-8 decoded framing, protocol validation và message lifecycle. |
| `apps/web/src/app/chat/page.tsx` | Terminal replacement, safe failure/unknown, per-attempt IDs/loading/abort, final citation selection. |
| `apps/web/src/features/chat/ChatPanel.tsx` | Provisional/unknown/stopped labels; prevent provisional actions/citations/feedback. |
| `tests/api/test_chat_sse.py` | Actual router + identity middleware, deterministic in-memory results/faults, schema assertions. |
| `tests/unit/conversation/test_stream_result.py` (new) | Grounded mapping/provenance, guard conversion, immutable saved result. |
| `apps/web/src/features/chat/sse.test.ts` (new) | Fragmented frames/UTF-8, malformed/unknown/EOF, replacement/citations. |
| `apps/web/src/app/chat/page.test.tsx` | Lifecycle UI tests; giữ existing authentication assertions. |
| `apps/web/src/features/chat/ChatPanel.test.tsx` | Provisional/unknown/stopped action isolation. |
| `infra/local/rag-fixture/chat_stream_20261004_02.py` (new) | Fresh retained offline harness và final preservation audit. |
| Report này (new) | Bàn giao có giới hạn verification rõ ràng. |

Evidence additions dùng prefix `infra/local/rag-fixture/chat-stream-20261004-02-`:
baseline, preflight, suite-01/suite-02 JSON/log/artifacts/temp, final-verification,
final-scope. Không dùng lại labels đã tồn tại; không cleanup artifacts.

## 4. Acceptance → evidence

Test oracle: approved API_CONVENTIONS 8.1, PRD 6.1 và JSON schemas; không dùng old
faulty stream làm oracle. Existing successful router fixture được cấu hình explicit
synthetic runner vì approved absent-runner semantics là failure; positive assertions
được giữ và bổ sung separate missing-runner test. Không nới expected/thresholds.

| Tiêu chí | Evidence / trạng thái |
|---|---|
| A: events/payloads, answered/abstained/failed | Actual router tests + Draft202012 schema/format validation; schemas check_schema; invalid status/class negatives. Verified offline. |
| A: safe errors/no raw sensitive text | Sync timeout/runtime error, async timeout, invalid/safe_failure state, missing runner, retrieval unavailable; synthetic exception sentinels không vào stream. Verified offline. |
| A: final IDs/content/citations/persistence | Router grounded-citation test kiểm started=added=completed=saved ID, exact final metadata/content; immutable mapping và duplicate-ID test. Verified in-memory. |
| A: rejected draft không là final answer | Existing StreamGuardrail unchanged; actual router reject sentinel không xuất hiện trong delta hoặc saved message; no grounded citations. Verified offline. |
| A: auth/ownership/no retry | Existing 401/404/403 regressions; resume zero execution/zero writes; faults call runner một lần. Verified offline. |
| C: disconnect/cancel/storage faults | Direct endpoint body iterator: disconnect trước started/runner/delta; CancelledError sau delta; assistant persistence failure sau provisional → failed; user persistence failure pre-stream safe problem. Verified cases, không claim mọi race/live transport. |
| B/C: fragmentation, UTF-8, multiline/CR/LF/CRLF | Parser tests viết đầy đủ, source reviewed. Runtime not_verified. |
| B: terminal replacement, UNKNOWN/error/abstention/loading/message isolation | Parser/Page/ChatPanel tests viết, source reviewed; final text replaces, old turns preserved, citations locked until terminal. Runtime/browser not_verified. |
| Preservation | Final manifest: zero outside-scope covered-file hash mismatches; exact incremental diffs và retained new-file hashes. |

58 backend tests bao gồm `tests/api/test_chat_sse.py`, `test_problem_details.py`,
`tests/unit/agent/test_stream_guardrail.py`, `tests/unit/conversation`,
`tests/integration/conversation/test_messages.py` (in-memory) và `tests/architecture`.
Không bootstrap settings/dotenv, không truy cập DB/container/network/provider.

## 5. Runtime, commands, exit codes và failures

Chỉ dùng approved `infra/local/rag-fixture/.venv/Scripts/python.exe -B`, Python
**3.12.14**. Guards deny network/DNS, credential-file reads, deletion và writes
ngoài canonical workspace. Không chạy PATH Python/Node, install hay thay pins.

| Command/action | Exit | Bằng chứng |
|---|---:|---|
| Exclusive current baseline, prior manifest/hash reconciliation | 0 | `chat-stream-20261004-02-baseline.json`; prior final SHA `738fea8840ca6997100d99e16fe0fc357ac9f929d2545998efe21f71ff47bd6c`. |
| Initial OpenAPI run after metadata patch | 1 | Duplicate `API-OPS-001`; retained observation trong preflight. Sửa thành API-CAPABILITY-001/002, giữ existing metrics ID. |
| Python `chat_stream_20261004_02.py preflight` | 0 | Individual dependency/catalog/OpenAPI exits 0/0/0, captured outputs. |
| Python `chat_stream_20261004_02.py suite-01` | 0 | 54 passed, 4.04s; retained JSON/log/temp/artifacts. |
| Python `chat_stream_20261004_02.py suite-02` | 0 | 58 passed, 4.73s; thêm router citation, async timeout và schema negative tests; SHA `f13167c45fbffa2a904bf119b24692b106ff987b375790653b1afb5b7a57722b`. |
| Read-only baseline summary via approved Python | 1 → 0 | cp1252 stdout UnicodeEncodeError; UTF-8 stdout correction. Không phải product-test failure, không có mutation từ command lỗi. |
| Python `chat_stream_20261004_02.py final-verification` | See evidence | Dependency → catalog → OpenAPI, individual exit/log trong fresh final-verification JSON. |
| Python `chat_stream_20261004_02.py final-scope` | See evidence | Test evidence reference → git diff --check → diff names → status → exact hash/scope checks. |

Final gates không rerun blindly các suite labels. Backend/product bytes không đổi
sau suite-02; sau đó chỉ chỉnh frontend test ES5 compatibility, harness và report.
No implementation-test failure/repair loop. Initial contract metadata failure và
tooling stdout failure được giữ, không bỏ hoặc kể thành success.

## 6. Preservation và giới hạn

Final evidence:
[verification](../../infra/local/rag-fixture/chat-stream-20261004-02-final-verification.json),
[scope/hashes/diffs](../../infra/local/rag-fixture/chat-stream-20261004-02-final-scope.json).
Manifest kiểm từng covered pre-existing file, chỉ cho phép 10 exact existing
files thay đổi. 1448 covered files ngoài các edits đó giữ nguyên; không restore
từ manifest. Pre-existing trusted runner imports/signature/call của chat.py giữ
nguyên và được assert riêng. Dirty retrieval/graph/dependency/migration changes
của người dùng được giữ nguyên; không xử lý để làm git status sạch.

`.env.example` excluded có chủ ý; ignored credential/model/runtime paths không đọc
và không tuyên bố hash-verified. Git metadata, backups và artifacts không bị xóa.
Không commit/push/deploy/reset/clean, subagent/chat creation hoặc external message.

Chưa xác minh/ngoài objective:

- Frontend Node/package runtime chưa được verified/approved; không có lockfile
  frontend trong scope đã kiểm. TypeScript/Vitest/build/browser chưa chạy; source
  review không thay thế runtime evidence. Không cài thêm để vượt gate.
- Real retrieval/model grounding, corpus trust, eval quality, end-to-end latency,
  live network cancellation và sync-runner deadline enforcement chưa kiểm. Chỉ
  timeout fault injection; sync runner vẫn có thể giữ event loop.
- Durable database persistence và transcript GET endpoint chưa được triển khai
  trong chat router. Link lịch sử không chứng minh endpoint hiện khả dụng; UI
  giữ hướng hỗ trợ an toàn và không tự regeneration.
- Mapper tin application graph terminal cho tool/action/handover. Real execution,
  uncertain outcomes và handover receipt cần objective riêng; current graph có
  simulation paths, stream class label không chứng minh side effect hay receipt.
- Grounded candidate thiếu provenance sẽ abstain; implementation này không sửa
  retrieval để sản sinh provenance hoặc nâng trạng thái nguồn/corpus.

Bước tiếp theo: verified frontend runtime để chạy typecheck/parser/component/page
tests và browser acceptance; sau đó riêng objective citation provenance/transcript
storage/real-runtime với approval và independent review áp dụng. Không mở rộng
RAG pipeline trong lượt streaming này.
