"""Retain the two distinct cohort pages without merging their course scopes."""
from datetime import UTC, datetime

from continue_huce_completion_20261025 import CORPUS, OUT, ROOT, checked, read, save, sha


def main():
    source = "f634f981-e997-70dc-89ea-f78f8e327268"
    receipt_file = checked(OUT / "black-border-tables-02" / source / "receipt.json")
    receipt = read(receipt_file)
    entry = next(e for e in read(CORPUS / "candidate-plan-32.json")["sources"] if e["source_id"] == source)
    candidate_file = checked(ROOT / entry["candidate"])
    assert sha(candidate_file.read_bytes()) == entry["candidate_sha256"]
    candidate = read(candidate_file)
    assert candidate["original_sha256"] == receipt["original_sha256"]
    assert candidate["applicability"]["cohort_partitioned"] is True
    assert candidate["applicability"]["cohorts"] == ["K69", "K70"]
    pages = []
    for page, heading, code, credits, count in zip(receipt["pages"],
            ("ÁP DỤNG CHO KHÓA 69", "ÁP DỤNG TỪ KHÓA 70"), ("608800", "608829"), (1, 2), (77, 76), strict=True):
        geometry_file = checked(ROOT / page["geometry"])
        assert sha(geometry_file.read_bytes()) == page["geometry_sha256"]
        assert sha(checked(ROOT / page["image"]).read_bytes()) == page["image_sha256"]
        geometry = read(geometry_file)
        assert heading in geometry["text"]
        assert page["cell_count"] == page["centre_agreement"] == page["bounded_agreement"] == count
        cells = [c for c in page["cells"] if c["semester"] is not None]
        assert len(cells) == count - 1
        intro = next(c for c in cells if c["text"].startswith(code))
        assert intro["course_code_credit_pairs"] == [[code, str(credits)]]
        starred = [c for c in cells if "2*" in c["text"]]
        assert len(starred) == 2 and all(not c["course_code_credit_pairs"] for c in starred)
        legend = next(c for c in page["cells"] if c["semester"] is None)
        assert "Học một trong hai học phần phụ thuộc kết quả phân loại tiếng Anh đầu vào" in legend["text"]
        pages.append({"page": page["page"], "printed_heading": heading, "introductory_cell": intro,
            "curriculum_cell_count": len(cells), "geometry": page["geometry"], "geometry_sha256": page["geometry_sha256"],
            "image": page["image"], "image_sha256": page["image_sha256"], "starred_english_cells": starred,
            "legend": legend, "cell_transcription": cells})
    save(OUT / "cs69-70-source-limits-01.json", {"at": datetime.now(UTC), "source_id": source,
        "original_sha256": receipt["original_sha256"], "receipt": str(receipt_file.relative_to(ROOT)),
        "receipt_sha256": sha(receipt_file.read_bytes()), "existing_candidate": str(candidate_file.relative_to(ROOT)),
        "existing_candidate_sha256": sha(candidate_file.read_bytes()), "existing_cohort_partition_preserved": True,
        "pages": pages, "findings": [
            "The two full original images were inspected independently. Page1 explicitly applies to cohort69; page2 prints from cohort70. The existing retained candidate already partitions these pages. No new current-cohort applicability inferred.",
            "The introductory course changes from608800/1credit on page1 to608829/2credits on page2. Do not substitute one for the other based on the document title.",
            "Both pages print448803–2* and440218–2*. Their legend ties selection of one of the two to English entrance classification. Current simple code-credit parser omits these starred pairs; do not remove the asterisk or treat both courses as mandatory.",
            "Page1 has76 physical curriculum cells; page2 has75, including a combined PE2/PE3 cell. No PE credit inferred from the name's digit.4801xx is retained as an unresolved printed identifier.",
            "No new arrow endpoint pairs bound, source permissions changed or serving content expanded in this inspection."],
        "visual_cell_review_completed": True, "full_relationship_review_completed": False,
        "source_semantics_resolved": False, "serving_scope_expanded": False})
    print({"pages": len(pages), "curriculum_cells": sum(p["curriculum_cell_count"] for p in pages),
        "existing_cohort_partition_preserved": True, "admitted": False})


if __name__ == "__main__":
    main()
