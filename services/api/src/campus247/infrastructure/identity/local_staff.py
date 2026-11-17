"""Password-authenticated local support-officer access, separate from HUCE SSO and from other accounts."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from datetime import UTC, datetime

from campus247.domain.shared.values import is_valid_uuid7
from campus247.ports.identity import IdentityContext, IdentityRole

ISSUER = "urn:campus247:issuer:local-staff"


class LocalStaffIdentityAdapter:
    def __init__(self, path, tenant):
        self.path, self.tenant = path, tenant
        self._attempts = {}

    def directory(self):
        value = json.loads(self.path.read_text(encoding="utf-8"))
        if (value.get("schema") != "local-staff-v1" or value.get("tenant") != self.tenant
                or value.get("issuer") != ISSUER or value.get("role") != "SUPPORT_OFFICER"
                or value.get("university_identity_verified") is not False
                or not is_valid_uuid7(value.get("subject_id", ""))
                or not value.get("staff_code", "").startswith("LOCAL-STAFF-")):
            raise ValueError("Local staff scope mismatch")
        return value

    def authenticate(self, username, password):
        now = time.monotonic()
        self._attempts = {name: recent for name, attempts in self._attempts.items()
                          if (recent := [at for at in attempts if now - at < 60])}
        attempts = self._attempts.setdefault(username, [])
        if len(attempts) >= 5:
            raise ValueError("Login rate limited")
        attempts.append(now)
        value = self.directory()
        actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(value["salt"]), n=16384, r=8, p=1).hex()
        if not (hmac.compare_digest(username, value["username"]) and hmac.compare_digest(actual, value["password_hash"])):
            raise ValueError("Invalid credentials")
        self._attempts.pop(username, None)
        now = int(datetime.now(UTC).timestamp())
        claims = {"sub": value["subject_id"], "iss": ISSUER, "tenant": self.tenant,
                  "iat": now, "exp": now + 3600, "jti": secrets.token_urlsafe(24)}
        encoded = base64.urlsafe_b64encode(json.dumps(claims, sort_keys=True).encode()).decode()
        signature = hmac.new(bytes.fromhex(value["signing_key"]), encoded.encode(), hashlib.sha256).digest()
        return encoded + "." + base64.urlsafe_b64encode(signature).decode()

    def resolve_token(self, token):
        value = self.directory()
        encoded, signature = token.split(".")
        expected = hmac.new(bytes.fromhex(value["signing_key"]), encoded.encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(expected, base64.urlsafe_b64decode(signature)):
            raise ValueError("Invalid signature")
        claims = json.loads(base64.urlsafe_b64decode(encoded))
        now = int(datetime.now(UTC).timestamp())
        if (claims.get("iss") != ISSUER or claims.get("tenant") != self.tenant
                or claims.get("sub") != value["subject_id"] or not claims.get("jti")
                or type(claims.get("iat")) is not int or type(claims.get("exp")) is not int
                or claims["iat"] > now or claims["exp"] <= now or not 0 < claims["exp"] - claims["iat"] <= 3600):
            raise ValueError("Invalid local staff session")
        return IdentityContext(claims["sub"], "local-staff:" + claims["sub"], ISSUER,
                               (IdentityRole.SUPPORT_OFFICER,), "Cán bộ Một cửa — tài khoản local",
                               datetime.fromtimestamp(claims["iat"], UTC), datetime.fromtimestamp(claims["exp"], UTC),
                               tenant_id=self.tenant, session_id=claims["jti"], is_synthetic=False)
