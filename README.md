# Campus 24/7

[![CI](https://github.com/DuongVinh2004/Campus/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/DuongVinh2004/Campus/actions/workflows/ci.yml)
[![Security & Supply Chain](https://github.com/DuongVinh2004/Campus/actions/workflows/security.yaml/badge.svg?branch=main)](https://github.com/DuongVinh2004/Campus/actions/workflows/security.yaml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Python 3.12-3.13](https://img.shields.io/badge/python-3.12--3.13-blue)
![Status: pre-release](https://img.shields.io/badge/status-pre--release-orange)

**A source-grounded academic assistant and campus-services platform** built around the public information of Hanoi University of Civil Engineering (HUCE): chat with citations, academic service requests, timetable and exams, room booking, learning materials, and a knowledge-management console that keeps the assistant's sources current.

> **Independent project. Not an official service of HUCE.** It is built from public HUCE information and clearly labelled synthetic data. It has **no connection** to HUCE's student information, grades, single sign-on, request intake or room-booking systems, and must not be presented as one of them. Student-facing screens say so wherever simulated data is shown.

*Tóm tắt tiếng Việt:* Campus 24/7 là trợ lý học vụ có trích dẫn nguồn và nền tảng dịch vụ sinh viên (hỏi đáp, hồ sơ, lịch học/thi, đặt phòng, học liệu, quản trị nguồn tri thức), xây dựng trên thông tin công khai của Trường Đại học Xây dựng Hà Nội. Đây là dự án độc lập, **không phải dịch vụ chính thức của trường**; dữ liệu cá nhân là dữ liệu mô phỏng, giao diện chính là tiếng Việt.

## What it does

| Area | Capabilities |
| --- | --- |
| **Assistant (RAG)** | Answers only from approved sources and shows the citations; refuses or asks to clarify when evidence is missing; guards against prompt injection and stale sources. |
| **Academic services** | Students prepare, preview and confirm requests (certificate, grade appeal, general support); a staff queue handles them with replies, notes and status changes; every write action needs permission, preview, confirmation, idempotency and an audit record. |
| **Timetable and rooms** | Weekly timetable, exams, personal events, calendar export; room search, availability and booking with conflict checks. |
| **Learning materials** | Lecturers publish PDF/PPTX lectures per class session after a malware scan; students read, bookmark, annotate and ask questions on a page. |
| **Knowledge management** | Document intake with automatic checks, review and publication; a polite crawler for public HUCE pages; index rebuild and hot reload; freshness reminders and answer-gap reports. |
| **Operations** | Admin overview, metrics, alerts, backups and restore drills, rate limiting and admission control, installable web app (PWA). |

## Architecture at a glance

```
 Browser (Next.js 16, React 19, Tailwind 4)
        │  same-origin /v1/* and pages
        ▼
 API (FastAPI) ── presentation → application → domain      (ports isolate the outside world)
        │             │
        │             ├─ agent: LangGraph flow, grounding, guardrails, human confirmation
        │             └─ infrastructure: PostgreSQL + pgvector, SQLite stores, Redis (optional),
        │                                 model gateway, ClamAV, file storage
        ▼
 Knowledge index (RAG v2) ◄── ingestion worker ◄── documents, crawler
```

Principles that shape the code:

- **The model proposes; deterministic code decides.** Authentication, authorization and execution of any write are never delegated to a prompt.
- **Layered, with enforced boundaries.** `domain` and `application` never import web, database or framework code; `tests/architecture` checks it.
- **Contracts first.** The HTTP API is described in `contracts/openapi/v1/openapi.yaml`; contract tests keep code and description aligned.
- **Evidence over claims.** Answer quality, refusals and safety are measured by evaluation sets and gates in `evals/`.

## Repository layout

| Path | Contents |
| --- | --- |
| `apps/web` | Next.js web application (Vietnamese UI, partial English) |
| `services/api` | FastAPI backend (`campus247` package), Alembic migrations |
| `services/worker`, `workers/` | Background workers (document ingestion, jobs) |
| `packages/` | Shared packages: `evals`, `prompts`, `synthetic` |
| `contracts/` | OpenAPI, JSON Schema, AsyncAPI |
| `evals/` | Evaluation datasets, runners, red-team cases, regression gates |
| `infra/` | Local runtime profiles, cloud deployment kit, CDK, specifications |
| `scripts/` | Runtime launcher, data acquisition, maintenance and QA tools |
| `tests/` | Backend and integration tests |
| `docs/` | Governance, product, architecture, AI, security and quality documents |
| `release/` | Release manifest and evidence |

## Getting started

Requirements: Python 3.12 or 3.13 with [uv](https://docs.astral.sh/uv/), Node.js with pnpm 9.12.0.

```bash
git clone https://github.com/DuongVinh2004/Campus.git
cd Campus

uv sync --frozen                                   # Python dependencies (exact versions in uv.lock)
pnpm install --frozen-lockfile --filter 'web...' --ignore-scripts

pnpm --filter web exec tsc --noEmit                # type check the web app
pnpm --filter web test                             # web unit and accessibility tests
uv run --frozen python -B evals/runners/run_full_regression.py --ci --out .ci-evidence/regression
```

The last command is the portable regression subset that CI runs. The **full local runtime** (PostgreSQL with pgvector, embedding and reranking model servers, ClamAV scanner, the model gateway, the RAG index) needs data and model files that are not in this repository; it is described in [`verification.md`](.claude/skills/campus247/references/verification.md) and in [`docs/`](docs/README.md). Calls to the paid language-model provider are never made by tests: they use deterministic fakes unless you configure a provider yourself.

## Quality gates

`main` is protected: every change arrives through a pull request and must pass six checks — task catalog validation, backend regression subset, web tests and type check, AI safety gate, release manifest gate, and a supply-chain and secret audit. Secret scanning with push protection, Dependabot, least-privilege CI tokens and SHA-pinned actions are enabled. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Documentation

- [Documentation index](docs/README.md) — governance, product, architecture, AI, security, quality.
- [Architecture and conventions](.claude/skills/campus247/references/architecture.md)
- [RAG and AI safety rules](.claude/skills/campus247/references/rag-and-ai-safety.md)
- [Local runtime history (archived notes)](docs/LOCAL_RUNTIME_HISTORY.md)

## Project status and limitations

Pre-release: there is no tagged version yet and only `main` is supported. It is developed by a single maintainer and has been run on one machine, with a cloud deployment kit prepared in `infra/cloud` but not operated in production. Answer quality and safety are measured on evaluation sets with machine-verified gold answers; behaviour with real users is **not measured**. Personal data in the demo (accounts, timetables, requests) is simulated.

## Contributing, security, license

- Contributions are welcome: read [CONTRIBUTING.md](CONTRIBUTING.md) and the [Code of Conduct](CODE_OF_CONDUCT.md).
- Report vulnerabilities privately as described in [SECURITY.md](SECURITY.md).
- Released under the [MIT License](LICENSE).
