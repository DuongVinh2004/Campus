"""Background loops of the announcements feature (F1.5). Each runs under `run_gated`, so it stops while announcements.publish is off."""
from __future__ import annotations

import asyncio
import logging

LOG = logging.getLogger("campus247.announcements")


def _loop(name: str, every_s: float, work):
    async def run():
        while True:
            try:
                await asyncio.to_thread(work)
            except asyncio.CancelledError:
                raise
            except Exception as error:  # noqa: BLE001 -- keep the loop alive; the next pass retries from the stored cursor
                LOG.warning("announcement_job_failed job=%s kind=%s", name, type(error).__name__)
            await asyncio.sleep(every_s)
    return run


def announcement_jobs(service) -> list[tuple[str, object]]:
    return [("announcement_publisher", _loop("publisher", 30, service.run_publisher_once)),
            ("announcement_reconcile", _loop("reconcile", 3600, service.run_reconcile_once)),
            ("announcement_expiry", _loop("expiry", 300, service.run_expiry_once)),
            ("announcement_ack_reminders", _loop("ack", 900, service.run_ack_reminders_once))]
