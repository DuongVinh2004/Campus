"""The discipline guard stops invented terms, not the name of the cited decision or a bare adverb."""
from hashlib import sha256

from campus247.rag_v2.discipline import discipline_failure
from campus247.rag_v2.types import Citation, Outcome, Statement

RULE = "b) Sinh viên đã bị kỷ luật từ mức cảnh cáo trở lên trong thời gian học thì hạng tốt nghiệp loại xuất sắc và giỏi bị giảm một mức."
TITLE = "Quy chế đào tạo HUCE — Quyết định 1486 ngày 06/11/2023"


def evidence(statement_text):
    digest = sha256(RULE.encode()).hexdigest()
    chunk = "chunk-" + digest
    rows = {chunk: {"chunk_id": chunk, "source_id": "doc", "document_version_id": "version", "content_text": RULE,
                    "evidence_sha256": digest, "canonical_uri": "https://huce.edu.vn/quy-che", "simulation_label": False,
                    "title": TITLE}}
    citation = Citation("u1", (chunk,), "doc", "version", TITLE, "Điều 14", 1, RULE)
    return Outcome("answer", statement_text, (Statement(statement_text, ("u1",)),), (citation,)), rows


def test_naming_the_cited_decision_does_not_count_as_an_addition():
    outcome, rows = evidence("Theo Quyết định 1486, hạng tốt nghiệp loại xuất sắc và giỏi bị giảm một mức nếu sinh viên đã bị kỷ luật "
                             "từ mức cảnh cáo trở lên trong thời gian học.")
    assert discipline_failure(outcome, rows) is None


def test_a_bare_adverb_does_not_count_as_an_addition():
    outcome, rows = evidence("Hạng tốt nghiệp cũng bị giảm một mức nếu sinh viên đã bị kỷ luật từ mức cảnh cáo trở lên trong thời gian học.")
    assert discipline_failure(outcome, rows) is None


def test_an_invented_consequence_is_still_refused():
    outcome, rows = evidence("Hạng tốt nghiệp bị giảm một mức và sinh viên bị đình chỉ nếu đã bị kỷ luật từ mức cảnh cáo trở lên.")
    assert discipline_failure(outcome, rows) == "word_not_in_source"


def test_a_sentence_aimed_at_a_person_is_still_refused():
    outcome, rows = evidence("Em đã bị kỷ luật từ mức cảnh cáo trở lên trong thời gian học nên hạng tốt nghiệp bị giảm một mức.")
    assert discipline_failure(outcome, rows) == "personal"
