---
document_id: "DOC-DELIVERY-CHAT-FRONTEND-PACKET-20261005-01"
version: "0.1.0"
status: "proposed"
owner: "Campus 24/7 Engineering"
approvers: []
last_updated: "2026-10-05"
---

# P-FE-VERIFY-004 — current offline streaming verification

**Proposed, not approved or executed.** P-FE-VERIFY-003 remains historical and
unapproved. This fresh packet binds current Next 16/React 19 source and installed
bytes. It requests one bounded offline TypeScript run and three Vitest suites;
browser/build/live services require separate packets. No receipt exists.

The direct handoff explicitly requires exact runtime approval. AGENTS.md,
DEPENDENCY_ALLOWLIST section 3 and execution plan 0.2.0 G0 do not grant execution
clearance to Vitest/jsdom/Testing Library, Lucide/Markdown/Playwright and their
transitive packages. Ordinary engineering authorization and installed bytes do
not resolve that gate. This packet neither changes the allowlist nor waives an
applicable independent/security review.

Runtime, inventoried without executing Node:

```text
C:\Users\Duong Vinh\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe
Metadata version 24.19.0; current bundle 26.1004.11800
SHA-256 3602f2bb1a10f2cbab4c36886218a33c1ab3db87290e73b033c46c77147d0237
Authenticode Valid; OpenJS Foundation
```

The launcher itself uses only the approved fixture Python 3.12.14 `-B`.
Node `--version` is the first future command; metadata is not execution evidence.

Exact dependency permission scope is **274 reachable installed package records /
23,026 file hashes** in
`infra/local/rag-fixture/chat-stream-20261005-01-frontend-active-inventory.json`.
SHA-256: `529b16fbc4acc819b42a36a5d425c5315b6e9d56d70f163c4ea137e0e4f8e625`.
This JSON enumerates every name/version/path/license/engine/file hash.
Actual dependency/optional/peer links are recorded in `...-active-closure.json`,
SHA `62a4105d752a344b4ff4f8d14cde13bbdc88bba0aec5d20860de03c1b9e45138`.
All 20 web importers match current lock versions; zero required missing or foreign
links. Optional absent platform/peer records remain explicitly recorded.

| Direct package | Installed version |
|---|---|
| next; react; react-dom | 16.3.8; 19.3.0; 19.3.0 |
| lucide-react; react-markdown; remark-gfm | 1.52.0; 10.1.0; 4.0.1 |
| @playwright/test | 1.63.0 — no browser execution in this packet |
| typescript; vitest | 5.6.3; 2.1.9 |
| jsdom; happy-dom | 25.0.1; 20.14.5 — jsdom selected |
| @testing-library/react; @testing-library/jest-dom | 16.3.3; 6.10.0 |
| @types/node; @types/react; @types/react-dom | 20.19.43; 18.3.31; 18.3.7 |
| tailwindcss; @tailwindcss/postcss; postcss | 4.3.3; 4.3.3; 8.5.28 |

Repository and installed locks match SHA
`edef03a93579c1da1014991ed7453a6413d32d88b574a8c37d41731fc354f58e`.
React runtime/types now have different major versions; diagnostics must remain
visible. No pins/config/oracles may be changed to make verification pass.

The complete store inventory contains 290 records / 42,893 file hashes, including
16 dormant records. Thirteen dormant records are absent from current lock.
These are preserved, not removed or treated as active dependencies. Their
original inventory issues remain in `...-frontend-inventory.json`, SHA
`53e248464a70b746164ecaf7019dfb457ac923f77829d343f1464905aa69f973`.
Fresh closure inspection determines reachability, not a weakened old validator.
The fresh guard also denies dormant paths and their resolved targets.

Unpacked hashes do not prove registry tarball integrity or independent security
clearance. License declarations are inventoried, not signed license dispositions.
Native modules can bypass JavaScript hooks; an OS sandbox remains required.
No elevated Node run is authorized by this packet. A sandbox read denial must
stop the run; do not relax controls or install/relink/delete packages to pass.

Prepared tools, not runtime verified:

