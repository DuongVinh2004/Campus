# RAG continuation — runtime intake and remaining execution plan

2026-10-03. Execution/planning artifact, không phải architecture/dependency
approval. Direct user delegation đã giải quyết reviewer/orchestrator và ownership;
không còn chat song song. Không cần người dùng duyệt lại backlog/ordinary coding.

## Verified frontier

FILTER-002/003 và fake isolation EMBED-003 accepted; contract/storage acceptances
chi tiết ở RAG_DELEGATED_DECISIONS_20261003.md. 648 deterministic và 57 actual
PostgreSQL tests pass, no skips. Head 0012/retained data/index fingerprints preserved.

Không có đủ runtime bundle trong approved repository artifacts. Read-only search
không tìm thấy private endpoint bindings, serving API/auth specification, reviewed
runtime packaging hoặc two model-artifact manifests. Hashes lặp a/b/c trong tests
chỉ là synthetic values. Profile/RuntimeRetrievalBinding là contract, không tự
chứng minh model hoặc active index. Fixture active pointer vẫn rỗng.

TrustedScopeResolver mới có protocol và test resolver. SyntheticIdentityAdapter
không cung cấp tenant/institution binding trong returned IdentityContext; bootstrap
chưa inject trusted resolver/context factory. Không lấy program/audience từ client,
không default ALL/FIT/STUDENT để mở quyền. V1 single-institution binding là deployment
configuration; không thêm tenant_id columns, SaaS hoặc tenant routing.

## Concrete inputs needed, no credentials in chat

| Input | Required content | Opens |
|---|---|---|
| Private embedding service bundle | Endpoint location; pinned OpenAPI/API revision; request/response/error/health/model-info schemas; auth mechanism and secret reference name only; exact model revision; complete artifact path/size/SHA-256 manifest; approved synthetic live environment | EMBED-002, then EMBED-005/006 |
| Private reranker service bundle | Same deployment/provenance/auth/API records; exact approved reranker revision; mapping ordered scores to supplied candidate IDs; approved synthetic live environment | RERANK-002 |
| Trusted institution/scope binding | Deployment institution identifier; trusted identity provider binding; server-side resolver/source for role/audience/faculty/program and revoked/expired/missing records | CONTEXT-003 production wiring |
| Trusted corpus and index activation records | Reviewed source/version/chunk provenance and authorized scopes, content checksums, corpus version, complete 1024-dim embedding manifest; activation record only after validation | EMBED-006/007, FILTER-004/005 and gold shard acceptance |

Exact models stay unchanged:

- BAAI/bge-m3 @ 5617a9f61b028005a4858fdac845db406aefb181; 1024, L2/cosine.
- BAAI/bge-reranker-v2-m3 @ 953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e.

Artifact checksum phải thuộc bytes thực tế được deploy, tokenizer/config/pooling
và weights đều có provenance; upstream pointer hash không thay verification của
local deployed bytes. Revision/name/dimension không đủ để activate manifest.

## Runtime choice prepared

Ưu tiên dùng private service đã được review nếu có, qua approved HTTP client;
không cần thêm inference SDK vào API/worker lockfile. Endpoint/API/provenance
phải được supplied/verified trước implementation adapter, không invent wire protocol.

Nếu chưa có service, phương án cần packaging review là hai private self-hosted
Hugging Face Text Embeddings Inference services, model directories pinned và
read-only, acquisition tách khỏi offline serving. Đây là proposal, chưa install,
pull image, tải weights, mở port, launch hoặc gọi live model.
Official docs mô tả /embed, /rerank và air-gapped local-directory serving;
khả năng hỗ trợ XLM-RoBERTa/sequence classification chỉ là suitability evidence,
không xác nhận exact-revision compatibility hoặc performance trên máy này.
[Quick Tour](https://huggingface.co/docs/text-embeddings-inference/en/quick_tour),
[Supported models/hardware](https://huggingface.co/docs/text-embeddings-inference/en/supported_models).

Read-only upstream inventory cho approved bge-m3 revision có pytorch_model.bin;
approved reranker revision có model.safetensors. Vì vậy không giả định một image
load được cả hai; phải kiểm chứng loader/conversion provenance riêng trước review.
Không đổi sang mutable main hoặc revision khác để tránh format issue.
[Embedding exact-revision weight](https://huggingface.co/BAAI/bge-m3/blob/5617a9f61b028005a4858fdac845db406aefb181/pytorch_model.bin),
[Reranker exact-revision inventory](https://huggingface.co/BAAI/bge-reranker-v2-m3/tree/953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e).

Trước khi local proposal có thể thực thi: cần exact immutable image digest,
license/SCA/provenance, model bundle checksums, compatibility evidence, hardware/
memory budget, exact acquisition and isolated synthetic live-test scope. CPU smoke
test nếu được duyệt cũng không chứng minh approved production latency thresholds.
Old 53-package/uv.lock approval explicitly excluded different model packaging;
delegated planning không được coi là pin/checksum hoặc live-environment evidence.
Không có một lệnh launch/download chưa pin được trình bày như action đã approved.

## Execution order after inputs are available

1. Review bundle against approved revisions/checksums/API/privacy boundary and
   exact packaging/live authorization. Then implement EMBED-002 and RERANK-002
   one objective at a time; deterministic transports first, real synthetic smoke
   only in the specifically approved environment.
2. Finish trusted CONTEXT-003 propagation: same object through graph/bootstrap,
   lexical/vector/reranker/citation, retries/degraded paths and delegate-only
   wrappers. Trusted resolver configuration is required; missing remains abstain.
3. EMBED-005/006 versioned ingestion/query/index compatibility; retain old data,
   parallel reindex/checkpoints and atomic pointer activation EMBED-007 only when
   its exact environment/operation is authorized. Never overwrite legacy vectors.
4. FILTER-004/005 actual pgvector authorization before ANN limit, filtered recall
   and cross-branch leakage. Only then complete FILTER-001 full runtime AC.
5. Finish RETRIEVE-001 constants/wiring and canonical RETRIEVE-002..006; bounded
   branches, deterministic RRF, provenance, context packing and explicit degradation.
   Profile loader passing alone does not complete production wiring.
6. RERANK-003/004, EVID/CITE, reviewed 500-case gold shards, real eval/ablation/
   subgroup gates. Do not author accepted gold against three legacy synthetic
   chunks or read sealed test text to improve implementation.
7. OPS/cache/performance/release only after upstream gates. Promotion/deployment
   requires its own exact authorization; no current release-readiness claim.

## Structured blockers

- B-MODEL-RUNTIME: missing verified private model-serving bundle and exact
  packaging/live scope. EMBED-002/RERANK-002 not_verified; downstream vector/index,
  canonical retriever, real eval and performance cannot be accepted.
- B-TRUSTED-SCOPE-BINDING: no production trusted resolver/institution binding.
  CONTEXT-003 propagation code still incomplete; no fabricated authorized scope.
- B-GOLD-CORPUS: no reviewed trusted active 1024 index/corpus snapshot. DATA-001..020
  cannot meet gold-exists-in-trusted-index/reviewer AC yet.
- Historical FILTER-001 initial-hash gap: audit limitation retained, not a claim
  that current source preservation has failed. New baseline is complete in its
  declared non-ignored source coverage.

Không coi mọi unfinished implementation task là external blocker: CONTEXT-003,
RETRIEVE-001 và canonical wiring còn code work sau khi bindings/upstream gates đủ.
Không downgrade quality/security hoặc đổi accepted documents để gọi toàn RAG done.
