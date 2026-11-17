"""Build an exclusive UI snapshot; keep the previous guard and build intact."""
import sys
import prepare_unified_ai_session02 as prior
from unified_ai_runtime_probe import ROOT, checked, retain

STATE = checked(ROOT / "infra/local/unified-ai-20261014-03")
FRONTEND = checked(STATE / "frontend01/acceptance-20261012-58-frontend-repair1-local-repair2")
tools = prior.build_tools
tools.STATE, tools.ATTEMPT, tools.FRONTEND = STATE, "01", FRONTEND


def environment():
    return {**prior.environment(), "NEXT_PUBLIC_UNIFIED_WORKFLOW": "true"}


tools.runtime_environment = environment
tools.retain = retain


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) != 2 or sys.argv[1] not in {"prepare", "build"}:
        raise ValueError("explicit prepare/build command required")
    {"prepare": tools.prepare, "build": tools.build}[sys.argv[1]]()
