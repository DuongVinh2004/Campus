"""Quota extension preserves inherited uncertainty, charges and all ceilings."""
import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "infra/local/rag-fixture")]
import multi_agent_live_resources as resources
import public_rag_budget
from evals.runners.paid_budget import BudgetExceeded


@pytest.fixture
def transition(monkeypatch):
    monkeypatch.setattr(public_rag_budget, "PriorBudget", public_rag_budget.FullBudget)
    before = {"hard_cap_usd": "1.5", "conservative_charged_usd": "0.0015",
        "remaining_usd": "1.4985", "calls": 3, "call_cap": 8500,
        "input_tokens_charged": 1000, "output_tokens_charged": 1000,
        "unsettled_attempts_retained": [2], "actual_billed_usd": None}
    records = {"2": {"input_cap": 100, "output_cap": 100, "counted_before_HTTP": True,
        "snapshot": {"calls": 2, "unsettled_attempts_retained": [2], "hard_cap_usd": "1.5"}}}
    prior = {"authorized_cap_usd": "3", "call_cap": 8500, "before": copy.deepcopy(before),
        "pending_reservation_records": copy.deepcopy(records)}
    snapshot = public_rag_budget.resume_authorized_budget(before, records, prior).snapshot()
    authorization = {"paid_caps": resources.PAID_CAPS, "paid_before": copy.deepcopy(snapshot),
                     "pending_reservation_records": copy.deepcopy(records)}
    return snapshot, records, authorization, prior


def restore(values):
    snapshot, records, authorization, prior = values
    return resources.resume_paid(snapshot, records, authorization, prior_migration=prior)


def test_extension_retains_charge_pending_and_original_artifacts(transition):
    original = copy.deepcopy(transition)
    budget = restore(transition)
    assert budget.snapshot()["calls"] == 3 and budget.snapshot()["hard_cap_usd"] == "10"
    assert budget.snapshot()["conservative_charged_usd"] == "0.0015"
    assert budget.snapshot()["call_cap"] == 10000 and transition == original
    with pytest.raises(ValueError, match="STAYS_FULLY_CHARGED"):
        budget.settle_verified(budget.pending[2], 0, 0)
    with pytest.raises(BudgetExceeded):
        budget.reserve(100_000_000, 0)


def test_restart_keeps_new_verified_usage(transition):
    budget = restore(transition)
    reservation = budget.reserve(100, 20)
    budget.settle_verified(reservation, 90, 10)
    _, records, authorization, prior = transition
    resumed = resources.resume_paid(budget.snapshot(), records, authorization, prior_migration=prior)
    assert resumed.snapshot() == budget.snapshot()


@pytest.mark.parametrize("tamper", ["drop", "refund", "reservation", "cap", "remaining"])
def test_invalid_continuation_fails_closed(transition, tamper):
    snapshot, records, authorization, prior = transition
    view = restore(transition).snapshot()
    if tamper == "drop":
        records.clear(); view["unsettled_attempts_retained"] = []
    elif tamper == "refund":
        view.update(conservative_charged_usd="0", remaining_usd="10")
    elif tamper == "reservation":
        records["2"]["input_cap"] = 0
    elif tamper == "cap":
        authorization["paid_caps"] = {"usd": "20", "calls": 10000}
    else:
        view["remaining_usd"] = "10"
    with pytest.raises(ValueError):
        resources.resume_paid(view, records, authorization, prior_migration=prior)


def test_native_transition_keeps_inference_tokens_and_unknown_http_envelope():
    last = {"caps": resources.OLD_NATIVE_CAPS, "counts": {"http": 2018, "inference": 1990, "tokens": 394527}}
    authorization = {"native_caps": resources.NATIVE_CAPS, "native_before": copy.deepcopy(last)}
    counts, caps = resources.native_transition(last, authorization)
    assert counts == {"http": 6000, "inference": 1990, "tokens": 394527}
    assert caps == resources.NATIVE_CAPS and last["counts"]["http"] == 2018
    with pytest.raises(ValueError):
        resources.native_transition(last | {"counts": {"http": 2018, "inference": 0, "tokens": 0}}, authorization)


