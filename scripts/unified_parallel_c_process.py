"""C-only child process for fresh fixture contention/recovery; no runtime control."""
import argparse
from dataclasses import replace
import json
import sys
import time

sys.dont_write_bytecode = True
from unified_parallel_c_preserve import ROOT, STATE, checked, retain as c_retain
from unified_completion_scope import completion_fixture


def retain(path, value):
    path = checked(path)
    if completion_fixture(path.parent):
        with path.open('x', encoding='utf-8') as output:
            json.dump(value, output, ensure_ascii=False, indent=2)
    else:
        c_retain(path, value)


def main(mode, fixture, index):
    fixture = checked(fixture)
    if (not fixture.is_relative_to(checked(STATE / "checks")) and not completion_fixture(fixture)) or not fixture.is_dir():
        raise ValueError("exact existing C check fixture required")
    sys.path[:0] = [str(ROOT), str(ROOT / "services/api/src"), str(ROOT / "services/worker/src"), str(ROOT / "packages/synthetic/src")]
    from campus247.bootstrap.unified_demo import create_unified_demo_app
    business, actor_path = checked(fixture / "business.sqlite3"), checked(fixture / "actor.sqlite3")
    if not business.is_file() or not actor_path.is_file():
        raise ValueError("existing exact C fixture DBs required")
    if mode == "worker":
        from campus247.infrastructure.repositories.sqlite_assistant_memory import SQLiteAssistantMemory
        from campus247.infrastructure.repositories.sqlite_assistant_tracking import SQLiteAssistantTracking
        from campus247_worker.assistant_tracking.worker import AssistantTrackingWorker
        memory, tracking = checked(fixture / "personal-memory.sqlite3"), checked(fixture / "personal-tracking.sqlite3")
        if not memory.is_file() or not tracking.is_file():
            raise ValueError("existing C personal fixtures required")
        app = create_unified_demo_app(business, state_database=actor_path, consent_mode="sqlite",
            personal_memory_store=SQLiteAssistantMemory(memory), personal_tracking_store=SQLiteAssistantTracking(tracking))
        retain(fixture / ("c-worker-result-" + str(index) + ".json"), AssistantTrackingWorker(app.state.assistant_tracking).tick())
        return
    from campus247.infrastructure.identity.mock import SyntheticIdentityAdapter
    from campus247.application.assistance.case_contracts import CaseConfirm
    from campus247.application.assistance.state_storage import StorageConflict
    from campus247.application.document_request.certificates import CertificateError
    # Ephemeral confirmation token arrives through stdin only; never log/persist it.
    payload = json.loads(sys.stdin.readline())
    app = create_unified_demo_app(business, state_database=actor_path)
    adapter = SyntheticIdentityAdapter("campus247-demo-secret-key-huce", environment="development", tenant_id="huce-local-public")
    actor = adapter.resolve_token(adapter.mint_token(payload["owner"]))
    actor = replace(actor, session_id=payload["session"])
    retain(fixture / ("c-ready-" + str(index) + ".json"), {"ready": True})
    gate = checked(fixture / "c-process-gate.json")
    deadline = time.monotonic() + 15
    while not gate.exists():
        if time.monotonic() > deadline:
            raise TimeoutError("C fixture gate")
        time.sleep(.02)
    try:
        if mode == "case_confirm":
            receipt = app.state.case_workflow.confirm(actor, CaseConfirm.model_validate(payload["confirmation"]))
            result = {"state": "committed", "receipt_id": receipt["receipt_id"], "is_replay": receipt["is_replay"]}
        elif mode == "draft":
            app.state.staff_drafts.save(actor, payload["resource"], "C manual process " + str(index), 0, payload["client_id"])
            result = {"state": "committed"}
        else:
            resource = payload["resource"]
            app.state.service_requests.act(actor, resource["id"], "claim", resource["expected_version"],
                "c-process:" + payload["client_id"], "C synthetic claim contention")
            result = {"state": "committed"}
    except (CertificateError, StorageConflict) as exc:
        result = {"state": "conflict", "code": getattr(exc, "code", "STATE_CONFLICT")}
    retain(fixture / ("c-process-result-" + str(index) + ".json"), result)


if __name__ == "__main__":
    from pathlib import Path
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["case_confirm", "draft", "claim", "worker"])
    parser.add_argument("fixture", type=Path)
    parser.add_argument("index", type=int, choices=[0, 1])
    args = parser.parse_args()
    main(args.mode, args.fixture, args.index)
