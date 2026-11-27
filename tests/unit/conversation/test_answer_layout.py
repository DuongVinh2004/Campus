"""Readable layout of grounded answers: same checked words, set out as paragraphs, lists and sections."""
from __future__ import annotations

import re
from dataclasses import replace

from campus247.agent.state import DraftResponse
from campus247.application.conversation.answer_layout import layout_claims, layout_grounded_draft, quote
from campus247.application.conversation.stream_result import prepare_chat_result
from campus247.application.retrieval.evidence_gate import GroundedClaim
from tests.unit.conversation.test_stream_result import grounded_state


def words(text: str) -> list[str]:
    return re.findall(r"\w+", re.sub(r"\[CIT-\d{3}\]", "", text))


def test_single_claim_stays_one_paragraph_with_key_values_bold():
    text = layout_claims([("Hạn nộp: từ ngày 29/9/2026 đến hết ngày 20/10/2026.", ["CIT-001"])])
    assert text == "Hạn nộp: từ ngày **29/9/2026** đến hết ngày **20/10/2026**. [CIT-001]"


def test_rows_of_values_become_one_list():
    claims = [("Chương trình CDIO, K64: 649.000 đồng/tín chỉ.", ["CIT-001"]),
              ("Chương trình KS/KTS (đã có bằng CN): 696.500 đồng/tín chỉ.", ["CIT-001"]),
              ("Đại học vừa làm vừa học: 964.500 đồng/tín chỉ.", ["CIT-002"])]
    text = layout_claims(claims)
    assert text.split("\n") == [
        "- Chương trình CDIO, K64: **649.000 đồng/tín chỉ**. [CIT-001]",
        "- Chương trình KS/KTS (đã có bằng CN): **696.500 đồng/tín chỉ**. [CIT-001]",
        "- Đại học vừa làm vừa học: **964.500 đồng/tín chỉ**. [CIT-002]"]


def test_narrative_answer_keeps_a_lead_paragraph_then_bullets():
    claims = [("Trạm y tế không khám chữa bệnh theo bảo hiểm y tế.", ["CIT-001"]),
              ("Không cần xuất trình thẻ BHYT khi khám tại Trạm.", ["CIT-001"]),
              ("Trạm không viết giấy chuyển viện theo BHYT.", ["CIT-002"])]
    lead, bullets = layout_claims(claims).split("\n\n")
    assert lead == "Trạm y tế không khám chữa bệnh theo bảo hiểm y tế. [CIT-001]"
    assert bullets.split("\n") == ["- Không cần xuất trình thẻ BHYT khi khám tại Trạm. [CIT-001]",
                                   "- Trạm không viết giấy chuyển viện theo BHYT. [CIT-002]"]


def test_short_label_is_bold_when_the_claim_has_no_key_value():
    assert layout_claims([("Sổ tay: không dùng chung mật khẩu.", ["CIT-001"])]) == (
        "**Sổ tay:** không dùng chung mật khẩu. [CIT-001]")


def test_parts_of_the_question_become_sections_in_the_users_words():
    claims = [("Đăng nhập sinhvien.huce.edu.vn để tự đánh giá.", ["CIT-001"]),
              ("Điểm rèn luyện dùng để xét học bổng.", ["CIT-001"]),
              ("Điểm rèn luyện dùng để xét lưu trú ký túc xá.", ["CIT-002"]),
              ("Kết quả được ghi vào bảng điểm.", ["CIT-002"])]
    groups = (("phải đăng nhập vào hệ thống nào", (0,)), ("được dùng để xét những việc gì ạ?", (1, 2)), ("", (3,)))
    text = layout_claims(claims, groups)
    assert text == ("### Phải đăng nhập vào hệ thống nào\n\n"
                    "Đăng nhập sinhvien.huce.edu.vn để tự đánh giá. [CIT-001]\n\n"
                    "### Được dùng để xét những việc gì\n\n"
                    "- Điểm rèn luyện dùng để xét học bổng. [CIT-001]\n"
                    "- Điểm rèn luyện dùng để xét lưu trú ký túc xá. [CIT-002]\n\n"
                    "### Thông tin liên quan\n\n"
                    "Kết quả được ghi vào bảng điểm. [CIT-002]")
    # Every claim word is shown, once and in order; only the headings are added.
    body = re.sub(r"^### .*$", "", text, flags=re.MULTILINE)
    assert words(body) == words(" ".join(claim for claim, _ in claims))


