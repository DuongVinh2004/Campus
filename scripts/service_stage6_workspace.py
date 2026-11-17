"""Exclusive stage6 evidence and read-only baselines; never clean old evidence."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from certificate_stage1_workspace import ROOT, checked

STATE = ROOT / "infra/local/service-stage6-20261014-01"
BUSINESS = ROOT / "infra/local/certificate-stage1-20261013-01/demo.sqlite3"


def destination(name):
    if Path(name).name != name or not name:
        raise ValueError("one evidence filename required")
    return checked(STATE / name, STATE)


def retain(name, value):
    with destination(name).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)


def rows_digest(connection, table):
    # Names are obtained from sqlite_master, quoted as identifiers, never input SQL.
    quoted = '"' + table.replace('"', '""') + '"'
    rows = connection.execute(f"SELECT * FROM {quoted}").fetchall()
    encoded = sorted(json.dumps(row, default=lambda b: b.hex(), ensure_ascii=False) for row in rows)
    return {"rows": len(rows), "sha256": hashlib.sha256("\n".join(encoded).encode()).hexdigest()}


def initialize():
    checked(STATE).mkdir(exist_ok=False)
    status = subprocess.run(["git", "status", "--porcelain=v1"], cwd=ROOT, capture_output=True,
                            text=True, encoding="utf-8", errors="replace")
    with sqlite3.connect(f"{checked(BUSINESS).as_uri()}?mode=ro", uri=True) as source:
        tables = [r[0] for r in source.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        baseline = {t: rows_digest(source, t) for t in tables}
        with sqlite3.connect(destination("business-before.sqlite3")) as backup:
            source.backup(backup)
    retain("initial-discovery-01.json", {"captured_at": datetime.now(timezone.utc).isoformat(),
        "workspace": str(ROOT), "business": str(BUSINESS), "tables": baseline,
        "git_status": status.stdout, "git_warnings": status.stderr,
        "paid_writer": "http://127.0.0.1:8003", "new_runtime_owns_paid_ledger": False})


if __name__ == "__main__":
    initialize()
