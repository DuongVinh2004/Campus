"""The whole sign-in with the university account against a simulated provider: the happy path and every way it must fail closed."""
from __future__ import annotations

import base64
import json
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit/identity"))
from fake_oidc_provider import CLIENT_ID, ISSUER, REDIRECT, FakeProvider  # noqa: E402

from campus247.application.identity.session_service import SessionService  # noqa: E402
from campus247.infrastructure.identity.oidc import OidcClient, OidcConfig  # noqa: E402
from campus247.infrastructure.identity.oidc_accounts import OidcAccountStore  # noqa: E402
from campus247.infrastructure.identity.oidc_session import OidcSessionAdapter, load_or_create_key  # noqa: E402
from campus247.ports.identity import IdentityRole  # noqa: E402
from campus247.presentation.identity import IdentityMiddleware, get_current_identity  # noqa: E402
from campus247.presentation.oidc import create_oidc_router  # noqa: E402

ROLE_MAP = {"sinhvien": "STUDENT", "giangvien": "LECTURER"}


class Rig:
    def __init__(self, tmp_path, **config_over):
        self.provider = FakeProvider()
        self.config = OidcConfig(issuer=ISSUER, client_id=CLIENT_ID, redirect_uri=REDIRECT, role_map=ROLE_MAP, jit_provisioning=True, **config_over)
        self.store = OidcAccountStore(tmp_path / "oidc.sqlite3")
        self.sessions = OidcSessionAdapter(load_or_create_key(tmp_path / "oidc-session.key"), "huce-local-public")
        self.revocations = SessionService()
        app = FastAPI()
        app.add_middleware(IdentityMiddleware, adapter=self.sessions, session_service=self.revocations)
        app.include_router(create_oidc_router(self.config, OidcClient(self.config, self.provider.client()), self.store, self.sessions))

        @app.get("/whoami")
        def whoami(request: Request):
            identity = get_current_identity(request)
            return {"roles": [r.value for r in identity.roles], "code": identity.student_code, "name": identity.display_name}

        self.app = app

    def browser(self, **kwargs):
        return TestClient(self.app, follow_redirects=False, **kwargs)


@pytest.fixture
def rig(tmp_path):
    return Rig(tmp_path)


def sign_in(rig, browser, *, next_path="/chat", **claim_overrides):
    """start -> the provider -> callback, the way a browser does it. Returns the callback response."""
    started = browser.get("/v1/auth/oidc/start", params={"next": next_path} if next_path else {})
    assert started.status_code == 302
    returned = rig.provider.authorize(started.headers["location"], **claim_overrides)
    return browser.get(returned.replace(REDIRECT, "/v1/auth/oidc/callback"))  # the test client talks to the app directly, not to the public host


def location(response):
    return response.headers["location"]


def test_the_providers_endpoint_offers_the_university_account(rig):
    assert rig.browser().get("/v1/auth/providers").json() == {"providers": [{"id": "oidc", "label": "Tài khoản trường"}]}


def test_start_redirects_to_the_provider_with_pkce_and_a_locked_attempt_cookie(rig):
    response = rig.browser().get("/v1/auth/oidc/start")
    assert response.status_code == 302 and response.headers["cache-control"] == "no-store"
    target = urlparse(location(response))
    query = parse_qs(target.query)
    assert f"{target.scheme}://{target.netloc}{target.path}" == ISSUER + "/protocol/openid-connect/auth"
    assert query["code_challenge_method"] == ["S256"] and query["redirect_uri"] == [REDIRECT] and len(query["state"][0]) >= 24
    cookie = response.headers["set-cookie"]
    assert cookie.startswith("oidc_attempt=") and "HttpOnly" in cookie and "SameSite=lax" in cookie and "Path=/v1/auth/oidc" in cookie and "Secure" not in cookie


def test_the_attempt_cookie_is_secure_over_https_or_behind_our_own_proxy(rig):
    assert "Secure" in TestClient(rig.app, base_url="https://chat.example.edu.vn", follow_redirects=False).get("/v1/auth/oidc/start").headers["set-cookie"]
    behind = rig.browser(client=("127.0.0.1", 50000)).get("/v1/auth/oidc/start", headers={"X-Forwarded-Proto": "https"})
    assert "Secure" in behind.headers["set-cookie"]
    spoofed = rig.browser(client=("203.0.113.9", 50000)).get("/v1/auth/oidc/start", headers={"X-Forwarded-Proto": "https"})
    assert "Secure" not in spoofed.headers["set-cookie"]  # a forwarded header from anywhere but this machine is ignored


def test_a_complete_sign_in_creates_a_session_for_the_right_person_and_lands_on_the_page_asked_for(rig):
    browser = rig.browser()
    done = sign_in(rig, browser, next_path="/knowledge/sources")
    assert done.status_code == 302 and location(done) == "/knowledge/sources"
    cookies = done.headers.get_list("set-cookie")
    session = next(c for c in cookies if c.startswith("auth_token="))
    assert "HttpOnly" in session and "SameSite=lax" in session and "Max-Age=3600" in session
    assert any(c.startswith("oidc_attempt=") and ("Max-Age=0" in c or '=""' in c or "expires" in c.lower()) for c in cookies)  # the attempt cookie is cleared
    me = browser.get("/whoami").json()
    assert me == {"roles": ["STUDENT"], "code": "20215678", "name": "Nguyễn Văn A"}


def test_the_session_token_is_ours_not_the_providers(rig):
    browser = rig.browser()
    done = sign_in(rig, browser)
    token = next(c for c in done.headers.get_list("set-cookie") if c.startswith("auth_token=")).split(";")[0].split("=", 1)[1]
    payload = json.loads(base64.urlsafe_b64decode(token.split(".")[0]))
    assert payload["iss"] == "urn:campus247:issuer:oidc-session" and payload["exp"] - payload["iat"] <= 3600
    assert "id_token" not in token and "opaque" not in token


