# W11 — Record the owner's dependency approval (Campus 24/7)

Workspace: C:\Users\Duong Vinh\Vinh (branch rag-v2-hardening). Reply/report in Vietnamese.

## Approval (from the repository owner, in chat, 2026-11-03)
The owner reviewed `evals/results/audit-opus-20261101/dependency-review-20261103.md` and said: "oke duyệt".
The approval covers EXACTLY the current `uv.lock` bytes:
sha256 `251e0a8fbd1f5910abd30105a3a0e6b63f6ab9a51244d209cfc29848b2dbce46`
(133 unlisted resolved packages + 21 declared, including the 10 OpenTelemetry `0.66b0` prereleases already listed in `APPROVED_OTEL_PRERELEASES`).

## Goal
Make `tests/unit/dependency_resolution/test_verifier.py` pass by recording this approval, without weakening the gate.

## Do
1. In `scripts/verify_dependencies.py`:
   - `APPROVAL_REFERENCE = "DIRECT-HUMAN-2026-11-03-STACK-002"`
   - `APPROVED_CANDIDATE_SHA256 =` the sha256 above (recompute from the file and confirm it matches; if it does not match, STOP and report).
   - `APPROVED_ADDITIONAL_PACKAGE_COUNT =` the number the gate itself computes for this lock (packages not in the allowlist doc and not the root). Report the number.
   - Update the comment above to say the 2026-11-03 owner approval covers these exact candidate bytes; new names/versions still need new approval.
2. In `pyproject.toml` `[tool.campus247.dependency-approval]`: set `reference` and `candidate-lock-sha256` to the same values.
3. Run `.venv/Scripts/python.exe -B scripts/verify_dependencies.py` (or call `verify_dependencies`) and list remaining errors. Expected remaining: `lock drift: production requirement metadata differs`, `lock drift: root dependency references differ`, and one `dependency must use an exact stable == pin` error. Find the exact cause of each (compare `pyproject.toml` `[project].dependencies` / dev group with the root package `metadata.requires-dist` / `dependencies` in `uv.lock`).
   - If the fix is to make `pyproject.toml` declare exactly what `uv.lock` already records (same names, `==` versions, extras, markers), do that in `pyproject.toml` only.
   - Do NOT modify `uv.lock` and do NOT run `uv lock`/`uv sync`/pip install. The approval is for these exact lock bytes. If the only fix requires changing `uv.lock`, STOP and report what would change.
4. Run: `.venv/Scripts/python.exe -B -m pytest tests/unit/dependency_resolution -q -p no:cacheprovider --basetemp=.pytest-tmp-w11` then delete `.pytest-tmp-w11`. All must pass, including the negative tests (count mismatch, bytes drift, self-approval of a different candidate).

## Do not
- Do not change any other gate rule, regex, allowlist doc, test expectation or `APPROVED_OTEL_PRERELEASES`.
- Do not commit, push, reset, clean or delete anything. Do not print secrets.

## Report (write to `evals/results/audit-opus-20261101/impl/W11-report.md`)
Files changed with a short diff summary, the computed sha256 and package count, the exact cause and fix for each remaining gate error, and the pytest result.
