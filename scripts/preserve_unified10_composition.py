"""Exclusive graph preimage for the final scoped multi-agent capability repair."""
import hashlib
from unified_ai_runtime_probe import ROOT, checked, retain

if __name__ == "__main__":
    state = checked(ROOT / "infra/local/unified-ai-20261015-10")
    source = checked(ROOT / "services/api/src/campus247/agent/graph.py")
    target = checked(state / "source-composition-01.snapshot")
    data = source.read_bytes()
    with target.open("xb") as stream:
        stream.write(data)
    retain(state / "composition-preimages.json", [{"path": source.relative_to(ROOT).as_posix(),
        "backup": target.name, "sha256": hashlib.sha256(data).hexdigest()}])
