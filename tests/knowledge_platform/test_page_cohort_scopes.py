from copy import deepcopy
from datetime import UTC, datetime

import pytest
from campus247.application.knowledge.platform_models import PlatformError, digest
from campus247.application.knowledge.source_snapshot import (
    PROCESSOR,
    scope_allows,
    validate_snapshot,
)


def fixture():
    now = datetime(2026, 10, 24, tzinfo=UTC)
    texts = ["NGÀNH KHOA HỌC MÁY TÍNH (ÁP DỤNG CHO KHÓA 69)\nTổng: 180TC",
        "NGÀNH KHOA HỌC MÁY TÍNH (ÁP DỤNG TỪ KHÓA 70)\nTổng: 185TC"]
    blocks = [{"block_id": str(n), "page": n+1, "text": text} for n, text in enumerate(texts)]
    scope = {"kind": "COHORT_SNAPSHOT", "cohort_partitioned": True, "cohorts": ["K69", "K70"],
        "programme_codes": [], "admission_only": True, "legal_effective_from": None, "reviewed_at": now.isoformat()}
    rendition = {"processor": PROCESSOR, "original_sha256": "a"*64, "applicability": scope, "issues": [],
        "pages": [{**b, "char_start": 0, "char_end": len(b["text"]), "text_sha256": digest(b["text"].encode()),
            "cohorts": ["K" + str(69+n)]} for n,b in enumerate(blocks)]}
    return rendition, {"original_sha256": "a"*64, "blocks": blocks}, now


def test_each_cohort_is_bound_to_its_own_printed_source_page():
    rendition, extraction, now = fixture()
    validate_snapshot(rendition, extraction, original_sha256="a"*64, effective_from=now)
    scopes = [{**rendition["applicability"], "cohorts": page["cohorts"]} for page in rendition["pages"]]
    assert scope_allows("Khóa 69 có tổng bao nhiêu tín chỉ?", scopes[0])
    assert not scope_allows("Khóa 69 có tổng bao nhiêu tín chỉ?", scopes[1])


def test_union_or_swapped_cohort_metadata_cannot_hide_different_totals():
    rendition, extraction, now = fixture()
    for cohorts in (["K69"], ["K69", "K70"]):
        tampered = deepcopy(rendition); tampered["pages"][1]["cohorts"] = cohorts
        with pytest.raises(PlatformError, match="SOURCE_COHORT_SPAN_MISMATCH"):
            validate_snapshot(tampered, extraction, original_sha256="a"*64, effective_from=now)


def test_unmapped_calendar_never_assigns_a_mixed_row_to_a_specific_cohort():
    scope = {**fixture()[0]["applicability"], "cohort_partitioned": False, "mixed_cohort_table": True}
    assert not scope_allows("Lịch thi K69 là ngày nào?", scope)
    assert scope_allows("Kế hoạch học tập nói về những khóa nào?", scope)
