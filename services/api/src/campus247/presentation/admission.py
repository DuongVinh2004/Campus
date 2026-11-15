"""Admission control for chat turns: bound the work in flight, shed the rest quickly.

One API process can only do so much CPU-bound work. Without a bound every extra turn is accepted, waits in an
invisible queue and fails 30-40 s later. With a bound a turn either starts within `max_wait_s` or is told at once
that the system is busy, so the client can retry and no accepted turn is starved.

Per process: each worker keeps its own gate, so the effective total is workers x limit.
Nothing here touches authentication, authorization or the turn itself.
"""
from __future__ import annotations

import asyncio
from collections import deque


class Slot:
    """One admitted turn. `release` is idempotent; a lease timer frees it if the response is never finished."""

    def __init__(self, gate: "AdmissionGate") -> None:
        self._gate: AdmissionGate | None = gate
        self._timer: asyncio.TimerHandle | None = None

    def arm(self, lease_s: float) -> None:
        self._timer = asyncio.get_running_loop().call_later(lease_s, self.release)

    def release(self) -> None:
        gate, self._gate = self._gate, None
        if gate is None:
            return
        if self._timer is not None:
            self._timer.cancel()
        gate._release()


class AdmissionGate:
    def __init__(self, limit: int, max_wait_s: float = 4.0, lease_s: float = 120.0) -> None:
        if limit < 1:
            raise ValueError("limit must be at least 1")
        if max_wait_s < 0 or lease_s <= 0:
            raise ValueError("wait must not be negative and lease must be positive")
        self.limit, self.max_wait_s, self.lease_s = limit, max_wait_s, lease_s
        self._in_flight = 0
        self._waiters: deque[asyncio.Future[None]] = deque()
        self.admitted = 0
        self.rejected = 0

    @property
    def in_flight(self) -> int:
        return self._in_flight

    @property
    def waiting(self) -> int:
        return sum(1 for waiter in self._waiters if not waiter.done())

    async def acquire(self) -> Slot | None:
        """A slot, or None when none became free within `max_wait_s`."""
        if self._in_flight < self.limit and not self._waiters:
            return self._admit()
        waiter: asyncio.Future[None] = asyncio.get_running_loop().create_future()
        self._waiters.append(waiter)
        try:
            await asyncio.wait_for(waiter, self.max_wait_s)
        except asyncio.TimeoutError:
            self.rejected += 1
            return None
        except BaseException:
            # Cancelled (client went away). A slot handed over in the same instant must not leak.
            if waiter.done() and not waiter.cancelled():
                self._release()
            raise
        finally:
            try:
                self._waiters.remove(waiter)
            except ValueError:
                pass
        return self._admit(counted=True)

    def _admit(self, counted: bool = False) -> Slot:
        if not counted:
            self._in_flight += 1
        self.admitted += 1
        slot = Slot(self)
        slot.arm(self.lease_s)
        return slot

    def _release(self) -> None:
        # Hand the slot straight to the longest waiter (first come, first served); otherwise free it.
        while self._waiters:
            waiter = self._waiters.popleft()
            if not waiter.done():
                waiter.set_result(None)
                return
        self._in_flight -= 1
