"""Exclusive preimages for two additional existing integration boundaries."""
import hashlib
from unified_ai_runtime_probe import ROOT, checked, retain

STATE = checked(ROOT / "infra/local/unified-ai-20261014-09")
SOURCES = ["services/api/src/campus247/bootstrap/certificate_demo.py",
           "services/api/src/campus247/presentation/held_history.py"]

if __name__ == "__main__":
    output = checked(STATE / "extra-preimages.json")
    if output.exists():
        raise FileExistsError("retain prior preimages")
    records = []
    for i, name in enumerate(SOURCES):
        source, target = checked(ROOT / name), checked(STATE / f"source-extra-{i:02d}.snapshot")
        data = source.read_bytes()
        with target.open("xb") as stream:
            stream.write(data)
        records.append({"path": name, "backup": target.name, "sha256": hashlib.sha256(data).hexdigest()})
    retain(output, records)
