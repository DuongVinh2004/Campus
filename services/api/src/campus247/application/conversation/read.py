"""Public message projection from persisted immutable fields, shared by GET/SSE."""
import json
import re
from campus247.application.conversation.messages import MessageRecord, SenderType
from campus247.application.conversation.stream_result import ApiCitation
from campus247.domain.shared.values import is_valid_uuid7


class StoredMessageError(ValueError):
    """Invalid stored semantics cannot be presented as a verified final result."""


def final_payload(message: MessageRecord) -> dict | None:
    if message.sender_type != SenderType.ASSISTANT or message.redacted_at is not None:
        return None
    if message.finish_status is None and message.response_class is None:
        return None
    classes = {
        "answered": {"grounded_answer", "partial_answer", "tool_result"},
        "abstained": {"safe_refusal", "clarification_request", "system_error"},
        "completed": {"tool_result", "action_preview", "action_result"},
        "cancelled": {"safe_refusal"}, "handed_over": {"handover_notice"},
    }
    if (not is_valid_uuid7(message.id) or not is_valid_uuid7(message.conversation_id)
            or message.agent_run_id is not None and not is_valid_uuid7(message.agent_run_id)
            or message.response_class not in classes.get(message.finish_status, set())
            or not message.content_redacted.strip() or len(message.content_redacted) > 20000
            or len(message.citations) > 20
            or (message.finish_status in {"abstained", "cancelled"} and message.citations)
            or (message.response_class in {"grounded_answer", "partial_answer"} and not message.citations)):
        raise StoredMessageError("Invalid stored final result")
    try:
        mappings = [item.to_dict() for item in message.citations]
        local_ids = [item["turn_citation_id"] for item in mappings]
        durable_ids = [item["citation"]["citation_id"] for item in mappings]
        if (len(set(local_ids)) != len(local_ids) or len(set(durable_ids)) != len(durable_ids)
                or any(re.fullmatch(r"CIT-[0-9]{3,}", item) is None for item in local_ids)):
            raise ValueError("Invalid citation identity")
        for item in mappings:
            citation = ApiCitation.model_validate(item["citation"])
            locator = citation.locator.model_dump(exclude_none=True)
            if not locator or (citation.locator.page_end is not None and
                    (citation.locator.page_start is None or citation.locator.page_end < citation.locator.page_start)):
                raise ValueError("Invalid citation locator")
    except (ValueError, TypeError, KeyError):
        raise StoredMessageError("Invalid stored final citations") from None
    return {"message_id": message.id, "conversation_id": message.conversation_id,
        "status": message.finish_status, "response_class": message.response_class,
        "content": message.content_redacted, "citations": mappings,
        **({"run_id": message.agent_run_id} if message.agent_run_id else {})}


def public_message(message: MessageRecord) -> dict:
    final = final_payload(message)
    return {"id": message.id, "conversation_id": message.conversation_id,
        "sequence_no": message.sequence_no, "sender_type": str(message.sender_type),
        "content": message.content_redacted, "content_format": str(message.content_format),
        "delivery_state": "completed" if final else "stored_unverified" if message.sender_type == SenderType.ASSISTANT else "accepted",
        **({"client_id": message.turn_client_id} if message.turn_client_id else {}),
        "citations": [] if message.redacted_at is not None else [json.loads(item.citation_json) for item in message.citations],
        "created_at": message.created_at.isoformat(), **({"final_result": final} if final else {})}
