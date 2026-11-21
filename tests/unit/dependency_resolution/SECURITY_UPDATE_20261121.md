# Dependency security update — 2026-11-21

Owner approval: given in chat on 2026-11-21 ("Duyệt nâng cấp") for security updates of the dependencies listed here, after the
list of Dependabot alerts was shown. Reference in `scripts/verify_dependencies.py` and `pyproject.toml`:
`DIRECT-HUMAN-2026-11-21-SECURITY-UPDATES-001`. The approval is bound to the exact bytes of `uv.lock`
(`candidate-lock-sha256`); the package set is unchanged (134 packages outside the allowlist, none added or removed).

## Python (`pyproject.toml`, `uv.lock`)

| Package | From | To | Kind | Why |
| --- | --- | --- | --- | --- |
| pypdf | 6.19.0 | 6.21.4 | direct | Several high advisories (infinite loops and memory use on crafted PDFs); the learning module parses uploaded PDFs with it. 6.21.4 is the lowest version that fixes all open ones. |
| langgraph | 1.2.12 | 1.2.14 | direct | Medium: unencoded identifiers in SDK v3 streaming. |
| langgraph-sdk | 0.4.5 | 0.4.6 | transitive | Same advisory. |
| pillow | 12.3.0 | 13.0.0 | transitive | One critical (FPX decoder) and many high/medium advisories; fixed in 13.0.0. |
| certifi | 2026.7.22 | 2026.10.18 | transitive | Critical: bundled root CAs with compromised intermediate keys. |
| brotli | 1.2.0 | 1.2.1 | transitive | Critical: out-of-bounds write in the decoder. |

Each version is the lowest one that fixes the advisory, not the latest release.

## Web (`apps/web/package.json`, `pnpm-lock.yaml`)

| Package | From | To | Kind | Why |
| --- | --- | --- | --- | --- |
| next | 16.3.8 | 16.4.5 | runtime | Critical and high advisories (fixed in 16.4.1) and medium ones (fixed in 16.4.5). |

## Deliberately not changed

- **Web dev tooling: vitest 2.1.9 (critical), happy-dom 20.14.5 (high), vite 5.4.21 (fixes only on 6.x), esbuild 0.21.5, source-map-js 1.2.1.** These were upgraded to vitest 3.2.6 / happy-dom 21.0.4 / vite 6.4.4 and the suite passed three times locally, but vitest 3 made async tests flaky: one test failed on CI and a second failed in a local full run (both passed on re-run, and the old runner passed 20 of 20 runs of the first one). They are development-only tools and do not ship, so they are left for a follow-up that stabilises those tests first. The upgrade is kept on the local branch `chore/web-devtools-security-wip`.

- **OpenTelemetry (opentelemetry-api 1.45.0, medium, fixed in 1.45.2).** `opentelemetry-sdk` 1.45.2 requires the instrumentation family at `0.66b2`, but the owner's prerelease approval names exactly `0.66b0`. Extending it needs a separate approval.
- **tinypool 1.1.1 (critical, dev only).** Fixed only in 2.x, which needs vitest 4 (a further major migration of the test runner).
- **infra/cdk** (`vitest` alert): the CDK project has no lockfile and is outside the pnpm workspace.

## Evidence

- `scripts/verify_dependencies.py`: passed (approved exact pins, closure, sources, artifact hashes).
- Python, on an environment built with `uv sync --frozen` from the new lock: `tests/unit/dependency_resolution`, `tests/delivery`, `tests/operations/test_campus_parser_runtime.py` (67 passed); `tests/learning_entry` and `tests/unit/learning` (the three real-child PDF tests need one local fixture PDF and pass with it); the CI regression subset (`evals/runners/run_full_regression.py --ci`).
- Web: `tsc --noEmit` clean, vitest 145 files / 922 tests passed in four full local runs with `next` 16.4.5, `next build` completed.
- Not measured: behaviour of the live runtime on 8015, which uses separate local virtual environments and was not touched.
