"""Fresh candidate build with the existing preservation guard unchanged."""
import sys

import prepare_certificate_frontend as build_tools
from unified_ai_runtime_probe import ROOT, checked, retain

STATE = checked(ROOT / "infra/local/unified-ai-20261014-07")
FRONTEND = checked(STATE / "frontend01/acceptance-20261012-58-frontend-repair1-local-repair2")
build_tools.STATE,build_tools.ATTEMPT,build_tools.FRONTEND = STATE,"01",FRONTEND
original = build_tools.runtime_environment


def environment():
    return {**original(),"NEXT_PUBLIC_API_URL":"http://localhost:8006","NEXT_PUBLIC_SERVICE_DEMO":"true",
        "NEXT_PUBLIC_MULTI_AGENT":"true","NEXT_PUBLIC_UNIFIED_AI":"true","NEXT_PUBLIC_UNIFIED_WORKFLOW":"true",
        "NEXT_PUBLIC_UNIFIED_DURABLE_DRAFTS":"true"}


build_tools.runtime_environment = environment
build_tools.retain = retain

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) != 2 or sys.argv[1] not in {"prepare","build"}:raise ValueError("explicit fresh prepare/build required")
    {"prepare":build_tools.prepare,"build":build_tools.build}[sys.argv[1]]()
