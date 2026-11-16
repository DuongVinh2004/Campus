"""Fresh stage6 copy/build, with the prior preservation guard unchanged."""
import sys
from service_stage6_workspace import ROOT, STATE
from certificate_stage1_workspace import checked
import prepare_certificate_frontend as build_tools

ordinal = sys.argv[2] if len(sys.argv) > 2 else "01"
if ordinal not in {"01", "02", "03"}:
    raise ValueError("explicit fresh build ordinal required")
build_tools.STATE = STATE
build_tools.ATTEMPT = ordinal
build_tools.FRONTEND = STATE / ("frontend" + ordinal) / "acceptance-20261012-58-frontend-repair1-local-repair2"
original_environment = build_tools.runtime_environment


def environment():
    return {**original_environment(), "NEXT_PUBLIC_API_URL": "http://localhost:8004",
        "NEXT_PUBLIC_SERVICE_DEMO": "true", "NEXT_PUBLIC_MULTI_AGENT": "true"}


def retain(path, value):
    import json
    with checked(path, STATE).open("x", encoding="utf-8") as out:
        json.dump(value, out, ensure_ascii=False, indent=2)


build_tools.runtime_environment, build_tools.retain = environment, retain
if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    {"prepare": build_tools.prepare, "build": build_tools.build}[sys.argv[1]]()
