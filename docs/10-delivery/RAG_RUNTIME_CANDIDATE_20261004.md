# RAG model runtime — exact candidate and approval frontier

2026-10-04, Asia/Bangkok. Non-normative proposal/evidence, not runtime approval.
Direct request requires a concrete candidate before asking for exact packaging
or live scope approval. Nothing downloaded except public metadata/small configs;
no model weights, image filesystem layers, runtime install/pull/launch or inference.

## Current implementation outcome

CONTEXT-003 request-local propagation and RETRIEVE-001 independent profile wiring
implemented with retained evidence. Final regression label
`continuation-20261004-final-broad-01`: **679 passed**, no skip/warning, exit 0.
The final added guard also validates direct graph/retrieval-node context before
callbacks; lost/swapped/dict context cannot reach retrieval. Earlier execution
reports retain their point-in-time 659/678 counts and scope hashes; final bytes
and preservation are recorded in `continuation-20261004-final-scope.json`.

Neither whole objective is accepted/completed: real reranker/citation resolver,
canonical retry/degradation and tokenizer/evidence consumers remain downstream.
No fake model, legacy scorer or profile test is release/quality evidence.

Read-only search: infra/specs, bootstrap, delivery RAG artifacts, dependency
review records and source context resolver. No private service bundle, reviewed
deployment institution binding/resolver or trusted active 1024 corpus/index found.
Existing synthetic identities omit tenant binding; configuration label HUCE Demo
alone cannot establish institution identifier or actor program/audience grants.

## Immutable image and supply-chain evidence

Candidate: official Hugging Face **TEI cpu-1.9.4**, Linux/amd64, CPU HTTP build.

`ghcr.io/huggingface/text-embeddings-inference@sha256:8419f533857b503ebf6ec292a95d4f1cf9c0464ac8b8abeef39518cf110e5726`

- OCI index digest: `sha256:2538ea1c9640d3763b15af668039d24172d063b42337b0c27796fc2be180c78d`.
- OCI config digest: `sha256:8ce0330d3eae11511627a5b3eeef7001f76970ad3633d771147b57915c021dd7`.
- Source commit: `e80ef225ed0e6cb1717ce632a6a84b6cf211bb67`.
- Compressed image filesystem layers: **239,307,989 bytes**, not acquired.
- Published license label/source: Apache-2.0. Native Intel MKL redistribution
  terms and OS/native dependency license closure still require review.
- SLSA provenance statement digest:
  `sha256:1eb13ebe35c14977c771be38bf6411d636643f726609f7d4bb0484036ad2a56f`.
  Statement subject matches image digest; cryptographic signer/issuer verification
  is **not_verified**. Digest/provenance is not equivalent to signature verification.

Full evidence: `infra/local/rag-fixture/runtime-candidate-20261004.json`.
Includes OCI descriptors/config labels/provenance, source-file checksums, exact
**593** Cargo.lock package/version/source/checksum records. This is an inventory
of upstream lock, including optional/build/GPU packages, not a compiled CPU SBOM.
Representative pins: Candle core/nn/transformers **0.8.4**, tokenizers **0.21.4**,
hf-hub **0.4.3**, safetensors **0.4.5**, ort/ort-sys **2.0.0-rc.10**,
intel-mkl-src/tool **0.8.1**. App uv.lock and installed packages unchanged.

## Exact model-file manifest

| Model | Revision | Selected runtime files | Total bytes | Weight SHA-256 |
|---|---|---:|---:|---|
| BAAI/bge-m3 | 5617a9f61b028005a4858fdac845db406aefb181 | 10 | 2,293,315,801 | pytorch_model.bin: b5e0ce3470abf5ef3831aa1bd5553b486803e83251590ab7ff35a117cf6aad38 |
| BAAI/bge-reranker-v2-m3 | 953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e | 6 | 2,293,242,108 | model.safetensors: d9e3e081faff1eefb84019509b2f5558fd74c1a05a2c7db22f74174fcedb5286 |

All **16 exact paths/sizes/SHA-256/origin URLs** are in the JSON `models[].files`.
No wildcard model snapshot acquisition is proposed. Embedding includes tokenizer,
sentencepiece, config, sentence-transformers/module/pooling configs and dense
weight; sparse/ColBERT heads, ONNX and images are excluded from dense-only scope.
Reranker includes weight/tokenizer/sentencepiece/config. Metadata manifest hashes:

- Embedding: `9ade4a9786deff5ad4a31c1dc5cbbb719c0d97983f3c6ce5be01175fa5a5f19f`.
- Reranker: `a6e6d5c1ee0db7d1f0e37887f5ff48aef9df67ea790a089b86efbd680932bb2d`.

