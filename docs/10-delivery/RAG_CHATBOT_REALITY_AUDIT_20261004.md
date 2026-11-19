# Kiểm định thực tế RAG chatbot Campus 24/7 — 2026-10-04

**Nếu mở chatbot và hỏi ngay bây giờ, nó có thực sự tìm tài liệu và dùng model thật để trả lời không? Chưa, với đường chạy mặc định trong source hiện tại.** UI và chat API có nối với graph, nhưng câu hỏi FAQ dừng trước retrieval vì entrypoint không cấp trusted retrieval context. Sau điểm đó vẫn còn nhiều thành phần chưa nối. Model/image đã có bytes trong workspace; điều này không chứng minh model đã được load hoặc inference.

Đã kiểm chứng offline bằng Python 3.12.14: **511 tests pass**, 15 quan sát graph, 7 quan sát ASGI và probe ASGI bổ sung. Các câu trả lời có nguồn trong probe đều dùng **candidate synthetic + deterministic fake**, hoặc fallback chép đoạn nguồn. Không có model inference, browser E2E, server socket, lifespan startup, database/container access hoặc live-provider call trong lượt này. Cấu hình bí mật và trạng thái deployment đang chạy không được đọc, nên không khẳng định về một deployment có composition khác source mặc định.

| Nội dung đánh giá | Kết luận | Cơ sở và giới hạn |
|---|---|---|
| (a) Chạy end-to-end thật | **Chỉ chạy được một phần; real RAG E2E chưa có bằng chứng** | Source UI → API → graph đã nối; ASGI mặc định với settings synthetic trả abstention, không retrieval. Startup qua ASGI factory pass; lifespan/server/browser chưa thực thi. |
| (b) Chất lượng trả lời có căn cứ | **not_verified với model/corpus thật** | Fake chứng minh wiring một đoạn nguồn và kiểm tra một số lỗi. Thiếu provenance vẫn được nhận, citation ID không thống nhất, history không vào model, injection guard chưa nối. Không dùng kết quả này để nghiệm thu grounded quality. |
| (c) Production readiness | **Chưa sẵn sàng** | Các lỗi kỹ thuật và gate đầu vào còn mở; readiness hiện không kiểm tra pipeline RAG. CONTEXT-003/RETRIEVE-001 vẫn partial, không tự accepted từ tests pass. |

## Phạm vi, thẩm quyền và bảo toàn

Đây là báo cáo kiểm định theo direct human request, không phải giao nhiệm vụ sửa, triển khai hoặc nghiệm thu catalog task. Tuân thủ `AGENTS.md`, document control/decision register, approved product/security/identity/acceptance contracts, sau đó mới đối chiếu code và execution evidence. Không phát hiện nested instructions bổ sung cho write scope đã dùng. Không spawn agent/chat hoặc gửi message.

Đã đọc tối thiểu các tài liệu được yêu cầu: DOCUMENT_CONTROL, DECISION_REGISTER, DEPENDENCY_ALLOWLIST, RAG_PRODUCTION_UPGRADE_PLAN, RAG_PIPELINE, ADR-005, DATA_DICTIONARY, delegated decisions, CONTEXT-003/RETRIEVE-001 execution, runtime candidate/acquisition/frontier/license review, PostgreSQL fixture; cùng `fixture.py`, `continuation_audit.py`, `delegated_verify.py` và source/tests liên quan. Đối chiếu thêm identity claims, authentication/authorization, memory, gateway, error/SSE và evaluation contracts. Không đọc sealed test text để chỉnh implementation.

Reconcile: upgrade plan draft là đề xuất, không thay approved RAG_PIPELINE v1.1, ADR-005 v1.1 và DATA_DICTIONARY v1.2. Profile đã chấp thuận là BGE-M3 dense 1024, L2/cosine; lexical 30 + semantic 30, RRF k=60, fusion 20, rerank 20 → context 8/6000 tokens; timeout lexical/vector/rerank 400/700/700 ms, retrieval overall 1800 ms, support threshold 0.78. Các con số này là yêu cầu, không phải hiệu năng đã đo trong lượt kiểm định.

