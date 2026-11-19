"""Regression: a mixed tuition table must not convert ĐVHT into credits."""
from pathlib import Path

import pytest

from campus247.application.retrieval.material_support import support_issues
from campus247.infrastructure.retrieval.public_knowledge import PublicKnowledgeStore

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def fees():
    store = PublicKnowledgeStore(ROOT / "data/huce-public-20261013", tenant_id="HUCE", campus_id="HUCE")
    return next(row["content_text"] for row in store.rows if row["document_number"] == "924/QĐ-ĐHXDHN" and row["page_start"] == 2)


@pytest.mark.parametrize("unit", ["đồng/tín chỉ", "đồng trên tín chỉ", "đồng cho mỗi tín chỉ", "VND/tin chi"])
def test_observed_wrong_denominator_is_rejected(fees, unit):
    assert "CONTRADICTED_UNIT" in support_issues(f"Kỹ sư chất lượng cao K66 trở về trước là 336.000 {unit}.", fees)


@pytest.mark.parametrize("text", [
    "Kỹ sư chất lượng cao K66 trở về trước là 336.000 đồng/ĐVHT.",
    "Kỹ sư chất lượng cao K66 trở về trước là 336.000 đồng/đơn vị học trình.",
    "Kỹ sư từ K69 là 547.000 đồng/tín chỉ.",
    "Kỹ sư chất lượng cao K66 trở về trước có mức học phí 336.000 đồng.",
])
def test_correct_units_and_amount_without_denominator_are_preserved(fees, text):
    assert "CONTRADICTED_UNIT" not in support_issues(text, fees)


def test_mixed_table_header_alone_does_not_infer_row_denominators():
    source = "Chương trình | Đối tượng | Mức học phí (đồng)/tín chỉ (ĐVHT)\nKỹ sư | K69 | 547.000"
    assert "CONTRADICTED_UNIT" not in support_issues("K69 là 547.000 đồng/tín chỉ.", source)


def test_prose_denominator_cannot_be_reversed():
    assert "CONTRADICTED_UNIT" in support_issues("Học phí là 547.000 đồng/ĐVHT.", "Học phí là 547.000 đồng/tín chỉ.")
