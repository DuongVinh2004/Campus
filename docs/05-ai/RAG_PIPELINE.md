---
document_id: "DOC-RAG-001"
version: "1.1.2"
status: "approved"
owner: "Knowledge Engineering Lead"
approvers: ["AI Architecture Lead", "Knowledge Governance Lead", "Security Architect", "AI Quality Lead"]
last_updated: "2026-10-12"
---

# RAG ingestion, retrieval, reranking, citation và evidence gate

### Mở nguồn từ citation đã lưu

Theo `API-CONV-005` và DEC-023, UI mở đoạn nguồn gốc qua read API gắn với
conversation/message/citation đã lưu. Server MUST kiểm tra ownership, retention,
final semantics, quyền actor hiện tại và cùng eligibility predicate của retrieval
trước khi trả đoạn gốc. Checksum chunk, metadata, locator và quote phải khớp;
nguồn bị thu hồi, hết hiệu lực hoặc ngoài scope không được mở dù citation cũ còn
trong lịch sử. UI hiển thị plaintext, issuer/version/effective dates/locator và
nhãn simulation; không biến synthetic URI thành URL điều hướng hoặc quyền admin.

## 1. Mục tiêu

RAG chỉ được trả lời từ nguồn đã publish, còn hiệu lực và phù hợp audience. Vector similarity không phải bằng chứng. Mỗi material claim phải liên kết tới đoạn nguồn đủ cụ thể để người dùng và evaluator kiểm tra.

Thiết kế dùng PostgreSQL full-text search + pgvector semantic search theo `DEC-012`, hợp nhất bằng Reciprocal Rank Fusion (RRF), rerank tập nhỏ và qua deterministic evidence gate.

## 1.1 Production retrieval profile

Mọi giá trị production trong pipeline này thuộc profile bất biến `rag-prod-v1.0.0`; thay đổi bất kỳ giá trị nào MUST tạo profile version mới và chạy lại full evaluation trên cùng corpus/index.

| Group | `rag-prod-v1.0.0` |
|---|---|
| Embedding | `BAAI/bge-m3@5617a9f61b028005a4858fdac845db406aefb181`; dense 1024; L2 normalize; cosine distance; query/document cùng revision |
| Reranker | `BAAI/bge-reranker-v2-m3@953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e`; tối đa 20 input, 8 output |
| Retrieval | lexical 30, semantic 30, RRF constant 60, fused 20; stable `chunk_id` dedupe |
| Context | tối đa 6,000 tokenizer tokens; không quá 3 near-duplicate chunks từ một section |
| Timeouts | lexical 400 ms; semantic 700 ms; reranker 700 ms; hard deadline 1,800 ms; tối đa một transient retry khi còn deadline |
| Evidence | support threshold 0.78; một repair tối đa; repair chỉ remove/qualify/clarify/abstain |
| Quality | Recall@10 >=0.90; critical subgroup >=0.85; citation precision >=0.95; grounded correctness >=0.90; exact-ID Recall@5 >=0.98; conflict handling >=0.98; invalid-source leakage =0 |
| Performance | p95 <=1,800 ms; p99 <=3,000 ms trên `TP-RAG`; error rate <1%; benchmark phải ghi hardware, concurrency, pool và memory |

Profile thiếu field, mutable model revision, model/index mismatch hoặc artifact checksum mismatch MUST block startup/query. Unit tests MAY dùng deterministic fake nhưng fake/stub không hợp lệ làm production/release evidence.

### 1.2 Local/synthetic M1 performance configuration

Direct human decision ngày 12/10/2026 cho phép cấu hình hiệu năng hữu hạn để
nghiệm thu M1. Các deadline 700/1,800ms và CPU4/5GiB là baseline lịch sử cho chu kỳ
local mới. Production profile/TP-RAG SLO ở bảng trên giữ nguyên; không tuyên bố
đạt latency cũ hoặc production readiness từ phép thử local.

`RuntimeDeadlines` là overlay có revision riêng, chỉ trong development/testing
với DEMO_MODE. Không đổi index/model identity, quality thresholds, EvidenceGate
0.78, authorization, source filters, context/token/input limits hoặc test oracles.
Semantic/reranker adapters và overall retrieval dùng cùng effective overlay.
Native Session, model service, provider batch và controller đọc cùng cấu hình
local JSON đã hash và ghi receipt trước chạy. Không có timeout vô hạn.

