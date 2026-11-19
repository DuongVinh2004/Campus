"""Behavioral regressions; model fakes here do not establish live RAG quality."""
import json
from dataclasses import replace

import pytest
from campus247.agent.nodes.definitions import (
    grounded_request,
    retrieval_query,
    route_intent_node,
)
from campus247.agent.state import AgentState, NormalizedTurn, Route, Terminal
from campus247.application.conversation.context import TurnItem
from campus247.application.conversation.history import HistoryContext
from campus247.application.retrieval.citations import CitationBundle
from campus247.application.retrieval.evidence_gate import (
    EvidenceGate,
    parse_grounded_claims,
)
from campus247.application.retrieval.structure import structured_spans


def state(question, *goals):
    history = HistoryContext("actor", "session", tuple(TurnItem(str(i), role, text)
        for i, (role, text) in enumerate(goals)), 100, "test") if goals else None
    return AgentState(NormalizedTurn("session", "turn", "actor", question, history=history))


def test_elliptical_followups_keep_topic_and_new_conditions_without_assistant_facts():
    turn = state("Còn năm nhất thì sao?", ("user", "Điều kiện xét học bổng?"),
                 ("assistant", "UNTRUSTED_FACT 999 điểm"))
    query = retrieval_query(turn)
    assert "học bổng" in query and "năm nhất" in query and "UNTRUSTED_FACT" not in query
    second = state("Vậy GPA cần bao nhiêu?", ("user", "Điều kiện xét học bổng?"),
                   ("user", "Còn năm nhất thì sao?"))
    assert "năm nhất" in retrieval_query(second) and "học bổng" in retrieval_query(second)


def test_topic_switch_does_not_retrieve_previous_topic():
    turn = state("Còn học phí thì bao nhiêu?", ("user", "Điều kiện xét học bổng?"))
    assert retrieval_query(turn) == turn.request.query


@pytest.mark.parametrize("question", ["Bạn giúp được gì?", "ban co the lam gi", "Còn năm nhất thì sao?"])
def test_capabilities_and_ambiguous_reference_do_not_require_retrieval(question):
    result = route_intent_node(state(question))
    assert result.terminal == Terminal.ABSTAINED and "AI_CLARIFICATION_REQUIRED" in result.errors
    assert result.draft and result.draft.text and "[CIT-" not in result.draft.text


def test_personal_schedule_question_is_not_document_search():
    assert route_intent_node(state("Lịch học của tôi?")).route == Route.PERSONAL_SCHEDULE
    assert route_intent_node(state("Quy định xếp lịch học là gì?")).route == Route.GROUNDED_FAQ


@pytest.mark.parametrize("question", ["Điểm D có phải học lại không?", "Nếu em ốm đúng ngày thi thì xin hoãn thế nào?"])
def test_self_contained_questions_are_not_mistaken_for_ambiguous_followups(question):
    assert route_intent_node(state(question)).terminal is None


def test_library_aliases_do_not_trigger_redundant_multi_topic_search():
    from campus247.application.conversation.understanding import retrieval_subqueries
    assert len(retrieval_subqueries("Phòng tự học thư viện ở đâu?")) == 1


@pytest.mark.parametrize("reason,expected", [
    ("AI_GENERATION_INVALID_SCHEMA", "định dạng"), ("AI_GENERATION_TIMEOUT", "quá chậm")])
def test_generation_failures_have_truthful_persistable_response_without_citations(reason, expected):
    from campus247.agent.state import DraftResponse
    from campus247.application.conversation.stream_result import prepare_chat_result
    value = replace(state("Học bổng?"), terminal=Terminal.SAFE_FAILURE,
        errors=("AI_GENERATION_UNAVAILABLE", reason), draft=DraftResponse("rejected raw draft"))
    result = prepare_chat_result(value)
    assert result.status == "abstained" and result.response_class == "safe_refusal"
    assert expected in result.content and "raw draft" not in result.content and not result.citations


@pytest.mark.parametrize("claim", ["GPA tối thiểu là 3.0.", "GPA phải lớn hơn 2.0.",
    "Sinh viên được tự ý đổi chỗ ở trong ký túc xá."])
