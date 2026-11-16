"""Combined backend verification and preserved-state audit; no UI/runtime launch."""
import sys
import os
import subprocess
sys.dont_write_bytecode = True
args = sys.argv
sys.argv = sys.argv[:1]
import verify_unified_ai_session08 as previous
from unified_ai_runtime_probe import ROOT, checked
sys.argv = args
previous.STATE = checked(ROOT / "infra/local/unified-ai-20261014-09")


def tests(number):
    import verify_unified_ai_session06 as suite
    suite.TEST_FILES = [*suite.TEST_FILES, "tests/integration/test_unified_consumers09.py", "tests/unit/assistance/test_consumer_contracts09.py"]
    if number == "07":
        state = previous.STATE
        paths = [checked(state / name) for name in ("backend-tests-07", "backend-tests-07.xml", "backend-tests-07.log", "idempotency-07.sqlite3", "test-command-07.json")]
        if any(path.exists() for path in paths):
            raise FileExistsError("retain prior attempt")
        command = [sys.executable, "-B", "-u", "-m", "pytest", "tests/integration/test_unified_consumers09.py", "tests/unit/assistance/test_consumer_contracts09.py", "-q", "-p", "no:cacheprovider", "-p", "pytest_asyncio.plugin", "--basetemp="+str(paths[0]), "--junitxml="+str(paths[1])]
        env = {**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD":"1", "PYTHONDONTWRITEBYTECODE":"1", "CAMPUS247_IDEMPOTENCY_DB":str(paths[3]), "PYTHONIOENCODING":"utf-8"}
        with paths[2].open("xb") as output:
            result = subprocess.run(command,cwd=ROOT,env=env,stdout=output,stderr=subprocess.STDOUT)
        previous.retain(paths[4], {"command":command,"exit_code":result.returncode,"ui_tests":False,"provider_dispatches":0})
        print(paths[2].read_text(encoding="utf-8")[-12000:]); raise SystemExit(result.returncode)
    elif number == "02":
        previous.tests("04")
    elif number in {"01", "03", "06"}:
        previous.tests(number)
    else:
        raise ValueError("fresh explicit backend attempt required")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) != 3 or sys.argv[1] not in {"tests", "audit"}:
        raise ValueError("explicit tests/audit required")
    {"tests": tests, "audit": previous.audit}[sys.argv[1]](sys.argv[2])
