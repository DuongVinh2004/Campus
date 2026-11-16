"""Exclusive evidence files and canonical scope for the current synthetic task."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "infra/local/certificate-stage1-20261013-01"


def checked(path: Path, scope: Path = ROOT) -> Path:
    path, scope = path.absolute(), scope.resolve()
    resolved = path.resolve()
    if resolved == scope or not resolved.is_relative_to(scope):
        raise ValueError("exact child workspace destination required")
    for parent in (path, *path.parents):
        if parent.exists() and (parent.is_symlink() or parent.is_junction()
                                or getattr(parent.stat(), "st_file_attributes", 0) & 0x400):
            raise ValueError("reparse target denied")
        if parent == ROOT:
            break
    return resolved


def retain(path, value):
    with checked(path, STATE).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)


def initialize():
    checked(STATE).mkdir(exist_ok=False)
    result = subprocess.run(["git", "status", "--porcelain=v1"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    retain(STATE / "initial-discovery.json", {"workspace": str(ROOT), "git_status_exit": result.returncode,
        "git_status_at_evidence_capture": result.stdout, "warnings": result.stderr,
        "note": "Capture after initial scoped backend patches; initial pre-edit status is retained in the chat and inventory. All pre-existing dirty/deleted/untracked data is preserved."})


if __name__ == "__main__":
    initialize()
