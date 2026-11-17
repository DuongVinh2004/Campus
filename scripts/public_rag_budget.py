"""Apply the human-authorized USD 3 cap without refunding historical usage."""
from decimal import Decimal

from m2_budget_20261012_71 import ConservativeBudget as FullBudget
from m2_budget_20261012_74 import ConservativeBudget as PriorBudget


def resume_authorized_budget(snapshot, records, migration):
    if migration["authorized_cap_usd"] != "3" or migration["call_cap"] != 8500:
        raise ValueError("UNAUTHORIZED_CAP")
    before = migration["before"]
    historical = migration["pending_reservation_records"]
    PriorBudget.resume_full_records(before, historical, cap_usd="1.5", call_cap=8500)
    if snapshot["hard_cap_usd"] == "1.5":
        if snapshot != before or records != historical:
            raise ValueError("UNBOUND_MIGRATION_INPUT")
    elif snapshot["hard_cap_usd"] != "3":
        raise ValueError("UNAUTHORIZED_CAP")
    elif (Decimal(snapshot["remaining_usd"]) != Decimal("3") - Decimal(snapshot["conservative_charged_usd"])
            or Decimal(snapshot["conservative_charged_usd"]) < Decimal(before["conservative_charged_usd"])
            or any(snapshot[key] < before[key] for key in
                   ("calls", "input_tokens_charged", "output_tokens_charged"))
            or not set(historical).issubset(records)):
        raise ValueError("HISTORICAL_USAGE_MUST_REMAIN_CHARGED")
    normalized = {}
    for key, record in records.items():
        if record["snapshot"]["hard_cap_usd"] != "3" and record != historical.get(key):
            raise ValueError("UNBOUND_HISTORICAL_RESERVATION")
        normalized[key] = dict(record, snapshot=dict(record["snapshot"], hard_cap_usd="3"))
    charged = Decimal(snapshot["conservative_charged_usd"])
    view = dict(snapshot, hard_cap_usd="3", remaining_usd=str(Decimal("3") - charged))
    return FullBudget.resume_full_records(view, normalized, cap_usd="3", call_cap=8500)
