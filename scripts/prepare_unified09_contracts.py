"""Export new schemas exclusively; preserve every existing contract artifact."""
import json
import sys
from unified_ai_runtime_probe import ROOT, checked, retain
sys.path[:0] = [str(ROOT / "services/api/src"), str(ROOT / "packages/synthetic/src")]
from campus247.application.assistance.consumer_contracts import AssistantDisplayContent
from campus247.presentation.assistant_state import SurfaceBody, MetadataBody
from campus247.presentation.chat import CreateMessagePayload, CreateConversationPayload

MODELS = (AssistantDisplayContent, SurfaceBody, MetadataBody, CreateMessagePayload, CreateConversationPayload)

if __name__ == "__main__":
    destination = checked(ROOT / "contracts/json-schema/assistance/unified-consumers-v1")
    destination.mkdir(exist_ok=False)
    for model in MODELS:
        path = checked(destination / (model.__name__+".schema.json"))
        with path.open("x", encoding="utf-8") as output:
            output.write(json.dumps(model.model_json_schema(), ensure_ascii=False, indent=2)+"\n")
    retain(ROOT / "infra/local/unified-ai-20261014-09/contracts-01.json", {"models": [m.__name__ for m in MODELS], "exit_code": 0, "method": "exclusive schema export"})
