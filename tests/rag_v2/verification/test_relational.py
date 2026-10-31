"""Values are checked with their unit, date form and scope, not as bare sets of numbers."""
import pytest
from campus247.rag_v2.types import Scope, Statement, Unit
from campus247.rag_v2.verification.deterministic import check_statement


def unit(text, uid="u1", scope=None):
    return Unit(uid, ("c",), "d", "v", "Quy chế", "quy_che", "clause", "Điều 1", 1, text, scope=scope or Scope())


def check(source, claim, scope=None):
    return check_statement(Statement(claim, ("u1",)), {"u1": unit(source, scope=scope)})


@pytest.mark.parametrize(("source", "claim"), [
    ("Hạn ngày 01 tháng 9 năm 2026.", "Hạn 2026-09-01."),
    ("Hạn 01.09.2026.", "Hạn 01/09/2026."),
    ("Hạn 01/09/2026.", "Hạn ngày 01 tháng 9 năm 2026."),
    ("Tỷ lệ 50 phần trăm.", "Tỷ lệ 50%."),
    ("Tỷ lệ 50%.", "Tỷ lệ 50 phần trăm."),
    ("Học kỳ II nộp hồ sơ.", "Hồ sơ nộp ở học kỳ 2."),
    ("Mức thu 580.500 đồng/tín chỉ.", "Mức thu là 580.500 đồng cho mỗi tín chỉ."),
    ("Giá 100 USD.", "Giá 100 USD."),
])
def test_equivalent_forms_of_the_same_value_pass(source, claim):
    assert check(source, claim).passed, check(source, claim).reasons


@pytest.mark.parametrize(("source", "claim", "reason"), [
    ("Giá 100 USD.", "Giá 100 EUR.", "UNIT_MISMATCH"),
    ("Khối lượng 5 kg.", "Khối lượng 5 tấn.", "UNIT_MISMATCH"),
    ("Nộp trong 7 ngày.", "Nộp trong 7 tháng.", "UNIT_MISMATCH"),
    ("Tối đa 14 tín chỉ.", "Tối đa 14 giờ.", "UNIT_MISMATCH"),
    ("Học kỳ II nộp hồ sơ.", "Học kỳ IV nộp hồ sơ.", "NUMBER_NOT_IN_SOURCE"),
    ("Mức A 0.125.", "Mức A 125.", "NUMBER_NOT_IN_SOURCE"),
    ("Hạn ngày 01 tháng 9 năm 2026.", "Hạn 2026-09-02.", "DATE_NOT_IN_SOURCE"),
    ("Mức thu 100 đồng.", "Mức thu 999 đồng.", "NUMBER_NOT_IN_SOURCE"),
])
def test_changed_unit_semester_decimal_or_date_is_rejected(source, claim, reason):
    verdict = check(source, claim)
    assert not verdict.passed and reason in verdict.reasons


def test_a_number_without_an_adjacent_unit_in_the_source_is_not_over_rejected():
    # Table cells and parenthetical numbers carry the unit elsewhere; the semantic check judges those.
    assert check("Số ngày: 07 (bảy)", "Thời hạn là 07 ngày.").passed


def test_statement_combining_two_cited_cohort_units_is_accepted():
    k64 = unit("K64 dùng A1.", "u1", Scope(cohorts=("K64",)))
    k65 = unit("K65 dùng B2.", "u2", Scope(cohorts=("K65",)))
    verdict = check_statement(Statement("K64 dùng A1 và K65 dùng B2.", ("u1", "u2")), {"u1": k64, "u2": k65})
    assert verdict.passed, verdict.reasons


def test_a_cohort_declared_by_none_of_the_cited_units_is_still_rejected():
    k64 = unit("K64 dùng A1.", "u1", Scope(cohorts=("K64",)))
    verdict = check_statement(Statement("K66 dùng A1.", ("u1",)), {"u1": k64})
    assert not verdict.passed and "SCOPE_MISMATCH" in verdict.reasons
