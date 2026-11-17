"""Export exact Pydantic coordination schemas into a new exclusive pack."""
import sys
import json
sys.dont_write_bytecode = True
from unified_ai_runtime_probe import ROOT, checked, retain
sys.path.insert(0, str(checked(ROOT / "services/api/src")))
from campus247.application.multi_agent.contracts import (
    CoordinationBinding, TaskBinding, TaskSpec, TaskResult, ControllerCheckpoint, ContinuationCheckpoint,
)
from campus247.application.multi_agent.service_adapter import ResourceSpecialistResult, ResourceRunMetadata

if __name__ == "__main__":
    number = sys.argv[1] if len(sys.argv) == 2 else "01"
    if number not in {"01", "02", "03"}:
        raise ValueError("fresh exact contract attempt required")
    folder = checked(ROOT / ("contracts/json-schema/assistance/coordination-v1" if number == "01" else "contracts/json-schema/assistance/coordination-v1-" + number))
    folder.mkdir(exist_ok=False)
    records = []
    for contract in (CoordinationBinding, TaskBinding, TaskSpec, TaskResult, ControllerCheckpoint, ContinuationCheckpoint, ResourceSpecialistResult, ResourceRunMetadata):
        schema = contract.model_json_schema()
        destination = checked(folder / (contract.__name__ + ".schema.json"))
        retain(destination, schema)
        records.append({"contract": contract.__name__, "path": str(destination.relative_to(ROOT))})
    retain(checked(ROOT / ("infra/local/unified-ai-20261015-10/contracts-" + number + ".json")), {"contracts": records, "schema_source": "pydantic", "authority": "none"})
    print(json.dumps(records))
