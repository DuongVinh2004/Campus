import json

import pytest

from campus247.application.knowledge.platform_models import digest
from campus247.application.retrieval.citations import CitationBundle
from campus247.application.retrieval.curriculum_quotation import present_curriculum_quotation
from campus247.application.retrieval.evidence_gate import parse_grounded_claims
from campus247.domain.curriculum import VerifiedCurriculumParent
from campus247.ports.llm import LlmResponse, LlmResponseStatus, TokenUsage

SOURCE = "71TEST\nHọc kỳ 1\n123456 – 3\nMôn A\n\nTỰ CHỌN 1 (2TC)\n234567 – 2\nMôn B\n345678 – 2\nMôn C\nTổng: 5TC"


def row():
    proof = VerifiedCurriculumParent("source", "version", digest(SOURCE.encode()), "release", (1,), ("123456", "234567", "345678"))
    return {"source_id": "source", "document_version_id": "version", "release_id": "release",
        "content_text": SOURCE, "simulation_label": False, "_verified_curriculum": proof}


def response():
    return LlmResponse(LlmResponseStatus.COMPLETED, "fixture", "synthetic", usage=TokenUsage(10, 0, 20),
        output_text=json.dumps({"claims": [{"text": "Môn A có ba tín chỉ.", "citation_ids": ["CIT-001"], "claim_type": "policy"}]}))


@pytest.mark.parametrize("question,expected", [("Học kỳ 1 môn 123456 có tên và bao nhiêu tín chỉ?", "123456 – 3\nMôn A"),
    ("Nhóm tự chọn 1 ở học kỳ 1 có những môn nào?", "TỰ CHỌN 1 (2TC)\n234567 – 2\nMôn B\n345678 – 2\nMôn C")])
def test_exact_reviewed_cell_and_elective_group_keep_original_abbreviations_and_every_option(question, expected):
    initial = response(); bundle = CitationBundle.build([row()])
    quoted = present_curriculum_quotation(initial, bundle, question)
    assert parse_grounded_claims(quoted.output_text).claims[0].text == expected
    assert quoted.usage == initial.usage and "_verified_curriculum" not in bundle.to_prompt_context()


@pytest.mark.parametrize("fault", ["dict", "source", "version", "release", "evidence", "simulation"])
def test_missing_or_transferred_geometry_attestation_never_enables_quotation(fault):
    source = row()
    if fault == "dict": source["_verified_curriculum"] = source["_verified_curriculum"].__dict__
    elif fault == "evidence": source["content_text"] += "\nChanged."
    elif fault == "simulation": source["simulation_label"] = True
    else: source[{"source": "source_id", "version": "document_version_id", "release": "release_id"}[fault]] = "other"
    initial = response()
    assert present_curriculum_quotation(initial, CitationBundle.build([source]), "Môn 123456 bao nhiêu tín chỉ?") is initial


def test_quotation_cannot_replace_a_relation_or_multiple_course_question():
    initial = response(); bundle = CitationBundle.build([row()])
    for query in ("123456 là tiên quyết của 234567 không?", "123456 và 234567 có tên gì?", "Môn 999999 có tên gì?"):
        assert present_curriculum_quotation(initial, bundle, query) is initial


@pytest.mark.parametrize("printed,quoted", [("Giáo dục\nthể chất 2 – 1TC", True), ("GD thể chất 2", False)])
def test_pe_credit_requires_a_printed_unit_in_the_exact_attested_parent(printed, quoted):
    source = row(); text = "71TEST\nHọc kỳ 2\n\n" + printed + "\n\nTổng: 180TC"
    source.update(content_text=text, _verified_curriculum=VerifiedCurriculumParent(
        "source", "version", digest(text.encode()), "release", (2,), ()))
    initial = response()
    result = present_curriculum_quotation(initial, CitationBundle.build([source]), "Giáo dục thể chất 2 ghi bao nhiêu TC?")
    if quoted:
        assert parse_grounded_claims(result.output_text).claims[0].text == printed
        assert result.usage == initial.usage
    else:
        assert result is initial


def test_catalogue_column_can_be_quoted_without_admitting_semester_or_neighbor_group():
    text = "Programme\nHọc phần tự chọn bắt buộc\nHPTCBB 1 (2TC)\nLựa chọn 1\n123456 – Môn A\nLựa chọn 2\n234567 – Môn B"
    source = row(); source.update(content_text=text, _verified_curriculum=VerifiedCurriculumParent(
        "source", "version", digest(text.encode()), "release", (), ("123456", "234567"), ("HPTCBB 1",)))
    initial = response(); bundle = CitationBundle.build([source])
    actual = present_curriculum_quotation(initial, bundle, "Nhóm HPTCBB 1 ghi những phương án nào?")
    assert parse_grounded_claims(actual.output_text).claims[0].text == text[text.index("HPTCBB 1"):]
    assert present_curriculum_quotation(initial, bundle, "Nhóm HPTCBB 2 ghi gì?") is initial


def test_english_catalogue_label_does_not_borrow_a_vietnamese_group_attestation():
    text = "Programme\nRequired Elective 4 (2 Credits)\nOption 1\n123456 – Title A\nOption 2\n234567 – Title B"
    source = row(); source.update(content_text=text, _verified_curriculum=VerifiedCurriculumParent(
        "source", "version", digest(text.encode()), "release", (), ("123456", "234567"), ("REQUIRED ELECTIVE 4",)))
    initial = response(); bundle = CitationBundle.build([source])
    actual = present_curriculum_quotation(initial, bundle, "What is printed under Required Elective 4?")
    assert parse_grounded_claims(actual.output_text).claims[0].text == text[text.index("Required Elective 4"):]
    assert present_curriculum_quotation(initial, bundle, "HPTCBB 4 ghi gì?") is initial
