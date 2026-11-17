"""Read-only original cited chunk; implementations must prefilter current grants."""
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from campus247.domain.retrieval import RetrievalContext


@dataclass(frozen=True)
class CitationSourceExcerpt:
    source_id: str
    document_version_id: str
    chunk_id: str
    title: str
    canonical_uri: str
    version_label: str
    source_status: str
    locator: dict
    issuer: str
    effective_from: datetime
    effective_until: datetime | None
    content_text: str
    content_sha256: str
    applicability_note: str | None = None


class CitationSourceReader(Protocol):
    async def read(self, source_id: str, version_id: str, chunk_id: str,
                   *, context: RetrievalContext) -> CitationSourceExcerpt | None:
        """Return only currently eligible, authorized source content; never fetch URI."""
        ...
