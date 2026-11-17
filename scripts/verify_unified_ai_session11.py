"""Combined backend/contracts and read-only retained-row verification for U4."""
import os
import subprocess
import sys
sys.dont_write_bytecode = True
arguments = sys.argv
sys.argv = sys.argv[:1]
import verify_unified_ai_session08 as previous
import verify_unified_ai_session10 as host_probe
sys.argv = arguments
from unified_ai_runtime_probe import ROOT, checked, retain
STATE = checked(ROOT / "infra/local/unified-ai-20261015-11")
previous.STATE = STATE
host_probe.previous.STATE = STATE


def tests(number):
    from verify_unified_ai_session06 import TEST_FILES
    selected = list(dict.fromkeys([*TEST_FILES,
        "tests/integration/test_unified_actor_features.py", "tests/integration/test_unified_storage_completion.py",
        "tests/integration/test_unified_consumers09.py", "tests/unit/assistance/test_consumer_contracts09.py",
        "tests/api/test_privacy_requests.py", "tests/api/test_answer_feedback.py", "tests/api/test_session_revocation.py",
        "tests/api/test_identity_boundary.py", "tests/api/test_identity_middleware.py", "tests/unit/conversation/test_context.py",
        "tests/integration/test_unified_coordination10.py", "tests/integration/test_unified_student11.py"]))
    if number not in {"01", "02", "03"}:
        selected = ["tests/integration/test_unified_student11.py", "tests/api/test_certificate_stage1.py",
            "tests/api/test_service_stage6.py", "tests/integration/test_unified_coordination10.py",
            "tests/unit/agent/test_multi_agent_integrated.py", "tests/unit/assistance/test_consumer_contracts09.py"]
    paths = [checked(STATE / name) for name in (f"backend-tests-{number}", f"backend-tests-{number}.xml",
        f"backend-tests-{number}.log", f"idempotency-{number}.sqlite3", f"test-command-{number}.json")]
    if any(p.exists() for p in paths):
        raise FileExistsError("preserve previous attempt")
    command = [sys.executable, "-B", "-u", "-m", "pytest", *selected, "-q", "-o", "faulthandler_timeout=30",
        "-p", "no:cacheprovider", "-p", "pytest_asyncio.plugin", "--basetemp=" + str(paths[0]), "--junitxml=" + str(paths[1])]
    env = {**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "PYTHONDONTWRITEBYTECODE": "1",
        "CAMPUS247_IDEMPOTENCY_DB": str(paths[3]), "PYTHONIOENCODING": "utf-8"}
    with paths[2].open("xb") as log:
        result = subprocess.run(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
    retain(paths[4], {"command": command, "exit_code": result.returncode, "ui_tests": False, "provider_dispatches": 0})
    print(paths[2].read_text(encoding="utf-8", errors="replace")[-16000:])
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) != 3 or sys.argv[2] not in {"01", "02", "03", "04", "05", "06"}:
        raise ValueError("fresh exact attempt required")
    {"tests": tests, "audit": previous.audit, "host": host_probe.host}[sys.argv[1]](sys.argv[2])
