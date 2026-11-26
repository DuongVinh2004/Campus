"""Background loop of F2: mark a rule STALE as soon as a unit it cites changes (a new release landed)."""
from __future__ import annotations

import asyncio
import logging

LOG = logging.getLogger("campus247.policy_rules")


async def run_rule_staleness(service, *, interval_s: float = 300.0) -> None:
    while True:
        try:
            stale = await asyncio.to_thread(service.check_staleness)
            if stale:
                LOG.warning("policy rules went stale", extra={"rules": [s["rule_id"] for s in stale]})
        except asyncio.CancelledError:
            raise
        except Exception as error:  # noqa: BLE001 -- the loop must survive a bad tick
            LOG.warning("rule staleness tick failed", extra={"error_type": type(error).__name__})
        await asyncio.sleep(interval_s)