def test_a_logout_revokes_the_session_for_good(rig):
    browser = rig.browser()
    done = sign_in(rig, browser)
    token = next(c for c in done.headers.get_list("set-cookie") if c.startswith("auth_token=")).split(";")[0].split("=", 1)[1].strip('"')  # the cookie value is quoted
    assert browser.get("/whoami").status_code == 200
    rig.revocations.revoke(token)
    assert browser.get("/whoami").status_code == 401


@pytest.mark.parametrize("override", [{"nonce": "not-the-nonce-we-sent"}, {"aud": "another-client"}, {"iss": "https://evil.example/realms/huce"}, {"exp": 1}])
def test_a_bad_id_token_never_creates_a_session(rig, override):
    browser = rig.browser()
    done = sign_in(rig, browser, **override)
    assert location(done).startswith("/login?error=TOKEN_") and "auth_token" not in done.headers.get("set-cookie", "")
    assert browser.get("/whoami").status_code == 401


def test_the_callback_cannot_be_replayed(rig):
    browser = rig.browser()
    started = browser.get("/v1/auth/oidc/start")
    callback = rig.provider.authorize(location(started)).replace(REDIRECT, "/v1/auth/oidc/callback")
    assert location(browser.get(callback)) == "/"
    again = browser.get(callback)
    assert location(again) == "/login?error=LOGIN_ATTEMPT_INVALID"


def test_a_callback_from_a_different_browser_is_refused(rig):
    victim, attacker = rig.browser(), rig.browser()
    started = victim.get("/v1/auth/oidc/start")
    callback = rig.provider.authorize(location(started)).replace(REDIRECT, "/v1/auth/oidc/callback")
    assert location(attacker.get(callback)) == "/login?error=LOGIN_ATTEMPT_INVALID"  # the attacker has no attempt cookie
    assert attacker.get("/whoami").status_code == 401


def test_a_forged_state_is_refused_and_does_not_burn_the_real_attempt(rig):
    browser = rig.browser()
    started = browser.get("/v1/auth/oidc/start")
    real = rig.provider.authorize(location(started)).replace(REDIRECT, "/v1/auth/oidc/callback")
    forged = real.replace("state=", "state=forged")
    assert location(browser.get(forged)) == "/login?error=LOGIN_ATTEMPT_INVALID"
    assert location(browser.get(real)) == "/"


def test_missing_parameters_and_provider_errors_fail_closed(rig):
    browser = rig.browser()
    assert location(browser.get("/v1/auth/oidc/callback")) == "/login?error=LOGIN_ATTEMPT_INVALID"
    browser.get("/v1/auth/oidc/start")
    assert location(browser.get("/v1/auth/oidc/callback", params={"error": "access_denied", "error_description": "<script>"})) == "/login?error=PROVIDER_DENIED"
    assert location(browser.get("/v1/auth/oidc/callback", params={"code": "x" * 3000, "state": "s"})) == "/login?error=LOGIN_ATTEMPT_INVALID"


def test_an_unknown_person_is_refused_when_jit_is_off(tmp_path):
    rig = Rig(tmp_path)
    rig.config = OidcConfig(issuer=ISSUER, client_id=CLIENT_ID, redirect_uri=REDIRECT, role_map=ROLE_MAP, jit_provisioning=False)
    app = FastAPI()
    app.include_router(create_oidc_router(rig.config, OidcClient(rig.config, rig.provider.client()), rig.store, rig.sessions))
    browser = TestClient(app, follow_redirects=False)
    done = sign_in(rig, browser)
    assert location(done) == "/login?error=ACCOUNT_NOT_PROVISIONED" and "auth_token" not in done.headers.get("set-cookie", "")


def test_a_student_without_a_student_code_is_refused(rig):
    done = sign_in(rig, rig.browser(), student_id="abc")
    assert location(done) == "/login?error=STUDENT_CODE_INVALID"


def test_a_provider_that_is_down_ends_on_the_login_page(rig):
    rig.provider.down = True
    assert location(rig.browser().get("/v1/auth/oidc/start")) == "/login?error=PROVIDER_UNREACHABLE"


def test_the_return_path_cannot_point_off_site(rig):
    for evil in ("https://evil.example/phish", "//evil.example", "/\\evil.example"):
        done = sign_in(rig, rig.browser(), next_path=evil)
        assert location(done) == "/"


def test_the_privileged_roles_are_granted_only_to_the_listed_subject(tmp_path):
    rig = Rig(tmp_path, privileged_subjects=({"sub": "user-123", "roles": ["KNOWLEDGE_ADMIN"]},))
    browser = rig.browser()
    sign_in(rig, browser)
    assert set(browser.get("/whoami").json()["roles"]) == {"STUDENT", "KNOWLEDGE_ADMIN"}
    stranger = rig.browser()
    sign_in(rig, stranger, sub="someone-else", student_id="20219999")
    assert stranger.get("/whoami").json()["roles"] == ["STUDENT"]


def test_nothing_secret_reaches_the_log(rig, caplog):
    import logging
    with caplog.at_level(logging.INFO, logger="campus247.oidc"):
        sign_in(rig, rig.browser(), aud="another-client")
        sign_in(rig, rig.browser())
    assert "oidc_login_refused code=TOKEN_AUDIENCE_MISMATCH" in caplog.text and "oidc_login_ok roles=STUDENT" in caplog.text
    assert "20215678" not in caplog.text and "user-123" not in caplog.text and "Nguy" not in caplog.text
