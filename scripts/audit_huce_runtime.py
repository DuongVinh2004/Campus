"""Read-only, bounded runtime diagnostics; omit user content and credentials."""
import json
import sqlite3
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


def main():
    with httpx.Client(trust_env=False, timeout=5) as client:
        for path in ("/health/live", "/health/entry"):
            try:
                response = client.get("http://127.0.0.1:8006" + path)
                print(path, response.status_code, response.text[:1200])
            except httpx.HTTPError as exc:
                print(path, type(exc).__name__)
    for name in ("coordination", "actor"):
        file = ROOT / ".tooling/campus-single-entry-20261015-01/runtime" / (name + ".sqlite3")
        with sqlite3.connect(file.as_uri() + "?mode=ro", uri=True) as connection:
            tables = connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            print(name, json.dumps(tables))
            for (table,) in tables:
                if table in {"agent_run", "agent_event", "unified_actor_state"}:
                    print(table, connection.execute('PRAGMA table_info("' + table + '")').fetchall())
            if name == "coordination":
                rows = connection.execute("SELECT id,status,record FROM agent_run ORDER BY rowid DESC LIMIT 4").fetchall()
                for run_id, status, encoded in rows:
                    record = json.loads(encoded)
                    print(json.dumps({"run_id": run_id, "status": status, "keys": list(record),
                        "usage": record.get("usage"), "errors": record.get("error_codes"),
                        "controller_keys": list(record.get("controller", {}))}, ensure_ascii=False))
                    events = connection.execute("SELECT record FROM agent_event WHERE run_id=? ORDER BY seq DESC LIMIT 2", (run_id,)).fetchall()
                    print("last_events", events)
            else:
                rows = connection.execute("SELECT key,version,record FROM unified_actor_state WHERE namespace='consent' LIMIT 8").fetchall()
                for key, version, encoded in rows:
                    record = json.loads(encoded)
                    print("consent", key, version, record.get("payload", {}).get("decision"))


if __name__ == "__main__":
    main()
