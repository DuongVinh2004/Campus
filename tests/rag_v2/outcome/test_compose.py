from dataclasses import replace

import pytest
from campus247.rag_v2.generation.contacts import contact_map
from campus247.rag_v2.outcome.compose import (
    PARTIAL_NOTE,
    REFUSAL_MESSAGES,
    build_outcome,
)
from campus247.rag_v2.types import Statement, Understanding, Unit
from campus247.rag_v2.verification.deterministic import check_statement

UNDERSTANDING = Understanding("Học phí?", "học phí", (), None, None, None, "number", (), (), None)
SOURCE = Unit("a", ("chunk-a",), "doc", "v1", "Học phí", "fee", "clause", "Điều 1", 2,
              "Học phí 580.500 đồng.")
UNITS = {"a": SOURCE}


def verdict(text=SOURCE.text):
    return check_statement(Statement(text, ("a",)), UNITS)


def test_answer_preserves_verified_words_and_exact_citation():
    result = build_outcome(UNDERSTANDING, [verdict()], UNITS, semantic_results=[True])
    assert result.kind == "answer" and result.text == SOURCE.text
    citation, = result.citations
    assert citation.quote in SOURCE.text and "580.500" in citation.quote
    assert (citation.chunk_ids, citation.document_id, citation.version_id, citation.path, citation.page) == (
        SOURCE.chunk_ids, SOURCE.document_id, SOURCE.version_id, SOURCE.path, SOURCE.page)


@pytest.mark.parametrize("kwargs", [{}, {"semantic_results": [False]}, {"semantic_results": []},
                                     {"semantic_results": [1]}])
def test_semantic_required_defaults_to_fail_closed(kwargs):
    result = build_outcome(UNDERSTANDING, [verdict()], UNITS, **kwargs)
    assert result.kind == "refuse" and result.reason == "unverified"
    assert not result.statements and not result.citations


def test_explicit_semantic_optional_and_negative_verdict():
    assert build_outcome(UNDERSTANDING, [verdict()], UNITS, semantic_required=False).kind == "answer"
    assert build_outcome(UNDERSTANDING, [verdict()], UNITS,
                         semantic_required=False, semantic_results=[False]).kind == "refuse"


@pytest.mark.parametrize("kwargs", [
    {"coverage": 0.5}, {"understanding": replace(UNDERSTANDING, missing_slots=("program",))},
    {"extra_bad": True},
])
def test_partial_when_coverage_slots_or_statements_missing(kwargs):
    understanding = kwargs.pop("understanding", UNDERSTANDING)
    verdicts = [verdict()]
    if kwargs.pop("extra_bad", False):
        verdicts.append(verdict("Học phí 680.500 đồng."))
    result = build_outcome(understanding, verdicts, UNITS,
                           semantic_results=[True] * len(verdicts), **kwargs)
    assert result.kind == "partial" and result.partial_note == PARTIAL_NOTE
    assert result.text == SOURCE.text + "\n\n" + PARTIAL_NOTE
    assert len(result.statements) == 1


def test_no_statements_distinguishes_no_source_from_unverified():
    assert build_outcome(UNDERSTANDING).reason == "no_source"
    assert build_outcome(UNDERSTANDING, units_by_id=UNITS).reason == "unverified"
    assert build_outcome(UNDERSTANDING, candidate_count=4).reason == "unverified"
    result = build_outcome(UNDERSTANDING, [verdict("Học phí 680.500 đồng.")], UNITS,
                           semantic_results=[True])
    assert result.kind == "refuse" and result.reason == "unverified"


def test_clarify_uses_fixed_understanding_prompt_and_suggestions():
    understanding = replace(UNDERSTANDING, clarify_prompt="Bạn học khóa nào?", missing_slots=("cohort",))
    result = build_outcome(understanding, suggestions=("K64", "K65"))
    assert result.kind == "clarify" and result.text == understanding.clarify_prompt
    assert result.suggestions == ("K64", "K65")


def test_infrastructure_errors_have_retry_hint():
    result = build_outcome(UNDERSTANDING, infra_error=True)
    assert result.kind == "transient_error" and result.retry_hint
    assert "dịch vụ chưa hoàn tất" not in result.text


def test_refusal_reasons_have_distinct_fixed_messages():
    assert len(set(REFUSAL_MESSAGES.values())) == 4
    for reason, message in REFUSAL_MESSAGES.items():
        result = build_outcome(UNDERSTANDING, refuse_reason=reason)
        assert result.kind == "refuse" and result.reason == reason and result.text == message
    assert build_outcome(replace(UNDERSTANDING, out_of_scope=True)).reason == "out_of_scope"


def test_contact_restored_from_exact_cited_unit():
    source = replace(SOURCE, text="Liên hệ synthetic-office@huce.edu.vn hoặc 0912345678.")
    markers = contact_map([source])
    text = source.text
    for marker, value in markers.items():
        text = text.replace(value, marker)
    units = {"a": source}
    checked = check_statement(Statement(text, ("a",)), units)
    result = build_outcome(UNDERSTANDING, [checked], units, semantic_results=[True])
    assert result.kind == "answer" and result.text == source.text
    assert result.citations[0].quote == source.text
    assert "PUBLIC_CONTACT_" not in result.text


def test_forged_passed_verdict_cannot_bypass_deterministic_gate():
    forged = replace(verdict("Học phí 680.500 đồng."), passed=True, reasons=())
    assert build_outcome(UNDERSTANDING, [forged], UNITS, semantic_results=[True]).kind == "refuse"
