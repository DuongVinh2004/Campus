"""Resolve stored evidence after ownership and current trusted authorization."""
import hashlib
import re
from datetime import datetime, timezone

from campus247.application.audit.writer import AuditWriter
from campus247.application.authorization.concealment import ResourceNotFoundError
from campus247.application.conversation.messages import ConversationMessageService
from campus247.application.conversation.read import final_payload
from campus247.application.retrieval.context import RetrievalContextFactory
from campus247.domain.shared.values import is_valid_uuid7
from campus247.ports.citation_source import CitationSourceExcerpt, CitationSourceReader
from campus247.ports.identity import IdentityContext


class CitationSourceUnavailable(RuntimeError):
    """Safe dependency failure; no storage or identity details cross transport."""


class CitationSourceService:
    def __init__(self, *, conversations: ConversationMessageService,
                 context_factory: RetrievalContextFactory | None,
                 reader: CitationSourceReader | None, audit_writer: AuditWriter,
                 allow_simulation: bool = False):
        self._conversations, self._factory, self._reader = conversations, context_factory, reader
        self._audit, self._simulation = audit_writer, allow_simulation

    async def read(self, identity: IdentityContext, conversation_id: str, message_id: str,
                   citation_id: str, *, trace_id: str, request_id: str) -> dict:
        outcome, reason = "DENIED", "NOT_ACCESSIBLE"
        try:
            if not all(is_valid_uuid7(value) for value in (conversation_id, message_id, citation_id)):
                raise ResourceNotFoundError()
            if self._factory is None or self._reader is None:
                raise CitationSourceUnavailable()
            now = datetime.now(timezone.utc)
            conv = await self._conversations.get_conversation(conversation_id)
            if (conv is None or conv.owner_user_id != identity.subject_id
                    or conv.retention_expires_at <= now):
                raise ResourceNotFoundError()
            context = self._factory.create(identity, effective_at=now, locale="vi-VN",
                trace_id=trace_id, allow_simulation=self._simulation)
            # Page and authorize before reading any message content.
            cursor = None
            message = None
            for _ in range(20):
                page, cursor, _ = await self._conversations.list_owned_page(
                    identity.subject_id, conversation_id, cursor=cursor, limit=100)
                message = next((item for item in page if item.id == message_id), None)
                if message is not None or cursor is None:
                    break
            if message is None or message.conversation_id != conversation_id:
                raise ResourceNotFoundError()
            final = final_payload(message)
            if final is None or final["response_class"] not in {"grounded_answer", "partial_answer"}:
                raise ResourceNotFoundError()
            citation = next((item["citation"] for item in final["citations"]
                if item["citation"]["citation_id"] == citation_id), None)
            if citation is None:
                raise ResourceNotFoundError()
            source = await self._reader.read(citation["source_id"], citation["document_version_id"],
                citation["chunk_id"], context=context)
            if source is None:
                raise ResourceNotFoundError()
            self._validate(source, citation, now)
            result = {"conversation_id": conversation_id, "message_id": message_id,
                "citation": citation, "issuer": source.issuer,
                "effective_from": self._instant(source.effective_from),
                "effective_until": self._instant(source.effective_until) if source.effective_until else None,
                "content_text": source.content_text, "content_sha256": source.content_sha256,
                "representation": "CITED_CHUNK"}
            if source.applicability_note is not None:
                if not isinstance(source.applicability_note, str) or not 1 <= len(source.applicability_note) <= 1000:
                    raise CitationSourceUnavailable()
                result["applicability_note"] = source.applicability_note
            outcome, reason = "ALLOWED", "CURRENT_ELIGIBLE_CITATION"
            return result
        except ResourceNotFoundError:
            raise
        except Exception:
            outcome, reason = "FAILED", "SOURCE_READ_UNAVAILABLE"
            raise CitationSourceUnavailable() from None
        finally:
            self._audit.record_event(actor_type="USER", actor_id=identity.subject_id,
                action_code="READ_CITATION_SOURCE", resource_type="CITATION", resource_id=None,
                outcome=outcome, reason_code=reason, correlation_id=trace_id, request_id=request_id)

    @staticmethod
    def _instant(value: datetime) -> str:
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _validate(source: CitationSourceExcerpt, citation: dict, now: datetime) -> None:
        if not isinstance(source, CitationSourceExcerpt):
            raise CitationSourceUnavailable()
        binding = {"source_id": source.source_id, "document_version_id": source.document_version_id,
            "chunk_id": source.chunk_id, "source_title": source.title,
            "canonical_uri": source.canonical_uri, "version_label": source.version_label,
            "source_status": source.source_status, "locator": source.locator}
        locator = {key: value for key, value in citation["locator"].items() if value is not None}
        if any(citation[key] != value for key, value in binding.items() if key != "locator") or locator != source.locator:
            raise CitationSourceUnavailable()
        if (source.source_status not in {"CURRENT", "SYNTHETIC"}
                or not 1 <= len(source.content_text) <= 20000
                or not 1 <= len(source.issuer) <= 300
                or re.fullmatch(r"[0-9a-f]{64}", source.content_sha256) is None
                or hashlib.sha256(source.content_text.encode()).hexdigest() != source.content_sha256
                or citation.get("evidence_sha256") not in (None, source.content_sha256)
                or not citation["quote"] or not (
                    citation["quote"] in source.content_text
                    if citation.get("unit_id") and citation.get("evidence_sha256") == source.content_sha256
                    else source.content_text.startswith(citation["quote"]))
                or source.effective_from.tzinfo is None or source.effective_from > now
                or (source.effective_until is not None and
                    (source.effective_until.tzinfo is None or source.effective_until <= now))):
            raise CitationSourceUnavailable()
