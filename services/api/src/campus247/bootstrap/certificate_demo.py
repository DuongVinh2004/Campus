"""Local synthetic business API, reusing one existing RAG writer through HTTP.

No provider credentials, model runtime, PostgreSQL connection or paid ledger is
initialized here. The same router/service can be injected into the main app.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field
from starlette.responses import JSONResponse, Response, StreamingResponse

from identities import generate_identities
from campus247.application.document_request.assistant import propose_certificate
from campus247.application.document_request.certificates import CertificateError, CertificateService
from campus247.application.identity.session_service import SessionService
from campus247.bootstrap.settings import Settings
from campus247.domain.action.confirmation import ConfirmationTokenService
from campus247.infrastructure.identity.mock import SyntheticIdentityAdapter
from campus247.infrastructure.repositories.sqlite_certificates import SQLiteCertificateRepository, workspace_path, ROOT
from campus247.presentation.certificates import create_certificate_router
from campus247.presentation.errors import create_problem_details, http_exception_handler, validation_exception_handler
from campus247.presentation.identity import IdentityMiddleware, get_current_identity
from campus247.presentation.middleware.abuse_limits import AbuseLimiterMiddleware, InMemoryRateLimiterStore, RateLimitRule
from campus247.ports.identity import IdentityRole


class LoginBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    account: str


class AssistantBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=2000)


def public_guidance():
    path = ROOT / "data/huce-public-20261013/handbook-human-reviewed.json"
    corpus = json.loads(path.read_text(encoding="utf-8"))
    pdf = ROOT / "data/huce-public-20261013/handbook-2026-2027.pdf"
    manifest = next(row for row in corpus["sources"] if row["file"] == pdf.name)
    if hashlib.sha256(pdf.read_bytes()).hexdigest() != manifest["sha256"]:
        raise CertificateError(409, "PUBLIC_SOURCE_HASH_MISMATCH", "Bản chụp PDF không khớp manifest; dừng sử dụng nguồn")
    sources = []
    for key, page in (("catalog", 35), ("procedure", 39)):
        row = next(r for r in corpus["chunks"] if r["page"] == page and r["source_file"] == "handbook-2026-2027.pdf")
        sources.append({"id": key, "title": row["title"], "version": "2026–2027", "locator": f"Trang {page}",
                        "url": row["url"], "download_url": row["download_url"], "content_text": row["text"],
                        "content_sha256": hashlib.sha256(row["text"].encode()).hexdigest(),
                        "source_sha256": manifest["sha256"], "effective_status": "unknown"})
    return {"summary": "Sổ tay hướng dẫn đăng nhập Một cửa HUCE, chọn dịch vụ và mẫu xác nhận, gửi yêu cầu; chuyên viên tiếp nhận, hẹn trả trên website/email, trình ký và lấy dấu; nhận tại Phòng CTCT & QLSV theo lịch hẹn.",
            "sources": sources, "snapshot_only": True,
            "demo_configuration": "Mục đích, nơi nộp, 1–3 bản, DIGITAL/PICKUP và tệp văn bản minh họa là cấu hình demo. Chưa xác minh biểu mẫu chi tiết, phí, SLA và điều kiện cấp hiện hành. Demo không gửi đến trường."}


def create_certificate_demo_app(database: Path, *, settings: Settings | None = None,
                                rag_transport=None, frontend_port: int | None = None,
                                integrated_rag_app=None, service_operations=False):
    settings = settings or Settings(_env_file=None, ENVIRONMENT="development", DEMO_MODE=True,
                                    OPENAI_API_KEY=None, GEMINI_API_KEY=None, DEEPSEEK_API_KEY=None)
    if settings.ENVIRONMENT != "development" or not settings.DEMO_MODE:
        raise ValueError("certificate runtime requires explicit local synthetic demo")
    repository = SQLiteCertificateRepository(workspace_path(database))
    directory = generate_identities()["records"]
    profiles = {p["user_id"]: dict(p) for p in directory["student_profile"]}
    users = {u["id"]: u for u in directory["user_identity"]}
    for uid, profile in profiles.items():
        profile["display_name"] = users[uid]["display_name"]
    adapter = SyntheticIdentityAdapter(settings.IDENTITY_SECRET_KEY, environment="development", tenant_id="huce-local-public")
    session_service = SessionService(repository)
    if integrated_rag_app is not None:
        integrated_rag_app.state.current_session_service = session_service
    service = CertificateService(repository, ConfirmationTokenService(settings.CONFIRMATION_SIGNING_KEY), profiles.get,
                                 guidance_reader=public_guidance)
    guidance = public_guidance()
    from campus247.application.multi_agent.service_adapter import CertificateDraftAdapter
    draft_adapter = CertificateDraftAdapter(service, guidance)
    from campus247.infrastructure.streaming_asgi import StreamingASGITransport
    app_transport = StreamingASGITransport(integrated_rag_app) if integrated_rag_app is not None else rag_transport
    aliases = {"SV001": directory["student_profile"][0]["user_id"],
               "SV024": directory["student_profile"][1]["user_id"],
               "OF001": next(r["user_id"] for r in directory["role_binding"] if r["role"] == "SUPPORT_OFFICER" and r["scope_key"] == "HUCE_GENERAL")}
    if service_operations:
        aliases["OF002"] = next(r["user_id"] for r in directory["role_binding"] if r["role"] == "SUPPORT_OFFICER" and r["scope_key"] == "ACADEMIC_SERVICES")
    if service_operations or integrated_rag_app is not None and getattr(integrated_rag_app.state, "policy_graph", None) is not None:
        # Existing synthetic knowledge administrators; no new role grants.
        knowledge_admins = list(dict.fromkeys(r["user_id"] for r in directory["role_binding"] if r["role"] == "KNOWLEDGE_ADMIN"))
        aliases.update({f"KA{i+1:03d}": uid for i, uid in enumerate(knowledge_admins[:2])})
    app = FastAPI(title="Campus 24/7 — Certificate demo", version="0.1.0")
    app.state.certificate_service = service
    app.state.certificate_draft_adapter = draft_adapter
    app.state.certificate_repository = repository
    app.state.current_session_service = session_service
    app.add_middleware(AbuseLimiterMiddleware, store=InMemoryRateLimiterStore(), rules=[
        RateLimitRule(path_prefix="/v1/auth", max_requests=60, window_seconds=60, fail_closed=True),
        RateLimitRule(path_prefix="/v1/document-requests", max_requests=120, window_seconds=60, fail_closed=True),
        RateLimitRule(path_prefix="/v1/staff", max_requests=120, window_seconds=60, fail_closed=True),
        RateLimitRule(path_prefix="/v1/conversations", max_requests=30, window_seconds=60, fail_closed=True),
    ])
    app.add_middleware(IdentityMiddleware, adapter=adapter, session_service=session_service)
    local_origins = ["http://localhost:8002", "http://127.0.0.1:8002", "http://localhost:3002", "http://127.0.0.1:3002"]
    if integrated_rag_app is not None:
        local_origins.extend(["http://localhost:8003", "http://127.0.0.1:8003", "http://localhost:3003", "http://127.0.0.1:3003"])
        if getattr(integrated_rag_app.state, "policy_graph", None) is not None:
            local_origins.extend(["http://localhost:3004", "http://127.0.0.1:3004"])
    if service_operations:
        local_origins.extend(["http://localhost:8004", "http://127.0.0.1:8004", "http://localhost:3005", "http://127.0.0.1:3005"])
    app.add_middleware(CORSMiddleware, allow_origins=local_origins, allow_credentials=True, allow_methods=["GET", "POST"], allow_headers=["Content-Type", "Authorization"])
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)

    @app.exception_handler(CertificateError)
    async def business_error(request, exc):
        return create_problem_details(request=request, status=exc.status, code=exc.code,
                                      title="Không thể thực hiện", detail=exc.detail)

    @app.middleware("http")
    async def no_store(request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/v1/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    def me(actor):
        return {"user_id": actor.subject_id, "display_name": actor.display_name,
                "roles": [r.value for r in actor.roles], "is_synthetic": True,
                "student_code": actor.student_code, "profile": profiles.get(actor.subject_id)}

    @app.get("/health/live")
    def health():
        return {"status": "ok", "mode": "synthetic_service_operations" if service_operations else "multi_agent_integrated" if integrated_rag_app is not None else "synthetic_certificate",
                "owns_paid_ledger": bool(getattr(app.state, "owns_paid_ledger", False))}

    @app.get("/v1/auth/demo-accounts")
    def accounts():
        return {"items": [{"account": name, "display_name": users[uid]["display_name"],
                            "role": "KNOWLEDGE_ADMIN" if name.startswith("KA") else "SUPPORT_OFFICER" if name.startswith("OF") else "STUDENT"} for name, uid in aliases.items()]}

    @app.post("/v1/auth/demo-login")
    def login(body: LoginBody):
        uid = aliases.get(body.account.upper())
        if not uid:
            raise CertificateError(401, "DEMO_ACCOUNT_UNKNOWN", "Tài khoản không tồn tại")
        token = adapter.mint_token(uid)
        response = JSONResponse({"token": token, "user": me(adapter.resolve_token(token))})
        response.set_cookie("auth_token", token, httponly=True, samesite="lax", path="/", max_age=3600)
        return response

    @app.get("/v1/auth/demo-session")
    def current_session(request: Request):
        # Preserve the actor and session; never silently switch an officer to a student.
        actor = get_current_identity(request)
        token = request.headers.get("authorization", "").removeprefix("Bearer ").strip() or request.cookies.get("auth_token")
        return {"token": token, **me(actor)}

    @app.get("/v1/users/me")
    def current_user(request: Request):
        return me(get_current_identity(request))

    @app.post("/v1/auth/logout")
    def logout(request: Request):
        actor = get_current_identity(request)
        token = request.headers.get("authorization", "").removeprefix("Bearer ").strip() or request.cookies.get("auth_token")
        session_service.revoke_session(token, actor_id=actor.subject_id)
        response = JSONResponse({"status": "revoked"})
        response.delete_cookie("auth_token", path="/")
        return response

    @app.get("/v1/certificate-guidance")
    def get_guidance():
        return guidance

    @app.get("/v1/certificate-guidance/sources/{source_id}")
    def source(source_id: str):
        row = next((r for r in guidance["sources"] if r["id"] == source_id), None)
        if row is None:
            raise HTTPException(404)
        return row

    @app.post("/v1/document-assistant")
    def assistant(body: AssistantBody, request: Request):
        actor = get_current_identity(request)
        draft_adapter.propose(actor, body.message)
        return propose_certificate(body.message, guidance)

    app.include_router(create_certificate_router(service, draft_adapter=draft_adapter if integrated_rag_app is not None else None))

    @app.get("/v1/conversations")
    @app.post("/v1/conversations")
    @app.get("/v1/conversations/{resource:path}")
    @app.post("/v1/conversations/{resource:path}")
    @app.get("/v1/policy-graph/{resource:path}")
    @app.post("/v1/policy-graph/{resource:path}")
    async def rag_proxy(request: Request, resource: str = ""):
        actor = get_current_identity(request)
        if request.url.path.startswith("/v1/conversations"):
            if getattr(request.app.state, 'native_chat_local', False):
                raise HTTPException(503, 'Local chat consumer unavailable; proxy fallback disabled')
            service.authorize(actor, IdentityRole.STUDENT)
        # Fixed loopback destination, existing actor token, no credentials or new ledger.
        path = request.url.path
        if ".." in path or "\\" in path or len(path) > 500 or len(request.url.query) > 1024:
            raise HTTPException(404)
        body = await request.body()
        if len(body) > 20000:
            raise HTTPException(413)
        catalog = getattr(request.app.state, "conversation_catalog", None)
        if catalog is not None and request.method == "POST" and path.startswith("/v1/conversations"):
            from campus247.presentation.chat import CreateMessagePayload, CreateConversationPayload
            try:
                payload = json.loads(body) if body else {}
                if path.endswith("/messages:stream"):
                    value = CreateMessagePayload.model_validate(payload)
                    if value.client_id is not None:
                        raise CertificateError(409, "CAPABILITY_NOT_AVAILABLE", "Writer proxy chưa hỗ trợ stable turn receipt")
                    identifier = path.split("/")[3]
                    if not (await catalog.read(actor, identifier))["can_continue"]:
                        raise CertificateError(409, "CHAT_NOT_CONTINUABLE", "Hội thoại lưu trữ hoặc hết hạn; dữ liệu được giữ")
                elif path == "/v1/conversations":
                    if CreateConversationPayload.model_validate(payload).client_id is not None:
                        raise CertificateError(409, "CAPABILITY_NOT_AVAILABLE", "Writer proxy chưa hỗ trợ stable create receipt")
            except ValueError:
                raise HTTPException(422, "Invalid conversation payload") from None
        token = request.headers.get("authorization", "").removeprefix("Bearer ").strip() or request.cookies.get("auth_token")
        client = httpx.AsyncClient(base_url="http://127.0.0.1:8003" if service_operations else "http://127.0.0.1:8000", timeout=40, trust_env=False, follow_redirects=False, transport=app_transport)
        try:
            upstream = await client.send(client.build_request(request.method, path,
                params=request.query_params, content=body, headers={"Authorization": "Bearer " + token,
                "Content-Type": request.headers.get("content-type", "application/json")}), stream=True)
        except httpx.HTTPError:
            await client.aclose()
            raise CertificateError(503, "RAG_UNAVAILABLE", "Dịch vụ hỏi đáp hiện không khả dụng") from None
        async def stream():
            try:
                async for part in upstream.aiter_bytes():
                    yield part
            finally:
                await upstream.aclose()
                await client.aclose()
        return StreamingResponse(stream(), status_code=upstream.status_code,
                                 headers={"Content-Type": upstream.headers.get("content-type", "application/json"),
                                     **({"X-Request-Id": upstream.headers["x-request-id"]} if "x-request-id" in upstream.headers else {})})

    if frontend_port is not None:
        if frontend_port not in {3002, 3003, 3004, 3005} or frontend_port == 3005 and not service_operations or frontend_port == 3004 and getattr(integrated_rag_app.state, "policy_graph", None) is None:
            raise ValueError("explicit certificate frontend port required")
        @app.get("/{page_path:path}", include_in_schema=False)
        async def frontend(page_path: str, request: Request):
            path = "/" + page_path
            if path not in {"/", "/login", "/tickets", "/staff", "/chat", "/privacy", "/knowledge/policy-graph", "/services", "/knowledge/sources"} and not path.startswith(("/_next/static/", "/images/")):
                raise HTTPException(404)
            if ".." in path or "\\" in path or len(request.url.query) > 1024:
                raise HTTPException(404)
            try:
                async with httpx.AsyncClient(timeout=10, trust_env=False, follow_redirects=False) as client:
                    response = await client.get(f"http://127.0.0.1:{frontend_port}" + path, params=request.query_params)
                    if len(response.content) > 4_194_304:
                        raise HTTPException(502)
                    return Response(response.content, status_code=response.status_code,
                                    headers={"Content-Type": response.headers.get("content-type", "application/octet-stream")})
            except httpx.HTTPError:
                raise HTTPException(503, detail="Frontend demo chưa khởi chạy") from None
    return app
