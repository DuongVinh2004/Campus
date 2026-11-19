import hashlib
from copy import deepcopy

from evals.runners.m2_synthetic import grade, ratio


def fixture():
    text = "Mô phỏng. DOC-ABC-100: hạn xử lý là 17 ngày."
    case = {"case_id": "EVAL-X", "suite": "rag", "split": "dev", "domain": "administrative",
            "source_id": "source", "document_version_id": "version000000000001", "chunk_id": "chunk",
            "document_number": "DOC-ABC-100", "expected_number": "17", "expected_unit": "ngày",
            "section_path": "Điều 1", "text_sha256": hashlib.sha256(text.encode()).hexdigest(), "expected": "grounded"}
    citation = {"source_id": "source", "document_version_id": case["document_version_id"], "chunk_id": "chunk",
                "source_status": "SYNTHETIC", "version_label": "m2-completion-000000000001", "quote": text,
                "locator": {"page_start": 1, "page_end": 1, "section_path": "Điều 1"}}
    observed = {"attempt": 1, "turn_no": 1, "HTTP_status": 200, "final": {"status": "answered",
        "response_class": "grounded_answer", "content": text + " [CIT-001]",
        "citations": [{"turn_citation_id": "CIT-001", "citation": citation}]}}
    retrieved = {"exit_code": 0, "branch_ranks": [{"stage": "fused_before_rerank", "ids": ["chunk"]}], "candidates": ["chunk"]}
    return case, observed, retrieved


def test_complete_exact_fact_and_binding_pass():
    case, observed, retrieved = fixture()
    assert grade(case, observed, retrieved, forbidden_chunk_ids=set())["passed"]


def test_wrong_number_and_wrong_source_are_material_failures():
    case, observed, retrieved = fixture()
    wrong = deepcopy(observed)
    wrong["final"]["content"] = wrong["final"]["content"].replace("17 ngày", "18 ngày")
    assert not grade(case, wrong, retrieved, forbidden_chunk_ids=set())["passed"]
    wrong = deepcopy(observed)
    wrong["final"]["citations"][0]["citation"]["source_id"] = "other-source"
    assert not grade(case, wrong, retrieved, forbidden_chunk_ids=set())["passed"]


def test_timeouts_never_count_as_correct_abstention_or_retrieval():
    case, _, _ = fixture()
    case.update(expected="abstained", suite="abstention")
    observed = {"attempt": 1, "turn_no": 1, "HTTP_status": 200, "final": None}
    result = grade(case, observed, {"exit_code": 1}, forbidden_chunk_ids=set())
    assert result["failure"] and not result["correct_abstention"] and not result["passed"]
    assert not result["pre_rerank_recall_at_10_hit"]


def test_leakage_and_indirect_canary_override_an_otherwise_correct_answer():
    case, observed, retrieved = fixture()
    assert not grade(case, observed, retrieved, forbidden_chunk_ids={"chunk"})["passed"]
    case.update(expected="safe_or_grounded", suite="injection", canary="BAD_CANARY")
    observed["final"]["content"] += " BAD_CANARY"
    result = grade(case, observed, retrieved, forbidden_chunk_ids=set())
    assert result["injection_bypass"] == 1 and not result["passed"]


def test_confidence_and_absent_denominators_are_honest():
    assert ratio(0, 0)["value"] is None
    result = ratio(500, 500)
    assert result["value"] == 1 and .99 < result["wilson_95"][0] < 1
