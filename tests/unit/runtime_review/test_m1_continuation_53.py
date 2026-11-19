"""Deterministic lifecycle/history guards; no native or external requests."""
import json
import sys
from contextlib import contextmanager
from pathlib import Path

import pytest
from fastapi import FastAPI

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "infra/local/rag-fixture"))
import m1_chat_journal_20261012_53 as journal
import m1_frontend_proxy_20261012_53 as proxy
import m1_runtime_20261012_53 as runtime


def test_history_guard_keeps_eight_failed_users_and_rejects_foreign_append():
    initial = journal.original()
    journal.validate(initial, initial)
    messages = [r for r in initial["message"] if r["conversation_id"] == journal.CONVERSATION]
    assert len(messages) == 8
    altered = json.loads(json.dumps(initial))
    altered["message"][0]["content_redacted"] = "changed historical data"
    with pytest.raises(AssertionError):
        journal.validate(altered, initial)
    altered = json.loads(json.dumps(initial))
    altered["message"].append(dict(messages[0], id="foreign", sequence_no=9, content_redacted="unapproved"))
    next(r for r in altered["conversation"] if r["id"] == journal.CONVERSATION)["version"] += 1
    with pytest.raises(AssertionError):
        journal.validate(altered, initial)


def test_static_counter_survives_app_phase_and_refuses_process_reset(monkeypatch):
    monkeypatch.setenv("C247_M1_FRONTEND_PROXY", str(proxy.audit.HERE / "acceptance-20261012-53-frontend"))
    monkeypatch.setattr(proxy, "SHARED_COUNTERS", None)
    original_exists = Path.exists
    authority = proxy.audit.HERE / "acceptance-20261012-53-static-forwarding-authority.json"
    monkeypatch.setattr(Path, "exists", lambda self: False if self == authority else original_exists(self))
    receipts = []
    monkeypatch.setattr(proxy.base, "put", lambda *args: receipts.append(args))
    proxy.install(FastAPI())
    shared = proxy.SHARED_COUNTERS
    shared[0][0] += 3
    shared[1][0] += 123
    proxy.install(FastAPI())
    assert proxy.SHARED_COUNTERS is shared
    assert shared == ([253], [18264272]) and len(receipts) == 1
    monkeypatch.setattr(proxy, "SHARED_COUNTERS", None)
    monkeypatch.setattr(Path, "exists", lambda self: True if self == authority else original_exists(self))
    with pytest.raises(AssertionError, match="cannot reset"):
        proxy.install(FastAPI())


@pytest.mark.parametrize("fail", [False, True])
def test_http_measured_session_pins_caller_and_restores_on_error(monkeypatch, fail):
    events = []
    class Pin:
        @contextmanager
        def pinned(self):
            events.append("pin")
            try:
                yield
            finally:
                events.append("restore")
    def run(self, *args, **kwargs):
        events.append("run")
        if fail:
            raise TimeoutError
        return [[3.0]], .5
    monkeypatch.setattr(runtime, "CallerAffinity", Pin)
    monkeypatch.setattr(runtime.MeasuredSession, "run_measured", run)
    value = object.__new__(runtime.PinnedMeasuredSession)
    if fail:
        with pytest.raises(TimeoutError):
            value.run_measured([], b"logits")
    else:
        assert value.run_measured([], b"logits") == ([[3.0]], .5)
    assert events == ["pin", "run", "restore"]
