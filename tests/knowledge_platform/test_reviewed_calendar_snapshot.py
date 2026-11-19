"""The table replacement keeps row identity, provisional scope and exact spans."""
from datetime import datetime

import pytest

from complete_huce_corpus import read
from prepare_huce_evidence_20261025 import CALENDAR, OUT
from campus247.application.knowledge.source_snapshot import scope_allows, validate_snapshot


def candidate():
    return read(OUT / "candidates-01" / (CALENDAR + ".json"))


def test_reviewed_calendar_is_four_distinct_rows_with_208_week_cells():
    value = candidate()
    scope = validate_snapshot(value, value["extracted"], original_sha256=value["original_sha256"],
        effective_from=datetime.fromisoformat(value["applicability"]["reviewed_at"]))
    blocks = value["extracted"]["blocks"]
    assert [b["cohorts"] for b in blocks] == [["K68"], ["K69"], ["K70"], ["K71"]]
    assert sum(sum(line.split(" | ")[0].isdigit() for line in b["text"].splitlines()) for b in blocks) == 208
    assert "9 | 28/09/2026 | . | Thi hết HP" in blocks[0]["text"]
    assert "9 | 28/09/2026 |  | " in blocks[3]["text"]
    assert "40 | 03/05/2027 | Q | GDQP- An ninh" in blocks[3]["text"]
    assert blocks[3]["provisional"] and "DỰ\nKIẾN" in blocks[3]["text"]
    assert scope["requires_academic_year"] and not scope["mixed_cohort_table"]


@pytest.mark.parametrize("query,allowed", [
    ("K68 CNTT năm học 2026-2027 tuần 9 ghi ký hiệu gì?", True),
    ("K71 CNTT năm học 2026-2027 tuần 9 ghi ký hiệu gì?", False),
    ("K68 CNTT tuần 9 ghi ký hiệu gì?", False),
    ("K68 CNTT năm học 2025-2026 tuần 9 ghi ký hiệu gì?", False),
    ("K68 CNTT năm học 2026-2027 học kỳ 1 học môn gì?", False),
    ("K68 CNTT năm học 2026-2027 có môn tiên quyết nào?", False),
])
def test_a_selected_row_cannot_supply_another_cohort_year_or_unverified_relation(query, allowed):
    scope = {**candidate()["applicability"], "cohorts": ["K68"]}
    assert scope_allows(query, scope) is allowed
