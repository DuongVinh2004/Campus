"""Independent two-valued oracle and automatic boundary/combinatorial vectors for a rule.

The oracle shares nothing with engine.eval_node except the arithmetic derivation: it only answers for
*complete* inputs, using plain Python all/any and operator functions. The engine must agree on every vector.
"""
from __future__ import annotations

import operator
import random

from campus247.domain.policy_rules.engine import _breakpoints, _grid, evaluate
from campus247.domain.policy_rules.rule import predicates
from campus247.domain.policy_rules.variables import Vocabulary

_OPS = {"<": operator.lt, "<=": operator.le, ">": operator.gt, ">=": operator.ge, "=": operator.eq, "!=": operator.ne}


def oracle(body_when: dict, values: dict) -> bool:
    """True/False for a rule tree over complete values; KeyError if a needed variable is absent."""
    if "pred" in body_when:
        p = body_when["pred"]
        x = values[p["var"]]
        op, c = p["op"], p["value"]
        if op == "between":
            lo_ok = x >= c[0] if p.get("closed", (True, True))[0] else x > c[0]
            hi_ok = x <= c[1] if p.get("closed", (True, True))[1] else x < c[1]
            return lo_ok and hi_ok
        if op == "in":
            return x in c
        if op == "not_in":
            return x not in c
        return _OPS[op](x, c)
    if "not" in body_when:
        return not oracle(body_when["not"], values)
    if "all" in body_when:
        return all(oracle(c, values) for c in body_when["all"])
    return any(oracle(c, values) for c in body_when["any"])


def _candidates(vocab: Vocabulary, rec: dict, key: str, base: dict, inputs_hint: dict):
    var = vocab.get(key)
    if var.type == "boolean":
        return [True, False]
    if var.type == "enum":
        return list(var.values)
    if not var.numeric:
        return []
    lo = var.min if var.min is not None else 0.0
    hi = var.max if var.max is not None else lo + 100
    step = var.grid_step
    cands = {_grid(var, lo), _grid(var, hi), _grid(var, (lo + hi) / 2)}
    for b in _breakpoints(vocab, rec, key, base, inputs_hint):
        for d in (-1, 0, 1):
            cands.add(_grid(var, round(b / step) * step + d * step))
    out = sorted(c for c in cands if lo - 1e-9 <= c <= hi + 1e-9)
    return [int(c) if var.type == "integer" else c for c in out]


def input_variables(vocab: Vocabulary, body: dict) -> list[str]:
    keys: list[str] = []
    for node in predicates(body["when"]):
        v = node["pred"]["var"]
        for b in (vocab.base_variables(v) if vocab.expr(v) else (v,)):
            if b not in keys:
                keys.append(b)
    return keys


def generate_vectors(vocab: Vocabulary, body: dict, *, seed: int = 20261126, limit: int = 240) -> list[dict]:
    rec = {"body": body}
    keys = input_variables(vocab, body)
    rng = random.Random(seed)
    mid = {}
    for k in keys:
        v = vocab.get(k)
        if v.type == "boolean":
            mid[k] = True
        elif v.type == "enum":
            mid[k] = v.values[0]
        else:
            lo = v.min if v.min is not None else 0.0
            hi = v.max if v.max is not None else lo + 100
            g = _grid(v, (lo + hi) / 2)
            mid[k] = int(g) if v.type == "integer" else g
    cands = {k: _candidates(vocab, rec, k, {**mid}, {}) for k in keys}
    vectors, seen = [], set()

    def add(origin, inputs):
        sig = tuple(sorted(inputs.items()))
        if sig in seen or len(vectors) >= limit:
            return
        seen.add(sig)
        vals, _, _ = vocab.resolve(inputs)
        try:
            expected = oracle(body["when"], vals)
        except KeyError:
            return
        vectors.append({"vector_id": f"{origin[:1]}{len(vectors):04d}", "origin": origin, "inputs": inputs,
            "expected": "SATISFIED" if expected else "NOT_SATISFIED"})

    # boundary: sweep one variable over its candidates while others sit at several baselines
    baselines = [dict(mid)]
    for _ in range(3):
        baselines.append({k: (rng.choice(cands[k]) if cands[k] else mid[k]) for k in keys})
    for base in baselines:
        for k in keys:
            for c in cands[k]:
                add("BOUNDARY", {**base, k: c})
    # combinatorial: random combinations of candidate values
    attempts = 0
    while len(vectors) < limit and attempts < limit * 6:
        attempts += 1
        add("COMBINATORIAL", {k: (rng.choice(cands[k]) if cands[k] else mid[k]) for k in keys})
    return vectors


def check_vectors(vocab: Vocabulary, body: dict, vectors: list[dict]) -> list[dict]:
    """Run the engine on each vector; return the mismatches (empty = engine agrees with the oracle)."""
    rec = {"body": body, "version": 1, "status": "PUBLISHED"}
    bad = []
    for v in vectors:
        r = evaluate(vocab, [rec], body["topic"], v["inputs"], as_of="2026-01-01", with_thresholds=False)
        if r["outcome"] != v["expected"]:
            bad.append({"vector_id": v["vector_id"], "inputs": v["inputs"], "expected": v["expected"], "actual": r["outcome"]})
    return bad
