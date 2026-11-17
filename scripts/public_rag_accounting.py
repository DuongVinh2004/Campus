"""User-authorized accounting without aggregate paid caps; uncertainty is retained."""
from decimal import Decimal

from public_rag_budget import FullBudget
from evals.runners.paid_budget import Reservation


class AccountingBudget(FullBudget):
    def __init__(self):
        self.cap = self.call_cap = None
        self.input_price, self.output_price = Decimal("0.3"), Decimal("1.2")
        self.calls = self.reserved_input = self.reserved_output = 0
        self.charged, self.pending = Decimal(0), {}
        self.inherited_unknown = frozenset()

    def reserve(self, input_cap, output_cap):
        if any(type(v) is not int or v < 0 for v in (input_cap, output_cap)):
            raise ValueError("INVALID_RESERVATION")
        cost = (input_cap*self.input_price + output_cap*self.output_price)/1000000
        self.calls += 1
        reservation = Reservation(self.calls, input_cap, output_cap, cost)
        self.pending[self.calls] = reservation
        self.charged += cost
        self.reserved_input += input_cap
        self.reserved_output += output_cap
        return reservation

    def snapshot(self):
        return {"hard_cap_usd": None, "call_cap": None, "remaining_usd": None,
            "calls": self.calls, "conservative_charged_usd": str(self.charged),
            "input_tokens_charged": self.reserved_input,
            "output_tokens_charged": self.reserved_output,
            "unsettled_attempts_retained": sorted(self.pending), "actual_billed_usd": None}

    @classmethod
    def resume_accounting(cls, snapshot, records, before, historical):
        if snapshot["hard_cap_usd"] is not None or snapshot["call_cap"] is not None:
            if snapshot != before or records != historical:
                raise ValueError("UNBOUND_ACCOUNTING_TRANSITION")
            snapshot = {**snapshot, "hard_cap_usd": None, "call_cap": None, "remaining_usd": None}
        if (snapshot["remaining_usd"] is not None or snapshot["actual_billed_usd"] is not None
                or any(records.get(k) != v for k, v in historical.items())):
            raise ValueError("HISTORICAL_ACCOUNTING_CHANGED")
        budget = cls()
        values = [snapshot[k] for k in ("calls", "input_tokens_charged", "output_tokens_charged")]
        charged = Decimal(snapshot["conservative_charged_usd"])
        ids = snapshot["unsettled_attempts_retained"]
        if (any(type(v) is not int or v < before[k] for k, v in zip(
                ("calls", "input_tokens_charged", "output_tokens_charged"), values))
                or not charged.is_finite() or charged < Decimal(before["conservative_charged_usd"])
                or charged != (values[1]*budget.input_price + values[2]*budget.output_price)/1000000
                or ids != sorted(set(ids)) or sorted(map(int, records)) != ids):
            raise ValueError("INVALID_ACCOUNTING_CONTINUATION")
        for ordinal in ids:
            record = records[str(ordinal)]
            caps = record["input_cap"], record["output_cap"]
            saved = record["snapshot"]
            if (type(ordinal) is not int or not 0 < ordinal <= values[0]
                    or any(type(v) is not int or v < 0 for v in caps)
                    or record["counted_before_HTTP"] is not True or saved["calls"] != ordinal
                    or ordinal not in saved["unsettled_attempts_retained"]
                    or str(ordinal) not in historical and (ordinal <= before["calls"]
                        or saved["hard_cap_usd"] is not None or saved["call_cap"] is not None)):
                raise ValueError("INVALID_RETAINED_RESERVATION")
            cost = (caps[0]*budget.input_price + caps[1]*budget.output_price)/1000000
            budget.pending[ordinal] = Reservation(ordinal, *caps, cost)
        if (sum(r.input_cap for r in budget.pending.values()) > values[1]
                or sum(r.output_cap for r in budget.pending.values()) > values[2]
                or sum(r.cost_usd for r in budget.pending.values()) > charged):
            raise ValueError("UNACCOUNTED_RETAINED_RESERVATION")
        budget.calls, budget.reserved_input, budget.reserved_output = values
        budget.charged, budget.inherited_unknown = charged, frozenset(ids)
        if budget.snapshot() != snapshot:
            raise ValueError("INVALID_ACCOUNTING_SNAPSHOT")
        return budget