def test_citation_and_high_word_overlap_cannot_validate_wrong_numbers_thresholds_or_negation(claim):
    source = "GPA tối thiểu là 2.0.\nSinh viên không được tự ý đổi chỗ ở trong ký túc xá."
    bundle = CitationBundle.build([{"source_id": "test-source", "chunk_id": "test-chunk", "content_text": source}])
    draft = parse_grounded_claims(json.dumps({"claims": [{"text": claim, "citation_ids": ["CIT-001"], "claim_type": "policy"}]}))
    assert not EvidenceGate(.25).verify(draft, bundle).passed


def test_correct_rule_and_equivalent_decimal_notation_still_pass():
    source = "GPA tối thiểu là 2,0. Sinh viên không được tự ý đổi chỗ ở."
    bundle = CitationBundle.build([{"source_id": "s", "chunk_id": "c", "content_text": source}])
    draft = parse_grounded_claims("GPA tối thiểu là 2.0 [CIT-001]")
    assert EvidenceGate(.78).verify(draft, bundle).passed


def test_working_days_cannot_be_silently_changed_into_calendar_days():
    bundle = CitationBundle.build([{"source_id": "s", "chunk_id": "c", "content_text": "Thời hạn là 10 ngày làm việc."}])
    assert not EvidenceGate(.25).verify(parse_grounded_claims("Thời hạn là 10 ngày [CIT-001]"), bundle).passed
    assert EvidenceGate(.78).verify(parse_grounded_claims("Thời hạn là 10 ngày làm việc [CIT-001]"), bundle).passed


def test_obligation_for_grade_f_does_not_reverse_the_passing_rule_for_grade_d():
    from campus247.application.retrieval.material_support import support_issues
    source = "Điểm D là loại đạt. Sinh viên điểm F phải học lại."
    assert not support_issues("Điểm D không phải học lại.", source)
    assert "CONTRADICTED_POLARITY" in support_issues("Sinh viên điểm F không phải học lại.", source)


def test_permission_to_improve_grade_d_does_not_impose_mandatory_retake():
    from campus247.application.retrieval.material_support import support_issues
    source = "Sinh viên có điểm D được đăng ký học lại để cải thiện điểm."
    assert not support_issues("Sinh viên có điểm D không phải học lại.", source)
    assert "CONTRADICTED_POLARITY" in support_issues("Sinh viên có điểm D không được đăng ký học lại để cải thiện điểm.", source)


@pytest.mark.parametrize("positive,negative", [
    ("phải học lại", "không phải học lại"), ("cần đăng ký học lại", "không cần đăng ký học lại"),
    ("được đăng ký học lại", "không được đăng ký học lại"), ("đạt yêu cầu", "không đạt yêu cầu"),
    ("đủ điều kiện", "chưa đủ điều kiện"),
])
def test_reversed_polarity_of_the_same_predicate_still_fails(positive, negative):
    from campus247.application.retrieval.material_support import support_issues
    assert "CONTRADICTED_POLARITY" in support_issues(f"Sinh viên {negative}.", f"Sinh viên {positive}.")


def test_year_one_credit_exception_keeps_equality_instead_of_a_minimum():
    from campus247.application.retrieval.material_support import support_issues
    source = ("Số tín chỉ học phần đăng ký học và thi trong kỳ tối thiểu 15 tín chỉ; "
        "Hoặc bằng số tín chỉ tối đa mở cho sinh viên năm nhất trong học kỳ I.")
    correct = "Sinh viên năm nhất trong học kỳ I đăng ký học và thi bằng số tín chỉ tối đa mở cho sinh viên năm nhất trong học kỳ I."
    assert not support_issues(correct, source)
    assert "CONTRADICTED_THRESHOLD" in support_issues(correct.replace("bằng số", "tối thiểu bằng số"), source)
    assert "CONTRADICTED_THRESHOLD" in support_issues(correct.replace("bằng số", "tối đa bằng số"), source)


