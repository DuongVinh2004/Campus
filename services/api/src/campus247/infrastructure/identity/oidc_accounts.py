"""From a verified ID token to a Campus 24/7 account: which person, which roles, and the one-time login attempts.

Rules that matter:
  * An account exists only if it was provisioned (a row in oidc_subjects, an entry in `privileged_subjects`, or JIT provisioning was
    turned on by the owner). The default is to refuse an unknown person.
  * STUDENT and LECTURER may come from the provider's group claim through `role_map`. SYSTEM_ADMIN, KNOWLEDGE_ADMIN, SUPPORT_OFFICER and
    KNOWLEDGE_CONTRIBUTOR never do: they are granted only to (issuer, subject) pairs the owner lists in `privileged_subjects`.
  * A STUDENT needs a student code that matches the configured pattern.
"""
from __future__ import annotations

import hmac
import re
import secrets
import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from campus247.domain.shared.values import generate_uuid7
from campus247.infrastructure.identity.oidc import OidcConfig, OidcError
from campus247.ports.identity import IdentityRole

ATTEMPT_TTL = timedelta(minutes=10)
FROM_PROVIDER = {IdentityRole.STUDENT, IdentityRole.LECTURER}
PRIVILEGED = {IdentityRole.SYSTEM_ADMIN, IdentityRole.KNOWLEDGE_ADMIN, IdentityRole.SUPPORT_OFFICER, IdentityRole.KNOWLEDGE_CONTRIBUTOR}


def validate_config(config: OidcConfig) -> None:
    """Refuse a configuration that would let the provider grant a privileged role."""
    for claim_value, role_name in config.role_map.items():
        try:
            role = IdentityRole(role_name)
        except ValueError:
            raise OidcError("CONFIG_ROLE_UNKNOWN") from None
        if role not in FROM_PROVIDER:
            raise OidcError("CONFIG_ROLE_NOT_ALLOWED_FROM_PROVIDER")
    for entry in config.privileged_subjects:
        try:
            roles = [IdentityRole(name) for name in entry.get("roles", ())]
        except ValueError:
            raise OidcError("CONFIG_ROLE_UNKNOWN") from None
        if not entry.get("sub") or not roles or any(role not in PRIVILEGED | FROM_PROVIDER for role in roles):
            raise OidcError("CONFIG_PRIVILEGED_ENTRY_INVALID")
    try:
        re.compile(config.student_code_pattern)
    except re.error:
        raise OidcError("CONFIG_PATTERN_INVALID") from None


def safe_next(value: str | None) -> str:
    """Only a path inside this site: it must start with one slash, never `//`, a backslash, a scheme or a control character."""
    if not value or not value.startswith("/") or value.startswith("//") or "\\" in value or any(ord(c) < 32 for c in value) or len(value) > 300:
        return "/"
    return value


def _now_text(now: datetime) -> str:
    return now.astimezone(UTC).isoformat().replace("+00:00", "Z")


