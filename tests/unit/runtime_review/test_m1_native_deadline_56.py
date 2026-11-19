import ctypes as ct
import json
from typing import ClassVar
import pytest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/"infra/local/rag-fixture"))
import m1_native_measure_20261012_56 as measure
import onnx_inference_20261012_56 as native
def counters():
    return {"cpu_ns": 10, "memory_available": True, "page_faults": 100,
        "working_set_bytes": 1024, "peak_working_set_bytes": 2048, "commit_bytes": 1024}


class FakeAPI:
    def __init__(self, fail=False):
        self.fail = fail
        self.calls = []
        self.logit = (ct.c_float * 1)(2.5)

    def status(self, name, arguments, *values):
        self.calls.append(name)
        if name in {"CreateCpuMemoryInfo", "CreateTensorWithDataAsOrtValue", "CreateRunOptions", "GetTensorTypeAndShape"}:
            values[-1]._obj.value = 1
        elif name == "Run":
            if self.fail:
                raise RuntimeError("PRIVATE_NATIVE_ERROR")
            values[-1][0] = 1
        elif name == "GetTensorElementType":
            values[-1]._obj.value = 1
        elif name == "GetDimensionsCount":
            values[-1]._obj.value = 2
        elif name == "GetDimensions":
            values[-2][0] = 1
            values[-2][1] = 1
        elif name == "GetTensorShapeElementCount":
            values[-1]._obj.value = 1
        elif name == "GetTensorMutableData":
            values[-1]._obj.value = ct.addressof(self.logit)

    def function(self, name, result, arguments):
        return lambda *values: self.calls.append(name)


class Timer:
    fired = False
    intervals: ClassVar[list] = []
    def __init__(self, seconds, callback):
        self.intervals.append(seconds)
        self.callback = callback
    def start(self):
        if self.fired:
            self.callback()
    def cancel(self):
        pass
    def join(self):
        pass


def session(monkeypatch, *, fail=False, fired=False, elapsed=.1):
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
    ticks = iter((1., 1. + elapsed))
    monkeypatch.setattr(native.time, "monotonic", lambda: next(ticks))
    return value, api


def invoke(value, receipts):
    return value.run_measured([[0, 10, 2]], b"logits", ordinal=30,
        payload_sha256="c" * 64, sink=receipts.append)


def test_native_measurement_preserves_logit_shape_and_configured_timer(monkeypatch):
    value, api = session(monkeypatch)
    receipts = []
    output, elapsed = invoke(value, receipts)
    assert output == [[2.5]] and elapsed == pytest.approx(.1)
    assert Timer.intervals == [1.6] and api.calls.count("Run") == 1
    row = receipts[0]
    assert row["shape"] == [1, 3] and row["token_count"] == 3
    assert {r["phase"] for r in row["phases"]} >= {"tensor_setup", "native_run", "output_extraction"}
    assert row["native_resources"]["page_fault_delta"] == 0
    assert value.engine.measurement is None


@pytest.mark.parametrize("fail,fired,elapsed", [(True, True, .1), (False, True, .1), (False, False, 1.601)])
def test_original_timeout_enforcement_and_failed_receipt_preserved(monkeypatch, fail, fired, elapsed):
    value, api = session(monkeypatch, fail=fail, fired=fired, elapsed=elapsed)
    receipts = []
    with pytest.raises(TimeoutError, match="1600ms"):
        invoke(value, receipts)
    assert Timer.intervals == [1.6]
    assert receipts[0]["outcome"] == "timeout" and receipts[0]["timeout_phase"] == "native_run"
    assert "PRIVATE_NATIVE" not in json.dumps(receipts)
    assert "ReleaseRunOptions" in api.calls and value.engine.measurement is None


def test_non_timeout_native_failure_is_never_labeled_timeout(monkeypatch):
    value, _ = session(monkeypatch, fail=True)
    receipts = []
    with pytest.raises(RuntimeError):
        invoke(value, receipts)
    assert receipts[0]["outcome"] == "failed" and receipts[0]["timeout_phase"] is None


