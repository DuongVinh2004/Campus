"""Re-ask only the questions a gate run did not answer well, with the code now running, and compare verdict by verdict.

  python evals/runners/rag_retry_misses.py --run-dir evals/results/rag-gate/<run> [--suites core,holdout,realstyle] [--out DIR]

Uses the gate's own runner and judge (real provider for answers, the same judge for scoring), so a "fixed" here means the same
thing as in the gate. It is a quick check of a change on the failures it targets; the full gate run is what decides.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNNERS = Path(__file__).resolve().parent
GOOD = {"helpful", "correct_stop"}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--suites", default="core,holdout,realstyle")
    parser.add_argument("--out", default=None)
    parser.add_argument("--base-url", default="http://127.0.0.1:8015")
    args = parser.parse_args()
    run = Path(args.run_dir)
    out = Path(args.out) if args.out else run / "retry-misses"
    out.mkdir(parents=True, exist_ok=True)
    summary = {}
    for suite in args.suites.split(","):
        judged = run / f"{suite}.a1.judged.jsonl"
        if not judged.is_file():
            continue
        before = {r["case_id"]: r for r in map(json.loads, judged.read_text(encoding="utf-8").splitlines()) if r.get("semantic_verdict") not in GOOD}
        cases = [c for c in map(json.loads, (run / f"{suite}.a1.cases.jsonl").read_text(encoding="utf-8").splitlines()) if c["case_id"] in before]
        if not cases:
            continue
        cases_path, results, rejudged = out / f"{suite}.cases.jsonl", out / f"{suite}.jsonl", out / f"{suite}.judged.jsonl"
        cases_path.write_text("\n".join(json.dumps(c, ensure_ascii=False) for c in cases) + "\n", encoding="utf-8")
        subprocess.run([sys.executable, str(RUNNERS / "rag_natural_eval.py"), "run", "--cases", str(cases_path), "--out", str(results),
                        "--base-url", args.base_url, "--concurrency", "2"], check=True, stdout=subprocess.DEVNULL)
        subprocess.run([sys.executable, str(RUNNERS / "rag_natural_judge.py"), "--results", str(results), "--cases", str(cases_path),
                        "--out", str(rejudged)], check=True, stdout=subprocess.DEVNULL)
        after = {r["case_id"]: r for r in map(json.loads, rejudged.read_text(encoding="utf-8").splitlines())}
        moves = Counter()
        for cid, row in before.items():
            now = after.get(cid, {}).get("semantic_verdict", "missing")
            moves[(row["semantic_verdict"], now)] += 1
            print(f"{suite:9} {cid:34} {row['semantic_verdict']:12} -> {now}")
        fixed = sum(n for (b, a), n in moves.items() if a in GOOD)
        worse = sum(n for (b, a), n in moves.items() if a in {"wrong", "error"} and b not in {"wrong", "error"})
        summary[suite] = {"misses": len(before), "now_good": fixed, "now_worse": worse}
    print(json.dumps(summary, ensure_ascii=False))
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