Report candidate cũ nói chưa acquired; report acquisition/license mới và rehash bytes đã thay đổi trạng thái đó thành **đã acquired, chưa launch/infer**. Acquisition approval không bao gồm launch/inference. B-RUNTIME-SECURITY vẫn mở; chưa có exact live approval phù hợp. Không dùng việc thiếu reviewer/binding/corpus để dừng audit kỹ thuật, nhưng không vượt gate để chạy runtime.

Manifest người dùng cung cấp `license-review-20261004-02-final-scope.json` có SHA-256 `fff9a8e815925ddfbe62a2e4c601b8f809274bae6dbd71582c107e8c3c649df0`: đã đối chiếu chính manifest và **rehash đủ 1.433 entries, 0 mismatch** trước làm. Baseline mới exclusive-create có 1.434 entries, gồm manifest trước và không tự hash baseline:

- [Baseline audit](../../infra/local/rag-fixture/reality-audit-20261004-01-baseline.json), SHA-256 `4e5c64743a3b45d313f29da5a8b281c878a45b236facf99ceea79c90e7f24d9a`.
- [Scope và preservation cuối](../../infra/local/rag-fixture/reality-audit-20261004-02-final-scope.json) ghi kết quả rehash, exact new paths/hashes, git status/diff và final command exits. Đây là evidence tạo sau report này, tránh self-hash hoặc vòng hash. Bản 01 vẫn giữ nguyên; bản 02 sửa danh sách ignored artifacts theo directories thực sự tồn tại (outputs/stdlib), thay cho hai basetemp paths chỉ được khai báo nhưng pytest chưa tạo.

Coverage hash là Git cached/nonignored untracked, bao gồm payload acquisition; không bao gồm ignored runtime/credential bytes hoặc self-hash. Không tuyên bố byte-for-byte verification của mọi ignored file. Không sửa/xóa dữ liệu có trước; test artifacts mới, kể cả temp/log/failure, được giữ lại. Canonical paths và reparse/junction được kiểm tra bằng `continuation_audit.checked`; fresh outputs dùng exclusive-create. 26 tracked dirty files và các untracked có trước được bảo toàn, không giải quyết hay đưa vào scope sửa.

## Trace đường chạy thực tế

`real` trong bảng là code adapter/transport thật có tồn tại; không tự hàm ý đã thực thi live. `missing` là thiếu binding/consumer trong composition; `fail-closed` là chủ động từ chối, không phải service đã hoạt động. `not_verified` là chưa thực thi trong môi trường cần thiết.

