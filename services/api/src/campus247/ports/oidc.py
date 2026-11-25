"""The parts of university sign-in (OpenID Connect) that the HTTP layer needs and that touch no network, file or database.

They live here so presentation code does not import infrastructure. The provider client, the account store and the session
adapter in `infrastructure/identity/oidc*.py` re-export these names, so existing imports keep working.
"""
from __future__ import annotations

import base64
import hashlib
import secrets


class OidcError(Exception):
    """`code` is one of a fixed set, safe to show in a URL or a log line."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def new_pkce() -> tuple[str, str]:
    """(verifier, S256 challenge)."""
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(48)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


def safe_next(value: str | None) -> str:
    """Only a path inside this site: it must start with one slash, never `//`, a backslash, a scheme or a control character."""
    if not value or not value.startswith("/") or value.startswith("//") or "\\" in value or any(ord(c) < 32 for c in value) or len(value) > 300:
        return "/"
    return value
