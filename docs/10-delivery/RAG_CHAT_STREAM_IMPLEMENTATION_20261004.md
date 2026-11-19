---
document_id: "DOC-DELIVERY-RAG-CHAT-STREAM-20261004"
version: "0.1.0"
status: "draft"
owner: "Codex — streaming implementation execution"
approvers: []
last_updated: "2026-10-04"
---

# API/UI chat streaming — execution blocked at contract preflight

**Kết quả: `blocked`, chưa sửa code sản phẩm.** Đã bảo toàn baseline, chạy
preflight, kiểm chứng hành vi router bằng synthetic fault injection và chạy
15 regression tests hiện có. Đây không phải nghiệm thu streaming hoặc real RAG.
Không có DB/container/provider/model inference, install, commit hoặc cleanup.

## 1. Task packet và quyền thực thi

Objective duy nhất: “API/UI phản ánh đúng kết quả chat streaming theo contracts
hiện có”, theo direct human request trong chat này ngày 2026-10-04. Đây không
phải execution của một catalog task; không đổi task lifecycle/dependencies.
Engineering thông thường đã được giao, không yêu cầu approval chung lần nữa.

Prospective product scope đã resolve/read trước mutation:

- `services/api/src/campus247/presentation/chat.py` (dirty từ trước).
- `apps/web/src/app/chat/page.tsx`.
- `apps/web/src/features/chat/sse.ts` (helper mới nếu cần).
- `apps/web/src/features/chat/sse.test.ts` (test mới nếu cần).
- `tests/api/test_chat_sse.py`.
- `apps/web/src/app/chat/page.test.tsx`.

Các paths này **chưa sửa/tạo**. Baseline giữ nguyên current text của files đã
tồn tại và pre-existing diff của `chat.py`; không suy ra ownership từ Git HEAD.
Không thay retrieval/model/identity/migrations/dependencies/StreamGuardrail.
Helpers application hoặc persistence bổ sung phải được chốt exact paths nếu
proposal bên dưới được duyệt; không đặt domain decisions vào route/UI.

## 2. Reconcile và blocker có thẩm quyền

Đã đọc root AGENTS, DOCUMENT_CONTROL, DECISION_REGISTER, contract indexes,
API_CONVENTIONS, ERROR_MODEL, error/citation schemas, OpenAPI chat operation,
DATA_MODEL và phần message trong DATA_DICTIONARY, idempotency/event contracts,
AI package index, AI_SYSTEM_SPEC, AGENT_STATE_MACHINE, prompt/output governance,
RAG_PIPELINE v1.1, MEMORY_POLICY, chat/citation UX, approved requirements/PRD,
audit và execution plan **0.2.0**, source/tests liên quan. Không có nested
AGENTS khác trong source/test scope được phát hiện.

Contract/AI indexes có approval cho synthetic implementation; một số artifacts
con vẫn mang header reviewed. Report không tự đổi headers hoặc coi draft plan
là approval của một behavior mới. Các blocker dưới đây có evidence độc lập.

### B-CONTRACT-PREFLIGHT-001 — OpenAPI validation thất bại

`contracts/tools/validate_openapi.py` exit **1**:
`GET /v1/capabilities: invalid x-contract-id`.

Hai operation `GET /v1/capabilities` và `GET /v1/operations/capabilities` đều thiếu
`x-contract-id`, `x-requirement-ids`, `x-control-ids`, `x-test-ids`. Validator dừng
ở lỗi đầu tiên; không khẳng định các lỗi sau đã được validator thực thi.
Hai files contract/validator là clean so với Git; lỗi này có trước lượt hiện tại.

Nguồn dừng: [contract README](../04-architecture/contracts/README.md), mục 4:
“Agent MUST NOT bắt đầu code … contract có lỗi parse/validate.”
AGENTS yêu cầu chạy applicable preflight trước mutation và không tự sửa
contracts. Vì đây là normative/preflight blocker, không phải live-runtime
blocker, quy tắc tiếp tục offline khi live gate thiếu không miễn bước này.
Chỉ fresh report/evidence phục vụ bàn giao được tạo; product code giữ nguyên.

### B-SSE-FINISH-001 — chưa có payload schema/enum cho kết thúc

