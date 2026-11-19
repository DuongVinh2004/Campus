"""A run above the old deadline succeeds; cancellation and scope stay enforced."""
import ctypes as ct
import json
import sys
from pathlib import Path

import pytest

from tests.unit.runtime_review.test_m1_native_deadline_56 import (
    FakeAPI,
    Timer,
    counters,
)

HERE = Path(__file__).resolve().parents[3] / "infra/local/rag-fixture"
sys.path.insert(0, str(HERE))
import m2_inference_20261012_64 as native
import m2_native_measure_20261012_64 as measure


def session(monkeypatch, *, elapsed=2.0, fail=False, fired=False):
    api = FakeAPI(fail)
    value = measure.MeasuredSession.__new__(measure.MeasuredSession)
    value.engine = measure.MeteredEngine(api)
    value.handle = ct.c_void_p(1)
    value.validation = {"graph_sha256": "a" * 64}
    value.config_sha256 = "b" * 64
    value.counters = counters
    monkeypatch.setattr(native.threading, "Timer", Timer)
    monkeypatch.setattr(Timer, "fired", fired)
    Timer.intervals = []
    ticks = iter((1.0, 1.0 + elapsed))
    monkeypatch.setattr(native.time, "monotonic", lambda: next(ticks))
    return value, api


def invoke(value, receipts):
    return value.run_measured([[0, 10, 2]], b"logits", ordinal=115,
                             payload_sha256="c" * 64, sink=receipts.append)


def test_run_past_old_deadline_uses_new_timer_and_returns_real_shape(monkeypatch):
    value, api = session(monkeypatch)
    receipts = []
    output, elapsed = invoke(value, receipts)
    assert output == [[2.5]] and elapsed == pytest.approx(2.0)
    assert Timer.intervals == [3.0] and api.calls.count("Run") == 1
    assert receipts[0]["outcome"] == "completed"
    assert "3000/1000" in receipts[0]["deadline_enforcement"]


@pytest.mark.parametrize("fail,fired,elapsed", [(True, True, 0.1),
                                              (False, True, 0.1), (False, False, 3.001)])
def test_new_deadline_still_cancels_and_preserves_failure(monkeypatch, fail, fired, elapsed):
    value, api = session(monkeypatch, fail=fail, fired=fired, elapsed=elapsed)
    receipts = []
    with pytest.raises(TimeoutError, match="3000ms"):
        invoke(value, receipts)
    assert Timer.intervals == [3.0]
    assert receipts[0]["outcome"] == "timeout"
    assert "ReleaseRunOptions" in api.calls and value.engine.measurement is None
    assert "PRIVATE_NATIVE_ERROR" not in json.dumps(receipts)


def test_non_timeout_errors_keep_their_failure_class(monkeypatch):
    value, _ = session(monkeypatch, fail=True)
    receipts = []
    with pytest.raises(RuntimeError):
        invoke(value, receipts)
    assert receipts[0]["outcome"] == "failed"


def test_all_consumers_use_same_overlay_and_preserve_M1():
    import m1_config_20261012_56 as previous
    import m2_config_20261012_64 as current
    import m2_runtime_20261012_64 as runtime
    from campus247.application.retrieval.profile import load_retrieval_profile
    from campus247.application.retrieval.runtime_config import (
        validate_effective_profile,
    )
    from campus247.bootstrap.settings import Settings

    timing = current.config()
    assert native.DEADLINES == measure.DEADLINES == runtime.DEADLINES == timing
    assert measure.Session is native.Session
    assert runtime.MeasuredSession is measure.MeasuredSession
    assert (timing.native_ms, timing.adapter_ms, timing.retrieval_ms) == (3000, 4000, 8500)
    effective = timing.apply(load_retrieval_profile())
    validate_effective_profile(effective)
    assert (effective.semantic_timeout_ms, effective.reranker_timeout_ms,
            effective.overall_timeout_ms) == (4000, 4000, 8500)
    assert effective.evidence_support_threshold == 0.78
    assert previous.config().native_ms == 1600
    with pytest.raises(ValueError):
        Settings(_env_file=None, ENVIRONMENT="production", DEMO_MODE=True,
                 RETRIEVAL_RUNTIME_DEADLINES=timing)
