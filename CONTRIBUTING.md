# Contributing to Campus 24/7

Thank you for taking the time to contribute. This guide says how to propose a change so that it can be reviewed and merged quickly. By taking part you agree to the [Code of Conduct](CODE_OF_CONDUCT.md). For vulnerabilities, follow [SECURITY.md](SECURITY.md) instead of opening an issue.

## Ground rules

- **No real data.** This project works with public university information and clearly labelled synthetic data. Never commit real student or staff data, credentials, tokens, `.env` files or local runtime state. Secret scanning with push protection is on; a push that contains a secret will be rejected.
- **The model proposes, code decides.** Authentication, authorization, confirmation and execution of any write action live in deterministic application code, never in a prompt or in the UI. See [architecture notes](.claude/skills/campus247/references/architecture.md).
- **Do not weaken protections to make a test pass** (authentication, authorization, confirmation, source verification, thresholds, expected results). Change the code, not the check.
- **Be honest about evidence.** State what you ran and what it showed. Say what you did not run.

## Before you start

1. Search [issues](https://github.com/DuongVinh2004/Campus/issues) and open pull requests for the same topic.
2. For anything larger than a small fix, open an issue first and describe the problem and your plan.

## Development setup

Requirements: Python 3.12 or 3.13, [uv](https://docs.astral.sh/uv/), Node.js with pnpm 9.12.0 (`npm install -g pnpm@9.12.0`).

```bash
# Python (API, evals): exact versions come from uv.lock
uv sync --frozen
uv run --frozen python -B -m pytest -q tests/delivery/test_release_manifest.py

# Web (apps/web)
pnpm install --frozen-lockfile --filter 'web...' --ignore-scripts
pnpm --filter web exec tsc --noEmit
pnpm --filter web test
```

The full local runtime (PostgreSQL with pgvector, model servers, ClamAV, the gateway) is documented in [`.claude/skills/campus247/references/verification.md`](.claude/skills/campus247/references/verification.md) and `docs/`. You do not need it for most changes; tests use fakes by default, and the CI checks below need none of it.

## Branches and commits

- Branch from `main`: `feat/<topic>`, `fix/<topic>`, `chore/<topic>`, `docs/<topic>`.
- Use [Conventional Commits](https://www.conventionalcommits.org/): `feat(learning): ...`, `fix(api): ...`, `docs: ...`, `chore(deps): ...`. One idea per commit.
- Keep a change small and focused. Every changed line should trace back to the purpose of the pull request.

## Checks that must pass

`main` is protected. A change reaches it only through a pull request, and these six CI checks must pass:

| Check | What it covers |
| --- | --- |
| Validate Task Catalog & DAG | structure of the task catalog |
| Backend Unit & Integration Gates | portable regression subset (`evals/runners/run_full_regression.py --ci`) |
| Web Unit & A11y Gates | `tsc --noEmit`, vitest, accessibility tests |
| AI Safety & Release Gates | audit remediation gate |
| Release Manifest Verification Gate | release manifest |
| Supply Chain and Secret Audit | lockfile integrity, secret and egress tests |

Run what is relevant to your change locally. Pick the nearest row, and run only what applies:

| You changed | Run |
| --- | --- |
| Web text, styles, components | `pnpm --filter web exec tsc --noEmit`, `pnpm --filter web test` |
| API route or logic | `uv run --frozen python -B -m pytest -q tests/<related directory>` |
| Imports between layers | `uv run --frozen python -B -m pytest -q tests/architecture` (one older violation is known; add no new ones) |
| API contract | update `contracts/` and run `tests/contract`, `tests/contracts` |
| Database migration | add a migration under `services/api/migrations`; additive only; test on a throwaway database |
| RAG, prompts, grounding, guardrails | `tests/evals`, `tests/knowledge_platform`, and the relevant gate in `evals/gates` |
| Security, permissions, confirmations | `tests/security` and red-team cases |

Add or update tests next to the behaviour you change. Prefer fakes over deep mocks.

## Pull requests

1. Push your branch and open a pull request against `main`. Fill in the template.
2. Describe the purpose, what changed, and how you verified it.
3. If your change depends on another open pull request, target that branch instead and say so; retarget to `main` after the first one merges.
4. Keep the discussion on the pull request. Resolve review comments by pushing commits or replying.
5. The maintainer merges once checks pass and review is done.

## Code style

- Python: type hints on public APIs, `async` for I/O, Pydantic v2 models, small functions with clear names. `ruff` and `mypy` are in the dev dependencies.
- Web: Next.js App Router, features under `apps/web/src/features/<name>`, design tokens instead of hard-coded colours, Vietnamese UI text, loading/empty/error states, accessible markup (roles, labels, focus, contrast).
- Layer boundaries (domain, application, ports, presentation, infrastructure) are enforced by `tests/architecture`; do not add new violations.
- Comments explain *why*, not *what*.

## Documentation

Architecture decisions and runbooks live in [`docs/`](docs/README.md). Update them in the same pull request when behaviour changes.

## Questions

Open an issue labelled `question`.
