"""Fresh snapshot build with the retained preservation guard unchanged."""
import sys
sys.dont_write_bytecode = True
arguments = sys.argv
sys.argv = sys.argv[:2] + ["01"]
import prepare_unified_ai_frontend08 as previous
sys.argv = arguments
from unified_ai_runtime_probe import ROOT, checked

previous.STATE = checked(ROOT / "infra/local/unified-ai-20261014-09")
previous.ATTEMPT = sys.argv[2] if len(sys.argv) == 3 else "01"
if previous.ATTEMPT not in {"01", "02", "03", "04", "05"}:
    raise ValueError("explicit fresh snapshot required")
previous.FRONTEND = checked(previous.STATE / ("frontend"+previous.ATTEMPT) / "acceptance-20261012-58-frontend-repair1-local-repair2")
previous.build_tools.STATE, previous.build_tools.FRONTEND, previous.build_tools.ATTEMPT = previous.STATE, previous.FRONTEND, previous.ATTEMPT

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) not in {2, 3} or sys.argv[1] not in {"prepare", "build"}:
        raise ValueError("explicit fresh prepare/build required")
    {"prepare": previous.build_tools.prepare, "build": previous.build_tools.build}[sys.argv[1]]()
