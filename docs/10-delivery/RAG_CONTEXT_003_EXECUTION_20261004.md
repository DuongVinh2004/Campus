# TASK-RAGUP-CONTEXT-003 — propagation implementation evidence

2026-10-04, Asia/Bangkok. Direct human continuation/delegation; one objective,
no parallel chats/agents. Execution evidence only, not a normative change or
catalog acceptance. Dependency CONTEXT-002 accepted in the delegated decisions.

## Decision and scope

**Propagation code milestone verified; full objective not accepted.** Deployment
institution binding and trusted resolver remain external inputs. Real reranker,
canonical retry/degradation and complete citation resolver remain downstream work.
Passing fakes does not close those ACs or establish production readiness.

The orchestrator reviews a scope exception to the default three-file guideline:
this is one context call chain through seven existing product files, rather than
independent features. No identity mapping, claims contract, authorization grants,
SQL filter, dependency, migration, profile or security policy changes.

Existing product files, read before scoped patches:

- `services/api/src/campus247/agent/graph.py`
- `services/api/src/campus247/agent/nodes/definitions.py`
- `services/api/src/campus247/bootstrap/app.py`
- `services/api/src/campus247/presentation/chat.py`
- `services/api/src/campus247/infrastructure/retrieval/hybrid.py`
- `services/api/src/campus247/infrastructure/retrieval/vector.py`
- `services/api/src/campus247/application/retrieval/citations.py`

New synthetic tests: `tests/unit/retrieval/test_context_propagation.py`.
Supporting evidence files are exclusive-created; existing evidence retained.

## Preflight and preservation

Canonical workspace is `C:\Users\Duong Vinh\Vinh`. All targets and ancestors
checked for symlinks, junctions and reparse attributes before mutation. Git
status/diff and nonignored untracked inventory retained. New Add File targets
checked absent. No destructive Git/filesystem/resource operation performed.

`continuation-20261004-baseline.json`: all **1,196** hashes from delegated final
scope reverified; new baseline **1,197** files, written directly with open mode
`x`. Coverage is cached/nonignored untracked source; ignored runtime/credentials
excluded; self hash excluded. First baseline attempt stopped on an overbroad
credential-name assertion matching tracked `.env.example`, before any write;
corrected discovery distinguishes that template from actual credential files.
No `.env`, Docker config or container environment printed/read by agent commands.

Python **3.12.14** and **66 installed packages** match reviewed uv.lock; only
uvloop/httpx2-jsfetch platform exclusions. uv.lock SHA-256 remains
`f7727721cc9d433f506b53f2d644230cca9534f9dcd845565c474554888ca55e`.

Final scope evidence `continuation-20261004-context003-scope.json` confirms exactly
seven authorized existing changes; **1,190 other baseline files unchanged**,
including dirty/untracked artifacts, accepted filters/helpers and old evidence.
The historical FILTER-001 initial-hash limitation remains; no recovery claim.

## Behavior and AC mapping

| AC | Result | Evidence and limit |
|---|---|---|
| Same context reaches lexical/vector/rerank/citation | passed for current call chain | Per-invocation closure; object identity at both branch callbacks, legacy rerank node and both citation builds. RerankerPort/model and complete resolver not yet wired. |
| No arbitrary production dict context | passed for added boundaries | Typed factory/context checks; cross-actor rejection before graph; middleware identity passed by chat; forged client role/tenant/program cannot set scope. |
| Legacy wrapper delegates context | passed for hybrid/graph binding | Hybrid forwards the identical object to branches; context-aware graph never falls back to a callback that drops scope. Existing RRF remains legacy implementation pending RETRIEVE-005. |
| Context survives retry/degraded paths | partial, not_verified in full | Callback failure preserves trace ref and abstains; caller retry reuses same context. Canonical branch retry/degradation policy not implemented/accepted. |
| Trusted deployment bindings | not_verified | No institution identifier/verified issuer and role/program/audience resolver source supplied. No default ALL/FIT/STUDENT/program/tenant grant. |

Graph binds trusted context to each invocation, not mutable workflow fields or
serialized claims in AgentState. State keeps only opaque trace reference. Shared
workflow concurrent turns are isolated. Citation prompt/records omit context.
Bootstrap uses server clock and generated audit-safe trace; missing/invalid scope
abstains before retrieval callback. Vector still rejects before DB/provider/config.
The existing rerank scorer and evidence gate are not claimed as real model or
canonical claim-level gate; citation completeness belongs to CITE-001/002.

## Commands, exit codes and retained evidence

All Python commands use `infra/local/rag-fixture/.venv/Scripts/python.exe -B`.
Tests use `delegated_verify.py <label> <targets>`, fresh canonical temp/output
directories, retention_policy=all, deletion denial and outbound network/DNS denial.

| Command/label | Exit | Evidence |
|---|---:|---|
| scripts/verify_dependencies.py; tasks/tools/validate_catalog.py before mutation | 0 each | baseline JSON; VALID 241 tasks/10 phases; no RAGUP YAML materialized |
| context003-20261004-preflight: agent, factory/profile/citation units | 0 | delegated-context003-20261004-preflight.json; 195 passed |
| context003-20261004-implementation-01: new propagation, related units/architecture/app boot | 0 | delegated-context003-20261004-implementation-01.json; 271 passed |
| context003-20261004-broad-01: broad plus historical test_retrieval.py | 1 | 663 passed/1 failed; legacy default localhost:5433 DNS probe denied before network access; retained failed evidence |
| snapshot-context003-20261004-01 in sandbox | 1 | Docker external-command access denied, no DB access |
| same guarded read-only snapshot with escalated Docker access | 0 | delegated-snapshot-context003-20261004-01.json; receipt/labels/image/binding/mount/network/marker verified |
| context003-20261004-broad-02: tests/unit, tests/architecture, tests/evals, tests/api/test_app_boot.py, tests/integration/retrieval/test_lexical.py | 0 | delegated-context003-20261004-broad-02.json; **659 passed**, no skips/warnings |
| verifier, catalog, git diff --check, git diff --name-only, git status --short after implementation | 0 each | continuation-20261004-context003-scope.json |

No product repair was needed. Broad selection was corrected to the authorized
offline suite; concurrency test uses synchronous fake node paths to avoid the
existing process-wide socketpair guard racing during Windows asyncio loop setup.
Assertions and safety guard remain unchanged. All failed artifacts retained.

Snapshot remains head **0012**, 1 source/1 document/3 chunks, vector(1536),
329 columns/51 indexes/169 constraints and **active pointer 0**. Rows SHA-256
`00a182aedfa2abaa918c64404673621dda9e15199cb1aa920812828e81dbc0c2`;
indexes SHA-256 `aa812b4615ba831bf8ce8956ddda436068e01a6f12bd291b37244b4a7ddc7304`.
No live model or database mutation in this objective.

Next: RETRIEVE-001 independent profile wiring, then concrete model-runtime intake.
Do not open canonical retriever/vector/filter downstream acceptance before DAG
dependencies and exact runtime/trusted-index inputs are met.
