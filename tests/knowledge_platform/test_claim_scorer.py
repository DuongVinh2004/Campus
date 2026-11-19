"""Mutation tests for evaluation, not tests of the production answer formatter."""
import importlib.util
import sys

import pytest

from .conftest import ROOT

spec = importlib.util.spec_from_file_location("knowledge_claims", ROOT / "evals/runners/knowledge_claims.py")
claims = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = claims
spec.loader.exec_module(claims)


def gold(witness, **kwargs):
    return claims.Expectation("answered", witness, witness_binding={"source": "synthetic-scorer-witness"}, **kwargs)


def score(text, expected):
    return claims.assess_material({"status": "answered", "content": text}, expected)


def test_known_extra_course_counterexample():
    expected = gold("531800 2TC; 291802 3TC", expected_codes=frozenset({"531800", "291802"}))
    answer = "531800 2TC; 291802 3TC"
    assert score(answer, expected)["answered_correctly"]
    bad = score(answer + ". Học kỳ này còn bắt buộc học môn 999999, 99 tín chỉ.", expected)
    assert not bad["passed"]
    assert any("unsupported_course_codes" in f for f in bad["failures"])
    assert any("unsupported_quantities" in f for f in bad["failures"])


@pytest.mark.parametrize("mutant", ["30 tín chỉ", "30 giờ", "3%", "30% và 99%"])
def test_unit_value_or_extra_quantity(mutant):
    assert not score(mutant, gold("30%", expected_quantities=frozenset({("3E+1", "percent")})))["passed"]


def test_equivalent_quantity_formatting():
    assert score("1.500.000 VND và 03 tín chỉ", gold("1.500.000 đồng và 3TC"))["passed"]


@pytest.mark.parametrize("answer", ["451802 → 531816", "531816 ↔ 451802", "531816 → 451802; 999999 → 531816"])
def test_direction_kind_and_extra_edge(answer):
    assert not score(answer, gold("531816 → 451802", expected_edges=frozenset({("directed", "531816", "451802")})))["passed"]


def test_written_edge_and_corequisite_order():
    assert score("531816 là tiên quyết của 451802", gold("531816 là tiên quyết của 451802"))["passed"]
    assert score("531830 ↔ 531829", gold("531829 ↔ 531830"))["passed"]


def test_negation_exception_and_scope():
    expected = gold("Không quá 30% chương trình; ngoại lệ thiên tai, dịch bệnh theo quy định của Bộ Giáo dục.",
        required_conditions=(("không quá", "tối đa"), ("ngoại lệ",), ("thiên tai",), ("dịch bệnh",), ("Bộ Giáo dục",)),
        forbidden_terms=("ít nhất 30%", "không có ngoại lệ"))
    assert score(expected.witness, expected)["passed"]
    for bad in ("Ít nhất 30% chương trình.", "Không quá 30% chương trình, không có ngoại lệ.", "Không quá 30% chương trình."):
        assert not score(bad, expected)["passed"]


def test_correct_refusal_is_not_answered_correctly():
    expected = claims.Expectation("abstained", "")
    result = claims.assess_material({"status": "abstained", "content": "Chưa kết nối API học vụ cá nhân."}, expected)
    assert result["correct_abstention"] and not result["answered_correctly"]
    assert not claims.assess_material({"status": "answered", "content": "Chưa kết nối."}, expected)["passed"]


def test_no_source_hash_substitute_for_semantics():
    result = score("99TC", gold("3TC"))
    assert not result["passed"] and not result["free_prose_semantics_verified"]


def test_no_unbound_answered_gold():
    with pytest.raises(ValueError):
        claims.Expectation("answered", "3TC")


def test_swapped_course_credits_are_not_a_correct_set_of_numbers():
    expected = gold("531800 - 2; 291802 - 3")
    assert not score("531800 - 3; 291802 - 2", expected)["passed"]
