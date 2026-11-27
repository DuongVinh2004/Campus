"""Background loop of F5: runs idle for 30 days expire and their field data is deleted."""
from __future__ import annotations

import asyncio
import logging

LOG = logging.getLogger("campus247.procedures")


async def run_procedure_expiry(service, *, interval_s: float = 3600.0) -> None:
    while True:
        try:
            n = await asyncio.to_thread(service.expire_stale)
            if n:
                LOG.info("procedure runs expired", extra={"count": n})
        except asyncio.CancelledError:
            raise
        except Exception as error:  # noqa: BLE001
            LOG.warning("procedure expiry failed", extra={"error_type": type(error).__name__})
        await asyncio.sleep(interval_s)
