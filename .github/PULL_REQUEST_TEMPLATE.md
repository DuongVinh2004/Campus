## Purpose
<!-- Why is this change needed? Link the issue: "Fixes #123". -->

## What changed
<!-- A short list. Every changed line should trace back to the purpose above. -->

## How it was verified
<!-- Commands you ran and what they showed. Say what you did NOT run. -->

## Risk and scope
- [ ] Touches authentication, authorization, confirmation of write actions, or tenant/scope filtering
- [ ] Touches RAG, prompts, grounding or refusal behaviour
- [ ] Changes the HTTP API (contract in `contracts/` updated, contract tests run)
- [ ] Adds a database migration (additive only, tested on a throwaway database)
- [ ] Changes dependencies or CI
- [ ] Changes the web UI (screenshots or a short description attached)

## Checklist
- [ ] The title follows [Conventional Commits](https://www.conventionalcommits.org/) (`feat(scope): ...`, `fix: ...`)
- [ ] Tests were added or updated next to the changed behaviour, and the relevant ones pass
- [ ] No secrets, tokens, `.env` files, real student/staff data or local runtime state are included
- [ ] No protection was weakened to make a test pass (authentication, authorization, confirmation, thresholds, expected results)
- [ ] Documentation and `CHANGELOG.md` (under *Unreleased*) are updated when behaviour changes
- [ ] If this depends on another open pull request, the base branch is that one and the description says so
