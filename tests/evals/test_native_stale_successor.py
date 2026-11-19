"""An interrupted empty branch cannot reset charges or hide another worker."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import multi_agent_live_resources as resources


@pytest.fixture
def lineage(tmp_path, monkeypatch):
    monkeypatch.setattr(resources, "ROOT", tmp_path)
    monkeypatch.setattr(resources, "native_process_stopped", lambda pid: True)
    parent = tmp_path / "infra/local"
    parent.mkdir(parents=True)
    prior = parent / "rag-advanced-models-20261013-13"
    stale = parent / "rag-advanced-models-20261013-14"
    target = parent / "rag-advanced-models-20261013-15"
    prior.mkdir(); stale.mkdir()
    def record(directory, name, value):
        path = directory / name
        path.write_text(json.dumps(value), encoding="utf-8")
        return path
    last = {"caps": dict(resources.NATIVE_CAPS),
            "counts": {"http": 9353, "inference": 6121, "tokens": 1016597}, "reset": False}
    lower = {"http": 8694, "inference": 5440, "tokens": 905286}
    record(prior, "resource-transition.json", last)
    for directory in (prior, stale):
        record(directory, "launch.json", {"owned_pid": 1234})
    record(stale, "predecessor.json", {"path": str(prior), "retained_counts": lower, "reset": False})
    record(stale, "resource-transition.json", {"caps": dict(resources.NATIVE_CAPS), "counts": lower, "reset": False})
    authorization = {"native_caps": dict(resources.NATIVE_CAPS),
                     "native_before": {"counts": {"http": 2018, "inference": 1990, "tokens": 394527}}}
    return prior, stale, target, last, authorization, record


def test_empty_stopped_successor_keeps_exact_charges_and_evidence(lineage):
    prior, stale, target, last, auth, _ = lineage
    before = {p: p.read_bytes() for p in prior.parent.rglob("*.json")}
    counts, caps, proof = resources.recover_native_successor(last, auth, target, prior)
    assert counts == last["counts"] and caps == last["caps"]
    assert proof["skipped_usage_records"] == 0 and proof["caps_changed"] is False
    assert proof["historical_usage_retained"] is True and len(proof["evidence_sha256"]) == 4
    assert all(p.read_bytes() == data for p, data in before.items())
    assert not target.exists()


@pytest.mark.parametrize("tamper", ["usage", "result", "running", "lineage", "counter", "caps", "destination", "other_usage", "changed_predecessor"])
def test_recovery_rejects_unsafe_branches(lineage, monkeypatch, tamper):
    prior, stale, target, last, auth, record = lineage
    if tamper in {"usage", "result"}:
        record(stale, "native-05441-" + ("reservation" if tamper == "usage" else "result") + ".json", {})
    elif tamper == "running":
        monkeypatch.setattr(resources, "native_process_stopped", lambda pid: False)
    elif tamper == "lineage":
        record(stale, "predecessor.json", {"path": str(stale), "reset": False})
    elif tamper == "counter":
        last = {**last, "counts": {**last["counts"], "tokens": 0}}
    elif tamper == "caps":
        auth = {**auth, "native_caps": {**auth["native_caps"], "inference": 20000}}
    elif tamper == "destination":
        target = target.parent / "rag-advanced-models-20261013-16"
    elif tamper == "other_usage":
        other = target.parent / "rag-advanced-models-20261013-12"
        other.mkdir()
        record(other, "resource-transition.json", {**last, "counts": {**last["counts"], "http": 10000}})
    else:
        record(prior, "resource-transition.json", {**last, "counts": {**last["counts"], "inference": 6122}})
    with pytest.raises(ValueError):
        resources.recover_native_successor(last, auth, target, prior)
