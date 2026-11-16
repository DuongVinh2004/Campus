"""Exclusive local copies before/after this evidence batch; never restores."""
import argparse
import asyncio
import json
import os
import sqlite3
import subprocess
from datetime import UTC, datetime

import asyncpg

from complete_huce_corpus import SCOPE
from knowledge_platform import PGROOT, ROOT, STATE, checked_path, connection, retain
from campus247.application.knowledge.platform_models import digest


async def backup(label):
    target = checked_path(SCOPE / "backups" / label, ROOT)
    target.mkdir(exist_ok=False)
    parameters = connection()
    conn = await asyncpg.connect(**parameters)
    copies = []
    try:
        async with conn.transaction(readonly=True, isolation="repeatable_read"):
            assert await conn.fetchval("SELECT current_database()") == "campus247_knowledge_local_20261023"
            snapshot = await conn.fetchval("SELECT pg_export_snapshot()")
            environment = {k: v for k, v in os.environ.items() if k.upper() in {"PATH", "SYSTEMROOT", "WINDIR"}}
            environment.update(PGPASSWORD=parameters["password"], PGHOST=parameters["host"],
                PGPORT=str(parameters["port"]), PGUSER=parameters["user"])
            destination = checked_path(target / "metadata.dump", ROOT)
            with destination.open("xb") as output:
                process = subprocess.run([str(PGROOT / "bin/pg_dump.exe"), "-Fc", "--snapshot=" + snapshot,
                    parameters["database"]], stdout=output, stderr=subprocess.PIPE, env=environment,
                    creationflags=0x08000000, check=False)
            if process.returncode:
                raise RuntimeError("PG_DUMP_FAILED; partial file retained")
            copies.append({"file": destination.name, "sha256": digest(destination.read_bytes()),
                "bytes": destination.stat().st_size, "exit_code": process.returncode})
        for name in ("action-idempotency.sqlite3", "actor-state.sqlite3", "conversations.sqlite3"):
            source = checked_path(STATE / name, ROOT)
            destination = checked_path(target / name, ROOT)
            with destination.open("xb"):
                pass
            with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as origin:
                with sqlite3.connect(destination) as copied:
                    origin.backup(copied)
                    assert copied.execute("PRAGMA quick_check").fetchone() == ("ok",)
            copies.append({"file": name, "sha256": digest(destination.read_bytes()), "quick_check": "ok"})
        receipt = {"at": datetime.now(UTC).isoformat(), "copies": copies, "restore_not_run": True,
            "scope": "each database copy consistent individually; no cross-store atomicity claimed"}
        retain(target / "receipt.json", receipt)
        print(json.dumps({"backup": str(target / "receipt.json"), "copies": len(copies)}))
    finally:
        await conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("label", choices=("pre-stage-20261025-01", "post-verification-20261025-01"))
    asyncio.run(backup(parser.parse_args().label))