| Chặng | Source/function chọn thực tế | Wiring mặc định và phân loại | Bằng chứng |
|---|---|---|---|
| UI gửi câu hỏi | `apps/web/src/app/chat/page.tsx:62,85`: POST conversations rồi messages:stream | **real transport code**, đúng route; `NEXT_PUBLIC_API_URL` hoặc localhost:8000. Live backend/browser **not_verified**. | Đọc source; không mở browser hoặc đọc localStorage. |
| Đăng nhập/context | `AppShell.tsx`; `bootstrap/app.py:create_app`, `run_trusted_agent` | Demo session auto-fetch host cố định localhost:8000; default SyntheticIdentityAdapter. Trusted context factory **missing** ở `main.py:16` (`create_app()` không inject). Không tự gán tenant/issuer/grants. | Source; ASGI synthetic boundary: unauthenticated 401, actor khác 403. Đây không phải production identity proof. |
| API/conversation | `presentation/chat.py:create_chat_router`; `application/conversation/messages.py` | **real in-process API**; mặc định InMemoryConversationRepository, không durable storage. | ASGI captured actual bootstrap runner tạo conversation và lưu 4 messages. Không lifespan/DB. |
| Graph | `agent/graph.py:build_agent_graph`, `CampusAgentWorkflow.run` | **real orchestration**; require_retrieval_context=True; entrypoint không cấp context → **fail-closed** trước search callback. | Default-runner probe + source main/bootstrap/graph. |
| Safety/intent model | `agent/nodes/definitions.py:sensitive_classifier_node`, `route_intent_node` | Có gateway calls trước retrieval; configured provider có thể được gọi ở đây dù RAG sẽ dừng sau đó. Synthetic settings không keys → **fake**. | Source + factory probe. Không suy ra actual deployment không gọi model nào. |
| Ingestion/query embedding | `scripts/run_ingestion.py:run_ingestion`; `infrastructure/retrieval/vector.py:_search_async`; worker `embed_fake.py` | Ingestion/vector **fail-closed**, chưa có approved embedding adapter nối active manifest. Fake embedding chỉ explicit test. | Đọc source; không chạy ingestion/model hoặc mặc định DB. |
| Vector index | migration 0009/0011/0012; domain embedding manifest | Physical legacy column khai báo vector(1536); metadata 1024 không thay vectors. Active index hiện tại **not_verified**. | Source migrations; snapshot head 0012/3 legacy chunks/active pointer 0 chỉ là lịch sử, không phải inspection hôm nay. |
| Lexical retrieval | `infrastructure/retrieval/lexical.py:_search_async` | Có **real SQL** và authorization predicate trước rank/LIMIT, nhưng bootstrap `LexicalSearchAdapter()` thiếu trusted filter compiler và explicit DB binding → **fail-closed**. | Source/tests offline; không SQL/network execution. |
| Hybrid/fusion | `bootstrap/app.py:228–230`; `hybrid.py:search` | Có concurrency/deadlines/RRF helper; accepted profile yêu cầu RuntimeRetrievalBinding, bootstrap không cấp → **fail-closed** trước branches. Canonical retry/degradation consumer chưa hoàn chỉnh. | Source + profile/context unit tests; không hai branch live. |
| Rerank | `definitions.py:rerank_evidence_node:326`; `ports/reranker.py` | **legacy score sort**, không inject/call RerankerPort hoặc model. Strict validator/typed port có code, chưa là runtime adapter. | Probe low/high chỉ đảo theo score sẵn có; contract fake tests pass. |
| Context/provenance | `bootstrap/app.py:search_knowledge:232`; `citations.py:CitationBundle` | Mapping bỏ source_id/issuer/effective/locator/URI; CitationBundle chấp nhận blanks, default issuer HUCE/simulation. Tokenizer budget/approved evidence consumers **missing** trên path này. | Source + missing-provenance probe. |
| LLM trả lời | `infrastructure/llm/factory.py:create_llm_gateway`; `openai_adapter.py`; `definitions.py:compose_grounded_node` | Factory có **real HTTP adapter class** cho configured Gemini/DeepSeek; khi DEMO_MODE, có deterministic fake fallback. Credential/service khả dụng **not_verified**. Graph còn fallback chép nguồn khi generate lỗi. | Synthetic factory live_provider_count=0; fault probes. Không live inference. |
| Evidence gate | `definitions.py:evidence_gate_node:397` → application retrieval EvidenceGate | **partial/legacy validation**: một macro claim toàn draft, lexical overlap .25; chưa nối canonical per-claim/profile .78 consumer/repair. | Unknown CIT-999 bị reject; missing provenance vẫn answered. .25 và .78 là khác metric, không so sánh trực tiếp như hai threshold cùng phép đo. |
| SSE/citations | `presentation/chat.py:89–194` | **real SSE formatting**, nhưng chia lời đáp đã hoàn thành thành word chunks; không provider token streaming. Tự tạo `cit-1` từ candidates, không reuse CitationBundle CIT-001, không lưu citation_set_id. | Actual router + synthetic graph supplemental probe. |
| UI trả kết quả/lỗi | `page.tsx:128,146`; `features/chat/CitationDrawer.tsx:getValidityBadge` | Chỉ đọc delta/citations, bỏ event/status/error/abstain; thiếu metadata vẫn gắn confidence .95, thiếu validity mặc định “đang hiệu lực”. **partial**, lỗi SSE có thể bị che. | Static source + captured message.error/message.abstained events; browser rendering chưa thực thi. |
| Hỏi tiếp | `graph.py:run`; `chat.py`; ConversationMessageService | Có lưu transcript nhưng **history consumer missing**: mỗi turn tạo state mới, không list history cho LlmRequest; bootstrap không checkpointer. | Hai lượt cùng session: mỗi grounded request đúng 1 input item, chỉ câu hỏi hiện tại. |
| Readiness | health router/bootstrap | **placeholder/partial**: database disabled vẫn ready, Redis ready cố định; không kiểm active manifest/embedding/reranker/LLM. | Supplemental ASGI health output, không lifespan. Không coi là health của service đang chạy. |

