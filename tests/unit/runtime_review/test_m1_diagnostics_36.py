"""Deterministic measurement/cancellation/privacy tests; never invoke a model."""
import asyncio
import ctypes as ct
import json
import sys
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar

import httpx
import pytest

HERE = Path(__file__).resolve().parents[3] / "infra/local/rag-fixture"
sys.path.insert(0, str(HERE))
import m1_native_measure_20261011_36 as measure
import m1_reranker_diagnostic_20261011_36 as diagnostic
import onnx_inference_20261011_30 as native
from campus247.domain.retrieval import (
    AuthorizedScope,
    RetrievalCandidate,
    RetrievalContext,
    RetrievalQuery,
    SimulationPolicy,
)
from campus247.infrastructure.retrieval.tei import (
    TEIEmbeddingAdapter,
    TEIRerankerAdapter,
)
from campus247.ports.embedding import EmbeddingProfile
from campus247.ports.reranker import (
    RerankerContractError,
    RerankerProfile,
    RerankerTimeoutError,
    RerankRequest,
)


def counters():
    return {"cpu_ns": 10, "memory_available": True, "page_faults": 100,
        "working_set_bytes": 1024, "peak_working_set_bytes": 2048, "commit_bytes": 1024}


def test_counter_wrap_and_unavailable_are_explicit():
    before, after = counters(), counters()
    before["page_faults"] = (1 << 32) - 2
    after.update(page_faults=1, cpu_ns=40)
    result = measure.resource_delta(before, after)
    assert result["page_fault_delta"] == 3 and result["process_cpu_ns"] == 30
    after["memory_available"] = False
    assert measure.resource_delta(before, after)["page_fault_delta"] is None


def test_profile_API_rejects_other_prefix_and_foreign_session(monkeypatch):
    monkeypatch.setattr(diagnostic.CPU, "__init__", lambda self: setattr(self, "fields", {"EnableProfiling": 14, "SessionEndProfiling": 110}))
    engine = diagnostic.ProfileCPU(HERE / "acceptance-20261011-36-profile30" / "reranker")
    with pytest.raises(AssertionError):
        engine.status("EnableProfiling", [ct.c_void_p, ct.c_wchar_p], ct.c_void_p(), "C:\\outside\\profile")
    with pytest.raises(AssertionError):
        engine.status("SessionEndProfiling", [ct.c_void_p, ct.c_void_p, ct.POINTER(ct.c_void_p)], ct.c_void_p(99), ct.c_void_p(), ct.byref(ct.c_void_p()))
    assert "SetOptimizedModelFilePath" not in engine.ALLOWED


def test_profile_summary_uses_runtime_operators_and_marks_partial_trace():
    class ProfileInput:
        def read_bytes(self):
            return json.dumps([{"cat": "Node", "dur": 600, "args": {"op_name": "FusedMatMul"}},
                {"cat": "Session", "dur": 700, "args": {}},
                {"cat": "Node", "dur": 100, "args": {"op_name": "Transpose"}}]).encode()
    result = diagnostic.summarize_profile(ProfileInput())
    assert list(result["operators"]) == ["FusedMatMul", "Transpose"]
    assert result["operators"]["Transpose"]["summed_duration_us"] == 100
    assert "partial" in result["caveat"] and result["runtime_operator_observation"]


def test_phase_clock_is_high_resolution_and_contains_no_exception_text():
    ticks = iter(range(0, 1000, 10))
    row = measure.Measurement(counters, lambda: next(ticks))
    with pytest.raises(ValueError), row.phase("tokenization"):
        raise ValueError("PRIVATE_INPUT_SECRET")
    assert row.rows == [{"phase": "tokenization", "start_offset_ns": 10,
                         "elapsed_ns": 10, "outcome": "failed"}]
    assert "PRIVATE_INPUT" not in json.dumps(row.rows)


