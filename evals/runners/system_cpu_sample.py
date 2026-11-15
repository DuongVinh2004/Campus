"""Whole-machine CPU by role while a load test runs: which process eats the cores.

  python evals/runners/system_cpu_sample.py --seconds 150 --out evals/results/.../cpu.json

Samples Windows per-process counters every 3 s and groups them by role (API workers, model server, gateway sidecar,
Postgres, frontend, load generator, other). Reports average and peak cores used by each role plus the whole-machine
total. Only counters and command-line shapes are read; nothing is written but the summary.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import time
from collections import defaultdict
from pathlib import Path

SCRIPT = r"""
$names = @{}
Get-CimInstance Win32_Process | ForEach-Object { $names[[int]$_.ProcessId] = @{cmd = $_.CommandLine; parent = [int]$_.ParentProcessId; name = $_.Name} }
$rows = Get-CimInstance Win32_PerfFormattedData_PerfProc_Process | Where-Object { $_.Name -ne '_Total' -and $_.Name -ne 'Idle' -and $_.PercentProcessorTime -gt 0 }
$out = foreach ($r in $rows) { $i = $names[[int]$r.IDProcess]; [pscustomobject]@{pid = [int]$r.IDProcess; cpu = [int]$r.PercentProcessorTime; name = $r.Name; cmd = if ($i) { $i.cmd } else { '' }; parent = if ($i) { $i.parent } else { 0 }; pname = if ($i) { $i.name } else { '' } }}
$apiParents = @($names.Keys | Where-Object { $names[$_].cmd -match 'knowledge_platform.py serve' })
@{rows = @($out); api_parents = $apiParents} | ConvertTo-Json -Compress -Depth 4
"""


def role(row: dict, api_parents: set[int]) -> str:
    cmd = (row.get("cmd") or "").replace("\\", "/")
    if "serve_rag_models.py" in cmd:
        return "model_server"
    if "gateway_sidecar.py" in cmd:
        return "gateway_sidecar"
    if "knowledge_platform.py serve" in cmd or row["parent"] in api_parents:
        return "api"
    if "rag_load_test.py" in cmd:
        return "load_generator"
    if row["name"].startswith("postgres"):
        return "postgres"
    if "knowledge_platform_frontend" in cmd or row["pname"] == "node.exe":
        return "frontend"
    return "other"


def sample() -> tuple[list[dict], set[int]]:
    out = subprocess.run(["powershell", "-NoProfile", "-Command", SCRIPT], capture_output=True, text=True).stdout
    value = json.loads(out) if out.strip() else {"rows": [], "api_parents": []}
    rows, parents = value.get("rows") or [], value.get("api_parents") or []
    return (rows if isinstance(rows, list) else [rows]), set(parents if isinstance(parents, list) else [parents])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=int, default=120)
    parser.add_argument("--interval", type=int, default=3)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    per_role: dict[str, list[float]] = defaultdict(list)
    other_by_name: dict[str, float] = defaultdict(float)
    started = time.time()
    while time.time() - started < args.seconds:
        rows, api_parents = sample()  # API workers are children of the serving process, which may itself be idle
        totals: dict[str, float] = defaultdict(float)
        for row in rows:
            totals[role(row, api_parents)] += row["cpu"] / 100.0
            if role(row, api_parents) == "other":
                other_by_name[row["name"].split("#")[0]] += row["cpu"] / 100.0
        for key in ("api", "model_server", "gateway_sidecar", "postgres", "frontend", "load_generator", "other"):
            per_role[key].append(totals.get(key, 0.0))
        time.sleep(args.interval)
    summary = {key: {"avg_cores": round(sum(v) / len(v), 2), "peak_cores": round(max(v), 2)} for key, v in per_role.items()}
    summary["machine_total_avg_cores"] = round(sum(sum(v) / len(v) for v in per_role.values()), 2)
    summary["samples"] = len(per_role["api"])
    samples = max(1, summary["samples"])
    summary["other_top_avg_cores"] = {name: round(value / samples, 2) for name, value in
                                      sorted(other_by_name.items(), key=lambda item: -item[1])[:6]}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
