"""Fresh graph UI copy with the existing preservation guard copied byte-for-byte."""
import sys
from build_policy_graph import ROOT, STATE
from certificate_stage1_workspace import checked
import prepare_certificate_frontend as build_tools

build_tools.STATE = STATE
build_tools.ATTEMPT = "01"
build_tools.FRONTEND = STATE / "frontend01" / "acceptance-20261012-58-frontend-repair1-local-repair2"
original_environment = build_tools.runtime_environment
def environment():
    return {**original_environment(), "NEXT_PUBLIC_API_URL": "http://localhost:8003", "NEXT_PUBLIC_MULTI_AGENT": "true"}
def retain(path, value):
    import json
    with checked(path, STATE).open("x", encoding="utf-8") as out:
        json.dump(value, out, indent=2, ensure_ascii=False)
build_tools.runtime_environment = environment
build_tools.retain = retain
if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    {"prepare": build_tools.prepare, "build": build_tools.build}[sys.argv[1]]()
