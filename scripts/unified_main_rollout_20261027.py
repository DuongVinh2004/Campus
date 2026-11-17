"""Switch the one local entry; retain data, build artifacts and idle-test evidence."""
import asyncio
from datetime import UTC, datetime
import hashlib
import json
import shlex
import sqlite3
import subprocess
import sys

from knowledge_platform import ROOT, STATE, checked_path, connection, rehearsal_bundle_paths, retain
from knowledge_platform_runtime import FRONTEND, HIDDEN, matching_processes, process_inventory, start, worker_state
from knowledge_automation_checkpoint_20261027 import database

OLD = "frontend-knowledge-automation-20261027-15"
REHEARSALS = {
    8017: ROOT / "infra/local/knowledge-automation-20261026/schema-rehearsal-bundle-20261027T072224263352.json",
    8018: ROOT / "infra/local/knowledge-automation-20261026/schema-rehearsal-bundle-20261026T174106266973.json",
}


def ps(command):
    value = subprocess.run(["powershell.exe", "-NoProfile", "-Command", command], cwd=ROOT,
        capture_output=True, text=True, encoding="utf-8", creationflags=HIDDEN, check=True).stdout.strip()
    return json.loads(value) if value else []


def listeners():
    rows = ps("Get-NetTCPConnection -State Listen | Where-Object { $_.LocalPort -in 8015,3015,8017,8018,3018,8006,3115 } | Select-Object LocalPort,OwningProcess | ConvertTo-Json -Compress")
    return rows if isinstance(rows, list) else [rows]


def process(pid):
    value = ps(f"Get-CimInstance Win32_Process -Filter 'ProcessId={int(pid)}' | Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress")
    if not isinstance(value, dict) or value.get("ProcessId") != pid:
        raise RuntimeError("Listener process changed")
    return value


def idle(path):
    path = checked_path(path, ROOT)
    with sqlite3.connect(path.as_uri()+"?mode=ro", uri=True) as conn:
        pending = conn.execute("SELECT count(*) FROM conversation_turn WHERE json_extract(receipt,'$.state')='pending'").fetchone()[0]
        recent_user = 0
        for (encoded,) in conn.execute("SELECT m.record FROM message m WHERE m.sequence=(SELECT max(x.sequence) FROM message x WHERE x.conversation_id=m.conversation_id)"):
            value = json.loads(encoded)
            if value["sender_type"] == "USER" and (datetime.now(UTC)-datetime.fromisoformat(value["created_at"])).total_seconds() < 90:
                recent_user += 1
        if pending or recent_user:
            raise RuntimeError("Active/pending chat exists; listener preserved")
        return {"path":str(path.relative_to(ROOT)), "pending":pending, "recent_unanswered":recent_user,
                "conversations":conn.execute("SELECT count(*) FROM conversation").fetchone()[0],
                "messages":conn.execute("SELECT count(*) FROM message").fetchone()[0]}


def identities():
    return {name:hashlib.sha256(checked_path(STATE/name,ROOT).read_bytes()).hexdigest() for name in
        ("owner-identity.json","owner-credentials.json","student-identity.json","student-credentials.json")}


async def main():
    scope = checked_path(ROOT / "infra/local/knowledge-automation-20261026" / ("unified-main-rollout-"+datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")), ROOT)
    scope.mkdir(exist_ok=False)
    report = {"entry":"http://127.0.0.1:8015", "complete":False, "data_deleted":False}
    try:
        report["before"] = await database(connection())
        report["identities_before"] = identities()
        report["worker_before"] = worker_state(process_inventory(OLD))
        report["idle_before"] = [idle(STATE/"conversations.sqlite3")]
        for manifest in REHEARSALS.values():
            report["idle_before"].append(idle(rehearsal_bundle_paths(manifest)["conversations.sqlite3"]))
        before = listeners()
        exact = []
        inventory = process_inventory(OLD)
        for listener in before:
            port, pid = listener["LocalPort"], listener["OwningProcess"]
            row = process(pid)
            words = [w.strip('"').replace("\\","/").casefold() for w in shlex.split(row["CommandLine"], posix=False)]
            if port in {8015,3015}:
                if pid not in matching_processes(inventory, "api" if port == 8015 else "frontend", OLD):
                    raise RuntimeError("Main listener identity mismatch")
            elif port in REHEARSALS:
                script = str(ROOT/"scripts/knowledge_platform.py").replace("\\","/").casefold()
                manifest = str(checked_path(REHEARSALS[port],ROOT)).replace("\\","/").casefold()
                if not (any(w in {script,"scripts/knowledge_platform.py"} for w in words) and
                        "serve" in words and "--rehearsal" in words and manifest in words and str(port) in words and "--generation" not in words):
                    raise RuntimeError("Rehearsal listener identity mismatch")
            elif port == 3018:
                build = str(checked_path(STATE/"frontend-knowledge-automation-20261027-13",ROOT)).replace("\\","/").casefold()
                if not (build in words and "start" in words and "3018" in words):
                    raise RuntimeError("Rehearsal frontend identity mismatch")
            else:
                raise RuntimeError("Historical entry is occupied; owner must be inspected before changing it")
            exact.append({"port":port, **row})
        if {row["port"] for row in exact} != {8015,3015,8017,8018,3018}:
            raise RuntimeError("Listener set changed; preflight required")
        report["stop_targets"] = exact
        retain(scope/"preflight.json", report)
        for row in sorted(exact, key=lambda row:row["port"]):
            # Check live identity immediately before stopping this exact process.
            if process(row["ProcessId"]) != {k:row[k] for k in ("ProcessId","CommandLine")}:
                raise RuntimeError("Process identity changed since preflight")
            escaped = row["CommandLine"].replace("'", "''")
            command = f"$targetProcess=Get-CimInstance Win32_Process -Filter 'ProcessId={row['ProcessId']}'; if ($targetProcess.CommandLine -cne '{escaped}') {{ throw 'Identity changed' }}; Stop-Process -Id {row['ProcessId']} -ErrorAction Stop"
            subprocess.run(["powershell.exe","-NoProfile","-Command",command], cwd=ROOT, check=True,
                capture_output=True, creationflags=HIDDEN)
        report["runtime"] = await asyncio.to_thread(start, FRONTEND)
        report["after"] = await database(connection())
        report["identities_unchanged"] = report["identities_before"] == identities()
        report["worker_after"] = worker_state(process_inventory(FRONTEND))
        report["idle_after"] = [idle(STATE/"conversations.sqlite3")]
        for manifest in REHEARSALS.values():
            report["idle_after"].append(idle(rehearsal_bundle_paths(manifest)["conversations.sqlite3"]))
        report["listeners_after"] = listeners()
        report["checks"] = {"data_and_release_preserved": report["before"] == report["after"],
            "account_files_preserved":report["identities_unchanged"],
            "worker_reused":report["worker_before"]["owner"] == report["worker_after"]["owner"],
            "chat_data_preserved":report["idle_before"] == report["idle_after"],
            "one_serving_entry":{row["LocalPort"] for row in report["listeners_after"]} == {8015,3015}}
        report["complete"] = all(report["checks"].values())
        if not report["complete"]:
            raise RuntimeError("Consolidation verification failed; evidence retained")
    except Exception as error:
        report["error_type"] = type(error).__name__
        raise
    finally:
        retain(scope/"receipt.json", report)
        print(json.dumps({"receipt":str(scope/"receipt.json"),"complete":report["complete"]}))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(main())
