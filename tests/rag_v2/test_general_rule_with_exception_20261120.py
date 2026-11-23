"""A statement that gives the general rule and then one exception naming another programme is still a general rule.

Found by held-out set 2 (tt-06): "Sinh viên ngành Cầu đường thực tập tối thiểu bao nhiêu tuần?" against a document that says 8 weeks for
everybody and 10 weeks for Kiến trúc. The generated statement named Kiến trúc, so the check treated the whole statement as being about that
other programme and judged it against the full question, which mentions a programme the document does not. Only a statement in which EVERY
clause names a major is about those majors.
"""
import pytest

from campus247.rag_v2.scope_terms import names_only_other_majors
from campus247.rag_v2.vocabulary import Vocabulary

VOCAB = Vocabulary(majors=frozenset({"kien truc", "cong nghe thong tin", "ky thuat dien"}))


@pytest.mark.parametrize("text,expected", [
    ("Thời gian thực tập tối thiểu là 8 tuần liên tục; sinh viên ngành Kiến trúc thực tập tối thiểu 10 tuần.", False),
    ("Học phí chung là 17.000.000 đồng/năm. Ngành Kiến trúc là 18.000.000 đồng/năm.", False),
    ("Ngành Kiến trúc đóng 18.000.000 đồng/năm; ngành Kỹ thuật điện đóng 19.000.000 đồng/năm.", True),
    ("Sinh viên ngành Kiến trúc thực tập tối thiểu 10 tuần.", True),
    ("Thời gian thực tập tối thiểu là 8 tuần liên tục.", False),
    ("", False),
])
def test_only_a_statement_whose_every_clause_names_a_major_is_about_those_majors(text, expected):
    assert names_only_other_majors(text, VOCAB) is expected
