import json
import math
import os

import pytest
from campus247.observability import ops_metrics as om
from campus247.observability.ops_metrics import (
    LATENCY_BUCKETS_S,
    OpsMetrics,
    aggregate,
    percentile_upper_bound,
    prune_snapshots,
    summarize_window,
    write_snapshot,
)

T0 = 1_800_000_000.0  # a whole minute: T0 % 60 == 0


class Clock:
    def __init__(self, now=T0):
        self.now = now

    def __call__(self):
        return self.now


def metrics(clock=None):
    return OpsMetrics(clock or Clock())


class TestRecording:
    def test_turns_are_counted_by_outcome_and_latency_bucket(self):
        clock = Clock()
        m = metrics(clock)
        m.record_turn(outcome="ok", first_token_s=0.4, total_s=4.0)
        m.record_turn(outcome="ok", first_token_s=1.5, total_s=11.9)
        m.record_turn(outcome="abstained", first_token_s=0.2, total_s=1.0)
        m.record_turn(outcome="error", error_code="AI_WORKFLOW_UNAVAILABLE", total_s=30.0)
        (minute,) = m.snapshot()["minutes"]
        assert (minute["turns"], minute["ok"], minute["abstained"]) == (4, 2, 1)
        assert minute["errors"] == {"AI_WORKFLOW_UNAVAILABLE": 1}
        edges = list(LATENCY_BUCKETS_S)
        assert minute["total"][edges.index(5.0)] == 1 and minute["total"][edges.index(12.0)] == 1
        assert minute["total"][edges.index(1.0)] == 1 and minute["total"][edges.index(30.0)] == 1
        assert sum(minute["first_token"]) == 3

    def test_a_value_above_the_last_bound_goes_to_the_overflow_bucket(self):
        m = metrics()
        m.record_turn(outcome="ok", total_s=31.0)
        assert m.snapshot()["minutes"][0]["total"][-1] == 1

    def test_error_codes_are_whitelisted_by_shape_so_text_cannot_leak(self):
        m = metrics()
        m.record_turn(outcome="error", error_code="RuntimeError: sinh viên 20215678 hỏi về điểm", total_s=1)
        m.record_turn(outcome="error", error_code=None, total_s=1)
        m.record_turn(outcome="error", error_code="lowercase", total_s=1)
        assert m.snapshot()["minutes"][0]["errors"] == {"OTHER": 3}

    def test_unknown_outcome_is_a_programming_error(self):
        with pytest.raises(ValueError):
            metrics().record_turn(outcome="weird", total_s=1)

    def test_route_groups_are_a_fixed_set(self):
        m = metrics()
        m.record_rate_limited("chat")
        m.record_rate_limited("/v1/conversations/abc-123")
        assert m.snapshot()["minutes"][0]["rate_limited"] == {"chat": 1, "other": 1}

    def test_loop_blocks_keep_the_longest(self):
        m = metrics()
        m.record_loop_blocked(1200)
        m.record_loop_blocked(3400)
        m.record_loop_blocked(900)
        minute = m.snapshot()["minutes"][0]
        assert (minute["loop_blocked"], minute["loop_blocked_max_ms"]) == (3, 3400)

    def test_old_minutes_fall_out_of_the_ring(self):
        clock = Clock()
        m = OpsMetrics(clock, window_minutes=60)
        m.record_admission_rejected()
        clock.now += 61 * 60
        m.record_admission_rejected()
        minutes = m.snapshot()["minutes"]
        assert [x["admission_rejected"] for x in minutes] == [1]

    def test_snapshot_holds_only_numbers_and_fixed_labels(self):
        m = metrics()
        m.record_turn(outcome="error", error_code="BAD_CODE", first_token_s=1, total_s=2)
        m.record_rate_limited("auth")
        text = json.dumps(m.snapshot())
        assert all(word not in text for word in ("question", "subject", "conversation", "message"))


