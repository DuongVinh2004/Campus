"""Exclusive additional preimages before editing existing source boundaries."""
import hashlib
from unified_ai_runtime_probe import ROOT, checked, retain

STATE = checked(ROOT / "infra/local/unified-ai-20261015-10")
SOURCES = ["services/api/src/campus247/application/assistance/state_storage.py",
           "services/api/src/campus247/application/assistance/durable_services.py",
           "apps/web/src/features/chat/sse.ts", "apps/web/src/features/chat/ChatPanel.tsx",
           "tests/unit/agent/test_multi_agent_integrated.py"]

if __name__ == "__main__":
    records = []
    for i, name in enumerate(SOURCES):
        source, target = checked(ROOT / name), checked(STATE / f"source-extra-{i:02d}.snapshot")
        data = source.read_bytes()
        with target.open("xb") as stream:
            stream.write(data)
        records.append({"path": name, "backup": target.name, "sha256": hashlib.sha256(data).hexdigest()})
    retain(STATE / "extra-preimages.json", records)
