"""Sign in with the university account: /v1/auth/oidc/start sends the browser to the provider, /v1/auth/oidc/callback receives it back.

Every failure ends as a redirect to /login?error=<fixed code>: no provider text, token or claim value reaches the URL or a log line.
The cookie that ties a callback to the browser that started the login is HttpOnly, SameSite=Lax (the callback is a cross-site
navigation) and limited to this path. The session cookie is SameSite=Lax for the same reason: with Strict, the page the user lands on
after the redirect would be requested without it.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse

from campus247.ports.oidc import OidcError, new_pkce, safe_next

LOG = logging.getLogger("campus247.oidc")
ATTEMPT_COOKIE = "oidc_attempt"
COOKIE_PATH = "/v1/auth/oidc"
LOOPBACK = {"127.0.0.1", "::1"}
NO_STORE = {"Cache-Control": "no-store"}


def _secure(request: Request) -> bool:
    """HTTPS directly, or through our own reverse proxy on this machine that says so. A forwarded header from anywhere else is ignored."""
    if request.url.scheme == "https":
        return True
    return request.client is not None and request.client.host in LOOPBACK and request.headers.get("x-forwarded-proto") == "https"


def _failure(code: str, *, keep_attempt: bool = False) -> RedirectResponse:
    """Back to the login page. The attempt cookie is kept when the attempt itself was not used up (a request with the wrong state),
    so a forged callback cannot make the real one fail."""
    response = RedirectResponse(f"/login?error={quote(code)}", status_code=302, headers=NO_STORE)
    if not keep_attempt:
        response.delete_cookie(ATTEMPT_COOKIE, path=COOKIE_PATH)
    return response


def create_oidc_router(config: Any, client: Any, store: Any, sessions: Any, *, clock=lambda: datetime.now(UTC)) -> APIRouter:
    """`config`, `client`, `store` and `sessions` are the OidcConfig, OidcClient, OidcAccountStore and OidcSessionAdapter the caller built
    (infrastructure/identity/oidc*.py); this layer only calls them."""
    router = APIRouter(tags=["Authentication"])

    @router.get("/v1/auth/providers")
    async def providers():
        return JSONResponse({"providers": [{"id": "oidc", "label": "Tài khoản trường"}]}, headers=NO_STORE)

    @router.get("/v1/auth/oidc/start")
    async def start(request: Request, next: str | None = None):
        verifier, challenge = new_pkce()
        attempt = store.start_attempt(verifier=verifier, next_path=safe_next(next), now=clock())
        try:
            target = await client.authorization_url(state=attempt["state"], nonce=attempt["nonce"], code_challenge=challenge)
        except OidcError as error:
            LOG.warning("oidc_start_failed code=%s", error.code)
            return _failure(error.code)
        response = RedirectResponse(target, status_code=302, headers=NO_STORE)
        response.set_cookie(ATTEMPT_COOKIE, attempt["id"], max_age=600, httponly=True, samesite="lax", secure=_secure(request), path=COOKIE_PATH)
        return response

    @router.get("/v1/auth/oidc/callback")
    async def callback(request: Request, code: str | None = None, state: str | None = None, error: str | None = None):
        attempt_id = request.cookies.get(ATTEMPT_COOKIE)
        if error:
            LOG.info("oidc_provider_denied")
            return _failure("PROVIDER_DENIED")
        if not attempt_id or not code or not state or len(code) > 2048 or len(state) > 256:
            return _failure("LOGIN_ATTEMPT_INVALID", keep_attempt=True)
        try:
            attempt = store.finish_attempt(attempt_id, state, now=clock())
        except OidcError as failure:
            LOG.warning("oidc_login_refused code=%s", failure.code)
            return _failure(failure.code, keep_attempt=True)
        try:
            tokens = await client.exchange_code(code, attempt["verifier"])
            claims = await client.verify_id_token(tokens["id_token"], nonce=attempt["nonce"])
            account = store.resolve(config, claims, now=clock())
        except OidcError as failure:
            LOG.warning("oidc_login_refused code=%s", failure.code)
            return _failure(failure.code)
        token = sessions.mint(account)
        response = RedirectResponse(attempt["next_path"], status_code=302, headers=NO_STORE)
        response.delete_cookie(ATTEMPT_COOKIE, path=COOKIE_PATH)
        response.set_cookie("auth_token", token, max_age=3600, httponly=True, samesite="lax", secure=_secure(request), path="/")
        LOG.info("oidc_login_ok roles=%s", ",".join(role.value for role in account["roles"]))
        return response

    return router
