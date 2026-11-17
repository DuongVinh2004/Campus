"""Reload only the positively identified task API, retaining all stores and accounting."""
import argparse
import json
import subprocess
import time
from datetime import UTC, datetime

from continue_huce_completion_20261025 import CORPUS, OUT, read, save
from knowledge_platform_runtime import HIDDEN, api_state, matching_processes, process_inventory, start


def main(attempt):
    before = api_state()
    release_number, generation = {"01": ("08", 17), "02": ("10", 18), "03": ("10", 18), "04": ("12", 19), "05": ("13", 20), "06": ("13", 20), "07": ("14", 21), "08": ("14", 21), "09": ("14", 21), "10": ("14", 21), "11": ("18", 22), "12": ("18", 22), "13": ("18", 22), "14": ("21", 24), "15": ("22", 25), "16": ("22", 25), "17": ("25", 26), "18": ("25", 26), "19": ("32", 27), "20": ("32", 27)}[attempt]
    baseline = read(CORPUS / f"candidate-release-{release_number}.json")
    assert before["release_id"] == baseline["release_id"] and before["generation"] == generation
    result = subprocess.run(["powershell.exe", "-NoProfile", "-Command",
        "Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 8015 -State Listen | Select-Object -ExpandProperty OwningProcess"],
        capture_output=True, text=True, check=True, creationflags=HIDDEN)
    values = set(result.stdout.split())
    assert len(values) == 1 and next(iter(values)).isdigit()
    pid = int(next(iter(values)))
    assert pid in matching_processes(process_inventory(), "api")
    save(OUT / f"api-restart-preflight-{attempt}.json", {"at": datetime.now(UTC), "before": before, "listener_pid": pid,
        "scope": "Only the exact verified API process; preserve PostgreSQL, BGE, worker, frontend, stores, releases and ledgers"})
    subprocess.run(["powershell.exe", "-NoProfile", "-Command", f"Stop-Process -Id {pid} -ErrorAction Stop"],
        capture_output=True, check=True, creationflags=HIDDEN)
    until = time.monotonic()+15
    while time.monotonic() < until:
        if not matching_processes(process_inventory(), "api"):
            break
        time.sleep(.3)
    else:
        raise RuntimeError("Verified old API still exists; other processes preserved")
    report = start(); after = api_state(); assert before == after
    save(OUT / f"api-restart-ready-{attempt}.json", {"at": datetime.now(UTC), "runtime": report, "after": after,
        "release_unchanged": True, "accounting_reset": False})
    print(json.dumps({"ready": True, "generation": after["generation"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--attempt", choices=["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12", "13", "14", "15", "16", "17", "18", "19", "20"], default="13")
    main(parser.parse_args().attempt)
