"""A phrase that follows a negator in one clause and an affirmative in another is not a dropped negation."""
from campus247.rag_v2.verification.deterministic import _polarity_mismatch, _fold

SOURCE = ("Số lần cảnh báo học tập vượt quá 2 lần liên tiếp; hoặc quá 4 lần không liên tiếp đối với chương trình "
          "đào tạo trình độ cử nhân hoặc vượt quá 2 lần liên tiếp đối với chương trình đào tạo chuyên sâu.")


def mismatch(statement, source=SOURCE):
    return _polarity_mismatch(_fold(statement), _fold(source))


def test_restating_both_clauses_is_not_a_polarity_mismatch():
    assert not mismatch("Sinh viên bị buộc thôi học khi cảnh báo học tập vượt quá 2 lần liên tiếp hoặc quá 4 lần "
                        "không liên tiếp đối với chương trình đào tạo trình độ cử nhân.")


def test_statement_spanning_semicolon_clauses_keeps_its_negator():
    source = ("a) Số lần cảnh báo học tập hoặc mức cảnh báo học tập vượt quá 2 lần liên\ntiếp; hoặc quá 4 lần không "
              "liên tiếp đối với chương trình cử nhân\nhoặc vượt quá 2 lần liên tiếp đối với chương trình kỹ sư.")
    assert not mismatch("Sinh viên bị buộc thôi học khi cảnh báo học tập vượt quá 2 lần liên tiếp; hoặc quá 4 lần "
                        "không liên tiếp đối với chương trình cử nhân.", source)


def test_a_negator_the_row_never_states_there_is_still_rejected():
    source = "Sinh viên được đăng ký tối đa 24 tín chỉ. Sinh viên được rút học phần trước tuần 5."
    assert mismatch("Sinh viên không được rút học phần trước tuần 5.", source)


def test_a_dropped_negator_is_still_caught_when_the_row_only_states_it_negated():
    source = "Sinh viên không được đăng ký học phần tự chọn khi chưa hoàn thành học phần tiên quyết."
    assert mismatch("Sinh viên được đăng ký học phần tự chọn khi chưa hoàn thành.", source)


def test_an_added_negator_is_still_caught():
    assert mismatch("Sinh viên không bị buộc thôi học khi vượt quá 2 lần liên tiếp.")


def test_punctuation_between_a_negator_and_its_object_changes_nothing():
    source = "5. Cấm: mang các vật dễ cháy, nổ, nước uống, thức ăn, hút thuốc lá. Giữ gìn vệ sinh chung."
    assert not mismatch("Cấm mang nước uống và thức ăn vào phòng máy.", source)
    assert mismatch("Được mang nước uống vào phòng máy.", source)          # the negation is dropped
    assert mismatch("Không cấm mang nước uống vào phòng máy.", source)     # a negation is added
