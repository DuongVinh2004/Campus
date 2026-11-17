"""Fresh session02 build with the existing preservation guard unchanged."""
import sys

from unified_ai_runtime_probe import ROOT, checked, retain
from unified_ai_session02_preflight import STATE
import prepare_certificate_frontend as build_tools

ordinal = "03" if len(sys.argv) == 2 and sys.argv[1] in {"prepare03","build03"} else "02" if len(sys.argv) == 2 and sys.argv[1] in {"prepare02","build02"} else "01"
FRONTEND = STATE / ("frontend"+ordinal) / "acceptance-20261012-58-frontend-repair1-local-repair2"
build_tools.STATE, build_tools.ATTEMPT, build_tools.FRONTEND = STATE, ordinal, FRONTEND
original = build_tools.runtime_environment


def environment():
    return {**original(),"NEXT_PUBLIC_API_URL":"http://localhost:8006","NEXT_PUBLIC_SERVICE_DEMO":"true",
            "NEXT_PUBLIC_MULTI_AGENT":"true","NEXT_PUBLIC_UNIFIED_AI":"true"}


build_tools.runtime_environment = environment
build_tools.retain = lambda path,value: retain(path,value)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) != 2 or sys.argv[1] not in {"prepare","build","prepare02","build02","prepare03","build03"}:
        raise ValueError("explicit fresh prepare/build command required")
    {"prepare":build_tools.prepare,"build":build_tools.build,"prepare02":build_tools.prepare,"build02":build_tools.build,"prepare03":build_tools.prepare,"build03":build_tools.build}[sys.argv[1]]()
