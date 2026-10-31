"""Deterministic gold arithmetic, fake SSE/HTTP and an in-memory filesystem.

No service, real credentials, corpus, network connection or basetemp is used.
"""
import importlib.util
import io
import json
import socket
import threading
import time
from copy import deepcopy
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("rag_v2_eval", ROOT / "evals/runners/rag_v2_eval.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


@pytest.fixture(autouse=True)
def no_real_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Real network access is forbidden in T7 tests")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)


def case(case_id="c1", **updates):
    return {"case_id": case_id, "split": "holdout", "family": "hoc_phi", "variant": "form",
            "question": "Học phí bao nhiêu?", "expected": "answer", "group_id": "g1",
            "gold": [{"chunk_id": "gold1", "quote": "Học phí 580.500 đồng mỗi tín chỉ."}],
            "required_facts": ["580.500 đồng", "mỗi tín chỉ"], "forbidden_facts": ["999.000 đồng"], **updates}


def row(case_id="c1", repeat=1, **updates):
    return {"case_id": case_id, "repeat": repeat, "outcome_class": "answer",
            "answer_text": "HỌC PHÍ 580,500 ĐỒNG mỗi tín chỉ.", "citation_chunk_ids": ["gold1"],
            "citation_count": 1, "seconds": 2, "first_byte_seconds": .4, "first_content_seconds": 1,
            "final_event": True, "http_status": 200, "error": None, **updates}


@pytest.mark.parametrize("amount", ["580.500", "580,500", "580500", "580 500", "580  500"])
def test_numeric_and_vietnamese_normalization(amount):
    assert runner.normalize(f"HỌC PHÍ {amount} ĐỒNG\n mỗi  tín chỉ") == "hoc phi 580500 dong moi tin chi"
    assert runner.fact_matches("580.500 đồng", f"Học phí {amount} dong/tín chỉ")


def test_fact_boundaries_conditions_and_forbidden():
    assert runner.fact_matches("ít nhất 12 tín chỉ", "SV đăng ký ÍT NHẤT 12 TÍN CHỈ.")
    assert not runner.fact_matches("12 tín chỉ", "112 tín chỉ")
    assert not runner.fact_matches("ít nhất 12 tín chỉ", "12 tín chỉ")
    assert not runner.fact_matches("580500", "1580500")
    assert not runner.fact_matches("", "anything")
    assert runner.normalize("15/09/2026") == "15 09 2026"


def test_known_a1_a3_a5_a6_arithmetic():
    cases = [case(), case("c2", variant="keyword"), case("n", expected="abstain", gold=[], required_facts=[])]
    rows = [row(), row(repeat=2, answer_text="580500 đồng"),  # Missing condition.
            row("c2", answer_text="999000 đồng", citation_chunk_ids=["wrong"]),
            row("c2", repeat=2, outcome_class="refuse", answer_text="Không đủ nguồn"),
            row("n", outcome_class="refuse"), row("n", repeat=2, outcome_class="clarify")]
    report = runner.score_records(rows, cases)
    m = report["metrics"]
    assert m["A1"]["numerator"] == 2 and m["A1"]["denominator"] == 4
    assert m["A1"]["value"] == .5
    assert m["A3"]["value"] == 1
    assert m["A5"]["value"] == pytest.approx(2 / 3)
    assert m["A6"]["value"] is None  # Two repeats no longer measure the three-repeat criterion.
    repeated = runner.score_records(rows + [row(repeat=3), row("c2", repeat=3),
        row("n", repeat=3, outcome_class="refuse")], cases)["metrics"]["A6"]
    assert repeated["value"] == pytest.approx(1 / 3)
    assert repeated["inconsistent_cases"] == ["c2", "n"]
    assert m["A1"]["incorrect"][1]["forbidden_facts"] == ["999.000 đồng"]
    assert report["by_variant"]["keyword"]["A1"]["value"] == .5
    assert report["coverage"]["fewer_than_three_repeats"] == ["c1", "c2", "n"]


def test_proxy_citations_vs_unresolved_chunk_and_no_samples():
    m = runner.score_records([row(citation_chunk_ids=[])], [case()])["metrics"]
    assert m["uncited_answer"]["value"] == 0  # An unresolved citation still exists.
    assert m["A2"]["passed"] is None  # Source text could not be resolved.
    assert m["A5"]["value"] == 0
    assert m["A6"]["passed"] is None
    m = runner.score_records([row(citation_count=0, citation_chunk_ids=[])], [case()])["metrics"]
    assert m["uncited_answer"]["value"] == 1
    assert m["uncited_answer"]["cases"] == [{"case_id": "c1", "repeat": 1}]
    assert runner.score_records([], [case()])["metrics"]["A7"]["passed"] is None


def test_a4_combined_variants_latency_and_strict_a7_boundary():
    variants = ["form", "no_diacritics", "keyword", "slang"]
    cases = [case(str(i), variant=variant) for i, variant in enumerate(variants)]
    rows = [row(str(i), seconds=i + 1, first_byte_seconds=i / 10) for i in range(4)]
    m = runner.score_records(rows, cases)["metrics"]
    assert m["A4"]["passed"]
    assert m["A4"]["by_variant"]["form+no_diacritics"]["denominator"] == 2
    assert m["A8"]["median_seconds"] == 2.5
    assert m["A8"]["p95_seconds"] == 4
    assert m["A8"]["passed"]
    assert runner.ratio(1, 100, .01, maximum=True, strict=True)["passed"] is False
    assert runner.percentile(list(range(1, 101))) == 95
    rows[0]["first_byte_seconds"] = None
    assert runner.score_records(rows, cases)["metrics"]["A8"]["passed"] is None


@pytest.mark.parametrize("updates", [{"outcome_class": "error"}, {"final_event": False},
    {"error": "ReadTimeout"}, {"http_status": 500}])
def test_a7_infrastructure_failures(updates):
    m = runner.score_records([row(**updates)], [case()])["metrics"]
    assert m["A7"]["value"] == 1
    assert m["failures"][0]["label"] == "INFRA"


def test_labels_are_single_and_trace_based_only():
    assert runner.error_label(case(), row(outcome_class="refuse")) == "OVER_REFUSE"
    assert runner.error_label(case(expected="abstain"), row()) == "OVER_ANSWER"
    assert runner.error_label(case(), row(trace={"in_pool": False})) == "RETRIEVAL"
    for label in ("GENERATION", "VERIFICATION", "RERANK", "INGEST", "CORPUS_MISSING"):
        assert runner.error_label(case(), row(trace={"failure_layer": label})) == label
    assert runner.error_label(case(), row()) == "UNLABELED"


def test_split_filter_coverage_duplicates_unknown_cases():
    cases = [case(), case("dev", split="dev")]
    report = runner.score_records([row("dev")], cases)
    assert report["coverage"]["missing_cases"] == ["c1"]
    assert report["metrics"]["A1"]["value"] is None
    for rows in ([row(), row()], [row("unknown")]):
        with pytest.raises(ValueError):
            runner.score_records(rows, cases, strict=True)
    with pytest.raises(ValueError):
        runner.score_records([], [case(), case()])
    report = runner.score_records([row(repeat=i) for i in range(1, 4)], [case()])
    assert report["coverage"]["holdout_three_repeats_complete"]


@pytest.mark.parametrize("final,expected", [
    ({"outcome_kind": "partial"}, "partial"), ({"outcome_kind": "clarify"}, "clarify"),
    ({"outcome_kind": "refuse"}, "refuse"), ({"outcome_kind": "transient_error"}, "error"),
    ({"status": "answered", "response_class": "grounded_answer"}, "answer"),
    ({"status": "answered", "response_class": "partial_answer"}, "partial"),
    ({"status": "abstained", "response_class": "clarification_request"}, "clarify"),
    ({"status": "abstained", "response_class": "safe_refusal"}, "refuse"),
    ({"status": "safe_failure", "response_class": "system_error"}, "error"),
    (None, "error"), ({"status": "unknown"}, "error")])
def test_v2_and_legacy_outcomes(final, expected):
    assert runner.outcome(final) == expected


def test_citation_mapping_direct_nested_quote_title_ambiguity():
    corpus = [{"chunk_id": "a", "doc_title": "Phí", "text": "Phí 580.500 đồng\n mỗi tín chỉ."},
              {"chunk_id": "b", "doc_title": "Khác", "text": "Phí 580.500 đồng mỗi tín chỉ."}]
    assert runner.citation_ids({"citations": [{"citation": {"chunk_id": "z"}}]}, corpus) == ["z"]
    quote = {"quote": "580.500 đồng mỗi tín chỉ."}
    assert runner.citation_ids({"citations": [quote]}, corpus) == []
    assert runner.citation_ids({"citations": [dict(quote, source_title="PHÍ")]}, corpus) == ["a"]
    assert runner.citation_ids({"citations": [{"source_title": "Phí"}]}, corpus) == []


class Chunks(httpx.SyncByteStream):
    def __init__(self, chunks):
        self.chunks = chunks

    def __iter__(self):
        yield from self.chunks


def sse(final, *, delta=True, crlf=False):
    text = ": heartbeat\n\nevent: message.started\ndata: {}\n\n"
    if delta:
        text += 'event: message.delta\ndata: {"delta":"Học phí"}\n\n'
    if final is not None:
        text += "event: message.completed\ndata: " + json.dumps(final, ensure_ascii=False) + "\n\n"
    if crlf:
        text = text.replace("\n", "\r\n")
    raw = text.encode()
    return [raw[i:i + 1] for i in range(len(raw))]  # UTF-8/CRLF boundaries split.


def fake_client(handler):
    return httpx.Client(base_url="http://127.0.0.1:8015", transport=httpx.MockTransport(handler))


def test_stream_fake_sse_new_conversation_each_repeat_and_timing(monkeypatch):
    calls = []
    tick = iter(i / 100 for i in range(1000))
    monkeypatch.setattr(runner.time, "perf_counter", lambda: next(tick))
    final = {"outcome_kind": "answer", "content": "580500 đồng mỗi tín chỉ", "citations": [{"chunk_id": "gold1"}]}

    def handler(request):
        calls.append(request.url.path)
        if request.url.path.endswith("/conversations"):
            return httpx.Response(200, json={"id": "conv" + str(len(calls))})
        return httpx.Response(200, stream=Chunks(sse(final, crlf=True)))

    with fake_client(handler) as client:
        one = runner.run_case(client, case(), 1, [], runner.RateLimit())
        two = runner.run_case(client, case(), 2, [], runner.RateLimit())
    assert one["outcome_class"] == "answer"
    assert one["citation_chunk_ids"] == ["gold1"]
    assert one["first_byte_seconds"] < one["first_content_seconds"] < one["seconds"]
    assert one["conversation_id"] != two["conversation_id"]
    assert one["final_event"] and two["repeat"] == 2


@pytest.mark.parametrize("status,body,error", [(200, None, "MissingFinalEvent"),
    (503, None, "HTTPStatusError"), (200, b"event: message.completed\ndata: invalid\n\n", "JSONDecodeError")])
def test_stream_failures_are_sanitized(status, body, error):
    def handler(request):
        if request.url.path.endswith("/conversations"):
            return httpx.Response(200, json={"id": "conv"})
        return httpx.Response(status, stream=Chunks([body] if body else sse(None)))
    with fake_client(handler) as client:
        record = runner.run_case(client, case(), 1, [], runner.RateLimit())
    assert record["outcome_class"] == "error" and record["error"] == error
    assert not record["final_event"]
    assert record["answer_text"] == ""  # Never expose provisional deltas as final.


def test_stream_and_conversation_429_retries(monkeypatch):
    monkeypatch.setattr(runner.time, "sleep", lambda delay: None)
    limiter = runner.RateLimit()
    monkeypatch.setattr(limiter, "wait", lambda: None)
    deferred = []
    monkeypatch.setattr(limiter, "defer", deferred.append)
    counts = {"conversation": 0, "stream": 0}

    def handler(request):
        name = "conversation" if request.url.path.endswith("/conversations") else "stream"
        counts[name] += 1
        if counts[name] == 1:
            return httpx.Response(429, headers={"Retry-After": "7"})
        return (httpx.Response(200, json={"id": "conv"}) if name == "conversation" else
                httpx.Response(200, stream=Chunks(sse({"outcome_kind": "refuse", "content": "No source"}))))
    with fake_client(handler) as client:
        result = runner.run_case(client, case(), 1, [], limiter)
    assert result["outcome_class"] == "refuse"
    assert counts == {"conversation": 2, "stream": 2} and deferred == ["7", "7"]


def test_rate_limit_global_gate_and_http_date(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(runner.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(runner.time, "sleep", lambda delay: clock.__setitem__(0, clock[0] + delay))
    limiter = runner.RateLimit()
    limiter.defer("7")
    limiter.wait()
    assert clock[0] == pytest.approx(7.3)
    limiter.defer("Thu, 01 Jan 1970 00:00:00 GMT")
    limiter.wait()
    assert clock[0] == pytest.approx(7.6)
    limiter.defer("garbage")
    limiter.wait()
    assert clock[0] == pytest.approx(12.9)


def test_429_exhaustion(monkeypatch):
    limiter = runner.RateLimit()
    monkeypatch.setattr(limiter, "wait", lambda: None)
    with fake_client(lambda request: httpx.Response(429, headers={"Retry-After": "0"})) as client:
        record = row(first_byte_seconds=None, first_content_seconds=None)
        final = runner.stream_reply(client, "/stream", "question", limiter, time.perf_counter(), record)
    assert final is None and record["error"] == "RateLimitExhausted"


def test_trace_attribution_ignores_other_conversations():
    lines = ['conv-other failure_layer="GENERATION"', 'conv-one error_label="VERIFICATION"']
    trace = runner.trace_from_log(lines, "conv-one", case(), [])
    assert trace == {"failure_layer": "VERIFICATION"}


def test_stream_timeout_records_only_exception_type():
    def handler(request):
        if request.url.path.endswith("/conversations"):
            return httpx.Response(200, json={"id": "conv"})
        raise httpx.ReadTimeout("DO_NOT_EXPOSE_PRIVATE_DIAGNOSTIC", request=request)
    with fake_client(handler) as client:
        record = runner.run_case(client, case(), 1, [], runner.RateLimit())
    assert record["outcome_class"] == "error" and record["error"] == "ReadTimeout"
    assert "DO_NOT_EXPOSE" not in json.dumps(record)


def test_sse_multiline_data_and_final_only_content_timing():
    body = b'event: message.completed\ndata: {"outcome_kind":"partial",\ndata: "content":"answer"}\n\n'

    def handler(request):
        if request.url.path.endswith("/conversations"):
            return httpx.Response(200, json={"id": "conv"})
        return httpx.Response(200, stream=Chunks([body]))
    with fake_client(handler) as client:
        record = runner.run_case(client, case(), 1, [], runner.RateLimit())
    assert record["outcome_class"] == "partial" and record["answer_text"] == "answer"
    assert record["first_content_seconds"] is not None


class MemoryFile:
    """Only new virtual paths: tests never create files or a pytest basetemp."""
    files = None

    def __init__(self, name):
        self.name = str(name)

    def __str__(self):
        return self.name

    def resolve(self):
        return self

    def __truediv__(self, name):
        return MemoryFile(self.name + "/" + name)

    @property
    def parent(self):
        return self

    def mkdir(self, **kwargs):
        pass

    def with_name(self, name):
        return MemoryFile(name)

    def exists(self):
        return self.name in self.files

    def read_bytes(self):
        return self.files[self.name]

    def read_text(self, **kwargs):
        return self.read_bytes().decode("utf-8")

    def open(self, mode, **kwargs):
        if "x" in mode and self.exists():
            raise FileExistsError(self.name)
        owner = self

        class Text(io.StringIO):
            def fileno(self):
                return 123

            def close(self):
                if not self.closed:
                    owner.files[owner.name] = self.getvalue().encode()
                super().close()

        class Binary(io.BytesIO):
            def close(self):
                if not self.closed:
                    owner.files[owner.name] = self.getvalue()
                super().close()

        return Binary() if "b" in mode else Text()

    def replace(self, path):
        self.files[str(path)] = self.files.pop(self.name)


@pytest.fixture
def memory(monkeypatch):
    import os
    monkeypatch.setattr(MemoryFile, "files", {})
    monkeypatch.setattr(runner, "writable_path", lambda path: path if isinstance(path, MemoryFile) else MemoryFile(path))
    monkeypatch.setattr(os, "fsync", lambda fd: None)
    return MemoryFile


def test_checkpoint_incremental_resume_force_retains_exact_old_bytes(memory):
    path = memory("out.json")
    saved = runner.prepare_run(path, [case()], "http://localhost")
    saved["records"].append(row())
    runner.write_json(path, saved, replace=True)
    previous_bytes = path.read_bytes()
    assert runner.prepare_run(path, [case()], "http://localhost") == saved
    with pytest.raises(ValueError):
        runner.prepare_run(path, [case(question="different")], "http://localhost")
    assert path.read_bytes() == previous_bytes
    reset = runner.prepare_run(path, [case()], "http://localhost", force=True)
    assert reset["records"] == []
    assert any(content == previous_bytes for name, content in memory.files.items() if ".backup-" in name)
    with pytest.raises(FileExistsError):
        runner.write_json(path, {})


def test_interrupted_atomic_checkpoint_preserves_previous_result(memory, monkeypatch):
    path = memory("out.json")
    runner.write_json(path, {"records": [row()]})
    previous = path.read_bytes()

    def fail_replace(*args):
        raise OSError("simulated interruption")
    monkeypatch.setattr(memory, "replace", fail_replace)
    with pytest.raises(OSError):
        runner.write_json(path, {"records": []}, replace=True)
    assert path.read_bytes() == previous


def test_existing_unrelated_json_cannot_be_overwritten_even_with_force(memory):
    path = memory("unrelated.json")
    runner.write_json(path, {"precious": True})
    before = path.read_bytes()
    with pytest.raises(ValueError):
        runner.prepare_run(path, [case()], "http://localhost", force=True)
    assert path.read_bytes() == before


def test_real_output_boundary_without_writing():
    with pytest.raises(ValueError):
        runner.writable_path(ROOT.parent / "outside.json")
    with pytest.raises(ValueError):
        runner.writable_path(ROOT)
    with pytest.raises(ValueError):
        runner.writable_path(ROOT / "evals" / ".." / "bad.json")


def test_comparison_detects_outcome_and_same_outcome_fact_changes():
    a = runner.score_records([row()], [case()])
    b = runner.score_records([row(outcome_class="refuse")], [case()])
    assert runner.compare_reports(a, b)["changed_cases"][0]["case_id"] == "c1"
    b = runner.score_records([row(answer_text="999000 đồng")], [case()])
    assert len(runner.compare_reports(a, b)["changed_cases"]) == 1
    assert runner.compare_reports(a, a)["changed_cases"] == []
    b["split"] = "dev"
    with pytest.raises(ValueError):
        runner.compare_reports(a, b)


def test_score_compare_cli_json_and_tables(memory, monkeypatch, capsys):
    monkeypatch.setattr(runner, "Path", memory)
    monkeypatch.setattr(runner, "read_jsonl", lambda path: [case()])
    runner.write_json(memory("a.json"), {"records": [row()]})
    runner.write_json(memory("b.json"), {"records": [row()]})
    runner.main(["score", "--results", "a.json", "--results", "b.json", "--cases", "cases.jsonl"])
    report = json.loads(memory("a.json.score.json").read_text())
    assert report["metrics"]["A6"]["value"] is None
    assert "duplicate_repeat" in report["provenance"]["issues"]
    printed = capsys.readouterr().out
    assert "family: hoc_phi" in printed and "variant: form" in printed and "A9 | EXTERNAL" in printed
    runner.main(["compare", "--a", "a.json.score.json", "--b", "a.json.score.json", "--out", "compare.json"])
    assert json.loads(memory("compare.json").read_text())["changed_cases"] == []
    assert "v1 (a) | v2 (b)" in capsys.readouterr().out


def test_run_filters_concurrency_checkpoints_and_resume_without_login(memory, monkeypatch):
    cases = [case(str(i), split="dev") for i in range(5)] + [case("ignored", split="holdout")]
    monkeypatch.setattr(runner, "read_jsonl", lambda path: [] if str(path) == "corpus" else cases)
    monkeypatch.setattr(runner.probe, "STATE", memory("state"))
    memory.files["state/owner-credentials.json"] = b'{"username":"fake-user","password":"fake-secret"}'
    lock = threading.Lock()
    active = [0, 0]
    snapshots = []
    original_write = runner.write_json

    def write(path, result, **kwargs):
        original_write(path, result, **kwargs)
        snapshots.append(deepcopy(result))
    monkeypatch.setattr(runner, "write_json", write)
    client_type = httpx.Client

    def handler(request):
        if request.url.path.endswith("/session"):
            return httpx.Response(200, json={"ok": True})
        if request.url.path.endswith("/conversations"):
            return httpx.Response(200, json={"id": "fake-conversation"})
        with lock:
            active[0] += 1
            active[1] = max(active)
        time.sleep(.01)
        with lock:
            active[0] -= 1
        return httpx.Response(200, stream=Chunks(sse({"outcome_kind": "answer", "content": "580500 đồng mỗi tín chỉ"})))

    monkeypatch.setattr(runner.httpx, "Client", lambda **kwargs: client_type(
        **kwargs, transport=httpx.MockTransport(handler)))
    argv = ["run", "--out", "run.json", "--cases", "cases", "--corpus", "corpus",
            "--split", "dev", "--repeat", "2", "--concurrency", "2", "--limit", "3", "--family", "hoc_phi"]
    runner.main(argv)
    assert active[1] == 2
    assert [len(item["records"]) for item in snapshots] == list(range(7))
    saved = json.loads(memory("run.json").read_text())
    assert len(saved["records"]) == 6 and {row["case_id"] for row in saved["records"]} == {"0", "1", "2"}
    # Extend an interrupted/incomplete campaign: only the missing repeat runs.
    argv[argv.index("--repeat") + 1] = "3"
    runner.main(argv)
    resumed = json.loads(memory("run.json").read_text())
    assert resumed["records"][:6] == saved["records"]
    assert len(resumed["records"]) == 9
    assert all(row["repeat"] == 3 for row in resumed["records"][6:])
    monkeypatch.setattr(runner.httpx, "Client", lambda **kwargs: pytest.fail("Completed resume must not log in"))
    runner.main(argv)
    assert json.loads(memory("run.json").read_text()) == resumed
