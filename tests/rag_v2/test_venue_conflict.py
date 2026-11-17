"""A source for one place must not answer a question about another place."""
from types import SimpleNamespace

import pytest

from campus247.rag_v2.verification.venue import venue_conflict


def unit(path: str, text: str):
    return SimpleNamespace(path=path, text=text)


LAB = unit("Nội quy Phòng thực hành máy tính > 3", "Không được sử dụng điện thoại di động trong phòng máy.")
EXAM = unit("Quy chế thi > Điều 9", "Thí sinh không mang điện thoại vào phòng thi.")
GENERIC = unit("Quy chế đào tạo > Điều 5", "Sinh viên đăng ký học phần đúng hạn.")
BOTH = unit("Nội quy > 1", "Phòng thi và phòng máy đều cấm điện thoại.")


@pytest.mark.parametrize("question,cited,expected", [
    ("Dùng điện thoại trong phòng thi có bị đình chỉ không?", [LAB], True),
    ("Dùng điện thoại trong phòng thi có bị đình chỉ không?", [EXAM], False),
    ("Dùng điện thoại trong phòng thi có bị đình chỉ không?", [LAB, EXAM], False),
    ("Dùng điện thoại trong phòng thi có bị đình chỉ không?", [BOTH], False),
    ("Dùng điện thoại trong phòng thi có bị đình chỉ không?", [GENERIC], False),
    ("Học phí K69 là bao nhiêu?", [LAB], False),
    ("Thư viện mở cửa mấy giờ?", [LAB], True),
    ("Dùng điện thoại trong phòng máy được không?", [LAB], False),
    ("Dùng điện thoại trong phòng thi có bị đình chỉ không?", [], False),
])
def test_venue_conflict(question, cited, expected):
    assert venue_conflict(question, cited) is expected
