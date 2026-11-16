"""Respect each PDF page's actual box; retain the original extraction for old citations."""
import json
import sys
from pathlib import Path

from acquire_huce_public_knowledge import DEST, checked

sys.path.append(str(Path(sys.base_prefix) / "Lib/site-packages"))
import pdfplumber

original = json.loads((DEST / "corpus.json").read_text(encoding="utf-8"))
target = checked(DEST / "handbook-visible.json")
if target.exists():
    raise FileExistsError("retain existing visible-page extraction")
template = original["chunks"][0]
chunks = []
with pdfplumber.open(DEST / "handbook-2026-2027.pdf") as document:
    for number, page in enumerate(document.pages, 1):
        # The booklet reuses a spread content stream in two half-page boxes.
        # PyPDF extraction includes invisible neighboring text. Bounding the
        # actual page fixes both relevance and the visible citation page number.
        text = page.crop(page.bbox).extract_text(x_tolerance=2, y_tolerance=3) or ""
        if text.strip():
            chunks.append(dict(template, page=number, section=f"Trang {number}", text=text.strip()))
chunks.extend(item for item in original["chunks"] if item["page"] is None)
with target.open("x", encoding="utf-8") as stream:
    json.dump(dict(original, chunks=chunks, extraction="pdfplumber-visible-page-box"), stream,
              ensure_ascii=False, indent=2)
print("visible-page chunks", len(chunks))
