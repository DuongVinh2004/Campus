"""Text of a .docx file (paragraphs and tables, in order) with zipfile and ElementTree; bounded against hostile archives."""
from __future__ import annotations

import io
import re
import zipfile
from xml.etree import ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
MAX_XML_BYTES = 20 * 1024 * 1024
MAX_ENTRIES = 2000


class DocxError(ValueError):
    pass


def _paragraph(node) -> str:
    parts = []
    for element in node.iter():
        if element.tag == W + "t":
            parts.append(element.text or "")
        elif element.tag in (W + "tab",):
            parts.append("\t")
        elif element.tag in (W + "br", W + "cr"):
            parts.append("\n")
    return re.sub(r"[ \t]+", " ", "".join(parts)).strip()


def docx_to_text(data: bytes) -> str:
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise DocxError("DOCX_NOT_A_ZIP") from None
    with archive:
        infos = archive.infolist()
        if len(infos) > MAX_ENTRIES or sum(info.file_size for info in infos) > 200 * 1024 * 1024:
            raise DocxError("DOCX_ARCHIVE_TOO_LARGE")
        try:
            info = archive.getinfo("word/document.xml")
        except KeyError:
            raise DocxError("DOCX_WITHOUT_DOCUMENT") from None
        if info.file_size > MAX_XML_BYTES:
            raise DocxError("DOCX_DOCUMENT_TOO_LARGE")
        try:
            root = ET.fromstring(archive.read(info))
        except ET.ParseError:
            raise DocxError("DOCX_XML_INVALID") from None
    body = root.find(W + "body")
    if body is None:
        raise DocxError("DOCX_WITHOUT_BODY")
    lines = []
    for child in body:
        if child.tag == W + "p":
            text = _paragraph(child)
            if text:
                lines.append(text)
        elif child.tag == W + "tbl":
            for row in child.iter(W + "tr"):
                cells = [" ".join(filter(None, (_paragraph(p) for p in cell.iter(W + "p")))) for cell in row.findall(W + "tc")]
                cells = [c for c in cells if c]
                if cells:
                    lines.append(" | ".join(cells))
    return "\n".join(lines)
