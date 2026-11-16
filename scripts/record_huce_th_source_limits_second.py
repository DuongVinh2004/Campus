"""Retain 71TH's printed values and missing fields without expanding service."""
from datetime import UTC, datetime

from continue_huce_completion_20261025 import OUT, ROOT, checked, read, save, sha


def main():
    source = "e97e2bad-d225-74b1-8e5d-ba9595dbc54b"
    receipt_file = checked(OUT / "black-border-tables-02" / source / "receipt.json")
    receipt = read(receipt_file)
    page = receipt["pages"][0]
    geometry_file = checked(ROOT / page["geometry"])
    assert sha(geometry_file.read_bytes()) == page["geometry_sha256"]
    assert sha(checked(ROOT / page["image"]).read_bytes()) == page["image_sha256"]
    geometry = read(geometry_file)
    assert "TIN HỌC XÂY DỰNG – 71TH" in geometry["text"]
    assert page["cell_count"] == page["centre_agreement"] == page["bounded_agreement"] == 86
    cells = [c for c in page["cells"] if c["semester"] is not None]
    legend = [c for c in page["cells"] if c["semester"] is None]
    assert len(cells) == 83 and len(legend) == 3
    electives = [c for c in cells if c["text"].startswith("Tự chọn")]
    assert len(electives) == 2
    assert "040307\nBê tông tiên tiến" in electives[0]["text"]
    assert "020315\nBảo trì công trình" in electives[1]["text"]
    assert all(c["text"].splitlines()[0].endswith("2TC") for c in electives)
    unlabelled = [c for c in cells if c["text"].startswith("Giáo dục TC")]
    assert [c["text"] for c in unlabelled] == ["Giáo dục TC1", "Giáo dục TC2", "Giáo dục TC3"]
    save(OUT / "th-71-source-limits-01.json", {"at": datetime.now(UTC), "source_id": source,
        "original_sha256": receipt["original_sha256"], "receipt": str(receipt_file.relative_to(ROOT)),
        "receipt_sha256": sha(receipt_file.read_bytes()), "geometry": page["geometry"],
        "geometry_sha256": page["geometry_sha256"], "image": page["image"], "image_sha256": page["image_sha256"],
        "programme_printed": "71TH", "cohort": "K71", "physical_curriculum_cells": 83,
        "decoder_agreement": {"bounded": 86, "centre": 86, "includes_legend_cells": 3},
        "semester_cells": cells, "excluded_legend_cells": legend,
        "unlabelled_physical_education_cells": unlabelled, "elective_cells": electives,
        "missing_option_credit_codes": ["040307", "020315"],
        "findings": [
            "The complete original page was visually read.83 curriculum cells span nine semesters; three additional detected cells are legend/Block2/elective keys, not courses.",
            "Both elective groups print2TC.040307 and020315 print a code/name but no individual credit value; group2TC does not establish those options' credits or the number of options to choose.",
            "Giáo dụcTC1/2/3 print no individual credit. Their name digits do not establish credits.",
            "Preserve leading zeroes in course identifiers, native440203 for Anh ngữ3, and original spellings/abbreviations. Do not silently repair identifiers or wording.",
            "Native arrows and all coloured objects remain in the original geometry. Endpoint pairs have not yet been bound in a retained source-specific review; no new relationships admitted.",
            "Current geometry code parser requires an explicit code-credit pair. The two unlabelled option codes need a source-bound representation before a full semantic review can be admitted. No credits invented to satisfy that parser."],
        "visual_cell_review_completed": True, "full_relationship_review_completed": False,
        "source_semantics_resolved": False, "serving_scope_expanded": False,
        "reviewer": "coding agent technical visual review; no official HUCE approval claimed"})
    print({"curriculum_cells": len(cells), "legend_cells": len(legend), "missing_option_credit_codes": 2,
        "unlabelled_pe_cells": len(unlabelled), "admitted": False})


if __name__ == "__main__":
    main()
