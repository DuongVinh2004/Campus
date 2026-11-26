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


def test_a_negator_before_a_colon_governs_every_item_of_its_list():
    source = ("6. Trang phục gọn gàng, lịch sự, tư thế ngồi học phải ngay ngắn, nghiêm túc. Không: nói chuyện, đi lại tự do, "
              "sử dụng điện thoại di động, sử dụng máy tính xách tay.")
    assert not mismatch("Trong giờ thực hành, không được sử dụng điện thoại di động và máy tính xách tay trong phòng máy.", source)
    assert not mismatch("Không được nói chuyện trong phòng máy.", source)
    assert mismatch("Không được mặc trang phục gọn gàng.", source)        # not an item of the list
    assert mismatch("Được sử dụng máy tính xách tay.", source)             # the negation is dropped


def test_words_that_only_look_like_a_negator_once_folded_are_not_negators():
    from campus247.rag_v2.verification.deterministic import _polarity_fold

    def folded_mismatch(statement, source):
        return _polarity_mismatch(_polarity_fold(statement), _polarity_fold(source))
    card = ("30. THẺ SINH VIÊN ĐƯỢC SỬ DỤNG NHƯ THẾ NÀO?\nCấp thẻ sinh viên\nsau khi nhập học\nHết hạn khi tốt\nnghiệp\n"
            "Tích hợp với thẻ thư viện Chứa đựng thông tin\ncá nhân")
    assert not folded_mismatch("Thẻ sinh viên được cấp sau khi nhập học.", card)          # "Chứa" is not "chưa"
    assert not folded_mismatch("Sinh viên ở nội trú được cấp thẻ ra vào.", "Sinh viên ở nội trú được cấp thẻ ra vào ký túc xá.")
    assert not folded_mismatch("Dữ liệu được lưu trữ 5 năm.", "Dữ liệu được lưu trữ 5 năm kể từ ngày nộp.")
    # The real negators keep working, with or without diacritics.
    assert folded_mismatch("Thẻ sinh viên được cấp sau khi nhập học.", "Thẻ sinh viên chưa được cấp sau khi nhập học.")
    assert folded_mismatch("Sinh viên được mang nước uống.", "Cấm mang nước uống.")
    assert folded_mismatch("Sinh vien duoc mang nuoc uong.", "Cam mang nuoc uong.")
    assert folded_mismatch("Sinh viên được miễn học phí.", "Sinh viên được miễn học phí, trừ sinh viên học lại.")
