import pytest
from campus247.application.knowledge.colloquial import expand_colloquial


@pytest.mark.parametrize("question,expected", [
    ("đk học phần cần lưu ý j ko", "đăng ký học phần cần lưu ý gì không"),
    ("bị đuổi học khi nào v ạ", "bị buộc thôi học khi nào v ạ"),
    ("rút môn đc đến khi nào", "rút học phần được đến khi nào"),
    ("điểm rl tính ntn z", "điểm rèn luyện tính như thế nào z"),
    ("học phí 1 tc năm 26-27 bao nhiêu", "học phí 1 tín chỉ năm 2026-2027 bao nhiêu"),
    ("hk2 sv K64 đóng bao nhiêu", "học kỳ 2 sinh viên K64 đóng bao nhiêu"),
    ("rớt môn học lại thì điểm tính sao", "không đạt học phần học lại thì điểm tính sao"),
    ("ktx ở đâu", "ký túc xá ở đâu"),
])
def test_common_shorthand_is_expanded_in_place(question, expected):
    assert expand_colloquial(question) == expected


@pytest.mark.parametrize("question", [
    "Sinh viên đăng ký học phần như thế nào?",
    "Theo Quyết định 924/QĐ-ĐHXDHN, học phí K64 kỹ sư là bao nhiêu?",
    "Môn học nào là tiên quyết của 428802?",
    "Điều 14 khoản 1 quy định gì? Học kỳ 2 năm 2026-2027",
    "hp là gì",
    "Phiên bản 12-13 của biểu mẫu",
    "Nộp trước ngày 05/06 nhé",
    "Số hiệu 12/QĐ-ĐHXDHN và 5-sv",
    "tcvn và sv123 là mã",
])
def test_formal_text_and_ambiguous_tokens_are_left_alone(question):
    assert expand_colloquial(question) == question