def test_latest_snapshot_reads_reservation_then_verified_result_and_rejects_mismatch(tmp_path, monkeypatch):
    monkeypatch.setattr(resources, "PAID_STATE", tmp_path)
    reserve = tmp_path / "provider-00005-reservation.json"
    result = tmp_path / "provider-00005-result.json"
    reserve.write_text(json.dumps({"stage": "reservation", "snapshot": {"calls": 5, "charged": "retained"}}), encoding="utf-8")
    assert resources.latest_paid_snapshot()["charged"] == "retained"
    result.write_text(json.dumps({"stage": "result", "snapshot": {"calls": 5, "charged": "verified"}}), encoding="utf-8")
    assert resources.latest_paid_snapshot()["charged"] == "verified"
    # New later ordinal cannot hide/reset the cumulative snapshot counter.
    later = tmp_path / "provider-00006-reservation.json"
    later.write_text(json.dumps({"stage": "reservation", "snapshot": {"calls": 0}}), encoding="utf-8")
    with pytest.raises(ValueError, match="filename/snapshot"):
        resources.latest_paid_snapshot()


@pytest.mark.parametrize("usage", [None, {}, {"prompt_tokens": 0, "completion_tokens": 1},
    {"prompt_tokens": True, "completion_tokens": 1}, {"prompt_tokens": 20, "completion_tokens": 0}])
def test_missing_provider_usage_cannot_be_treated_as_zero_verified_cost(usage):
    from scripts.run_public_rag import require_provider_usage
    with pytest.raises(ValueError, match="usage unavailable"):
        require_provider_usage({"usage": usage, "choices": [{"message": {"content": "nonempty"}}]})


def test_native_recovery_preserves_every_counter_in_next_namespace():
    last = {"caps": resources.NATIVE_CAPS, "counts": {"http": 6500, "inference": 2500, "tokens": 500000}}
    authorization = {"native_caps": resources.NATIVE_CAPS,
        "native_before": {"counts": {"http": 2018, "inference": 1990, "tokens": 394527}}}
    state = ROOT / "infra/local/rag-advanced-models-20261013-08"
    counts, caps = resources.continue_native(last, authorization, state, resources.NATIVE_STATE)
    assert counts == last["counts"] and caps == last["caps"]
    with pytest.raises(ValueError):
        resources.continue_native(last, authorization, ROOT / "infra/local/rag-advanced-models-20261013-09", resources.NATIVE_STATE)
    with pytest.raises(ValueError):
        resources.continue_native(last | {"counts": {"http": 0, "inference": 0, "tokens": 0}}, authorization, state, resources.NATIVE_STATE)


def call_extension(values):
    before = restore(values).snapshot()
    return {"paid_before": before, "pending_reservation_records": copy.deepcopy(values[1]),
        "prior_paid_caps": dict(resources.PAID_CAPS), "paid_caps": dict(resources.EXTENDED_PAID_CAPS),
        "native_caps": dict(resources.NATIVE_CAPS)}


def test_call_only_extension_keeps_old_and_new_unknown_attempts(transition):
    _, records, authorization, prior = transition
    extension = call_extension(transition)
    original = copy.deepcopy((records, authorization, extension))
    budget = resources.resume_paid_extended(extension["paid_before"], records, authorization, extension, prior_migration=prior)
    assert budget.snapshot() == extension["paid_before"] | {"call_cap": 12000}
    reservation = budget.reserve(100, 20)
    new_records = {**records, str(reservation.ordinal): {"input_cap": 100, "output_cap": 20,
        "counted_before_HTTP": True, "snapshot": budget.snapshot()}}
    resumed = resources.resume_paid_extended(budget.snapshot(), new_records, authorization, extension, prior_migration=prior)
    assert resumed.snapshot() == budget.snapshot()
    assert resumed.inherited_unknown == frozenset({2, 4})
    with pytest.raises(ValueError, match="STAYS_FULLY_CHARGED"):
        resumed.settle_verified(resumed.pending[4], 0, 0)
    assert (records, authorization, extension) == original


@pytest.mark.parametrize("tamper", ["drop", "refund", "reservation", "usd", "calls", "native", "remaining", "counter", "unbound"])
def test_call_extension_rejects_other_changes(transition, tamper):
    _, records, authorization, prior = transition
    extension = call_extension(transition)
    view = extension["paid_before"] | {"call_cap": 12000}
    if tamper == "drop":
        records = {}; view["unsettled_attempts_retained"] = []
    elif tamper == "refund":
        view.update(conservative_charged_usd="0", remaining_usd="10")
    elif tamper == "reservation":
        records["2"]["input_cap"] = 0
    elif tamper == "usd":
        extension["paid_caps"]["usd"] = "20"
    elif tamper == "calls":
        view["call_cap"] = 15000
    elif tamper == "native":
        extension["native_caps"]["inference"] = 20000
    elif tamper == "remaining":
        view["remaining_usd"] = "10"
    elif tamper == "counter":
        view["calls"] = 2
    else:
        view.update(call_cap=10000, calls=4)
    with pytest.raises(ValueError):
        resources.resume_paid_extended(view, records, authorization, extension, prior_migration=prior)
