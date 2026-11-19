# Dependency resolution candidate review

Status: exact candidate approved by the human on 2026-10-02; isolated Python 3.12.14 runtime provisioned and verified.

Candidate lock SHA-256: `f7727721cc9d433f506b53f2d644230cca9534f9dcd845565c474554888ca55e`.

Resolver: uv 0.12.22; direct versions frozen to installed baseline; Python >=3.12,<3.14.

68 registry packages; the human approved exactly the 53 additions listed below.

PyPI metadata hashes match every artifact in the candidate; PyPI reports no advisories for these versions. This is not independent SCA or release approval. No GPL/AGPL license is reported. Certifi and orjson include MPL-2.0 obligations requiring review.

Existing docs label pgvector as PostgreSQL license and httpx as MIT; version metadata says MIT and BSD respectively. Governance remains unchanged.

Approval reference: `DIRECT-HUMAN-2026-10-02-DEP-001`. Human answer: “Phê duyệt đúng candidate và 53 package/version”. Approval includes recording this decision in the dependency scope and provisioning the isolated fixture runtime. Root `uv.lock` now matches the approved candidate bytes. The verifier permits the additions only with the anchored reference and exact lock SHA-256; all source/hash/closure/drift checks remain active.

## Exact packages requiring approval

| Package | Candidate version | Installed baseline | License metadata |
|---|---|---|---|
| annotated-doc | 0.0.5 | absent | MIT |
| annotated-types | 0.8.0 | absent | MIT |
| anyio | 4.15.1 | absent | MIT |
| attrs | 26.1.0 | 26.1.0 | MIT |
| certifi | 2026.7.22 | absent | License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0) |
| charset-normalizer | 3.5.2 | absent | MIT |
| click | 8.5.0 | absent | BSD-3-Clause |
| colorama | 0.4.6 | absent | License :: OSI Approved :: BSD License |
| distro | 1.9.0 | absent | License :: OSI Approved :: Apache Software License |
| greenlet | 3.5.6 | absent | MIT AND PSF-2.0 |
| h11 | 0.16.0 | absent | License :: OSI Approved :: MIT License |
| httpcore | 1.0.9 | absent | BSD-3-Clause |
| httpcore2 | 2.13.1 | 2.13.0 | BSD-3-Clause |
| httptools | 0.8.0 | 0.8.0 | MIT |
| httpx2 | 2.13.1 | 2.13.0 | BSD-3-Clause |
| httpx2-jsfetch | 1.0 | absent | BSD-3-Clause |
| idna | 3.20 | absent | BSD-3-Clause |
| iniconfig | 2.3.0 | absent | MIT |
| jsonpatch | 1.33 | 1.33 | License :: OSI Approved :: BSD License |
| jsonpointer | 3.1.1 | 3.1.1 | License :: OSI Approved :: BSD License |
| jsonschema-specifications | 2025.9.1 | 2025.9.1 | MIT |
| langchain-core | 1.6.3 | 1.6.3 | License :: OSI Approved :: MIT License |
| langchain-protocol | 0.0.19 | 0.0.19 | License :: OSI Approved :: MIT License |
| langgraph-checkpoint | 4.2.0 | 4.2.0 | MIT |
| langgraph-prebuilt | 1.1.0 | 1.1.0 | MIT |
| langgraph-sdk | 0.4.5 | 0.4.5 | MIT |
| langsmith | 0.14.3 | 0.13.0 | MIT |
| mako | 1.4.3 | 1.4.1 | MIT |
| markupsafe | 3.0.3 | 3.0.3 | BSD-3-Clause |
| orjson | 3.12.0 | 3.12.0 | MPL-2.0 AND (Apache-2.0 OR MIT) |
| ormsgpack | 1.12.2 | 1.12.2 | Apache-2.0 OR MIT |
| packaging | 26.3 | absent | Apache-2.0 OR BSD-2-Clause |
| pluggy | 1.6.0 | absent | License :: OSI Approved :: MIT License |
| pydantic-core | 2.46.4 | absent | MIT |
| pygments | 2.21.0 | absent | BSD-2-Clause |
| python-dotenv | 1.2.4 | absent | BSD-3-Clause |
| referencing | 0.37.0 | 0.37.0 | MIT |
| requests | 2.34.2 | absent | License :: OSI Approved :: Apache Software License |
| requests-toolbelt | 1.0.0 | 1.0.0 | License :: OSI Approved :: Apache Software License |
| rpds-py | 2026.6.3 | 2026.6.3 | MIT |
| sniffio | 1.3.1 | absent | License :: OSI Approved :: Apache Software License; License :: OSI Approved :: MIT License |
| starlette | 1.7.0 | absent | BSD-3-Clause |
| tenacity | 9.1.4 | absent | License :: OSI Approved :: Apache Software License |
| truststore | 0.10.4 | 0.10.4 | MIT |
| typing-extensions | 4.16.0 | absent | PSF-2.0 |
| typing-inspection | 0.4.4 | absent | MIT |
| urllib3 | 2.8.0 | absent | MIT |
| uuid-utils | 0.17.1 | 0.17.1 | BSD-3-Clause |
| uvloop | 0.23.0 | absent | License :: OSI Approved :: Apache Software License; License :: OSI Approved :: MIT License |
| watchfiles | 1.3.0 | 1.2.0 | License :: OSI Approved :: MIT License |
| websockets | 16.1.1 | absent | BSD-3-Clause |
| xxhash | 4.0.1 | 4.0.1 | BSD-2-Clause |
| zstandard | 0.25.0 | 0.25.0 | BSD-3-Clause |

