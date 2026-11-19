"""Nightly retrieval check: does the index still find the right passages? No answer is generated, so it costs nothing.

  python evals/runners/nightly_retrieval.py run     [--limit 120] [--index DIR] [--results evals/results/nightly]
  python evals/runners/nightly_retrieval.py adopt-baseline --from evals/results/nightly/<date>      # replace the baseline: always an explicit decision
  python evals/runners/nightly_retrieval.py status  [--results ...]

`run` starts the existing retrieval probe (evals/runners/rag_v2_retrieval_probe.py: embedding and rerank servers on this machine, no model
that writes answers, no paid call), keeps its raw output in a NEW folder named by date (nothing is overwritten), appends one line to
trend.jsonl and writes LATEST.json with the numbers and any regression against baseline.json. It is skipped, and says so in LATEST.json,
when the embedding or rerank server is not answering. Regressions are reported, never repaired: changing retrieval is the owner's decision.
The first successful run with no baseline.json becomes the baseline (recorded with "auto": true); an existing baseline is never replaced by a run.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[2]
PROBE = ROOT / "evals/runners/rag_v2_retrieval_probe.py"
DEFAULT_RESULTS = ROOT / "evals/results/nightly"
DEFAULT_INDEX = os.environ.get("CAMPUS247_RAG_V2_INDEX", "data/rag_v2_index/embedded2")
MODEL_URLS = ("http://127.0.0.1:18081/info", "http://127.0.0.1:18082/info")
# Drops (in percentage points of the share of cases) that count as a regression against the baseline.
TOLERANCE = {"fused_top8": 0.03, "survive": 0.05}

Probe = Callable[[Path, int, str], dict]


def metrics_from(probe_output: dict) -> dict:
    """Shares of answerable cases whose gold passage is in the fused top 8 / anywhere / survives rerank. Counts come from the probe."""
    total = {"n": 0, "any_hit": 0, "fused_top8_hit": 0, "final_hit": 0}
    for counters in probe_output.get("summary", {}).values():
        for key in total:
            total[key] += int(counters.get(key, 0))
    n = total["n"]
    if n == 0:
        raise ValueError("the probe reported no cases")
    return {"cases": n, "any": total["any_hit"] / n, "fused_top8": total["fused_top8_hit"] / n, "survive": total["final_hit"] / n,
            "rerank": probe_output.get("rerank_mode"), "embedding": probe_output.get("embedding_mode")}


def regressions(metrics: dict, baseline: dict | None) -> list[str]:
    if baseline is None:
        return []
    found = []
    for key, allowed in TOLERANCE.items():
        drop = round(baseline[key] - metrics[key], 6)  # exactly at the limit is allowed; rounding hides float noise
        if drop > allowed:
            found.append(f"{key} fell {drop * 100:.1f} points (baseline {baseline[key] * 100:.1f}%, now {metrics[key] * 100:.1f}%, allowed {allowed * 100:.0f})")
    return found


def free_folder(results: Path, now: datetime) -> Path:
    """A folder for this run that does not exist yet: nightly/20261117, then 20261117-02 ... Earlier results are never touched."""
    results.mkdir(parents=True, exist_ok=True)
    base = now.strftime("%Y%m%d")
    for number in range(1, 100):
        folder = results / (base if number == 1 else f"{base}-{number:02d}")
        try:
            folder.mkdir()
            return folder
        except FileExistsError:
            continue
    raise SystemExit("no free folder for today's run")


def write_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=1, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)


def models_up(check: Callable[[str], bool]) -> bool:
    return all(check(url) for url in MODEL_URLS)


def http_check(url: str) -> bool:
    import urllib.request
    try:
        with urllib.request.urlopen(url, timeout=3) as response:  # noqa: S310 -- loopback URLs fixed above
            return response.status < 300
    except OSError:
        return False


def real_probe(out: Path, limit: int, index: str) -> dict:
    command = [sys.executable, "-B", str(PROBE), "--split", "dev", "--limit", str(limit), "--index", index, "--out", str(out)]
    subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True, timeout=3600,
                   env=dict(os.environ, PYTHONPATH=os.pathsep.join([str(ROOT), str(ROOT / "services/api/src"), os.environ.get("PYTHONPATH", "")])))
    return json.loads(out.read_text(encoding="utf-8"))


def run(results: Path, *, limit: int = 120, index: str = DEFAULT_INDEX, probe: Probe = real_probe, check: Callable[[str], bool] = http_check,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc), trigger: str = "schedule") -> dict:
    started = now()
    latest = {"at": started.isoformat().replace("+00:00", "Z"), "trigger": trigger, "ok": False}
    if not models_up(check):
        latest["skipped"] = "models_down"  # not a quality problem; the alert rules treat it separately
        write_json(_ensure(results) / "LATEST.json", latest)
        return latest
    folder = free_folder(results, started)
    try:
        output = probe(folder / "retrieval.json", limit, index)
        metrics = metrics_from(output)
    except (subprocess.SubprocessError, OSError, ValueError, KeyError) as error:
        latest["error"] = type(error).__name__
        write_json(folder / "run.json", latest)
        write_json(results / "LATEST.json", latest)
        return latest
    baseline_path = results / "baseline.json"
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))["metrics"] if baseline_path.is_file() else None
    found = regressions(metrics, baseline)
    latest |= {"ok": True, "folder": folder.name, "metrics": metrics, "regressions": found, "baseline": baseline is not None, "limit": limit}
    write_json(folder / "run.json", latest)
    if baseline is None:  # nothing to compare with yet: this run is the reference from now on
        write_json(baseline_path, {"adopted_at": latest["at"], "from": folder.name, "metrics": metrics, "auto": True})
    with (results / "trend.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"at": latest["at"], "trigger": trigger, "folder": folder.name, **metrics, "regressed": bool(found)}, ensure_ascii=False) + "\n")
    write_json(results / "LATEST.json", latest)
    return latest


def _ensure(results: Path) -> Path:
    results.mkdir(parents=True, exist_ok=True)
    return results


def adopt_baseline(results: Path, source: Path) -> dict:
    """Make a finished run the reference for later comparisons. Only on an explicit command; the previous baseline is kept next to it."""
    run_file = json.loads((source / "run.json").read_text(encoding="utf-8"))
    if not run_file.get("ok"):
        raise SystemExit("that run did not finish; it cannot be a baseline")
    target = results / "baseline.json"
    if target.exists():
        stem = f"baseline-before-{int(time.time())}"
        kept = results / f"{stem}.json"
        for number in range(2, 100):  # two decisions in the same second must not collide
            if not kept.exists():
                break
            kept = results / f"{stem}-{number:02d}.json"
        target.rename(kept)
    record = {"adopted_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"), "from": source.name, "metrics": run_file["metrics"]}
    write_json(target, record)
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("run", "adopt-baseline", "status"))
    parser.add_argument("--limit", type=int, default=120)
    parser.add_argument("--index", default=DEFAULT_INDEX)
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--from", dest="source", type=Path)
    parser.add_argument("--trigger", default="schedule", choices=("schedule", "release", "manual"))
    args = parser.parse_args()
    if args.command == "run":
        latest = run(args.results, limit=args.limit, index=args.index, trigger=args.trigger)
        print(json.dumps(latest, ensure_ascii=False))
        return 0 if latest.get("ok") or latest.get("skipped") else 1
    if args.command == "adopt-baseline":
        if not args.source:
            parser.error("--from is required")
        print(json.dumps(adopt_baseline(args.results, args.source), ensure_ascii=False))
        return 0
    path = args.results / "LATEST.json"
    print(path.read_text(encoding="utf-8") if path.is_file() else "no run yet")
    return 0


if __name__ == "__main__":
    sys.exit(main())
