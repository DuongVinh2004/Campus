# Python dependency update — 2026-11-27

Owner approval: given in chat on 2026-11-27 for the Python minor/patch group of pull request #41 and the OpenTelemetry
security update, including its `0.66b2` prerelease family. Reference in `scripts/verify_dependencies.py` and
`pyproject.toml`: `DIRECT-HUMAN-2026-11-27-PYTHON-UPDATES-001`, bound to the exact bytes of `uv.lock`
(`candidate-lock-sha256`). No package was added or removed (134 packages outside the allowlist).

## Changes

- Added after a second approval the same day (pull request #59, published while this update was being checked): langfuse
  4.18.0, langsmith 0.16.2, openai 3.58.0, pdfplumber 0.11.11, pypdfium2 5.15.2, pyyaml 6.0.4. These replace the
  versions of the same packages listed below.

- Pull request #41: alembic 1.20.1, asyncpg 0.32.0, fastapi 0.165.0, langchain-core 1.8.4, langgraph 1.2.24,
  numpy 2.5.5, openai 3.57.0, pgvector 0.5.1, pydantic 2.14.4, pydantic-settings 2.16.3, sqlalchemy 2.1.9,
  python-multipart 0.0.34, uvicorn 0.54.0; dev tools pytest 9.2.0, pytest-asyncio 1.5.0, pytest-mock 3.17.0,
  pytest-benchmark 5.3.1, locust 2.47.0, ruff 0.17.6, mypy 2.4.1; transitive certifi, langchain-protocol,
  langgraph-checkpoint, langgraph-prebuilt, langsmith, pydantic-core.
- OpenTelemetry (medium advisory in opentelemetry-api up to 1.45.1): api/sdk/exporters/proto 1.45.2, instrumentation
  family 0.66b2. The prerelease exception now names exactly `0.66b2`; `0.66b0` is denied again.

## Not covered

- The local runtime on 8015 uses its own virtual environments and was not changed by this update.
