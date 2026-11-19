import ctypes as ct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "infra/local/rag-fixture"))
from m1_affinity_20261011_41 import CPU, CallerAffinity


class Function:
    def __init__(self, fn):
        self.fn = fn

    def __call__(self, *args):
        return self.fn(*args)


def fake_kernel(mask=85):
    calls = []
    def read(handle, process, system):
        assert handle == 42
        process._obj.value = mask
        system._obj.value = 4095
        return 1
    def write(handle, value):
        assert handle == 43
        calls.append(value)
        return 85 if value == 1 else 1
    class Kernel:
        GetCurrentProcess = Function(lambda: 42)
        GetCurrentThread = Function(lambda: 43)
        GetProcessAffinityMask = Function(read)
        SetThreadAffinityMask = Function(write)
    return Kernel(), calls


@pytest.mark.parametrize("fail", [False, True])
def test_only_current_caller_and_exact_previous_mask_restored(fail):
    kernel, calls = fake_kernel()
    pin = CallerAffinity(kernel)
    try:
        with pin.pinned() as row:
            assert row["worker_masks"] == [4, 16, 64] and row["caller_mask"] == 1
            if fail:
                raise TimeoutError
    except TimeoutError:
        assert fail
    assert calls == [1, 85]


def test_other_process_allocation_refused_before_affinity_mutation():
    kernel, calls = fake_kernel(255)
    with pytest.raises(AssertionError), CallerAffinity(kernel).pinned():
        pass
    assert calls == []


def test_config_rejects_other_workers_before_C_API_call():
    engine = object.__new__(CPU)
    with pytest.raises(AssertionError):
        engine.status("AddSessionConfigEntry", [ct.c_void_p, ct.c_char_p, ct.c_char_p], ct.c_void_p(), b"session.intra_op_thread_affinities", b"1;2;3")
    assert CPU.CONFIG[b"session.intra_op_thread_affinities"] == b"3;5;7"
