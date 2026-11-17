"""Create a fresh retained local test DB and rehearse additive migrations.

Never uses a production/default DSN, clones the serving DB, resets or deletes data.
"""
import asyncio
import json
from datetime import UTC, datetime
from uuid import uuid4

import asyncpg
from alembic import command
from alembic.config import Config
from sqlalchemy.engine import URL

from knowledge_platform import ROOT, connection, retain, checked_path


async def create(database):
    parameters = connection()  # Verifies exact retained loopback cluster/user/database.
    conn = await asyncpg.connect(**(parameters | {"database": "postgres"}))
    try:
        if await conn.fetchval("SELECT EXISTS(SELECT 1 FROM pg_database WHERE datname=$1)", database):
            raise RuntimeError("New test database required; existing database preserved")
        await conn.execute('CREATE DATABASE "' + database + '"')
    finally:
        await conn.close()
    conn = await asyncpg.connect(**(parameters | {"database": database}))
    try:
        if await conn.fetchval("SELECT current_database()") != database:
            raise RuntimeError("Test database identity mismatch")
        await conn.execute("CREATE EXTENSION vector")
        await conn.execute("CREATE EXTENSION btree_gist")
    finally:
        await conn.close()


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--revision", choices=("0020", "0021", "0022"), default="0020")
    revision = parser.parse_args().revision
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")
    database = "campus247_automation_20261026_" + uuid4().hex[:12]
    # Exact new name; only ASCII literal identifiers enter CREATE DATABASE.
    import re
    if not re.fullmatch(r"campus247_automation_20261026_[0-9a-f]{12}", database):
        raise ValueError("Invalid test namespace")
    output = checked_path(ROOT / "infra/local/knowledge-automation-20261026" / ("schema-rehearsal-" + stamp + ".json"), ROOT)
    result = {"database": database, "host": "127.0.0.1", "port": 55437,
        "serving_database_modified": False, "new_database_retained": True,
        "started_at": datetime.now(UTC).isoformat(), "status": "started"}
    try:
        asyncio.run(create(database))
        parameters = connection() | {"database": database}
        config = Config(str(ROOT / "services/api/alembic.ini"))
        url = URL.create("postgresql+asyncpg", **{k: v for k, v in parameters.items() if k != "user"}, username=parameters["user"])
        config.set_main_option("sqlalchemy.url", url.render_as_string(hide_password=False).replace("%", "%%"))
        command.upgrade(config, revision)
        command.upgrade(config, revision)  # Migration replay is a no-op, not a reset.
        result.update(status="passed", revision=revision, replay="passed")
    except Exception as error:
        result.update(status="failed", error_type=type(error).__name__)
        raise
    finally:
        result["finished_at"] = datetime.now(UTC).isoformat()
        retain(output, result)
        print(json.dumps({"receipt": str(output), **result}))


if __name__ == "__main__":
    main()
