"""Export the running local platform's OpenAPI annex to a fresh workspace file."""
import argparse
import json
from pathlib import Path

import httpx

from knowledge_platform import ROOT, checked_path
from campus247.application.knowledge.platform_models import IntakeMetadata


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    target = checked_path(args.output, ROOT)
    allowed = checked_path(ROOT / "contracts/openapi", ROOT)
    if target.parent != allowed or target.suffix != ".json":
        raise ValueError("Fresh OpenAPI annex in contracts/openapi required")
    with httpx.Client(trust_env=False, timeout=30) as client:
        response = client.get("http://127.0.0.1:8015/openapi.json")
        response.raise_for_status()
        document = response.json()
    paths = {key: value for key, value in document["paths"].items() if key.startswith("/v1/knowledge/")}
    retained = set()
    def references(value):
        if isinstance(value, dict):
            if "$ref" in value:
                name = value["$ref"].removeprefix("#/components/schemas/")
                if name not in retained:
                    retained.add(name)
                    references(document["components"]["schemas"][name])
            for item in value.values():
                references(item)
        elif isinstance(value, list):
            for item in value:
                references(item)
    references(paths)
    schemas = {name: document["components"]["schemas"][name] for name in sorted(retained)}
    schemas["IntakeMetadata"] = IntakeMetadata.model_json_schema()
    for path, methods in paths.items():
        for method, operation in methods.items():
            if not isinstance(operation, dict):
                continue
            operation["security"] = [{"bearerAuth": []}, {"cookieAuth": []}]
            if path.endswith("/local-session"):
                operation["security"] = []
                operation["description"] = "Development launcher only; loopback synthetic accounts KA01/KA02/SV01. Not production SSO."
            if method == "post" and path.endswith(("/uploads", "/applicability-versions", "/releases", "/confirmations")):
                operation.setdefault("parameters", []).append({"in": "header", "name": "Idempotency-Key", "required": True,
                    "schema": {"type": "string", "minLength": 1, "maxLength": 128}})
            if method == "post" and not path.endswith("/local-session"):
                operation["x-browser-origin-policy"] = "If Origin is supplied, it must equal the request origin."
    result = {"openapi": document["openapi"], "info": {"title": "Campus 24/7 knowledge platform local annex", "version": "2026-10-23"},
        "servers": [{"url": "http://127.0.0.1:8015"}], "paths": paths,
        "components": {"schemas": schemas, "securitySchemes": {
            "bearerAuth": {"type": "http", "scheme": "bearer"},
            "cookieAuth": {"type": "apiKey", "in": "cookie", "name": "auth_token"}}},
        "x-scope": "Actual local endpoints; all catalog/platform operations require KNOWLEDGE_ADMIN. No sync/OCR/DOCX endpoints implied.",
        "x-upload-metadata": "multipart metadata is a JSON string validated against components.schemas.IntakeMetadata; file limit 50 MiB.",
        "x-state-pagination": "Bounded state projection: 200 sources, versions and jobs; 50 sealed releases. No cursor pagination yet."}
    with target.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"output": str(target), "paths": len(paths), "schemas": len(schemas)}))


if __name__ == "__main__":
    main()