Luồng FAQ hiện tại sau authentication thành công: UI POST → chat router lưu user → `run_trusted_agent` với context=None → safety/intent → retrieval yêu cầu context → abstain “chưa tìm thấy tài liệu” → API vẫn phát `message.completed` với citations rỗng → UI hiển thị câu đó. Default bootstrap runner đã tái hiện offline hai lượt. Nếu thiếu login/host đúng, UI có thể dừng sớm hơn; chưa thử browser/actual configured auth.

Nếu sau này chỉ inject context: hybrid binding còn thiếu; nếu cấp binding: vector vẫn chặn adapter/active manifest, lexical vẫn thiếu compiler/explicit DB. Không có bằng chứng embedding, reranker hoặc active 1024 index đang được sử dụng trong chatbot. Không mở fake/legacy fallback để che các điểm dừng này.

## Hành vi offline đã quan sát

Harness mới [reality_audit_20261004_01.py](../../infra/local/rag-fixture/reality_audit_20261004_01.py) chỉ phục vụ audit; không sửa implementation, không có assertions nghiệm thu quality. Nó dùng network/DNS denial, synthetic identity/query/candidate/gateway, Settings.model_construct để không đọc dotenv và invalid explicit database URI. Không truy cập auth secrets. ASGITransport không mở socket hoặc chạy lifespan. Các fault là lỗi synthetic chủ động đưa vào boundary, không phải outage service thật.

| Trường hợp | Quan sát | Diễn giải |
|---|---|---|
| Có nguồn synthetic | answered, 1 retrieval callback, 1 grounded fake call | Wiring source→prompt→draft chạy được khi thay boundary. Không chứng minh runtime canonical. |
| Không nguồn / evidence rỗng | abstained, không grounded call | Có abstention; API mặc định vẫn phát completed, không phân biệt terminal. |
| Retrieval TimeoutError/RuntimeError | abstained, AI_RETRIEVAL_UNAVAILABLE | Câu hiển thị giống thiếu tài liệu; không thông báo khác biệt hệ thống gặp lỗi. |
| Reranker timeout/error | **Không thể inject vào graph một reranker được nối vì graph chưa gọi port** | Đã kiểm typed errors/request/output contracts bằng offline tests; runtime recovery cho model reranker **not_verified/missing**, không coi score-sort là smoke reranker. |
| LLM TimeoutError/RuntimeError | answered, errors rỗng, copy đoạn nguồn kèm CIT-001 | Fallback tạo đáp án trông grounded dù không generation thành công, thiếu degraded/provider-state. |
| Citation CIT-999 | abstained, EVIDENCE_GATE_REJECTED | Có kiểm ID trong bundle; chưa đủ chứng minh toàn bộ provenance/claim support. |
| Citation thiếu source/URI/page | answered; builder source_id/URI rỗng, page=None, default issuer HUCE | Không enforce nguồn truy xuất được và metadata completeness trên path graph. |
| Candidate synthetic is_authorized=False | answered trên callback được inject | Khoảng trống defense ở graph boundary. **Không phải bằng chứng PostgreSQL/default path làm lộ tài liệu**; lexical SQL có filter sớm, default retrieval còn bị chặn. |
| Actor khác truy cập conversation | HTTP403; chưa auth HTTP401 | Chat ownership boundary hoạt động trong probe synthetic; document entitlement với real DB chưa thực thi. |
| Prompt injection trong tài liệu | Standalone detector báo injection; graph vẫn đặt chuỗi đó vào system instructions | Guard/trust-domain composer chưa nối. Fake không tuân injection; **không chứng minh hành vi model thật** hoặc bypass production đã xảy ra. |
| Hỏi tiếp “Còn trường hợp đó thì sao?” | Grounded input mỗi lần chỉ 1 item; lịch sử không được truyền | Transcript tồn tại khác với context được sử dụng. Probe grounded_calls=2 ở lượt hai là số tích lũy hai lượt, không phải hai calls trong một turn. |
| Runner ném lỗi | HTTP200, SSE started/error, chỉ lưu user | UI bỏ qua message.error nên có thể hiện câu trả lời trống mà không báo lỗi. Đây là suy luận source từ event đã bắt. |
| Stream bị guard reject | Provisional delta đã emit rồi mới abstain, chỉ lưu safe assistant | UI đã append delta và không xử lý abstain replacement; có nguy cơ hiển thị provisional bị từ chối. Sentinel hoàn toàn synthetic, không secret thật. |
| Graph → router → citations | Answer dùng [CIT-001]; completed gửi id cit-1; message citation_set_ids đều null | Mismatch ID và persistence là quan sát thực thi offline actual router. |

