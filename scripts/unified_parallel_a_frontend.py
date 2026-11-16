"""Fresh A snapshot and byte-identical existing production build guard."""
import sys
sys.dont_write_bytecode = True
arguments = sys.argv
sys.argv = [sys.argv[0], "prepare", "01"]
import prepare_unified_ai_frontend08 as previous
sys.argv = arguments
from unified_parallel_a_workspace import ROOT, STATE, checked, retain
import subprocess
number = sys.argv[2]
if number not in {"01", "02", "03", "04", "05"}: raise ValueError("exact fresh snapshot required")
previous.STATE = STATE
previous.ATTEMPT = number
previous.FRONTEND = checked(STATE / ("frontend"+number) / "acceptance-20261012-58-frontend-repair1-local-repair2")
previous.build_tools.STATE, previous.build_tools.ATTEMPT, previous.build_tools.FRONTEND = STATE, number, previous.FRONTEND

def typecheck():
    output = checked(STATE / ("frontend-typescript-"+number+".json"))
    if output.exists(): raise FileExistsError("preserve prior typecheck")
    command = [str(previous.build_tools.NODE), str(ROOT / "apps/web/node_modules/typescript/bin/tsc"),
        "--project", str(previous.FRONTEND / "tsconfig.json"), "--noEmit", "--incremental", "false"]
    result = subprocess.run(command, cwd=previous.FRONTEND, env=previous.build_tools.runtime_environment(), capture_output=True,
        text=True, encoding="utf-8", errors="replace", timeout=180, creationflags=0x08000000)
    retain(output, {"command": command, "exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr})
    sys.stdout.reconfigure(encoding="utf-8"); print(result.stdout, result.stderr)
    raise SystemExit(result.returncode)

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    {"prepare": previous.build_tools.prepare, "build": previous.build_tools.build, "typecheck": typecheck}[sys.argv[1]]()
