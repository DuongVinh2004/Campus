"""Read-only view of the running rag_v2 index units (G-PG.1): verbatim text, path and release binding.

`text(unit_id)` returns the unit's source text without the retrieval-context prefix, exactly the bytes a
quote must be a substring of. The file is re-read when its mtime changes (a new release lands on disk).
"""
from __future__ import annotations

import json
import threading
from pathlib import Path

SOURCE_MARK = "⟦RAG_V2_SOURCE⟧"


def unit_body(raw_text: str) -> str:
    i = raw_text.find(SOURCE_MARK)
    return raw_text[i + len(SOURCE_MARK):].strip() if i >= 0 else raw_text


class RagV2Units:
    def __init__(self, index_dir: Path):
        self.index_dir = Path(index_dir)
        self._lock = threading.Lock()
        self._mtime = None
        self._units: dict[str, dict] = {}

    def _load(self) -> None:
        path = self.index_dir / "units.jsonl"
        try:
            mtime = path.stat().st_mtime_ns
        except OSError:
            self._units, self._mtime = {}, None
            return
        if mtime == self._mtime:
            return
        with self._lock:
            units = {}
            with path.open(encoding="utf-8") as handle:
                for line in handle:
                    u = json.loads(line)
                    units[u["unit_id"]] = {"text": unit_body(u["text"]), "path": u["path"], "version_id": u["version_id"],
                        "document_id": u["document_id"], "doc_title": u["doc_title"], "doc_family": u["doc_family"],
                        "scope": u.get("scope") or {}, "effective_from": u.get("effective_from"), "effective_until": u.get("effective_until")}
            self._units, self._mtime = units, mtime

    def get(self, unit_id: str) -> dict | None:
        self._load()
        return self._units.get(unit_id)

    def text(self, unit_id: str) -> str | None:
        u = self.get(unit_id)
        return u["text"] if u else None

    def rows(self):
        """Every unit as a plain dict (for release snapshots)."""
        self._load()
        for unit_id, u in self._units.items():
            yield {"unit_id": unit_id, "document_id": u["document_id"], "version_id": u["version_id"], "doc_family": u["doc_family"],
                   "doc_title": u["doc_title"], "path": u["path"], "text": u["text"], "scope": u.get("scope") or {},
                   "effective_from": u.get("effective_from"), "effective_until": u.get("effective_until")}

    def release(self) -> dict:
        try:
            m = json.loads((self.index_dir / "manifest.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"release_id": "unknown", "binding_sha256": "unknown"}
        return {"release_id": str(m.get("release_id") or "unknown"),
                "binding_sha256": str(m.get("binding_sha256") or m.get("corpus_sha256") or "unknown")}

    def __len__(self) -> int:
        self._load()
        return len(self._units)
