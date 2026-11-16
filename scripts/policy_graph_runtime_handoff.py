"""Read-only state snapshot and exact guarded API owner handoff for this local task."""
import argparse
import hashlib
import json
import sqlite3
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from build_policy_graph import ROOT, destination
from multi_agent_live_resources import paid_view, native_view

RECEIPT = ROOT / "infra/local/multi-agent-integrated-20261013-01/20261013T215634152756-live-launch.json"
EXPECTED = {
    13108: {"parent": 18752, "created": "2026-10-14T04:56:34.1553170+07:00"},
    10336: {"parent": 13108, "created": "2026-10-14T04:56:34.1824350+07:00"},
}


def retain(name, value):
    with destination(name).open("x", encoding="utf-8") as out:
        json.dump(value, out, indent=2, ensure_ascii=False)


def quiet_state():
    path = (ROOT / "infra/local/multi-agent-integrated-20261013-01/agent-runs.sqlite3").resolve()
    with sqlite3.connect(path.as_uri()+"?mode=ro", uri=True) as db:
        active = db.execute("SELECT COUNT(*) FROM agent_run WHERE status='running' AND lease_until>?", (time.time(),)).fetchone()[0]
        pending = sum(bool(json.loads(row[0]).get("pending")) for row in db.execute("SELECT record FROM agent_run WHERE status='running'"))
    if active or pending:
        raise ValueError("API has active lease or pending model; handoff denied")
    return {"active_leases": active, "pending_models": pending}


def backup(source_name, output):
    source = (ROOT/source_name).resolve(strict=True)
    target = destination(output)
    if not source.is_relative_to(ROOT) or target.exists():
        raise ValueError("exact new workspace backup required")
    with target.open("xb"):
        pass
    src = sqlite3.connect(source.as_uri()+"?mode=ro", uri=True)
    dst = sqlite3.connect(target)
    try:
        src.backup(dst)
    finally:
        dst.close(); src.close()
    return {"source": str(source), "backup": str(target), "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}


def prepare():
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    if receipt["owned_pids"] != {"api": 13108} or receipt["paid_writer"] != "api8003_only":
        raise ValueError("old owner receipt mismatch")
    quiet = quiet_state()
    copies = [backup(source, output) for source, output in (
        ("infra/local/certificate-stage1-20261013-01/demo.sqlite3", "business-before-live-01.sqlite3"),
        ("infra/local/public-rag-20261013/conversations.sqlite3", "history-before-live-01.sqlite3"),
        ("infra/local/multi-agent-integrated-20261013-01/agent-runs.sqlite3", "runs-before-live-01.sqlite3"),
    )]
    retain("runtime-handoff-preflight-01.json", {"at": datetime.now(timezone.utc).isoformat(),
        "receipt_sha256": hashlib.sha256(RECEIPT.read_bytes()).hexdigest(), "expected_owners": EXPECTED,
        "quiet": quiet, "backups": copies, "paid": paid_view(), "native": native_view(),
        "effect": "stop only verified idle local API worker10336 and wrapper13108; retain every database and other runtime"})


def handoff():
    quiet_state()
    # Immutable discovery above is revalidated in the same PowerShell process
    # immediately before the two exact Stop-Process calls. No tree/wildcard kill.
    command = r'''
$a=Get-CimInstance Win32_Process -Filter 'ProcessId=10336'
$b=Get-CimInstance Win32_Process -Filter 'ProcessId=13108'
if(!$a -or !$b -or $a.ParentProcessId -ne 13108 -or $b.ParentProcessId -ne 18752){throw 'owner parent changed'}
if($a.CreationDate.ToString('o') -ne '2026-10-14T04:56:34.1824350+07:00' -or $b.CreationDate.ToString('o') -ne '2026-10-14T04:56:34.1553170+07:00'){throw 'PID creation changed'}
$expectedA='"C:\Users\Duong Vinh\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -B -u "C:\Users\Duong Vinh\Vinh\scripts\run_multi_agent.py" --mode live --frontend 3003'
$expectedB='"C:\Users\Duong Vinh\Vinh\infra\local\rag-fixture\.venv\Scripts\python.exe" -B -u "C:\Users\Duong Vinh\Vinh\scripts\run_multi_agent.py" --mode live --frontend 3003'
if($a.CommandLine -cne $expectedA -or $b.CommandLine -cne $expectedB){throw 'exact API command changed'}
$l=Get-NetTCPConnection -State Listen -LocalPort 8003
if(@($l).Count -ne 1 -or $l.OwningProcess -ne 10336 -or $l.LocalAddress -ne '127.0.0.1'){throw 'listener changed'}
Stop-Process -Id 10336 -ErrorAction Stop
if(Get-Process -Id 13108 -ErrorAction SilentlyContinue){Stop-Process -Id 13108 -ErrorAction Stop}
'''
    result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
        capture_output=True, text=True, encoding="utf-8", errors="replace", creationflags=0x08000000)
    retain("runtime-handoff-result-01.json", {"at": datetime.now(timezone.utc).isoformat(),
        "targets": [10336, 13108], "exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr,
        "native_frontend_proxy_targets": [], "data_deleted": False})
    if result.returncode:
        raise RuntimeError("exact owner handoff did not complete; inspect retained result")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("mode", choices=("prepare", "handoff"))
    {"prepare": prepare, "handoff": handoff}[parser.parse_args().mode]()
