"""Optional portable PostgreSQL acquisition in a new workspace-only directory.

No installer, service registration, old database access or system configuration.
The two URLs are publisher endpoints; HTTPS validation stays enabled. Receipts
record downloaded hashes, not a claim of independent publisher checksum review.
"""
from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services/api/src"))
from campus247.infrastructure.knowledge.storage import checked_path

DEST = checked_path(ROOT / ".tooling/knowledge-postgres-20261023", ROOT)
SOURCES = {
    "postgres.zip": "https://sbp.enterprisedb.com/getfile.jsp?fileid=1260616",
    "pgvector.zip": "https://github.com/pgvector/pgvector/archive/refs/tags/v0.8.7.zip",
}


def main():
    if DEST.exists():
        raise ValueError("Fresh acquisition directory required; existing downloads are preserved")
    DEST.mkdir()
    receipts = []
    for name, url in SOURCES.items():
        archive = checked_path(DEST / name, ROOT)
        checksum, size = hashlib.sha256(), 0
        with httpx.stream("GET", url, follow_redirects=True, timeout=60, trust_env=False) as response:
            response.raise_for_status()
            with archive.open("xb") as stream:
                for chunk in response.iter_bytes(1024*1024):
                    size += len(chunk)
                    if size > 1024**3:
                        raise ValueError("Acquisition exceeds 1 GiB archive limit")
                    checksum.update(chunk)
                    stream.write(chunk)
        print(json.dumps({"downloaded": name, "bytes": size}), flush=True)
        receipts.append({"url": url, "sha256": checksum.hexdigest(), "bytes": size})
        with zipfile.ZipFile(archive) as zipped:
            for info in zipped.infolist():
                relative = Path(info.filename)
                if relative.is_absolute() or ".." in relative.parts or info.file_size > 256*1024**2:
                    raise ValueError("Archive path/size rejected")
                if name == "postgres.zip" and not info.filename.startswith(("pgsql/bin/", "pgsql/lib/", "pgsql/share/", "pgsql/include/")):
                    continue
                target = checked_path(DEST / relative, ROOT)
                if (info.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ValueError("Archive symlink rejected")
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with zipped.open(info) as source, target.open("xb") as output:
                        while data := source.read(1024*1024):
                            output.write(data)
        with checked_path(DEST / (name + ".receipt.json"), ROOT).open("x", encoding="utf-8") as stream:
            json.dump(receipts[-1], stream, indent=2)
    print(json.dumps({"ready_for_build": str(DEST), "system_configuration_changed": False}), flush=True)


if __name__ == "__main__":
    main()
