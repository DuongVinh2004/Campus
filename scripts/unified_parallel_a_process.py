"""New A fixture process contention; never accepts retained source DB paths."""
import json
import sys
import time
from pathlib import Path
from dataclasses import replace
sys.dont_write_bytecode = True
from unified_parallel_a_workspace import ROOT, STATE, checked, retain
from unified_completion_scope import completion_fixture
sys.path[:0] = [str(ROOT / "services/api/src"), str(ROOT / "packages/synthetic/src")]
from campus247.bootstrap.unified_demo import create_unified_demo_app
from campus247.infrastructure.identity.mock import SyntheticIdentityAdapter
from campus247.application.assistance.case_contracts import CaseConfirm

if __name__ == "__main__":
    fixture = checked(Path(sys.argv[1]))
    index = sys.argv[2]
    if (not fixture.is_relative_to(STATE) and not completion_fixture(fixture)) or index not in {"0", "1"}: raise ValueError("exact registered fixture required")
    value = json.loads((fixture / "process-input.json").read_text(encoding="utf-8"))
    app = create_unified_demo_app(fixture / "business.sqlite3", state_database=fixture / "state.sqlite3")
    adapter = SyntheticIdentityAdapter("campus247-demo-secret-key-huce", environment="development", tenant_id="huce-local-public")
    actor = replace(adapter.resolve_token(adapter.mint_token(value["owner"])), session_id=value["session"])
    retain(fixture / ("process-ready-"+index+".json"), {"ready": True})
    deadline = time.monotonic() + 15
    while not (fixture / "process-gate.json").exists():
        if time.monotonic() > deadline: raise TimeoutError("fixture start gate")
        time.sleep(.02)
    result = app.state.case_workflow.confirm(actor, CaseConfirm.model_validate(value["confirmation"]))
    retain(fixture / ("process-result-"+index+".json"), {"receipt_id": result["receipt_id"], "is_replay": result["is_replay"], "version": result["resource"]["version"]})