API_CONVENTIONS mục 8 và OpenAPI API-CONV-004 cùng xác định năm events:
`message.started`, `message.delta`, `citation.added`, `message.completed`,
`message.failed`. Completed phải có final message ID, citations, finish status;
failed sau headers phải có safe problem. Delta không phải final grounded answer.

OpenAPI chỉ mô tả stream bằng string; không định nghĩa tên field, enum của
finish status, payload `citation.added`, hay final replacement text khi abstain.
Agent Terminal enum định nghĩa domain terminal nhưng không định nghĩa wire
mapping. Không có contract cho `message.error` hoặc `message.abstained`.
Không tự thêm event/field/enum để giải quyết gap này.

### B-CITATION-MAPPING-001 — hai miền citation IDs chưa được reconcile

Approved RAG_PIPELINE v1.1 mục 7 dùng `citation_id: CIT-<turn-local-sequence>`;
API citation schema yêu cầu `citation_id` là UUIDv7. RAG metadata còn dùng
`title`, `section_path` array; API dùng `source_title`, `locator.section_path`
string và yêu cầu `version_label`, `source_status`. Chưa có approved mapping
giữa hai representations. Graph hiện dùng `CIT-001`; route tự dựng `cit-1` từ
candidates, không phải authoritative citation resolver.

Không chọn một phía, sinh UUID giả, bịa provenance hoặc sửa schema để tests pass.
Đây là contract mismatch ảnh hưởng citations trong final payload của objective.

### B-RESPONSE-CLASS-001 — upstream taxonomy reference không resolve

Approved `requirements.yaml` REQ-F-CHAT-002 yêu cầu exactly one response class
“defined in PRD section 6.1”; PRD hiện không có section 6.1 hoặc danh sách đó.
REQ-F-CHAT-005 có `safe_refusal | clarification_request`, và CHAT-001/003 có
`system_error`/`grounded_answer`, nhưng không đủ exhaustive mapping cho các
agent terminals/tool responses. Không đồng nhất graph terminal, transport event
và product response class bằng phỏng đoán.

## 3. Concrete proposal để review — chưa có hiệu lực

### P-CONTRACT-STREAM-001

Chốt một SSE payload schema riêng, reference tại API-CONV-004; giữ năm event
names hiện có. Proposal tối thiểu:

1. `message.started`: `{conversation_id, message_id}`; định nghĩa rõ message ID
   được reserve server-side và giữ nguyên đến persisted final assistant message.
2. `message.delta`: `{seq, delta}`; seq integer dương tăng đơn điệu trong attempt;
   text provisional, không bật citations/action/feedback như final.
3. `citation.added`: citation mapping đã reconcile, gắn đúng message/turn; chỉ
   hiển thị như nguồn đã xác thực sau terminal completion.
4. `message.completed`: `{conversation_id, message_id, status, content, citations}`.
   `status` mang graph finish enum `answered | abstained | completed | cancelled |
   handed_over`; `content` là **toàn bộ safe final text** đã validate. UI thay toàn
   provisional text bằng `content`, không nối thêm. Abstained không trở thành
   answered; rejected content không lưu như grounded answer. Response class là
   taxonomy riêng do upstream quyết định, không suy ra chỉ từ tên event.
5. `message.failed`: `data` là trực tiếp error.schema.json problem object,
   không wrapper tự chọn; generic INTERNAL_ERROR 500 hoặc DEPENDENCY_UNAVAILABLE
   503 theo outcome có căn cứ, fixed safe Vietnamese guidance. `retryable=false`
   khi không chứng minh side effects chưa commit; không raw exception/guard reason.
6. Unknown event/status/malformed JSON, sai sequence/ID và EOF trước terminal
   không trở thành success. Client thu hồi provisional text/citations của đúng
   attempt, báo trạng thái UNKNOWN/lỗi an toàn, telemetry chỉ event/status code.
   Unknown fields được ignore. Fragmentation, UTF-8, CR/LF/CRLF, comments và
   multi-line `data` được parse tại blank-line event boundary.