Model cards at exact revisions declare MIT (embedding) and Apache-2.0 (reranker).
Small config bytes were hashed in memory; LFS SHA values are upstream expectations,
**not verification of acquired/deployed bytes**. Acquisition must hash actual full
files and produce a new verified bundle before runtime/manifest use. Metadata
manifest checksum must not substitute for model bundle/index checksum.

Pinned Candle source selects `from_pth` for .bin and mmap safetensors for the
other format, and dispatches XLM-RoBERTa CPU models to its RoBERTa implementation.
The classification head handles the reranker config's single label. This resolves
the format suitability question at source-review level; exact-model load/output
remains **not_verified**, with no conversion or changed revision proposed.
[Pinned loader](https://github.com/huggingface/text-embeddings-inference/blob/e80ef225ed0e6cb1717ce632a6a84b6cf211bb67/backends/candle/src/lib.rs),
[classification source](https://github.com/huggingface/text-embeddings-inference/blob/e80ef225ed0e6cb1717ce632a6a84b6cf211bb67/backends/candle/src/models/bert.rs).

## Official protocol, not an invented API

Saved official OpenAPI **1.9.4**:
`infra/local/rag-fixture/runtime-candidate-20261004-openapi.json`, SHA-256
`83269464f2a6d3f4c36280ece0311f9cc0318e539928bb4fa106e091c017496f`.
[Pinned official specification](https://github.com/huggingface/text-embeddings-inference/blob/e80ef225ed0e6cb1717ce632a6a84b6cf211bb67/docs/openapi.json).

- `POST /embed`: inputs array; normalize=true, truncate=false; array of vectors.
  Dense query/document same model/revision, 1024 finite values, L2 normalization.
  No query/document-specific prompt is introduced.
- `POST /rerank`: query/texts, raw_scores=true, return_text=false, truncate=false.
  Response array of index/score; server adapter maps positional index only to
  supplied stable candidate IDs, rejects foreign/duplicate/out-of-range/non-finite.
- `GET /health`, `GET /info`: health/type/dimension/version checks. With local
  directories model_sha may be null; /info is not a full artifact checksum proof.
  Independently verified deployment bundle must bind exact model/revision/bytes.
- Official API supports bearer API key. Future private deployment must supply an
  approved secret-reference name/mechanism, never a secret/token in chat. No auth
  mapping or secret is created by this proposal.

## Hardware and isolated synthetic smoke proposal

Measured read-only: i7-10850H, 6 cores/12 logical; host RAM **16,762,388,480 bytes**.
Docker Linux/amd64: 12 CPUs, **8,118,734,848 bytes** memory (~7.56 GiB).
Quadro P620 is ~4 GB, not the selected CPU execution target. No GPU/CUDA setup,
driver/Docker allocation change or host Python/package installation proposed.

After SCA/compatibility clearance and **separate exact live approval**:

- Run one model container at a time, 4 CPUs and 5 GiB cap, read-only model mount,
  float32; reserve remaining Docker memory for existing services/fixture.
- Names: `campus247-rag-embed-smoke-20261004`,
  `campus247-rag-rerank-smoke-20261004`; separate internal network
  `campus247-rag-model-smoke-20261004`; no business DB access.
- Proposed host bindings: only `127.0.0.1:18081` embedding and `127.0.0.1:18082`
  reranker; reject existing-name/port collisions rather than reuse resources.
- Synthetic input <=128 tokens/item, max batch requests=1, max batch tokens=1024,
  bounded clients, no request text in logs/spans. Requests use truncate=false;
  oversized input must reject. Image MKL instruction setting must be validated
  for this CPU before launch; do not assume image AVX512 default is suitable.
- Embedding checks shape/norm/finite output/query-document parity; reranker checks
  ordered indices/raw finite scores and deterministic supplied-ID mapping.
- Do not connect model containers to the DB network, reindex, activate pointer,
  change 1536 legacy vectors or call real-data/provider services.
- All runtime/test artifacts and resources retained; no automatic removal/cleanup.

These settings are a bounded compatibility smoke proposal, not a new production
profile, production 8192-token behavior, quality evaluation or SLO evidence.
Model maximum is 8192 tokens; runtime max_batch_tokens/input limits and warmup
memory must be reviewed before any production envelope. Both simultaneous models
and approved 700ms reranker deadline cannot be promised on this hardware.

## SCA findings and required security decision

`runtime-candidate-20261004-sca.json`: OSV query against **576 registry crates**
in the pinned lock, **10 package entries / 8 advisory IDs**. Not a clean scan.

| Dependency | Finding | Required disposition |
|---|---|---|
| h2 0.3.27 | RUSTSEC-2026-0258, unbounded empty DATA frames | Prove CPU binary feature/reachability or use reviewed patched runtime |
| rustls 0.23.43 | RUSTSEC-2026-0285, TLS handshake encryption boundaries | Patched runtime/reachability decision; no production exception inferred |
| opentelemetry_sdk 0.19.0/0.22.1/0.23.0 | GHSA-w9wp-h8wv-79jx, W3C baggage memory allocation | Feature/reachability and mitigation review |
| number_prefix, opentelemetry_api, paste, proc-macro-error, yaml-rust | Five maintenance/deprecation advisories | Review linked metadata and runtime/build relevance |

Primary advisories: [h2](https://rustsec.org/advisories/RUSTSEC-2026-0258.html),
[rustls](https://rustsec.org/advisories/RUSTSEC-2026-0285.html),
[OpenTelemetry](https://github.com/open-telemetry/opentelemetry-rust/security/advisories/GHSA-w9wp-h8wv-79jx).
OS/native/MKL scan, binary feature reachability, license closure and signer
verification remain missing. No runtime launch approval is requested yet.
Replacing crate pins or rebuilding an image would be a different exact candidate,
not covered by old dependency approval or an approval for this digest.

## Concrete approval requested: acquisition/inspection only

Proposed first-stage authorization, limited to the above immutable image and 16
listed model files, followed by actual-byte verification and offline security/
license inspection. Image download would be about 239 MB compressed; selected
models total **4,586,557,909 bytes**. Check free space before acquisition and retain
all acquired bytes/evidence on failure. No launch/inference/deployment/activation.

Exact fresh workspace destinations to inspect/create only after authorization:

- `C:\Users\Duong Vinh\Vinh\infra\local\rag-fixture\runtime-acquisition-20261004\bge-m3`
- `C:\Users\Duong Vinh\Vinh\infra\local\rag-fixture\runtime-acquisition-20261004\bge-reranker-v2-m3`
- `C:\Users\Duong Vinh\Vinh\infra\local\rag-fixture\runtime-acquisition-20261004\image-oci`
- `C:\Users\Duong Vinh\Vinh\infra\local\rag-fixture\runtime-acquisition-20261004\review`

Image layers should be retained as OCI inspection artifacts in the displayed
workspace scope, rather than implicitly modifying an external Docker cache.
No tool installation is approved by this request; if image inspection needs a
new scanner/runtime, prepare a separate exact pinned tool candidate first.
Existing resources/files remain untouched. Later live approval must name the
reviewed image/bundles, endpoints/containers/network/hardware/input envelope.

Reason this approval is required: repository AGENTS.md Human approval section
requires stopping for "dependencies outside the approved allowlist" and
"paid external services or live-provider tests"; the direct handoff explicitly
excludes new runtime packaging from old 53-package approval. This first-stage
request concerns new image/model acquisition/packaging, not ordinary code approval.

## Verification and remaining blockers

| Command/read | Exit | Evidence |
|---|---:|---|
| fixture Python -B runtime_candidate_intake_20261004.py | 0 | Candidate JSON; exclusive creation of pinned official OpenAPI; 16 expected checksums/593 package pins/OCI provenance |
| fixture Python -B public OSV metadata query script | 0 | runtime-candidate-20261004-sca.json; exact hits and full public advisory records retained |
| Read-only CIM hardware/Docker info | 0 after sandbox escalation | Hardware above; no configuration mutation |
| Final retained broad regression | 0 | delegated-continuation-20261004-final-broad-01.json; 679 passed, no skips |
| Dependency/catalog/diff/scope final verification | recorded in final scope | No dependency/profile/SQL/corpus/pointer change |

- **B-RUNTIME-ACQUISITION:** exact first-stage acquisition/inspection authorization
  or an existing vetted private bundle needed. No image/weight bytes acquired.
- **B-RUNTIME-SECURITY:** SCA findings/native license/signer/binary review above;
  cannot claim approved runtime or ask a generic waiver for live execution.
- **B-TRUSTED-SCOPE-BINDING:** deployment institution identifier, verified issuer
  binding and reviewed resolver source for role validity/revocation, audience,
  faculty/program. No secrets requested; no user-controlled/default grants.
- **B-TRUSTED-CORPUS:** reviewed source/version/chunk/scope/provenance snapshot and
  corpus owner review. Activation requires separately validated 1024 manifest;
  three legacy synthetic chunks cannot satisfy 500-case gold acceptance.

EMBED-002/RERANK-002 wait for exact runtime/dependency approval; then EMBED-005/006,
FILTER-004/005, canonical retrieval, rerank/evidence/citation, trusted gold/eval and
OPS/performance/release follow the original DAG. No downstream accepted gate is
invented to bypass these inputs, and no sealed-test text was read.