class TestSharingBetweenWorkers:
    def make_worker(self, directory, pid, now, *, turns, retrieval=None, gauges=(2, 0, 16)):
        clock = Clock(now)
        m = OpsMetrics(clock)
        for _ in range(turns):
            m.record_turn(outcome="ok", first_token_s=1.0, total_s=3.0)
        m.set_gauges(in_flight=gauges[0], waiting=gauges[1], limit=gauges[2])
        snapshot = m.snapshot(retrieval) | {"pid": pid}
        write_snapshot(directory, snapshot)

    def test_two_workers_add_up_and_a_dead_worker_drops_out(self, tmp_path):
        self.make_worker(tmp_path, 101, T0 + 10, turns=3, retrieval={"retrievals": 25, "failed": 1, "timeouts": 1, "vector_ms_max": 1100})
        self.make_worker(tmp_path, 102, T0 + 12, turns=4, retrieval={"retrievals": 25, "failed": 0, "timeouts": 0, "vector_ms_max": 400})
        self.make_worker(tmp_path, 103, T0 - 300, turns=99)  # stopped five minutes ago
        merged = aggregate(tmp_path, now=T0 + 20)
        assert merged["workers_reporting"] == 2
        assert merged["gauges"] == {"in_flight": 4, "waiting": 0, "limit": 32}
        assert merged["retrieval"]["retrievals"] == 50 and merged["retrieval"]["failed"] == 1
        assert merged["retrieval"]["failed_rate"] == pytest.approx(0.02) and merged["retrieval"]["vector_ms_max"] == 1100
        assert sum(m["turns"] for m in merged["minutes"]) == 7

    def test_missing_directory_and_damaged_files_are_not_fatal(self, tmp_path):
        assert aggregate(tmp_path / "nope", now=T0)["workers_reporting"] == 0
        (tmp_path / "worker-1.json").write_text("{not json", encoding="utf-8")
        assert aggregate(tmp_path, now=T0)["workers_reporting"] == 0

    def test_write_is_atomic_and_leaves_no_temporary_file(self, tmp_path):
        self.make_worker(tmp_path, 7, T0, turns=1)
        assert sorted(p.name for p in tmp_path.iterdir()) == ["worker-7.json"]

    def test_prune_deletes_only_stale_worker_snapshots(self, tmp_path):
        self.make_worker(tmp_path, 1, T0 - 1000, turns=1)
        self.make_worker(tmp_path, 2, T0 - 5, turns=1)
        (tmp_path / "notes.txt").write_text("keep me", encoding="utf-8")
        assert prune_snapshots(tmp_path, now=T0) == 1
        assert sorted(p.name for p in tmp_path.iterdir()) == ["notes.txt", "worker-2.json"]


class TestWindowSummary:
    def test_percentiles_use_bucket_upper_bounds(self):
        hist = [0] * (len(LATENCY_BUCKETS_S) + 1)
        hist[list(LATENCY_BUCKETS_S).index(5.0)] = 90
        hist[list(LATENCY_BUCKETS_S).index(12.0)] = 10
        assert percentile_upper_bound(hist, 0.50) == 5.0
        assert percentile_upper_bound(hist, 0.90) == 5.0
        assert percentile_upper_bound(hist, 0.95) == 12.0
        assert percentile_upper_bound([0] * len(hist), 0.95) is None
        hist[-1] = 100
        assert percentile_upper_bound(hist, 0.95) == math.inf

    def test_window_picks_only_recent_minutes_and_computes_rates(self, tmp_path):
        clock = Clock(T0)
        m = OpsMetrics(clock)
        for _ in range(10):
            m.record_turn(outcome="ok", first_token_s=1, total_s=4)  # minute T0
        clock.now = T0 + 20 * 60
        for _ in range(18):
            m.record_turn(outcome="ok", first_token_s=1, total_s=6)
        m.record_turn(outcome="error", error_code="AI_WORKFLOW_UNAVAILABLE", total_s=20)
        m.record_turn(outcome="error", error_code="AI_WORKFLOW_UNAVAILABLE", total_s=20)
        m.record_admission_rejected()
        m.record_admission_rejected()
        write_snapshot(tmp_path, m.snapshot() | {"pid": os.getpid()})
        merged = aggregate(tmp_path, now=T0 + 20 * 60 + 5)
        recent = summarize_window(merged, minutes=5)
        assert recent["turns"] == 20 and recent["errors"] == {"AI_WORKFLOW_UNAVAILABLE": 2}
        assert recent["error_rate"] == pytest.approx(0.1)
        assert recent["admission_rejected_rate"] == pytest.approx(2 / 22)
        assert recent["p95_s_le"] == 20.0 and recent["p50_s_le"] == 8.0
        assert summarize_window(merged, minutes=30)["turns"] == 30

    def test_empty_window(self):
        merged = {"now": T0, "minutes": []}
        summary = summarize_window(merged, minutes=5)
        assert summary["turns"] == 0 and summary["p95_s_le"] is None and summary["error_rate"] == 0.0


