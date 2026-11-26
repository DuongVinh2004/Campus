"""Deterministic three-valued (Kleene) evaluation of published policy rules. Pure: no I/O, no model."""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone

from campus247.domain.policy_rules.rule import Source, predicates
from campus247.domain.policy_rules.variables import Vocabulary

T, F, U = "T", "F", "U"
OUTCOME = {T: "SATISFIED", F: "NOT_SATISFIED", U: "UNDETERMINED"}
VN = timezone(timedelta(hours=7))
DISCLAIMER = "SIMULATION_NOT_DECISION"

UNIT_SYMBOL = {"percent": "%", "point10": "điểm", "point4": "điểm", "credit": "tín chỉ",
    "period": "tiết", "day": "ngày", "semester": "học kỳ", "vnd": "đồng"}
OP_TEXT = {"<": "nhỏ hơn", "<=": "không vượt quá", ">": "lớn hơn", ">=": "tối thiểu", "=": "bằng",
    "!=": "khác", "in": "thuộc", "not_in": "không thuộc", "between": "trong khoảng"}


def _not(v):
    return {T: F, F: T, U: U}[v]


def _all(values):
    if F in values:
        return F
    return U if U in values else T


def _any(values):
    if T in values:
        return T
    return U if U in values else F


def _fmt(v):
    if isinstance(v, bool):
        return "có" if v else "không"
    if isinstance(v, float):
        return ("%g" % round(v, 4)).replace(".", ",") if v != int(v) else str(int(v))
    return str(v)


def _compare(op, actual, expected, closed=(True, True)):
    if op == "between":
        lo, hi = expected
        ok_lo = actual >= lo if closed[0] else actual > lo
        ok_hi = actual <= hi if closed[1] else actual < hi
        return ok_lo and ok_hi
    if op == "in":
        return actual in expected
    if op == "not_in":
        return actual not in expected
    if op == "=":
        return actual == expected
    if op == "!=":
        return actual != expected
    return {"<": actual < expected, "<=": actual <= expected, ">": actual > expected,
        ">=": actual >= expected}[op]


def eval_node(vocab: Vocabulary, node: dict, values: dict, with_proof: bool = True):
    """-> (T|F|U, proof_dict|None, missing:list[str])."""
    if "pred" in node:
        p = node["pred"]
        var = vocab.get(p["var"])
        label = var.label if var else p["var"]
        sym = UNIT_SYMBOL.get(p.get("unit") or "", "")
        const = p["value"]
        const_txt = (f"{_fmt(const[0])}–{_fmt(const[1])}" if isinstance(const, list) and p["op"] == "between"
            else ", ".join(_fmt(c) for c in const) if isinstance(const, list) else _fmt(const))
        req = f"yêu cầu {OP_TEXT[p['op']]} {const_txt}{' ' + sym if sym else ''}".replace("  ", " ")
        src = Source.parse(node.get("source"))
        if p["var"] not in values:
            res, missing = U, [p["var"]]
            text = f"Chưa có thông tin: {label} ({req})"
        else:
            actual = values[p["var"]]
            ok = _compare(p["op"], actual, const, tuple(p.get("closed", (True, True))))
            res, missing = (T if ok else F), []
            text = f"{label}: {_fmt(actual)}{' ' + sym if sym else ''} — {req}"
        proof = {"id": node["id"], "kind": "pred", "value": res, "text": text, "var": p["var"],
            "source": src.public() if src else None} if with_proof else None
        return res, proof, missing
    if "not" in node:
        v, child, miss = eval_node(vocab, node["not"], values, with_proof)
        res = _not(v)
        proof = {"id": node["id"], "kind": "not", "value": res, "children": [child]} if with_proof else None
        return res, proof, miss
    key = "all" if "all" in node else "any"
    results = [eval_node(vocab, c, values, with_proof) for c in node[key]]
    vals = [r[0] for r in results]
    res = _all(vals) if key == "all" else _any(vals)
    missing: list[str] = []
    # only variables that can still change a non-decided outcome are worth asking for
    if res == U:
        for v, _, m in results:
            if v == U:
                missing += [x for x in m if x not in missing]
    proof = {"id": node["id"], "kind": key, "value": res, "children": [r[1] for r in results]} if with_proof else None
    return res, proof, missing


