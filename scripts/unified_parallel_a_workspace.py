"""Chat A: exclusive evidence/preimages, read-only retained row digests."""
import hashlib
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "infra/local/unified-ai-parallel-20261015-01/stream-a"
SOURCES = [
    "services/api/src/campus247/bootstrap/unified_demo.py",
    "services/api/src/campus247/bootstrap/assistant_features.py",
    "services/api/src/campus247/application/document_request/certificates.py",
    "services/api/src/campus247/application/document_request/service_requests.py",
    "apps/web/src/features/documents/ServiceWorkspace.tsx",
    "apps/web/src/features/documents/CertificateWorkspace.tsx",
    "apps/web/src/lib/unified-assistant-runtime.tsx",
    "apps/web/src/lib/assistant-state-service.ts",
]
DATABASES = ["infra/local/unified-ai-20261014-01/business-candidate01.sqlite3",
    "infra/local/unified-ai-20261014-05/actor-state.sqlite3",
    "infra/local/public-rag-20261013/conversations.sqlite3",
    "infra/local/multi-agent-integrated-20261013-01/agent-runs.sqlite3"]

def checked(path):
    resolved = path.resolve()
    if resolved == ROOT or not resolved.is_relative_to(ROOT):
        raise ValueError("exact workspace descendant required")
    for part in [path, *path.parents]:
        if part == ROOT.parent:
            break
        if part.exists() and (part.is_symlink() or part.is_junction() or getattr(part.stat(), "st_file_attributes", 0) & 0x400):
            raise ValueError("reparse destination denied")
    return resolved

def write(path, data):
    path = checked(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(data)

def retain(path, value):
    write(path, json.dumps(value, ensure_ascii=False, indent=2).encode())

def database_digests():
    result = {}
    for name in DATABASES:
        path = checked(ROOT / name)
        if not path.exists():
            result[name] = None
            continue
        with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as connection:
            connection.execute("BEGIN")
            rows = []
            for table, sql in connection.execute("SELECT name,sql FROM sqlite_master WHERE type='table' ORDER BY name"):
                quoted = '"' + table.replace('"', '""') + '"'
                hashes = sorted(hashlib.sha256(repr(row).encode()).hexdigest() for row in connection.execute("SELECT * FROM " + quoted))
                rows.append({"table": table, "schema": sql, "rows": len(hashes), "sha256": hashlib.sha256(json.dumps(hashes).encode()).hexdigest()})
            result[name] = rows
    return result

def main():
    checked(STATE).mkdir(exist_ok=False)
    for name in ["handoffs", "integration-acks", "preimages", "checks"]:
        checked(STATE / name).mkdir()
    git = subprocess.run(["git", "status", "--porcelain=v1"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    preimages = []
    for name in SOURCES:
        path = checked(ROOT / name)
        data = path.read_bytes()
        write(STATE / "preimages" / name, data)
        preimages.append({"path": name, "sha256": hashlib.sha256(data).hexdigest()})
    retain(STATE / "preflight-01.json", {"workspace": str(ROOT), "git": git.stdout, "git_warnings": git.stderr,
        "preimages": preimages, "retained_databases": database_digests()})
    print(str(STATE / "preflight-01.json"))

if __name__ == "__main__":
    main()
