"""Exclusive-create exact schema artifacts; no overwrite of earlier contracts."""
import sys
sys.dont_write_bytecode = True
from unified_ai_runtime_probe import ROOT, checked, retain
sys.path[:0] = [str(checked(ROOT / "services/api/src")), str(checked(ROOT / "packages/synthetic/src"))]
from campus247.application.assistance.staff_contracts import StaffRead, StaffReview, StaffSourceRead, StaffDossier

if __name__ == "__main__":
    folder = checked(ROOT / "contracts/json-schema/assistance/staff-v1-01")
    folder.mkdir(exist_ok=False)
    for model in (StaffRead, StaffReview, StaffSourceRead, StaffDossier):
        retain(checked(folder / (model.__name__ + ".json")), model.model_json_schema())
    retain(checked(ROOT / "infra/local/unified-ai-20261015-12/contracts-01.json"), {"schemas": 4, "exact_model_schema": True})
