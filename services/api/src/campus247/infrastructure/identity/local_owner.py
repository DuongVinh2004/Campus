"""Explicit owner-designated local identity; no university directory claims."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from datetime import UTC, datetime, timedelta

from campus247.ports.identity import IdentityContext, IdentityRole

ISSUER = "urn:campus247:issuer:local-owner"


class LocalOwnerIdentityAdapter:
    def __init__(self, path, tenant):
        self.path, self.tenant = path, tenant
        self._attempts = []

    def directory(self):
        value = json.loads(self.path.read_text(encoding="utf-8"))
        if value["tenant"] != self.tenant or value["issuer"] != ISSUER:
            raise ValueError("Local identity scope mismatch")
        return value

    def authenticate(self, username, password):
        now = time.monotonic()
        self._attempts = [at for at in self._attempts if now - at < 60]
        if len(self._attempts) >= 5:
            raise ValueError("Login rate limited")
        self._attempts.append(now)
        value = self.directory()
        actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(value["salt"]), n=16384, r=8, p=1).hex()
        if not (hmac.compare_digest(username, value["username"]) and hmac.compare_digest(actual, value["password_hash"])):
            raise ValueError("Invalid credentials")
        self._attempts.clear()
        return self.mint_token(value["owner_id"])

    def mint_token(self, subject, ttl_seconds=3600):
        value = self.directory()
        if subject not in {value["owner_id"], value["agent_id"]}:
            raise ValueError("Unknown local principal")
        now = int(datetime.now(UTC).timestamp())
        payload = {"sub": subject, "iss": ISSUER, "tenant": self.tenant, "iat": now,
                   "exp": now + min(ttl_seconds, 3600), "jti": secrets.token_urlsafe(24)}
        encoded = base64.urlsafe_b64encode(json.dumps(payload, sort_keys=True).encode()).decode()
        signature = hmac.new(bytes.fromhex(value["signing_key"]), encoded.encode(), hashlib.sha256).digest()
        return encoded + "." + base64.urlsafe_b64encode(signature).decode()

    def resolve_token(self, token):
        value = self.directory()
        payload, signature = token.split(".")
        expected = hmac.new(bytes.fromhex(value["signing_key"]), payload.encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(expected, base64.urlsafe_b64decode(signature)):
            raise ValueError("Invalid signature")
        claims = json.loads(base64.urlsafe_b64decode(payload))
        now = int(datetime.now(UTC).timestamp())
        if (claims["iss"] != ISSUER or claims["tenant"] != self.tenant or claims["exp"] <= now
            or claims["iat"] > now or claims["exp"] - claims["iat"] > 3600
            or claims["sub"] not in {value["owner_id"], value["agent_id"]}):
            raise ValueError("Invalid local session")
        agent = claims["sub"] == value["agent_id"]
        return IdentityContext(claims["sub"], "local:" + claims["sub"], ISSUER,
            (IdentityRole.KNOWLEDGE_ADMIN,), "Agent kỹ thuật (tự động)" if agent else "Quản trị tri thức — chủ hệ thống chỉ định",
            datetime.fromtimestamp(claims["iat"], UTC), datetime.fromtimestamp(claims["exp"], UTC),
            tenant_id=self.tenant, session_id=claims["jti"], is_synthetic=False, faculty_code="FIT")