Tests mang tên `apps/web/e2e/grounded-faq.spec.ts` dùng Vitest/React render, prepopulated answers và mockCitations. Tên thư mục E2E không làm chúng thành browser→backend→model tests. Không chạy frontend build/tests bằng runtime ngoài phạm vi Python được duyệt.

## Việc kỹ thuật trong repo và đầu vào ngoài repo

Các phát hiện dưới đây là đề xuất công việc tiếp theo, **chưa sửa**. Không yêu cầu thay requirement, giảm threshold, phá gate hoặc tự accepted dependency.

| Việc kỹ thuật có thể triển khai trong repo khi được giao | Đầu vào/gate phải được cung cấp riêng |
|---|---|
| Composition root inject request-local context factory, filter compiler, independently verified runtime binding; truyền metadata đầy đủ. | Trusted institution/issuer/resolver và role validity/revocation/audience/faculty/program. Không dùng nhãn HUCE Demo hoặc client input làm grants. |
| Approved embedding/TEI adapter, canonical ingestion/index/query path, 1024 schema/index + manifest compatibility, tokenizer limits. | Runtime security disposition/independent review; exact launch approval; reviewed corpus/index snapshot. Thay index/migration/activation cần scope riêng, không overwrite legacy vectors. |
| Nối canonical retrieval retry/degradation, real reranker port + strict validator, token budget, evidence/claim support consumer. | Endpoint và artifact binding đúng pins; hardware/SLO capacity; trusted gold/eval corpus. |
| Nối PromptComposer/PromptInjectionDetector và citation resolver với authorization/effective-date/provenance; thống nhất citation IDs qua graph/API/UI/storage. | Source owner/canonical URI/version metadata và quyền actor được xác thực. Security-related implementation vẫn cần approval đúng mục tiêu theo AGENTS. |
| Bounded conversation history theo identity/conversation vào prompt hoặc graph; durable repositories. | Approved storage deployment và retention/privacy inputs. Không suy ra permission truy cập production DB. |
| API giữ terminal abstain/error/degraded, kiểm trước phát nội dung hoặc rollback UI an toàn; UI parse event/status/error, citation metadata và citations theo từng message. | Không cần live model để sửa/kiểm deterministic error handling; task sửa riêng vẫn cần được giao. |
| LLM gateway thực thi egress/policy/budget; explicit fake state; structured sanitized errors; health kiểm dependency RAG thật. | Exact provider/endpoint/model approval, secret-reference mechanism và quota; không gửi secret trong chat. |

Rủi ro gateway cụ thể qua source: factory chọn OpenAICompatibleAdapter/multi-provider, chưa wrap EgressGuardedLlmGateway/GatewayPolicyExecutor; timeout dùng max(request deadline, default 15s), max_tokens dùng max(request cap,1024), có thể nới thay vì giữ giới hạn; graph nuốt generation exception, multi-provider log exception text, SSE gửi str(err). Đây là các phát hiện code cần review đúng security scope, không khẳng định đã rò token hay đã có live traffic.

Worker `ingestion/index.py:KnowledgeIndexer.persist_chunks` insert/commit basic chunk fields, chưa ghi payload embedding_vector/tsv/manifest; chunker hiện theo ký tự 1200/overlap150, chưa chứng minh tokenizer envelope approved. Script ingestion chủ động chặn nên không sử dụng các helper đó như pipeline production đã hoàn thiện.

