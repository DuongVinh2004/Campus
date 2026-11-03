# Rà soát cổng phụ thuộc (chuẩn bị cho người duyệt) — 2026-11-03
Tạo bởi `scripts/verify_dependencies.py` + `uv.lock`; KHÔNG phải phê duyệt. Phê duyệt hiện có: `DIRECT-HUMAN-2026-10-05-STACK-001`, số gói bổ sung đã duyệt: 132, checksum ứng viên đã duyệt khớp: **không**.
- `uv.lock` sha256 hiện tại: `251e0a8fbd1f5910abd30105a3a0e6b63f6ab9a51244d209cfc29848b2dbce46`

## Tóm tắt lỗi cổng
- human approval reference or candidate checksum mismatch: 1
- dependency must use an exact stable == pin; URL/VCS/range/wildcard denied: 1
- immutable stable version required: 10
- lock drift: 2
- unapproved declared dependency: 21
- unapproved resolved dependency: 133

## Cần chú ý trước khi duyệt
- **Tên giống gói phổ biến (kiểm trên PyPI xem có phải bản chính chủ):** `ast-serialize` 0.12.1 (do mypy kéo vào), `httpcore2` 2.13.1 (do httpx2 kéo vào), `httpx2` 2.13.1 (do langsmith, openai kéo vào), `httpx2-jsfetch` 1.0 (do httpx2 kéo vào), `librt` 0.16.0 (do mypy kéo vào), `py-cpuinfo2` 10.1.1 (do pytest-benchmark kéo vào).
- **Phiên bản tiền phát hành OpenTelemetry (cổng yêu cầu bản ổn định):** `opentelemetry-exporter-http-transport`, `opentelemetry-exporter-otlp-common`, `opentelemetry-instrumentation`, `opentelemetry-instrumentation-asgi`, `opentelemetry-instrumentation-fastapi`, `opentelemetry-instrumentation-httpx`, `opentelemetry-instrumentation-redis`, `opentelemetry-instrumentation-sqlalchemy`, `opentelemetry-semantic-conventions`, `opentelemetry-util-http`.
- **Lock drift:** production requirement metadata differs; root dependency references differ.
- **Một khai báo không dùng pin `==` ổn định** (URL/VCS/khoảng/wildcard bị cấm) — xem `pyproject.toml`.

## Gói khai báo trực tiếp chưa duyệt (21)
`cryptography`, `langchain-core`, `langfuse`, `locust`, `mypy`, `numpy`, `openai`, `opentelemetry-api`, `opentelemetry-exporter-otlp`, `opentelemetry-sdk`, `pdfplumber`, `prometheus-client`, `pyjwt`, `pypdf`, `pytest-benchmark`, `pytest-mock`, `python-multipart`, `ruff`, `scikit-learn`, `structlog`, `tiktoken`

## Gói resolve chưa duyệt (133) — phiên bản, nguồn, gói kéo vào

