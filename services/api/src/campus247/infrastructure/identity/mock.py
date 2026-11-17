from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
from typing import Any

from identities import generate_identities
from campus247.ports.identity import AccountState, IdentityContext, IdentityRole

ALLOWED_ENVIRONMENTS = {"local", "development", "test", "testing", "demo-synthetic"}


class SyntheticIdentityAdapter:
    def __init__(self, secret_key: str, environment: str = "local") -> None:
        if environment.lower() == "production" or environment.lower() not in ALLOWED_ENVIRONMENTS:
            raise ValueError(f"Synthetic identity adapter forbidden in environment: {environment}")
        self._secret = secret_key.encode("utf-8")
        self._environment = environment
        data = generate_identities()
        self._users = {u["id"]: u for u in data["records"]["user_identity"]}
        self._profiles = {p["user_id"]: p for p in data["records"]["student_profile"]}
        self._roles = data["records"]["role_binding"]
        self._code_to_uid: dict[str, str] = {
            p["student_code"]: p["user_id"] for p in data["records"]["student_profile"]
        }
        for u in data["records"]["user_identity"]:
            self._code_to_uid[u["id"]] = u["id"]

    def mint_token(self, user_id_or_code: str, ttl_seconds: int = 3600) -> str:
        uid = self._code_to_uid.get(user_id_or_code, user_id_or_code)
        if uid not in self._users:
            raise ValueError(f"User not found in synthetic directory: {user_id_or_code}")
        now = datetime.now(timezone.utc)
        exp = now + timedelta(seconds=ttl_seconds)
        import secrets
        payload = {
            "sub": uid,
            "iat": int(now.timestamp()),
            "exp": int(exp.timestamp()),
            "jti": secrets.token_urlsafe(8),
        }
        payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
        b64_payload = base64.urlsafe_b64encode(payload_bytes).decode("ascii")
        sig = hmac.new(self._secret, b64_payload.encode("ascii"), hashlib.sha256).digest()
        b64_sig = base64.urlsafe_b64encode(sig).decode("ascii")
        return f"{b64_payload}.{b64_sig}"

    def resolve_token(self, token: str) -> IdentityContext:
        parts = token.split(".")
        if len(parts) != 2:
            raise ValueError("Tampered token: invalid format")
        b64_payload, b64_sig = parts
        expected_sig = hmac.new(self._secret, b64_payload.encode("ascii"), hashlib.sha256).digest()
        actual_sig = base64.urlsafe_b64decode(b64_sig.encode("ascii"))
        if not hmac.compare_digest(expected_sig, actual_sig):
            raise ValueError("Invalid signature: signature verification failed")

        payload = json.loads(base64.urlsafe_b64decode(b64_payload.encode("ascii")).decode("utf-8"))
        now_ts = int(datetime.now(timezone.utc).timestamp())
        if payload.get("exp", 0) <= now_ts:
            raise ValueError("Token has expired")

        uid = payload["sub"]
        u = self._users[uid]
        prof = self._profiles.get(uid)
        user_roles = [
            IdentityRole(r["role"]) for r in self._roles if r["user_id"] == uid
        ] or [IdentityRole.STUDENT]

        auth_time = datetime.fromtimestamp(payload["iat"], tz=timezone.utc)
        expires_at = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)

        return IdentityContext(
            subject_id=uid,
            external_subject=f"syn_{uid}",
            issuer="urn:campus247:issuer:synthetic",
            roles=tuple(user_roles),
            display_name=u["display_name"],
            email=u.get("primary_email"),
            auth_time=auth_time,
            expires_at=expires_at,
            account_state=AccountState(u["status"]),
            is_synthetic=True,
            student_code=prof["student_code"] if prof else None,
            faculty_code=prof["faculty_code"] if prof else None,
        )
