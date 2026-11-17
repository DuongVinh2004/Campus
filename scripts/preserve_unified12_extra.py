"""One additional preimage before the native capability projection edit."""
import hashlib
import sys
sys.dont_write_bytecode = True
from unified_ai_runtime_probe import ROOT, checked, retain

if __name__ == "__main__":
    state = checked(ROOT / "infra/local/unified-ai-20261015-12")
    source = checked(ROOT / "services/api/src/campus247/presentation/assistant_state.py")
    data = source.read_bytes()
    backup = checked(state / "assistant-state-before.snapshot")
    with backup.open("xb") as output: output.write(data)
    retain(state / "extra-preimages.json", [{"path": source.relative_to(ROOT).as_posix(), "backup": backup.name,
        "sha256": hashlib.sha256(data).hexdigest()}])
