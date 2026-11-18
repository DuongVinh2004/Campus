"""Answer first, then guide: per-scope answers, honest scope relaxation and server-built next steps."""
import pytest

from campus247.application.conversation.guidance_block import GUIDANCE_MARKER, render_guidance
from campus247.rag_v2.outcome.guidance import related_documents, scope_chips
from campus247.rag_v2.types import Scope
from campus247.rag_v2.understanding.analyze import analyze

from tests.rag_v2.test_service import FakeGateway, Reranker, UnitIndex, answer, unit

FEE = "Khóa K67 chương trình đại trà có mức học phí 580.500 đồng/tín chỉ."


def fee_unit(cohorts=("K67",), years=("2026-2027",), programs=(), uid="b" * 16):
    return unit(FEE, uid=uid, scope=Scope(cohorts=tuple(cohorts), programs=tuple(programs), academic_years=tuple(years)))


@pytest.mark.asyncio
async def test_fee_question_without_scope_is_answered_then_the_server_invites_narrowing():
    index = UnitIndex([fee_unit(), fee_unit(("K68",), uid="c" * 16)])
    gateway = FakeGateway(drafts=[[FEE]])
    result = await answer(question="Học phí bao nhiêu một tín chỉ?", gateway=gateway, index=index)
    assert result.kind == "partial" and result.statements and "580.500" in result.text
    assert "phụ thuộc vào khóa hoặc năm học" in result.partial_note and "ngành" in result.partial_note
    assert result.suggestions == ("K67",)  # tappable values come only from the sources that actually answered
    assert [r.request_id for r in gateway.requests][0] == "rag_v2_generation"  # it did not stop to ask first


@pytest.mark.asyncio
async def test_year_with_no_source_is_relaxed_and_the_difference_is_stated_before_the_answer():
    index = UnitIndex([fee_unit(years=("2026-2027",))])
    gateway = FakeGateway(drafts=[[FEE]])
    result = await answer(question="Học phí K67 năm học 2025-2026 là bao nhiêu?", gateway=gateway, index=index)
    assert result.kind == "partial" and "580.500" in result.text
    assert result.preface and "năm học 2025-2026" in result.preface and "năm học 2026-2027" in result.preface
    generation = next(r for r in gateway.requests if r.request_id == "rag_v2_generation")
    assert '"scope_relaxed": true' in "".join(item["content"] for item in generation.input_items)


@pytest.mark.asyncio
async def test_exact_scope_match_is_never_relaxed():
    index = UnitIndex([fee_unit(years=("2026-2027",))])
    result = await answer(question="Học phí K67 năm học 2026-2027 là bao nhiêu?", gateway=FakeGateway(drafts=[[FEE]]), index=index)
    assert result.preface is None


def test_scope_chips_prefer_newest_cohorts_programs_and_years():
    units = [fee_unit(("K65",)), fee_unit(("K69",), uid="d" * 16), fee_unit(("K67",), uid="e" * 16)]
    assert scope_chips(("cohort|academic_year",), units, limit=2) == ("K69", "K67")
    programmes = [unit(FEE, uid="f" * 16, scope=Scope(programs=("7480201", "Đại trà")))]
    assert scope_chips(("program",), programmes) == ("Công nghệ thông tin", "Đại trà")
    only_years = [fee_unit(cohorts=(), years=("2026-2027", "2025-2026"), uid="9" * 16)]
    assert scope_chips(("semester|academic_year",), only_years)[0] == "Học kỳ 1 năm học 2026-2027"


def test_related_documents_are_distinct_titles_only():
    a, b = unit(uid="1" * 16), unit(uid="2" * 16)
    assert related_documents([a, b, unit(uid="3" * 16)]) == ("Quy chế",)


def test_guidance_block_is_plain_bullets_and_never_leaks_slot_names():
    text = render_guidance(["K67", "Công nghệ thông tin", "cohort|academic_year", "K67", "  "])
    assert text == f"\n\n{GUIDANCE_MARKER}\n- K67\n- Công nghệ thông tin"
    assert render_guidance(["program", "semester"]) == ""


@pytest.mark.parametrize("question", ["Khi nào đóng học phí?", "học phí bao nhiêu vậy ad"])
def test_missing_slot_questions_carry_an_ask_back_instead_of_a_blocking_prompt(question):
    u = analyze(question, ())
    assert u.clarify_prompt is None and u.ask_back and u.missing_slots


def test_scope_chips_fall_back_to_cohorts_named_in_the_source_text():
    table = unit("Học phí K64 trở về trước là 580.500; từ K69 là 592.500 đồng/tín chỉ.", uid="8" * 16)
    assert scope_chips(("cohort|academic_year",), [table]) == ("K69", "K64")
