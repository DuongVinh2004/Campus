"""Combined backend/contracts and full retained-row audit; no UI/runtime launch."""
import sys
import os
import subprocess
sys.dont_write_bytecode = True
arguments = sys.argv
sys.argv = sys.argv[:1]
import verify_unified_ai_session08 as previous
from unified_ai_runtime_probe import ROOT, checked
sys.argv = arguments
previous.STATE = checked(ROOT / "infra/local/unified-ai-20261015-10")


def tests(number):
    from verify_unified_ai_session06 import TEST_FILES
    selected = list(dict.fromkeys([*TEST_FILES,
        "tests/integration/test_unified_actor_features.py", "tests/integration/test_unified_storage_completion.py",
        "tests/integration/test_unified_consumers09.py", "tests/unit/assistance/test_consumer_contracts09.py",
        "tests/api/test_privacy_requests.py", "tests/api/test_answer_feedback.py", "tests/api/test_session_revocation.py",
        "tests/api/test_identity_boundary.py", "tests/api/test_identity_middleware.py", "tests/unit/conversation/test_context.py",
        "tests/integration/test_unified_coordination10.py"]))
    if number == "06":
        selected = ["tests/integration/test_unified_coordination10.py::test_native_multi_agent_unconfigured_tool_routes_never_report_business_success"]
    elif number == "05":
        selected = ["tests/integration/test_unified_coordination10.py", "tests/unit/agent/test_multi_agent_integrated.py", "tests/api/test_multi_agent_api.py"]
    elif number != "01":
        selected = ["tests/integration/test_unified_coordination10.py", "tests/unit/agent/test_multi_agent_integrated.py",
                    "tests/api/test_multi_agent_api.py", "tests/integration/test_unified_consumers09.py",
                    "tests/unit/assistance/test_consumer_contracts09.py", "tests/integration/test_unified_actor_features.py"]
    paths = [checked(previous.STATE / name) for name in (f"backend-tests-{number}", f"backend-tests-{number}.xml",
        f"backend-tests-{number}.log", f"idempotency-{number}.sqlite3", f"test-command-{number}.json")]
    if any(path.exists() for path in paths):
        raise FileExistsError("preserve previous attempt")
    command = [sys.executable, "-B", "-u", "-m", "pytest", *selected, "-q", "-o", "faulthandler_timeout=30",
        "-p", "no:cacheprovider", "-p", "pytest_asyncio.plugin", "--basetemp=" + str(paths[0]), "--junitxml=" + str(paths[1])]
    env = {**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "PYTHONDONTWRITEBYTECODE": "1",
        "CAMPUS247_IDEMPOTENCY_DB": str(paths[3]), "PYTHONIOENCODING": "utf-8"}
    with paths[2].open("xb") as log:
        result = subprocess.run(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
    previous.retain(paths[4], {"command": command, "exit_code": result.returncode, "ui_tests": False, "provider_dispatches": 0})
    print(paths[2].read_text(encoding="utf-8", errors="replace")[-20000:])
    raise SystemExit(result.returncode)


def host(number):
    import json
    from unified_ai_runtime_probe import http
    from prepare_unified_ai_session08 import listener_inventory
    prior = json.loads(checked(ROOT / "infra/local/unified-ai-20261014-09/host-runtime-read-01.json").read_text(encoding="utf-8"))
    observed = {str(port): http(port, "/v1/assistant/runtime" if port == 8006 else "/health/live") for port in (8006, 8003)}
    previous.retain(previous.STATE / ("host-runtime-read-" + number + ".json"), {"runtime": observed,
        "listeners": listener_inventory(), "prior_session_runtime": prior["runtime"],
        "same_runtime_values": json.loads(json.dumps(observed)) == prior["runtime"], "method": "GET health/runtime and netstat only",
        "runtime_transition": False, "provider_dispatches": 0})
    print(json.dumps(observed))


def audit(number):
    import json
    import hashlib
    import difflib
    previous.audit(number)
    entries = [*json.loads(checked(previous.STATE / "schema-preimages.json").read_text(encoding="utf-8")),
               *json.loads(checked(previous.STATE / "composition-preimages.json").read_text(encoding="utf-8"))]
    differences = []
    for entry in entries:
        source, backup = checked(ROOT / entry["path"]), checked(previous.STATE / entry["backup"])
        assert hashlib.sha256(backup.read_bytes()).hexdigest() == entry["sha256"]
        differences.extend(difflib.unified_diff(backup.read_text(encoding="utf-8").splitlines(True),
            source.read_text(encoding="utf-8").splitlines(True), fromfile=entry["path"] + " (preimage)", tofile=entry["path"]))
    with checked(previous.STATE / ("schema-changes-" + number + ".patch")).open("x", encoding="utf-8") as patch:
        patch.write("".join(differences))
    previous.retain(previous.STATE / ("extended-preservation-" + number + ".json"), {"schema_preimages_verified": len(entries), "schema_diff": "schema-changes-" + number + ".patch"})


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) != 3 or sys.argv[2] not in {"01", "02", "03", "04", "05", "06"}:
        raise ValueError("fresh exact attempt required")
    {"tests": tests, "audit": audit, "host": host}[sys.argv[1]](sys.argv[2])
