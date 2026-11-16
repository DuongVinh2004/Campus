"""Compare old content columns exactly before serving the approved new schema."""
import asyncio
from datetime import UTC, datetime
import hashlib
import json
import re

import asyncpg

from knowledge_platform import ROOT, connection, retain
from knowledge_automation_checkpoint_20261027 import database


async def main():
    scope = ROOT / "infra/local/knowledge-automation-20261026"
    pre = json.loads((scope / "rollout-preflight-20261027T084915271098.json").read_bytes())
    conn = await asyncpg.connect(**connection())
    hashes = {}
    try:
        async with conn.transaction(readonly=True,isolation="repeatable_read"):
            for table,names in pre["content_columns"].items():
                if not all(re.fullmatch("[a-z_0-9]+",name) for name in [table,*names]):
                    raise ValueError("Unsafe identifier")
                rows = await conn.fetch('SELECT '+','.join('"'+name+'"' for name in names)+' FROM "'+table+'"')
                encoded = sorted(json.dumps(dict(row),ensure_ascii=False,sort_keys=True,default=str) for row in rows)
                hashes[table] = {"count":len(rows),"sha256":hashlib.sha256("\n".join(encoded).encode()).hexdigest()}
    finally:
        await conn.close()
    current = await database(connection())
    # The retained JSON uses str(UUID/datetime). Normalize live typed values to
    # that same serialization, without changing any business field or expected value.
    pointer = json.loads(json.dumps(current["pointer"],default=str))
    unchanged = hashes == pre["content_hashes"]
    passed = unchanged and current["schema"] == "0022" and pointer == pre["main"]["pointer"]
    target = scope / ("rollout-migration-"+datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")+".json")
    retain(target,{"at":datetime.now(UTC),"schema":current["schema"],"passed":passed,
        "all_existing_content_rows_unchanged":unchanged,"pointer_unchanged":pointer == pre["main"]["pointer"],
        "pointer":pointer,"content_hashes":hashes,"checker_correction":"Normalize typed UUID/datetime to retained JSON representation; prior failed receipt preserved"})
    print(json.dumps({"receipt":str(target),"passed":passed,"schema":current["schema"]}))
    if not passed:
        raise RuntimeError("Migration comparison failed; stop before serving")


if __name__ == "__main__":
    asyncio.run(main())