def _as_of(value) -> datetime:
    if value is None:
        return datetime.now(VN).replace(hour=0, minute=0, second=0, microsecond=0)
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=VN)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=VN)
    return datetime.fromisoformat(str(value)).replace(tzinfo=VN) if len(str(value)) <= 10 else datetime.fromisoformat(str(value))


def _cohort_ok(applies: dict, cohort):
    rng = applies.get("cohorts") or {}
    lo, hi = rng.get("from"), rng.get("to")
    if lo is None and hi is None:
        return True, False
    if cohort is None:
        return None, True
    try:
        c = int(cohort)
    except ValueError:
        return False, True
    return (lo is None or c >= int(lo)) and (hi is None or c <= int(hi)), True


def select_rules(records: list[dict], topic: str, as_of, cohort, program, audience="STUDENT"):
    """-> (selected_records, cohort_unknown). Records carry body/version/status/... See evaluate()."""
    at = _as_of(as_of)
    cand, cohort_unknown = [], False
    for rec in records:
        body = rec["body"]
        if body["topic"] != topic or rec.get("status") not in {"PUBLISHED", "STALE"}:
            continue
        ap = body.get("applies") or {}
        auds = ap.get("audiences") or []
        if audience not in auds and "*" not in auds:
            continue
        eff = ap.get("effective") or {}
        if eff.get("from") and at < datetime.fromisoformat(eff["from"]):
            continue
        if eff.get("to") and at >= datetime.fromisoformat(eff["to"]):
            continue
        progs = ap.get("programs") or ["*"]
        if "*" not in progs and (program is None or program not in progs):
            if program is None:
                pass  # unknown program cannot exclude; handled like cohort below
            else:
                continue
        ok, bounded = _cohort_ok(ap, cohort)
        if ok is False:
            continue
        if ok is None:
            cohort_unknown = True
        cand.append(rec)
    superseded = {s for rec in cand for s in rec["body"].get("supersedes") or ()}
    return [r for r in cand if r["body"]["rule_id"] not in superseded], cohort_unknown


def _ref(rec: dict) -> dict:
    return {"rule_id": rec["body"]["rule_id"], "version": rec.get("version"),
        "content_sha256": rec.get("content_sha256"), "release_id": rec.get("release_id"),
        "graph_version": rec.get("graph_version")}


def _decide_one(vocab, rec, values, pool, with_proof=True):
    """Main rule + exceptions -> dict(value, proof, missing, exceptions, reason)."""
    body = rec["body"]
    main, proof, missing = eval_node(vocab, body["when"], values, with_proof)
    exc_out, fired, maybe = [], [], []
    for ex in body.get("exceptions") or ():
        target = next((r for r in pool if r["body"]["rule_id"] == ex["rule_id"]
            and r.get("status") in {"PUBLISHED", "STALE"}), None)
        if target is None:
            ev, em = U, ["exception:" + ex["rule_id"]]
        else:
            ev, _, em = eval_node(vocab, target["body"]["when"], values, False)
        eff = ex["effect"]
        exc_out.append({"rule_id": ex["rule_id"], "value": ev, "effect": eff, "missing": em if ev == U else [],
            "source": (Source.parse(ex.get("source")) or Source("", "", "", "")).public()})
        if ev == T:
            fired.append(eff)
        elif ev == U:
            flips = (eff == "OVERRIDE_SATISFIED" and main != T) or (eff == "OVERRIDE_NOT_SATISFIED" and main != F) \
                or (eff == "DEFER_TO_STAFF" and main != U)
            if flips:
                maybe.append((eff, em))
    final, reason, refer = main, None, False
    if len(set(fired)) > 1:
        final, reason = U, "EXCEPTION_CONFLICT"
    elif fired:
        eff = fired[0]
        final = {"OVERRIDE_SATISFIED": T, "OVERRIDE_NOT_SATISFIED": F, "DEFER_TO_STAFF": U}[eff]
        if eff == "DEFER_TO_STAFF":
            reason, refer = "DEFER_TO_STAFF", True
    elif maybe and main != U:
        final, reason = U, "MISSING_INPUT"
        missing = [x for _, em in maybe for x in em if x.startswith("exception:") is False] or missing
        missing = list(dict.fromkeys(missing))
    if final == U and reason is None:
        reason = "MISSING_INPUT"
    return {"value": final, "proof": proof, "missing": missing if final == U else [], "exceptions": exc_out,
        "reason": reason, "main": main}


