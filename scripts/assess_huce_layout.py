"""Separate sparse native pages from scanned pages; retain partial visual transcription."""
import json
from datetime import UTC, datetime
from pathlib import Path

import pypdfium2 as pdfium

from huce_source_registry import ROOT, checked, save


def main():
    directory = checked(ROOT / "data/huce-discovery-20261020/layout-20261020T153253945901Z")
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    assessments = []
    for item in manifest["files"]:
        if not item["needs_ocr_pages"]: continue
        file = json.loads(checked(ROOT / item["file"]).read_text(encoding="utf-8"))
        with pdfium.PdfDocument(str(checked(ROOT / file["source_file"]))) as document:
            for row in file["pages"]:
                if row["ocr_quality"] != "needs_ocr": continue
                page = document[row["page"] - 1]
                images = sum(obj.type == pdfium.raw.FPDF_PAGEOBJ_IMAGE for obj in page.get_objects())
                assessments.append({"drive_id": item["drive_id"], "page": row["page"], "source_sha256": item["source_sha256"],
                    "image_objects": images, "native_text": row["text"],
                    "assessment": "scanned_image_needs_ocr" if images else "sparse_native_text_requires_visual_review_not_automatically_ocr",
                    "rag_status": "not_admitted"})
                page.close()
    save(directory / "assessment.json", {"created_at": datetime.now(UTC).isoformat(), "pages": assessments,
        "scanned_image_pages": sum(r["image_objects"] > 0 for r in assessments),
        "sparse_native_pages": sum(r["image_objects"] == 0 for r in assessments)})
    save(directory / "scan-selected-fields.json", {
        "drive_id": "1nPJqjaUqzlYIvT4OR1YMFoBjnP4yysxb", "method": "partial_visual_transcription_from_rendered_original",
        "complete_ocr": False, "rag_status": "not_admitted",
        "title_page_1": "KẾ HOẠCH GIẢNG DẠY CHƯƠNG TRÌNH ĐÀO TẠO TRÌNH ĐỘ KỸ SƯ — NGÀNH CÔNG NGHỆ KỸ THUẬT VẬT LIỆU XÂY DỰNG (2025)",
        "issuer_page_1": "TRƯỜNG ĐẠI HỌC XÂY DỰNG HÀ NỘI — KHOA VẬT LIỆU XÂY DỰNG",
        "semester_credits_page_1": {str(i): count for i, count in enumerate([19, 19, 20, 19, 22, 23, 20, 20, 18], 1)},
        "page_2": "English version of the chart; semester counts visually agree with page 1",
        "unresolved": ["Chart is dated 2025 while publication links it under both K71 and earlier cohorts; do not infer universal applicability.",
                       "Course cells, contact-hour units and prerequisite/corequisite arrows are not fully transcribed or admitted.",
                       "No printed overall total was observed; any sum of semester counts is derived, not an original total-row quote."],
        "visual_evidence": ["data/huce-discovery-20261020/curricula-20261020T150911234144Z/scan-review/page-1.png",
                            "data/huce-discovery-20261020/curricula-20261020T150911234144Z/scan-review/page-2.png"]})
    print(json.dumps({"assessment": str(directory / "assessment.json"), "scanned_image_pages": sum(r["image_objects"] > 0 for r in assessments),
                      "sparse_native_pages": sum(r["image_objects"] == 0 for r in assessments)}))


if __name__ == "__main__":
    main()
