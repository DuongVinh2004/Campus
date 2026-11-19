"""Conservative paid-run reservations. Failures retain their full reservation."""
from dataclasses import dataclass
from decimal import Decimal


class BudgetExceeded(ValueError):
    """A request must not be sent after this exception."""


@dataclass(frozen=True)
class Reservation:
    ordinal: int
    input_cap: int
    output_cap: int
    cost_usd: Decimal


class PaidBudget:
    def __init__(self, *, cap_usd: str, call_cap: int, input_price: str = "0.3",
                 output_price: str = "1.2"):
        self.cap = Decimal(cap_usd)
        self.input_price, self.output_price = Decimal(input_price), Decimal(output_price)
        if (not self.cap.is_finite() or self.cap <= 0 or type(call_cap) is not int or call_cap <= 0
                or any(not price.is_finite() or price <= 0 for price in
                       (self.input_price, self.output_price))):
            raise ValueError("INVALID_BUDGET")
        self.call_cap, self.calls = call_cap, 0
        self.charged = Decimal(0)
        self.pending = {}
        self.reserved_input = self.reserved_output = 0

    def reserve(self, input_cap: int, output_cap: int) -> Reservation:
        if any(type(value) is not int or value < 0 for value in (input_cap, output_cap)):
            raise ValueError("INVALID_RESERVATION")
        cost = (input_cap * self.input_price + output_cap * self.output_price) / 1000000
        if self.calls >= self.call_cap or self.charged + cost > self.cap:
            raise BudgetExceeded("PAID_HARD_CAP_REACHED")
        self.calls += 1
        reservation = Reservation(self.calls, input_cap, output_cap, cost)
        self.pending[self.calls] = reservation
        self.charged += cost
        self.reserved_input += input_cap
        self.reserved_output += output_cap
        return reservation

    @classmethod
    def resume_settled(cls, snapshot: dict, *, cap_usd: str, call_cap: int):
        """Resume a hash-verified caller ledger; never refund prior attempts.

        Unsettled ledgers require their full reservation records and cannot be
        reconstructed from the aggregate snapshot alone.
        """
        budget = cls(cap_usd=cap_usd, call_cap=call_cap)
        charged = Decimal(snapshot["conservative_charged_usd"])
        values = [snapshot[key] for key in
                  ("calls", "input_tokens_charged", "output_tokens_charged")]
        if (Decimal(snapshot["hard_cap_usd"]) != budget.cap
                or snapshot["unsettled_attempts_retained"]
                or any(type(value) is not int or value < 0 for value in values)
                or values[0] > call_cap or not charged.is_finite()
                or charged < 0 or charged > budget.cap
                or charged != (values[1] * budget.input_price
                               + values[2] * budget.output_price) / 1000000):
            raise ValueError("INVALID_CONTINUATION_LEDGER")
        budget.calls, budget.reserved_input, budget.reserved_output = values
        budget.charged = charged
        return budget

    def settle_verified(self, reservation: Reservation, input_used: int, output_used: int):
        if (self.pending.get(reservation.ordinal) != reservation
                or any(type(value) is not int or value < 0 for value in (input_used, output_used))
                or input_used > reservation.input_cap or output_used > reservation.output_cap):
            raise ValueError("UNVERIFIED_USAGE")
        cost = (input_used * self.input_price + output_used * self.output_price) / 1000000
        self.charged -= reservation.cost_usd - cost
        self.reserved_input -= reservation.input_cap - input_used
        self.reserved_output -= reservation.output_cap - output_used
        del self.pending[reservation.ordinal]

    def snapshot(self):
        return {"hard_cap_usd": str(self.cap), "conservative_charged_usd": str(self.charged),
                "remaining_usd": str(self.cap - self.charged), "calls": self.calls,
                "call_cap": self.call_cap, "input_tokens_charged": self.reserved_input,
                "output_tokens_charged": self.reserved_output,
                "unsettled_attempts_retained": sorted(self.pending), "actual_billed_usd": None}
