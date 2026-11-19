---
document_id: "DOC-DELIVERY-CHAT-STREAM-20261005-03"
version: "1.0.0"
status: "not_verified"
owner: "Campus 24/7 Engineering"
last_updated: "2026-10-05"
---

# Streaming continuation — immediate UI cancellation patch

**Implementation patched; frontend runtime remains not_verified.** Exactly two
product files changed in this run: `apps/web/src/app/chat/page.tsx` and its
`page.test.tsx`. `frontend/` is outside Campus 24/7. All prior UI edits and tests
were retained. No contract, dependency, auth or permission control was edited.

## Behavior and authority

Before: clicking Stop only aborted the controller. Provisional-text withdrawal
and loading completion depended on fetch/reader settling; normal completion also
awaited reader cancellation before clearing loading. An abort-insensitive
transport or pending cleanup promise could leave the UI busy.

After: an abort listener replaces the current provisional message with the safe
stopped guidance, clears citations/drawer/loading, and invalidates that attempt
immediately. Delayed callbacks are rejected by the existing attempt identity
checks. Reader cancellation is handled asynchronously without delaying UI state;
finally removes the abort listener and clears only the matching attempt before
cleanup. This does not assert server-side cancellation or durable persistence.

Two new regressions retain existing assertions: pending stream cleanup still
permits a subsequent successful turn; a late conversation response cannot bind
the conversation or clear loading for a new active attempt. They are source tests
**not executed yet**. The original cancellation test remains unchanged.

Direct human continuation authorizes ordinary scoped engineering under accepted
P-CONTRACT-STREAM-001, API_CONVENTIONS8.1, and execution plan v0.2.0. The user
confirmed Python dependency files are being edited elsewhere. Those files and
their updated verifier/review were inspected, not edited by this run. Initially
dependency verification failed; the exact output remains in the chat. On this
turn's retry, all three preflight checks passed before product mutation.

## Preservation and evidence

Fresh exclusive baseline `chat-stream-20261005-03-baseline.json`, SHA256
`1f340b4e7608369fc20c6aadcd2a14dbcc114b85ff884440f7f9b3d9bd6aba0b`,
captures current bytes for **1,591 readable historical files**, original current
texts of the two write targets and Git status/diffs. Six dependency-related
files differed from the prior scope; their current bytes were captured without
restoring older data. Four historical DB/audit fixture files were inaccessible;
their integrity remains not_verified and their paths are outside write scope.
The first reconstruction failure is disclosed in the fresh baseline. No DB,
permission/ACL change or broad inventory expansion was performed to read them.
Other inherited sensitive/model/other-frontend coverage exclusions remain.

Own incremental patch, separated from pre-existing Git changes:
`chat-stream-20261005-03-incremental-diff.json`, SHA256
`13dbef63d33c73c13f73d59187f1b15c0ca82874df74a13de716a203ef8122ca`.
The preparation baseline captures exact new tool/report paths before creation.
Current closure rehash matched **23,026/23,026 files**, and the existing Node hash,
version metadata and signature were rechecked without executing Node.

Fixture Python 3.12.14 `-B` with existing guards ran dependency verification,
catalog and OpenAPI validation in order: preflight exit **0/0/0**. Final checks
are recorded in `chat-stream-20261005-03-final-verification.json`. Final scope
records exact changed files, before/after hashes, all other covered bytes,
`git diff --check`, diff names/status and new artifact hashes separately.

## Remaining gate

P-FE-VERIFY-004 was approved with an OS sandbox requirement. This host now has
`danger-full-access`; general continuation and technical access do not grant
the exact protection exception. Source inputs also changed through this patch.
No Node, typecheck, Vitest, browser/build, DB/container or live provider ran.
No install/pin, guard/permission change, commit/push/deploy or cleanup occurred.

Concrete proposed P-FE-VERIFY-005 binds the updated source, unchanged current
closure, unchanged guard/runner, fresh approval receipt and exact launcher. It
requests explicit acceptance of running these bounded Node commands without the
OS sandbox; native code can bypass JavaScript hooks. No approved receipt exists.
An appropriately reviewed sandbox remains the alternative. Independent security
and release gates are not waived. Whole streaming objective, browser acceptance,
real RAG and M1/M2/M3 remain **not_verified**.
