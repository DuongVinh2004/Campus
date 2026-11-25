"""Who exists and which groups they belong to, for sending announcements (F1.2). Separate from IdentityContext on purpose:
adding faculty or class there would narrow the retrieval scope of the RAG pipeline."""
from __future__ import annotations

from typing import Iterator, Protocol

from campus247.domain.announcements import AudienceSpec, Recipient


class RecipientDirectoryPort(Protocol):
    def recipients(self, spec: AudienceSpec) -> Iterator[Recipient]: ...  # ordered by subject_id

    def all_recipients(self) -> list[Recipient]: ...

    def teaches(self, subject_id: str, offering_id: str) -> bool: ...
