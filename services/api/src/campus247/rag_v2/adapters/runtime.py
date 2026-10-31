"""Per-turn view: authorization precedes ranking and every evidence limit."""
from __future__ import annotations

from hashlib import sha256

from campus247.rag_v2.ingest.units import CONTEXT_START, SOURCE_SEPARATOR, extract_scope
from campus247.rag_v2.types import Unit


class AuthorizedIndex:
    def __init__(self, index, units, *, rows=None, injection_check=None):
        self.index, self.units = index, dict(units)
        self._rows, self._injection_check = rows or {}, injection_check
        self._chunk_units: dict[str, Unit | None] = {}
        # A blocked/unreadable parent invalidates every dependent slice, including facts.
        if rows is not None:
            self.units = {uid: unit for uid, unit in self.units.items()
                          if unit.chunk_ids and all(self.chunk_unit(chunk) is not None for chunk in unit.chunk_ids)}

    def get(self, unit_id):
        return self.units.get(unit_id)

    def all_ids(self):
        return tuple(self.units)

    def chunk_unit(self, chunk_id):
        """The whole authorized source row as one unit (text comes from the database row, not the index file).

        Fine-grained units rank well but strip the sibling rows, footnotes and headers that complete
        an answer; the generator therefore reads the parent rows of the best units.
        """
        if chunk_id in self._chunk_units:
            return self._chunk_units[chunk_id]
        row = self._rows.get(chunk_id)
        unit = None
        if row is not None and isinstance(row.get("content_text"), str) and row["content_text"]:
            title = row.get("title") or ""
            path = row.get("section_path") or title
            if not (self._injection_check and self._injection_check(chunk_id, title + "\n" + str(path) + "\n" + row["content_text"])):
                unit = Unit(
                    unit_id=sha256(("chunk:" + chunk_id).encode()).hexdigest()[:16], chunk_ids=(chunk_id,), document_id=row["source_id"],
                    version_id=row["document_version_id"], doc_title=title, doc_family="chunk", kind="page",
                    path=str(path), page=row.get("page_start"),
                    text=CONTEXT_START + title + SOURCE_SEPARATOR + row["content_text"],
                    effective_from=row.get("effective_from"), effective_until=row.get("effective_until"),
                    scope=extract_scope(title + " " + str(path)))
        self._chunk_units[chunk_id] = unit
        return unit

    def _allowed(self, allowed):
        return set(self.units) if allowed is None else set(self.units).intersection(allowed)

    def lexical(self, query, limit, *, allowed=None):
        return self.index.lexical(query, limit, allowed=self._allowed(allowed))

    async def vector(self, query, limit, *, allowed=None):
        return await self.index.vector(query, limit, allowed=self._allowed(allowed))

    def anchored(self, query, limit, *, allowed=None):
        # The identifier branch must see the same authorization as lexical/vector; without it the
        # runtime ranks differently from the offline probes that use the bare index.
        anchored = getattr(self.index, "anchored", None)
        return anchored(query, limit, allowed=self._allowed(allowed)) if anchored else []
