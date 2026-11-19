import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import evaluate_policy_graph_live as runner


def test_preflight_retains_caps_and_reserves_full_campaign_without_opening_gateway(monkeypatch):
    paid = {"calls": 11994, "call_cap": 12000, "hard_cap_usd": "10", "remaining_usd": "5.5956985"}
    native = {"caps": {"http": 20000, "inference": 10000, "tokens": 5000000},
        "counts": {"http": 7976, "inference": 4630, "tokens": 797145}}
    monkeypatch.setattr(runner, "paid_view", lambda: paid.copy())
    monkeypatch.setattr(runner, "native_view", lambda: native)
    report = runner.preflight()
    assert report["admitted"] is False and report["reserved_provider_calls"] == 192
    assert report["proposed_call_cap"] == 12192 and report["conservative_new_reservation_usd"] == "2.88"
    assert paid["call_cap"] == 12000 and report["live_calls_dispatched"] == 0
    with pytest.raises(RuntimeError, match="zero live dispatch"):
        runner.execute(Path("not-used-receipt.json"))


def test_live_questions_do_not_embed_a_gold_rubric_in_model_context():
    data = json.loads(runner.DATASET.read_text(encoding="utf-8"))
    assert len(data["questions"]) == 12 and len(data["extraction_targets"]) == 2
    assert data["model_context_contains_gold"] is False
    assert data["kind"] == "development_authored_not_held_out"
    assert all(isinstance(q, str) for q in data["questions"])


def test_admitted_stage5_preflight_does_not_propose_a_further_cap(monkeypatch):
    monkeypatch.setattr(runner, "paid_view", lambda: {"calls": 11994, "call_cap": 12192, "hard_cap_usd": "10", "remaining_usd": "5.5956985"})
    monkeypatch.setattr(runner, "native_view", lambda: {"caps": {"http": 20000, "inference": 10000, "tokens": 5000000}, "counts": {"http": 7976, "inference": 4630, "tokens": 797145}})
    assert runner.preflight()["admitted"] is True and runner.preflight()["proposed_call_cap"] == 12192