def test_windows_memory_ABI_uses_only_current_process():
    class Function:
        def __init__(self, body):
            self.body = body
        def __call__(self, *args):
            return self.body(*args)
    handles = []
    def read(handle, pointer, size):
        handles.append(handle)
        assert size == 72
        pointer._obj.PageFaultCount = 123
        pointer._obj.WorkingSetSize = 4096
        return 1
    class Kernel:
        GetCurrentProcess = Function(lambda: 42)
        K32GetProcessMemoryInfo = Function(read)
    result = measure.OwnedCounters(Kernel())()
    assert handles == [42] and result["memory_available"]
    assert result["page_faults"] == 123 and result["working_set_bytes"] == 4096


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


def test_native_measurement_preserves_logit_shape_and_original_timer(monkeypatch):
    value, api = session(monkeypatch)
    receipts = []
    output, elapsed = invoke(value, receipts)
    assert output == [[2.5]] and elapsed == pytest.approx(.1)
    assert Timer.intervals == [.7] and api.calls.count("Run") == 1
    row = receipts[0]
    assert row["shape"] == [1, 3] and row["token_count"] == 3
    assert {r["phase"] for r in row["phases"]} >= {"tensor_setup", "native_run", "output_extraction"}
    assert row["native_resources"]["page_fault_delta"] == 0
    assert value.engine.measurement is None


@pytest.mark.parametrize("fail,fired,elapsed", [(True, True, .1), (False, True, .1), (False, False, .701)])
def test_original_timeout_enforcement_and_failed_receipt_preserved(monkeypatch, fail, fired, elapsed):
    value, api = session(monkeypatch, fail=fail, fired=fired, elapsed=elapsed)
    receipts = []
    with pytest.raises(TimeoutError, match="700ms"):
        invoke(value, receipts)
    assert Timer.intervals == [.7]
    assert receipts[0]["outcome"] == "timeout" and receipts[0]["timeout_phase"] == "native_run"
    assert "PRIVATE_NATIVE" not in json.dumps(receipts)
    assert "ReleaseRunOptions" in api.calls and value.engine.measurement is None


def test_non_timeout_native_failure_is_never_labeled_timeout(monkeypatch):
    value, _ = session(monkeypatch, fail=True)
    receipts = []
    with pytest.raises(RuntimeError):
        invoke(value, receipts)
    assert receipts[0]["outcome"] == "failed" and receipts[0]["timeout_phase"] is None


def request():
    profile = RerankerProfile("BAAI/bge-reranker-v2-m3", "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e", 20, 100)
    context = RetrievalContext(AuthorizedScope("SYN", "SYN", "actor", frozenset({"STUDENT"}),
        frozenset({"STUDENT"}), frozenset({"FIT"}), frozenset({"SYN"})), "vi",
        datetime(2026, 10, 11, tzinfo=UTC), SimulationPolicy.ALLOW_LABELED, "trace")
    candidate = RetrievalCandidate("source", "version", "chunk", "PRIVATE_PASSAGE_CANARY",
        "Synthetic", "Synthetic", "synthetic://policy", "a" * 64, ("Section 1",))
    return RerankRequest(profile, RetrievalQuery("PRIVATE_QUERY_CANARY"), context, (candidate,))


def client(req, delay=0, revision=None):
    instances = []
    async def handle(http_request):
        if http_request.url.path == "/info":
            if delay:
                await asyncio.sleep(delay)
            body = {"model_id": req.profile.model_id, "model_sha": revision or req.profile.model_revision,
                "model_type": {"reranker": {}}, "auto_truncate": False}
        else:
            body = [{"index": 0, "score": 2.5}]
        return httpx.Response(200, json=body)
    def factory():
        item = httpx.AsyncClient(base_url="https://synthetic.invalid", transport=httpx.MockTransport(handle))
        instances.append(item)
        return item
    return factory, instances


