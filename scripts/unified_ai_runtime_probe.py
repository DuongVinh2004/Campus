"""UNI-001: bounded readback, synthetic identity checks, no model dispatch.

Evidence is exclusive-create. Database inspection uses mode=ro and exports
counts/schema only. Tokens and profile contents never enter the report.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "infra/local/unified-ai-20261014-01"


def checked(path: Path) -> Path:
    absolute = path.resolve()
    if not absolute.is_relative_to(ROOT) or absolute == ROOT:
        raise ValueError("exact workspace descendant required")
    for parent in [path, *path.parents]:
        if parent == ROOT.parent:
            break
        if parent.is_symlink() or parent.is_junction():
            raise ValueError("reparse path is outside this probe's scope")
    return absolute


def retain(path: Path, value):
    target = checked(path)
    if not target.parent.is_dir():
        raise ValueError("preflight the evidence directory first")
    with target.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)


def http(port, path, token=None, body=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    request = Request(f"http://127.0.0.1:{port}{path}", headers=headers,
                      data=json.dumps(body).encode() if body is not None else None)
    try:
        with urlopen(request, timeout=8) as response:
            data = response.read(1_048_577)
            if len(data) > 1_048_576:
                raise ValueError("readback too large")
            return response.status, json.loads(data)
    except HTTPError as exc:
        return exc.code, {}
    except (URLError, TimeoutError) as exc:
        return None, {"error_type": type(exc).__name__}


def probe(api_port=8004):
    report = {"captured_at": datetime.now(timezone.utc).isoformat(),
              "workspace": str(ROOT), "no_model_calls": True,
              "production_changes": False, "health": [], "actors": [],
              "storage": [], "source_snapshot_comparison": []}
    for port in [8003, api_port]:
        status, health = http(port, "/health/live")
        report["health"].append({"port": port, "status": status, "health": health})
    for account in ["SV001", "SV024", "OF001", "OF002", "KA001"]:
        status, session = http(api_port, "/v1/auth/demo-login", body={"account": account})
        row = {"account": account, "login_status": status, "reads": {}}
        if status == 200:
            token = session["token"]  # Request-local; deliberately not retained.
            user = session["user"]
            row.update(subject_id=user["user_id"], roles=user["roles"], is_synthetic=user["is_synthetic"])
            for path in ["/v1/service-course-records", "/v1/service-requests",
                         "/v1/staff/service-requests", "/v1/capabilities", "/v1/assistant/capabilities"]:
                code, value = http(api_port, path, token)
                row["reads"][path] = {"status": code, "items": len(value.get("items", [])) if code == 200 else None}
                if code == 200 and path == "/v1/assistant/capabilities":
                    row["reads"][path]["capabilities"] = value
        report["actors"].append(row)
    for name in ["infra/local/certificate-stage1-20261013-01/demo.sqlite3",
                 "infra/local/public-rag-20261013/conversations.sqlite3",
                 "infra/local/multi-agent-integrated-20261013-01/agent-runs.sqlite3"]:
        path = checked(ROOT / name)
        row = {"path": name, "exists": path.is_file()}
        if path.is_file():
            with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as connection:
                row["tables"] = []
                for (table,) in connection.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
                    quoted = '"' + table.replace('"', '""') + '"'
                    count = connection.execute(f"SELECT COUNT(*) FROM {quoted}").fetchone()[0]
                    row["tables"].append({"name": table, "rows": count})
        report["storage"].append(row)
    snapshot = checked(ROOT / "infra/local/service-stage6-20261014-01/frontend02/acceptance-20261012-58-frontend-repair1-local-repair2") if api_port == 8004 else checked(STATE / "frontend01/acceptance-20261012-58-frontend-repair1-local-repair2")
    build = snapshot / ".next/BUILD_ID"
    report["frontend"] = {"port": 3005 if api_port == 8004 else 3006, "api_port": api_port, "snapshot": str(snapshot),
                           "build_id": build.read_text().strip() if build.is_file() else None}
    for name in ["src/app/layout.tsx", "src/app/chat/page.tsx", "src/features/documents/ServiceWorkspace.tsx",
                 "src/components/student/StudentRuntime.tsx", "src/lib/assistant-context.tsx"]:
        files = [checked(ROOT / "apps/web" / name), checked(snapshot / name)]
        hashes = [hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None for p in files]
        report["source_snapshot_comparison"].append({"path": name, "source_sha256": hashes[0],
                                                     "snapshot_sha256": hashes[1], "matches": hashes[0] == hashes[1]})
    status = subprocess.run(["git", "status", "--porcelain=v1"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    report["git"] = {"exit_code": status.returncode, "status": status.stdout, "warnings": status.stderr}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--api-port", type=int, choices=[8004, 8006], default=8004)
    args = parser.parse_args()
    output = checked(args.output)
    if not output.is_relative_to(STATE) or output.exists():
        raise ValueError("fresh output within unified evidence namespace required")
    retain(output, probe(args.api_port))
    print(str(output))
