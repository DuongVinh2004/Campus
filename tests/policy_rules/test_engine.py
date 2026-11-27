"""F2.1/F2.2: vocabulary, rule language, three-valued engine, thresholds, properties (seeded loops)."""
from __future__ import annotations

import copy
import random
import time
from pathlib import Path

import pytest

from campus247.domain.policy_rules.engine import _all, _any, _not, evaluate, what_if
from campus247.domain.policy_rules.rule import structural_issues, value_in_quote, verbatim_issues
from campus247.domain.policy_rules.variables import Expr, load_vocabulary

ROOT = Path(__file__).resolve().parents[2]
VOCAB = load_vocabulary(ROOT / "config" / "policy" / "variables.toml")
Q = "Sinh viên vắng quá 20% số tiết bị cấm thi."
SRC = {"unit_id": "u1", "version_id": "v1", "path": "Điều 1 > Khoản 1", "quote": Q}


def pred(nid, var, op, value, unit=None, source=SRC):
    unit = unit or VOCAB.get(var).unit
    return {"id": nid, "pred": {"var": var, "op": op, "value": value, "unit": unit}, "source": source}


def rule(rule_id="rule-1", when=None, exceptions=(), **kw):
    body = {"rule_id": rule_id, "topic": "EXAM_ELIGIBILITY", "version": 1,
        "conclusion": {"code": "ELIGIBLE", "label": "Được dự thi", "source": SRC},
        "applies": {"audiences": ["STUDENT"], "cohorts": {"from": None, "to": None}, "programs": ["*"],
            "effective": {"from": "2020-01-01T00:00:00+07:00", "to": None}},
        "when": when or {"id": "g", "all": [pred("c1", "attendance.absent_ratio", "<=", 20),
            pred("c2", "grade.process_score", ">=", 4)]},
        "exceptions": list(exceptions), "on_undetermined": {"refer_to": "ACADEMIC_SERVICES"}}
    body.update(kw)
    return {"body": body, "version": 1, "status": "PUBLISHED", "content_sha256": "x" * 64, "release_id": "rel", "graph_version": "g1"}


def run(records, inputs, **kw):
    clean, errors = VOCAB.validate_inputs(inputs)
    assert not errors, errors
    return evaluate(VOCAB, records, "EXAM_ELIGIBILITY", clean, as_of="2026-11-26", **kw)


def test_kleene_tables():
    for a in "TFU":
        assert _not(_not(a)) == a
    assert _all(["T", "U"]) == "U" and _all(["F", "U"]) == "F" and _all(["T", "T"]) == "T"
    assert _any(["T", "U"]) == "T" and _any(["F", "U"]) == "U" and _any(["F", "F"]) == "F"
    assert _all(["U", "U"]) == "U" == _any(["U", "U"]) == _not("U")


def test_expression_parser_and_derivation():
    e = Expr("a / b * 100 + (c - 1)")
    assert e.variables() == ("a", "b", "c")
    assert e.evaluate({"a": 9, "b": 36, "c": 3}) == 27.0
    assert e.evaluate({"a": 9, "b": 36}) is None
    with pytest.raises(ArithmeticError):
        e.evaluate({"a": 1, "b": 0, "c": 1})
    for bad in ("__import__('os')", "a ** 2", "a;b", "max(a)"):
        with pytest.raises(ValueError):
            Expr(bad)


def test_decision_with_proof_and_thresholds():
    r = run([rule()], {"attendance.absent_periods": 9, "course.total_periods": 36, "grade.process_score": 5.0})
    assert r["outcome"] == "NOT_SATISFIED"
    assert r["derived"]["attendance.absent_ratio"]["from"] == {"attendance.absent_periods": 9, "course.total_periods": 36}
    c1 = r["proof"]["children"][0]
    assert (c1["value"], r["proof"]["children"][1]["value"], r["proof"]["value"]) == ("F", "T", "F")
    assert c1["source"]["path"] == "Điều 1 > Khoản 1"
    th = [t for t in r["thresholds"] if t["var"] == "attendance.absent_periods"]
    assert th and th[0]["flip_at"] == 7 and th[0]["direction"] == "<="  # 7/36 = 19.4 % <= 20 %, 8/36 = 22.2 %
    assert r["disclaimer_code"] == "SIMULATION_NOT_DECISION"


def test_missing_variables_never_guessed():
    r = run([rule()], {"grade.process_score": 5.0})
    assert r["outcome"] == "UNDETERMINED" and r["reason"] == "MISSING_INPUT"
    assert set(r["missing"]) == {"attendance.absent_periods", "course.total_periods"}
    assert r["refer_to"] == {"refer_to": "ACADEMIC_SERVICES"}
    # a decided False beats an unknown (Kleene): bad score decides ALL without the attendance data
    r = run([rule()], {"grade.process_score": 1.0})
    assert r["outcome"] == "NOT_SATISFIED"


