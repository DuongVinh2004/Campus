"""The continued profiler can only target its exact fresh workspace prefix."""
import ctypes as ct
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[3] / "infra/local/rag-fixture"
sys.path.insert(0, str(HERE))
import m1_profile_diagnostic_20261011_40 as diagnostic


def test_new_profile_keeps_owned_session_and_exact_API_restrictions(monkeypatch):
    monkeypatch.setattr(diagnostic.CPU, "__init__", lambda self: setattr(self, "fields", {"EnableProfiling": 14, "SessionEndProfiling": 110}))
    engine = diagnostic.ReviewedProfileCPU(diagnostic.PROFILE)
    with pytest.raises(AssertionError):
        engine.status("EnableProfiling", [ct.c_void_p, ct.c_wchar_p], ct.c_void_p(), str(HERE / "foreign"))
    with pytest.raises(AssertionError):
        engine.status("SessionEndProfiling", [ct.c_void_p, ct.c_void_p, ct.POINTER(ct.c_void_p)], ct.c_void_p(99), ct.c_void_p(), ct.byref(ct.c_void_p()))
    assert "SetOptimizedModelFilePath" not in engine.ALLOWED


@pytest.mark.parametrize("path", [HERE / "acceptance-20261011-36-profile30" / "reranker", HERE / "acceptance-20261011-40-profile41" / "foreign"])
def test_profile_rejects_historical_or_other_target(path):
    with pytest.raises(AssertionError):
        diagnostic.ReviewedProfileCPU(path)