Candidate `m1-local-20261012-v1`: native 1,000ms; adapter 1,400ms; retrieval
3,300ms; native/provider active batch 600s; controller 900s. Native 100–3,000ms,
adapter tối đa5,000ms và ít nhất native+200ms; retrieval tối đa12,000ms và ít nhất
2×adapter+400ms; batch30–600s; controller bao trùm batch và tối đa1,200s.
Resource/thread configuration hiện hành giữ nguyên để tách biến deadline.
Sau full-stack v1 timeout với native Run khoảng1,031s, người dùng yêu cầu tăng
tiếp. Candidate `m1-local-20261012-v2`: native1,600ms; adapter2,100ms;
retrieval4,700ms; batch/controller giữ600/900s. Ledger và mọi failed USER/reservations
được nối tiếp. Thời gian bị terminate không phải natural completion; candidate
v2 vẫn phải qua real acceptance và bounded repeats trước khi ghi completed.
QPC dùng đo; monotonic/Timer dùng enforcement, cancel/join trước release
RunOptions. Receipt phải ghi natural completion, headroom, budgets và giới hạn
phạm vi; cấu hình candidate chưa tự tạo acceptance evidence.

## 2. Source lifecycle

```text
discovered -> quarantined -> scanned -> parsed -> reviewed
           -> approved -> indexed -> published -> superseded|withdrawn
```

Chỉ `published` được retrieval production. `superseded` được giữ audit nhưng excluded mặc định. `withdrawn` MUST bị loại ngay bằng metadata filter và cache invalidation; không chờ re-embedding.

### 2.1 Metadata bắt buộc

| Field | Rule |
|---|---|
| `source_id` | Stable, immutable. |
| `document_version_id` | Mới cho mỗi content checksum/version. |
| `title` | Không rỗng. |
| `issuer` | Đơn vị ban hành. |
| `document_number` | Nullable chỉ khi loại nguồn không có số. |
| `source_type` | `regulation|procedure|faq|form|notice|handbook|synthetic`. |
| `canonical_uri` | Official URI hoặc `synthetic://...`. |
| `content_sha256` | Hash bytes canonical. |
| `published_at` | Known timestamp/date. |
| `effective_from`/`effective_until` | Explicit nullable semantics. |
| `audiences` | Allowlist role/program/cohort. |
| `faculty_scope` | `FIT` hoặc approved scope. |
| `language` | V1 `vi`. |
| `approval_status` | `approved` trước publish. |
| `source_owner`/`approved_by` | Role/reference, không tự giả. |
| `simulation_label` | `true` cho synthetic. |
| `parser_version`/`chunker_version`/`embedding_version` | Traceability. |

Thiếu bất kỳ metadata required nào MUST quarantine source. `effective_until = null` nghĩa chưa biết ngày hết hiệu lực, không có nghĩa vĩnh viễn. Production retrieval MUST exclude version này cho đến khi knowledge owner xác nhận applicability và đặt `applicability_reviewed_at`; xác nhận không được suy ra tự động từ ngày publish.

## 3. Ingestion pipeline

| ID | Bước | MUST |
|---|---|---|
| RAG-ING-001 | Acquire | Chỉ allowlisted origin/upload role; lưu provenance, license/usage note và checksum. |
| RAG-ING-002 | Quarantine | Không render active content; malware/file-type/size validation trước parse. |
| RAG-ING-003 | Parse/OCR | Giữ page, heading, article/section, table cells và reading order; ghi OCR confidence. |
| RAG-ING-004 | Normalize | Unicode NFC, whitespace có kiểm soát; giữ bản raw immutable. |
| RAG-ING-005 | Structure | Tạo hierarchy document→section→clause→table/list; không trộn hai section độc lập. |
| RAG-ING-006 | Chunk | Semantic boundaries trước token size; overlap không vượt 20% trừ table/definition. |
| RAG-ING-007 | Enrich | Title path, exact identifiers, entities, audience và effective metadata. |
| RAG-ING-008 | Quality gate | Reject empty, duplicate, low OCR, missing page/section hoặc broken table theo threshold cấu hình. |
| RAG-ING-009 | Human review | Knowledge admin approve source/version và conflict disposition. |
| RAG-ING-010 | Index | Trong transaction/versioned job; lexical + embedding + manifest. |
| RAG-ING-011 | Publish | Atomic active-version pointer; rollback tới index snapshot trước. |

### 3.1 Chunking baseline

- Target 350–700 tokens; hard maximum 900 tokens sau tokenizer của embedding model.
- Chunk một điều/mục ngắn như một đơn vị dù dưới target.
- Definition và điều được định nghĩa SHOULD đồng xuất hiện qua metadata/link, không duplicate vô hạn.
- Table không được cắt làm mất header. Table lớn chia theo row groups và lặp header có đánh dấu.
- Mỗi chunk MUST có `chunk_id`, `document_version_id`, `section_path`, `page_start`, `page_end`, `char_start`, `char_end`, `text_sha256`.
- Boilerplate lặp phải được đánh dấu/loại theo deterministic rule và có report.

