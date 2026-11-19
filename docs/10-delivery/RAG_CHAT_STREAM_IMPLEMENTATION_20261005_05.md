---
document_id: "DOC-DELIVERY-CHAT-STREAM-20261005-05"
version: "1.0.0"
status: "not_verified"
owner: "Campus 24/7 Engineering"
last_updated: "2026-10-05"
---

# Streaming verification — unit suites pass; browser startup remains blocked

**Streaming objective remains not_verified.** The three required frontend suites
executed **47 tests, all passed**, with no skips or unhandled errors. TypeScript
5.6.3 checked **150 files, zero diagnostics**. The guarded backend regression
selection executed **58 tests, all passed**. The real chat client bundle built
without errors/warnings. Browser acceptance executed **zero cases**: Chrome
failed its remote-debugging data-directory check and timed out before attachment.
Neither an exit0 without a receipt nor a successful client build is browser pass.
Full Next production build, durable storage and real RAG M1/M2/M3 remain open.

## Scope and authority

Direct human pasted request dated2026-10-05 authorizes ordinary implementation,
the exact Node/dependency closure, a new Windows harness/guard, four additional
approaches for the previously blocked frontend harness, and bounded local
browser/build verification. P-CONTRACT-STREAM-001 and execution plan **0.2.0**
remain the behavior authority. No requirement, contract, security policy,
dependency pin, threshold, assertion or product source was changed in this run.
`apps/web` is the FE. `frontend/` was not read as product/dependency input, run,
changed, or included in Campus verification coverage. No agents/chats were created.

Read/reconciled root instructions, document control/accepted streaming decision,
PRD6.1, API_CONVENTIONS8.1, stream/error/citation schemas, error/memory/AI/RAG
contracts, data persistence references, dependency policy, plan0.2.0,
CONTEXT-003/RETRIEVE-001, runtime review, prior streaming reports and runtime
packets. No task catalog state or dependency acceptance was fabricated.

New files are this report and `chat-stream-20261005-05-*` evidence/tooling under
`infra/local/rag-fixture`, plus `chat_stream_20261005_05.py`. New artifact/profile
paths are exclusive-created. Historical receipts, guard, runner and failures
remain immutable. Product cancellation code/regressions inherited from report03
ran successfully without an implementation repair.

## Runtime binding and new harness behavior

- Fixture Python **3.12.14**, invoked with `-B`.
- Exact Node **24.19.0** at the directly approved bundled path; SHA256
  `3602f2bb1a10f2cbab4c36886218a33c1ab3db87290e73b033c46c77147d0237`.
- Active inventory SHA256
  `529b16fbc4acc819b42a36a5d425c5315b6e9d56d70f163c4ea137e0e4f8e625`;
  **274 records / 23,026 dependency hashes** revalidated before each launcher.
  Importer targets and lock binding were also checked by the unit launcher.
- Historical guard SHA256 remains
  `4a21d9563bab6a10f9e76c6a20fb2ec201f65363f4cc83e103ad643b52933368`.

Before: report04 could not collect tests due to parent package scope probing and
Vite's Windows realpath helper attempting `net use`.
After: the new guard normalizes URL and Windows `/C:/` paths before checking
containment, then returns synthetic ENOENT for outside-workspace `package.json`
probes without read/stat/realpath of the outside target. Callback and promise
forms retain their API behavior. Realpath native entrypoints are guarded too.
Vite `resolve.preserveSymlinks=true` avoids the Windows helper, and the server host
is literal127.0.0.1. Module paths are explicit where the installed pnpm closure
requires them. DNS, arbitrary subprocesses, destructive FS operations, credentials,
dormant packages, foreign FE and writes outside the bound output remain denied.

The containment probe passes URL/path equivalence, synthetic parent-scope errors,
credential/foreign/outside read denial, product-write/deletion/DNS denial and
`net use` denial. These JavaScript guards are not an independent OS sandbox or
native-browser security clearance; the human's explicit OS exception remains
scoped to the approved execution. No source inside node_modules was modified.

## Commands, failures and repair accounting

Commands below run from the canonical workspace with the exact fixture Python
path `infra/local/rag-fixture/.venv/Scripts/python.exe -B`. Each JSON receipt
records exact child argv, cwd, hashes and exit codes. No output label was reused.

| Command / evidence label | Result |
|---|---|
| `chat_stream_20261005_05.py preflight` | dependency → catalog → OpenAPI exit0/0/0 |
| `chat-stream-20261005-05-launch.py` / `run-01` | version0; containment0; typecheck0; tests1; zero assertions |
| `chat-stream-20261005-05-launch-02.py` / `run-02` | version0; containment0; typecheck0; tests0; **47/47 passed** |
| `chat_stream_20261005_05.py backend-suite-01` | exit0; **58 passed**, no skips |
| `chat-stream-20261005-05-browser-launch.py` / `run-browser-01` | exit1 before build/browser; bare playwright-core resolution failed |
| `chat-stream-20261005-05-browser-launch-02.py` / `run-browser-02` | raw exit0, **not accepted**; client build succeeded but no browser receipt/cases |
| `chat-stream-20261005-05-browser-launch-03.py` / `run-browser-03` | raw/qualified exit1; client build succeeded; Chrome startup timeout; **0/21 cases** |
| `chat_stream_20261005_05.py final-verification` | dependency → catalog → OpenAPI exit0/0/0 |
| `chat_stream_20261005_05.py final-scope` | Git diff check/names/status and covered-byte audit; see final receipt |

