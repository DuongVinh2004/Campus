from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import re
from typing import Any
import unicodedata


@dataclass(frozen=True)
class ParsedSection:
    section_title: str
    section_path: str
    content: str
    char_start: int
    char_end: int


@dataclass(frozen=True)
class ParsedDocument:
    title: str
    canonical_text: str
    canonical_hash: str
    sections: tuple[ParsedSection, ...]
    metadata: dict[str, Any] = field(default_factory=dict)


class DocumentParser:
    """Normalizes document text into NFC with section hierarchy and provenance offsets."""

    def parse(self, raw_text: str, metadata: dict[str, Any] | None = None) -> ParsedDocument:
        if not raw_text or not raw_text.strip():
            raise ValueError("Input text is empty")

        # Unicode NFC normalization
        normalized = unicodedata.normalize("NFC", raw_text)
        # Controlled whitespace: replace Windows \r\n with \n, strip trailing whitespace per line
        lines = [line.rstrip() for line in normalized.splitlines()]
        canonical_text = "\n".join(lines).strip()
        canonical_hash = f"sha256:{hashlib.sha256(canonical_text.encode('utf-8')).hexdigest()}"
        # Character locators belong to the canonical text, after outer trimming.
        lines = canonical_text.splitlines()

        # Source metadata supplies the title when text has no level-one heading.
        # It labels the locator; it never changes the canonical source or offsets.
        metadata_title = (metadata or {}).get("title")
        doc_title = (
            unicodedata.normalize("NFC", metadata_title.strip())
            if isinstance(metadata_title, str) and metadata_title.strip()
            else "Untitled Document"
        )
        sections: list[ParsedSection] = []

        heading_pattern = re.compile(r"^(#{1,3})\s+(.*)$")
        current_h1 = ""
        current_sec_title = ""
        current_sec_lines: list[str] = []
        current_sec_start = 0

        current_offset = 0
        for line in lines:
            line_len = len(line) + 1  # include \n
            m = heading_pattern.match(line)
            if m:
                level = len(m.group(1))
                heading_text = m.group(2).strip()

                if level == 1 and not current_h1:
                    current_h1 = heading_text
                    doc_title = heading_text

                # Flush previous section if any content
                if current_sec_title and current_sec_lines:
                    raw_section = canonical_text[current_sec_start:current_offset]
                    sec_text = raw_section.strip()
                    if sec_text:
                        content_start = current_sec_start + len(raw_section) - len(raw_section.lstrip())
                        sec_path = f"{doc_title} > {current_sec_title}" if doc_title != current_sec_title else doc_title
                        sections.append(
                            ParsedSection(
                                section_title=current_sec_title,
                                section_path=sec_path,
                                content=sec_text,
                                char_start=content_start,
                                char_end=content_start + len(sec_text),
                            )
                        )

                current_sec_title = heading_text
                current_sec_lines = []
                current_sec_start = current_offset + line_len
            else:
                if line.strip():
                    current_sec_lines.append(line)

            current_offset += line_len

        # Flush final section
        if current_sec_title and current_sec_lines:
            raw_section = canonical_text[current_sec_start:]
            sec_text = raw_section.strip()
            if sec_text:
                content_start = current_sec_start + len(raw_section) - len(raw_section.lstrip())
                sec_path = f"{doc_title} > {current_sec_title}" if doc_title != current_sec_title else doc_title
                sections.append(
                    ParsedSection(
                        section_title=current_sec_title,
                        section_path=sec_path,
                        content=sec_text,
                        char_start=content_start,
                        char_end=content_start + len(sec_text),
                    )
                )

        # Fallback if no sections were parsed
        if not sections and canonical_text:
            sections.append(
                ParsedSection(
                    section_title=doc_title,
                    section_path=doc_title,
                    content=canonical_text,
                    char_start=0,
                    char_end=len(canonical_text),
                )
            )

        return ParsedDocument(
            title=doc_title,
            canonical_text=canonical_text,
            canonical_hash=canonical_hash,
            sections=tuple(sections),
            metadata=dict(metadata or {}),
        )
