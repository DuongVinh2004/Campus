"""Exclusive backend commands and logs; new fixture paths for every attempt."""
import os
import subprocess
import sys
from unified_parallel_a_workspace import ROOT, STATE, checked, retain

if __name__ == "__main__":
    number = sys.argv[1]
    if len(number) != 2 or not number.isdigit() or not 2 <= int(number) <= 99:
        raise ValueError("exact fresh attempt required")
    paths = [checked(STATE / "checks" / ("backend-" + number + suffix)) for suffix in [".log", ".xml", ".json"]]
    if any(p.exists() for p in paths):
        raise FileExistsError("preserve prior run")
    tests = sys.argv[2:] or ["tests/unified_workflow13a"]
    command = [sys.executable, "-B", "-u", "-m", "pytest", *tests, "-q", "-o", "faulthandler_timeout=30",
        "-p", "no:cacheprovider", "-p", "pytest_asyncio.plugin", "--basetemp=" + str(checked(STATE / ("pytest-" + number))), "--junitxml=" + str(paths[1])]
    environment = {**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "PYTHONDONTWRITEBYTECODE": "1",
        "CAMPUS247_IDEMPOTENCY_DB": str(checked(STATE / ("idempotency-" + number + ".sqlite3"))), "PYTHONIOENCODING": "utf-8"}
    with paths[0].open("xb") as log:
        result = subprocess.run(command, cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT)
    retain(paths[2], {"command": command, "exit_code": result.returncode, "ui_tests": False, "provider_calls": 0})
    sys.stdout.reconfigure(encoding="utf-8")
    print(paths[0].read_text(encoding="utf-8", errors="replace")[-14000:])
    raise SystemExit(result.returncode)
