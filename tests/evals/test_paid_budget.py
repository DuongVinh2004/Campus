from decimal import Decimal

import pytest

from evals.runners.paid_budget import BudgetExceeded, PaidBudget


def test_exact_cap_boundary_and_no_call_after_exhaustion():
    budget = PaidBudget(cap_usd="1", call_cap=10)
    budget.reserve(2000000, 0)
    budget.reserve(0, 333333)
    assert budget.charged == Decimal("0.9999996")
    with pytest.raises(BudgetExceeded):
        budget.reserve(2, 0)
    assert budget.calls == 2


def test_unknown_failed_usage_stays_reserved():
    budget = PaidBudget(cap_usd="1", call_cap=1)
    budget.reserve(1000, 1000)
    assert budget.snapshot()["unsettled_attempts_retained"] == [1]
    with pytest.raises(BudgetExceeded):
        budget.reserve(0, 0)
    assert budget.charged == Decimal("0.0015")


def test_only_verified_usage_releases_reservation_and_call_never_refunded():
    budget = PaidBudget(cap_usd="1", call_cap=1)
    reservation = budget.reserve(1000, 1000)
    budget.settle_verified(reservation, 100, 100)
    assert budget.charged == Decimal("0.00015")
    assert budget.snapshot()["unsettled_attempts_retained"] == []
    with pytest.raises(ValueError):
        budget.settle_verified(reservation, 0, 0)
    with pytest.raises(BudgetExceeded):
        budget.reserve(0, 0)


@pytest.mark.parametrize("used", [(-1, 0), (True, 0), (101, 0), (0, 101), (0, 0.5)])
def test_invalid_usage_cannot_refund_or_raise_cap(used):
    budget = PaidBudget(cap_usd="1", call_cap=2)
    reservation = budget.reserve(100, 100)
    before = budget.snapshot()
    with pytest.raises(ValueError):
        budget.settle_verified(reservation, *used)
    assert budget.snapshot() == before


@pytest.mark.parametrize("cap", ["NaN", "Infinity", "0", "-1"])
def test_invalid_financial_limits(cap):
    with pytest.raises(ValueError):
        PaidBudget(cap_usd=cap, call_cap=1)


def test_continuation_preserves_whole_cycle_cost_and_attempts():
    prior = PaidBudget(cap_usd="1", call_cap=2)
    reservation = prior.reserve(1000, 1000)
    prior.settle_verified(reservation, 100, 100)
    budget = PaidBudget.resume_settled(prior.snapshot(), cap_usd="1", call_cap=2)
    assert budget.calls == 1 and budget.charged == Decimal("0.00015")
    assert budget.reserve(200, 200).ordinal == 2
    with pytest.raises(BudgetExceeded):
        budget.reserve(0, 0)


def test_unknown_usage_ledger_cannot_be_silently_resumed():
    prior = PaidBudget(cap_usd="1", call_cap=2)
    prior.reserve(1000, 1000)
    with pytest.raises(ValueError):
        PaidBudget.resume_settled(prior.snapshot(), cap_usd="1", call_cap=2)


def test_continuation_rejects_cost_drift_and_cap_changes():
    prior = PaidBudget(cap_usd="1", call_cap=2).snapshot()
    prior["conservative_charged_usd"] = "0.1"
    with pytest.raises(ValueError):
        PaidBudget.resume_settled(prior, cap_usd="1", call_cap=2)
    prior["conservative_charged_usd"] = "0"
    with pytest.raises(ValueError):
        PaidBudget.resume_settled(prior, cap_usd="2", call_cap=2)
