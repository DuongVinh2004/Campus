"""Password-authenticated simulated campus accounts (students and support officers) from one directory file.

The single-account student and staff files stay as they are; this directory adds many simulated people for the
local demo semester. Accounts are invented (``simulated`` is required) and never HUCE SSO identities. Every account
has its own scrypt salt and hash; one signing key per file signs the sessions, and the role always comes from the
file, never from the token.
"""
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

ISSUER = "urn:campus247:issuer:local-directory"
SCHEMA = "local-campus-directory-v1"
_ROLES = {"STUDENT": IdentityRole.STUDENT, "SUPPORT_OFFICER": IdentityRole.SUPPORT_OFFICER}


class LocalDirectoryIdentityAdapter:
    def __init__(self, path: Path, tenant: str):
        self.path, self.tenant = path, tenant
        self._attempts: list[tuple[float, str]] = []
        self._cache: tuple[float, dict] | None = None

    def directory(self) -> dict:
        stamp = self.path.stat().st_mtime_ns
        if self._cache is not None and self._cache[0] == stamp:
            return self._cache[1]
        value = json.loads(self.path.read_text(encoding="utf-8"))
        if (value.get("schema") != SCHEMA or value.get("tenant") != self.tenant or value.get("issuer") != ISSUER
                or value.get("university_identity_verified") is not False or value.get("simulated") is not True):
            raise ValueError("Local directory scope mismatch")
        if len(bytes.fromhex(value["signing_key"])) != 32 or not isinstance(value.get("accounts"), list):
            raise ValueError("Invalid local directory")
        usernames, subjects = set(), set()
        for account in value["accounts"]:
            role = account.get("role")
            code_ok = (str(account.get("student_code", "")).startswith("SIM-") if role == "STUDENT"
                       else str(account.get("staff_code", "")).startswith("SIM-"))
            if (role not in _ROLES or not code_ok or not is_valid_uuid7(account.get("subject_id", ""))
                    or not isinstance(account.get("display_name"), str) or not account["display_name"].strip()
                    or not isinstance(account.get("username"), str) or not 0 < len(account["username"]) <= 100
                    or account["username"] in usernames or account["subject_id"] in subjects
                    or len(bytes.fromhex(account["salt"])) != 16 or len(bytes.fromhex(account["password_hash"])) != 64):
                raise ValueError("Invalid local directory account")
            usernames.add(account["username"])
            subjects.add(account["subject_id"])
        self._cache = (stamp, value)
        return value

    def usernames(self) -> set[str]:
        return {a["username"] for a in self.directory()["accounts"]}

    def public_directory(self, role: str | None = None) -> list[dict]:
        return [{"subject_id": a["subject_id"], "display_name": a["display_name"], "roles": [a["role"]],
                 "is_synthetic": False}
                for a in self.directory()["accounts"] if role is None or a["role"] == role]

    def authenticate(self, username, password):
        if not isinstance(username, str) or not isinstance(password, str) or len(username) > 100 or len(password) > 200:
            raise ValueError("Invalid credentials")
        now = time.monotonic()
        self._attempts = [(at, name) for at, name in self._attempts if now - at < 60]
        if sum(name == username for _, name in self._attempts) >= 5:
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
            raise ValueError("Invalid local directory session")
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
            raise ValueError("Invalid local directory session")
        account = next((a for a in directory["accounts"] if a["subject_id"] == claims.get("sub")), None)
        if account is None:
            raise ValueError("Local directory account unavailable")
        student = account["role"] == "STUDENT"
        # No faculty claim: the public knowledge scope of this local tenant is resolved like the existing local student
        # (simulated faculty codes would otherwise narrow retrieval to nothing). The faculty stays in the directory file.
        return IdentityContext(account["subject_id"], "local-directory:" + account["subject_id"], ISSUER,
                               (_ROLES[account["role"]],), account["display_name"],
                               datetime.fromtimestamp(claims["iat"], UTC), datetime.fromtimestamp(claims["exp"], UTC),
                               tenant_id=self.tenant, session_id=claims["jti"], is_synthetic=False,
                               student_code=account["student_code"] if student else None)
