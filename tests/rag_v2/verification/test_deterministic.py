import pytest
from campus247.rag_v2.generation.contacts import contact_map
from campus247.rag_v2.types import Scope, Statement, Unit
from campus247.rag_v2.verification.deterministic import REASON_CODES, check_statement


def unit(text, scope=None, ref="a"):
    return Unit(ref, ("chunk",), "doc", "v1", "Nguồn", "policy", "clause", "Điều 1", 1,
                text, scope=scope or Scope())


@pytest.mark.parametrize(("source", "draft", "reason"), [
    ("Học phí 580.500 đồng.", "Học phí 580.600 đồng.", "NUMBER_NOT_IN_SOURCE"),
    ("Hệ số 1,5.", "Hệ số 1,6.", "NUMBER_NOT_IN_SOURCE"),
    ("Mức thu 50%.", "Mức thu 5%.", "NUMBER_NOT_IN_SOURCE"),
    ("Có 50 tín chỉ.", "Mức thu 50%.", "NUMBER_NOT_IN_SOURCE"),
    ("Môn INT1234.", "Môn INT1235.", "CODE_NOT_IN_SOURCE"),
    ("Quyết định 123/QĐ-ĐHXD.", "Quyết định 123/QĐ-ABC.", "CODE_NOT_IN_SOURCE"),
    ("Hạn 01/02/2026.", "Hạn 02/01/2026.", "DATE_NOT_IN_SOURCE"),
    ("Hạn ngày 1 tháng 2 năm 2026.", "Hạn ngày 2 tháng 1 năm 2026.", "DATE_NOT_IN_SOURCE"),
    ("Hạn 01/02.", "Hạn 02/01.", "DATE_NOT_IN_SOURCE"),
    ("Hạn ngày 1 tháng 2.", "Hạn ngày 2 tháng 1.", "DATE_NOT_IN_SOURCE"),
    ("Sinh viên không được nghỉ.", "Sinh viên được nghỉ.", "NEGATION_MISMATCH"),
    ("Sinh viên được nghỉ.", "Sinh viên không được nghỉ.", "NEGATION_MISMATCH"),
    ("Sinh viên chưa được nghỉ.", "Sinh viên được nghỉ.", "NEGATION_MISMATCH"),
    ("Cấm sao chép.", "Được sao chép.", "NEGATION_MISMATCH"),
    ("Được nghỉ, ngoại trừ kỳ thi.", "Được nghỉ.", "NEGATION_MISMATCH"),
    ("Áp dụng trừ khóa cũ.", "Áp dụng mọi khóa.", "NEGATION_MISMATCH"),
    ("Sinh viên không được nghỉ.", "Sinh viên không phải không được nghỉ.", "NEGATION_MISMATCH"),
    ("Sinh viên chưa được nghỉ.", "Sinh viên không được nghỉ.", "NEGATION_MISMATCH"),
])
def test_changed_values_codes_dates_and_polarity_fail(source, draft, reason):
    verdict = check_statement(Statement(draft, ("a",)), {"a": unit(source)})
    assert not verdict.passed and reason in verdict.reasons
    assert set(verdict.reasons) <= REASON_CODES


@pytest.mark.parametrize(("source", "draft"), [
    ("Học phí 580.500 đồng.", "Học phí 580 500 đồng."),
    ("Hệ số 1,5.", "Hệ số 1.5."),
    ("Mức thu 50 %.", "Mức thu 50%."),
    ("Môn INT1234.", "Môn int1234."),
    ("Môn INT1234.", "Môn int 1234."),
    ("Hệ số 1,0.", "Hệ số 1."),
    ("Quyết định 123/QĐ-ĐHXD.", "Quyết định 123 / qđ - đhxd."),
    ("Hạn 01/02/2026.", "Hạn ngày 1 tháng 2 năm 2026."),
    ("Sinh viên không được nghỉ.", "Sinh viên không được nghỉ."),
])
def test_normalization_preserves_values(source, draft):
    assert check_statement(Statement(draft, ("a",)), {"a": unit(source)}).passed


def test_only_cited_units_count():
    units = {"a": unit("Học phí 580.500 đồng."), "b": unit("Học phí 680.500 đồng.", ref="b")}
    assert not check_statement(Statement("Học phí 580.500 đồng.", ("b",)), units).passed
    for refs in [(), ("unknown",), ("a", "unknown")]:
        assert check_statement(Statement("x", refs), units).reasons == ("UNIT_NOT_CITED",)


@pytest.mark.parametrize(("draft", "scope"), [
    ("Áp dụng khóa 65.", Scope(cohorts=("K64",))),
    ("Áp dụng K65.", Scope(cohorts=("K64",))),
    ("Áp dụng ngành 7480202.", Scope(programs=("7480201",))),
    ("Áp dụng ngành Kiến trúc.", Scope(programs=("Công nghệ thông tin",))),
    ("Áp dụng năm học 2025-2026.", Scope(academic_years=("2026-2027",))),
    ("Áp dụng năm 2025.", Scope(academic_years=("2026-2027",))),
])
def test_scope_conflicts_fail_even_if_text_has_the_number(draft, scope):
    verdict = check_statement(Statement(draft, ("a",)), {"a": unit(draft, scope)})
    assert "SCOPE_MISMATCH" in verdict.reasons


def test_matching_scope_and_contact_labels_pass():
    source = unit("Khóa K64 ngành Công nghệ thông tin năm học 2026-2027: liên hệ synthetic-office@huce.edu.vn.",
                  Scope(("K64",), ("Công nghệ thông tin",), ("2026-2027",)))
    marker = next(iter(contact_map([source])))
    text = source.text.replace("synthetic-office@huce.edu.vn", marker)
    assert check_statement(Statement(text, ("a",)), {"a": source}).passed


