"""Exclusive session02 evidence, exact source backups and read-only DB backup."""
import hashlib
import json
import sqlite3
import subprocess

from unified_ai_runtime_probe import ROOT, checked, retain

STATE = ROOT / "infra/local/unified-ai-20261014-02"
FILES = [
    "docs/UNIFIED_AI_IMPLEMENTATION_BACKLOG_20261014.json",
    "docs/UNIFIED_AI_IMPLEMENTATION_PLAN_20261014.md",
    "services/api/src/campus247/bootstrap/unified_demo.py",
    "services/api/src/campus247/bootstrap/certificate_demo.py",
    "services/api/src/campus247/presentation/assistance.py",
    "services/api/src/campus247/application/assistance/contracts.py",
    "apps/web/src/features/documents/ServiceWorkspace.tsx",
    "scripts/unified_ai_candidate.py",
]


if __name__ == "__main__":
    checked(STATE).mkdir(exist_ok=False)
    files = []
    for index, relative in enumerate(FILES):
        source = checked(ROOT / relative)
        content = source.read_bytes()
        backup = checked(STATE / f"source-before-{index:02d}.txt")
        with backup.open("xb") as stream:
            stream.write(content)
        files.append({"path":relative, "backup":backup.name, "sha256":hashlib.sha256(content).hexdigest()})
    database = checked(ROOT / "infra/local/unified-ai-20261014-01/business-candidate01.sqlite3")
    backup = checked(STATE / "business-before-01.sqlite3")
    with backup.open("xb"):
        pass
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as source:
        with sqlite3.connect(backup) as destination:
            source.backup(destination)
    status = subprocess.run(["git", "status", "--porcelain=v1"], cwd=ROOT, capture_output=True,
                            text=True, encoding="utf-8", errors="replace")
    retain(STATE / "preflight-01.json", {"source_backups":files, "database":str(database),
        "database_backup":backup.name, "git_status":status.stdout, "git_warnings":status.stderr,
        "git_exit_code":status.returncode, "prior_session_preserved":True})
    print(str(STATE))
