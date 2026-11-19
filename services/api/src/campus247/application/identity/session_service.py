from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from typing import Any, Protocol


class RevocationStoreError(Exception):
    """Raised when session revocation fails in store."""
    pass


class RevocationStore(Protocol):
    def revoke(self, key: str) -> None:
        ...

    def is_revoked(self, key: str) -> bool:
        ...


class InMemoryRevocationStore:
    def __init__(self) -> None:
        self._revoked: set[str] = set()

    def revoke(self, key: str) -> None:
        self._revoked.add(key)

    def is_revoked(self, key: str) -> bool:
        return key in self._revoked

    def clear(self) -> None:
        self._revoked.clear()


class SessionService:
    def __init__(self, store: RevocationStore | None = None) -> None:
        self._store = store if store is not None else InMemoryRevocationStore()
        self._audit_events: list[dict[str, Any]] = []

    @staticmethod
    def hash_token(token: str) -> str:
        """Derive a deterministic SHA-256 safe identifier from a token or secret."""
        return hashlib.sha256(token.strip().encode("utf-8")).hexdigest()

    def is_revoked(self, token: str) -> bool:
        """Check if token or its hash has been marked as revoked."""
        if not token:
            return True
        safe_hash = self.hash_token(token)
        return self._store.is_revoked(safe_hash) or self._store.is_revoked(token)

    def revoke(self, token_or_session_id: str) -> None:
        """RevocationStore protocol compliance."""
        self.revoke_session(token_or_session_id)

    def revoke_session(
        self,
        token: str,
        reason: str = "logout",
        actor_id: str | None = None,
    ) -> dict[str, Any]:
        """Idempotently revoke a session/token, persist to store, and emit safe audit record."""
        if not token or not token.strip():
            raise ValueError("Token or session ID is required for revocation")

        safe_hash = self.hash_token(token)
        already_revoked = self._store.is_revoked(safe_hash)

        if not already_revoked:
            try:
                if callable(getattr(self._store,"record_revocation",None)):
                    self._store.record_revocation(safe_hash,reason=reason,actor_id=actor_id)
                else:
                    self._store.revoke(safe_hash)
            except Exception as exc:
                raise RevocationStoreError(f"Failed to record session revocation: {exc}") from exc

        # Emit safe audit event with NO raw secret or token
        audit_event = {
            "safe_id": safe_hash[:16],
            "reason": reason,
            "actor_id": actor_id or "anonymous",
            "outcome": "revoked",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._audit_events.append(audit_event)

        return {
            "status": "revoked",
            "idempotent": already_revoked,
            "safe_id": safe_hash[:16],
        }

    def get_audit_events(self) -> list[dict[str, Any]]:
        return list(self._audit_events)

    def clear(self) -> None:
        if hasattr(self._store, "clear"):
            self._store.clear()
        self._audit_events.clear()


_GLOBAL_SESSION_SERVICE: SessionService | None = None


def get_session_service() -> SessionService:
    global _GLOBAL_SESSION_SERVICE
    if _GLOBAL_SESSION_SERVICE is None:
        _GLOBAL_SESSION_SERVICE = SessionService()
    return _GLOBAL_SESSION_SERVICE
