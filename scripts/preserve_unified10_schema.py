"""Retain the exact pre-existing schema before its single-field patch."""
import hashlib
from unified_ai_runtime_probe import ROOT, checked, retain

if __name__ == "__main__":
    state = checked(ROOT / "infra/local/unified-ai-20261015-10")
    source = checked(ROOT / "contracts/json-schema/assistance/unified-consumers-v1/SurfaceBody.schema.json")
    target = checked(state / "source-schema-01.snapshot")
    data = source.read_bytes()
    with target.open("xb") as stream:
        stream.write(data)
    retain(state / "schema-preimages.json", [{"path": source.relative_to(ROOT).as_posix(),
        "backup": target.name, "sha256": hashlib.sha256(data).hexdigest()}])
