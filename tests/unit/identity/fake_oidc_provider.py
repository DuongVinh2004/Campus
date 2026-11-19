"""An OpenID Connect provider simulated in memory (discovery, key set, token endpoint) for tests. No network, no real keys."""
from __future__ import annotations

import base64
import hashlib
import json
import secrets
import time
from urllib.parse import parse_qs, urlencode, urlparse

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from jwt.algorithms import ECAlgorithm, RSAAlgorithm

ISSUER = "https://idp.example.edu.vn/realms/huce"
CLIENT_ID = "campus247"
REDIRECT = "https://chat.example.edu.vn/v1/auth/oidc/callback"


class FakeProvider:
    def __init__(self, issuer: str = ISSUER) -> None:
        self.issuer = issuer
        self.rsa = {"kid-1": rsa.generate_private_key(public_exponent=65537, key_size=2048)}
        self.ec = ec.generate_private_key(ec.SECP256R1())
        self.published = ["kid-1"]  # kids in the key set; the test may swap or add
        self.requests: list[tuple[str, str]] = []
        self.issued_codes: dict[str, dict] = {}
        self.discovery_override: dict | None = None
        self.down = False

    # --------------------------------------------------------------- tokens
    def claims(self, **over) -> dict:
        now = int(time.time())
        base = {"iss": self.issuer, "sub": "user-123", "aud": CLIENT_ID, "iat": now, "exp": now + 600, "nonce": "n-1",
                "name": "Nguyễn Văn A", "student_id": "20215678", "groups": ["sinhvien"]}
        return {key: value for key, value in (base | over).items() if value is not None}

    def sign(self, claims: dict | None = None, *, kid: str = "kid-1", alg: str = "RS256", key=None, **over) -> str:
        payload = claims if claims is not None else self.claims(**over)
        signing_key = key or (self.ec if alg == "ES256" else self.rsa[kid])
        return jwt.encode(payload, signing_key, algorithm=alg, headers={"kid": kid})

    def add_rsa_key(self, kid: str, *, publish: bool = True) -> None:
        self.rsa[kid] = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        if publish:
            self.published.append(kid)

    def authorize(self, authorization_url: str, **claim_overrides) -> str:
        """What the user's browser does at the provider: sign in, then come back to the redirect URI with a code and the state."""
        query = {key: values[0] for key, values in parse_qs(urlparse(authorization_url).query).items()}
        assert query["code_challenge_method"] == "S256" and query["client_id"] == CLIENT_ID
        code = secrets.token_urlsafe(12)
        self.issued_codes[code] = {"challenge": query["code_challenge"], "id_token": self.sign(**({"nonce": query["nonce"]} | claim_overrides))}
        return f"{query['redirect_uri']}?{urlencode({'code': code, 'state': query['state']})}"

    # --------------------------------------------------------------- http
    def jwks(self) -> dict:
        keys = []
        for kid in self.published:
            if kid == "ec-1":
                public = json.loads(ECAlgorithm.to_jwk(self.ec.public_key()))
            else:
                public = json.loads(RSAAlgorithm.to_jwk(self.rsa[kid].public_key()))
            keys.append(public | {"kid": kid, "use": "sig"})
        return {"keys": keys}

    def metadata(self) -> dict:
        base = self.issuer
        return self.discovery_override or {"issuer": base, "authorization_endpoint": base + "/protocol/openid-connect/auth",
                                           "token_endpoint": base + "/protocol/openid-connect/token", "jwks_uri": base + "/protocol/openid-connect/certs"}

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append((request.method, request.url.path))
        if self.down:
            raise httpx.ConnectError("provider down", request=request)
        if request.url.path.endswith("/.well-known/openid-configuration"):
            return httpx.Response(200, json=self.metadata())
        if request.url.path.endswith("/certs"):
            return httpx.Response(200, json=self.jwks())
        if request.url.path.endswith("/token") and request.method == "POST":
            form = {key: values[0] for key, values in parse_qs(request.content.decode()).items()}
            issued = self.issued_codes.pop(form.get("code", ""), None)  # a code works once
            verified = issued is not None and (
                issued.get("verifier") == form.get("code_verifier") if "verifier" in issued
                else base64.urlsafe_b64encode(hashlib.sha256(form.get("code_verifier", "").encode()).digest()).rstrip(b"=").decode() == issued["challenge"])
            if issued is None or not verified or form.get("redirect_uri") != REDIRECT:
                return httpx.Response(400, json={"error": "invalid_grant"})
            return httpx.Response(200, json={"id_token": issued["id_token"], "access_token": "opaque", "token_type": "Bearer"})
        return httpx.Response(404)

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(self.handler))

    def count(self, suffix: str) -> int:
        return sum(1 for _, path in self.requests if path.endswith(suffix))
