"""Correct one automated excerpt after visual PDF review; retain its old readback."""
import hashlib
import json
from datetime import UTC, datetime

from huce_source_registry import ROOT, checked, save


def main():
    directory = ROOT / "data/huce-public-20261013"
    old = json.loads(checked(directory / "reviewed-expansion-20261020-batch2.json").read_text(encoding="utf-8"))
    item = next(row for row in old["chunks"] if row["title"] == "K71 — Quản lý dự án")
    original = checked(ROOT / "data" / item["source_file"])
    assert hashlib.sha256(original.read_bytes()).hexdigest() == item["source_sha256"]
    text = ("KẾ HOẠCH GIẢNG DẠY CTĐT TRÌNH ĐỘ CỬ NHÂN\nNGÀNH QUẢN LÝ DỰ ÁN (K71QLDA)\n"
        "Học kỳ 1\n420103 – 3\nTriết học Mác - Lênin\n521322 – 1\nGiới thiệu ngành quản lý dự án\n"
        "100201 – 2\nMôi trường và phát triển bền vững\n"
        "Tổng: 131TC (Không tính HP giáo dục thể chất, Giáo dục quốc phòng và An ninh, các học phần đánh chữ in nghiêng là học phần tự chọn)")
    now = datetime.now(UTC).isoformat()
    reviewed = {**item, "text": text, "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "section": "K71QLDA — tiêu đề, ba ô học phần ở học kỳ 1 và dòng tổng, trang 1",
        "issuer": "Trường Đại học Xây dựng", "published_at": None, "collected_at": None,
        "academic_year": None, "legal_effective_from": None, "reviewed_at": now,
        "effective_from": item["effective_from"], "supersedes": [],
        "replaces_excerpt_text_sha256": item["text_sha256"],
        "review_status": "visually_reviewed_selected_cells",
        "ocr_quality": "not_applicable_native_pdf",
        "review_scope": "Whole page visually inspected; verbatim heading, three semester-1 cells and total/exclusion footnote only",
        "applicability": {"cohort": "K71", "programme": "Quản lý dự án", "degree": "cử nhân",
                          "system": None, "academic_year": None},
        "limitations": ["Only three semester-1 cells transcribed; remaining grid and arrows not admitted",
                        "No publication date or academic year stated on this page",
                        "Replaces an automated excerpt, not a superseding university regulation"],
        "visual_evidence": ".tooling/huce-continuation-20261020-01/qlda-page1.png"}
    # Same original PDF bytes and acquisition: retain its document-version identity.
    # The extraction/review revision has a distinct label and content/chunk hash.
    save(directory / "reviewed-course-review-20261021.json", {"public_only": True,
        "acquired_at": old["acquired_at"], "reviewed_at": now, "version_label": "reviewed-course-review-20261021",
        "verification": "visually_reviewed_source_excerpts", "chunks": [reviewed]})
    save(ROOT / ".tooling/huce-continuation-20261020-01/curriculum-review.json", {
        "reviewed_at": now, "source_sha256": item["source_sha256"], "page": 1, "cohort": "K71",
        "programme": "Quản lý dự án", "degree": "cử nhân", "total_credits": 131,
        "original_excerpt_sha256": item["text_sha256"], "new_excerpt_sha256": reviewed["text_sha256"],
        "issue": "Automated industry line was actually a truncated course title; the true programme heading was omitted",
        "originals_preserved": True, "relationship_review": "arrows not transcribed",
        "visual_evidence": reviewed["visual_evidence"]})
    print(json.dumps({"reviewed_pdfs": 1, "selected_course_cells": 3, "original_preserved": True}))


if __name__ == "__main__":
    main()