def sse(name, data):
    return f"id: 018f\nevent: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


class TestTurnObserver:
    def observer(self):
        clock = Clock(100.0)
        target = metrics()
        return clock, target, om.TurnObserver(target, clock=clock)

    def test_a_grounded_answer_is_ok_with_first_token_and_total_time(self):
        clock, target, watch = self.observer()
        watch.feed(sse("message.started", {"message_id": "m"}))
        clock.now += 1.2
        watch.feed(sse("message.delta", {"seq": 1, "delta": "Xin chào"}))
        clock.now += 3.0
        watch.feed(sse("message.delta", {"seq": 2, "delta": " bạn"}))
        watch.feed(sse("message.completed", {"status": "answered", "content": "Câu hỏi riêng tư của sinh viên"}))
        watch.finish()
        minute = target.snapshot()["minutes"][0]
        assert (minute["turns"], minute["ok"], minute["abstained"]) == (1, 1, 0)
        edges = list(LATENCY_BUCKETS_S)
        assert minute["first_token"][edges.index(2.0)] == 1 and minute["total"][edges.index(5.0)] == 1
        assert "riêng tư" not in json.dumps(target.snapshot())

    def test_an_abstained_answer_is_counted_apart(self):
        _, target, watch = self.observer()
        watch.feed(sse("message.completed", {"status": "abstained"}))
        watch.finish()
        assert target.snapshot()["minutes"][0]["abstained"] == 1

    def test_a_failed_turn_records_its_error_code(self):
        _, target, watch = self.observer()
        watch.feed(sse("message.failed", {"code": "AI_WORKFLOW_UNAVAILABLE", "detail": "chi tiết"}))
        watch.finish()
        assert target.snapshot()["minutes"][0]["errors"] == {"AI_WORKFLOW_UNAVAILABLE": 1}

    def test_events_split_across_bytes_chunks_and_extra_events_are_handled(self):
        _, target, watch = self.observer()
        watch.feed(sse("agent.status", {"stage": "retrieve"}).encode())
        watch.feed(sse("citation.added", {"citation": {}}).encode())
        watch.feed(sse("message.completed", {"status": "answered"}).encode())
        watch.finish()
        assert target.snapshot()["minutes"][0]["ok"] == 1

    def test_an_abandoned_turn_is_not_recorded_and_finish_is_idempotent(self):
        _, target, watch = self.observer()
        watch.feed(sse("message.delta", {"seq": 1, "delta": "x"}))
        watch.finish()
        assert target.snapshot()["minutes"] == []
        watch.feed(sse("message.completed", {"status": "answered"}))
        watch.finish()
        watch.finish()
        assert target.snapshot()["minutes"][0]["turns"] == 1

    def test_garbage_in_a_terminal_event_does_not_raise(self):
        _, target, watch = self.observer()
        watch.feed("event: message.completed\ndata: {broken\n\n")
        watch.finish()
        assert target.snapshot()["minutes"][0]["ok"] == 1


def test_module_constants_are_consistent():
    assert list(LATENCY_BUCKETS_S) == sorted(LATENCY_BUCKETS_S) and om.FRESH_FOR_S > om.WRITE_EVERY_S
