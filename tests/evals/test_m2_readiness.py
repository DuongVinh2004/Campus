"""Known denominator/rank boundaries; no live or sealed evaluation data."""
from copy import deepcopy
from math import log2

import pytest

from evals.runners.m2_readiness import dataset_readiness, retrieval_metrics
from tests.evals.test_rag_gold import fixture


def observation(case="EVAL-M2-001", attempt=1, **changes):
    row = {"case_id": case, "attempt": attempt, "status": "passed", "retrievable": True,
           "exact_identifier": True, "critical": True,
           "gold_chunk_ids": ["gold"], "retrieved_chunk_ids": ["other", "gold"]}
    row.update(changes)
    return row


def metrics(*rows):
    return retrieval_metrics(rows, expected_attempts=[(row["case_id"], row["attempt"]) for row in rows])


def test_smoke_is_integrity_valid_but_not_m2():
    record, chunks, contexts = fixture()
    result = dataset_readiness([record], trusted_chunks=chunks, trusted_contexts=contexts)
    assert result["status"] == "blocked"
    assert result["integrity"]["case_count"] == 1
    assert result["deficits"]["rag"] == {"dev": 299, "validation": 100, "sealed_test": 100}
    assert result["counts"]["multi_turn"]["dev"] == 0
    assert "ONE_SOURCE_VERSION_SMOKE_ONLY" in result["reason_codes"]
    assert result["sealed_content_emitted"] is False


def test_no_fabricated_gold_can_pass_input_checks():
    record, chunks, contexts = fixture()
    record["gold"]["citations"][0]["chunk_id"] = "invented"
    result = dataset_readiness([record], trusted_chunks=chunks, trusted_contexts=contexts)
    assert result["reason_codes"] == ["UNRESOLVED_GOLD_CITATION"]


def test_cross_split_shared_source_blocks():
    record, chunks, contexts = fixture()
    other = deepcopy(record)
    other["case"]["case_id"] = "EVAL-M2-002"
    other["case"]["split"] = "sealed_test"
    other["case"]["input"]["turns"][0]["content"] = "Test-only distinct query"
    other["gold"]["scenario_family"] = "other"
    other["gold"]["paraphrase_family"] = "other"
    result = dataset_readiness([record, other], trusted_chunks=chunks, trusted_contexts=contexts)
    assert result["reason_codes"] == ["SPLIT_LEAKAGE"]
    assert "Test-only" not in str(result)


def test_hand_calculated_metrics_keep_error_denominators():
    success = observation()
    timeout = observation("EVAL-M2-002", status="timeout", retrieved_chunk_ids=[])
    negative = observation("EVAL-M2-003", retrievable=False, exact_identifier=False,
                           critical=False, gold_chunk_ids=[], retrieved_chunk_ids=[])
    result = metrics(success, timeout, negative)
    values = result["metrics"]
    assert values["recall_at_10"] == {"numerator": 1, "denominator": 2, "value": 0.5}
    assert values["exact_id_recall_at_5"]["value"] == 0.5
    assert values["mrr_at_10"] == 0.25
    assert values["ndcg_at_10"] == pytest.approx(1 / log2(3) / 2)
    assert result["execution_failures"] == 1
    assert result["M2_acceptance"] == "not_verified"


def test_case_hit_recall_does_not_use_fraction_of_gold_chunks():
    values = metrics(observation(gold_chunk_ids=["gold", "second"],
                                 retrieved_chunk_ids=["gold"]))["metrics"]
    assert values["recall_at_10"]["value"] == 1
    assert values["ndcg_at_10"] == pytest.approx(1 / (1 + 1 / log2(3)))


def test_exact_id_boundary_five_and_ten_are_distinct():
    row = observation(retrieved_chunk_ids=[f"other-{i}" for i in range(5)] + ["gold"])
    values = metrics(row)["metrics"]
    assert values["recall_at_10"]["value"] == 1
    assert values["exact_id_recall_at_5"]["value"] == 0


def test_repeat_majority_and_all_preserve_failed_attempt():
    rows = [observation(attempt=i, retrieved_chunk_ids=["gold"] if i < 3 else [])
            for i in (1, 2, 3)]
    result = metrics(*rows)
    assert result["metrics"]["retrieval_pass_at_all"] == 0
    assert result["metrics"]["retrieval_pass_at_majority"] == 1
    assert result["metrics"]["recall_at_10"]["denominator"] == 3
    assert result["failed_retrieval_attempts"] == [{"case_id": "EVAL-M2-001", "attempt": 3}]


def test_missing_attempt_cannot_be_dropped():
    result = retrieval_metrics([observation()], expected_attempts=[("EVAL-M2-001", 1),
                                                                  ("EVAL-M2-001", 2)])
    assert result["status"] == "not_verified"
    assert result["metrics"] is None


@pytest.mark.parametrize("change", [
    {"retrieved_chunk_ids": ["gold", "gold"]},
    {"gold_chunk_ids": ["gold", "gold"]},
    {"status": "timeout"}, {"critical": "true"},
    {"retrievable": False}, {"retrieved_chunk_ids": [123]},
])
def test_invalid_or_unverified_ranks_fail_closed(change):
    with pytest.raises(ValueError):
        metrics(observation(**change))


def test_unplanned_duplicate_and_empty_plans_fail():
    with pytest.raises(ValueError, match="UNPLANNED"):
        retrieval_metrics([observation()], expected_attempts=[("EVAL-M2-002", 1)])
    with pytest.raises(ValueError, match="UNPLANNED"):
        retrieval_metrics([observation(), observation()], expected_attempts=[("EVAL-M2-001", 1)])
    with pytest.raises(ValueError, match="INVALID_ATTEMPT_PLAN"):
        retrieval_metrics([], expected_attempts=[])


def test_empty_subgroup_is_unknown_not_perfect():
    values = metrics(observation(exact_identifier=False, critical=False))["metrics"]
    assert values["exact_id_recall_at_5"]["value"] is None
    assert values["critical_recall_at_10"]["value"] is None