| gói | phiên bản | nguồn | kéo vào bởi |
|---|---|---|---|
| `annotated-doc` | 0.0.5 | https://pypi.org/simple | fastapi |
| `annotated-types` | 0.8.0 | https://pypi.org/simple | pydantic |
| `anyio` | 4.15.1 | https://pypi.org/simple | httpx, httpx2, langsmith, openai, starlette, watchfiles |
| `asgiref` | 3.12.1 | https://pypi.org/simple | opentelemetry-instrumentation-asgi |
| `ast-serialize` | 0.12.1 | https://pypi.org/simple | mypy |
| `attrs` | 26.1.0 | https://pypi.org/simple | jsonschema, referencing |
| `backoff` | 2.2.1 | https://pypi.org/simple | langfuse |
| `bidict` | 0.24.1 | https://pypi.org/simple | python-socketio |
| `blinker` | 1.9.0 | https://pypi.org/simple | flask |
| `brotli` | 1.2.0 | https://pypi.org/simple | geventhttpclient |
| `certifi` | 2026.7.22 | https://pypi.org/simple | geventhttpclient, httpcore, httpx, requests |
| `cffi` | 2.1.1 | https://pypi.org/simple | cryptography, gevent, pyzmq |
| `charset-normalizer` | 3.5.2 | https://pypi.org/simple | pdfminer-six, requests |
| `click` | 8.5.0 | https://pypi.org/simple | flask, uvicorn |
| `cloudpickle` | 3.1.2 | https://pypi.org/simple | joblib |
| `colorama` | 0.4.6 | https://pypi.org/simple | pytest |
| `configargparse` | 1.8.0 | https://pypi.org/simple | locust |
| `cryptography` | 50.0.2 | https://pypi.org/simple | campus247, pdfminer-six |
| `distro` | 1.9.0 | https://pypi.org/simple | langsmith |
| `flask` | 3.1.3 | https://pypi.org/simple | flask-cors, flask-login, locust |
| `flask-cors` | 6.0.5 | https://pypi.org/simple | locust |
| `flask-login` | 0.6.3 | https://pypi.org/simple | locust |
| `gevent` | 26.9.0 | https://pypi.org/simple | geventhttpclient, locust |
| `geventhttpclient` | 2.5.1 | https://pypi.org/simple | locust |
| `googleapis-common-protos` | 1.75.5 | https://pypi.org/simple | opentelemetry-exporter-otlp-proto-grpc, opentelemetry-exporter-otlp-proto-http |
| `greenlet` | 3.5.6 | https://pypi.org/simple | gevent, sqlalchemy |
| `grpcio` | 1.84.0 | https://pypi.org/simple | opentelemetry-exporter-otlp-proto-grpc |
| `h11` | 0.16.0 | https://pypi.org/simple | httpcore, httpcore2, uvicorn, wsproto |
| `httpcore` | 1.0.9 | https://pypi.org/simple | httpx |
| `httpcore2` | 2.13.1 | https://pypi.org/simple | httpx2 |
| `httptools` | 0.8.0 | https://pypi.org/simple |  |
| `httpx2` | 2.13.1 | https://pypi.org/simple | langsmith, openai |
| `httpx2-jsfetch` | 1.0 | https://pypi.org/simple | httpx2 |
| `idna` | 3.20 | https://pypi.org/simple | anyio, httpx, httpx2, requests |
| `iniconfig` | 2.3.0 | https://pypi.org/simple | pytest |
| `itsdangerous` | 2.2.0 | https://pypi.org/simple | flask |
| `jinja2` | 3.1.6 | https://pypi.org/simple | flask |
| `jiter` | 0.17.0 | https://pypi.org/simple | openai |
| `joblib` | 1.6.0 | https://pypi.org/simple | scikit-learn |
| `jsonpatch` | 1.33 | https://pypi.org/simple | langchain-core |
| `jsonpointer` | 3.1.1 | https://pypi.org/simple | jsonpatch |
| `jsonschema-specifications` | 2025.9.1 | https://pypi.org/simple | jsonschema |
| `langchain-core` | 1.6.3 | https://pypi.org/simple | campus247, langgraph, langgraph-checkpoint, langgraph-prebuilt, langgraph-sdk |
| `langchain-protocol` | 0.0.19 | https://pypi.org/simple | langchain-core, langgraph-sdk |
| `langfuse` | 4.17.0 | https://pypi.org/simple | campus247 |
| `langgraph-checkpoint` | 4.2.0 | https://pypi.org/simple | langgraph, langgraph-prebuilt |
| `langgraph-prebuilt` | 1.1.0 | https://pypi.org/simple | langgraph |
| `langgraph-sdk` | 0.4.5 | https://pypi.org/simple | langgraph |
| `langsmith` | 0.14.4 | https://pypi.org/simple | langchain-core |
| `librt` | 0.16.0 | https://pypi.org/simple | mypy |
| `locust` | 2.46.7 | https://pypi.org/simple |  |
| `mako` | 1.4.3 | https://pypi.org/simple | alembic |
| `markupsafe` | 3.0.4 | https://pypi.org/simple | flask, jinja2, mako, werkzeug |
| `msgpack` | 1.2.3 | https://pypi.org/simple | locust |
| `mypy` | 2.4.0 | https://pypi.org/simple |  |
| `mypy-extensions` | 1.1.0 | https://pypi.org/simple | mypy |
| `narwhals` | 2.26.0 | https://pypi.org/simple | scikit-learn |
| `numpy` | 2.5.3 | https://pypi.org/simple | campus247, scikit-learn, scipy |
| `openai` | 3.24.0 | https://pypi.org/simple | campus247 |
| `opentelemetry-api` | 1.45.0 | https://pypi.org/simple | campus247, langfuse, opentelemetry-exporter-http-transport, opentelemetry-export |
| `opentelemetry-exporter-http-transport` | 0.66b0 | https://pypi.org/simple | opentelemetry-exporter-otlp-proto-http |
| `opentelemetry-exporter-otlp` | 1.45.0 | https://pypi.org/simple | campus247 |
| `opentelemetry-exporter-otlp-common` | 0.66b0 | https://pypi.org/simple | opentelemetry-exporter-otlp-proto-grpc, opentelemetry-exporter-otlp-proto-http |
| `opentelemetry-exporter-otlp-proto-common` | 1.45.0 | https://pypi.org/simple | opentelemetry-exporter-otlp-proto-grpc, opentelemetry-exporter-otlp-proto-http |
| `opentelemetry-exporter-otlp-proto-grpc` | 1.45.0 | https://pypi.org/simple | opentelemetry-exporter-otlp |
| `opentelemetry-exporter-otlp-proto-http` | 1.45.0 | https://pypi.org/simple | langfuse, opentelemetry-exporter-otlp |
| `opentelemetry-instrumentation` | 0.66b0 | https://pypi.org/simple | opentelemetry-instrumentation-asgi, opentelemetry-instrumentation-fastapi, opent |
| `opentelemetry-instrumentation-asgi` | 0.66b0 | https://pypi.org/simple | opentelemetry-instrumentation-fastapi |
| `opentelemetry-instrumentation-fastapi` | 0.66b0 | https://pypi.org/simple | campus247 |
| `opentelemetry-instrumentation-httpx` | 0.66b0 | https://pypi.org/simple | campus247 |
| `opentelemetry-instrumentation-redis` | 0.66b0 | https://pypi.org/simple | campus247 |
| `opentelemetry-instrumentation-sqlalchemy` | 0.66b0 | https://pypi.org/simple | campus247 |
| `opentelemetry-proto` | 1.45.0 | https://pypi.org/simple | opentelemetry-exporter-otlp-proto-common, opentelemetry-exporter-otlp-proto-grpc |
| `opentelemetry-sdk` | 1.45.0 | https://pypi.org/simple | campus247, langfuse, opentelemetry-exporter-otlp-common, opentelemetry-exporter- |
| `opentelemetry-semantic-conventions` | 0.66b0 | https://pypi.org/simple | opentelemetry-instrumentation, opentelemetry-instrumentation-asgi, opentelemetry |
| `opentelemetry-util-http` | 0.66b0 | https://pypi.org/simple | opentelemetry-instrumentation-asgi, opentelemetry-instrumentation-fastapi, opent |
| `orjson` | 3.12.0 | https://pypi.org/simple | langgraph-sdk, langsmith |
| `ormsgpack` | 1.12.2 | https://pypi.org/simple | langgraph-checkpoint |
| `packaging` | 26.3 | https://pypi.org/simple | langchain-core, langfuse, langsmith, opentelemetry-instrumentation, opentelemetr |
| `pathspec` | 1.1.1 | https://pypi.org/simple | mypy |
| `pdfminer-six` | 20260107 | https://pypi.org/simple | pdfplumber |
| `pdfplumber` | 0.11.10 | https://pypi.org/simple | campus247 |
| `pillow` | 12.3.0 | https://pypi.org/simple | pdfplumber |
| `pluggy` | 1.6.0 | https://pypi.org/simple | pytest |
| `prometheus-client` | 0.26.0 | https://pypi.org/simple | campus247 |
| `protobuf` | 7.36.2 | https://pypi.org/simple | googleapis-common-protos, opentelemetry-proto |
| `psutil` | 7.2.2 | https://pypi.org/simple | locust |
| `py-cpuinfo2` | 10.1.1 | https://pypi.org/simple | pytest-benchmark |
| `pycparser` | 3.0 | https://pypi.org/simple | cffi |
| `pydantic-core` | 2.46.4 | https://pypi.org/simple | pydantic |
| `pygments` | 2.21.0 | https://pypi.org/simple | pytest |
| `pyjwt` | 2.15.1 | https://pypi.org/simple | campus247 |
| `pypdf` | 6.19.0 | https://pypi.org/simple | campus247 |
| `pypdfium2` | 5.14.0 | https://pypi.org/simple | pdfplumber |
| `pytest-benchmark` | 5.3.0 | https://pypi.org/simple |  |
| `pytest-mock` | 3.16.0 | https://pypi.org/simple |  |
| `python-dotenv` | 1.2.4 | https://pypi.org/simple | pydantic-settings |
| `python-engineio` | 4.14.0 | https://pypi.org/simple | locust, python-socketio |
| `python-multipart` | 0.0.32 | https://pypi.org/simple | campus247 |
| `python-socketio` | 5.17.0 | https://pypi.org/simple | locust |
| `pywin32` | 312 | https://pypi.org/simple | locust |
| `pyzmq` | 27.2.0 | https://pypi.org/simple | locust |
| `referencing` | 0.37.0 | https://pypi.org/simple | jsonschema, jsonschema-specifications |
| `regex` | 2026.9.29 | https://pypi.org/simple | tiktoken |
| `requests` | 2.34.2 | https://pypi.org/simple | langsmith, locust, requests-toolbelt, tiktoken |
| `requests-toolbelt` | 1.0.0 | https://pypi.org/simple | langsmith |
| `rpds-py` | 2026.9.1 | https://pypi.org/simple | jsonschema, referencing |
| `ruff` | 0.16.10 | https://pypi.org/simple |  |
| `scikit-learn` | 1.9.1 | https://pypi.org/simple | campus247 |
| `scipy` | 1.18.1 | https://pypi.org/simple | scikit-learn |
| `simple-websocket` | 1.1.0 | https://pypi.org/simple | python-engineio |
| `sniffio` | 1.3.1 | https://pypi.org/simple | langsmith, openai |
| `starlette` | 1.7.0 | https://pypi.org/simple | fastapi |
| `structlog` | 26.1.0 | https://pypi.org/simple | campus247 |
| `tenacity` | 9.1.4 | https://pypi.org/simple | langchain-core |
| `threadpoolctl` | 3.7.0 | https://pypi.org/simple | scikit-learn |
| `tiktoken` | 0.14.0 | https://pypi.org/simple | campus247 |
| `truststore` | 0.10.4 | https://pypi.org/simple | httpcore2, httpx2 |
| `typing-extensions` | 4.16.0 | https://pypi.org/simple | alembic, anyio, fastapi, grpcio, httpx2, langchain-core, langchain-protocol, lan |
| `typing-inspection` | 0.4.4 | https://pypi.org/simple | fastapi, pydantic, pydantic-settings |
| `urllib3` | 2.8.0 | https://pypi.org/simple | requests |
| `uuid-utils` | 0.17.1 | https://pypi.org/simple | langchain-core, langsmith |
| `uvloop` | 0.23.0 | https://pypi.org/simple |  |
| `watchfiles` | 1.3.0 | https://pypi.org/simple |  |
| `websocket-client` | 1.9.2 | https://pypi.org/simple |  |
| `websockets` | 16.1.1 | https://pypi.org/simple | langgraph-sdk, langsmith |
| `werkzeug` | 3.1.9 | https://pypi.org/simple | flask, flask-cors, flask-login, locust |
| `wrapt` | 2.5.0 | https://pypi.org/simple | langfuse, opentelemetry-instrumentation, opentelemetry-instrumentation-httpx, op |
| `wsproto` | 1.3.2 | https://pypi.org/simple | simple-websocket |
| `xxhash` | 4.0.1 | https://pypi.org/simple | langgraph, langsmith |
| `zope-event` | 6.2 | https://pypi.org/simple | gevent |
| `zope-interface` | 8.6 | https://pypi.org/simple | gevent |
| `zstandard` | 0.25.0 | https://pypi.org/simple | langsmith |

## Sau khi bạn duyệt
Cập nhật `APPROVED_CANDIDATE_SHA256`, `APPROVED_ADDITIONAL_PACKAGE_COUNT` và tham chiếu phê duyệt trong `scripts/verify_dependencies.py` (hoặc nhắn để tôi ghi theo đúng quyết định của bạn), rồi chạy `tests/unit/dependency_resolution/test_verifier.py`.