7. Application chuyển AgentState/guard outcome thành typed presentation result;
   route chỉ serialize, UI chỉ render. Không blind retry/re-run graph. Cần reserve
   final ID qua conversation service để started/completed/persistence nhất quán.
   Cancellation/disconnect trước validation không ghi partial assistant answer.

Citation proposal: giữ UUIDv7 làm durable API citation ID; thêm explicit
`turn_citation_id` (ví dụ `CIT-001`) trong stream citation representation và
immutable server-side bundle mapping. UI marker/claim dùng turn ID, resolver và
persistence dùng durable ID. Missing mapping/provenance làm grounded response
fail closed, không tạo defaults. Đây là proposal cần Architecture/Knowledge
approval để reconcile RAG với API; chưa sửa RAG/schema/citation builder.

Exact normative change candidates, **chỉ sau approval đúng scope**:

- `contracts/openapi/v1/openapi.yaml`: bổ sung validated traceability cho hai
  capability operations; bind SSE payload schema tại API-CONV-004. Không đổi auth,
  resource behavior hoặc nới validator. Chỉ gắn existing IDs sau trace review;
  không tự tạo requirement/control để làm validator xanh.
- `contracts/json-schema/chat/stream-event.schema.json` (new): schema của proposal.
- `docs/04-architecture/contracts/API_CONVENTIONS.md`: finish status, final
  replacement, IDs/citation mapping, unknown-event behavior và traceability.
- Một accepted mapping decision cho API UUID và RAG turn-local citation IDs;
  exact decision-record path phải được chốt trước mutation.
- Upstream owner khôi phục/clarify response-class baseline ở PRD theo
  REQ-F-CHAT-002; không tự thay product requirement hoặc đoán tool classes.

Các changes cần product/architecture approval theo DOCUMENT_CONTROL và AGENTS.
Không yêu cầu approval lại cho coding thường; không xin thay safety controls,
security policy, thresholds, pins hoặc quyền live runtime.

## 4. Trước/sau và evidence thực thi

Code trước/sau **không đổi**, vì gate dừng trước product mutation. Actual router
được gọi tại endpoint boundary với synthetic IdentityContext, in-memory
ConversationMessageService, deterministic AgentState/faults. Không bootstrap
settings/dotenv, không DB, không network hoặc real model. Probes ghi observations,
không dùng faulty output làm expected acceptance oracle.

| Case | Quan sát actual router | Acceptance implication |
|---|---|---|
| answered synthetic | started/delta/completed, 2 messages, final ID được lưu, started ID khác final ID | Happy path hiện có; không chứng minh finish class/citations quality. |
| graph abstained/no source | completed vẫn `status: completed` | Không phân biệt abstention. |
| graph safe_failure | completed vẫn `status: completed`, lưu assistant | Failure bị chuyển thành completion. |
| runner timeout và RuntimeError | `message.error` với raw synthetic exception text; chỉ lưu user | Không tuân allowed SSE event/safe problem. |
| stream guard rejection | synthetic blocked sentinel có trong deltas rồi `message.abstained`; lưu safe fallback | UI hiện tại bỏ event nên có thể giữ rejected provisional text. |
| disconnect | chỉ started, chỉ lưu user | Không ghi partial ở probe đã kiểm. |
| cancellation sau delta | không completed, chỉ lưu user | Không ghi partial ở probe đã kiểm. |
| foreign owner | HTTP403, không ghi message | Ownership regression observation pass. |

Frontend source hiện parse từng data line, bỏ event names và nuốt JSON error;
không thay nội dung theo terminal replacement. Đây là source inspection;
malformed/fragmented SSE và browser rendering **not_verified**. Không chạy
Node/frontend/browser vì chưa có verified/approved runtime scope cho lượt này.

| Tiêu chí người dùng | Evidence / trạng thái |
|---|---|
| A: SSE payload + answered/abstained/failed | Probes tái hiện lỗi; implementation blocked bởi B-SSE-FINISH-001. |
| A: safe problem, raw exception không expose | Hiện vi phạm qua sentinel synthetic; chưa sửa. |
| A: final IDs/persistence/rejected content | Final ID được lưu nhưng started khác; guard lưu fallback, phát draft trước reject; chưa nghiệm thu. |
| A: ownership/no blind retry | Foreign-owner probe 403/zero messages; harness không retry graph/provider. |
| B: parser/terminal/errors/provisional/unknown | Source inspected; code/runtime tests not_verified. |
| C: answer/no source/fault/guard/disconnect/cancel/ownership | 9 offline observations đã chạy, không đồng nghĩa all acceptance pass. |
| C: fragmented/malformed/late frontend failure | Chưa có parser implementation; not_verified. |
| D: preservation | Exclusive baseline + final scope rehash, current pre-existing `chat.py` diff giữ nguyên. |

