#!/usr/bin/env python3
"""Run many worker jobs in parallel and print one compact table.

  python -I fanout.py jobs.json [--parallel 6]

jobs.json:
  {"defaults": {"mode": "text", "context": ["README.md"]},
   "jobs": [{"id": "a", "brief_text": "...", "context": ["x.tsx"], "mode": "files", "allow": ["x.tsx"]}, ...]}

Job keys = worker.py options (brief | brief_text, context, mode, allow, model, verify_quotes, words, ...).
Files-mode jobs that write the same path are flagged as conflicts; nothing is applied here.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import load_config  # noqa: E402
from worker import run_job  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("jobs")
    ap.add_argument("--parallel", type=int, default=6)
    ap.add_argument("--show-output", action="store_true", help="also print text/json outputs (costs supervisor context)")
    a = ap.parse_args()
    spec = json.loads(Path(a.jobs).read_text(encoding="utf-8"))
    defaults = spec.get("defaults", {})
    jobs = [{**defaults, **j} for j in spec["jobs"]]
    cfg = load_config()
    results = []
    with ThreadPoolExecutor(max_workers=max(1, a.parallel)) as pool:
        futs = {pool.submit(run_job, j, cfg, not a.show_output): j for j in jobs}
        for fut in as_completed(futs):
            j = futs[fut]
            try:
                results.append(fut.result())
            except BaseException as e:  # noqa: BLE001
                results.append({"id": j.get("id"), "status": "error", "error": f"{type(e).__name__}: {e}"[:300]})
    order = {j.get("id"): i for i, j in enumerate(jobs)}
    results.sort(key=lambda r: order.get(r.get("id"), 0))
    written = Counter()
    for r in results:
        for f in (r.get("guard") or {}).get("files", []):
            written[f.split(" (")[0]] += 1
    sys.stdout.reconfigure(encoding="utf-8")
    for r in results:
        g = r.get("guard") or {}
        line = f"[{r.get('status')}] {r.get('id')}  {r.get('latency_s', '?')}s  {r.get('run', '')}"
        print(line)
        for k in ("error", "worker_says"):
            if r.get(k):
                print(f"    {k}: {r[k]}")
        for f in g.get("files", []):
            print(f"    file: {f}")
        for b in g.get("blocking", []):
            print(f"    BLOCK: {b}")
        for w in g.get("warnings", []) + r.get("warnings", []):
            print(f"    warn: {w}")
        if r.get("quote_check", {}).get("failed"):
            print(f"    quotes failed: {r['quote_check']}")
        if a.show_output and r.get("output"):
            print("    " + r["output"].replace("\n", "\n    "))
    conflicts = [p for p, n in written.items() if n > 1]
    if conflicts:
        print("CONFLICT (same path from several jobs): " + ", ".join(conflicts))
    ok = sum(r.get("status") == "ok" for r in results)
    print(f"done: {ok}/{len(results)} ok")
    (Path(a.jobs).with_suffix(".results.json")).write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0 if ok == len(results) and not conflicts else 2


if __name__ == "__main__":
    raise SystemExit(main())