Các giá trị baseline phải được tune bằng eval; thay đổi là behavioral change và MUST tạo `retrieval_profile` version mới.

## 4. Query preparation

1. Validate length/language/encoding.
2. Redact PII không cần cho knowledge lookup.
3. Trích exact tokens deterministic: mã môn, số văn bản, biểu mẫu, ngày, khóa, cơ sở.
4. Lập metadata filters từ trusted context và intent; model MAY đề xuất filter nhưng server MUST intersect với authorized scope.
5. MAY tạo một semantic rewrite; rewrite MUST giữ exact identifiers, phủ định, time constraint và audience.
6. Nếu rewrite làm mất constraint, dùng original query.

## 5. Candidate retrieval

### 5.1 Lexical branch

- Dùng PostgreSQL `tsvector` và `websearch_to_tsquery` hoặc query builder được kiểm thử cho input người dùng.
- Rank baseline bằng `ts_rank_cd` với weight title/section/body và normalization đã version hóa.
- GIN là index baseline cho `tsvector` thường xuyên được search.
- Lấy `lexical_k = 30` theo `rag-prod-v1.0.0`, sau metadata/authorization filter trong SQL và trước `LIMIT`.

PostgreSQL docs xác nhận ranking có thể xét tần suất, proximity và structural weight; relevance vẫn application-specific nên phải eval, không coi rank là xác suất. Xem [PostgreSQL text search controls](https://www.postgresql.org/docs/17/textsearch-controls.html) và [preferred indexes](https://www.postgresql.org/docs/17/textsearch-indexes.html) (`SRC-POSTGRES-001`).

### 5.2 Semantic branch

- Embedding model/version/dimension MUST nằm trong index manifest.
- Similarity function MUST cố định theo model; V1 baseline cosine distance.
- HNSW MAY được dùng khi exact-search benchmark không đạt latency; profile MUST ghi `m`, `ef_construction`, `ef_search` và iterative-scan settings.
- Lấy `semantic_k = 30` theo `rag-prod-v1.0.0`, sau metadata/authorization filter trong SQL và trước ANN `LIMIT`. Nếu approximate filtering trả thiếu candidate, use iterative scan/exact fallback theo profile.

pgvector phân biệt exact nearest-neighbor và approximate index đánh đổi recall lấy tốc độ; HNSW có tuning và filtering có thể làm giảm kết quả. Xem [pgvector README](https://github.com/pgvector/pgvector) (`SRC-PGVECTOR-001`).

### 5.3 Fusion

RRF baseline:

```text
rrf_score(document) = Σ_branch 1 / (60 + rank_branch(document))
```

- Deduplicate bằng `chunk_id` trước fusion.
- Exact identifier match nhận deterministic boost versioned, không vượt qua authorization/effective filters.
- Lấy tối đa `fusion_k = 20` theo `rag-prod-v1.0.0` cho reranker.
- Nếu một branch unavailable, degraded retrieval MAY dùng branch còn lại nhưng trace MUST ghi degradation; release/online metric phân tách.

## 6. Reranking và context assembly

- Reranker nhận query và tối đa 20 candidate với stable IDs.
- Output chỉ là ordered IDs + bounded score/reason code; MUST NOT sửa chunk text.
- Candidate ID ngoài allowlist hoặc duplicate làm output invalid.
- Fallback deterministic là RRF order và MUST ghi degraded reason. Hai branch fail, hoặc branch còn lại không bảo đảm SQL authorization/effective filters, MUST abstain.
- Chọn tối đa 8 chunk và 6,000 tokenizer tokens theo `rag-prod-v1.0.0`.
- Diversity rule: không quá 3 chunk gần trùng từ một section trừ khi query hỏi liệt kê đầy đủ.
- Conflict detector đánh dấu nguồn mâu thuẫn về hiệu lực/giá trị. Không tự chọn nếu authority order chưa xác định; handover/abstain.
- Context assembly MUST giữ citation locator và simulation label.

## 7. Citation contract

Mỗi citation:

```yaml
citation_id: "CIT-<turn-local-sequence>"
source_id: "..."
document_version_id: "..."
chunk_id: "..."
title: "..."
issuer: "..."
document_number: "... or null"
section_path: ["...", "..."]
page_start: 1
page_end: 1
canonical_uri: "..."
effective_from: "date|null"
effective_until: "date|null"
simulation_label: true
quote_span_hash: "sha256:..."
```

Model chỉ được phát `citation_id` có trong evidence bundle. UI/API resolve metadata từ server-side bundle; model MUST NOT tự sinh URL, page, title hoặc document number.

## 8. Claim và evidence gate

### 8.1 Material claim

Claim là material nếu ảnh hưởng hành động/quyền lợi hoặc khẳng định: điều kiện, deadline, mức phí, hồ sơ, đơn vị, địa điểm, lịch, trạng thái, quy định, ngoại lệ hoặc bước thủ tục.

`GroundedDraft` MUST tách:

```yaml
claims:
  - claim_id: "CLM-001"
    text: "..."
    citation_ids: ["CIT-001"]
    claim_type: "policy|procedure|deadline|fee|contact|personal_data"
response_text: "..."
```

### 8.2 Gate rules

Gate deterministic MUST kiểm tra:

1. mọi material claim có citation;
2. citation ID tồn tại trong turn bundle;
3. source/version đang publish và audience authorized tại thời điểm trả lời;
4. effective date bao phủ ngày áp dụng hoặc câu trả lời nêu rõ uncertainty;
5. claim text có lexical/semantic support tối thiểu theo calibrated verifier;
6. không có contradiction chưa giải quyết;
7. personal data claim đến từ tool result, không từ RAG;
8. contact/fee/deadline không được suy ra từ nguồn synthetic như official fact mà không gắn simulation.

Verifier score không phải xác suất. `rag-prod-v1.0.0` dùng support threshold `0.78`, chỉ được promote khi validation đạt citation precision ≥95% và các gate mục 11. Threshold nằm trong versioned profile, không hard-code ở prompt. Nếu một material claim fail, composer MAY được yêu cầu remove/qualify/clarify claim và render lại đúng một lần; không được thêm nguồn mới trong revision. Nếu vẫn fail, abstain.

## 9. Insufficient evidence behavior

Hệ thống MUST phân biệt:

- `no_candidates`: không tìm thấy;
- `low_retrieval_confidence`: có candidate nhưng dưới calibrated gate;
- `conflicting_sources`: nguồn mâu thuẫn;
- `out_of_scope`: không thuộc knowledge scope;
- `unpublished_or_expired`: chỉ có nguồn không hợp lệ;
- `authorization_filtered`: có thể tồn tại dữ liệu nhưng user không được xem;
- `index_unavailable`: lỗi hệ thống.

Response không được tiết lộ rằng unauthorized source tồn tại. Với ba lỗi đầu MAY đề nghị ticket/handover; với `index_unavailable` dùng thông báo degraded service.

## 10. Cache và invalidation

- Cache key MUST gồm normalized query hash, authorized audience scope hash, locale, active-index version, retrieval profile và effective date bucket.
- Không cache personal tool data trong RAG cache.
- Publish/withdraw source MUST invalidate bằng active-index version.
- Cached answer MUST chạy lại authorization/effective check trước trả.
- Cache hit vẫn ghi citations/version và online metrics.

## 11. Eval và acceptance

| ID | Gate |
|---|---|
| RAG-EVAL-001 | `Recall@10 >= 0.90` tổng thể và không subgroup critical nào <0.85. |
| RAG-EVAL-002 | Citation precision ≥0.95 trên sampled answered claims. |
| RAG-EVAL-003 | Grounded correctness ≥0.90 trên answered cases. |
| RAG-EVAL-004 | 100% material claims có citation IDs hợp lệ. |
| RAG-EVAL-005 | Expired/withdrawn/unauthorized source leakage = 0. |
| RAG-EVAL-006 | Exact identifier suite đạt Recall@5 ≥0.98. |
| RAG-EVAL-007 | Conflict cases abstain/handover đúng ≥0.98. |
| RAG-EVAL-008 | P95 retrieval+rereank trong budget route trên ASM-001/003 load profile. |

Evidence gồm dataset manifest/hash, index/profile/model versions, query-level results, subgroup report, failed-case IDs và benchmark hardware/config.

## 12. Failure và rollback

- Parsing regression: không publish version mới.
- Embedding drift/dimension mismatch: build index song song, không mutate active index.
- Eval gate fail: active pointer giữ version cũ.
- Source withdrawal: immediate metadata block trước background cleanup.
- Reranker unavailable: RRF fallback và metric degradation.
- Vector unavailable: lexical fallback nếu route cho phép; citation/evidence gates vẫn giữ nguyên.
- Lexical unavailable hoặc database degraded: không dùng vector-only nếu authorization/effective filters không được bảo đảm.

## 13. Approval record

Profile `rag-prod-v1.0.0` và các contract changes trong version 1.1.0 được direct human approval ngày 2026-09-29 cho `TASK-RAGUP-GOV-001`. Approval bao phủ architecture, knowledge governance, security và AI quality decision; implementation vẫn phải chứng minh từng gate bằng evidence tái lập được.

