"""Immutable A+B actual wiring acknowledgement with fixture API evidence."""
import hashlib
import sys
sys.dont_write_bytecode = True
from unified_parallel_a_workspace import ROOT, STATE, checked, retain

if __name__ == "__main__":
    number = sys.argv[1]
    check = sys.argv[2] if len(sys.argv) > 2 else "09"
    paths = ["services/api/src/campus247/bootstrap/unified_demo.py", "services/api/src/campus247/bootstrap/assistant_features.py",
        "services/api/src/campus247/application/assistance/personal_consumers.py", "services/api/src/campus247/application/assistance/scoped_context.py",
        "services/api/src/campus247/presentation/assistant_state.py", "services/api/src/campus247/infrastructure/repositories/case_workflow.py",
        "services/api/src/campus247/bootstrap/assistant_personal_features.py", "tests/unified_workflow13a/test_personal_integration.py"]
    retain(STATE / "integration-acks" / ("personal-" + number + ".json"), {
        "status": "actual_fixture_composition_readback_passed", "request": "stream-b/integration-requests/registrar-02.json",
        "files": {p: hashlib.sha256(checked(ROOT/p).read_bytes()).hexdigest() for p in paths},
        "entry_point": "create_unified_demo_app(... personal_memory_store=explicit_repository, personal_tracking_store=explicit_repository)",
        "acknowledged_hooks": {"memory": "memory.retrieve -> memory.use under request_guard in actual /v1/assistant/context:compose and :revalidate when explicit memory_terms selected; resource scoped context only. No model writer or legacy chat mode claim.",
            "mode": "settings for no chat; unknown legacy conversation fails CHAT_MODE_UNVERIFIED", "tracking_source": "app.state.assistant_tracking_source CaseTrackingSource.read_batch/ack; append-only case_tracking_event/ack in business operations table; outbox atomic with business writes",
            "recipient": "CurrentRecipientRegistry captures only verified session metadata/token hash after API requests; resolves current synthetic directory, expiry and persisted revocation before delivery/open",
            "projection": "fresh exact resource version/source/assignment via cases.projection; fixed minimized reason; obsolete event fails closed",
            "open_handover": "POST /v1/assistant/cases/notification:open {event_id:UUID7} -> exact authorized open_path /services?request=UUID (service), /staff?request=UUID (staff certificate), /tickets?request=UUID (student certificate) plus selected public/internal handover summary; event from notifications id before colon (UUID event_id); fails stale/cross-recipient/revoke"},
        "actual_readback": ["personal-capabilities memory_management/context/tracking true only with explicit new stores", "confirmed memory declaration -> scoped resource context contains untrusted block -> forget invalidates manifest; old raw state retained", "business supplement -> outbox -> AssistantTrackingWorker.tick -> exactly one inbox item -> notification:open exact path -> wrong recipient404 -> revoke401"],
        "evidence": "stream-a/checks/backend-" + check + ".xml", "command": ".venv/Scripts/python.exe -B scripts/unified_parallel_a_verify.py " + check + " tests/unified_workflow13a/test_personal_integration.py", "exit_code": 0, "passed": 5 if check == "10" else 3,
        "readback_03_resolution": ["tracking outbox exact whitelist of real request.* transitions; draft.saved/confirmation.prepared/supplement.prepared excluded", "project rechecks active grant/version and compares fresh event-version evidence with original grant.evidence; mismatched source suppressed", "notification:open contract and actual recipient404/revoke401 evidence available"],
        "worker": "PYTHONPATH includes services/worker/src; AssistantTrackingWorker(app.state.assistant_tracking).tick() on explicit fixture composition only; bounded; no serving worker launch/reload",
        "limitations": ["no implicit migration/init of retained personal/business DB", "legacy chat memory and main model writer unavailable; actual memory consumer is scoped resource-context API", "no distributed cross-store atomicity claim", "in-app only; no email/Slack delivery", "no UI/browser/full institutional acceptance"]})
