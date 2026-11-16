"""Provision a NEW isolated synthetic learning runtime without touching existing user stores."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from learning_local_identity import ROOT, provision


def setup(directory: Path, tenant: str, fixture: Path | None = None, *, second_student: bool = False):
    hashes = []
    if fixture is not None:
        fixture = fixture.resolve(strict=True)
        if fixture.suffix.lower() != ".pdf" or not fixture.is_file():
            raise ValueError("An exact synthetic PDF fixture is required")
        with fixture.open("rb") as stream:
            hashes.append(hashlib.file_digest(stream, "sha256").hexdigest())
    result = provision(directory, tenant, second_student=second_student)
    directory = Path(result["directory"])
    blobs = directory / "blobs"
    blobs.mkdir(exist_ok=False)
    from campus247.infrastructure.learning.repository import SQLiteLearningRepository
    SQLiteLearningRepository(directory / "learning.sqlite3", workspace=ROOT, tenant_id=tenant, create=True)
    config = {"schema": "local-learning-runtime-v1", "tenant_id": tenant, "synthetic_only": True,
        "storage": "sqlite", "identity_file": "identity.json", "database_file": "learning.sqlite3",
        "blob_directory": "blobs", "synthetic_fixture_sha256": hashes}
    with (directory / "config.json").open("x", encoding="utf-8") as stream:
        json.dump(config, stream, indent=2)
    return result | {"config": str(directory / "config.json"), "fixture_count": len(hashes),
        "scanner": "synthetic_fixture_hash_allowlist" if hashes else "unavailable"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--synthetic-fixture", type=Path)
    parser.add_argument("--second-student", action="store_true")
    args = parser.parse_args()
    print(json.dumps(setup(args.directory, args.tenant, args.synthetic_fixture, second_student=args.second_student)))