## Thứ tự tối thiểu để có một câu hỏi RAG thật từ UI

1. Giao scope sửa rõ ràng; hoàn tất runtime security disposition và exact isolated inference approval. Giữ nguyên pins; clearance không đồng nghĩa model đã hoạt động. Có thể kiểm deterministic wiring/API/UI lỗi độc lập trong lúc chờ.
2. Load đúng embedding/reranker bytes trong isolated smoke bên dưới; xác minh shape/norm/ID mapping/timeouts và ghi latency/digests. Chưa dùng DB hoặc corpus nghiệp vụ ở bước này.
3. Cung cấp trusted context resolver và reviewed corpus nhỏ có provenance. Tạo index 1024/manifest riêng theo schema/migration scope được duyệt, ingestion đúng adapter; xác minh active binding bằng storage. Không dùng ba legacy chunks để nghiệm thu.
4. Nối composition và canonical retrieval: context/compiler → lexical/vector → merge/degradation → reranker thật → budget/evidence/citation resolver; authorization trước candidate selection và khi resolve nguồn. Không tháo fail-closed để vượt missing inputs.
5. Nối real LLM qua policy/egress guard với exact approved provider/model; đặt evidence đúng trust domain, history có budget; lỗi model phải báo rõ. Đồng nhất citation IDs, metadata và persistence.
6. Sửa API/UI xử lý terminal/error/degraded và provisional text; readiness đo đúng dependencies. Kiểm API deterministic đủ các case trước browser smoke.
7. Chạy **một** UI question qua endpoint cô lập đã duyệt: ghi browser request → auth/context → index/version → embedding → hai branches → fusion → reranker → LLM → gate/citations → SSE/UI. Hỏi tiếp một lượt để xác nhận history. Đây chỉ chứng minh technical E2E; quality/release phải theo evaluation/acceptance/OPS gates riêng.

Thứ tự này là dependency của một smoke kỹ thuật, không đổi catalog DAG hoặc công nhận CONTEXT-003/RETRIEVE-001 hoàn tất. Không thể hứa real grounded E2E chỉ bằng việc bật một cấu hình/provider key.

## Smoke test cụ thể chưa được thực thi

### A. Exact embedding/reranker compatibility smoke

Giữ candidate từ runtime evidence; **đề xuất, chưa cho phép chạy**:

- Image Linux/amd64 TEI cpu-1.9.4: `ghcr.io/huggingface/text-embeddings-inference@sha256:8419f533857b503ebf6ec292a95d4f1cf9c0464ac8b8abeef39518cf110e5726`; source commit `e80ef225ed0e6cb1717ce632a6a84b6cf211bb67`.
- Embedding BAAI/bge-m3 revision `5617a9f61b028005a4858fdac845db406aefb181`, acquired bundle checksum `27494beaa7a3dfc6bdff315254232b6a53fca3b39d37dadecdc92bc264981e9a`.
- Reranker BAAI/bge-reranker-v2-m3 revision `953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e`, bundle checksum `b0b73b8047e52a0fb3670a3b4789cfa07fe52fe1d910e48dcfd9dd0f79aaa732`.
- Read-only mounts: exact canonical workspace directories `infra/local/rag-fixture/runtime-acquisition-20261004/bge-m3` và `.../bge-reranker-v2-m3`; không host/profile/credential mounts. Rehash trước launch; không convert weights hoặc đổi pins.
- Fresh container names `campus247-rag-embed-smoke-20261004`, `campus247-rag-rerank-smoke-20261004`; internal network `campus247-rag-model-smoke-20261004`, không nối business/fixture DB network. Collision phải chọn scope mới, không xóa/reuse đối tượng không rõ ownership.
- Loopback-only `127.0.0.1:18081` và `127.0.0.1:18082`; một model mỗi lần, 4 CPUs/5GiB float32. Hardware đã ghi ở candidate là lịch sử; phải kiểm capacity/collision read-only lại trước approval/launch. Không thay Docker allocation/driver/GPU settings. CPU instruction/MKL compatibility còn cần xác nhận.
- Input duy nhất synthetic: query “Học phí thử nghiệm là bao nhiêu?”, hai texts “Học phí thử nghiệm là 100 đơn vị mỗi tín chỉ.” và “Thư viện thử nghiệm mở cửa lúc 8 giờ.”, IDs SYN-1/SYN-2, mỗi item ≤128 tokens; batch requests=1, batch tokens=1024, truncate=false. Không log request text ở runtime.
- `GET /health`, `/info`; `POST /embed` inputs array/normalize=true/truncate=false: kiểm 1024 finite values, L2 norm, query/document parity. `POST /rerank` query/texts/raw_scores=true/return_text=false/truncate=false: finite raw scores, indices duy nhất đúng supplied-ID range, mapping giữ nguyên candidates. Không dùng thứ tự hai đoạn đơn giản để nghiệm thu quality.
- Effects: tạo resource/output mới, load weights vào RAM và HTTP inference loopback; **không** truy cập DB, reindex, activate pointer hoặc live external LLM. Giữ mọi artifacts/resources, không auto-remove/cleanup. Đề xuất deadline smoke 60s startup/request cap 30s, chỉ đo latency; không thay production deadline 700ms để pass.
- Evidence fresh suffix tại fixture: command argv đã loại secrets, exact artifact digests, bounded synthetic input/output, health/info, per-call monotonic latency, exit codes; không env dump.

