"""Fresh build copy; the established preservation guard is copied unchanged."""
import sys

from multi_agent_workspace import ROOT, STATE, checked

# Existing preparation code writes exclusively into a fresh scoped directory.
# Reuse it with a new output namespace, not a modified protection mechanism.
import prepare_certificate_frontend as build_tools

attempt = sys.argv[2] if len(sys.argv) > 2 else "01"
if attempt not in {"01", "02", "03"}:
    raise ValueError("explicit fresh build attempt required")
build_tools.STATE = STATE
build_tools.ATTEMPT = attempt
build_tools.FRONTEND = STATE / ("frontend"+attempt) / "acceptance-20261012-58-frontend-repair1-local-repair2"
original_environment = build_tools.runtime_environment
def environment():
    return {**original_environment(), "NEXT_PUBLIC_API_URL": "http://localhost:8003", "NEXT_PUBLIC_MULTI_AGENT": "true"}
build_tools.runtime_environment = environment
build_tools.retain = __import__("multi_agent_workspace").retain

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    {"prepare": build_tools.prepare, "build": build_tools.build}[sys.argv[1]]()
