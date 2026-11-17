"""Summarize the paid-provider calls made after a ledger ordinal: calls per route, tokens and prompt-cache share.

  python evals/runners/ledger_window.py --mark                  # print the current last ordinal (call before a run)
  python evals/runners/ledger_window.py --after 110268 [--out file.json] [--turns 120]

Reads only the retained ledger records (no prompts, no answers). cached_input_tokens exists for calls made after lever L4's
accounting change; older records count as 0.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

LEDGER = Path(__file__).resolve().parents[2] / "infra/local/public-rag-20261013"
NAME = re.compile(r"provider-(\d+)-(reservation|result)\.json$")


def last_ordinal() -> int:
    best = 0
    for path in LEDGER.glob("provider-*-result.json"):
        match = NAME.search(path.name)
        if match:
            best = max(best, int(match.group(1)))
    return best


def summarize(after: int, turns: int | None) -> dict:
    routes: Counter = Counter()
    tokens = defaultdict(lambda: [0, 0, 0])      # route -> input, cached, output
    failed = 0
    for path in LEDGER.glob("provider-*.json"):
        match = NAME.search(path.name)
        if not match or int(match.group(1)) <= after:
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        route = data.get("route")
        if match.group(2) == "reservation":
            routes[route] += 1
            continue
        if data.get("exit_code") != 0:
            failed += 1
            continue
        key = data.get("route") or "?"
        row = tokens[key]
        row[0] += data.get("input_tokens", 0)
        row[1] += data.get("cached_input_tokens", 0)
        row[2] += data.get("output_tokens", 0)
    calls = sum(routes.values())
    total_in = sum(v[0] for v in tokens.values())
    total_cached = sum(v[1] for v in tokens.values())
    out = {"after_ordinal": after, "calls": calls, "failed_calls": failed, "calls_by_route": dict(routes.most_common()),
           "input_tokens": total_in, "cached_input_tokens": total_cached,
           "cached_share": round(total_cached / total_in, 4) if total_in else None,
           "tokens_by_route": {k: {"input": v[0], "cached": v[1], "output": v[2]} for k, v in tokens.items()}}
    if turns:
        out["turns"] = turns
        out["calls_per_turn"] = round(calls / turns, 3)
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mark", action="store_true")
    parser.add_argument("--after", type=int)
    parser.add_argument("--turns", type=int)
    parser.add_argument("--out")
    args = parser.parse_args()
    if args.mark:
        print(last_ordinal())
        return 0
    if args.after is None:
        parser.error("--after or --mark required")
    result = summarize(args.after, args.turns)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
