"""Exclusive export of the UNI-004 context slice, preserving old contracts."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services/api/src"))
from campus247.application.assistance.contracts import AssistanceRequest, AssistanceResponse
from unified_ai_runtime_probe import checked

DESTINATION = ROOT / "contracts/json-schema/assistance/unified-context-v1"


if __name__ == "__main__":
    checked(DESTINATION).mkdir(parents=True, exist_ok=False)
    for name, model in [("request.schema.json", AssistanceRequest), ("response.schema.json", AssistanceResponse)]:
        schema = {"$schema": "https://json-schema.org/draft/2020-12/schema", **model.model_json_schema()}
        with checked(DESTINATION / name).open("x", encoding="utf-8") as stream:
            json.dump(schema, stream, ensure_ascii=False, indent=2)
