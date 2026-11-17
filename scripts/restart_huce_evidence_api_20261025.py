"""Restart only the verified local API listener to load scoped code repairs."""
import json
import argparse
import subprocess
import time
from datetime import UTC, datetime

from knowledge_platform import ROOT, checked_path, retain
from knowledge_platform_runtime import HIDDEN, api_state, matching_processes, process_inventory, start


def main(attempt="01"):
    out = checked_path(ROOT / "infra/local/huce-evidence-20261025-01", ROOT)
    before = api_state()
    expected = {16: "01a16ef3-3129-7b4a-b16c-569cda6d916b", 17: "01a16f03-62a4-7fa1-ade2-c848a2b16ad7"}
    assert before["release_id"] == expected[before["generation"]]
    result = subprocess.run(["powershell.exe", "-NoProfile", "-Command",
        "Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 8015 -State Listen | Select-Object -ExpandProperty OwningProcess"],
        capture_output=True, text=True, check=True, creationflags=HIDDEN)
    values = set(result.stdout.split())
    assert len(values) == 1 and next(iter(values)).isdigit()
    pid = int(next(iter(values)))
    assert pid in matching_processes(process_inventory(), "api")
    retain(out / f"api-restart-preflight-{attempt}.json", {"at": datetime.now(UTC).isoformat(), "listener_pid": pid,
        "before": before, "scope": "Only verified API listener 8015; DB, model services, worker, data and ledger retained"})
    # Exact process identity and listener ownership were checked immediately above.
    subprocess.run(["powershell.exe", "-NoProfile", "-Command", f"Stop-Process -Id {pid} -ErrorAction Stop"],
        capture_output=True, check=True, creationflags=HIDDEN)
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if not matching_processes(process_inventory(), "api"):
            break
        time.sleep(.3)
    else:
        raise RuntimeError("Old API launcher still exists; no other process stopped")
    report = start()
    after = api_state()
    assert after == before
    retain(out / f"api-restart-ready-{attempt}.json", {"at": datetime.now(UTC).isoformat(), "runtime": report,
        "after": after, "release_and_generations_unchanged": True})
    print(json.dumps({"ready": True, "generation": after["generation"], "same_release": True}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", choices=("01", "02", "03", "04", "05", "06"), default="01")
    main(parser.parse_args().attempt)