def _big_row(core: str) -> str:
    filler = " ".join(f"Mục {i}: sinh viên không phải nộp hồ sơ giấy cho mục này." for i in range(20))
    return filler + " " + core + " " + filler


def _check(statement: str, core: str):
    from campus247.rag_v2.types import Statement, Unit
    unit = Unit("u" * 16, ("c",), "d", "v", "t", "f", "page", "p", None, _big_row(core))
    return check_statement(Statement(statement, (unit.unit_id,)), {unit.unit_id: unit})


def test_unrelated_negators_in_a_long_row_do_not_reject_a_correct_statement():
    assert _check("Sinh viên nộp đơn tại phòng đào tạo.", "Sinh viên nộp đơn tại phòng đào tạo.").passed


def test_long_row_still_rejects_added_or_dropped_negation():
    assert "NEGATION_MISMATCH" in _check("Sinh viên không nộp đơn tại phòng đào tạo.", "Sinh viên nộp đơn tại phòng đào tạo.").reasons
    assert "NEGATION_MISMATCH" in _check("Sinh viên được nghỉ học tạm thời.", "Sinh viên không được nghỉ học tạm thời.").reasons
    assert _check("Sinh viên không được nghỉ học tạm thời.", "Sinh viên không được nghỉ học tạm thời.").passed


def test_course_code_next_to_a_word_in_a_table_cell_is_still_a_number_of_the_source():
    from campus247.rag_v2.types import Statement, Unit
    unit = Unit("a" * 16, ("c",), "d", "v", "t", "f", "page", "p", None,
                "PM PTKC trong TK cầu\nvà CTN\n160470 - 2\nHệ thống GT thông minh\n120332 - 3\n")
    verdict = check_statement(Statement("Học phần Hệ thống GT thông minh có mã 160470 và 2 tín chỉ.", (unit.unit_id,)),
                              {unit.unit_id: unit})
    assert verdict.passed, verdict.reasons


def test_swapped_negation_and_a_short_source_are_rejected():
    from campus247.rag_v2.types import Statement, Unit
    unit = Unit("b" * 16, ("c",), "d", "v", "t", "f", "page", "p", None, "Sinh viên không được nghỉ học và được dự thi.")
    for statement in ("Sinh viên được nghỉ học và không được dự thi.", "Sinh viên được nghỉ học."):
        verdict = check_statement(Statement(statement, (unit.unit_id,)), {unit.unit_id: unit})
        assert "NEGATION_MISMATCH" in verdict.reasons, statement
    ok = check_statement(Statement("Sinh viên không được nghỉ học.", (unit.unit_id,)), {unit.unit_id: unit})
    assert ok.passed


def test_negator_in_a_neighbouring_sentence_of_a_short_source_does_not_reject_a_restated_sentence():
    from campus247.rag_v2.verification.deterministic import _polarity_mismatch
    source = "sinh vien duoc bao luu. sinh vien khong duoc rut hoc phan."
    assert not _polarity_mismatch("sinh vien duoc bao luu", source)
    assert _polarity_mismatch("sinh vien khong duoc bao luu", source)
    assert _polarity_mismatch("sinh vien duoc rut hoc phan", source)



def test_the_year_of_a_referenced_decision_date_is_not_an_academic_year_claim():
    from campus247.rag_v2.types import Scope, Statement, Unit
    body = ("Quyết định này thay thế Quyết định số 960/QĐ-ĐHXDHN ngày 21 tháng 6 năm 2024 của Hiệu trưởng "
            "và áp dụng cho năm học 2026-2027.")
    unit = Unit("e" * 16, ("c",), "d", "v", "t", "f", "page", "p", None, body,
                scope=Scope(academic_years=("2026-2027",)))
    ok = check_statement(Statement("Quyết định thay thế Quyết định số 960/QĐ-ĐHXDHN ngày 21 tháng 6 năm 2024.",
                                   (unit.unit_id,)), {unit.unit_id: unit})
    assert ok.passed, ok.reasons
    wrong = check_statement(Statement("Quyết định áp dụng cho năm học 2024-2025.", (unit.unit_id,)),
                            {unit.unit_id: unit})
    assert "SCOPE_MISMATCH" in wrong.reasons
    bare = check_statement(Statement("Quyết định áp dụng cho năm 2024.", (unit.unit_id,)), {unit.unit_id: unit})
    assert "SCOPE_MISMATCH" in bare.reasons


def test_short_negated_phrase_elsewhere_in_a_long_row_does_not_reject_an_affirmative_restriction():
    source = ("Được phép làm các bài thực hành theo đúng chương trình học, chỉ được sử dụng phần mềm do giảng viên "
              "hướng dẫn chỉ định. Không được sử dụng máy tính vào các mục đích khác như chơi game, chat.")
    assert _check("Sinh viên chỉ được sử dụng phần mềm do giảng viên hướng dẫn chỉ định.", source).passed
    source = "Không truy nhập, mở các trang tin, thư điện tử không rõ nguồn gốc. Tài khoản quản trị phải tách biệt với tài khoản truy nhập của người dùng."
    assert _check("Tài khoản quản trị phải tách biệt với tài khoản truy nhập của người dùng.", source).passed


def test_dropped_three_word_negation_in_a_long_row_is_still_rejected():
    source = "Quy định chung về thi. " * 40 + "Sinh viên không được nghỉ học tạm thời trong học kỳ thi."
    assert "NEGATION_MISMATCH" in _check("Sinh viên được nghỉ học tạm thời trong học kỳ thi.", source).reasons
