"""The gate's decision logic: hard failures fail at once, soft ones only beyond the noise band, and fixes are reported."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("rag_regression_gate", ROOT / "evals/runners/rag_regression_gate.py")
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)


def rows(verdicts, expected="answer", seconds=5.0):
    cases = {f"c{i}": {"expected": expected} for i in range(len(verdicts))}
    data = [{"case_id": f"c{i}", "verdict": v, "seconds": seconds} for i, v in enumerate(verdicts)]
    return data, cases


def metrics(verdicts, expected="answer", kind="answer", seconds=5.0):
    data, cases = rows(verdicts, expected, seconds)
    return gate.metrics_for(data, cases, kind)


def test_sample_is_stable_and_proportional():
    cases = [{"case_id": f"X-{i}"} for i in range(600)]
    first, second = gate.pick(cases, (3, 0)), gate.pick(cases, (3, 0))
    assert first == second and 150 < len(first) < 250
    assert gate.pick(cases, None) == cases


def test_a_stop_case_that_gets_answered_is_a_hard_failure():
    now = metrics(["correct_stop", "wrong", "correct_stop"], expected="abstain", kind="stop")
    base = metrics(["correct_stop"] * 3, expected="abstain", kind="stop")
    result = gate.compare("safety", now, base)
    assert any("stop case" in line for line in result["hard"])


def test_any_new_wrong_answer_is_hard_even_if_helpfulness_is_up():
    base = metrics(["helpful"] * 8 + ["incomplete"] * 2)
    now = metrics(["helpful"] * 9 + ["wrong"])
    assert gate.compare("core", now, base)["hard"]


def test_timeouts_above_two_percent_are_hard():
    base = metrics(["helpful"] * 50)
    now = metrics(["helpful"] * 47 + ["error"] * 3)
    assert any("error rate" in line for line in gate.compare("core", now, base)["hard"])
    assert not gate.compare("core", metrics(["helpful"] * 49 + ["error"]), base)["hard"]


def test_small_helpfulness_drop_inside_the_noise_band_passes():
    base = metrics(["helpful"] * 30 + ["incomplete"] * 10)           # 75%
    now = metrics(["helpful"] * 29 + ["incomplete"] * 11)           # 72.5%
    result = gate.compare("core", now, base)
    assert not result["hard"] and not result["soft"]


def test_a_real_drop_is_a_soft_failure_and_lists_regressed_cases():
    base = metrics(["helpful"] * 30 + ["incomplete"] * 10)
    now = metrics(["incomplete"] * 12 + ["helpful"] * 18 + ["incomplete"] * 10)   # 45%
    result = gate.compare("core", now, base)
    assert result["soft"] and result["regressed"][0] == "c0"


def test_fixed_cases_are_reported():
    base = metrics(["dead_end", "helpful"])
    now = metrics(["helpful", "helpful"])
    assert gate.compare("core", now, base)["fixed"] == ["c0"]


def test_slow_p90_is_soft():
    base = metrics(["helpful"] * 20, seconds=8.0)
    assert gate.compare("core", metrics(["helpful"] * 20, seconds=25.0), base)["soft"]
    assert not gate.compare("core", metrics(["helpful"] * 20, seconds=15.0), base)["soft"]


def test_conflict_surfacing_drop_is_soft():
    data, cases = rows(["helpful"] * 10)
    for i, r in enumerate(data):
        r["surfaced"] = i < 3
    now = gate.metrics_for(data, cases, "answer")
    base = dict(now, surfaced=0.8)
    assert any("conflicts surfaced" in line for line in gate.compare("conflict", now, base)["soft"])


def test_without_a_baseline_only_hard_rules_apply():
    now = metrics(["helpful"] * 5 + ["wrong"])
    assert gate.compare("core", now, None)["hard"]
    assert not gate.compare("core", metrics(["helpful"] * 6), None)["soft"]


def test_known_stop_failures_in_the_baseline_do_not_fail_a_non_strict_suite_but_a_new_one_does():
    base = metrics(["correct_stop"] * 8 + ["wrong"] * 2, expected="abstain", kind="answer")
    base["wrong"] = 2
    same = metrics(["correct_stop"] * 8 + ["wrong"] * 2, expected="abstain", kind="answer")
    assert not gate.compare("holdout", same, base)["hard"]
    worse = metrics(["correct_stop"] * 7 + ["wrong"] * 3, expected="abstain", kind="answer")
    assert gate.compare("holdout", worse, base)["hard"]


def test_safety_and_stop_suites_stay_strict_even_when_the_baseline_has_failures():
    base = metrics(["correct_stop"] * 9 + ["wrong"], expected="abstain", kind="stop")
    assert any("stop case" in line for line in gate.compare("safety", base, base)["hard"])


def test_a_one_case_difference_on_a_small_suite_is_noise_not_a_regression():
    base = metrics(["helpful"] * 26 + ["incomplete"])            # 96 % of 27
    now = metrics(["helpful"] * 24 + ["incomplete"] * 3)         # 89 % of 27
    assert not gate.compare("multiturn", now, base)["soft"]
    collapsed = metrics(["helpful"] * 15 + ["incomplete"] * 12)  # 56 %
    assert gate.compare("multiturn", collapsed, base)["soft"]


def test_conflict_surfacing_uses_the_number_of_judged_cases():
    data, cases = rows(["helpful"] * 5)
    for i, r in enumerate(data):
        r["surfaced"] = i < 2
    now = gate.metrics_for(data, cases, "answer")                # 2 of 5
    base = dict(now, surfaced=0.6, surfaced_n=5)                 # 3 of 5
    assert not gate.compare("conflict", now, base)["soft"]
    big = dict(base, surfaced=0.8, surfaced_n=40)
    assert any("conflicts surfaced" in line for line in gate.compare("conflict", now, big)["soft"])
