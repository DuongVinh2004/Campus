"""Answer receipts (F4.2): record at answer time, re-check against the current release when the owner opens one."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Callable

from campus247.domain.shared.values import generate_uuid7
from campus247.ports.campus_ops import OpsError


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class AnswerReceiptService:
    def __init__(self, store, *, current_unit_sha: Callable[[str], str | None], current_release: Callable[[], str | None],
                 enabled: Callable[[], bool] = lambda: True, impact_run_for: Callable[[list[str]], str | None] | None = None,
                 clock: Callable[[], datetime] | None = None, on_error: Callable[[Exception], None] = lambda e: None,
                 version_state: Callable[[str | None, str | None], str] | None = None):
        self.store, self.current_unit_sha, self.current_release = store, current_unit_sha, current_release
        self.enabled, self.impact_run_for, self.on_error = enabled, impact_run_for, on_error
        self.version_state = version_state
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def record(self, *, owner: str, conversation_id: str, message_id: str, release_id: str, binding_sha256: str, outcome_kind: str,
               statements: list[str], sources: list[dict], checks: list[dict], rejected_counts: dict[str, int], expires_at: str) -> str | None:
        """Never raises: a failed write must not break the answer. Returns the receipt id, or None when off or failed."""
        if not self.enabled():
            return None
        try:
            receipt_id = generate_uuid7()
            self.store.save({"receipt_id": receipt_id, "owner_subject_id": owner, "conversation_id": conversation_id, "message_id": message_id,
                             "release_id": release_id, "binding_sha256": binding_sha256, "outcome_kind": outcome_kind,
                             "statements_sha256": sha(json.dumps(statements, ensure_ascii=False)), "sources": sources, "checks": checks,
                             "rejected_counts": rejected_counts, "created_at": self.clock().isoformat(timespec="seconds"), "expires_at": expires_at})
            return receipt_id
        except Exception as error:  # noqa: BLE001
            self.on_error(error)
            return None

    def open_for_message(self, owner: str, conversation_id: str, message_id: str) -> dict:
        row = self.store.for_message(conversation_id, message_id)
        if row is None:
            raise OpsError(404, "RECEIPT_NOT_FOUND", "Không tìm thấy biên nhận.")
        return self.open(owner, row["receipt_id"])

    def open(self, owner: str, receipt_id: str) -> dict:
        row = self.store.get(receipt_id)
        if row is None or row["owner_subject_id"] != owner or row["expires_at"] <= self.clock().isoformat(timespec="seconds"):
            raise OpsError(404, "RECEIPT_NOT_FOUND", "Không tìm thấy biên nhận.")
        changed = removed = 0
        sources = []
        for source in row["sources"]:
            if self.version_state is not None and source.get("version_id"):
                status = self.version_state(source["version_id"], source.get("document_id"))
            else:
                now_sha = self.current_unit_sha(source["unit_id"])
                status = "REMOVED" if now_sha is None else "UNCHANGED" if now_sha == source["text_sha256"] else "CHANGED"
            changed += status == "CHANGED"
            removed += status == "REMOVED"
            sources.append({"unit_id": source["unit_id"], "path": source.get("path"), "doc_title": source.get("doc_title"), "page": source.get("page"), "status_now": status})
        by_unit = {s["unit_id"]: s for s in sources}
        statements = []
        for index, check in enumerate(row["checks"]):
            shown = {k: v for k, v in check.items() if k != "unit_ids"}
            statements.append({"index": index + 1, "checks": shown, "sources": [by_unit[u] for u in check.get("unit_ids", []) if u in by_unit]})
        impact = self.impact_run_for([s["unit_id"] for s in sources if s["status_now"] == "CHANGED"]) if self.impact_run_for and changed else None
        return {"receipt_id": receipt_id, "created_at": row["created_at"], "release_id": row["release_id"], "outcome_kind": row["outcome_kind"],
                "statements": statements, "sources": sources, "rejected_counts": row["rejected_counts"],
                "now": {"release_id": self.current_release(), "sources_changed": changed, "sources_removed": removed, "impact_run_id": impact}}
