---
document_id: "DOC-DELIVERY-CHAT-STREAM-20261005-04"
version: "1.0.0"
status: "not_verified"
owner: "Campus 24/7 Engineering"
last_updated: "2026-10-05"
---

# Approved frontend run — typecheck passed; Vitest initialization blocked

**TypeScript verified; streaming objective remains not_verified.** TypeScript
5.6.3 checked **150 files with zero diagnostics**, exit0. Vitest executed **zero
tests / zero suites** and reported three unhandled initialization errors, exit1.
The cancellation source patch and two new regressions from report03 are preserved;
their assertions have not run. No product file was changed in this turn.

## Authority and preservation

The human replied “ok phê duyệt” directly to the concrete P-FE-VERIFY-005 question,
including the exact OS sandbox exception. Approval is recorded separately in
`infra/local/rag-fixture/chat-stream-20261005-03-frontend-approval.json`, SHA256
`822cdde244a6e6867a452eb71b59a57a5190f82ad00196faa0d25856eabbea91`.
The approved packet bytes and all old receipts/reports remain immutable. This
approval grants no installation, pin change, live service, DB/container,
browser/build, guard modification or independent release/security acceptance.

One objective: API/UI reflect approved streaming outcomes under accepted
P-CONTRACT-STREAM-001 and execution plan v0.2.0. FE scope is `apps/web`;
`frontend/` is excluded from this project. Shared Python dependency work owned
elsewhere was not edited.

Fresh baseline `chat-stream-20261005-04-baseline.json`, SHA256
`0185ca54939bc7048e4a5c65c69862ced781668238e6b505255ca2ada02d0428`,
captured **1,602 covered pre-existing files**, current Git state and exact output
scope. All matched before runtime. The 158 approved source inputs, runtime,
package closure and tooling hashes matched; all 23,026 installed dependency file
hashes were rechecked by each launcher before output creation. Four previously
inaccessible historical fixture files and inherited sensitive/model/other-FE
coverage exclusions remain explicitly not_verified. No access/ACL change was
made to inspect them.

## Attempts and exact evidence

Commands used approved fixture Python 3.12.14 `-B`, the same signed bundled Node
24.19.0 and sanitized test environment. Each child had a 120-second limit. All
outputs remain under the originally approved
`infra/local/rag-fixture/chat-stream-20261005-01-frontend-run-01` root.

| Fresh attempt | Launcher under `infra/local/rag-fixture/` | Version / typecheck / tests |
|---|---|---|
| Initial | chat-stream-20261005-03-frontend-launch.py | 0 / 1 / not executed |
| attempt-02 | chat-stream-20261005-04-frontend-launch.py | 0 / 0 / 1 |
| attempt-03 | chat-stream-20261005-04-frontend-launch-02.py | 0 / 0 / 1 |

Initial failure: Node `--import` treated the Windows absolute path as unsupported
scheme `c:`; guard/typecheck did not load. Routine repair1 uses `Path.as_uri()` to
name the identical guard file. The derived runner only binds artifact output to
a fresh child label within the same approved root; original test selection,
diagnostics, assertions and all guard bytes remain unchanged.

Attempt02: typecheck passed. Vite's default `localhost` hostname triggered its
DNS lookup helper; the original DNS guard denied it before tests. Routine repair2
sets `server.host` to literal `127.0.0.1`, avoiding that lookup. This config change
allows no socket/listen/network action and changes no expected results. Fresh
mutation baselines and binding reviews retain both failures and exact diffs.

Attempt03: typecheck passed again. Vitest's package-scope resolver attempted a
read beyond the workspace boundary, denied by guard line29. Its resulting
“Cannot find dependency 'jsdom'” message is a guarded resolution failure, not
evidence that the inventoried package is absent. Vite's Windows realpath helper
also invokes `child_process.exec('net use')`; the existing subprocess restriction
denied it. Three initialization errors prevented all test collection/execution.
Read-only inspection of installed Vite source confirms these helper branches;
no package source was edited and the denied command was not permitted to run.

The original guard remains byte-for-byte SHA256
`4a21d9563bab6a10f9e76c6a20fb2ec201f65363f4cc83e103ad643b52933368`.
It was neither disabled nor relaxed to make tests pass. Two materially different
tooling repairs were attempted; no source implementation repair was attempted.
Root AGENTS requires stopping after two different repairs, so no further runtime
retry or harness change follows this attempt.

Evidence summary `chat-stream-20261005-04-frontend-result.json`, SHA256
`477c74e8e970de9b14789dece9cf7e3200869cb19e6009274c208a5e87829e22`,
links all command records. Final typecheck JSON is under
`...frontend-run-01/attempt-03/typecheck.json`; Vitest JSON/log are siblings.
Vitest JSON misleadingly has `success:true` with zero suites/tests. That flag is
**not accepted**: zero execution, the three log errors and launcher exit1 govern.
Initial commands.json retains the inherited text “OS sandbox remains mandatory”;
the unchanged P-FE-VERIFY-005 receipt records the actual approved exception.
This stale descriptive field was disclosed, not overwritten.

## Verification and remaining boundary

Dependency verifier, catalog and OpenAPI checks passed in order, exit **0/0/0**,
before execution. Final verification records them again in
`chat-stream-20261005-04-final-verification.json`. Final scope retains command
exit codes, `git diff --check`, diff names/status, all 1,602 covered hashes and
all new output hashes, including failed runs. No cleanup, deletion or overwrite
of pre-existing output/evidence occurred. No product file was changed this turn.

Verified: approved Node runtime execution and static typing of current web source.
Blocked: executing the three streaming suites under the unchanged guard on this
Windows toolchain. This is runtime tooling incompatibility; UI correctness is
not established by the passing typecheck. The next runtime approach needs a
reviewed way to avoid parent-scope reads and the Windows process helper while
retaining protections. Broad parent reads, subprocess exceptions, package edits
or guard changes are not authorized by this result.

Browser/build acceptance, durable transcript/storage, server-side cancellation,
real providers/RAG and M1/M2/M3 remain **not_verified**. No downstream objective
was started before streaming acceptance; prior 58 passing backend tests remain
historical retained evidence, not a new backend run in this turn.
