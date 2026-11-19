import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "infra/local/rag-fixture"))
from m1_thread_measure_20261011_48 import delta


def row(created=10, cpu=100, cycles=200):
    return {"created": created, "cpu_ns": cpu, "cycles": cycles, "affinity": {"mask": 4, "group": 0}, "priority": 8}


def test_reused_tid_and_terminated_thread_are_not_misattributed():
    result = delta({1: row(), 2: row(), 3: row()}, {1: row(cpu=200, cycles=400), 2: row(created=11, cpu=0, cycles=0)})
    assert result == [{"tid": 1, "cpu_ns": 100, "cycles": 200, "affinity_before": {"mask": 4, "group": 0}, "affinity_after": {"mask": 4, "group": 0}, "priority": 8}]


def test_regressing_counters_fail_closed():
    with pytest.raises(AssertionError):
        delta({1: row()}, {1: row(cpu=99)})
