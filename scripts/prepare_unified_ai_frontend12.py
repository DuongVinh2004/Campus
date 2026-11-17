"""Fresh U5 source snapshot; inherited preservation guard remains byte-identical."""
import sys
sys.dont_write_bytecode = True
arguments = sys.argv
sys.argv = sys.argv[:2] + ["01"]
import prepare_unified_ai_frontend08 as previous
sys.argv = arguments
from unified_ai_runtime_probe import ROOT, checked
from unified_ai_runtime_probe import retain
import subprocess
previous.STATE = checked(ROOT / "infra/local/unified-ai-20261015-12")
previous.ATTEMPT = sys.argv[2]
if previous.ATTEMPT not in {"01", "02", "03", "04", "05"}:
    raise ValueError("fresh exact attempt required")
previous.FRONTEND = checked(previous.STATE / ("frontend" + previous.ATTEMPT) / "acceptance-20261012-58-frontend-repair1-local-repair2")
previous.build_tools.STATE, previous.build_tools.FRONTEND, previous.build_tools.ATTEMPT = previous.STATE, previous.FRONTEND, previous.ATTEMPT


def typecheck():
    output = checked(previous.STATE / ("frontend-typescript-" + previous.ATTEMPT + ".json"))
    if output.exists(): raise FileExistsError("preserve prior typecheck")
    command = [str(previous.build_tools.NODE), str(ROOT / "apps/web/node_modules/typescript/bin/tsc"),
        "--project", str(previous.FRONTEND / "tsconfig.json"), "--noEmit", "--incremental", "false"]
    result = subprocess.run(command, cwd=previous.FRONTEND, env=previous.build_tools.runtime_environment(),
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180, creationflags=0x08000000)
    retain(output, {"command": command, "exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr})
    print(result.stdout, result.stderr)
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    {"prepare": previous.build_tools.prepare, "build": previous.build_tools.build, "typecheck": typecheck}[sys.argv[1]]()