def _expand_missing(vocab: Vocabulary, missing: list[str], values: dict) -> list[str]:
    out: list[str] = []
    for m in missing:
        for b in (vocab.base_variables(m) if vocab.get(m) and vocab.expr(m) else (m,)):
            if b not in values and b not in out:
                out.append(b)
    return out


def evaluate(vocab: Vocabulary, records: list[dict], topic: str, inputs: dict, as_of=None,
        cohort=None, program=None, audience="STUDENT", with_thresholds=True) -> dict:
    """Inputs must already be validated by vocab.validate_inputs (the API does this)."""
    at = _as_of(as_of)
    base = {"topic": topic, "as_of": at.date().isoformat(), "disclaimer_code": DISCLAIMER,
        "inputs_used": {}, "derived": {}, "proof": None, "exceptions": [], "missing": [], "thresholds": [],
        "refer_to": None, "rule": None, "conclusion": None, "reason": None}

    def undetermined(reason, missing=(), **kw):
        out = {**base, "outcome": "UNDETERMINED", "reason": reason, "missing": list(missing), **kw}
        return out

    chosen, cohort_unknown = select_rules(records, topic, at, cohort, program, audience)
    if not chosen:
        return undetermined("NO_APPLICABLE_RULE")
    if any(r.get("status") == "STALE" for r in chosen):
        return undetermined("RULE_STALE", rule=_ref(chosen[0]))
    if cohort_unknown:
        return undetermined("MISSING_INPUT", ["student.cohort"], rule=_ref(chosen[0]))
    values, derived, errors = vocab.resolve(inputs)
    if any(e["code"] == "DERIVATION_INVALID" for e in errors):
        # a derived value that cannot be computed is UNDETERMINED only if it matters; keep it simple and honest
        pass
    decided = [(_decide_one(vocab, rec, values, records), rec) for rec in chosen]
    outcomes = {d["value"] for d, _ in decided}
    if len(decided) > 1 and len(outcomes) > 1:
        return undetermined("RULE_CONFLICT", rule=_ref(chosen[0]),
            conflict=[_ref(r) for _, r in decided])
    d, rec = decided[0]
    body = rec["body"]
    used = {k: v for k, v in values.items() if k in {p["pred"]["var"] for p in predicates(body["when"])}}
    res = {**base, "outcome": OUTCOME[d["value"]], "reason": d["reason"], "rule": _ref(rec),
        "conclusion": {"code": body["conclusion"]["code"], "label": body["conclusion"]["label"]},
        "inputs_used": used, "derived": {k: v for k, v in derived.items() if k in used},
        "proof": d["proof"], "exceptions": d["exceptions"], "missing": _expand_missing(vocab, d["missing"], values),
        "also_applied": [_ref(r) for _, r in decided[1:]]}
    if d["value"] == U or d["reason"] == "DEFER_TO_STAFF":
        res["refer_to"] = body.get("on_undetermined")
    if with_thresholds and d["value"] != U:
        res["thresholds"] = find_thresholds(vocab, records, rec, values, inputs)
    return res


def _grid(var, v):
    step = var.grid_step
    return round(round(v / step) * step, 6)


def _breakpoints(vocab: Vocabulary, rec: dict, key: str, values: dict, inputs: dict):
    """Solve a*x+b = c for each predicate involving `key` (directly or via a derived variable)."""
    pts = []
    for node in predicates(rec["body"]["when"]):
        p = node["pred"]
        if p["op"] in {"in", "not_in"} or not isinstance(p["value"], (int, float, list)):
            continue
        target = p["var"]
        consts = p["value"] if isinstance(p["value"], list) else [p["value"]]
        if key == target:
            pts += [float(c) for c in consts]
            continue
        expr = vocab.expr(target)
        if expr is None or key not in vocab.base_variables(target) or target in inputs:
            continue
        base = {dep: values.get(dep) for dep in expr.variables()}
        if any(v is None for k, v in base.items() if k != key):
            continue
        try:
            f = lambda x: expr.evaluate({**base, key: x})  # noqa: E731
            f0, f1, f2, f3 = f(0.0), f(1.0), f(2.0), f(3.0)
        except ArithmeticError:
            continue
        if None in (f0, f1, f2, f3) or abs((f2 - f1) - (f1 - f0)) > 1e-9 or abs((f3 - f2) - (f2 - f1)) > 1e-9:
            continue  # not linear in this variable: do not guess
        a = f1 - f0
        if abs(a) < 1e-12:
            continue
        pts += [(float(c) - f0) / a for c in consts]
    return pts


