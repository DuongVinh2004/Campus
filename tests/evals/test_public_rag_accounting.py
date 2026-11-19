"""The explicit no-aggregate-cap mode preserves accounting and uncertainty."""
import copy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "infra/local/rag-fixture")]
from public_rag_accounting import AccountingBudget
from public_rag_budget import FullBudget


def baseline():
    old = FullBudget(cap_usd="10", call_cap=12192)
    old.inherited_unknown = frozenset()
    reservation = old.reserve(100, 20)
    snapshot = old.snapshot()
    records = {str(reservation.ordinal): {"input_cap": 100, "output_cap": 20,
        "counted_before_HTTP": True, "snapshot": copy.deepcopy(snapshot)}}
    return snapshot, records


def test_no_aggregate_limits_preserves_charge_and_inherited_unknown():
    before, records = baseline()
    original = copy.deepcopy((before, records))
    budget = AccountingBudget.resume_accounting(before, records, before, records)
    assert budget.snapshot()["hard_cap_usd"] is budget.snapshot()["call_cap"] is None
    assert budget.snapshot()["conservative_charged_usd"] == before["conservative_charged_usd"]
    with pytest.raises(ValueError, match="STAYS_FULLY_CHARGED"):
        budget.settle_verified(budget.pending[1], 0, 0)
    # Cross both old aggregate thresholds without raising or resetting usage.
    budget.calls = 12192
    reservation = budget.reserve(100_000_000, 100)
    assert reservation.ordinal == 12193 and budget.charged > 10
    budget.settle_verified(reservation, 100_000_000, 20)
    assert budget.calls == 12193 and (before, records) == original


def test_restart_keeps_unknown_new_reservations_and_settled_usage():
    before, historical = baseline()
    budget = AccountingBudget.resume_accounting(before, historical, before, historical)
    unknown = budget.reserve(200, 50)
    record = {"input_cap": 200, "output_cap": 50, "counted_before_HTTP": True,
        "snapshot": copy.deepcopy(budget.snapshot())}
    settled = budget.reserve(100, 20)
    budget.settle_verified(settled, 80, 10)
    records = {**historical, str(unknown.ordinal): record}
    reopened = AccountingBudget.resume_accounting(budget.snapshot(), records, before, historical)
    assert reopened.snapshot() == budget.snapshot()
    with pytest.raises(ValueError, match="STAYS_FULLY_CHARGED"):
        reopened.settle_verified(reopened.pending[unknown.ordinal], 0, 0)


@pytest.mark.parametrize("tamper", ["refund", "drop", "history", "restore_cap", "counter"])
def test_uncapped_mode_rejects_accounting_tampering(tamper):
    before, historical = baseline()
    view = AccountingBudget.resume_accounting(before, historical, before, historical).snapshot()
    records = copy.deepcopy(historical)
    if tamper == "refund": view["conservative_charged_usd"] = "0"
    elif tamper == "drop": view["unsettled_attempts_retained"] = []; records = {}
    elif tamper == "history": records["1"]["input_cap"] = 0
    elif tamper == "restore_cap": view["call_cap"] = 99999
    else: view["calls"] = 0
    with pytest.raises(ValueError):
        AccountingBudget.resume_accounting(view, records, before, historical)


def test_headroom_accepts_explicitly_uncapped_paid_accounting(monkeypatch):
    import multi_agent_live_resources as resources
    from scripts.run_multi_agent import headroom
    from campus247.application.multi_agent.contracts import MultiAgentPolicy
    monkeypatch.setattr(resources, "paid_view", lambda: {"hard_cap_usd": None,
        "call_cap": None, "calls": 50000, "remaining_usd": None})
    monkeypatch.setattr(resources, "authorized_paid_caps", lambda: {"usd": None, "calls": None})
    monkeypatch.setattr(resources, "native_view", lambda: {"caps": resources.NATIVE_CAPS,
        "counts": {"http": 8000, "inference": 5000, "tokens": 1000000}})
    assert headroom(MultiAgentPolicy()) is True
