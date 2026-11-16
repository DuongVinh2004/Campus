"""Immutable exact source contracts and milestone handoffs for B/C."""
import hashlib
import sys
import xml.etree.ElementTree as ET
sys.dont_write_bytecode = True
from unified_parallel_a_workspace import ROOT, STATE, SOURCES, checked, retain

NEW_SOURCE = ["services/api/src/campus247/application/assistance/case_contracts.py",
    "services/api/src/campus247/application/assistance/case_workflow.py",
    "services/api/src/campus247/infrastructure/repositories/case_workflow.py",
    "services/api/src/campus247/presentation/case_workflow.py",
    "services/api/src/campus247/application/assistance/personal_consumers.py",
    "services/api/src/campus247/application/assistance/scoped_context.py",
    "services/api/src/campus247/presentation/assistant_state.py",
    "apps/web/src/features/assistance/ResourceAssistant.tsx",
    "apps/web/src/features/assistance/CaseWorkflowPanel.tsx",
    "apps/web/src/features/assistance/CaseSupplementPanel.tsx",
    "apps/web/src/features/assistance/CaseProjectionPanel.tsx",
    "apps/web/src/features/assistance/StaffCaseInsights.tsx"]

def handoff(name, check):
    xml = checked(STATE / "checks" / check)
    cases = list(ET.parse(xml).getroot().iter("testcase"))
    failed = [c.get("name") for c in cases if c.find("failure") is not None or c.find("error") is not None]
    if failed:
        raise ValueError("milestone requires corresponding passing checks")
    files = sorted(set(p for p in [*SOURCES, *NEW_SOURCE] if checked(ROOT / p).is_file()))
    files += [str(p.relative_to(ROOT)).replace("\\", "/") for p in (ROOT / "tests/unified_workflow13a").rglob("*.py")]
    files += [str(p.relative_to(ROOT)).replace("\\", "/") for p in (ROOT / "contracts/json-schema/assistance/cases-v13-02").glob("*.json")]
    final = name.startswith("final")
    task_ids = ["UNI-"+str(n).zfill(3) for n in range(31,39)] if final else ["UNI-"+name[3:6]]
    retain(STATE / "handoffs" / (name + ".json"), {"milestone": name, "files": {p: hashlib.sha256(checked(ROOT/p).read_bytes()).hexdigest() for p in files},
        "task_ids": task_ids, "implementation": "local_synthetic_source_consumers_connected_full_acceptance_pending",
        "source_stable_for_C": final,
        "entry_point": "campus247.bootstrap.unified_demo.create_unified_demo_app -> app.state.case_workflow",
        "contracts": "campus247.application.assistance.case_contracts; /v1/assistant/cases/*",
        "transactional_event_hook": "CertificateService._event -> business_event_sink -> CaseWorkflowRepository.event; generic service_operations_record kind case_event; both service/certificate business transactions",
        "event_fields": ["id", "tenant", "resource_id", "resource_kind", "student_id", "queue", "assigned_actor", "version", "status", "action", "occurred_at", "invalidate"],
        "readback": "POST cases/projection:read and events:read require exact resource version/current session; staff assignment and student ownership remain checked",
        "checks": {"evidence": str(xml.relative_to(ROOT)), "unique": len(cases), "failed": failed, "exit_code": 0},
        "verification_summary": {"broad_backend": "backend-11.xml:352 passed/2 historical namespace probes deselected; own process contention passed", "final_affected": "backend-14.xml:79 passed", "baseline_failure": "backend-13.xml: existing 50ms reservation/model.calls mismatch remains; controls/assertions unchanged", "frontend": "frontend-typescript-02.json exit0; frontend-build-02.json exit0; BUILD_ID e1lwvBfjk0xQXu-gPwJrW; guard byte-identical", "integration_ack": "stream-a/integration-acks/personal-03.json; backend-14 includes latest integration and certificate staff-route checks"},
        "limitations": ["local/synthetic only; official rules/templates/eligibility remain unverified", "UI source connected; UI/browser acceptance not run", "final C combined snapshot/acceptance pending", "baseline deadline50ms unresolved; no fully green backend release gate", "no serving runtime reload, provider or production calls", "memory uses explicit stores/scoped-context API only; legacy chat/model writer memory unavailable; no distributed atomicity claim"],
        "next_consumers": ["B: tracking source adapter over exact authorized case projections/events; no private draft/memory in feed", "C: fresh final snapshot after final handoff"]})

if __name__ == "__main__":
    handoff(sys.argv[1], sys.argv[2])
