"""Compare a restored runtime with its source: exact row counts of every public table, every SQLite store, and the file
counts of the restored state. Used by the restore drill (rollout step 1.14).

  python infra/cloud/compare_restore.py dump --root <root> --out counts.json
  python infra/cloud/compare_restore.py diff --a source.json --b restored.json
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

STATE_REL = Path("infra/local/knowledge-platform-20261023")
STORES = ("conversations.sqlite3", "actor-state.sqlite3", "campus-ops.sqlite3", "action-idempotency.sqlite3", "write-previews.sqlite3",
          "source-reviews.sqlite3", "oidc.sqlite3")


def pg_counts(conn: dict) -> dict:
    import asyncio

    import asyncpg

    async def run() -> dict:
        connection = await asyncpg.connect(host=conn["host"], port=conn["port"], user=conn["user"], password=conn["password"],
                                           database=conn["database"])
        try:
            tables = [r["tablename"] for r in await connection.fetch("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY 1")]
            return {t: await connection.fetchval(f'SELECT count(*) FROM "{t}"') for t in tables}
        finally:
            await connection.close()

    return asyncio.run(run())


def dump(root: Path) -> dict:
    conn = json.loads((root / STATE_REL / "local-connection.json").read_text(encoding="utf-8"))
    counts = pg_counts(conn)
    sqlite_counts = {}
    for name in STORES:
        path = root / STATE_REL / name
        if not path.exists():
            continue
        with sqlite3.connect(f"file:{path.as_posix()}?mode=ro&immutable=1", uri=True) as db:
            tabs = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
            sqlite_counts[name] = {t: db.execute(f'SELECT count(*) FROM "{t}"').fetchone()[0] for t in tabs}
    return {"postgres": counts, "sqlite": sqlite_counts}


def diff(a: dict, b: dict) -> int:
    problems = []
    for kind in ("postgres",):
        for table in sorted(set(a[kind]) | set(b[kind])):
            if a[kind].get(table) != b[kind].get(table):
                problems.append(f"{kind}.{table}: {a[kind].get(table)} != {b[kind].get(table)}")
    for store in sorted(set(a["sqlite"]) | set(b["sqlite"])):
        for table in sorted(set(a["sqlite"].get(store, {})) | set(b["sqlite"].get(store, {}))):
            if a["sqlite"].get(store, {}).get(table) != b["sqlite"].get(store, {}).get(table):
                problems.append(f"sqlite.{store}.{table}: {a['sqlite'].get(store, {}).get(table)} != {b['sqlite'].get(store, {}).get(table)}")
    total = sum(a["postgres"].values())
    print(json.dumps({"postgres_tables": len(a["postgres"]), "postgres_rows": total,
                      "sqlite_tables": sum(len(v) for v in a["sqlite"].values()), "differences": problems}, indent=1))
    return 1 if problems else 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("dump", "diff"))
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path)
    parser.add_argument("--a", type=Path)
    parser.add_argument("--b", type=Path)
    args = parser.parse_args()
    if args.command == "dump":
        value = dump(args.root)
        args.out.write_text(json.dumps(value, indent=1), encoding="utf-8")
        print(json.dumps({"tables": len(value["postgres"]), "rows": sum(value["postgres"].values())}))
    else:
        sys.exit(diff(json.loads(args.a.read_text(encoding="utf-8")), json.loads(args.b.read_text(encoding="utf-8"))))


if __name__ == "__main__":
    main()