| File under `infra/local/rag-fixture/` | SHA-256 |
|---|---|
| chat-stream-20261005-01-frontend-launch.py | `2b9f8cf9703b4d56461ab201c49d90b84a2afc9f3ef368cb2a6d6cba097d6e98` |
| chat-stream-20261005-01-frontend-guard.mjs | `4a21d9563bab6a10f9e76c6a20fb2ec201f65363f4cc83e103ad643b52933368` |
| chat-stream-20261005-01-frontend-verify.mjs | `ed4efa5021f9d77c594fb3f677b79f4bc036b2a6dcac496ad51e762a6e071a7b` |

Source inputs, including existing generated `.next/types` TypeScript when present,
are bound by `...-frontend-source-inputs.json`, SHA
`43cc79dac56ccf125fd484eda1de2164bcc9aa480c69f50590112ebbb7a5890a`.
Launcher rehashes runtime, active package files, lock, tooling and source inputs
before creating its fresh output directory. Changed bytes invalidate the packet.

After actual direct human approval and any applicable clearance, exclusive-create
`infra/local/rag-fixture/chat-stream-20261005-01-frontend-approval.json` with packet
ID P-FE-VERIFY-004, actual human message reference, packet SHA, active inventory
SHA, source-input SHA, guard SHA and runner SHA. Never create an approved receipt
from this document or from ownership/engineering authorization alone.

Exact launcher, cwd `C:\Users\Duong Vinh\Vinh`:

```powershell
& 'C:\Users\Duong Vinh\Vinh\infra\local\rag-fixture\.venv\Scripts\python.exe' -B 'infra/local/rag-fixture/chat-stream-20261005-01-frontend-launch.py'
```

Its exact child commands use the Node path above:

```text
<Node> --version
<Node> --import <absolute fresh frontend-guard.mjs> <absolute fresh frontend-verify.mjs> typecheck
<Node> --import <absolute fresh frontend-guard.mjs> <absolute fresh frontend-verify.mjs> tests
```

Typecheck uses existing tsconfig via TypeScript API, noEmit and incremental=false;
no overwrite of tsbuildinfo. Tests select exactly:

```text
apps/web/src/features/chat/sse.test.ts
apps/web/src/features/chat/ChatPanel.test.tsx
apps/web/src/app/chat/page.test.tsx
```

Runner uses jsdom/globals, current alias/JSX semantics, single thread, no watch,
cache or HMR; configFile=false avoids config bundling/deletion; envFile=false
prevents dotenv loading. It does not invoke package-manager/lifecycle scripts.
Current PostCSS/Next modules are in the read scope; no Next build or server starts.
NODE_ENV=test blocks AppShell's existing demo-session effect; source auth remains
untouched. Tests' synthetic fetch/streams and jsdom storage use no browser profile.

Node write/output scope is only:

```text
C:\Users\Duong Vinh\Vinh\infra\local\rag-fixture\chat-stream-20261005-01-frontend-run-01
```

Outputs: version/typecheck/tests logs, typecheck.json, tests.json, commands.json,
retained temp and Vite-cache descendants. Sanitized literal child environment
sets test/CI/telemetry settings and workspace profile/temp refs; inherited secrets
are not copied or printed. Each command has a 120-second limit, then exit124 and
retained evidence. Existing labels are never reused or cleaned.

Guard preserves credential/config read denial, DNS/socket denial, deletion,
rename/permission denial, output-only writes and child-process restrictions.
Only exact installed esbuild.exe service `--service=0.21.5` / `--ping` may spawn;
windowsHide=true. No Next/SWC CLI, package install or Playwright/browser spawn.
Native DLL/addon containment and hook efficacy are not yet runtime verified.

Acceptance requires zero typecheck diagnostics, all three suites passing, no
unhandled errors/skipped assertions, and retained negative/cancellation cases.
Success, abstention, safe failure/timeout, guard rejection, UTF-8/newline framing,
unknown/malformed/EOF, late failure, cancellation/loading, correlation and citation
isolation must remain covered. Maximum two materially different implementation
repairs; each needs fresh baseline/run evidence and preserved prior failures.

This scope cannot close streaming browser acceptance, durable DB/transcript GET,
live deadlines/cancellation, real RAG, M1/M2/M3, action execution or handover
receipts. Browser/build need separate reviewed packets because current root layout
uses next/font/google and Store/Draft providers; plain startup may load dotenv,
fetch fonts or call session/API services. No live access, production, installation,
pins/allowlist/security changes, commit/push/deploy/reset/delete/cleanup or agents.