@pytest.mark.parametrize("source_id,section", [
    ("038ade6c-24dc-75cc-899f-04635544af2e", "Trang 110"),
    ("672d3a51-085e-7a46-818c-d741c4f05af9", "Điều 9. Đánh giá và tính điểm học phần"),
])
def test_swap_course_condition_is_required_from_real_source_but_not_for_sibling_retake(source_id, section):
    from pathlib import Path

    from campus247.infrastructure.retrieval.public_knowledge import PublicKnowledgeStore
    matches = [row for row in PublicKnowledgeStore(Path(__file__).resolve().parents[3] / "data/huce-public-20261013",
        tenant_id="HUCE", campus_id="HUCE").rows if row["source_id"] == source_id and row["section_path"] == section]
    assert len(matches) == 1
    source = matches[0]
    omitted = ("Sinh viên đã có điểm học phần đạt thì được đăng ký học lại hoặc học đổi sang học phần khác "
        "để cải thiện điểm trung bình chung tích lũy cuối khóa.")
    qualifier = " (là học phần tương đương hoặc thay thế trong trường hợp học phần bắt buộc)"
    preserved = omitted.replace("học phần khác", "học phần khác" + qualifier)
    bundle = CitationBundle.build([source])
    rejected = EvidenceGate(.78).verify(parse_grounded_claims(json.dumps({"claims": [
        {"text": omitted, "citation_ids": ["CIT-001"], "claim_type": "policy"}]})), bundle)
    accepted = EvidenceGate(.78).verify(parse_grounded_claims(json.dumps({"claims": [
        {"text": preserved, "citation_ids": ["CIT-001"], "claim_type": "policy"}]})), bundle)
    assert not rejected.passed and rejected.diagnostics[0]["reason_code"] == "MISSING_MATERIAL_CONDITION"
    assert accepted.passed
    sibling = omitted.replace(" hoặc học đổi sang học phần khác", "")
    assert EvidenceGate(.78).verify(parse_grounded_claims(json.dumps({"claims": [
        {"text": sibling, "citation_ids": ["CIT-001"], "claim_type": "policy"}]})), bundle).passed


def test_parenthetical_swap_condition_does_not_restrict_standalone_grade_or_retake_statement():
    from campus247.application.retrieval.material_support import support_issues
    source = ("Điểm D là loại đạt. Sinh viên có điểm D không phải học lại. "
        "Sinh viên được học lại hoặc học đổi sang học phần khác "
        "(là học phần tương đương hoặc thay thế trong trường hợp học phần bắt buộc).")
    assert not support_issues("Điểm D là loại đạt.", source)
    assert not support_issues("Sinh viên có điểm D không phải học lại.", source)


def test_actual_grade_table_keeps_passing_d_outside_failed_course_retake_obligation():
    from pathlib import Path

    from campus247.application.retrieval.material_support import support_issues
    from campus247.infrastructure.retrieval.public_knowledge import PublicKnowledgeStore
    matches = [row for row in PublicKnowledgeStore(Path(__file__).resolve().parents[3] / "data/huce-public-20261013",
        tenant_id="HUCE", campus_id="HUCE").rows if row["source_id"] == "672d3a51-085e-7a46-818c-d741c4f05af9"
        and row["section_path"] == "Điều 9. Đánh giá và tính điểm học phần"]
    assert len(matches) == 1
    source = matches[0]
    assert not support_issues("Sinh viên có điểm D không phải học lại.", source["content_text"])
    assert "CONTRADICTED_POLARITY" in support_issues("Sinh viên có điểm F không phải học lại.", source["content_text"])


def test_ocr_comparator_joins_preserve_complete_decimals_and_do_not_read_identifier_tails():
    from decimal import Decimal

    from campus247.application.retrieval.material_support import quantities
    assert quantities("từ4,0 đến4,9") == [(Decimal("4.0"), "ge"), (Decimal("4.9"), "le")]
    assert quantities("từ7,0đến7,9") == [(Decimal("7.0"), "ge"), (Decimal("7.9"), "le")]
    assert quantities("REF4,0") == []