def test_parts_typed_without_diacritics_are_set_apart_without_headings():
    claims = [("Không cần xuất trình thẻ BHYT.", ["CIT-001"]), ("Bắt đầu từ nơi đăng ký KCB ban đầu.", ["CIT-001"])]
    text = layout_claims(claims, (("co can mang the bhyt ko", (0,)), ("bat dau o dau", (1,))))
    assert text == "Không cần xuất trình thẻ BHYT. [CIT-001]\n\nBắt đầu từ nơi đăng ký KCB ban đầu. [CIT-001]"


def test_heading_markup_from_the_question_is_escaped():
    claims = [("A có.", ["CIT-001"]), ("B có.", ["CIT-001"])]
    text = layout_claims(claims, (("học *phí* [x](y)", (0,)), ("lịch # thi", (1,))))
    assert "### Học \\*phí\\* \\[x\\](y)" in text and "### Lịch \\# thi" in text


def test_malformed_groups_fall_back_to_flat_layout():
    claims = [("A có.", ["CIT-001"]), ("B có.", ["CIT-001"])]
    for groups in [(("học phí", (0, 1)),), (("học phí", (7,)), ("lịch thi", (9,))), "bad", ((1, 2), (3, 4))]:
        assert layout_claims(claims, groups) == "- A có. [CIT-001]\n- B có. [CIT-001]"


def test_claim_text_cannot_open_its_own_block():
    text = layout_claims([("# Tiêu đề\nxuống dòng", ["CIT-001"]), ("- 1. mục", ["CIT-001"])])
    assert text == "- \\# Tiêu đề xuống dòng [CIT-001]\n- 1\\. mục [CIT-001]"


def test_claims_with_their_own_emphasis_are_not_marked_again():
    assert layout_claims([("Mức *mới* 580.500 đồng.", ["CIT-001"])]) == "Mức *mới* 580.500 đồng. [CIT-001]"


def test_draft_is_laid_out_only_when_its_text_is_exactly_its_claims():
    claims = (GroundedClaim("v2-1", "Học phí 580.500 đồng.", ("CIT-001",), "policy"),
              GroundedClaim("v2-2", "Hạn nộp 20/10/2026.", ("CIT-001",), "policy"))
    draft = DraftResponse("Học phí 580.500 đồng. [CIT-001]\nHạn nộp 20/10/2026. [CIT-001]", grounded_claims=claims)
    assert layout_grounded_draft(draft) == "- Học phí **580.500 đồng**. [CIT-001]\n- Hạn nộp **20/10/2026**. [CIT-001]"
    assert layout_grounded_draft(replace(draft, text=draft.text + " thêm")) is None
    assert layout_grounded_draft(replace(draft, grounded_claims=())) is None


def test_quote_marks_every_line():
    assert quote("Một.\n\nHai.") == "> Một.\n>\n> Hai."


def test_stream_result_lays_out_claims_and_quotes_server_notes():
    state = grounded_state()
    claims = (GroundedClaim("v2-1", "Synthetic supported policy.", ("CIT-001",), "policy"),
              GroundedClaim("v2-2", "Synthetic second rule.", ("CIT-001",), "policy"))
    state = replace(state, errors=("AI_PARTIAL_COVERAGE",), draft=replace(
        state.draft, text="Synthetic supported policy. [CIT-001]\nSynthetic second rule. [CIT-001]",
        grounded_claims=claims, preface="Nguồn áp dụng cho K69.", partial_note="Chưa đủ căn cứ cho phần còn lại."))
    result = prepare_chat_result(state)
    assert result.response_class == "partial_answer" and len(result.citations) == 1
    assert result.content == ("> Nguồn áp dụng cho K69.\n\n"
                              "Dữ liệu mô phỏng; không phải quy định chính thức.\n\n"
                              "- Synthetic supported policy. [CIT-001]\n- Synthetic second rule. [CIT-001]\n\n"
                              "> Chưa đủ căn cứ cho phần còn lại.")


def test_stream_result_keeps_text_without_claims_as_before():
    result = prepare_chat_result(grounded_state())
    assert result.content == "Dữ liệu mô phỏng; không phải quy định chính thức.\nSynthetic supported policy. [CIT-001]"