def test_no_rule_conflict_stale_and_cohort():
    assert run([], {"grade.process_score": 5})["reason"] == "NO_APPLICABLE_RULE"
    stale = rule()
    stale["status"] = "STALE"
    assert run([stale], {"grade.process_score": 5})["reason"] == "RULE_STALE"
    yes = rule("a", when={"id": "g", "all": [pred("c", "grade.process_score", ">=", 4)]})
    no = rule("b", when={"id": "g", "all": [pred("c", "grade.process_score", ">=", 9)]})
    assert run([yes, no], {"grade.process_score": 5})["reason"] == "RULE_CONFLICT"
    assert run([yes, copy.deepcopy(yes) | {"body": {**yes["body"], "rule_id": "a2"}}], {"grade.process_score": 5})["outcome"] == "SATISFIED"
    old = rule("old", applies={"audiences": ["STUDENT"], "cohorts": {"from": None, "to": "63"}, "programs": ["*"], "effective": {"from": None, "to": None}})
    new = rule("new", applies={"audiences": ["STUDENT"], "cohorts": {"from": "64", "to": None}, "programs": ["*"], "effective": {"from": None, "to": None}})
    r = run([old, new], {"grade.process_score": 5})
    assert r["outcome"] == "UNDETERMINED" and r["missing"] == ["student.cohort"]
    assert run([old, new], {"grade.process_score": 5}, cohort="66")["rule"]["rule_id"] == "new"
    assert run([old, new], {"grade.process_score": 5}, cohort="60")["rule"]["rule_id"] == "old"


def test_exceptions():
    main = rule("m", when={"id": "g", "all": [pred("c", "grade.process_score", ">=", 4)]},
        exceptions=[{"rule_id": "exc", "effect": "OVERRIDE_SATISFIED", "source": SRC}])
    exc = rule("exc", when={"id": "g", "all": [pred("e", "discipline.level", "=", "NONE")]})
    exc["body"]["topic"] = "EXCUSED"
    # main says F, exception unknown and could flip -> UNDETERMINED
    r = run([main, exc], {"grade.process_score": 1})
    assert r["outcome"] == "UNDETERMINED" and "discipline.level" in r["missing"]
    # exception true -> override to SATISFIED
    assert run([main, exc], {"grade.process_score": 1, "discipline.level": "NONE"})["outcome"] == "SATISFIED"
    # exception false -> stays F
    assert run([main, exc], {"grade.process_score": 1, "discipline.level": "WARNING"})["outcome"] == "NOT_SATISFIED"
    # main already T: an unknown exception cannot flip it
    assert run([main, exc], {"grade.process_score": 9})["outcome"] == "SATISFIED"
    main2 = rule("m2", exceptions=[{"rule_id": "exc", "effect": "OVERRIDE_SATISFIED", "source": SRC},
        {"rule_id": "exc", "effect": "OVERRIDE_NOT_SATISFIED", "source": SRC}], when=main["body"]["when"])
    assert run([main2, exc], {"grade.process_score": 5, "discipline.level": "NONE"})["reason"] == "EXCEPTION_CONFLICT"


def test_boundaries_exact_and_between_modes():
    when = {"id": "g", "all": [pred("c", "grade.process_score", ">=", 4)]}
    for score, exp in [(3.9, "NOT_SATISFIED"), (4.0, "SATISFIED"), (4.1, "SATISFIED")]:
        assert run([rule(when=when)], {"grade.process_score": score})["outcome"] == exp
    p = pred("c", "grade.process_score", "between", [4, 6])
    p["pred"]["closed"] = [False, True]
    got = [run([rule(when={"id": "g", "all": [p]})], {"grade.process_score": s})["outcome"] for s in (4.0, 4.1, 6.0, 6.1)]
    assert got == ["NOT_SATISFIED", "SATISFIED", "SATISFIED", "NOT_SATISFIED"]


def test_monotonicity_property_seeded():
    """For `x <= c`, raising x never turns NOT_SATISFIED into SATISFIED (and dually for >=)."""
    rng = random.Random(20261126)
    for op in ("<=", "<"):
        for _ in range(200):
            c = rng.randint(1, 9)
            when = {"id": "g", "all": [pred("c", "grade.process_score", op, c)]}
            xs = sorted(round(rng.uniform(0, 10), 1) for _ in range(6))
            outs = [run([rule(when=when)], {"grade.process_score": x}, with_thresholds=False)["outcome"] for x in xs]
            seen_bad = False
            for o in outs:
                if o == "NOT_SATISFIED":
                    seen_bad = True
                assert not (seen_bad and o == "SATISFIED")
    for _ in range(200):
        c = rng.randint(1, 9)
        when = {"id": "g", "all": [pred("c", "grade.process_score", ">=", c)]}
        xs = sorted(round(rng.uniform(0, 10), 1) for _ in range(6))
        outs = [run([rule(when=when)], {"grade.process_score": x}, with_thresholds=False)["outcome"] for x in xs]
        seen_good = False
        for o in outs:
            if o == "SATISFIED":
                seen_good = True
            assert not (seen_good and o == "NOT_SATISFIED")


