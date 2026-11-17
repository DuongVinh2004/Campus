"""Host read-only runtime observations, with no dispatch or process mutation."""
import json
from unified_ai_runtime_probe import ROOT, checked, retain, http
from prepare_unified_ai_session08 import listener_inventory

if __name__ == "__main__":
    state=checked(ROOT/"infra/local/unified-ai-20261014-09")
    prior=json.loads((ROOT/"infra/local/unified-ai-20261014-08/session-verification-02.json").read_text(encoding="utf-8"))
    observed={str(port):http(port,"/v1/assistant/runtime" if port==8006 else "/health/live") for port in (8006,8003)}
    value={"runtime":observed,"listeners":listener_inventory(),"prior_session_runtime":prior["runtime_after"],
           "method":"GET runtime/health and netstat only; no auth/model/business requests", "runtime_transition":False}
    retain(state/"host-runtime-read-01.json",value)
    print(json.dumps(value,ensure_ascii=False))
