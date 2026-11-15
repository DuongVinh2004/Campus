from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
import base64
import hashlib
import hmac
import json
import secrets
import threading
from typing import Any

from campus247.agent.state import AgentState, ConfirmationContext, Terminal, ToolPhase
from campus247.domain.action.preview import ActionPreviewValue
from campus247.agent.tools.preview_store import InMemoryPreviewStore, SqlitePreviewStore, canonical
from campus247.domain.shared.values import generate_uuid7


class ConfirmationBindingError(Exception):
    pass


# One process: a random key and in-memory previews. Several processes: configure_shared_state() gives every process the
# same signing key and one preview store, so a preview made in one process is confirmed, and used once, in any.
_CONFIRMATION_SIGNING_KEY = secrets.token_bytes(32)
_CONTRACT_VERSION = "1.0.0"
_POLICY_VERSION = "policy-v1"
_STORE: InMemoryPreviewStore | SqlitePreviewStore = InMemoryPreviewStore()
_CONSUMED_LOCK = threading.Lock()


def configure_shared_state(database_path, signing_key: bytes) -> None:
    """Share previews, used-marks and the confirmation signing key between API processes."""
    global _STORE, _CONFIRMATION_SIGNING_KEY
    if not isinstance(signing_key, (bytes, bytearray)) or len(signing_key) < 32:
        raise ValueError("a shared signing key of at least 32 bytes is required")
    _STORE = SqlitePreviewStore(database_path)
    _CONFIRMATION_SIGNING_KEY = bytes(signing_key)


@dataclass(frozen=True)
class ConfirmationBindingResult:
    phase: ToolPhase
    is_authorized: bool
    preview_id: str
    error: str | None = None


@dataclass(frozen=True)
class ConfirmationBindingState:
    preview_id: str
    actor_id: str
    tool_id: str
    arguments_hash: str
    is_consumed: bool = False
    canonical_arguments: str = ""
    authorization_scope: str = "write"
    policy_version: str = _POLICY_VERSION
    contract_version: str = _CONTRACT_VERSION
    expires_at: str = ""
    risk_level: str = "HIGH"

    def to_agent_context(self) -> ConfirmationContext:
        return ConfirmationContext(
            preview_id=self.preview_id,
            tool_id=self.tool_id,
            canonical_arguments=self.canonical_arguments,
            payload_hash=self.arguments_hash,
            actor_id=self.actor_id,
            authorization_scope=self.authorization_scope,
            contract_version=self.contract_version,
            policy_version=self.policy_version,
            expires_at=self.expires_at,
            risk_level=self.risk_level,
        )

    def to_failed_state(self, state: AgentState, reason: str) -> AgentState:
        return replace(
            state,
            tool_phase=ToolPhase.FAILED,
            terminal=Terminal.SAFE_FAILURE,
            errors=state.errors + (reason,),
        )


def _normalize_and_hash(payload: dict[str, Any]) -> tuple[str, str]:
    normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    h = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return normalized, f"sha256:{h}"