class OidcAccountStore:
    """SQLite store for provisioned accounts and pending login attempts (its own file, so no migration is needed)."""

    def __init__(self, path: Path) -> None:
        self.path = path
        with closing(self._connect()) as db, db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS oidc_subjects(issuer TEXT NOT NULL, sub TEXT NOT NULL, subject_id TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL, last_login_at TEXT, disabled INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(issuer, sub));
                CREATE TABLE IF NOT EXISTS oidc_login_attempts(id TEXT PRIMARY KEY, state TEXT NOT NULL, nonce TEXT NOT NULL, verifier TEXT NOT NULL,
                    next_path TEXT NOT NULL, created_at TEXT NOT NULL, expires_at TEXT NOT NULL, used_at TEXT);""")

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=10)

    # ------------------------------------------------------------------ login attempts
    def start_attempt(self, *, verifier: str, next_path: str | None, now: datetime) -> dict[str, str]:
        attempt = {"id": secrets.token_urlsafe(24), "state": secrets.token_urlsafe(24), "nonce": secrets.token_urlsafe(24)}
        with closing(self._connect()) as db, db:
            db.execute("DELETE FROM oidc_login_attempts WHERE expires_at < ?", (_now_text(now - timedelta(hours=1)),))  # only expired rows of this table
            db.execute("INSERT INTO oidc_login_attempts(id, state, nonce, verifier, next_path, created_at, expires_at) VALUES (?,?,?,?,?,?,?)",
                       (attempt["id"], attempt["state"], attempt["nonce"], verifier, safe_next(next_path), _now_text(now), _now_text(now + ATTEMPT_TTL)))
        return attempt

    def finish_attempt(self, attempt_id: str, state: str, *, now: datetime) -> dict[str, str]:
        """Use the attempt once. Wrong state, unknown id, expired or already used: all the same refusal."""
        with closing(self._connect()) as db, db:
            row = db.execute("SELECT state, nonce, verifier, next_path, expires_at, used_at FROM oidc_login_attempts WHERE id = ?", (attempt_id,)).fetchone()
            if row is None or row[5] is not None or row[4] < _now_text(now) or not hmac.compare_digest(row[0], state):
                raise OidcError("LOGIN_ATTEMPT_INVALID")
            claimed = db.execute("UPDATE oidc_login_attempts SET used_at = ? WHERE id = ? AND used_at IS NULL", (_now_text(now), attempt_id)).rowcount
            if claimed != 1:
                raise OidcError("LOGIN_ATTEMPT_INVALID")  # lost a race with another request using the same attempt
        return {"nonce": row[1], "verifier": row[2], "next_path": row[3]}

    # ------------------------------------------------------------------ accounts
    def lookup(self, issuer: str, sub: str) -> dict[str, Any] | None:
        with closing(self._connect()) as db:
            row = db.execute("SELECT subject_id, disabled FROM oidc_subjects WHERE issuer = ? AND sub = ?", (issuer, sub)).fetchone()
        return {"subject_id": row[0], "disabled": bool(row[1])} if row else None

    def provision(self, issuer: str, sub: str, *, now: datetime) -> str:
        subject_id = generate_uuid7()
        with closing(self._connect()) as db, db:
            db.execute("INSERT OR IGNORE INTO oidc_subjects(issuer, sub, subject_id, created_at) VALUES (?,?,?,?)", (issuer, sub, subject_id, _now_text(now)))
            return db.execute("SELECT subject_id FROM oidc_subjects WHERE issuer = ? AND sub = ?", (issuer, sub)).fetchone()[0]

    def touch(self, issuer: str, sub: str, *, now: datetime) -> None:
        with closing(self._connect()) as db, db:
            db.execute("UPDATE oidc_subjects SET last_login_at = ? WHERE issuer = ? AND sub = ?", (_now_text(now), issuer, sub))

    def set_disabled(self, issuer: str, sub: str, disabled: bool) -> None:
        with closing(self._connect()) as db, db:
            db.execute("UPDATE oidc_subjects SET disabled = ? WHERE issuer = ? AND sub = ?", (int(disabled), issuer, sub))


def _claim_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def resolve_account(config: OidcConfig, store: OidcAccountStore, claims: dict[str, Any], *, now: datetime) -> dict[str, Any]:
    """The account a verified token stands for: subject id, roles, display name, student code. Raises OidcError with a fixed code otherwise."""
    issuer, sub = config.issuer, claims["sub"]
    listed = [entry for entry in config.privileged_subjects if entry.get("sub") == sub and entry.get("issuer", issuer) == issuer]
    existing = store.lookup(issuer, sub)
    if existing is not None and existing["disabled"]:
        raise OidcError("ACCOUNT_DISABLED")
    if existing is None and not listed and not config.jit_provisioning:
        raise OidcError("ACCOUNT_NOT_PROVISIONED")

    roles: list[IdentityRole] = []
    for value in _claim_list(claims.get(config.claims.get("roles", "groups"))):
        mapped = config.role_map.get(value)
        if mapped and IdentityRole(mapped) not in roles:
            roles.append(IdentityRole(mapped))
    for entry in listed:
        for name in entry["roles"]:
            if IdentityRole(name) not in roles:
                roles.append(IdentityRole(name))
    if not roles:
        raise OidcError("ROLE_NOT_MAPPED")

    student_code = None
    if IdentityRole.STUDENT in roles:
        raw = claims.get(config.claims.get("student_code", "student_id"))
        if not isinstance(raw, str) or not re.fullmatch(config.student_code_pattern, raw):
            raise OidcError("STUDENT_CODE_INVALID")
        student_code = raw

    subject_id = existing["subject_id"] if existing else store.provision(issuer, sub, now=now)
    store.touch(issuer, sub, now=now)
    display = claims.get(config.claims.get("display_name", "name"))
    return {"subject_id": subject_id, "roles": tuple(roles), "student_code": student_code, "issuer": issuer, "external_subject": sub,
            "display_name": display.strip()[:120] if isinstance(display, str) and display.strip() else "Người dùng"}
