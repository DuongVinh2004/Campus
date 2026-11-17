"""Export the new contract pack without touching retained context-v1 schemas."""
import json
import sys

from unified_ai_runtime_probe import ROOT, checked, retain
from unified_ai_session02_preflight import STATE

sys.path.insert(0,str(ROOT / "services/api/src"))
from campus247.application.assistance.unified_contracts import CONTRACT_MODELS
from campus247.application.assistance.baseline import BaselineStart, BaselineEvent


if __name__ == "__main__":
    destination = checked(ROOT / "contracts/json-schema/assistance/unified-core-v1")
    destination.mkdir(exist_ok=False)
    models = {**CONTRACT_MODELS,"BaselineStart":BaselineStart,"BaselineEvent":BaselineEvent}
    for name, model in models.items():
        with checked(destination / (name+".schema.json")).open("x",encoding="utf-8") as stream:
            json.dump({"$schema":"https://json-schema.org/draft/2020-12/schema",**model.model_json_schema()},stream,ensure_ascii=False,indent=2)
    retain(STATE / "contract-export-01.json",{"directory":str(destination),"models":sorted(models),"existing_context_contracts_preserved":True})
