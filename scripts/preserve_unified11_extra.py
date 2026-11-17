"""Preserve exact additional U4 route sources before scoped patches."""
import hashlib
import subprocess
from unified_ai_runtime_probe import ROOT, checked, retain

STATE = checked(ROOT / "infra/local/unified-ai-20261015-11")
names = ["apps/web/src/app/schedule/page.tsx", "apps/web/src/app/rooms/page.tsx"]
if __name__ == "__main__":
    status = subprocess.run(["git", "status", "--porcelain=v1"], cwd=ROOT, capture_output=True, text=True, check=True)
    rows = []
    for index, name in enumerate(names):
        source = checked(ROOT / name)
        data = source.read_bytes()
        target = checked(STATE / f"extra-before-{index:02d}.snapshot")
        with target.open("xb") as stream:
            stream.write(data)
        rows.append({"path": name, "backup": target.name, "sha256": hashlib.sha256(data).hexdigest()})
    retain(STATE / "extra-preimages.json", rows)
    retain(STATE / "extra-status.json", {"status": status.stdout, "warnings": status.stderr})
