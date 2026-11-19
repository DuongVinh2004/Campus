---
document_id: "DOC-DELIVERY-CHAT-FRONTEND-PACKET-20261005-03"
version: "0.1.0"
status: "proposed"
owner: "Campus 24/7 Engineering"
approvers: []
last_updated: "2026-10-05"
---

# P-FE-VERIFY-005 — current cancellation patch and explicit OS sandbox exception

**Proposed, not approved or executed.** This packet requests one bounded offline
typecheck and the three existing streaming suites against the current `apps/web`
source, including two new cancellation regressions. `frontend/` is outside this
project. P-FE-VERIFY-004 remains immutable and approved only on its original terms.

## Exact proposed exception

The current host permission profile is `danger-full-access`, with no OS filesystem
sandbox. The original packet explicitly required that sandbox. Full access and
general permission to continue do not authorize removing that requirement.

The requested human approval must explicitly accept **running these exact Node
commands without the OS sandbox**, while retaining the existing JavaScript guard,
sanitized child environment, exact hashes, output restrictions and bounds. This
is an exception solely to the OS sandbox requirement of P-FE-VERIFY-004 for this
one run. No global/project safety rule, ACL, hook, guard, dependency pin, backup or
existing evidence is edited. Approval grants no destructive operation or access
to real credentials, personal data, production, DB/container or live providers.

JavaScript guards are not an OS security boundary: native modules or internal
loaders can bypass them. Package hashes and declared licenses do not establish
independent security clearance. Native hook efficacy is not yet runtime verified.
The alternative is a reviewed sandboxed environment with read access to this
exact installed closure; no package install, copying/relinking or permission
changes are proposed as a workaround. Independent security and release gates
remain separate; this packet cannot confer production acceptance.

## Bound inputs and tools

Node path:
`C:\Users\Duong Vinh\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe`.
Read-only metadata rechecked: **24.19.0**, Authenticode **Valid**, OpenJS Foundation,
SHA256 `3602f2bb1a10f2cbab4c36886218a33c1ab3db87290e73b033c46c77147d0237`.
Node has not executed. The launcher uses the approved fixture Python 3.12.14 `-B`.

Exact installed dependency set: the unchanged
`infra/local/rag-fixture/chat-stream-20261005-01-frontend-active-inventory.json`,
SHA256 `529b16fbc4acc819b42a36a5d425c5315b6e9d56d70f163c4ea137e0e4f8e625`:
**274 reachable package records / 23,026 file hashes**. Every package file was
rehashed unchanged in the current environment, recorded in
`chat-stream-20261005-03-frontend-readiness.json`, SHA256
`d4b077f24b00000f4feb15c2e2be0fe2df07164bfb4b443182da4390620206ac`.
All 20 importers and versions remain as listed in P-FE-VERIFY-004; Next16.3.8,
React19.3.0, TypeScript5.6.3, Vitest2.1.9 and jsdom25.0.1. React types remain
18.3.31/18.3.7; diagnostics cannot be suppressed. No pins or installs are proposed.
Dormant records stay preserved and denied by the original guard.
Repository lock SHA256 remains
`edef03a93579c1da1014991ed7453a6413d32d88b574a8c37d41731fc354f58e`.

Current 158-file source-input manifest:
`chat-stream-20261005-03-frontend-source-inputs.json`, SHA256
`e6a5efa410c67234d7ae6d31038802b07268d72caa694405fa96abc74e0949c2`.
Fresh launcher: `chat-stream-20261005-03-frontend-launch.py`, SHA256
`76f0f13891df7fd394bfa67190a4f124e6e16f80c007d9768f0a37cecf24d4dc`.
Python AST parsing passed; execution remains pending. The original guard and
runner are reused byte-for-byte:

| File under `infra/local/rag-fixture/` | SHA256 |
|---|---|
| chat-stream-20261005-01-frontend-guard.mjs | `4a21d9563bab6a10f9e76c6a20fb2ec201f65363f4cc83e103ad643b52933368` |
| chat-stream-20261005-01-frontend-verify.mjs | `ed4efa5021f9d77c594fb3f677b79f4bc036b2a6dcac496ad51e762a6e071a7b` |

## Exact execution and output scope

After direct human approval specifically accepting the exception, exclusive-create
`chat-stream-20261005-03-frontend-approval.json` with packet_id `P-FE-VERIFY-005`,
status `approved`, actual human reference, this packet SHA, inventory/source/guard/
runner SHAs, and `os_sandbox_exception` equal to
`explicit-human-approved-P-FE-VERIFY-005`. No approved receipt exists now.

Exact command, cwd `C:\Users\Duong Vinh\Vinh`:

```powershell
& 'C:\Users\Duong Vinh\Vinh\infra\local\rag-fixture\.venv\Scripts\python.exe' -B 'infra/local/rag-fixture/chat-stream-20261005-03-frontend-launch.py'
```

Sequential child commands: exact Node `--version`, then Node `--import` the original
guard and original runner with `typecheck`, then `tests`. Each has a 120-second
limit and stops on failure. Full runtime/package/lock/source/tool hashes are
rechecked before output creation. Any changed bytes, unreadable inputs or missing
approval stop execution. No source mutation by the runner is allowed.

Only Node write/output scope is the still-absent original fresh directory:
`C:\Users\Duong Vinh\Vinh\infra\local\rag-fixture\chat-stream-20261005-01-frontend-run-01`.
The previous approved attempt never created it or launched Node. The new receipt
and commands.json identify this packet independently. A later retry needs fresh
reviewed output binding; never overwrite or clean existing evidence.

The launcher sanitizes child environment to literal test/CI/telemetry and
workspace temp/profile paths. Typecheck uses noEmit, incremental=false and no
tsbuildinfo overwrite. Tests select only `sse.test.ts`, `ChatPanel.test.tsx`, and
`app/chat/page.test.tsx`; single worker, jsdom, synthetic fetch/streams/storage,
no watch/HMR/cache, configFile=false, envFile=false and no lifecycle scripts.
The guard retains credential/config/foreign/dormant read denial, DNS/socket
denial, output-only writes and deletion/rename/permission denial. Only the exact
installed esbuild0.21.5 executable service arguments may spawn with windowsHide.
No browser, server, build, dotenv/font fetch, package manager or network test.

Acceptance: zero typecheck diagnostics; all three suites pass, no unhandled
errors or skipped assertions; retain unknown/malformed/EOF/failure/abstention,
correlation/citation isolation, cancellation/loading and both new delayed
transport regressions. Maximum two materially different implementation repairs,
with fresh baselines and retained failures. A failure is not success.

Browser/build require separate approval. Streaming browser acceptance, durable
storage, real RAG, M1/M2/M3, tools/actions and handover receipts remain open.
