# TASK-RAGUP-RETRIEVE-001 — profile runtime wiring milestone

2026-10-04, Asia/Bangkok. Direct human objective, dependency GOV-001 approved.
Non-normative execution evidence; no catalog status/requirements/threshold changes.

**Independent profile wiring verified; entire objective remains not_verified.**
Profile schema/loader already existed. This milestone removes bootstrap top-10
overrides and wires lexical/semantic counts, RRF/fusion and branch/overall
deadlines. Missing/mismatched runtime metadata fails before branch access.
Reranker/tokenizer/context/evidence/retry/fallback consumers require downstream
implementation and verified runtime/corpus; profile tests do not complete them.

## Preflight and changes

Canonical/reparse checks and git status passed; scoped exclusive baseline is
`infra/local/rag-fixture/continuation-20261004-retrieve001-baseline.json`.
Source was read before patching. Previous CONTEXT-003 changes remain preserved.
No lockfile/package, SQL, manifest activation, identity grant or migration change.

- `services/api/src/campus247/infrastructure/retrieval/hybrid.py`: defaults derive
  from immutable profile; production composition rejects overrides/dict profile
  and requires typed context plus independently supplied active-index/checksums.
  Each branch uses profile timeout; overall deadline bounded. Failure cancels and
  joins sibling tasks and propagates; no implicit successful-empty/degraded mode.
- `services/api/src/campus247/bootstrap/app.py`: passes loaded profile, removes
  fusion_k=10/top_k=10. No runtime binding is fabricated; query remains disabled.
- New `tests/unit/retrieval/test_profile_wiring.py`: synthetic profile/binding
  positive/negative tests, counts/fusion/RRF assertions, timeout cancellation and
  actual bootstrap callback propagation.

The legacy helper without explicit production profile retains offline regression
compatibility. It is not an approved canonical service or production activation.
`hybrid_search` keeps its algorithm; duplicate implementations/dedupe semantics
belong to RETRIEVE-002/005, not silently accepted by this patch.

## AC mapping

| AC | Status | Evidence/remaining work |
|---|---|---|
| Versioned complete immutable profile | passed | Existing complete-field/mutation/type/model/index/checksum tests; no profile values changed |
| Missing/mismatched runtime metadata fails query before DB/provider | passed for explicit profile composition | Missing binding/independent index/hash and seven mismatch cases reject before branch callbacks |
| Production candidate counts/RRF/fusion/deadlines derive from profile | passed for current bootstrap/hybrid call chain | 30 per branch, 20 fused, constant 60, 400/700/1800 ms; no top-10 override; sibling cancelled/joined on timeout |
| All production constants/consumers wired | not_verified | Real reranker, model tokenizer/context budget, canonical evidence/repair and eval-approved retry/fallback not ready; legacy helpers retain historical test semantics |
| Verified model/index startup and full pipeline | not_verified | No real serving artifacts/active 1024 manifest/trusted deployment resolver; bootstrap remains abstain |

Compatibility guard accepts caller-supplied trusted metadata, but is not a DB
active-pointer reader or proof that an inference service matches deployed bytes.
Those duties remain EMBED-006/007. No OPS/canonical downstream dependency is opened
by calling this partial milestone accepted.

## Verification and recovery

All commands use fixture Python 3.12.14 with `-B`; deterministic retained runner
blocks outbound/DNS and deletion, uses fresh canonical temp paths, keeps failed
artifacts. No implementation repair required.

| Command | Exit | Evidence |
|---|---:|---|
| delegated_verify.py retrieve001-20261004-implementation-01 tests/unit/retrieval tests/unit/agent tests/architecture tests/api/test_app_boot.py | 0 | delegated-retrieve001-20261004-implementation-01.json; 469 passed, no skip/warning |
| delegated_verify.py retrieve001-20261004-broad-01 tests/unit tests/architecture tests/evals tests/api/test_app_boot.py tests/integration/retrieval/test_lexical.py | 0 | delegated-retrieve001-20261004-broad-01.json; **678 passed**, no skip/warning |
| scripts/verify_dependencies.py; tasks/tools/validate_catalog.py; git diff --check | 0 each | Verifier exact pins/hashes pass; catalog 241/10; final-scope evidence retained separately |

Final scope hashes compare every original baseline file; seven existing product
files changed across both sequential objectives, all other 1,190 baseline files
preserved. New test/evidence/report bytes are included in final manifest; ignored
runtime/credential files excluded. No commit/push/deploy/delete/reset/cleanup.
Safe state: absent runtime metadata causes abstention; legacy vectors/index/data
unchanged. Recovery is a scoped reviewed forward patch, never workspace reset.

Next: exact runtime packaging/acquisition proposal. EMBED-002/RERANK-002 and
downstream remain gated by specific runtime approval/bundle and trusted corpus.
