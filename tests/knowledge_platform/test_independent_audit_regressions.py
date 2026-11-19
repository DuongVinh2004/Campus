"""Regressions from real HUCE audit failures; live campaign is separate."""
import json

import pytest

from campus247.application.retrieval.material_support import support_issues
from campus247.application.retrieval.material_support import applicable_fee_row_ranges
from campus247.application.knowledge.question_scope import focused_source_question
from campus247.application.knowledge.question_scope import tuition_answer_scope_issue
from campus247.application.retrieval.evidence_gate import GroundedDraft, GroundedClaim
from campus247.application.conversation.followup import prepare_followup_question
from campus247.application.conversation.history import HistoryContext
from campus247.application.conversation.context import TurnItem

TABLE = """Mức học phí (đồng)/tín chỉ (ĐVHT)
I. Đại học hệ chính quy
1 | Chương trình kỹ sư (KS) chính quy | K64 trở về trước | 580.500
2 | Chương trình Kỹ sư/kiến trúc sư (KTS) đào tạo theo tiếp cận CDIO | K64 | 649.000
3 | Chương trình Kỹ sư chất lượng cao | K66 trở về trước (ĐVHT) | 336.000
3 | Chương trình Kỹ sư chất lượng cao | Từ K67 | 533.000
4 | Chương trình Cử nhân (CN), Tích hợp CN - KS/KTS | K65 đến K68 | 592.500
5 | Chương trình CN | Từ K69 | 592.500
6 | Chương trình KS/KTS | Từ K69 | 547.000
II. Đại học vừa làm vừa học
1 | Chương trình cấp bằng cử nhân | | 964.500
2 | Chương trình cấp bằng kỹ sư, kiến trúc sư | | 870.500"""


@pytest.mark.parametrize("claim,issue", [
    ("Học phí kỹ sư chính quy K64 là 649.000 đồng/tín chỉ.", "CONTRADICTED_TABLE_ROW"),
    ("Học phí kỹ sư chính quy K64 là 547.000 đồng/tín chỉ.", "CONTRADICTED_TABLE_ROW"),
    ("Học phí kỹ sư chính quy K64 là 580.500 đồng/tín chỉ (ĐVHT).", "CONTRADICTED_UNIT"),
    ("Học phí kỹ sư chất lượng cao từ K67 là 533.000 đồng/ĐVHT.", "CONTRADICTED_UNIT"),
    ("Học phí tích hợp CN - KS/KTS K71 là 592.500 đồng/tín chỉ.", "CONTRADICTED_TABLE_ROW"),
])
def test_table_cannot_union_unrelated_rows(claim, issue):
    assert issue in support_issues(claim, TABLE)


@pytest.mark.parametrize("claim", [
    "Học phí kỹ sư chính quy K64 là 580.500 đồng/tín chỉ.",
    "Học phí kỹ sư CDIO K64 là 649.000 đồng/tín chỉ.",
    "Học phí kỹ sư chất lượng cao K66 là 336.000 đồng/ĐVHT.",
    "Học phí kỹ sư chất lượng cao từ K67 là 533.000 đồng/tín chỉ.",
    "Học phí cử nhân K71 là 592.500 đồng/tín chỉ.",
    "Học phí đại học vừa làm vừa học cấp bằng cử nhân là 964.500 đồng/tín chỉ.",
])
def test_correct_table_rows_still_pass(claim):
    assert support_issues(claim, TABLE) == ()


def test_reference_preamble_is_not_the_search_subject():
    q = "Theo quy chế an toàn thông tin HUCE QĐ 2114, người dùng phải đổi mật khẩu bao lâu một lần?"
    assert focused_source_question(q) == "người dùng phải đổi mật khẩu bao lâu một lần?"
    for value in ("Theo QĐ 924 năm 2026, học phí bao nhiêu?", "Theo hệ kỹ sư K64, học phí bao nhiêu?",
                  "Theo nội quy phòng máy HUCE, máy hỏng báo cho ai?"):
        assert focused_source_question(value) == value


def test_followup_retains_user_scope_answer_and_ignores_assistant_amounts():
    history = HistoryContext("audit", "conversation", (
        TurnItem("1", "user", "Cho biết học phí CNTT của HUCE?"),
        TurnItem("2", "assistant", "Bạn học khóa nào? K70 là 99.000.000 đồng."),
        TurnItem("3", "user", "Cử nhân chính quy K71, năm học 2026-2027.")), 100, "test")
    result = prepare_followup_question("Còn phụ thu Anh ngữ cho khóa đó thì sao?", history=history)
    assert result is not None
    reference = json.loads(result)["reference_target"]["prior_user_goal"]
    assert "học phí" in reference and "K71" in reference and "2026-2027" in reference
    assert "99.000.000" not in reference and "K70" not in reference


def test_scope_answer_itself_resolves_to_the_prior_tuition_goal():
    history = HistoryContext("audit", "conversation", (TurnItem("1", "user", "Học phí CNTT HUCE?"),), 50, "test")
    result = prepare_followup_question("Cử nhân chính quy K71, năm học 2026-2027.", history=history)
    assert result is not None and "Học phí CNTT" in result and "K71" in result


@pytest.mark.parametrize("answer,expected", [
    ("Cử nhân K65 đến K68 thu 592.500 đồng/tín chỉ.", "AI_QUESTION_SCOPE_MISMATCH"),
    ("Cử nhân từ K69 thu 592.500 đồng/tín chỉ.", None),
    ("Cử nhân K71 thu 592.500 đồng/tín chỉ.", None),
])
def test_correct_amount_for_wrong_cohort_is_not_an_answer(answer, expected):
    draft = GroundedDraft(answer, (GroundedClaim("one", answer, ("CIT-001",), "fee"),))
    assert tuition_answer_scope_issue("Học phí CNTT?\nCử nhân chính quy K71, năm học 2026-2027.", draft) == expected


def test_table_prompt_keeps_exact_header_and_only_the_applicable_row():
    ranges = applicable_fee_row_ranges(TABLE, "Học phí CNTT? Cử nhân chính quy K71, năm học 2026-2027.")
    assert ranges is not None
    spans = [TABLE[start:end] for start, end in ranges]
    assert spans[0].startswith("Mức học phí")
    assert spans[1] == "I. Đại học hệ chính quy\n"
    assert spans[2] == "5 | Chương trình CN | Từ K69 | 592.500\n"
    assert applicable_fee_row_ranges(TABLE, "Học phí và phụ thu Anh ngữ cử nhân K71?") is None
    assert applicable_fee_row_ranges(TABLE, "So sánh học phí K66 và K67?") is None
