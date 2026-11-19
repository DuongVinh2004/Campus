"""Unknown usage cannot disappear, refund or allow spending over USD1."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "infra/local/rag-fixture"))
from m2_budget_20261012_68 import ConservativeBudget
from m2_grade_20261012_68 import grade

from tests.evals.test_m2_synthetic import fixture


def retained():
    snapshot = {"hard_cap_usd": "1", "conservative_charged_usd": "0.0015", "remaining_usd": "0.9985",
        "calls": 3, "call_cap": 6500, "input_tokens_charged": 1000, "output_tokens_charged": 1000,
        "unsettled_attempts_retained": [2], "actual_billed_usd": None}
    records = {"2": {"input_cap": 100, "output_cap": 100, "counted_before_HTTP": True,
        "snapshot": {"calls": 2, "unsettled_attempts_retained": [2], "hard_cap_usd": "1"}}}
    return snapshot, records


def test_complete_unknown_reservation_stays_charged_and_cannot_be_settled_later():
    snapshot, records = retained()
    budget = ConservativeBudget.resume_full_records(snapshot, records)
    known = budget.reserve(10, 10)
    budget.settle_verified(known, 1, 1)
    assert budget.snapshot()["unsettled_attempts_retained"] == [2]
    assert budget.snapshot()["calls"] == 4 and budget.charged > 0
    with pytest.raises(ValueError, match="STAYS_FULLY_CHARGED"):
        budget.settle_verified(budget.pending[2], 0, 0)
    from evals.runners.paid_budget import BudgetExceeded
    with pytest.raises(BudgetExceeded):
        budget.reserve(4000000, 0)


@pytest.mark.parametrize("bad", ["missing", "charge", "caps", "cap"])
def test_missing_or_inconsistent_uncertain_records_fail_closed(bad):
    snapshot, records = retained()
    if bad == "missing":
        records.clear()
    elif bad == "charge":
        snapshot["conservative_charged_usd"] = "0"
    elif bad == "caps":
        records["2"]["input_cap"] = 10000
    else:
        snapshot["hard_cap_usd"] = "2"
    with pytest.raises(ValueError):
        ConservativeBudget.resume_full_records(snapshot, records)


@pytest.mark.parametrize("failure", ["retrieval", "generation"])
def test_error_with_abstained_final_never_passes_as_domain_refusal(failure):
    case, observed, retrieved = fixture()
    case.update(expected="abstained", suite="abstention")
    observed["final"] = {"status": "abstained", "response_class": "safe_refusal", "content": "Unavailable", "citations": []}
    if failure == "retrieval":
        retrieved["exit_code"] = 1
    else:
        observed["application_dependency_failed"] = True
    result = grade(case, observed, retrieved, forbidden_chunk_ids=set())
    assert result["failure"] and not result["correct_abstention"] and not result["passed"]
