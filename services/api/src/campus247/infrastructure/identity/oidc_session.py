"""Sessions issued after an OpenID Connect sign-in.

The provider's tokens are never used as the session. After the ID token is verified and mapped to an account, the application mints
its own short token (one hour), signed with a key that only this server holds, naming the account, its roles and a unique id. The
unique id is what a logout revokes. Roles are fixed for the life of the token, so a role change takes effect at the next sign-in.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from campus247.ports.identity import IdentityContext, IdentityRole

ISSUER = "urn:campus247:issuer:oidc-session"
MAX_TTL_S = 3600


def load_or_create_key(path: Path) -> bytes:
    """The signing key, created once with owner-only permissions. Losing the file signs everyone out; it is not a data loss."""
    if path.exists():
        return bytes.fromhex(path.read_text(encoding="ascii").strip())
    key = secrets.token_bytes(32)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="ascii") as stream:
        stream.write(key.hex())
    return key


class OidcSessionAdapter:
    def __init__(self, key: bytes, tenant: str) -> None:
        if len(key) < 32:
            raise ValueError("session key too short")
        self._key, self.tenant = key, tenant

    def _sign(self, encoded: str) -> str:
        return base64.urlsafe_b64encode(hmac.new(self._key, encoded.encode(), hashlib.sha256).digest()).decode()

    def mint(self, account: dict[str, Any], *, ttl_s: int = MAX_TTL_S) -> str:
        now = int(time.time())
        claims = {"sub": account["subject_id"], "iss": ISSUER, "tenant": self.tenant, "iat": now, "exp": now + min(ttl_s, MAX_TTL_S),
                  "jti": secrets.token_urlsafe(24), "roles": [role.value for role in account["roles"]], "name": account["display_name"],
                  "ext": account["external_subject"], "code": account.get("student_code")}
        encoded = base64.urlsafe_b64encode(json.dumps(claims, sort_keys=True).encode()).decode()
        return encoded + "." + self._sign(encoded)

    def resolve_token(self, token: str) -> IdentityContext:
        if not isinstance(token, str) or len(token) > 4096 or token.count(".") != 1:
            raise ValueError("Invalid session")
        encoded, signature = token.split(".")
        if not hmac.compare_digest(self._sign(encoded), signature):
            raise ValueError("Invalid session signature")
        claims = json.loads(base64.urlsafe_b64decode(encoded))
        now = int(datetime.now(UTC).timestamp())
        if (claims.get("iss") != ISSUER or claims.get("tenant") != self.tenant or not claims.get("jti") or type(claims.get("iat")) is not int
                or type(claims.get("exp")) is not int or claims["iat"] > now + 60 or claims["exp"] <= now or not 0 < claims["exp"] - claims["iat"] <= MAX_TTL_S):
            raise ValueError("Invalid session claims")
        roles = tuple(IdentityRole(name) for name in claims["roles"])
        return IdentityContext(claims["sub"], "oidc:" + str(claims.get("ext", "")), ISSUER, roles, claims.get("name") or "Người dùng",
                               datetime.fromtimestamp(claims["iat"], UTC), datetime.fromtimestamp(claims["exp"], UTC), tenant_id=self.tenant,
                               session_id=claims["jti"], is_synthetic=False, student_code=claims.get("code"))