Version-specific source URLs and full review data: [dependency-review.json](dependency-review.json).

Windows runtime contains 66 packages matching the lock exactly; `uvloop` and
`httpx2-jsfetch` are excluded by platform markers. Installation used a fresh
unseeded environment, frozen hashed requirements, `--require-hashes --no-deps
--no-build --strict`; no existing environment was synced/pruned. Python 3.12
verifier exits 0; Python 3.14 remains rejected with exit 1. Targeted tests:
28 dependency checks plus 9 fixture checks, 37 passed, no skips. Live fixture
and installed-version evidence: [verification-evidence.json](../../../infra/local/rag-fixture/verification-evidence.json).

Approval must name this exact candidate/hash and its listed packages. Resolution does not expand the allowlist by itself. No security-control waiver, provider test, production deployment, or real data access is included.

## 2026-10-05 approved AI engineering stack expansion

Approval reference: `DIRECT-HUMAN-2026-10-05-STACK-001`. The human approved the exact 148-package candidate lock SHA-256 `1855035D6132A8CA49615836D1DA5F197B50745312169B6C7F5911AB587F8349`; it contains 132 unlisted package/version records in addition to the 15 normative allowlist names and the project root.

New direct dependencies are OpenAI-compatible client, tokenization/PDF ingestion, cryptography/JWT, structured logging and metrics, OpenTelemetry instrumentation, Langfuse, numerical evaluation, and developer test/benchmark/quality tools. This approval does not authorize a provider call, production deployment, credentials, raw prompt logging, PII egress, or any safety-control waiver.

The human subsequently answered "ok" to the explicit request to amend
`scripts/verify_dependencies.py` for exactly the ten OTel `0.66b0` pairs listed
in `.dependency-candidate-20261005/OTEL_GATE_EXCEPTION_PROPOSAL.md`. The exception
requires validated reference, full candidate SHA and package count; other beta
versions remain rejected. Stable pins, registry/artifact checks and closure
checks remain in force. Gate and all 34 tests pass, including the negative
prerelease/approval/hash cases.

145 packages were installed into the new root `.venv` using Python 3.13.16,
`uv sync --frozen --all-groups --inexact --no-build --link-mode copy`. Windows
markers exclude `uvloop` and `httpx2-jsfetch`; the 148th record is the virtual
project root. Installed versions all match the approved lock; `uv pip check`
passes. Offline smoke verifies 35 of 36 imports and numerical evaluation.
Windows Application Control blocks charset-normalizer's `md` DLL (preventing
pdfplumber import) and mypy's `fscache` DLL (preventing its CLI). These are retained
as runtime limitations, not marked passed or bypassed.

Evidence: [installation-evidence.json](../../../.dependency-candidate-20261005/installation-evidence.json).
The earlier Python 3.12 fixture record above remains historical and unchanged.
