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
from evals.runners import rag_v2_scoring as scoring  # noqa: E402

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
            if scoring.infra_error(row):
                answerable["error"] += 1
            elif outcome in ANSWERED:
                full = scoring.classify(case, row) == "full"
                answerable["full" if full else "thin"] += 1
            else:
                answerable["refused_or_clarified"] += 1
        else:
            good = scoring.classify(case, row) == "correctly_declined"
            other["correct" if good else "error" if scoring.infra_error(row) else "answered"] += 1
            by_type.setdefault(case.get("case_type", case.get("family", "unknown")), Counter())["ok" if good else "bad"] += 1
    return answerable, other, by_type, statistics.median(seconds) if seconds else 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", required=True)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("runs", nargs="+")
    args = parser.parse_args()
    cases = {}
    for line in Path(args.cases).read_text(encoding="utf-8").splitlines():
        case = json.loads(line)
        cases[case["case_id"]] = case
    for item in args.runs:
        name, path = item.split("=", 1)
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        records = data["records"]
        issues = scoring.record_issues(records, list(cases.values()))
        issues += scoring.campaign_issues([data.get("metadata", {})], records, list(cases.values()))
        if issues and args.strict:
            parser.exit(2, "Invalid campaign coverage/provenance\n")
        if issues:
            print("WARNING: " + ", ".join(issues))
        answerable, other, by_type, median = summarize(cases, records)
        print(f"{name}: answerable {sum(answerable.values())} {dict(answerable)} | no-answer {sum(other.values())} "
              f"{dict(other)} | median {median:.1f}s")
        print("   by type:", {k: dict(v) for k, v in sorted(by_type.items())})


if __name__ == "__main__":
    main()
