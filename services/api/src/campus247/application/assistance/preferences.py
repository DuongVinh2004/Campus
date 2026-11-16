"""Confirmed account/chat presentation settings and purpose-specific consent."""
from dataclasses import dataclass
from datetime import datetime, timezone
import json

from campus247.agent.prompts.composer import PromptBlock, TrustDomain
from campus247.application.assistance.durable_services import ConfirmedStateService
from campus247.application.assistance.feature_contracts import AssistantPreferences, ChatPreferences
from campus247.application.assistance.state_storage import digest
from campus247.application.document_request.certificates import CertificateError
from campus247.ports.identity import IdentityRole


@dataclass(frozen=True)
class PresentationContext:
    actor_id: str
    tenant: str
    conversation_id: str
    audience: str
    preferences: AssistantPreferences
    version: str

    def block(self, actor_id, conversation_id):
        if (actor_id, conversation_id) != (self.actor_id, self.conversation_id):
            raise ValueError("presentation scope mismatch")
        # This block cannot enter the system channel or change the output schema.
        return PromptBlock(TrustDomain.MEMORY, json.dumps({
            "presentation_preferences": self.preferences.model_dump(mode="json"),
            "constraint": "Style only, subordinate to evidence, safety, schema and authorization."
        }, ensure_ascii=False), "presentation-preferences")


class AssistantPreferenceService(ConfirmedStateService):
    namespaces = frozenset({"assistant_preferences", "chat_preferences", "consent"})

    def __init__(self, *args, notice, **kwargs):
        super().__init__(*args, **kwargs)
        self.notice = notice

    def read(self, actor):
        scope = self.scope(actor)
        record = self.store.get(scope, "assistant_preferences", "account")
        legacy = self.store.get(scope, "preferences", "account") if record is None else None
        value = AssistantPreferences.model_validate(record.payload if record else legacy.payload if legacy else {})
        return {"version": record.version if record else 0, "saved": record is not None,
                "preferences": value.model_dump(mode="json"), "legacy_settings_preserved": legacy is not None,
                "consumer_enabled": self.consented(actor, "OPTIONAL_PERSONALIZATION")}

    def prepare(self, actor, preferences, expected_version, client_id):
        value = AssistantPreferences.model_validate(preferences)
        return self.preview(actor, "assistant_preferences", "account", expected_version,
                            value.model_dump(mode="json"), client_id)

    def prepare_chat(self, actor, conversation_id, preferences, expected_version, client_id, *, enabled=True):
        # Caller must resolve the conversation on the server first. The same
        # check is repeated by the HTTP confirmation route and model consumer.
        audience = self.audience(actor)
        value = ChatPreferences(conversation_id=conversation_id, audience=audience,
                                preferences=AssistantPreferences.model_validate(preferences), enabled=enabled)
        return self.preview(actor, "chat_preferences", conversation_id, expected_version,
                            value.model_dump(mode="json"), client_id)

    @staticmethod
    def audience(actor):
        roles = set(actor.roles)
        if roles == {IdentityRole.STUDENT}:
            return "student"
        if roles == {IdentityRole.SUPPORT_OFFICER}:
            return "staff"
        raise CertificateError(403, "ROLE_CONTEXT_AMBIGUOUS", "Cần một vai trò trợ giúp rõ ràng")

    def consented(self, actor, purpose):
        scope = self.scope(actor)
        if self.notice is None:
            return False
        notice = self.notice()
        record = self.store.get(scope, "consent", purpose)
        return bool(record and record.payload["decision"] == "GRANTED"
                    and record.payload["notice_version"] == notice.version
                    and purpose in notice.purposes and notice.status == "ACTIVE" and notice.effective_at <= datetime.now(timezone.utc))

    def prepare_consent(self, actor, purpose, decision, notice_version, expected_version, client_id):
        if purpose not in {"OPTIONAL_PERSONALIZATION", "QUALITY_FEEDBACK", "CONVERSATION_HISTORY"}:
            raise CertificateError(422, "CONSENT_PURPOSE_INVALID", "Mục đích consent không được hỗ trợ")
        return self.preview(actor, "consent", purpose, expected_version,
            {"purpose": purpose, "decision": decision, "notice_version": notice_version}, client_id)

    def revalidate(self, actor, namespace, key, payload):
        if namespace == "assistant_preferences" and key != "account":
            raise CertificateError(409, "SETTINGS_BINDING_INVALID", "Sai tài khoản settings")
        if namespace == "chat_preferences":
            value = ChatPreferences.model_validate(payload)
            if value.conversation_id != key or value.audience != self.audience(actor):
                raise CertificateError(409, "CHAT_BINDING_INVALID", "Sai ngữ cảnh chat")
        if namespace == "consent":
            if self.notice is None:
                raise CertificateError(503, "CONSENT_NOT_CONFIGURED", "Chưa cấu hình consent consumer")
            notice = self.notice()
            if (key != payload["purpose"] or key not in {"OPTIONAL_PERSONALIZATION", "QUALITY_FEEDBACK", "CONVERSATION_HISTORY"}
                    or key not in notice.purposes
                    or notice.status != "ACTIVE" or notice.effective_at > datetime.now(timezone.utc)
                    or payload["notice_version"] != notice.version):
                raise CertificateError(409, "NOTICE_CHANGED", "Cần đọc và xác nhận notice hiện hành")

    def resolve(self, actor, conversation_id):
        scope = self.scope(actor)
        audience = self.audience(actor)
        account = self.read(actor)
        chat = self.store.get(scope, "chat_preferences", conversation_id)
        enabled = account["consumer_enabled"]
        value = AssistantPreferences.model_validate(account["preferences"] if enabled else {})
        if enabled and chat is not None:
            override = ChatPreferences.model_validate(chat.payload)
            if override.audience != audience:
                raise CertificateError(403, "CHAT_AUDIENCE_CHANGED", "Vai trò của chat đã thay đổi")
            if override.enabled:
                value = override.preferences
        return PresentationContext(actor.subject_id, scope.tenant, conversation_id, audience, value,
            digest({"account": account["version"], "chat": chat.version if chat else 0,
                    "consent": enabled, "preferences": value.model_dump(mode="json")}))

    def consent_page(self, actor, purpose, after_version=0, limit=20):
        if purpose not in {"OPTIONAL_PERSONALIZATION", "QUALITY_FEEDBACK", "CONVERSATION_HISTORY"}:
            raise CertificateError(422, "CONSENT_PURPOSE_INVALID", "Mục đích consent không được hỗ trợ")
        if type(limit) is not int or not 1 <= limit <= 99:
            raise ValueError("bounded consent page required")
        records = self.store.history(self.scope(actor), "consent", purpose, after_version=after_version, limit=limit+1)
        page = records[:limit]
        return {"items": [r.model_dump(mode="json") for r in page], "has_more": len(records) > limit,
                "next_version": page[-1].version if len(records) > limit else None,
                "retention_effect": "no deletion or retention extension"}
