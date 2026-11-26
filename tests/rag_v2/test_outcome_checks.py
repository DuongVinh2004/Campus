"""F4.1: build_outcome adds per-statement checks and rejected counts, and changes nothing else."""
from __future__ import annotations

from dataclasses import replace

from campus247.rag_v2.outcome.compose import build_outcome
from campus247.rag_v2.types import Statement, StatementVerdict, Understanding, Unit
from campus247.rag_v2.verification.deterministic import check_statement

UNIT = Unit("u1", ("c1",), "d1", "v1", "Quy chế", "Quy chế", "article", "Điều 10", 4,
            "Sinh viên nộp học phí 580.500 đồng mỗi tín chỉ trước ngày 15/09/2026. Quá hạn bị phạt.")
U = Understanding("hp", "hoc phi", (), None, None, None, "number", (), (), None)


def verdicts(*texts):
    return [check_statement(Statement(t, ("u1",)), {"u1": UNIT}) for t in texts]


def test_accepted_statements_carry_checks_and_rejected_ones_are_only_counted():
    v = verdicts("Sinh viên nộp học phí 580.500 đồng mỗi tín chỉ", "Học phí là 999.000 đồng mỗi tín chỉ")
    out = build_outcome(U, v, {"u1": UNIT}, semantic_results=[True, True])
    assert [s.text for s in out.statements] == ["Sinh viên nộp học phí 580.500 đồng mỗi tín chỉ"]
    assert len(out.checks) == len(out.statements) == 1
    check = out.checks[0]
    assert check.deterministic == "PASSED" and check.verbatim is True and check.semantic == "PASSED"
    uid, start, end = check.support_spans[0]
    assert uid == "u1" and "580.500" in UNIT.text[start:end]
    assert out.rejected_counts == {"NUMBER_NOT_IN_SOURCE": 1}
    assert "999" not in repr(out.rejected_counts)


def test_paraphrase_is_not_verbatim_and_semantic_failure_is_counted():
    v = verdicts("Mỗi tín chỉ thu 580.500 đồng", "Quá hạn bị phạt")
    out = build_outcome(U, v, {"u1": UNIT}, semantic_results=[True, False])
    assert [c.verbatim for c in out.checks] == [False]
    assert out.rejected_counts == {"SEMANTIC_UNSUPPORTED": 1}


def test_without_semantic_results_the_check_says_not_run():
    out = build_outcome(U, verdicts("Sinh viên nộp học phí 580.500 đồng mỗi tín chỉ"), {"u1": UNIT}, semantic_required=False)
    assert out.checks[0].semantic == "NOT_RUN" and out.rejected_counts == {}


def test_decisions_text_and_citations_do_not_depend_on_the_new_fields():
    v = verdicts("Sinh viên nộp học phí 580.500 đồng mỗi tín chỉ", "Học phí là 999.000 đồng mỗi tín chỉ")
    out = build_outcome(U, v, {"u1": UNIT}, semantic_results=[True, True])
    stripped = replace(out, checks=(), rejected_counts={})
    assert (stripped.kind, stripped.text, stripped.statements, stripped.citations, stripped.partial_note) == \
           (out.kind, out.text, out.statements, out.citations, out.partial_note)
    assert out.kind == "partial" and out.statements == (Statement("Sinh viên nộp học phí 580.500 đồng mỗi tín chỉ", ("u1",)),)
