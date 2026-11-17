"""Immutable source media and a separately validated PDF rendition boundary."""
from pathlib import Path
from typing import Protocol

PDF_MEDIA_TYPE = 'application/pdf'
PPTX_MEDIA_TYPE = 'application/vnd.openxmlformats-officedocument.presentationml.presentation'


class LearningRendition(Protocol):
    rendition_id: str
    pdf_path: str
    pdf_sha256: str
    pdf_bytes: int
    source_sha256: str
    slide_count: int
    converter_version: str
    converter_sha256: str


class LearningPptxConverter(Protocol):
    @property
    def available(self) -> bool: ...

    async def convert(self, source: Path, expected_sha256: str) -> LearningRendition: ...
