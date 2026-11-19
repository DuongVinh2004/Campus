"""OpenID Connect sign-in (authorization code with PKCE) for a university identity provider.

This module only talks to the provider and verifies what comes back. It creates no session and decides no role: the caller maps the
verified claims to an account (see oidc_accounts.py). Nothing here has been run against a real university provider; it is tested
against a provider simulated in the test suite, including the attacks that matter (wrong issuer or audience, expired or replayed
tokens, `alg=none`, an HMAC token signed with the public key, a swapped key set).

Errors carry a short machine code (`OidcError.code`) and never the provider's text, a token or a claim value.
"""
from __future__ import annotations

import base64
import hashlib
import json
import secrets
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlencode, urlparse

import httpx
import jwt
from jwt.algorithms import ECAlgorithm, RSAAlgorithm

ALLOWED_ALGORITHMS = ("RS256", "ES256")
LEEWAY_S = 60
DISCOVERY_TTL_S = 3600
JWKS_REFRESH_MIN_S = 60
HTTP_TIMEOUT_S = 5.0


class OidcError(Exception):
    """`code` is one of a fixed set, safe to show in a URL or a log line."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class OidcConfig:
    issuer: str
    client_id: str
    redirect_uri: str
    client_secret: str | None = None
    scopes: tuple[str, ...] = ("openid", "profile", "email")
    claims: Mapping[str, str] = field(default_factory=lambda: {"student_code": "student_id", "display_name": "name", "roles": "groups"})
    role_map: Mapping[str, str] = field(default_factory=dict)
    student_code_pattern: str = r"^[0-9]{6,10}$"
    jit_provisioning: bool = False
    privileged_subjects: tuple[Mapping[str, Any], ...] = ()
    allow_insecure_localhost: bool = False  # only for tests with a simulated provider on http://localhost

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, secret_reader: Callable[[str], str] | None = None) -> "OidcConfig":
        """Build from the JSON config file. The client secret is read from the file named in `client_secret_file`, never inlined."""
        required = ("issuer", "client_id", "redirect_uri")
        missing = [name for name in required if not data.get(name)]
        if missing:
            raise OidcError("CONFIG_INCOMPLETE")
        secret = None
        if data.get("client_secret_file"):
            if secret_reader is None:
                raise OidcError("CONFIG_INCOMPLETE")
            secret = secret_reader(str(data["client_secret_file"]))
        return cls(issuer=str(data["issuer"]), client_id=str(data["client_id"]), redirect_uri=str(data["redirect_uri"]), client_secret=secret,
                   scopes=tuple(data.get("scopes", ("openid", "profile", "email"))),
                   claims=dict(data["claims"]) if data.get("claims") else {"student_code": "student_id", "display_name": "name", "roles": "groups"},
                   role_map=dict(data.get("role_map", {})), student_code_pattern=str(data.get("student_code_pattern", r"^[0-9]{6,10}$")),
                   jit_provisioning=bool(data.get("jit_provisioning", False)), privileged_subjects=tuple(data.get("privileged_subjects", ())))


def new_pkce() -> tuple[str, str]:
    """(verifier, S256 challenge)."""
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(48)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


def _https_or_local(url: str, *, allow_local: bool) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" or (allow_local and parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"})


class OidcClient:
    def __init__(self, config: OidcConfig, http: httpx.AsyncClient, *, clock: Callable[[], float] = time.time) -> None:
        if not _https_or_local(config.issuer, allow_local=config.allow_insecure_localhost):
            raise OidcError("CONFIG_INSECURE_ISSUER")
        self._config, self._http, self._clock = config, http, clock
        self._discovery: tuple[float, dict[str, Any]] | None = None
        self._jwks: tuple[float, dict[str, Any]] | None = None

    # ------------------------------------------------------------------ provider metadata
    async def _get_json(self, url: str, headers: Mapping[str, str] | None = None) -> dict[str, Any]:
        try:
            response = await self._http.get(url, headers=headers, timeout=HTTP_TIMEOUT_S)
            if response.status_code != 200:
                raise OidcError("PROVIDER_ERROR")
            data = response.json()
        except OidcError:
            raise
        except (httpx.HTTPError, ValueError):
            raise OidcError("PROVIDER_UNREACHABLE") from None
        if not isinstance(data, dict):
            raise OidcError("PROVIDER_ERROR")
        return data

    async def discovery(self) -> dict[str, Any]:
        now = self._clock()
        if self._discovery is not None and now - self._discovery[0] < DISCOVERY_TTL_S:
            return self._discovery[1]
        document = await self._get_json(self._config.issuer.rstrip("/") + "/.well-known/openid-configuration")
        if document.get("issuer") != self._config.issuer:  # exact match: a provider must not answer for another issuer
            raise OidcError("ISSUER_MISMATCH")
        for key in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
            if not isinstance(document.get(key), str) or not _https_or_local(document[key], allow_local=self._config.allow_insecure_localhost):
                raise OidcError("PROVIDER_METADATA_INVALID")
        self._discovery = (now, document)
        return document

    async def _key_for(self, kid: str | None, alg: str) -> Any:
        """The signing key for a token header. An unknown `kid` refreshes the key set once, at most once a minute."""
        document = await self.discovery()
        now = self._clock()
        if self._jwks is None:
            self._jwks = (now, await self._get_json(document["jwks_uri"]))
        key = self._find_key(kid, alg)
        if key is None and now - self._jwks[0] >= JWKS_REFRESH_MIN_S:  # the provider may have rotated its keys
            self._jwks = (now, await self._get_json(document["jwks_uri"]))
            key = self._find_key(kid, alg)
        if key is None:
            raise OidcError("SIGNING_KEY_UNKNOWN")
        return key

    def _find_key(self, kid: str | None, alg: str) -> Any:
        wanted_type = "RSA" if alg == "RS256" else "EC"
        for item in (self._jwks[1].get("keys", []) if self._jwks else []):
            if isinstance(item, dict) and item.get("kty") == wanted_type and item.get("use", "sig") == "sig" and (kid is None or item.get("kid") == kid):
                try:
                    return (RSAAlgorithm if alg == "RS256" else ECAlgorithm).from_jwk(json.dumps(item))
                except (jwt.PyJWTError, ValueError):
                    return None
        return None

    # ------------------------------------------------------------------ the flow
    async def authorization_url(self, *, state: str, nonce: str, code_challenge: str) -> str:
        document = await self.discovery()
        query = urlencode({"response_type": "code", "client_id": self._config.client_id, "redirect_uri": self._config.redirect_uri,
                           "scope": " ".join(self._config.scopes), "state": state, "nonce": nonce,
                           "code_challenge": code_challenge, "code_challenge_method": "S256"})
        return f"{document['authorization_endpoint']}?{query}"

    async def exchange_code(self, code: str, code_verifier: str) -> dict[str, Any]:
        document = await self.discovery()
        form = {"grant_type": "authorization_code", "code": code, "redirect_uri": self._config.redirect_uri,
                "client_id": self._config.client_id, "code_verifier": code_verifier}
        if self._config.client_secret:
            form["client_secret"] = self._config.client_secret
        try:
            response = await self._http.post(document["token_endpoint"], data=form, timeout=HTTP_TIMEOUT_S)
            body = response.json()
        except (httpx.HTTPError, ValueError):
            raise OidcError("PROVIDER_UNREACHABLE") from None
        if response.status_code != 200 or not isinstance(body, dict) or not isinstance(body.get("id_token"), str):
            raise OidcError("TOKEN_EXCHANGE_FAILED")
        return body

    async def verify_id_token(self, id_token: str, *, nonce: str) -> dict[str, Any]:
        """Signature, issuer, audience, expiry and nonce. Returns the claims; raises OidcError with a fixed code otherwise."""
        try:
            header = jwt.get_unverified_header(id_token)
        except jwt.PyJWTError:
            raise OidcError("TOKEN_MALFORMED") from None
        algorithm = header.get("alg")
        if algorithm not in ALLOWED_ALGORITHMS:  # blocks "none" and every HMAC algorithm before any key is looked at
            raise OidcError("TOKEN_ALGORITHM_NOT_ALLOWED")
        key = await self._key_for(header.get("kid"), algorithm)
        try:
            claims = jwt.decode(id_token, key, algorithms=list(ALLOWED_ALGORITHMS), audience=self._config.client_id, issuer=self._config.issuer,
                                leeway=LEEWAY_S, options={"require": ["exp", "iat", "iss", "aud", "sub"]})
        except jwt.ExpiredSignatureError:
            raise OidcError("TOKEN_EXPIRED") from None
        except jwt.InvalidAudienceError:
            raise OidcError("TOKEN_AUDIENCE_MISMATCH") from None
        except jwt.InvalidIssuerError:
            raise OidcError("TOKEN_ISSUER_MISMATCH") from None
        except jwt.InvalidSignatureError:
            raise OidcError("TOKEN_SIGNATURE_INVALID") from None
        except jwt.PyJWTError:
            raise OidcError("TOKEN_INVALID") from None
        audience = claims["aud"]
        if isinstance(audience, list) and len(audience) > 1 and claims.get("azp") != self._config.client_id:
            raise OidcError("TOKEN_AUTHORIZED_PARTY_MISMATCH")
        if not isinstance(claims.get("sub"), str) or not claims["sub"]:
            raise OidcError("TOKEN_INVALID")
        if not secrets.compare_digest(str(claims.get("nonce", "")), nonce):
            raise OidcError("TOKEN_NONCE_MISMATCH")
        return claims
