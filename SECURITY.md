# Security Policy

## Supported versions

Campus 24/7 has no tagged release yet. Only the `main` branch receives security fixes.

| Version | Supported |
| ------- | --------- |
| `main`  | Yes       |
| Anything else (old branches, forks, local snapshots) | No |

## Reporting a vulnerability

**Please do not open a public issue, pull request or discussion for a vulnerability.**

Report it privately through GitHub:
**[Report a vulnerability](https://github.com/DuongVinh2004/Campus/security/advisories/new)** (Security tab, "Report a vulnerability").

Include what you found, how to reproduce it (a minimal request, prompt or input is ideal), the commit or branch you tested, and the impact you expect. Do not include real student, staff or university data in a report.

What to expect from a single maintainer, on a best-effort basis:

- an acknowledgement within 7 days;
- a first assessment (accepted, needs more information, or not a vulnerability) within 14 days;
- a fix or mitigation on `main` as soon as it can be verified, with credit in the advisory if you want it.

There is no bug bounty.

## Scope

In scope: this repository's code, configuration and CI.

Of particular interest, because the system lets a model *propose* and code *decide*:

- bypass of authentication, role checks or tenant/scope filtering;
- a write action (request, booking, publication) executed without permission check, preview, user confirmation, idempotency or audit;
- prompt injection or poisoned knowledge that changes an answer's citations, makes the assistant act, or leaks another user's data or hidden instructions;
- exposure of secrets, tokens, personal data or internal prompts in code, logs, responses or evidence;
- SSRF, unsafe file handling or a scanner bypass in document or learning-material uploads;
- supply-chain problems in dependencies, lockfiles or workflows.

Out of scope: findings that need physical access to a maintainer's machine, denial of service by sheer volume against a local development runtime, social engineering, and the simulated accounts and data created for local demos (they exist only on a developer's machine and are labelled as simulated).

## Ground rules for researchers

- Test only against your own local copy. Do not probe any service run by someone else.
- Do not access, modify or exfiltrate data that is not yours, and stop as soon as you have shown the issue.
- Give a reasonable time to fix before publishing details.

This project is an independent work and is **not an official service of Hanoi University of Civil Engineering (HUCE)**. Do not report issues about HUCE's own systems here.

## What the repository already does

Secret scanning with push protection, Dependabot alerts and updates, least-privilege CI tokens, workflow actions pinned to commit SHAs, and a protected `main` branch (pull request plus passing CI required).
