"""Write the evidence receipt for a saved assistant message (F4.2). Best effort: it never raises into the chat path."""
from __future__ import annotations

import hashlib
import json


def record_receipt(service, *, owner: str, conversation_id: str, message, result, expires_at: str, release_id: str | None) -> str | None:
    evidence = getattr(result, "evidence", None)
    if service is None or not evidence or not release_id:
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
            sha = service.current_unit_sha(unit_id)
            if sha is None:
                return None  # cannot bind the receipt to the source text; better none than a wrong one
            data = meta.get(unit_id, {})
            sources.append({"unit_id": unit_id, "text_sha256": sha, "path": (data.get("locator") or {}).get("section_path"),
                            "doc_title": data.get("source_title"), "page": (data.get("locator") or {}).get("page_start")})
        binding = hashlib.sha256("|".join(f"{s['unit_id']}:{s['text_sha256']}" for s in sources).encode()).hexdigest()
        return service.record(owner=owner, conversation_id=conversation_id, message_id=message.id, release_id=release_id,
                              binding_sha256=binding, outcome_kind="partial" if result.response_class == "partial_answer" else "answer",
                              statements=evidence["statements"], sources=sources, checks=evidence["checks"],
                              rejected_counts=evidence["rejected_counts"], expires_at=expires_at)
    except Exception as error:  # noqa: BLE001
        service.on_error(error)
        return None