@pytest.mark.asyncio
async def test_adapter_measurement_has_only_safe_phase_fields_and_same_result():
    req = request()
    factory, instances = client(req)
    rows = []
    result = await TEIRerankerAdapter(req.profile, factory, diagnostics=rows.append).rerank(req)
    assert result.ranked[0].score == 2.5 and instances[0].is_closed
    assert {r["phase"] for r in rows} >= {"client_construct", "client_open", "identity_http", "identity_validation",
        "inference_http", "response_decode", "output_validation", "client_close", "adapter_total"}
    assert all(set(r) == {"phase", "elapsed_ns", "outcome", "clock"} and r["elapsed_ns"] >= 0 for r in rows)
    assert "PRIVATE_" not in json.dumps(rows)


@pytest.mark.asyncio
async def test_adapter_deadline_cancellation_records_phase_and_closes_client():
    req = request()
    req = replace(req, profile=replace(req.profile, timeout_ms=5))
    factory, instances = client(req, delay=1)
    rows = []
    with pytest.raises(RerankerTimeoutError):
        await TEIRerankerAdapter(req.profile, factory, diagnostics=rows.append).rerank(req)
    assert instances[0].is_closed
    assert next(r for r in rows if r["phase"] == "identity_http")["outcome"] == "cancelled"
    assert rows[-1]["phase"] == "adapter_total" and rows[-1]["outcome"] == "failed"


@pytest.mark.asyncio
async def test_observer_failure_cannot_accept_foreign_model_or_change_result():
    req = request()
    def denied(row):
        raise ValueError("PRIVATE_OBSERVER_FAILURE")
    factory, _ = client(req, revision="foreign")
    with pytest.raises(RerankerContractError):
        await TEIRerankerAdapter(req.profile, factory, diagnostics=denied).rerank(req)
    factory, _ = client(req)
    result = await TEIRerankerAdapter(req.profile, factory, diagnostics=denied).rerank(req)
    assert result.ranked[0].score == 2.5


@pytest.mark.asyncio
async def test_embedding_diagnostics_do_not_change_normalization_contract():
    profile = EmbeddingProfile("BAAI/bge-m3", "5617a9f61b028005a4858fdac845db406aefb181", 2, timeout_ms=100)
    async def handle(req):
        return httpx.Response(200, json={"model_id": profile.model_id, "model_sha": profile.model_revision,
            "model_type": {"embedding": {}}, "auto_truncate": False} if req.url.path == "/info" else [[1, 0]])
    def factory():
        return httpx.AsyncClient(base_url="https://synthetic.invalid", transport=httpx.MockTransport(handle))
    rows = []
    result = await TEIEmbeddingAdapter(profile, factory, diagnostics=rows.append)._embed(("PRIVATE_EMBED_CANARY",))
    assert result.vectors[0].values == (1., 0.)
    assert rows[-1]["phase"] == "adapter_total" and "PRIVATE_" not in json.dumps(rows)


@pytest.mark.parametrize("module_name", ["m1_chat_journal_20261011_36", "m1_chat_journal_20261011_38"])
def test_continuation_guard_preserves_failed_users_and_rejects_unknown_append(module_name):
    import importlib
    continuation = importlib.import_module(module_name)
    initial = continuation.original()
    continuation.validate(initial, initial)
    altered = json.loads(json.dumps(initial))
    failed = next(r for r in altered["message"] if r["conversation_id"] == continuation.CONVERSATION)
    failed["content_redacted"] = "changed historical data"
    with pytest.raises(AssertionError):
        continuation.validate(altered, initial)
    altered = json.loads(json.dumps(initial))
    failed = next(r for r in altered["message"] if r["conversation_id"] == continuation.CONVERSATION)
    next_sequence = 1+max(r["sequence_no"] for r in altered["message"] if r["conversation_id"] == continuation.CONVERSATION)
    appended = dict(failed, id="unknown-new-message", sequence_no=next_sequence, content_redacted="unapproved question")
    altered["message"].append(appended)
    next(r for r in altered["conversation"] if r["id"] == continuation.CONVERSATION)["version"] += 1
    with pytest.raises(AssertionError):
        continuation.validate(altered, initial)