Chưa đủ điều kiện: runtime security clearance/independent signed review, native license/signature/feature/reachability dispositions, exact launch/inference scope approval và verified execution configuration. Acquisition đã được duyệt/thực hiện, không hỏi lại acquisition. Không chạy `docker load/run`, HTTP model requests hoặc model deserialize trong audit này.

### B. UI → RAG → real LLM smoke sau khi nối code

Đề xuất isolated frontend `127.0.0.1:13000`, API `127.0.0.1:18000`, fresh names/ports được xác minh trước chạy. Dùng tài liệu synthetic riêng có source/version/canonical URI và actor scope reviewed dành cho smoke; không ghi đè corpus/index hiện có. Model endpoints giữ scope A. API phải inject explicit guarded fixture binding nếu scope fixture được giao; chỉ access qua receipt/labels/image/binding/mount/network/marker guards của `fixture.py`, không default DATABASE_URL, `.env` hoặc port5433. Không nêu receipt password trong approval/evidence.

**Chưa có exact approved LLM provider/endpoint/model target để điền vào lệnh thực thi**; không tự chọn Gemini/DeepSeek theo defaults. Approval phải chỉ rõ endpoint/immutable hoặc reviewed model identifier, egress hosts, secret-reference, 2 turns synthetic, output≤1000tokens/turn, cost cap và retry policy. Nếu provider paid chưa được duyệt, không gọi fallback paid. Fake không được tính là success.

Effects tiếp theo gồm conversation/message/citation records và index artifacts riêng theo scope được duyệt; mọi write/migration/activation phải được review riêng, không đề xuất reset existing fixture. Chạy browser thật kiểm nguồn mở được, ID đúng, follow-up dùng history, ngoài quyền/no-source/error hiển thị rõ. Record sanitized trace IDs/model response metadata/call counts/latency để phân biệt model thật với fake và copy-source fallback. Thiếu wiring, trusted input và exact live approval hiện tại khiến smoke B **not_verified**, không phải một lệnh có thể chạy an toàn ngay.

## Commands, exits và evidence giữ lại

Mọi Python command dùng `infra/local/rag-fixture/.venv/Scripts/python.exe -B` (3.12.14), không PATH Python hoặc install. Commands đọc source/status được batch; lỗi discovery được sửa đường dẫn, không làm mutation. Không có DB/Docker/model/network command trong lượt này.