@pytest.mark.parametrize("claim,passed", [
    ("Điểm D từ 4,0 đến 4,9 là loại đạt.", True),
    ("Điểm D từ 4.0 trở lên là loại đạt.", True),
    ("Điểm D (4.0–4.9) là loại đạt.", True),
    ("Điểm D dưới 4,0 là loại đạt.", False),
    ("Điểm D lớn hơn 4,0 đến 4,9 là loại đạt.", False),
    ("Điểm D từ 4,0 đến dưới 4,9 là loại đạt.", False),
    ("Điểm D từ 5,0 đến 5,4 là loại đạt.", False),
    ("Điểm D (4.0–5.4) là loại đạt.", False),
    ("Điểm D+ từ 5,0 đến 5,4 là loại đạt.", True),
    ("Điểm D+ từ 4,0 đến 4,9 là loại đạt.", False),
    ("Điểm F ít nhất 4,0 là loại không đạt.", False),
    ("Điểm F từ 4,0 trở lên là loại không đạt.", False),
])
def test_grade_range_uses_actual_matching_row_and_preserves_endpoint_and_grade_scope(claim, passed):
    from pathlib import Path

    from campus247.application.retrieval.material_support import support_issues
    from campus247.infrastructure.retrieval.public_knowledge import PublicKnowledgeStore
    matches = [row for row in PublicKnowledgeStore(Path(__file__).resolve().parents[3] / "data/huce-public-20261013",
        tenant_id="HUCE", campus_id="HUCE").rows if row["source_id"] == "672d3a51-085e-7a46-818c-d741c4f05af9"
        and row["section_path"] == "Điều 9. Đánh giá và tính điểm học phần"]
    assert len(matches) == 1
    source = matches[0]
    assert (not support_issues(claim, source["content_text"])) is passed


def test_grade_ranges_are_not_mixed_between_cited_sources():
    first = "Điểm học phần. Loại đạt:\nD: từ4,0 đến4,9."
    second = "Điểm học phần. Loại đạt:\nD: từ5,0 đến5,9."
    bundle = CitationBundle.build([{"source_id": "first", "chunk_id": "first", "content_text": first},
        {"source_id": "second", "chunk_id": "second", "content_text": second}])
    def check(text, refs):
        return EvidenceGate(.78).verify(parse_grounded_claims(json.dumps({"claims": [
            {"text": text, "citation_ids": refs, "claim_type": "policy"}]})), bundle)
    assert check("Điểm D từ 4,0 đến 4,9 là loại đạt.", ["CIT-001"]).passed
    assert not check("Điểm D từ 4,0 đến 4,9 là loại đạt.", ["CIT-002"]).passed
    assert not check("Điểm D từ 4,0 đến 5,9 là loại đạt.", ["CIT-001", "CIT-002"]).passed


def test_credit_and_gpa_conditions_keep_existing_numeric_guards_when_a_grade_is_mentioned():
    from campus247.application.retrieval.material_support import support_issues
    source = "Loại đạt:\nD: từ4,0 đến4,9.\nGPA tối thiểu 2,0. Số tín chỉ tối thiểu 15 tín chỉ."
    assert not support_issues("Sinh viên có điểm D cần GPA tối thiểu 2,0.", source)
    assert "CONTRADICTED_THRESHOLD" in support_issues("Sinh viên có điểm D cần GPA lớn hơn 2,0.", source)
    assert not support_issues("Sinh viên có điểm D đăng ký tối thiểu 15 tín chỉ.", source)
    assert "UNSUPPORTED_QUANTITY" in support_issues("Sinh viên có điểm D đăng ký tối thiểu 30 tín chỉ.", source)


def test_source_spans_preserve_offsets_complete_sentences_and_table_rows():
    source = ("Điều kiện học bổng.\n\n" + "Sinh viên cần điểm học tập và điểm rèn luyện. " * 8
              + "\n| GPA | Điểm rèn luyện |\n| 3.2 | 80 |\nNgoại lệ áp dụng cho năm thứ nhất.")
    spans = structured_spans(source, max_chars=160, overlap_chars=45)
    assert len(spans) > 1 and all(source[s.start:s.end] == s.text for s in spans)
    assert any("| 3.2 | 80 |" in s.text for s in spans)
    assert any("Ngoại lệ áp dụng cho năm thứ nhất." in s.text for s in spans)
    assert all(len(s.text) <= 160 for s in spans)


def test_history_scope_checked_before_evidence_access():
    turn = state("Còn năm nhất?", ("user", "Điều kiện học bổng?"))
    wrong = replace(turn, request=replace(turn.request, history=replace(turn.request.history, actor_id="other")))
    with pytest.raises(ValueError, match="history scope mismatch"):
        grounded_request(wrong, object())
