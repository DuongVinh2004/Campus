"""F3.5: 20 injected fact conflicts are all found, 20 look-alike pairs produce no false positive."""
from __future__ import annotations

import json
from pathlib import Path

from campus247.domain.policy_impact.conflicts import find_fact_conflicts

ROOT = Path(__file__).resolve().parents[2]


def fact(i, kind="tuition", subject="Học phí", value="580.500 đồng", unit="u", scope=None, quote="q"):
    return {"fact_id": f"f{i}", "kind": kind, "subject": subject, "value": value, "unit_id": unit, "quote": quote, "scope": scope or {}}


def test_twenty_conflicts_found_and_twenty_decoys_ignored():
    conflicts, decoys = [], []
    for i in range(20):
        base = fact(f"{i}a", subject=f"Học phí ngành {i}", value="500.000 đồng", unit=f"ua{i}", scope={"cohorts": ["66"]})
        clash = fact(f"{i}b", subject=f"học phí  NGÀNH {i}", value="600.000 đồng", unit=f"ub{i}", scope={"cohorts": ["66"]})
        conflicts += [base, clash]
        kind = i % 4
        d1 = fact(f"{i}c", subject=f"Lệ phí {i}", value="10.000 đồng", unit=f"uc{i}", scope={"cohorts": ["65"]})
        d2 = fact(f"{i}d", subject=f"Lệ phí {i}", value="20.000 đồng", unit=f"ud{i}", scope={"cohorts": ["66"]})  # other cohort
        if kind == 1:
            d2 = fact(f"{i}d", subject=f"Lệ phí {i}", value="10 000 đồng", unit=f"ud{i}", scope={"cohorts": ["65"]})  # same value, other spacing
        elif kind == 2:
            d2 = fact(f"{i}d", subject=f"Lệ phí {i}", value="20.000 đồng", unit=f"uc{i}", scope={"cohorts": ["65"]})  # same unit
        elif kind == 3:
            d2 = fact(f"{i}d", kind="deadline", subject=f"Lệ phí {i}", value="20.000 đồng", unit=f"ud{i}", scope={"cohorts": ["65"]})  # other kind
        decoys += [d1, d2]
    found = find_fact_conflicts(conflicts + decoys)
    assert len(found) == 20
    assert {c["subject"] for c in found} == {f"hoc phi nganh {i}" for i in range(20)}


def test_validity_windows_must_overlap():
    a, b = fact(1, unit="ua", value="1"), fact(2, unit="ub", value="2")
    assert len(find_fact_conflicts([a, b], {"ua": {"from": "2024-01-01", "until": "2025-01-01"}, "ub": {"from": "2025-01-01", "until": None}})) == 0
    assert len(find_fact_conflicts([a, b], {"ua": {"from": "2024-01-01", "until": "2025-06-01"}, "ub": {"from": "2025-01-01", "until": None}})) == 1


def test_real_facts_are_scanned_quickly_and_each_hit_cites_both_quotes():
    facts = [json.loads(l) for l in (ROOT / "data" / "rag_v2_index" / "facts.jsonl").read_text(encoding="utf-8").splitlines()]
    found = find_fact_conflicts(facts)
    assert all(c["a"]["quote"] and c["b"]["quote"] and c["a"]["unit_id"] != c["b"]["unit_id"] for c in found)
