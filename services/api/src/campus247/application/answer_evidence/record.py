"""Write the evidence receipt for a saved assistant message (F4.2). Best effort: it never raises into the chat path."""
from __future__ import annotations

import hashlib
import json
import logging

LOG = logging.getLogger("campus247.answer_receipts")


def record_receipt(service, *, owner: str, conversation_id: str, message, result, expires_at: str, release_id: str | None) -> str | None:
    evidence = getattr(result, "evidence", None)
    if service is None or not evidence or not release_id:
        LOG.warning("answer_receipt_skipped reason=%s", "NO_SERVICE" if service is None else "NO_EVIDENCE" if not evidence else "NO_RELEASE")
        return None
    try:
        unit_ids = list(dict.fromkeys(u for c in evidence["checks"] for u in c["unit_ids"]))
        meta = {}
        for citation in message.citations:
            data = json.loads(citation.citation_json)
            if data.get("unit_id"):
                meta[data["unit_id"]] = data
        sources = []
        for unit_id in unit_ids:
            data = meta.get(unit_id, {})
            # What the answer was built on: the hash of the cited source text itself, else the index's current hash of that unit.
            sha = data.get("evidence_sha256") or service.current_unit_sha(unit_id)
            if sha is None:
                LOG.warning("answer_receipt_skipped reason=SOURCE_NOT_BOUND unit=%s", unit_id)
                return None  # cannot bind the receipt to the source text; better none than a wrong one
            sources.append({"unit_id": unit_id, "text_sha256": sha, "path": (data.get("locator") or {}).get("section_path"),
                            "doc_title": data.get("source_title"), "page": (data.get("locator") or {}).get("page_start"),
                            "version_id": data.get("document_version_id"), "document_id": data.get("source_id")})
        binding = hashlib.sha256("|".join(f"{s['unit_id']}:{s['text_sha256']}" for s in sources).encode()).hexdigest()
        return service.record(owner=owner, conversation_id=conversation_id, message_id=message.id, release_id=release_id,
                              binding_sha256=binding, outcome_kind="partial" if result.response_class == "partial_answer" else "answer",
                              statements=evidence["statements"], sources=sources, checks=evidence["checks"],
                              rejected_counts=evidence["rejected_counts"], expires_at=expires_at)
    except Exception as error:  # noqa: BLE001
        LOG.warning("answer_receipt_write_failed kind=%s", type(error).__name__)
        service.on_error(error)
        return None
