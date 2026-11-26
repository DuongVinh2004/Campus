"""Background loop of F3: when the running release changes, snapshot it and analyse it against the previous one."""
from __future__ import annotations

import asyncio
import logging

LOG = logging.getLogger("campus247.policy_impact")


async def run_impact_snapshot(service, *, interval_s: float = 60.0) -> None:
    last = None
    while True:
        try:
            release = service.current_release()
            if release and release != last:
                result = await asyncio.to_thread(service.on_new_release)
                LOG.info("impact analysed", extra={"status": result["status"], "release": release})
                last = release
        except asyncio.CancelledError:
            raise
        except Exception as error:  # noqa: BLE001
            LOG.warning("impact tick failed", extra={"error_type": type(error).__name__})
        await asyncio.sleep(interval_s)
