"""Compare result files of the same cases: coverage on answerable cases, refusal accuracy on the rest.

    .venv/Scripts/python.exe -B evals/runners/rag_v2_gate_compare.py --cases <jsonl> name=<results.json> ...
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from evals.runners.rag_v2_eval import fact_matches  # noqa: E402

ANSWERED = {"answer", "partial"}


def summarize(cases, records):
    answerable, other = Counter(), Counter()
    by_type = {}
    seconds = []
    for row in records:
        case = cases[row["case_id"]]
        seconds.append(row["seconds"])
        outcome = row["outcome_class"]
        if case["expected"] == "answer":
            if outcome == "error":
                answerable["error"] += 1
            elif outcome in ANSWERED:
                full = all(fact_matches(f, row.get("answer_text", "")) for f in case["required_facts"])
                answerable["full" if full else "thin"] += 1
            else:
                answerable["refused_or_clarified"] += 1
        else:
            good = outcome in {"refuse", "clarify"}
            other["correct" if good else "error" if outcome == "error" else "answered"] += 1
            by_type.setdefault(case.get("case_type", case["family"]), Counter())["ok" if good else "bad"] += 1
    return answerable, other, by_type, statistics.median(seconds)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", required=True)
    parser.add_argument("runs", nargs="+")
    args = parser.parse_args()
    cases = {}
    for line in Path(args.cases).read_text(encoding="utf-8").splitlines():
        case = json.loads(line)
        cases[case["case_id"]] = case
    for item in args.runs:
        name, path = item.split("=", 1)
        records = [r for r in json.loads(Path(path).read_text(encoding="utf-8"))["records"] if r["case_id"] in cases]
        answerable, other, by_type, median = summarize(cases, records)
        print(f"{name}: answerable {sum(answerable.values())} {dict(answerable)} | no-answer {sum(other.values())} "
              f"{dict(other)} | median {median:.1f}s")
        print("   by type:", {k: dict(v) for k, v in sorted(by_type.items())})


if __name__ == "__main__":
    main()
