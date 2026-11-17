"""Exclusive U4 input schemas; no authority or model execution tools."""
import sys
sys.dont_write_bytecode = True
from unified_ai_runtime_probe import ROOT, checked, retain
sys.path.insert(0, str(checked(ROOT / "services/api/src")))
from campus247.application.document_request.student_preparation import StudentGoal, SavePreparedDraft

if __name__ == "__main__":
    folder = checked(ROOT / "contracts/json-schema/assistance/student-v1-01")
    folder.mkdir(exist_ok=False)
    records = []
    for model in (StudentGoal, SavePreparedDraft):
        destination = checked(folder / (model.__name__ + ".json"))
        retain(destination, model.model_json_schema())
        records.append(str(destination.relative_to(ROOT)))
    retain(checked(ROOT / "infra/local/unified-ai-20261015-11/contracts-01.json"), {"contracts": records})