Two new approaches were used for the report04 frontend initialization harness.
First solved its parent-resolution/helper problems, but incorrectly put
`preserveSymlinks` into esbuild transform options, which that API rejects. The
second removed only that transform option, keeping Vite/build resolution settings;
all original required tests/assertions then executed. Both attempts are retained,
with fresh baselines and exact guard/runner diffs in binding/repair receipts.

The separate browser harness had two materially different repairs:1) explicit
inventoried Playwright core path, with provisional assertions scoped to the active
turn so prior final citations remain visible;2) literal-IP bind without a DNS
lookup and moving startup awaits into the failure-reporting boundary. The second
also removed exception listeners that could consume an early failure and added
mandatory positive execution-receipt/case-count checks. Browser02's raw exit0 is
explicitly invalid; its receipt is preserved rather than corrected in place.
No production implementation repair was attempted.

## Browser evidence and limits

Chrome **154.0.8037.93**, Authenticode Valid, executable SHA256
`1e9412868bbc9faff92d129babd17331e7ceab0702cc07db02a34f3438ae04f2`.
Packets bind exact commands and fresh profile/output. CDP uses local pipes;
Chromium sandbox remains enabled. Only frontend127.0.0.1:3107 and synthetic
API127.0.0.1:3108 are served. Literal-IP lookup is synthesized without DNS;
other DNS remains denied. A renderer allowlist and a local proxy rejecting CONNECT
block outside destinations; denied native background requests are retained.
The test environment prevents the existing shell's real demo-session startup.

The bundle uses actual ChatPage/ChatPanel/SSE source and installed React. The
test-only Next link adapter renders navigation anchors; a fixture HTML wrapper
isolates root font/framework startup. No product streaming behavior is mocked.
Build errors/warnings are zero, with source map/metafile retained. This validates
the chat client bundle, **not** complete Next routes/SSR/CSS/production packaging.

Browser03 spawned the bound Chrome with the correct requested fresh profile,
but Chrome reported:
`DevTools remote debugging requires a non-default data directory. Specify this using --user-data-dir.`
It also reported inability to retrieve its AppData directory, then failed the
30-second attachment deadline. Browser receipt has `passed:false`, no cases,
and no UI screenshots. A hypothesis is that sanitized AppData paths must exist
before native startup; this is not yet proven.

Playwright could not finish closing the timed-out browser under the subprocess
restrictions. The exact test-owned PID20288 was independently matched against
the Chrome executable, fresh profile argument and CDP pipe argument before a
scoped Stop-Process. Its absence and absence of listeners3107/3108 were checked.
All profiles/artifacts remained; no taskkill/net-use permission was added.

Required browser cases remain not_verified: success, abstention, safe
failure/timeout, guard rejection, fragmentation/UTF-8/newlines, malformed/unknown
events, missing terminal EOF, failure after provisional, cancellation/loading,
late callbacks, request/message correlation and per-message citation isolation.
The corresponding unit cases pass; this does not substitute browser execution.

## Preservation, acceptance and next action

The handoff scope SHA256 matched
`41375b76a774535e1accf13ec490f770f8ebf6269c832844a1689a202fcdb051`.
Fresh baseline captures **1,632 pre-existing files**, with zero historical drift,
current Git state and inherited exclusions. Mutation checkpoints rehash these
current bytes; no historical restoration occurs. Final scope records exact new
hashes and validates all covered pre-existing bytes unchanged. Four historically
inaccessible fixture files remain explicitly not_verified; no ACL/DB operation
was used to read them. Ignored secrets/models and other FE stay excluded.

Incremental scope contains new tooling, prepared packets and evidence only;
there is no incremental product diff. Existing dirty, untracked and dependency
work is preserved. No install, live model/provider/DB, real session/credential,
commit/push/deploy, destructive operation or history rewrite occurred.

Under root AGENTS, after two browser repairs this harness stops. Prepared
**P-FE-BROWSER-006**, not executed, requests an explicit exception for at most two
additional browser startup repairs. Exact packet SHA256:
`5fd4309a4ff8771098f9bf7edec27975bddf104691f503fd6890775d96a07726`.
It first pre-creates fresh profile/AppData/temp/artifact paths with the same
Chrome/guard/scenarios; only if startup still fails, it uses already-installed
Edge154.0.4258.53, Authenticode Valid, SHA256
`39966f2799d3503e74871c945ba1c4877f38426d1c28756ab1545ad7c3de8907`.
Only the browser-version assertion changes for that alternative. There are no
new runtime downloads, broader egress, personal profiles or skipped cases.
Execution requires a new direct-human receipt bound to this packet's hash.

Streaming is not accepted; G0–G7 execution has not been opened by these partial
checks. Existing independent runtime review, trusted institution/corpus,
provider/model/endpoint/cost and release gates remain unchanged. Continue the
same streaming objective when the concrete browser retry exception is authorized.
