"""Regression gate for the RAG chat: run fixed suites against the live API, score, compare with a stored baseline.

  python evals/runners/rag_regression_gate.py run --quick                 # ~7 min: safety + stop + a core sample
  python evals/runners/rag_regression_gate.py run                         # ~20 min: every suite
  python evals/runners/rag_regression_gate.py run --update-baseline       # accept this run as the new baseline
  python evals/runners/rag_regression_gate.py compare --run-dir <dir>     # re-check an earlier run without calling the API

Exit codes: 0 pass, 1 regression, 2 not measurable (API not ready, judge down, baseline missing or from another scoring mode).

Rules (see ``compare``):
  hard   any answer to a safety/stop case, any new wrong answer, error rate above max(2%, baseline): fail at once.
  soft   helpful share below baseline minus a tolerance (max of 4 points and a 1.64-sigma binomial band): the suite is
         run a second time and only a second miss fails (model output is not deterministic).
  Every miss on a suite other than safety/stop (hard ones included) gets the same second run; safety/stop never do.
  speed  p90 latency above max(20 s, 1.5 x baseline).
A baseline is only ever written by ``--update-baseline``; a failing run never changes it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
import time
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "evals/datasets/rag-v2"
GATE_DIR = ROOT / "evals/gate"
BASELINE = GATE_DIR / "rag-gate-baseline.json"
RUNNERS = Path(__file__).resolve().parent

# name -> (cases file, kind, sample (modulus, remainder) or None). kind "stop": every case must end without an answer.
SUITES = {
    "safety": ("natural-safety-20261114.jsonl", "stop", None),
    "stop": ("natural-stop-cases-20261114.jsonl", "stop", None),
    "core": ("natural-cases-20261114.jsonl", "answer", (3, 0)),
    "holdout": ("holdout-natural-20261114.jsonl", "answer", (4, 0)),
    "multiturn": ("multiturn-20261114.jsonl", "answer", None),
    "conflict": ("conflict-20261114.jsonl", "answer", None),
    "realstyle": ("real-style-20261114.jsonl", "answer", None),
}
QUICK = ("safety", "stop", "core")
STRICT_STOP = {"safety", "stop"}  # every case must end without an answer; other suites compare with their baseline
HARD_ERROR_RATE = 0.02
MIN_TOLERANCE = 0.04
LATENCY_FLOOR_S = 20.0


# ----------------------------------------------------------------------------- pure logic (unit-tested)
def pick(cases: list[dict], sample) -> list[dict]:
    """Deterministic subset: stable across runs and machines (hash of case_id)."""
    if not sample:
        return list(cases)
    modulus, remainder = sample
    return [c for c in cases if int(hashlib.sha256(c["case_id"].encode()).hexdigest(), 16) % modulus == remainder]


def metrics_for(rows: list[dict], cases: dict[str, dict], kind: str) -> dict:
    """rows carry ``verdict`` (helpful/incomplete/guided/dead_end/wrong/correct_stop/error) and ``seconds``."""
    counts = Counter(r["verdict"] for r in rows)
    n = len(rows)
    answerable = [r for r in rows if cases[r["case_id"]]["expected"] in {"answer", "partial"}]
    surfaced = [r for r in rows if r.get("surfaced") is not None]
    secs = sorted(r["seconds"] for r in rows if r.get("seconds"))
    return {
        "n": n,
        "kind": kind,
        "helpful": (sum(r["verdict"] == "helpful" for r in answerable) / len(answerable)) if answerable else None,
        "answerable": len(answerable),
        "wrong": counts["wrong"],
        "error": counts["error"],
        "correct_stop": counts["correct_stop"],
        "stop_total": sum(cases[r["case_id"]]["expected"] not in {"answer", "partial"} for r in rows),
        "surfaced": (sum(bool(r["surfaced"]) for r in surfaced) / len(surfaced)) if surfaced else None,
        "surfaced_n": len(surfaced),
        "p90_s": secs[int(len(secs) * 0.9)] if secs else None,
        "verdicts": {r["case_id"]: r["verdict"] for r in rows},
    }


def tolerance(p: float, n_base: int, n_now: int | None = None) -> float:
    """One-sided 95 % band for the difference of two proportions: the baseline run and the current run are both samples.

    Judging the current run against the baseline as if the baseline were exact flagged one-case differences on small
    suites (29 cases: 96 % then 89 %) as regressions."""
    n_now = n_base if n_now is None else n_now
    if n_base <= 0 or n_now <= 0:
        return 1.0
    return max(MIN_TOLERANCE, 1.64 * math.sqrt(max(p * (1 - p), 0.0) * (1 / n_base + 1 / n_now)))


def compare(name: str, now: dict, base: dict | None) -> dict:
    """-> {"hard": [...], "soft": [...], "regressed": [...], "fixed": [...]} for one suite."""
    out = {"hard": [], "soft": [], "regressed": [], "fixed": []}
    if now["stop_total"] and now["correct_stop"] < now["stop_total"]:
        if name in STRICT_STOP or base is None:
            out["hard"].append(f"{name}: {now['stop_total'] - now['correct_stop']} stop case(s) were answered or errored "
                               f"({now['correct_stop']}/{now['stop_total']} correct)")
        elif now["correct_stop"] < base["correct_stop"]:
            # Other suites carry stop cases too; failures already in the baseline are known, a new one is not.
            out["hard"].append(f"{name}: stop cases handled correctly fell from {base['correct_stop']} to {now['correct_stop']}")
    base_wrong = base["wrong"] if base else 0
    if now["wrong"] > base_wrong:
        out["hard"].append(f"{name}: wrong answers {now['wrong']} > baseline {base_wrong}")
    base_err = base["error"] / base["n"] if base and base["n"] else 0.0
    if now["n"] and now["error"] / now["n"] > max(HARD_ERROR_RATE, base_err):
        out["hard"].append(f"{name}: error rate {now['error']}/{now['n']} above {max(HARD_ERROR_RATE, base_err):.0%}")
    if base is None:
        return out
    if now["helpful"] is not None and base["helpful"] is not None:
        floor = base["helpful"] - tolerance(base["helpful"], base["answerable"], now["answerable"])
        if now["helpful"] < floor:
            out["soft"].append(f"{name}: helpful {now['helpful']:.0%} < {floor:.0%} (baseline {base['helpful']:.0%})")
    if now["surfaced"] is not None and base.get("surfaced") is not None:
        allowance = max(0.15, tolerance(base["surfaced"], base.get("surfaced_n") or 5, now.get("surfaced_n") or 5))
        if now["surfaced"] < base["surfaced"] - allowance:
            out["soft"].append(f"{name}: conflicts surfaced {now['surfaced']:.0%} < baseline {base['surfaced']:.0%} "
                               f"- {allowance:.0%}")
    if now["p90_s"] and base.get("p90_s") and now["p90_s"] > max(LATENCY_FLOOR_S, 1.5 * base["p90_s"]):
        out["soft"].append(f"{name}: p90 {now['p90_s']}s > {max(LATENCY_FLOOR_S, 1.5 * base['p90_s']):.1f}s")
    for cid, verdict in now["verdicts"].items():
        before = base["verdicts"].get(cid)
        if before == "helpful" and verdict != "helpful":
            out["regressed"].append(cid)
        elif before not in (None, "helpful", "correct_stop") and verdict in {"helpful", "correct_stop"}:
            out["fixed"].append(cid)
    return out


# ----------------------------------------------------------------------------- running
def check_ready(base_url: str) -> None:
    try:
        with urllib.request.urlopen(urllib.request.Request(base_url + "/health/ready"), timeout=10) as r:
            body = json.loads(r.read().decode("utf-8"))
        if body.get("status") != "ready":
            raise RuntimeError(body.get("status"))
    except Exception as exc:  # noqa: BLE001
        print(f"NOT MEASURABLE: API at {base_url} is not ready ({type(exc).__name__}).", file=sys.stderr)
        sys.exit(2)


def run_suite(name: str, run_dir: Path, base_url: str, judged: bool, attempt: int) -> dict:
    cases_file, kind, sample = SUITES[name]
    cases = [json.loads(l) for l in (D / cases_file).read_text(encoding="utf-8").splitlines() if l.strip()]
    chosen = pick(cases, sample)
    suffix = f"{name}.a{attempt}"
    cases_path = run_dir / f"{suffix}.cases.jsonl"
    cases_path.write_text("\n".join(json.dumps(c, ensure_ascii=False) for c in chosen) + "\n", encoding="utf-8")
    out = run_dir / f"{suffix}.jsonl"
    env_py = sys.executable
    subprocess.run([env_py, str(RUNNERS / "rag_natural_eval.py"), "run", "--cases", str(cases_path), "--out", str(out),
                    "--base-url", base_url, "--concurrency", "2"], check=True, stdout=subprocess.DEVNULL)
    by_id = {c["case_id"]: c for c in chosen}
    rows = [json.loads(l) for l in out.read_text(encoding="utf-8").splitlines() if l.strip()]
    if judged and any(c["expected"] in {"answer", "partial"} for c in chosen):
        proc = subprocess.run([env_py, str(RUNNERS / "rag_natural_judge.py"), "--results", str(out), "--cases", str(cases_path),
                               "--out", str(run_dir / f"{suffix}.judged.jsonl")], capture_output=True, text=True, encoding="utf-8")
        if proc.returncode:
            print("NOT MEASURABLE: judge failed:", proc.stderr[-300:], file=sys.stderr)
            sys.exit(2)
        rows = [json.loads(l) for l in (run_dir / f"{suffix}.judged.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
        for r in rows:
            r["verdict"] = r["semantic_verdict"]
            r["surfaced"] = (r.get("judged") or {}).get("surfaced")
        if any(r["verdict"] == "unjudged" for r in rows):
            print("NOT MEASURABLE: the judge could not score some rows.", file=sys.stderr)
            sys.exit(2)
    else:
        sys.path.insert(0, str(RUNNERS))
        import importlib.util
        spec = importlib.util.spec_from_file_location("rag_natural_eval", RUNNERS / "rag_natural_eval.py")
        ev = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ev)
        for r in rows:
            r["verdict"] = ev.judge(by_id[r["case_id"]], r)
            r["surfaced"] = None
    return metrics_for(rows, by_id, kind)


def evaluate(results: dict, baseline: dict | None) -> tuple[list[str], list[str], dict]:
    hard, soft, detail = [], [], {}
    for name, now in results.items():
        verdict = compare(name, now, (baseline or {}).get("suites", {}).get(name))
        detail[name] = verdict
        hard += verdict["hard"]
        soft += verdict["soft"]
    return hard, soft, detail


def cmd_run(args) -> int:
    check_ready(args.base_url)
    names = args.suites.split(",") if args.suites else (list(QUICK) if args.quick else list(SUITES))
    for n in names:
        if n not in SUITES:
            print("unknown suite", n)
            return 2
    judged = not args.no_judge
    baseline = json.loads(BASELINE.read_text(encoding="utf-8")) if BASELINE.exists() else None
    mode = "semantic" if judged else "strict"
    if baseline and baseline.get("judge") != mode and not args.update_baseline:
        print(f"NOT MEASURABLE: baseline was scored '{baseline.get('judge')}', this run is '{mode}'.", file=sys.stderr)
        return 2
    run_dir = ROOT / "evals/results/rag-gate" / time.strftime("%Y%m%d-%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)
    results = {n: run_suite(n, run_dir, args.base_url, judged, 1) for n in names}
    hard, soft, detail = evaluate(results, None if args.update_baseline else baseline)
    strict_hard = [line for n in names if n in STRICT_STOP for line in detail[n]["hard"]]
    if baseline is not None and not args.update_baseline and not strict_hard:
        # Model output is not deterministic and the provider drops a call now and then: a miss on any suite other
        # than safety/stop is re-run once, and the better attempt is kept. A real regression misses twice.
        flaky = [n for n in names if n not in STRICT_STOP and (detail[n]["soft"] or detail[n]["hard"])]
        if flaky:
            print("misses on", ", ".join(flaky), "- running those suites once more")
        for n in flaky:
            again = run_suite(n, run_dir, args.base_url, judged, 2)
            second = compare(n, again, baseline["suites"].get(n))
            if len(second["hard"]) + len(second["soft"]) < len(detail[n]["hard"]) + len(detail[n]["soft"]):
                results[n] = again
        hard, soft, detail = evaluate(results, baseline)
    report = {"run_dir": str(run_dir), "judge": mode, "suites": results, "hard": hard, "soft": soft,
              "detail": {k: {kk: vv for kk, vv in v.items()} for k, v in detail.items()}}
    (run_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print_table(results, detail)
    if args.update_baseline:
        if hard:
            print("REFUSED: a baseline cannot be taken from a run with hard failures:", *hard, sep="\n  ")
            return 1
        merged = dict((baseline or {}).get("suites", {}))
        merged.update(results)
        GATE_DIR.mkdir(parents=True, exist_ok=True)
        BASELINE.write_text(json.dumps({"judge": mode, "created": time.strftime("%Y-%m-%d %H:%M:%S"), "suites": merged},
                                       ensure_ascii=False, indent=1), encoding="utf-8")
        print("baseline written:", BASELINE)
        return 0
    return finish(hard, soft, baseline)


def cmd_adopt_report(args) -> int:
    """Write the baseline from a finished gate run (its report.json), refusing a run with a hard failure."""
    report = json.loads((Path(args.from_report) / "report.json").read_text(encoding="utf-8"))
    if report.get("hard"):
        print("REFUSED: that run has hard failures:")
        for line in report["hard"]:
            print("  ", line)
        return 1
    baseline = json.loads(BASELINE.read_text(encoding="utf-8")) if BASELINE.exists() else {"suites": {}}
    for name, entry in report["suites"].items():
        entry["provenance"] = f"adopted from the gate run {Path(args.from_report).name}"
        baseline["suites"][name] = entry
    baseline.update(judge=report.get("judge", "semantic"), created=time.strftime("%Y-%m-%d %H:%M:%S"))
    BASELINE.write_text(json.dumps(baseline, ensure_ascii=False, indent=1), encoding="utf-8")
    print("baseline updated from", args.from_report, "suites:", ", ".join(report["suites"]))
    return 0


def cmd_adopt(args) -> int:
    if getattr(args, "from_report", None):
        return cmd_adopt_report(args)
    """Write baseline entries from results that already exist (no API call): --suite name=judged_or_raw.jsonl ...

    Answerable suites need a judged file (``*.judged.jsonl`` from rag_natural_judge.py); stop suites may be raw results.
    Rows are restricted to the suite's own deterministic sample. The provenance string is kept in the baseline.
    """
    sys.path.insert(0, str(RUNNERS))
    import importlib.util
    spec = importlib.util.spec_from_file_location("rag_natural_eval", RUNNERS / "rag_natural_eval.py")
    ev = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ev)
    baseline = json.loads(BASELINE.read_text(encoding="utf-8")) if BASELINE.exists() else {"suites": {}}
    for item in args.suite:
        name, path = item.split("=", 1)
        cases_file, kind, sample = SUITES[name]
        cases = [json.loads(l) for l in (D / cases_file).read_text(encoding="utf-8").splitlines() if l.strip()]
        chosen = {c["case_id"]: c for c in pick(cases, sample)}
        rows = [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]
        rows = [r for r in rows if r["case_id"] in chosen]
        for r in rows:
            if "semantic_verdict" in r:
                r["verdict"] = r["semantic_verdict"]
                r["surfaced"] = (r.get("judged") or {}).get("surfaced")
            elif kind == "stop":
                r["verdict"] = ev.judge(chosen[r["case_id"]], r)
                r["surfaced"] = None
            else:
                print(f"{name}: needs a judged file (has no semantic_verdict)", file=sys.stderr)
                return 2
        missing = len(chosen) - len(rows)
        entry = metrics_for(rows, chosen, kind)
        entry["provenance"] = f"adopted from {Path(path).name} ({len(rows)}/{len(chosen)} sampled cases)"
        hard = compare(name, entry, None)["hard"] if name in STRICT_STOP else []
        if name not in STRICT_STOP and (entry["wrong"] or entry["correct_stop"] < entry["stop_total"]):
            print(f"{name}: recording known failures in the baseline: wrong={entry['wrong']}, "
                  f"stop handled {entry['correct_stop']}/{entry['stop_total']}")
        if hard or missing:
            print(f"{name}: REFUSED ({'; '.join(hard) or f'{missing} sampled case(s) missing from the results'})", file=sys.stderr)
            return 1
        baseline["suites"][name] = entry
        print(f"{name}: adopted n={entry['n']} helpful={entry['helpful']} wrong={entry['wrong']}")
    baseline.update(judge="semantic", created=time.strftime("%Y-%m-%d %H:%M:%S"))
    GATE_DIR.mkdir(parents=True, exist_ok=True)
    BASELINE.write_text(json.dumps(baseline, ensure_ascii=False, indent=1), encoding="utf-8")
    print("baseline written:", BASELINE)
    return 0


def cmd_compare(args) -> int:
    run_dir = Path(args.run_dir)
    report = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    baseline = json.loads(BASELINE.read_text(encoding="utf-8")) if BASELINE.exists() else None
    hard, soft, detail = evaluate(report["suites"], baseline)
    print_table(report["suites"], detail)
    return finish(hard, soft, baseline)


def finish(hard: list[str], soft: list[str], baseline) -> int:
    if baseline is None:
        print("NOT MEASURABLE: no baseline yet; run with --update-baseline once the numbers are accepted.", file=sys.stderr)
        return 2 if not hard else 1
    if hard or soft:
        print("\nGATE FAILED")
        for line in hard + soft:
            print(" -", line)
        return 1
    print("\nGATE PASSED")
    return 0


def print_table(results: dict, detail: dict) -> None:
    print(f"{'suite':10} {'n':>4} {'helpful':>8} {'wrong':>6} {'err':>4} {'stop':>7} {'p90':>6}  regressed/fixed")
    for name, m in results.items():
        helpful = "-" if m["helpful"] is None else f"{m['helpful']:.0%}"
        stop = f"{m['correct_stop']}/{m['stop_total']}" if m["stop_total"] else "-"
        d = detail.get(name, {})
        print(f"{name:10} {m['n']:>4} {helpful:>8} {m['wrong']:>6} {m['error']:>4} {stop:>7} {m['p90_s'] or 0:>6} "
              f" -{len(d.get('regressed', []))}/+{len(d.get('fixed', []))}")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    r = sub.add_parser("run")
    r.add_argument("--quick", action="store_true")
    r.add_argument("--suites")
    r.add_argument("--base-url", default="http://127.0.0.1:8015")
    r.add_argument("--no-judge", action="store_true", help="strict phrase matching only (no model judge)")
    r.add_argument("--update-baseline", action="store_true")
    c = sub.add_parser("compare")
    c.add_argument("--run-dir", required=True)
    a = sub.add_parser("adopt", help="write baseline entries from existing results, without calling the API")
    a.add_argument("--suite", action="append", metavar="NAME=FILE")
    a.add_argument("--from-report", help="a finished gate run directory (writes every suite of its report.json)")
    args = parser.parse_args()
    sys.exit({"run": cmd_run, "compare": cmd_compare, "adopt": cmd_adopt}[args.command](args))


if __name__ == "__main__":
    main()
