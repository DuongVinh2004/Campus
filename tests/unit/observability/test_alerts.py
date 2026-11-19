import json
import logging
from datetime import UTC, datetime, timedelta

import pytest
from campus247.observability.alert_rules import Reading, Rule, Severity
from campus247.observability.alerts import AlertManager, AlertMessage, CompositeNotifier, LogNotifier

T0 = datetime(2026, 11, 17, 3, 0, 0, tzinfo=UTC)


class Recorder:
    def __init__(self, fail=0):
        self.sent, self.fail = [], fail

    def send(self, message: AlertMessage):
        if self.fail:
            self.fail -= 1
            raise OSError("channel down")
        self.sent.append(message)


def rule(box, *, for_s=0, rule_id="r1"):
    """A rule whose reading is whatever the test puts in `box` (a Reading or None)."""
    return Rule(rule_id, "Tiêu đề thử", lambda status: box["reading"], for_s=for_s)


def breach(value="giá trị", severity=Severity.WARNING):
    return Reading(True, value, severity)


OK = Reading(False, "bình thường")


def manager(tmp_path, notifier, box, **kwargs):
    return AlertManager(tmp_path / "alerts", notifier, rules=[rule(box, **{k: v for k, v in kwargs.items() if k == "for_s"})],
                        **{k: v for k, v in kwargs.items() if k == "repeat_s"})


def at(minutes):
    return T0 + timedelta(minutes=minutes)


def test_a_breach_sends_once_then_stays_quiet_until_the_repeat_interval(tmp_path):
    box, notifier = {"reading": breach()}, Recorder()
    alerts = manager(tmp_path, notifier, box, repeat_s=1800)
    assert alerts.evaluate({}, now=at(0)) == ["r1"]
    assert alerts.evaluate({}, now=at(1)) == [] and alerts.evaluate({}, now=at(29)) == []
    assert alerts.evaluate({}, now=at(31)) == ["r1"]
    assert [m.status for m in notifier.sent] == ["firing", "repeat"]


def test_a_breach_must_last_for_the_required_time(tmp_path):
    box, notifier = {"reading": breach()}, Recorder()
    alerts = manager(tmp_path, notifier, box, for_s=120)
    assert alerts.evaluate({}, now=at(0)) == [] and alerts.snapshot()["r1"]["state"] == "PENDING"
    assert alerts.evaluate({}, now=at(1)) == []
    assert alerts.evaluate({}, now=at(2)) == ["r1"]


def test_a_short_blip_never_fires(tmp_path):
    box, notifier = {"reading": breach()}, Recorder()
    alerts = manager(tmp_path, notifier, box, for_s=300)
    alerts.evaluate({}, now=at(0))
    box["reading"] = OK
    alerts.evaluate({}, now=at(2))
    box["reading"] = breach()
    alerts.evaluate({}, now=at(3))
    alerts.evaluate({}, now=at(6))  # only 3 minutes since the second breach began
    assert notifier.sent == [] and alerts.snapshot()["r1"]["state"] == "PENDING"


def test_resolved_needs_two_good_evaluations_in_a_row(tmp_path):
    box, notifier = {"reading": breach()}, Recorder()
    alerts = manager(tmp_path, notifier, box)
    alerts.evaluate({}, now=at(0))
    box["reading"] = OK
    assert alerts.evaluate({}, now=at(1)) == []
    box["reading"] = breach()
    alerts.evaluate({}, now=at(2))  # one good reading was not enough; the streak restarts
    box["reading"] = OK
    assert alerts.evaluate({}, now=at(3)) == [] and alerts.evaluate({}, now=at(4)) == ["r1"]
    assert [m.status for m in notifier.sent] == ["firing", "resolved"] and alerts.snapshot()["r1"]["state"] == "OK"
    box["reading"] = breach()
    assert alerts.evaluate({}, now=at(5)) == ["r1"]  # a new incident sends again


def test_a_rule_that_cannot_judge_keeps_its_state(tmp_path):
    box, notifier = {"reading": breach()}, Recorder()
    alerts = manager(tmp_path, notifier, box)
    alerts.evaluate({}, now=at(0))
    box["reading"] = None
    for minute in range(1, 6):
        assert alerts.evaluate({}, now=at(minute)) == []
    assert alerts.snapshot()["r1"]["state"] == "FIRING" and len(notifier.sent) == 1


