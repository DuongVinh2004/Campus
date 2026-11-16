"""Restore the retained candidate using fresh logs and cumulative native usage.

Reuse the verified restart implementation and its guards. Never rerun its old
namespace, create another paid writer, reset counters or terminate a process.
"""
import restart_unified_ai_local_20261014 as restart
import json
import subprocess
from unified_ai_runtime_probe import ROOT, checked


if __name__ == "__main__":
    # Socket failure in a restricted shell does not prove a port is free.
    # Require authoritative Windows inspection; access failure stops startup.
    result = subprocess.run(["powershell.exe", "-NoProfile", "-Command",
        "$ErrorActionPreference='Stop'; @(Get-NetTCPConnection -State Listen -ErrorAction Stop | "
        "Where-Object LocalPort -in 3006,8006,8003,8000,18081,18082 | "
        "Select-Object LocalPort,OwningProcess) | ConvertTo-Json -Compress"],
        capture_output=True, text=True, check=True, timeout=15)
    listeners = json.loads(result.stdout) if result.stdout.strip() else []
    if listeners:
        raise RuntimeError("Required ports already owned; reuse the existing runtime")
    restart.OUTPUT = checked(ROOT / "infra/local/unified-ai-20261014-03/runtime")
    restart.NATIVE = checked(ROOT / "infra/local/rag-advanced-models-20261013-12")
    restart.PRIOR_NATIVE = checked(ROOT / "infra/local/rag-advanced-models-20261013-11")
    restart.main()