class WriteToolFlowBroker:
    """Manages write-tool preview generation and human confirmation interrupt validation."""

    def __init__(
        self,
        expiry_minutes: int = 10,
        contract_version: str = _CONTRACT_VERSION,
        policy_version: str = _POLICY_VERSION,
    ) -> None:
        self._expiry_minutes = expiry_minutes
        self._contract_version = contract_version
        self._policy_version = policy_version
        self._consumed_previews: set[str] = set()
        self._preview_metadata: dict[str, dict[str, str]] = {}
        self._lock = threading.Lock()

    def build_preview(
        self,
        actor_id: str,
        tool_id: str,
        arguments: dict[str, Any],
        conversation_id: str | None = None,
    ) -> ActionPreviewValue:
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=self._expiry_minutes)

        normalized_json, payload_hash = _normalize_and_hash(arguments)
        confirmation_secret_hash = hashlib.sha256(secrets.token_bytes(32)).hexdigest()
        preview_id = generate_uuid7()

        metadata = {
            "conversation_id": conversation_id or preview_id,
            "contract_version": self._contract_version,
            "policy_version": self._policy_version,
            "nonce": hashlib.sha256(f"nonce:{payload_hash}".encode("utf-8")).hexdigest()[:32],
            "idempotency_key_ref": f"idem-{payload_hash[:24]}",
        }
        self._preview_metadata[preview_id] = metadata
        _STORE.put_metadata(preview_id, metadata)

        preview = ActionPreviewValue(
            id=preview_id,
            actor_user_id=actor_id,
            session_id=metadata.get("session_id", "none"),
            conversation_id=metadata.get("conversation_id", "none"),
            action_type=tool_id,
            tool_version=metadata.get("tool_version", "1.0"),
            policy_version=metadata.get("policy_version", "1.0"),
            normalized_payload=normalized_json,
            payload_hash=payload_hash,
            policy_decision="ALLOW",
            confirmation_secret_hash=confirmation_secret_hash,
            created_at=now,
            expires_at=expires_at,
        )
        _STORE.put_binding(preview.id, canonical(self._preview_fingerprint(preview)))
        return preview

    @staticmethod
    def _preview_fingerprint(preview: ActionPreviewValue) -> tuple[Any, ...]:
        return (
            preview.id,
            preview.actor_user_id,
            preview.action_type,
            preview.normalized_payload,
            preview.payload_hash,
            preview.policy_decision,
            preview.confirmation_secret_hash,
            preview.created_at,
            preview.expires_at,
        )

    def _assert_immutable_preview(self, preview: ActionPreviewValue) -> None:
        expected = _STORE.get_binding(preview.id)
        if expected is None or expected != canonical(self._preview_fingerprint(preview)):
            raise ConfirmationBindingError("Preview binding is invalid")

    def _metadata_for(self, preview: ActionPreviewValue) -> dict[str, str]:
        metadata = self._preview_metadata.get(preview.id) or _STORE.get_metadata(preview.id)
        if metadata is None:
            raise ConfirmationBindingError("Preview binding is invalid")
        self._preview_metadata[preview.id] = metadata
        return metadata

    def _confirmation_token(self, preview: ActionPreviewValue) -> str:
        self._assert_immutable_preview(preview)
        metadata = self._metadata_for(preview)
        claims = {
            "preview_id": preview.id,
            "actor_ref": preview.actor_user_id,
            "conversation_id": metadata["conversation_id"],
            "tool_id": preview.action_type,
            "contract_version": metadata["contract_version"],
            "payload_hash": preview.payload_hash,
            "policy_version": metadata["policy_version"],
            "issued_at": preview.created_at.isoformat(),
            "expires_at": preview.expires_at.isoformat(),
            "nonce": metadata["nonce"],
            "consumed": False,
        }
        encoded = base64.urlsafe_b64encode(
            json.dumps(claims, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).decode("ascii").rstrip("=")
        signature = hmac.new(_CONFIRMATION_SIGNING_KEY, encoded.encode("ascii"), hashlib.sha256).hexdigest()
        return f"{encoded}.{signature}"

    def create_confirmation_interrupt(self, preview: ActionPreviewValue) -> dict[str, Any]:
        self._assert_immutable_preview(preview)
        metadata = self._metadata_for(preview)
        payload = json.loads(preview.normalized_payload)
        summary = []
        for key, value in list(payload.items())[:20]:
            normalized_key = str(key).lower()
            redacted = any(marker in normalized_key for marker in ("id", "email", "phone", "token", "secret"))
            summary.append(
                {
                    "label_key": normalized_key[:100],
                    "display_value": "[REDACTED]" if redacted else json.dumps(value, ensure_ascii=False)[:500],
                    "redacted": redacted,
                }
            )
        return {
            "phase": ToolPhase.AWAITING_CONFIRMATION,
            "preview_id": preview.id,
            "tool_id": preview.action_type,
            "contract_version": metadata["contract_version"],
            "action_type": preview.action_type,
            "actor_id": preview.actor_user_id,
            "conversation_id": metadata["conversation_id"],
            "payload_hash": preview.payload_hash,
            "policy_version": metadata["policy_version"],
            "nonce": metadata["nonce"],
            "idempotency_key_ref": metadata["idempotency_key_ref"],
            "authorization_scope": "write",
            "risk_level": "HIGH",
            "summary": summary or [{"label_key": "tool", "display_value": preview.action_type}],
            "impact_message_key": "tool.write.confirm",
            "recipient_label": "Campus 24/7",
            "confirmation_token": self._confirmation_token(preview),
            "expires_at": preview.expires_at.isoformat(),
        }

    def revalidate(
        self,
        preview: ActionPreviewValue,
        arguments: dict[str, Any],
        at_time: datetime | None = None,
    ) -> bool:
        check_time = at_time or datetime.now(timezone.utc)
        try:
            self._assert_immutable_preview(preview)
        except ConfirmationBindingError:
            return False
        if preview.is_expired(check_time) or preview.is_consumed() or preview.is_cancelled():
            return False
        if _STORE.is_consumed(preview.id):
            return False

        _, current_hash = _normalize_and_hash(arguments)
        if current_hash != preview.payload_hash:
            return False

        return True

    def _verify_confirmation_token(
        self,
        preview: ActionPreviewValue,
        token: str,
        confirming_actor_id: str,
        at_time: datetime,
    ) -> None:
        try:
            encoded, signature = token.split(".", 1)
            expected = hmac.new(_CONFIRMATION_SIGNING_KEY, encoded.encode("ascii"), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature, expected):
                raise ValueError
            padded = encoded + "=" * (-len(encoded) % 4)
            claims = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
            metadata = self._metadata_for(preview)
            expected_claims = {
                "preview_id": preview.id,
                "actor_ref": confirming_actor_id,
                "conversation_id": metadata["conversation_id"],
                "tool_id": preview.action_type,
                "contract_version": metadata["contract_version"],
                "payload_hash": preview.payload_hash,
                "policy_version": metadata["policy_version"],
                "nonce": metadata["nonce"],
                "consumed": False,
            }
            if any(claims.get(key) != value for key, value in expected_claims.items()):
                raise ValueError
            if datetime.fromisoformat(claims["expires_at"]) <= at_time:
                raise ValueError
        except Exception:
            raise ConfirmationBindingError("Confirmation token invalid") from None

    def resume_with_confirmation(
        self,
        preview: ActionPreviewValue,
        confirming_actor_id: str,
        arguments: dict[str, Any],
        at_time: datetime | None = None,
        confirmation_token: str | None = None,
        conversation_id: str | None = None,
        contract_version: str | None = None,
        policy_version: str | None = None,
    ) -> ConfirmationBindingResult:
        check_time = at_time or datetime.now(timezone.utc)

        with self._lock, _CONSUMED_LOCK:
            self._assert_immutable_preview(preview)
            # Replay protection
            if _STORE.is_consumed(preview.id) or preview.id in self._consumed_previews:
                raise ConfirmationBindingError("Preview has already been consumed (replay attempt rejected)")

            # Expiry check
            if preview.is_expired(check_time):
                raise ConfirmationBindingError("Confirmation window expired")

            metadata = self._metadata_for(preview)
            if conversation_id is not None and conversation_id != metadata["conversation_id"]:
                raise ConfirmationBindingError("Confirmation context drift detected")
            if contract_version is not None and contract_version != metadata["contract_version"]:
                raise ConfirmationBindingError("Confirmation contract version is stale")
            if policy_version is not None and policy_version != metadata["policy_version"]:
                raise ConfirmationBindingError("Confirmation policy version is stale")

            if confirmation_token is not None:
                self._verify_confirmation_token(preview, confirmation_token, confirming_actor_id, check_time)

            # Actor binding check: only the exact authorized actor can confirm
            if confirming_actor_id != preview.actor_user_id:
                raise ConfirmationBindingError(
                    f"Actor mismatch: preview actor '{preview.actor_user_id}' != confirming actor '{confirming_actor_id}'"
                )

            # Argument drift check: arguments cannot be modified between preview and confirm
            _, current_hash = _normalize_and_hash(arguments)
            if current_hash != preview.payload_hash:
                raise ConfirmationBindingError("Payload drift detected: arguments modified after preview")

            # Mark consumed atomically: with a shared store exactly one process (or thread) wins this insert.
            if not _STORE.consume(preview.id):
                raise ConfirmationBindingError("Preview has already been consumed (replay attempt rejected)")
            self._consumed_previews.add(preview.id)

        return ConfirmationBindingResult(
            phase=ToolPhase.CONFIRMED,
            is_authorized=True,
            preview_id=preview.id,
        )
