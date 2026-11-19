"""Availability timestamps cannot impersonate legal dates or source geometry."""
from copy import deepcopy
from datetime import UTC, datetime

import pytest
from campus247.application.knowledge.platform_models import PlatformError, digest
from campus247.application.knowledge.source_snapshot import (
    PROCESSOR,
    scope_allows,
    snapshot_note,
    validate_snapshot,
)

NOW = datetime(2026, 10, 24, 8, tzinfo=UTC)


def fixture():
    text = "Học kỳ 1\n538801 – 3\nNhập môn lập trình\nTổng: 180 TC"
    scope = {"kind": "COHORT_SNAPSHOT", "reviewed_at": NOW.isoformat(), "admission_only": True,
        "legal_effective_from": None, "cohorts": ["K71"], "programme_codes": ["71PM"]}
    extracted = {"original_sha256": "a" * 64, "blocks": [{"block_id": "0", "page": 1, "text": text}]}
    rendition = {"processor": PROCESSOR, "original_sha256": "a" * 64, "applicability": scope, "issues": [],
        "pages": [{"block_id": "0", "page": 1, "char_start": 0, "char_end": len(text), "text": text, "text_sha256": digest(text.encode())}]}
    return rendition, extracted


def test_snapshot_admission_preserves_unknown_legal_effectivity_and_exact_source():
    rendition, extracted = fixture()
    scope = validate_snapshot(rendition, extracted, original_sha256="a" * 64, effective_from=NOW)
    assert scope["legal_effective_from"] is None
    assert "không phải ngày hiệu lực pháp lý" in snapshot_note(scope)


@pytest.mark.parametrize("field,value", [("legal_effective_from", NOW.isoformat()), ("admission_only", False),
    ("kind", "LEGAL_EFFECT"), ("reviewed_at", "2026-10-23T08:00:00+00:00")])
def test_snapshot_cannot_claim_a_legal_date_or_substitute_an_unbound_admission(field, value):
    rendition, extracted = fixture()
    rendition["applicability"][field] = value
    with pytest.raises(PlatformError):
        validate_snapshot(rendition, extracted, original_sha256="a" * 64, effective_from=NOW)


@pytest.mark.parametrize("field,value", [("text", "Tổng: 200 TC"), ("page", 2), ("char_start", -1),
    ("char_end", 100000), ("text_sha256", "0" * 64), ("block_id", "unknown")])
def test_source_span_tampering_is_rejected(field, value):
    rendition, extracted = fixture()
    rendition["pages"][0][field] = value
    with pytest.raises(PlatformError, match="SOURCE_SPAN_MISMATCH"):
        validate_snapshot(rendition, extracted, original_sha256="a" * 64, effective_from=NOW)


def test_snapshot_cannot_adopt_another_original_or_changed_extraction():
    rendition, extracted = fixture()
    with pytest.raises(PlatformError):
        validate_snapshot(rendition, extracted, original_sha256="b" * 64, effective_from=NOW)
    altered = deepcopy(extracted)
    altered["blocks"][0]["text"] = "A changed original page"
    with pytest.raises(PlatformError):
        validate_snapshot(rendition, altered, original_sha256="a" * 64, effective_from=NOW)


@pytest.mark.parametrize("key", ["_evidence_sections", "_evidence_hashes", "_evidence_scopes", "_verified_geometry"])
def test_stored_scope_cannot_supply_private_runtime_attestations(key):
    rendition, extracted = fixture()
    rendition["applicability"][key] = {"forged": "reviewed section"}
    with pytest.raises(PlatformError, match="SNAPSHOT_BINDING_REQUIRED"):
        validate_snapshot(rendition, extracted, original_sha256="a" * 64, effective_from=NOW)


@pytest.mark.parametrize("query,allowed", [("K71 kỹ sư phần mềm bao nhiêu tín chỉ?", True),
    ("K69 kỹ sư phần mềm bao nhiêu tín chỉ?", False), ("71PM có bao nhiêu tín chỉ?", True),
    ("71IS có bao nhiêu tín chỉ?", False), ("Môn nào là tiên quyết?", False),
    ("Các học phần song hành?", False), ("K71 học kỳ 2 có môn gì?", False)])
def test_cohort_programme_and_unencoded_arrow_scope_are_enforced(query, allowed):
    scope = fixture()[0]["applicability"]
    assert scope_allows(query, scope) is allowed


def test_unknown_cohort_never_becomes_a_generic_k70_or_k71_scope():
    scope = fixture()[0]["applicability"]
    scope["cohorts"] = []
    assert not scope_allows("K71 học bao nhiêu tín chỉ?", scope)
    assert "không gán cho một khóa cụ thể" in snapshot_note(scope)


@pytest.mark.parametrize("query,allowed", [("Hạn nộp miễn giảm HKI 2025-2026?", True),
    ("Hạn nộp miễn giảm 2026–2027?", False), ("Hạn nộp miễn giảm hiện nay?", False)])
def test_historical_notice_requires_its_explicit_academic_year(query, allowed):
    scope = {**fixture()[0]["applicability"], "kind": "INFORMATION_SNAPSHOT",
        "academic_years": ["2025-2026"], "requires_academic_year": True}
    assert scope_allows(query, scope) is allowed
    assert "2025-2026" in snapshot_note(scope)


def _cohort_scope(*codes, cohorts=("K71",)):
    return {"kind": "COHORT_SNAPSHOT", "cohorts": list(cohorts), "programme_codes": list(codes)}


def test_a_question_naming_two_programmes_reaches_the_rows_of_each_only_when_any_is_requested():
    from campus247.application.knowledge.source_snapshot import scope_allows
    query = "Trong kế hoạch kỹ sư K71MOE và K71KEC, mã môn Ứng dụng AI là gì?"
    moe, kec, other = _cohort_scope("71moe"), _cohort_scope("71kec"), _cohort_scope("71mec")
    assert not scope_allows(query, moe) and not scope_allows(query, kec)  # default: every code must belong to the row
    assert scope_allows(query, moe, any_requested=True) and scope_allows(query, kec, any_requested=True)
    assert not scope_allows(query, other, any_requested=True)  # a programme that was not asked about stays excluded


def test_any_requested_keeps_the_cohort_and_geometry_gates():
    from campus247.application.knowledge.source_snapshot import scope_allows
    old = _cohort_scope("71moe", cohorts=("K70",))
    assert not scope_allows("Mã môn trong kế hoạch K71MOE", old, any_requested=True)
    assert scope_allows("So sánh K70 và K71 của K71MOE", old, any_requested=True)
    assert not scope_allows("Môn tiên quyết của K71MOE và K71KEC", _cohort_scope("71moe"), any_requested=True)