def test_three_valued_property_missing_vars_are_listed_exactly():
    """With random subsets of inputs: UNDETERMINED always lists missing vars; decided results need none."""
    rng = random.Random(7)
    full = {"attendance.absent_periods": 4, "course.total_periods": 30, "grade.process_score": 5.5, "discipline.level": "NONE"}
    when = {"id": "g", "all": [pred("a", "attendance.absent_ratio", "<=", 20), pred("b", "grade.process_score", ">=", 4),
        {"id": "n", "not": pred("d", "discipline.level", "=", "SUSPENSION")}]}
    for _ in range(300):
        sub = {k: v for k, v in full.items() if rng.random() < 0.6}
        r = run([rule(when=when)], sub, with_thresholds=False)
        if r["outcome"] == "UNDETERMINED":
            assert r["missing"], sub
            assert all(m not in sub for m in r["missing"])
        else:
            assert r["missing"] == []
        if len(sub) == 4:
            assert r["outcome"] == "SATISFIED"


def test_input_validation_errors():
    _, errs = VOCAB.validate_inputs({"nope": 1, "grade.process_score": 11, "attendance.absent_periods": 2.5, "discipline.level": "X"})
    assert {(e["var"], e["code"]) for e in errs} == {("nope", "UNKNOWN_VARIABLE"), ("grade.process_score", "OUT_OF_RANGE"),
        ("attendance.absent_periods", "TYPE_MISMATCH"), ("discipline.level", "OUT_OF_RANGE")}


def test_division_by_zero_is_undetermined_not_crash():
    clean, _ = VOCAB.validate_inputs({"attendance.absent_periods": 3})
    vals, _, errs = VOCAB.resolve({**clean, "course.total_periods": 0})
    assert "attendance.absent_ratio" not in vals and errs[0]["code"] == "DERIVATION_INVALID"


def test_structural_and_verbatim_checks():
    good = rule()["body"]
    assert structural_issues(good, VOCAB) == []
    bad = copy.deepcopy(good)
    bad["when"]["all"][0]["pred"]["unit"] = "day"
    bad["when"]["all"][1]["pred"]["var"] = "nope.var"
    codes = {i["code"] for i in structural_issues(bad, VOCAB)}
    assert {"UNIT_MISMATCH", "UNKNOWN_VARIABLE"} <= codes
    deep = {"id": "n0", "pred": good["when"]["all"][0]["pred"], "source": SRC}
    for i in range(7):
        deep = {"id": f"d{i}", "not": deep}
    assert "TOO_DEEP" in {i["code"] for i in structural_issues({**good, "when": deep}, VOCAB)}
    texts = {"u1": "Điều 1. " + Q + " Hết."}
    ok = {**good, "when": {"id": "g", "all": [pred("c1", "attendance.absent_ratio", "<=", 20)]}}
    assert verbatim_issues(ok, texts.get) == []
    wrong_val = {**good, "when": {"id": "g", "all": [pred("c1", "attendance.absent_ratio", "<=", 30)]}}
    assert "VALUE_NOT_IN_QUOTE" in {i["code"] for i in verbatim_issues(wrong_val, texts.get)}
    texts["u1"] = "văn bản khác hoàn toàn"
    assert "QUOTE_NOT_VERBATIM" in {i["code"] for i in verbatim_issues(ok, texts.get)}


def test_value_forms_in_quote():
    assert value_in_quote(20, "không quá 20% số tiết")
    assert value_in_quote(20, "không quá 20 % số tiết")
    assert value_in_quote(20, "không quá hai mươi phần trăm")
    assert value_in_quote(4, "điểm từ 4,0 trở lên") is False or value_in_quote(4.0, "điểm từ 4,0 trở lên")
    assert value_in_quote(4.5, "điểm 4,5")
    assert not value_in_quote(20, "tối đa 120 tiết")
    assert not value_in_quote(2, "ngày 12/3")


def test_what_if_and_performance():
    clean, _ = VOCAB.validate_inputs({"attendance.absent_periods": 9, "course.total_periods": 36, "grade.process_score": 5})
    w = what_if(VOCAB, [rule()], "EXAM_ELIGIBILITY", clean, "attendance.absent_periods", as_of="2026-11-26")
    outs = [s["outcome"] for s in w["samples"]]
    assert outs[0] == "SATISFIED" and outs[-1] == "NOT_SATISFIED"
    recs = [rule()]
    times = []
    for _ in range(200):
        t = time.perf_counter()
        evaluate(VOCAB, recs, "EXAM_ELIGIBILITY", clean, as_of="2026-11-26")
        times.append((time.perf_counter() - t) * 1000)
    times.sort()
    assert times[int(len(times) * 0.95)] < 50, times[-5:]