def find_thresholds(vocab: Vocabulary, records: list[dict], rec: dict, values: dict, inputs: dict) -> list[dict]:
    out: list[dict] = []
    keys: list[str] = []
    for node in predicates(rec["body"]["when"]):
        v0 = node["pred"]["var"]
        for b in ((v0,) if v0 in inputs else vocab.base_variables(v0)):
            var = vocab.get(b)
            if var and var.numeric and var.input in {"USER", "DERIVED"} and b not in keys                     and (vocab.expr(b) is None or b in inputs):
                keys.append(b)
    current = _decide_one(vocab, rec, values, records, with_proof=False)["value"]
    for key in keys:
        var = vocab.get(key)
        lo = var.min if var.min is not None else 0.0
        hi = var.max if var.max is not None else lo + 1000
        step = var.grid_step
        bps = _breakpoints(vocab, rec, key, values, inputs)
        tests = {_grid(var, lo), _grid(var, hi)}
        for b in bps:
            if not math.isfinite(b):
                continue
            for d in (-1, 0, 1):
                g = _grid(var, math.floor(b / step) * step + d * step)
                tests.add(g)
                g2 = _grid(var, math.ceil(b / step) * step + d * step)
                tests.add(g2)
        pts = sorted(t for t in tests if lo - 1e-9 <= t <= hi + 1e-9)
        if len(pts) < 2:
            continue
        outs = []
        for x in pts:
            vals2, _, _ = vocab.resolve({**{k: v for k, v in inputs.items() if k != key}, key: (int(x) if var.type == "integer" else x)})
            outs.append(_decide_one(vocab, rec, vals2, records, with_proof=False)["value"])
        for i in range(len(pts) - 1):
            a, b = outs[i], outs[i + 1]
            if a == b or U in (a, b):
                continue
            label = var.label
            sym = UNIT_SYMBOL.get(var.unit or "", "")
            if a == T:  # satisfied up to pts[i]
                out.append({"var": key, "flip_at": pts[i], "direction": "<=", "satisfied_when": "<=",
                    "text": f"{label} cần không vượt quá {_fmt(pts[i])}{' ' + sym if sym else ''} để đạt điều này"})
            else:
                out.append({"var": key, "flip_at": pts[i + 1], "direction": ">=", "satisfied_when": ">=",
                    "text": f"{label} cần tối thiểu {_fmt(pts[i + 1])}{' ' + sym if sym else ''} để đạt điều này"})
    # a threshold is only informative on the side of the current value
    return out


def what_if(vocab: Vocabulary, records: list[dict], topic: str, inputs: dict, vary: str, points: int = 11, **kw) -> dict:
    var = vocab.get(vary)
    if var is None or not var.numeric:
        raise ValueError("vary needs a numeric variable")
    lo = var.min if var.min is not None else 0
    hi = var.max if var.max is not None else lo + 100
    n = max(2, min(points, 41))
    xs = sorted({_grid(var, lo + (hi - lo) * i / (n - 1)) for i in range(n)})
    samples = []
    for x in xs:
        r = evaluate(vocab, records, topic, {**inputs, vary: (int(x) if var.type == "integer" else x)}, with_thresholds=False, **kw)
        samples.append({"value": x, "outcome": r["outcome"]})
    base = evaluate(vocab, records, topic, inputs, **kw)
    return {"vary": vary, "samples": samples, "thresholds": [t for t in base["thresholds"] if t["var"] == vary],
        "outcome": base["outcome"], "disclaimer_code": DISCLAIMER}
