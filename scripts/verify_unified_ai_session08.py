"""Combined backend verification and retained-data audit, no UI/model calls."""
import difflib
import hashlib
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET

_arguments = sys.argv
sys.argv = sys.argv[:1]  # Older imported build helpers parse argv at import.
from unified_ai_runtime_probe import ROOT, checked, retain, http
from verify_unified_ai_candidate import database_digest
from multi_agent_live_resources import paid_view, native_view
from prepare_unified_ai_session08 import listener_inventory
sys.argv = _arguments

STATE = checked(ROOT / "infra/local/unified-ai-20261014-08")


def tests(number):
    from verify_unified_ai_session06 import TEST_FILES
    selected = list(dict.fromkeys([*TEST_FILES, "tests/integration/test_unified_actor_features.py",
        "tests/integration/test_unified_storage_completion.py", "tests/api/test_privacy_requests.py",
        "tests/api/test_answer_feedback.py", "tests/api/test_session_revocation.py", "tests/api/test_identity_boundary.py",
        "tests/api/test_identity_middleware.py", "tests/unit/conversation/test_context.py"]))
    if number not in {"01", "04", "06"}:
        selected = ["tests/integration/test_unified_actor_features.py", "tests/integration/test_unified_durable_services.py",
                    "tests/api/test_unified_storage_profile.py", "tests/unit/assistance/test_actor_state_storage.py"]
    paths = [checked(STATE / name) for name in (f"backend-tests-{number}", f"backend-tests-{number}.xml",
        f"backend-tests-{number}.log", f"idempotency-{number}.sqlite3", f"test-command-{number}.json")]
    if any(path.exists() for path in paths):
        raise FileExistsError("retain existing attempt; use a fresh exact attempt number")
    command = [sys.executable, "-B", "-u", "-m", "pytest", *selected, "-q", "-o", "faulthandler_timeout=30", "-p", "no:cacheprovider",
        "-p", "pytest_asyncio.plugin", "--basetemp="+str(paths[0]), "--junitxml="+str(paths[1])]
    env = {**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "PYTHONDONTWRITEBYTECODE": "1",
           "CAMPUS247_IDEMPOTENCY_DB": str(paths[3]), "PYTHONIOENCODING": "utf-8"}
    with paths[2].open("xb") as log:
        result = subprocess.run(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, check=False)
    retain(paths[4], {"command": command, "exit_code": result.returncode, "ui_tests": False, "provider_dispatches": 0,
                      "environment": {key: env[key] for key in ("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "PYTHONDONTWRITEBYTECODE", "CAMPUS247_IDEMPOTENCY_DB")}})
    print(paths[2].read_text(encoding="utf-8", errors="replace")[-22000:])
    raise SystemExit(result.returncode)


def audit(number):
    before = json.loads((STATE / "preflight.json").read_text(encoding="utf-8"))
    sources = [*before["sources"], *json.loads((STATE / "extra-preimages.json").read_text())]
    changes = []
    for item in sources:
        target, snapshot = checked(ROOT / item["path"]), checked(STATE / item["backup"])
        assert hashlib.sha256(snapshot.read_bytes()).hexdigest() == item["sha256"]
        changes.extend(difflib.unified_diff(snapshot.read_text(encoding="utf-8").splitlines(True),
            target.read_text(encoding="utf-8").splitlines(True), fromfile=item["path"]+" (preimage)", tofile=item["path"]))
    patch = checked(STATE / f"source-changes-{number}.patch")
    with patch.open("x", encoding="utf-8") as output:
        output.write("".join(changes))
    preservation = []
    for item in before["snapshots"]:
        current = database_digest(checked(ROOT / item["source"]))
        preservation.append({"database": item["source"], "all_tables_unchanged": current == item["tables"]})
    latest = {}
    for path in sorted(STATE.glob("backend-tests-*.xml")):
        for case in ET.parse(path).getroot().iter("testcase"):
            latest[(case.get("classname"), case.get("name"))] = not any(case.find(tag) is not None for tag in ("failure", "error", "skipped"))
    status = subprocess.run(["git", "status", "--porcelain=v1"], cwd=ROOT, capture_output=True, text=True, check=True)
    result = {"database_preservation": preservation, "backend_unique": len(latest), "backend_all_passed": bool(latest) and all(latest.values()),
        "runtime_before": before["runtime"], "runtime_after": {str(p): http(p, "/v1/assistant/runtime" if p == 8006 else "/health/live") for p in (8006, 8003)},
        "listeners_before": before["ownership"], "listeners_after": listener_inventory(),
        "paid_unchanged": paid_view() == before["paid_before"], "native_unchanged": native_view() == before["native_before"],
        "git_status": status.stdout, "git_warnings": status.stderr, "preimages_verified": len(sources),
        "ui_tests_run": False, "runtime_transition": False, "provider_dispatches": 0,
        "limitations": ["No human/browser acceptance", "Legacy owner evidence required for real imports", "Existing proxy writer does not consume new preferences until an explicitly composed transition"]}
    retain(STATE / f"session-verification-{number}.json", result)
    print(json.dumps({key: result[key] for key in ("backend_unique", "backend_all_passed", "database_preservation", "paid_unchanged", "native_unchanged")}))
    assert all(row["all_tables_unchanged"] for row in preservation)
    assert result["paid_unchanged"] and result["native_unchanged"]


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) != 3 or sys.argv[1] not in {"tests", "audit"} or sys.argv[2] not in {"01", "02", "03", "04", "05", "06", "07"}:
        raise ValueError("explicit stage and fresh attempt required")
    {"tests": tests, "audit": audit}[sys.argv[1]](sys.argv[2])
