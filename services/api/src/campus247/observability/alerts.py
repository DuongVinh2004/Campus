"""Alert state machine: decides when to say something, says it once, repeats rarely, and says when it is over.

For each rule:  OK -> PENDING (breached) -> FIRING (breached for `for_s` seconds; one message)
                FIRING -> OK after two evaluations in a row that are not breached (one "resolved" message)
A rule that cannot judge (None) keeps its state. A message that fails to send is retried at the next evaluation. While a rule
keeps firing the message repeats every `repeat_s` (30 minutes), and at once if the severity rises. The state and a history of
what was sent live in files, so a restart does not repeat a message or forget a firing alert.

Messages carry only the rule's title, a short value and the time. Never user text, identifiers or error strings.
"""
from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol
from zoneinfo import ZoneInfo

from campus247.observability.alert_rules import RULES, Reading, Rule, Severity

LOG = logging.getLogger("campus247.alerts")
VN = ZoneInfo("Asia/Ho_Chi_Minh")
REPEAT_S = 30 * 60
RESOLVE_AFTER = 2  # evaluations in a row


@dataclass(frozen=True)
class AlertMessage:
    rule_id: str
    status: str  # "firing" | "resolved" | "repeat"
    severity: Severity
    title: str
    value: str
    at: datetime

    def text(self) -> str:
        stamp = self.at.astimezone(VN).strftime("%H:%M %d/%m")
        tag = {"firing": f"[{self.severity.value.upper()}]", "repeat": f"[{self.severity.value.upper()} · vẫn còn]", "resolved": "[ĐÃ ỔN]"}[self.status]
        return f"{tag} Campus 24/7 · {self.title} · {self.value} · {stamp}"


class Notifier(Protocol):
    def send(self, message: AlertMessage) -> None: ...


class AlertManager:
    def __init__(self, directory: Path, notifier: Notifier, *, rules: Sequence[Rule] = RULES, repeat_s: int = REPEAT_S) -> None:
        self._dir, self._notifier, self._rules, self._repeat_s = directory, notifier, tuple(rules), repeat_s
        directory.mkdir(parents=True, exist_ok=True)
        self._state_file, self._history = directory / "state.json", directory / "history.jsonl"
        self._state: dict[str, dict[str, Any]] = self._load()

    # ------------------------------------------------------------------ persistence
    def _load(self) -> dict[str, dict[str, Any]]:
        try:
            value = json.loads(self._state_file.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save(self) -> None:
        temporary = self._state_file.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(self._state, indent=1), encoding="utf-8")
        os.replace(temporary, self._state_file)

    def _record(self, message: AlertMessage, sent: bool) -> None:
        line = {"at": message.at.isoformat(), "rule": message.rule_id, "status": message.status, "severity": message.severity.value,
                "value": message.value, "sent": sent}
        with self._history.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(line, ensure_ascii=False) + "\n")

    def snapshot(self) -> dict[str, dict[str, Any]]:
        return json.loads(json.dumps(self._state))

    # ------------------------------------------------------------------ evaluation
    def _send(self, rule: Rule, status: str, severity: Severity, value: str, now: datetime) -> bool:
        message = AlertMessage(rule.id, status, severity, rule.title, value, now)
        try:
            self._notifier.send(message)
        except Exception as error:  # noqa: BLE001 -- a broken channel must not stop evaluation; the next pass retries
            LOG.warning("alert_send_failed rule=%s kind=%s", rule.id, type(error).__name__)
            self._record(message, sent=False)
            return False
        self._record(message, sent=True)
        return True

    def evaluate(self, status: dict[str, Any], *, now: datetime) -> list[str]:
        """Judge every rule against the status document. Returns the ids of rules whose message was sent in this pass."""
        if now.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        sent_ids: list[str] = []
        stamp = now.timestamp()
        for rule in self._rules:
            try:
                reading: Reading | None = rule.evaluate(status)
            except Exception as error:  # noqa: BLE001 -- one broken rule must not hide the others
                LOG.warning("alert_rule_failed rule=%s kind=%s", rule.id, type(error).__name__)
                continue
            if reading is None:
                continue
            state = self._state.setdefault(rule.id, {"state": "OK"})
            if reading.breached:
                state["resolve_streak"] = 0
                if state["state"] == "OK":
                    state.update(state="PENDING", since=stamp)
                if state["state"] == "PENDING" and stamp - state["since"] >= rule.for_s:
                    state.update(state="FIRING", severity=reading.severity.value, last_sent=None)
                if state["state"] == "FIRING":
                    rising = reading.severity == Severity.CRITICAL and state.get("severity") != Severity.CRITICAL.value
                    never_sent = state.get("last_sent") is None
                    due_again = state.get("last_sent") is not None and stamp - state["last_sent"] >= self._repeat_s
                    if never_sent or rising or due_again:
                        label = "firing" if never_sent or rising else "repeat"
                        if self._send(rule, label, reading.severity, reading.value, now):
                            state.update(last_sent=stamp, severity=reading.severity.value)
                            sent_ids.append(rule.id)
            else:
                if state["state"] == "PENDING":
                    state.update(state="OK", since=None)
                elif state["state"] == "FIRING":
                    state["resolve_streak"] = state.get("resolve_streak", 0) + 1
                    if state["resolve_streak"] >= RESOLVE_AFTER:
                        if self._send(rule, "resolved", Severity(state.get("severity", "warning")), reading.value, now):
                            state.update(state="OK", since=None, last_sent=None, resolve_streak=0)
                            sent_ids.append(rule.id)
        self._save()
        return sent_ids


class LogNotifier:
    """Always on: writes the message to the application log."""

    def send(self, message: AlertMessage) -> None:
        LOG.warning("alert %s", message.text())


class CompositeNotifier:
    """Sends through every channel. It succeeds if at least one channel did, so a dead Telegram does not make the log channel retry."""

    def __init__(self, notifiers: Sequence[Notifier]) -> None:
        self._notifiers = list(notifiers)

    def send(self, message: AlertMessage) -> None:
        failures = 0
        for notifier in self._notifiers:
            try:
                notifier.send(message)
            except Exception as error:  # noqa: BLE001
                failures += 1
                LOG.warning("alert_channel_failed channel=%s kind=%s", type(notifier).__name__, type(error).__name__)
        if self._notifiers and failures == len(self._notifiers):
            raise RuntimeError("every alert channel failed")


def now_utc() -> datetime:
    return datetime.now(UTC)


Clock = Callable[[], datetime]
