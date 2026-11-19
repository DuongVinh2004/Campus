import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "infra/local/rag-fixture"))
from m1_cached_threads_20261011_49 import CachedThreadEngine, CachedThreads, Threads


def test_wrong_thread_owner_closes_acquired_handles(monkeypatch):
    monkeypatch.setattr(Threads, "__call__", lambda self: ({7: {"created": 10, "priority": 8}}, 100))
    closed = []
    obj = object.__new__(CachedThreads)
    obj.pid, obj.handles = 9, {}
    obj.k = SimpleNamespace(OpenThread=lambda rights, inherit, tid: 77, GetProcessIdOfThread=lambda h: 99, CloseHandle=lambda h: closed.append(h) or 1)
    with pytest.raises(AssertionError):
        obj.prime()
    assert closed == [77] and obj.handles == {}


def test_sampling_refuses_unprepared_handles():
    obj = object.__new__(CachedThreads)
    obj.handles = {}
    with pytest.raises(AssertionError, match="prime"):
        obj()


def test_engine_closes_query_handles_before_delegate():
    events = []
    obj = object.__new__(CachedThreadEngine)
    obj.threads = SimpleNamespace(close=lambda: events.append("query-handles"))
    obj.delegate = SimpleNamespace(close=lambda: events.append("model-engine"))
    obj.close()
    assert events == ["query-handles", "model-engine"]
