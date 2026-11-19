"""The approved cap preserves charges, uncertainty, and the hard spending limit."""
import copy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "infra/local/rag-fixture")]
import public_rag_budget as migration_api
from evals.runners.paid_budget import BudgetExceeded


@pytest.fixture
def ledger(monkeypatch):
    monkeypatch.setattr(migration_api, "PriorBudget", migration_api.FullBudget)
    before = {"hard_cap_usd": "1.5", "conservative_charged_usd": "0.0015",
        "remaining_usd": "1.4985", "calls": 3, "call_cap": 8500,
        "input_tokens_charged": 1000, "output_tokens_charged": 1000,
        "unsettled_attempts_retained": [2], "actual_billed_usd": None}
    records = {"2": {"input_cap": 100, "output_cap": 100, "counted_before_HTTP": True,
        "snapshot": {"calls": 2, "unsettled_attempts_retained": [2], "hard_cap_usd": "1.5"}}}
    migration = {"authorized_cap_usd": "3", "call_cap": 8500, "before": copy.deepcopy(before),
        "pending_reservation_records": copy.deepcopy(records)}
    return before, records, migration


def test_migration_retains_all_charges_and_unknown_reservations(ledger):
    before, records, migration = ledger
    originals = copy.deepcopy(ledger)
    budget = migration_api.resume_authorized_budget(*ledger)
    assert budget.snapshot() == before | {"hard_cap_usd": "3", "remaining_usd": "2.9985"}
    assert ledger == originals
    with pytest.raises(ValueError, match="STAYS_FULLY_CHARGED"):
        budget.settle_verified(budget.pending[2], 0, 0)
    with pytest.raises(BudgetExceeded):
        budget.reserve(10_000_000, 0)


def test_restart_keeps_new_and_historical_usage(ledger):
    before, records, migration = ledger
    budget = migration_api.resume_authorized_budget(*ledger)
    known = budget.reserve(10, 10)
    budget.settle_verified(known, 1, 1)
    resumed = migration_api.resume_authorized_budget(budget.snapshot(), records, migration)
    assert resumed.snapshot() == budget.snapshot()


@pytest.mark.parametrize("tamper", ["remaining", "drop_unknown", "refund"])
def test_restart_cannot_discard_prior_usage(ledger, tamper):
    before, records, migration = ledger
    snapshot = migration_api.resume_authorized_budget(*ledger).snapshot()
    if tamper == "remaining":
        snapshot["remaining_usd"] = "3"
    elif tamper == "drop_unknown":
        records.clear()
        snapshot["unsettled_attempts_retained"] = []
    else:
        snapshot.update(conservative_charged_usd="0", remaining_usd="3")
    with pytest.raises(ValueError):
        migration_api.resume_authorized_budget(snapshot, records, migration)


@pytest.mark.parametrize("tamper", ["cap", "charge", "reservation"])
def test_unapproved_cap_or_rewritten_history_fails_closed(ledger, tamper):
    before, records, migration = ledger
    if tamper == "cap":
        migration["authorized_cap_usd"] = "4"
    elif tamper == "charge":
        before["conservative_charged_usd"] = "0"
    else:
        records["2"]["input_cap"] = 0
    with pytest.raises(ValueError):
        migration_api.resume_authorized_budget(*ledger)
