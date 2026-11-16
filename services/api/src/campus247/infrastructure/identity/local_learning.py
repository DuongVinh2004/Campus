"""Explicitly provisioned synthetic learning accounts; no fallback identity or role grants."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from datetime import UTC, datetime
from pathlib import Path

from campus247.domain.shared.values import is_valid_uuid7
from campus247.ports.identity import IdentityContext, IdentityRole

ISSUER = "urn:campus247:issuer:local-learning"


class LocalLearningIdentityAdapter:
    def __init__(self, path: Path, tenant: str):
        self.path, self.tenant = path, tenant
        self._attempts: list[tuple[float, str]] = []

    def directory(self):
        value = json.loads(self.path.read_text(encoding="utf-8"))
        if value.get("schema") != "local-learning-v1" or value.get("tenant") != self.tenant:
            raise ValueError("Learning identity scope mismatch")
        if value.get("issuer") != ISSUER or value.get("university_identity_verified") is not False:
            raise ValueError("Learning identity issuer mismatch")
        key = bytes.fromhex(value["signing_key"])
        if len(key) != 32 or not isinstance(value.get("accounts"), list):
            raise ValueError("Invalid learning identity directory")
        usernames, subjects = set(), set()
        for account in value["accounts"]:
            if (not is_valid_uuid7(account.get("subject_id", ""))
                or account.get("role") not in {"LECTURER", "SYSTEM_ADMIN", "STUDENT"}
                or account.get("is_synthetic") is not True
                or not isinstance(account.get("display_name"), str) or not account["display_name"].strip()
                or not account.get("username") or len(account["username"]) > 100
                or account["username"] in usernames or account["subject_id"] in subjects
                or len(bytes.fromhex(account["salt"])) != 16
                or len(bytes.fromhex(account["password_hash"])) != 64):
                raise ValueError("Invalid learning identity account")
            usernames.add(account["username"])
            subjects.add(account["subject_id"])
        return value

    def public_directory(self):
        return [{"subject_id": a["subject_id"], "display_name": a["display_name"],
                 "roles": [a["role"]], "is_synthetic": True}
                for a in self.directory()["accounts"]]

    def authenticate(self, username, password):
        if not isinstance(username, str) or not isinstance(password, str) or len(username) > 100 or len(password) > 200:
            raise ValueError("Invalid credentials")
        now = time.monotonic()
        self._attempts = [(at, name) for at, name in self._attempts if now - at < 60]
        if len(self._attempts) >= 30 or sum(name == username for _, name in self._attempts) >= 5:
            raise ValueError("Login rate limited")
        self._attempts.append((now, username))
        directory = self.directory()
        account = next((a for a in directory["accounts"] if hmac.compare_digest(a["username"], username)), None)
        salt = bytes.fromhex(account["salt"]) if account else bytes(16)
        actual = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1).hex()
        if account is None or not hmac.compare_digest(actual, account["password_hash"]):
            raise ValueError("Invalid credentials")
        self._attempts = [(at, name) for at, name in self._attempts if name != username]
        timestamp = int(datetime.now(UTC).timestamp())
        claims = {"sub": account["subject_id"], "iss": ISSUER, "tenant": self.tenant,
                  "iat": timestamp, "exp": timestamp + 3600, "jti": secrets.token_urlsafe(24)}
        encoded = base64.urlsafe_b64encode(json.dumps(claims, sort_keys=True).encode()).decode()
        signature = hmac.new(bytes.fromhex(directory["signing_key"]), encoded.encode(), hashlib.sha256).digest()
        return encoded + "." + base64.urlsafe_b64encode(signature).decode()

    def resolve_token(self, token):
        if not isinstance(token, str) or len(token) > 4096:
            raise ValueError("Invalid local learning session")
        directory = self.directory()
        encoded, signature = token.split(".")
        expected = hmac.new(bytes.fromhex(directory["signing_key"]), encoded.encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(expected, base64.urlsafe_b64decode(signature)):
            raise ValueError("Invalid signature")
        claims = json.loads(base64.urlsafe_b64decode(encoded))
        now = int(datetime.now(UTC).timestamp())
        if (claims.get("iss") != ISSUER or claims.get("tenant") != self.tenant or not claims.get("jti")
            or type(claims.get("iat")) is not int or type(claims.get("exp")) is not int
            or claims["iat"] > now or claims["exp"] <= now or not 0 < claims["exp"] - claims["iat"] <= 3600):
            raise ValueError("Invalid local learning claims")
        account = next((a for a in directory["accounts"] if a["subject_id"] == claims.get("sub")), None)
        if account is None:
            raise ValueError("Learning account unavailable")
        return IdentityContext(account["subject_id"], "local-learning:" + account["subject_id"], ISSUER,
            (IdentityRole(account["role"]),), account["display_name"],
            datetime.fromtimestamp(claims["iat"], UTC), datetime.fromtimestamp(claims["exp"], UTC),
            tenant_id=self.tenant, session_id=claims["jti"], is_synthetic=True,
            student_code="SYN-LEARNING-" + account["subject_id"][-8:] if account["role"] == "STUDENT" else None)
