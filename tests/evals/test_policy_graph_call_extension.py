import copy

import pytest
from tests.evals.test_multi_agent_resources import transition, restore, call_extension
import multi_agent_live_resources as resources


def stage5(values):
    prior_extension = call_extension(values)
    _, records, authorization, prior = values
    before = resources.resume_paid_extended(prior_extension["paid_before"], records, authorization,
        prior_extension, prior_migration=prior).snapshot()
    extension = {"human_answer": resources.STAGE5_CALL_EXTENSION_ANSWER,
        "paid_before": before, "pending_reservation_records": copy.deepcopy(records),
        "paid_caps": dict(resources.STAGE5_PAID_CAPS), "prior_paid_caps": dict(resources.EXTENDED_PAID_CAPS),
        "native_caps": dict(resources.NATIVE_CAPS)}
    return before, records, authorization, prior_extension, extension, prior


def test_stage5_exact_call_extension_preserves_all_history_and_new_uncertainty(transition):
    before, records, auth, previous, extension, migration = stage5(transition)
    original = copy.deepcopy((before, records, auth, previous, extension))
    budget = resources.resume_paid_stage5(before, records, auth, previous, extension, prior_migration=migration)
    assert budget.snapshot() == before | {"call_cap": 12192}
    reservation = budget.reserve(100, 20)
    combined = {**records, str(reservation.ordinal): {"input_cap": 100, "output_cap": 20,
        "counted_before_HTTP": True, "snapshot": budget.snapshot()}}
    resumed = resources.resume_paid_stage5(budget.snapshot(), combined, auth, previous, extension, prior_migration=migration)
    assert resumed.snapshot() == budget.snapshot() and resumed.inherited_unknown == frozenset({2, 4})
    with pytest.raises(ValueError, match="STAYS_FULLY_CHARGED"):
        resumed.settle_verified(resumed.pending[4], 0, 0)
    assert (before, records, auth, previous, extension) == original


@pytest.mark.parametrize("tamper", ["drop", "refund", "reservation", "usd", "calls", "native", "counter", "answer", "unbound"])
def test_stage5_change_does_not_authorize_any_other_change(transition, tamper):
    before, records, auth, previous, extension, migration = stage5(transition)
    view = before | {"call_cap": 12192}
    if tamper == "drop": records.clear(); view["unsettled_attempts_retained"] = []
    elif tamper == "refund": view.update(conservative_charged_usd="0", remaining_usd="10")
    elif tamper == "reservation": records["2"]["input_cap"] = 0
    elif tamper == "usd": extension["paid_caps"]["usd"] = "20"
    elif tamper == "calls": view["call_cap"] = 13000
    elif tamper == "native": extension["native_caps"]["inference"] = 20000
    elif tamper == "counter": view["calls"] = 2
    elif tamper == "answer": extension["human_answer"] = "inferred authority"
    else: view.update(call_cap=12000, calls=4)
    with pytest.raises(ValueError):
        resources.resume_paid_stage5(view, records, auth, previous, extension, prior_migration=migration)
