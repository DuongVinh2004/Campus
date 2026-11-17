"""Exclusive preimages and consistent read-only retained snapshots for U5."""
import sys
sys.dont_write_bytecode = True
import prepare_unified_ai_session11 as prior
from unified_ai_runtime_probe import ROOT, checked

base = prior.base
base.STATE = checked(ROOT / "infra/local/unified-ai-20261015-12")
base.SOURCES = list(dict.fromkeys([*base.SOURCES,
    "services/api/src/campus247/application/assistance/workflow.py",
    "services/api/src/campus247/application/assistance/staff_drafts.py",
    "services/api/src/campus247/presentation/staff_drafts.py",
    "services/api/src/campus247/presentation/service_operations.py",
    "services/api/src/campus247/presentation/certificates.py",
    "apps/web/src/features/assistance/StaffDraftEditor.tsx",
    "apps/web/src/features/staff/StaffTicketQueue.tsx",
    "apps/web/src/components/staff/StaffTicketWorkspace.tsx",
    "apps/web/src/components/staff/useStaffDraft.ts",
    "apps/web/src/lib/staff-policy.ts",
    "infra/local/rag-fixture/m1_source_guard_20261012_58-repair1.mjs",
]))

if __name__ == "__main__":
    prior.prior.previous.previous.main()
