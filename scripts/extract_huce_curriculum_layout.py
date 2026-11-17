"""Re-extract retained PDFs with PDFium, keeping text-region geometry for table QA.

Text reading order alone does not encode prerequisite arrows or table columns.
These pages stay unadmitted until the relevant values/relationships are reviewed.
"""
import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pypdfium2 as pdfium

from huce_source_registry import BASE, ROOT, checked, save


def main(args):
    source = checked(Path(args.curricula))
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    output = checked(BASE / datetime.now(UTC).strftime("layout-%Y%m%dT%H%M%S%fZ"))
    output.mkdir(parents=True, exist_ok=False)
    files = []
    for record in manifest["files"]:
        if record["status"] != "downloaded": continue
        original = checked(ROOT / record["original_file"])
        if hashlib.sha256(original.read_bytes()).hexdigest() != record["sha256"]:
            raise ValueError("original hash mismatch")
        pages = []
        with pdfium.PdfDocument(str(original)) as document:
            for index in range(len(document)):
                page = document[index]
                textpage = page.get_textpage()
                text = textpage.get_text_bounded()
                regions = []
                for position in range(textpage.count_rects()):
                    bbox = textpage.get_rect(position)
                    # PDF coordinate system: left,bottom,right,top.
                    regions.append({"bbox": bbox, "text": textpage.get_text_bounded(*bbox)})
                lines = [line.strip() for line in text.splitlines() if line.strip()]
                pages.append({"page": index + 1, "width": page.get_width(), "height": page.get_height(),
                    "text": text, "text_sha256": hashlib.sha256(text.encode()).hexdigest(), "regions": regions,
                    "single_character_line_ratio": sum(len(line) <= 2 for line in lines) / max(1, len(lines)),
                    "ocr_quality": "needs_ocr" if len(text.strip()) < 60 else "native_text_extracted_not_ocr",
                    "table_semantics": "spatial_regions_preserved; row/column/arrows_require_review"})
                textpage.close(); page.close()
        destination = checked(output / (record["drive_id"] + ".json"))
        save(destination, {"source_sha256": record["sha256"], "source_file": record["original_file"],
                           "public_url": record["url"], "extractor": "PDFium", "pages": pages})
        files.append({"drive_id": record["drive_id"], "source_sha256": record["sha256"], "file": str(destination.relative_to(ROOT)),
                      "pages": len(pages), "needs_ocr_pages": sum(p["ocr_quality"] == "needs_ocr" for p in pages),
                      "rag_status": "unreviewed_layout_not_admitted"})
    save(output / "manifest.json", {"source_manifest": str((source / "manifest.json").relative_to(ROOT)), "files": files,
        "files_processed": len(files), "pages_processed": sum(f["pages"] for f in files),
        "needs_ocr_pages": sum(f["needs_ocr_pages"] for f in files), "originals_preserved": True})
    print(json.dumps({"output": str(output), "files": len(files), "pages": sum(f["pages"] for f in files),
                      "needs_ocr_pages": sum(f["needs_ocr_pages"] for f in files)}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--curricula", required=True)
    main(parser.parse_args())
