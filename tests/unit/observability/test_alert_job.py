import asyncio
import logging
from datetime import UTC, datetime, timedelta

import pytest
from campus247.observability.alert_job import run_alerts
from campus247.observability.alert_rules import Reading, Rule
from campus247.observability.alerts import AlertManager

T0 = datetime(2026, 11, 17, 3, 0, tzinfo=UTC)


class Recorder:
    def __init__(self):
        self.sent = []

    def send(self, message):
        self.sent.append(message)


def manager(tmp_path, notifier):
    rule = Rule("down", "Dịch vụ ngừng", lambda status: Reading(status["down"], "không trả lời"))
    return AlertManager(tmp_path / "alerts", notifier, rules=[rule])


@pytest.mark.asyncio
async def test_each_pass_builds_a_fresh_status_and_the_clock_moves(tmp_path):
    notifier, minutes = Recorder(), iter(range(10))
    docs = iter([{"down": False}, {"down": True}, {"down": True}])

    async def build():
        return next(docs)

    await run_alerts(manager(tmp_path, notifier), build, every_s=0, clock=lambda: T0 + timedelta(minutes=next(minutes)), passes=3)
    assert [m.status for m in notifier.sent] == ["firing"] and notifier.sent[0].at == T0 + timedelta(minutes=1)


@pytest.mark.asyncio
async def test_a_failing_pass_is_logged_by_type_only_and_the_loop_continues(tmp_path, caplog):
    notifier, calls = Recorder(), []

    async def build():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("probe exploded with a secret-looking detail")
        return {"down": True}

    with caplog.at_level(logging.WARNING, logger="campus247.alerts"):
        await run_alerts(manager(tmp_path, notifier), build, every_s=0, clock=lambda: T0, passes=2)
    assert len(notifier.sent) == 1
    assert "alert_pass_failed kind=RuntimeError" in caplog.text and "secret-looking" not in caplog.text


@pytest.mark.asyncio
async def test_cancellation_stops_the_loop(tmp_path):
    async def build():
        return {"down": False}

    task = asyncio.create_task(run_alerts(manager(tmp_path, Recorder()), build, every_s=3600))
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