def test_a_rising_severity_is_announced_at_once(tmp_path):
    box, notifier = {"reading": breach(severity=Severity.WARNING)}, Recorder()
    alerts = manager(tmp_path, notifier, box)
    alerts.evaluate({}, now=at(0))
    box["reading"] = breach("còn 4%", Severity.CRITICAL)
    assert alerts.evaluate({}, now=at(1)) == ["r1"]
    assert [m.severity for m in notifier.sent] == [Severity.WARNING, Severity.CRITICAL]


def test_a_failed_send_is_retried_at_the_next_evaluation_and_logged_as_not_sent(tmp_path):
    box, notifier = {"reading": breach()}, Recorder(fail=2)
    alerts = manager(tmp_path, notifier, box)
    assert alerts.evaluate({}, now=at(0)) == [] and alerts.evaluate({}, now=at(1)) == []
    assert alerts.evaluate({}, now=at(2)) == ["r1"]
    history = [json.loads(line) for line in (tmp_path / "alerts" / "history.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [entry["sent"] for entry in history] == [False, False, True]


def test_state_survives_a_restart_so_nothing_is_repeated_or_forgotten(tmp_path):
    box, notifier = {"reading": breach()}, Recorder()
    manager(tmp_path, notifier, box).evaluate({}, now=at(0))
    again = manager(tmp_path, notifier, box)
    assert again.evaluate({}, now=at(5)) == [] and len(notifier.sent) == 1
    box["reading"] = OK
    again.evaluate({}, now=at(6))
    assert manager(tmp_path, notifier, box).evaluate({}, now=at(7)) == ["r1"]  # the streak was saved too
    assert notifier.sent[-1].status == "resolved"


def test_a_corrupt_state_file_starts_clean_instead_of_crashing(tmp_path):
    (tmp_path / "alerts").mkdir()
    (tmp_path / "alerts" / "state.json").write_text("{broken", encoding="utf-8")
    assert manager(tmp_path, Recorder(), {"reading": breach()}).evaluate({}, now=at(0)) == ["r1"]


def test_a_rule_that_raises_does_not_stop_the_others(tmp_path):
    def broken(status):
        raise KeyError("missing field")

    fine = {"reading": breach()}
    alerts = AlertManager(tmp_path / "alerts", Recorder(), rules=[Rule("bad", "Hỏng", broken), rule(fine, rule_id="good")])
    assert alerts.evaluate({}, now=at(0)) == ["good"]


def test_the_message_text_has_severity_title_value_and_vietnam_time():
    message = AlertMessage("r1", "firing", Severity.CRITICAL, "Model ngừng", "reranker không trả lời", datetime(2026, 11, 17, 3, 42, tzinfo=UTC))
    assert message.text() == "[CRITICAL] Campus 24/7 · Model ngừng · reranker không trả lời · 10:42 17/11"
    resolved = AlertMessage("r1", "resolved", Severity.CRITICAL, "Model ngừng", "đều chạy", datetime(2026, 11, 17, 3, 50, tzinfo=UTC))
    assert resolved.text().startswith("[ĐÃ ỔN] ")


def test_naive_clock_is_refused(tmp_path):
    with pytest.raises(ValueError):
        manager(tmp_path, Recorder(), {"reading": OK}).evaluate({}, now=datetime(2026, 1, 1))


def test_composite_succeeds_if_one_channel_works_and_fails_if_all_fail(caplog):
    working, broken = Recorder(), Recorder(fail=99)
    message = AlertMessage("r", "firing", Severity.WARNING, "t", "v", T0)
    CompositeNotifier([broken, working]).send(message)
    assert len(working.sent) == 1
    with caplog.at_level(logging.WARNING, logger="campus247.alerts"):
        with pytest.raises(RuntimeError):
            CompositeNotifier([Recorder(fail=9), Recorder(fail=9)]).send(message)
    assert "channel down" not in caplog.text


def test_log_notifier_writes_the_message(caplog):
    with caplog.at_level(logging.WARNING, logger="campus247.alerts"):
        LogNotifier().send(AlertMessage("r", "firing", Severity.WARNING, "Tiêu đề", "giá trị", T0))
    assert "Tiêu đề · giá trị" in caplog.text