## 5. Commands, runtime, exits và retained artifacts

Tất cả Python: `infra/local/rag-fixture/.venv/Scripts/python.exe -B`, **3.12.14**.
Không dùng PATH Python hoặc cài runtime/package. Harness deny network/DNS,
credential-file reads và deletion; temp/log paths dùng fresh workspace labels.
Không sửa test expected outputs. Không có product repair attempts.

| Command | Exit | Evidence |
|---|---:|---|
| canonical/path/reparse + prior manifest/hash reconstruction + exclusive baseline | 0 | [baseline](../../infra/local/rag-fixture/chat-stream-20261004-01-baseline.json); 1,449 prior files rehashed. |
| Python `scripts/verify_dependencies.py` | 0 | Approved exact pins/closure/artifact hashes. |
| Python `tasks/tools/validate_catalog.py` | 0 | VALID 241 tasks / 10 phases. |
| Python `contracts/tools/validate_openapi.py` | 1 | Pre-existing capabilities contract metadata failure; retained. |
| `git diff --check` initial | 0 | Pre-existing CRLF warnings only. |
| Python `chat_stream_20261004_01.py preflight` | 1 | [preflight](../../infra/local/rag-fixture/chat-stream-20261004-01-preflight.json), individual exits 0/0/1. |
| Python `chat_stream_20261004_01.py probes` | 0 | [9 actual-router observations](../../infra/local/rag-fixture/chat-stream-20261004-01-probes.json). |
| Python `chat_stream_20261004_01.py tests` | 0 | [15 passed in 4.32s](../../infra/local/rag-fixture/chat-stream-20261004-01-tests.json). |
| Final dependency → catalog → existing regressions evidence → diff check → diff names/status → hash/scope | See final manifest | [final scope](../../infra/local/rag-fixture/chat-stream-20261004-01-final-scope.json). |

Existing tests run: `tests/api/test_chat_sse.py`,
`tests/unit/agent/test_stream_guardrail.py`, `tests/api/test_problem_details.py`,
`tests/unit/conversation`. Existing tests pass while observations show defects;
therefore these tests do not prove the requested streaming acceptance.
Do not rerun blindly using these labels; keep logs/temp/failure evidence.

Preservation: prior manifest verified SHA-256
`5e99af64989132a12cfb6bde977f010edba2c521edd2d0b5bfa522a9b8a4156b`;
reconstructed hashes use prior baseline, **current_plan_sha256** for plan 0.2.0,
new_file_hashes and prior final-manifest hash. `.env.example` deliberately excluded
from current reads; credential/runtime/model ignored paths are outside hash
coverage, not reported as verified. Manifest was never used to restore files.

Actual additions only: this report, exclusive baseline, fresh evidence harness,
preflight/probe/regression/final-verification/final-scope JSON and retained test
artifacts. Exact additions/hashes and command outputs are in final scope; tracked
diff set and every covered pre-existing file must remain unchanged.

## 6. Bàn giao

Verified: preservation preflight, dependency/catalog gates, 15 old regressions,
9 router observations và các exact normative gaps. **Objective chưa completed.**
Not verified: repaired API/UI streaming, frontend/browser, real RAG inference,
grounded quality, production readiness. Không khẳng định MoMo/Vietnam Airlines
dùng kiến trúc/provider nào; đây chỉ là tham chiếu trải nghiệm theo yêu cầu.

Bước tiếp theo vẫn là objective streaming này: chốt proposal contract/mapping,
sửa normative blockers bằng scope được duyệt, rồi triển khai backend/parser/UI
và tests trace tới approved oracle. Sau khi gói này đạt mới chuyển sang citation
provenance/history/runtime objectives; không mở rộng RAG pipeline trong lượt này.
