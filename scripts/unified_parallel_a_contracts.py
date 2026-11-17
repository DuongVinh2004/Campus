import sys
sys.dont_write_bytecode = True
from unified_parallel_a_workspace import ROOT, STATE, checked, retain
sys.path[:0] = [str(ROOT / "services/api/src"), str(ROOT / "packages/synthetic/src")]
from campus247.application.assistance import case_contracts
from campus247.application.assistance.scoped_context import ContextRequest

NAMES = ["SupplementItem", "HandoverSummary", "CaseDraftPrepare", "CaseDraftRead", "CaseDraftPreview", "CaseConfirm",
    "ReceiptRead", "ItemResponse", "SupplementResponse", "StaffIntent", "BatchPrepare", "BatchConfirm", "QueueRead", "NotificationOpen"]

if __name__ == "__main__":
    number = sys.argv[1] if len(sys.argv) > 1 else "01"
    if len(number) != 2 or not number.isdigit(): raise ValueError("exact version required")
    folder = checked(ROOT / ("contracts/json-schema/assistance/cases-v13-" + number))
    folder.mkdir(exist_ok=False)
    for name in NAMES:
        retain(folder / (name + ".schema.json"), getattr(case_contracts, name).model_json_schema())
    retain(folder / "ContextRequest.schema.json", ContextRequest.model_json_schema())
    retain(STATE / ("contracts-" + number + ".json"), {"models": NAMES + ["ContextRequest"], "directory": str(folder.relative_to(ROOT)), "exact_model_schema": True})