| Command/check | Exit | Kết quả/evidence |
|---|---:|---|
| Python inline: exact prior manifest SHA + rehash 1.433 files, canonical preflight, exclusive baseline | 0 | Baseline link ở trên; không mismatch. |
| `git status --short`, `git diff --name-only` trước mutations | 0 | Lưu baseline; giữ 26 tracked modifications và untracked có trước. |
| Python `scripts/verify_dependencies.py` preflight | 0 | Approved pins/closure/artifact hashes pass; không install. |
| Python `tasks/tools/validate_catalog.py` preflight | 0 | VALID 241 tasks / 10 phases. |
| `git diff --check` preflight | 0 | Chỉ CRLF warnings có trước. |
| `reality_audit_20261004_01.py suite` lần đầu | shell 1 / pytest 3 | INTERNALERROR vì pytest default log NUL resolve ngoài workspace, guard chặn trước write. [Failure suite](../../infra/local/rag-fixture/delegated-reality-audit-20261004-offline-01.json) giữ nguyên. |
| `reality_audit_20261004_01.py probes` lần đầu | 1 | Guard chặn tempfile write ngoài root từ IdempotencyLedger ở app factory; [failure type](../../infra/local/rag-fixture/reality-audit-20261004-01-probes-failure.json), không exception values. |
| Python inline diagnostic stack filenames/line numbers | 0 | Graph 15 observations; tìm đúng tempfile boundary; không dump prompt/settings. |
| Scoped harness repair | tool success | Chỉ harness mới: log/temp chuyển fresh workspace paths, giữ artifacts; không nới guards hoặc sửa product/tests. |
| `reality_audit_20261004_01.py suite-02` | 0 | **511 passed in 8.20s**, không skip/warning. [Suite evidence](../../infra/local/rag-fixture/delegated-reality-audit-20261004-offline-02.json). |
| `reality_audit_20261004_01.py probes-02` | 0 | [15 graph + 7 ASGI observations](../../infra/local/rag-fixture/reality-audit-20261004-02-probes.json). Execution success không đồng nghĩa behavior acceptance. |
| Python inline supplemental ASGI actual factory/router, Settings.model_construct, fake gateway | 0 | [Supplement](../../infra/local/rag-fixture/reality-audit-20261004-01-supplement.json): health/auth/citation mismatch/persistence; live_inference_calls=0. |
| Read-only JSON stdout lần đầu / UTF-8 retry | 1 / 0 | cp1252 UnicodeEncodeError chỉ khi display; evidence không sửa. |
| Discovery `rg` guessed paths / PowerShell brace-path syntax | 1 / corrected 0 | Không tồn tại một số guessed paths hoặc parser error; sau đó tìm bằng rg --files và đọc exact files. Không phải product test failures. |
| Final dependency verifier → catalog validator → diff check → scope/status/hash/sensitive-output scan | Ghi actual exits tại final-scope | Chỉ báo cáo/evidence/harness mới; không broad regression lần nữa khi product không đổi. |

Suite targets: `tests/unit/agent`, `tests/unit/retrieval`, `tests/unit/ai`, `tests/unit/conversation`, `tests/api/test_chat_sse.py`, `tests/chaos/test_llm_outage.py`, `tests/architecture`. Network/DNS denied; pytest cacheprovider disabled, importlib mode, fresh basetemp và retention all. Không chạy app boot tests đọc settings/dotenv; dùng factory probe với explicit synthetic settings. Không coi suite này là integration với DB hoặc live model.

SHA-256 evidence chính: suite-02 `86c1630db598eedffe075b2c862db8b9bb271d51b29df5c67daff8dcb5fa70f7`; probes-02 `71115948b4bbbd48af87924161e2c107404e1dac63cfd972e8da9c53b59a1752`; supplement `e3ae8952a8ec6deb04f2a866f53925a6956faa0b503113875d35bd024371bc47`. Failure suite-01 `90f2d3a4ca2d9af2f014b94b9ad72f8e62a8199f1c8dc3cfb3458abda44573ef`; probes failure `79327346d5d130ea705537ed0a0223cacde2d031592ec1771b028e5267688f93`. Final scope ghi hashes của toàn bộ new nonignored files, bao gồm report/harness/log; không tự hash chính final manifest.

**Audit có kết luận và bằng chứng; chatbot real RAG, grounded quality và production readiness chưa được nghiệm thu.** Không thay implementation/requirements/security/pins, không bypass gate, không commit/push/deploy/reset/clean hoặc cleanup.
