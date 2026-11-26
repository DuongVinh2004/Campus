"""F3.1/F3.2: deterministic diff of two releases against labelled mutations of real units."""
from __future__ import annotations

import dataclasses
import random
import re
import time
from pathlib import Path

import pytest

from campus247.domain.policy_impact.diff import Unit, diff_releases, numbers, summarize
from campus247.infrastructure.knowledge.rag_v2_units import RagV2Units

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def corpus():
    import json
    units = []
    with (ROOT / "data" / "rag_v2_index" / "units.jsonl").open(encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            from campus247.infrastructure.knowledge.rag_v2_units import unit_body
            row["text"] = unit_body(row["text"])
            units.append(Unit.from_row(row))
    return units


def mutate_numeric(u: Unit):
    m = re.search(r"\d+", u.text)
    return dataclasses.replace(u, unit_id="n" + u.unit_id, text=u.text[:m.start()] + str(int(m.group(0)) + 7) + u.text[m.end():]) if m else None


def mutate_negation(u: Unit):
    for a, b in ((" được ", " không được "), (" phải ", " không phải "), (" có ", " không có ")):
        if a in u.text:
            return dataclasses.replace(u, unit_id="g" + u.unit_id, text=u.text.replace(a, b, 1))
    return None


def mutate_scope(u: Unit):
    return dataclasses.replace(u, unit_id="s" + u.unit_id, scope={"cohorts": ["66"]})


def mutate_wording(u: Unit):
    return dataclasses.replace(u, unit_id="w" + u.unit_id, text="  ".join(u.text.split(" ")).rstrip(".") + ".")


def mutate_other(u: Unit):
    return dataclasses.replace(u, unit_id="o" + u.unit_id, text=u.text + " Xem thêm quy định liên quan.")


def renumber(u: Unit):
    path = re.sub(r"Điều (\d+)", lambda m: f"Điều {int(m.group(1)) + 20}", u.path, count=1)
    return dataclasses.replace(u, unit_id="r" + u.unit_id, path=path) if path != u.path else None


def build_pairs(corpus, seed=20261126):
    rng = random.Random(seed)
    pool = [u for u in corpus if u.doc_family == "quy_che" and len(u.text) > 80 and "Điều" in u.path]
    rng.shuffle(pool)
    kinds = [("NUMERIC", mutate_numeric), ("NEGATION", mutate_negation), ("SCOPE", mutate_scope), ("WORDING_ONLY", mutate_wording),
             ("TEXT_OTHER", mutate_other), ("RENUMBERED", renumber), ("REMOVED", None), ("ADDED", None)]
    cases, i = [], 0
    for kind, fn in kinds:
        made = 0
        while made < 8 and i < len(pool):
            u = pool[i]; i += 1
            if kind == "REMOVED":
                cases.append((kind, u, None)); made += 1; continue
            if kind == "ADDED":
                cases.append((kind, None, dataclasses.replace(u, unit_id="a" + u.unit_id, path="Điều 99 > Khoản 9", text="Quy định mới hoàn toàn về nội dung khác " + u.text[:60]))); made += 1; continue
            new = fn(u)
            if new is not None:
                cases.append((kind, u, new)); made += 1
    return cases


def test_sixty_labelled_pairs(corpus):
    cases = build_pairs(corpus)
    assert len(cases) >= 60
    context = [u for u in corpus if u.doc_family != "quy_che"][:25]
    ok = 0
    failures = []
    for kind, old, new in cases:
        old_units = context + ([old] if old else [])
        new_units = context + ([new] if new else [])
        changed = [c for c in diff_releases(old_units, new_units) if c.status != "UNCHANGED"]
        verdict = None
        if len(changed) == 1:
            c = changed[0]
            if kind in {"REMOVED", "ADDED"}:
                verdict = c.status == kind
            elif kind == "RENUMBERED":
                verdict = c.status == "MOVED" and c.renumbered
            elif kind == "WORDING_ONLY":
                verdict = c.status == "MODIFIED" and c.labels == ["WORDING_ONLY"] and c.severity == "LOW"
            elif kind == "NUMERIC":
                verdict = c.status == "MODIFIED" and "NUMERIC" in c.labels and c.severity == "HIGH"
            elif kind == "NEGATION":
                verdict = c.status == "MODIFIED" and "NEGATION" in c.labels and c.severity == "HIGH"
            elif kind == "SCOPE":
                verdict = c.status == "MODIFIED" and c.labels == ["SCOPE"] and c.severity == "HIGH"
            elif kind == "TEXT_OTHER":
                verdict = c.status == "MODIFIED" and c.labels == ["TEXT_OTHER"] and c.severity == "MEDIUM"
        if verdict:
            ok += 1
        else:
            failures.append((kind, [(c.status, c.labels) for c in changed]))
    assert ok / len(cases) >= 0.99, failures[:5]
    assert not failures


def test_numeric_normalisation_ignores_formatting_but_not_values():
    a = Unit("1", "d", "v", "hoc_phi", "t", "Điều 1", "Học phí 580.500 đồng mỗi tín chỉ, hạn 15/12/2026")
    same = dataclasses.replace(a, unit_id="2", text="Học phí 580500 đồng mỗi tín chỉ, hạn 15/12/2026")
    changed = dataclasses.replace(a, unit_id="3", text="Học phí 600.000 đồng mỗi tín chỉ, hạn 15/12/2026")
    assert numbers(a.text) == numbers(same.text) != numbers(changed.text)
    deadline = dataclasses.replace(a, unit_id="4", text="Học phí 580.500 đồng mỗi tín chỉ, hạn 20/12/2026")
    c = [x for x in diff_releases([a], [deadline]) if x.status != "UNCHANGED"][0]
    assert "DEADLINE" in c.labels and "NUMERIC" in c.labels and c.severity == "HIGH"
    assert c.public()["numeric"]


def test_new_edition_with_identical_text_is_low_severity():
    old = Unit("1", "d1", "v1", "quy_che", "Quy chế 2023", "Điều 3 > Khoản 1", "Sinh viên phải đóng học phí đúng hạn theo thông báo.")
    new = Unit("2", "d1", "v2", "quy_che", "Quy chế 2024", "Điều 3 > Khoản 1", "Sinh viên  phải đóng học phí đúng hạn theo thông báo.")
    [c] = [x for x in diff_releases([old], [new])]
    assert c.status == "UNCHANGED_TEXT_NEW_EDITION" and c.severity == "LOW"


def test_whole_index_diff_is_fast_and_reports_only_the_injected_changes(corpus):
    pool = [u for u in corpus if u.doc_family == "quy_che" and re.search(r"\d", u.text)][:20]
    mutated = {u.unit_id: mutate_numeric(u) for u in pool}
    new = [mutated.get(u.unit_id) or u for u in corpus]
    t = time.perf_counter()
    changes = diff_releases(corpus, new)
    elapsed = time.perf_counter() - t
    summary = summarize(changes)
    assert elapsed < 60, elapsed
    assert summary["by_status"].get("MODIFIED") == 20 and summary["by_status"].get("ADDED", 0) == 0 and summary["by_status"].get("REMOVED", 0) == 0
    assert summary["by_status"]["UNCHANGED"] == len(corpus) - 20
