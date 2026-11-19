"""Read-only ledger admission tests; never create a paid writer."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]
from scripts.run_multi_agent import headroom, make_app
import multi_agent_live_resources as resources
from campus247.application.multi_agent.contracts import MultiAgentPolicy


def test_historical_retained_headroom_fails_without_gateway(monkeypatch, tmp_path):
    monkeypatch.setattr(resources, "AUTHORIZATION", tmp_path / "not-authorized.json")
    monkeypatch.setattr(resources, "paid_view", lambda: {"hard_cap_usd": "3", "call_cap": 8500, "calls": 8495, "remaining_usd": "1.2453405"})
    monkeypatch.setattr(resources, "native_view", lambda: {"caps": {"http": 6000, "inference": 2000, "tokens": 750000},
        "counts": {"http": 2018, "inference": 1990, "tokens": 394527}})
    assert headroom(MultiAgentPolicy()) is False
    from scripts import run_public_rag
    monkeypatch.setattr(run_public_rag, "Gateway", lambda: pytest.fail("admission must fail before writer/credentials"))
    with pytest.raises(RuntimeError, match="insufficient shared ledger"):
        make_app(mode="live")


@pytest.mark.parametrize("short", ["calls", "cost", "inference", "tokens", "http"])
def test_every_resource_is_checked_not_just_remaining_dollars(monkeypatch, short, tmp_path):
    monkeypatch.setattr(resources, "AUTHORIZATION", tmp_path / "not-authorized.json")
    paid = {"hard_cap_usd": "3", "call_cap": 8500, "calls": 8400, "remaining_usd": "1"}
    native = {"caps": {"http": 6000, "inference": 2000, "tokens": 750000},
              "counts": {"http": 100, "inference": 100, "tokens": 100}}
    if short == "calls": paid["calls"] = 8499
    if short == "cost": paid["remaining_usd"] = "0.01"
    if short == "inference": native["counts"]["inference"] = 1990
    if short == "tokens": native["counts"]["tokens"] = 740000
    if short == "http": native["counts"]["http"] = 5990
    monkeypatch.setattr(resources, "paid_view", lambda: paid)
    monkeypatch.setattr(resources, "native_view", lambda: native)
    assert headroom(MultiAgentPolicy()) is False
