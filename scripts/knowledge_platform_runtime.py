"""Resume the retained local knowledge runtime; never initialize or replace data.

Run with infra/local/rag-fixture/.venv/Scripts/python.exe -B.
Existing listeners are reused only after checking their process and runtime
identity. Failed starts and their logs remain available; nothing is killed.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import socket
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import asyncpg
import httpx
from knowledge_platform import (
    CLUSTER,
    DB_NAME,
    DB_PORT,
    PGROOT,
    ROOT,
    STATE,
    TENANT,
    checked_path,
    connection,
    retain,
)

FRONTEND = None
HIDDEN = getattr(subprocess, "CREATE_NO_WINDOW", 0)
RAG_V2_INDEX = "data/rag_v2_index/embedded2"


class EngineMismatch(RuntimeError):
    pass


def listening(port):
    with socket.socket() as probe:
        probe.settimeout(1)
        return probe.connect_ex(("127.0.0.1", port)) == 0


def frontend_path(name):
    if name is None:
        name = select_frontend()
    if not re.fullmatch(r"frontend-knowledge-[a-z0-9-]+", name):
        raise ValueError("Exact retained frontend name required")
    return checked_path(STATE / name, ROOT)


def select_frontend(name=None):
    if name is not None:
        frontend_path(name)
        return name
    candidates = []
    for path in STATE.glob("frontend-knowledge-*"):
        if not path.is_dir() or not re.fullmatch(r"frontend-knowledge-[a-z0-9-]+", path.name):
            continue
        build_id = checked_path(frontend_path(path.name) / ".next/BUILD_ID", ROOT)
        if not build_id.is_file():
            continue
        built_at = build_id.stat().st_mtime
        receipt = checked_path(STATE / (path.name + "-build.json"), ROOT)
        if receipt.is_file():
            try:
                value = json.loads(receipt.read_text(encoding="utf-8"))
                if value.get("exit_code", 0) != 0:
                    continue
                if value.get("built_at"):
                    built_at = datetime.fromisoformat(value["built_at"].replace("Z", "+00:00"))
                    built_at = built_at.replace(tzinfo=built_at.tzinfo or UTC).timestamp()
            except (OSError, ValueError, TypeError, AttributeError):
                pass  # Older receipts have no build time; BUILD_ID remains authoritative.
        candidates.append((built_at, path.name))
    if not candidates:
        raise RuntimeError("No retained frontend build found; no automatic build attempted")
    return max(candidates)[1]


def process_inventory(frontend=FRONTEND):
    frontend = select_frontend(frontend)
    # Only the retained platform's Python/Node commands enter this process.
    command = (
        "Get-CimInstance Win32_Process | Where-Object { "
        "($_.Name -eq 'python.exe' -and $_.CommandLine -like '*knowledge_platform.py*') "
        f"-or ($_.Name -eq 'node.exe' -and $_.CommandLine -like '*{frontend}*') "
        "} | Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress"
    )
    result = subprocess.run(["powershell.exe", "-NoProfile", "-Command", command],
        capture_output=True, text=True, check=True, creationflags=HIDDEN)
    value = json.loads(result.stdout) if result.stdout.strip() else []
    return value if isinstance(value, list) else [value]


def matching_processes(rows, kind, frontend=FRONTEND):
    import shlex
    found = []
    for row in rows:
        # Windows command lines keep quotes around the interpreter's path.
        words = [word.strip('"').replace("\\", "/").casefold()
                 for word in shlex.split(row.get("CommandLine") or "", posix=False)]
        if kind == "frontend":
            expected = str(frontend_path(frontend)).replace("\\", "/").casefold()
            matches = expected in words and "start" in words and "3015" in words
        else:
            script = str(ROOT / "scripts/knowledge_platform.py").replace("\\", "/").casefold()
            matches = any(word in {script, "scripts/knowledge_platform.py"} for word in words)
            matches = matches and ("worker" if kind == "worker" else "serve") in words
            if kind == "api":
                matches = matches and "8015" in words and "--generation" in words and "3015" in words
            matches = matches and "--rehearsal" not in words
        if matches:
            found.append(row["ProcessId"])
    return found


async def queue_state():
    """Count only; external test tenants never enter the serving worker's claim."""
    conn = await asyncpg.connect(**connection(), timeout=10)
    try:
        async with conn.transaction(readonly=True):
            if await conn.fetchval("SELECT current_database()") != DB_NAME:
                raise RuntimeError("Worker queue database identity mismatch")
            rows = await conn.fetch("""SELECT tenant_id=$1 AS in_worker_scope,state,count(*) AS count
                FROM knowledge_ingestion_job WHERE state IN ('QUEUED','RUNNING','RETRY_WAIT')
                GROUP BY tenant_id=$1,state ORDER BY in_worker_scope,state""", TENANT)
            return {"tenant": TENANT, "pending": [dict(row) for row in rows]}
    finally:
        await conn.close()


def worker_state(rows):
    """A process alone is insufficient: require a fresh DB-verified loop pulse."""
    import shlex
    workers = matching_processes(rows, "worker")
    if not workers:
        raise RuntimeError("Exactly one retained scoped knowledge worker is required")
    from pathlib import Path
    paths = set()
    for row in rows:
        if row["ProcessId"] not in workers:
            continue
        words = [word.strip('"') for word in shlex.split(row.get("CommandLine") or "", posix=False)]
        if words.count("--worker-heartbeat") != 1 or words.index("--worker-heartbeat")+1 >= len(words):
            if len(workers) > 1:
                raise RuntimeError("Exactly one verifiable scoped knowledge worker is required")
            raise RuntimeError("Worker has no verifiable loop pulse; existing process preserved")
        path = checked_path(Path(words[words.index("--worker-heartbeat")+1]), ROOT)
        if path.parent.parent != STATE or not re.fullmatch(r"resume-\d{8}T\d{12}", path.parent.name) or path.name != "worker-health.jsonl":
            raise RuntimeError("Worker pulse path identity mismatch")
        paths.add(path)
    # Windows venv redirectors and their interpreter share one command/pulse.
    # The freshly reporting PID, rather than the wrapper PID, owns the loop.
    if len(paths) != 1:
        raise RuntimeError("Exactly one retained scoped knowledge worker is required")
    path = paths.pop()
    try:
        # Read a bounded tail, ignoring a concurrent incomplete final append.
        with path.open("rb") as stream:
            stream.seek(max(0, path.stat().st_size - 8192))
            lines = stream.read(8192).splitlines(keepends=True)
        complete = [line for line in lines if line.endswith(b"\n")]
        pulse = json.loads(complete[-1])
        age = (datetime.now(UTC)-datetime.fromisoformat(pulse["at"])).total_seconds()
    except (OSError, ValueError, KeyError, IndexError):
        raise RuntimeError("Worker loop pulse unavailable") from None
    if (pulse["pid"] not in workers or pulse["database"] != DB_NAME or pulse["tenant"] != TENANT
        or not 0 <= age <= 30 or pulse.get("database_verified") is not True
        or pulse["state"] not in {"PROCESSING", "IDLE", "RESOURCE_WAIT"}):
        raise RuntimeError("Worker pulse is stale, stopped, unverified or outside scope")
    return {**pulse, "pulse_file": str(path)}


async def database_identity():
    conn = await asyncpg.connect(**connection(), timeout=10)
    try:
        async with conn.transaction(readonly=True):
            name = await conn.fetchval("SELECT current_database()")
            version = await conn.fetchval("SELECT version_num FROM alembic_version")
            if name != DB_NAME or version not in {"0017", "0018", "0022"}:
                raise RuntimeError("Retained database/schema identity mismatch; no migration attempted")
            return {"database": name, "schema": version}
    finally:
        await conn.close()


def model_identity():
    from campus247.application.knowledge.platform_models import (
        EMBED_MODEL,
        EMBED_REVISION,
        RERANK_MODEL,
        RERANK_REVISION,
    )
    for port, model, revision in ((18081, EMBED_MODEL, EMBED_REVISION),
                                  (18082, RERANK_MODEL, RERANK_REVISION)):
        response = httpx.get(f"http://127.0.0.1:{port}/info", trust_env=False, timeout=10)
        response.raise_for_status()
        value = response.json()
        if (value.get("model_id"), value.get("model_sha")) != (model, revision):
            raise RuntimeError(f"Model identity mismatch on {port}; existing listener preserved")


def api_state(*, engine="v2"):
    with httpx.Client(base_url="http://127.0.0.1:8015", trust_env=False, timeout=10) as client:
        response = client.get("/health/ready")
        health = response.json()
        enabled = health.get("rag_v2", {}).get("enabled")
        if enabled is not (engine == "v2"):
            actual = "v2" if enabled is True else "v1" if enabled is False else "unknown"
            raise EngineMismatch(f"RAG engine mismatch: requested {engine}, running {actual}; existing listener preserved")
        response.raise_for_status()
        if health.get("status") != "ready":
            raise RuntimeError("API dependencies are not ready")
        credentials = json.loads(checked_path(STATE / "owner-credentials.json", ROOT).read_text(encoding="utf-8"))
        response = client.post("/v1/knowledge/platform/session",
            json={key: credentials[key] for key in ("username", "password")})
        response.raise_for_status()
        response = client.get("/v1/knowledge/platform/state")
        response.raise_for_status()
        value = response.json()
        desired = value["desired"]
        live = [ack for ack in value["serving"] if ack.get("live")
            and all(ack[key] == desired[key] for key in ("release_id", "generation", "policy_generation"))]
        if not live:
            raise RuntimeError("No live acknowledgement for the desired release")
        return {"release_id": desired["release_id"], "generation": desired["generation"],
                "policy_generation": desired["policy_generation"], "live_ack": True}


def wait_for(process, check, seconds=35):
    deadline = time.perf_counter() + seconds
    while time.perf_counter() < deadline:
        if process is not None and process.poll() is not None:
            raise RuntimeError("Owned process exited; inspect retained logs")
        try:
            return check()
        except EngineMismatch:
            raise
        except (OSError, RuntimeError):
            time.sleep(.5)
        except (httpx.HTTPError, ValueError, KeyError) as error:
            # HTTP readiness failures can be transient. Preserve the final
            # failure as a type only so credentials cannot enter the log.
            if time.perf_counter() + .5 >= deadline:
                raise RuntimeError(f"Readiness failed: {type(error).__name__}") from None
            time.sleep(.5)
    raise RuntimeError("Readiness timeout; inspect retained logs")


def frontend_ready():
    response = httpx.get("http://127.0.0.1:3015/login", trust_env=False, timeout=3)
    response.raise_for_status()
    if not any(title in response.text for title in ("Đăng nhập quản trị tri thức", "Đăng nhập Campus 24/7")):
        raise RuntimeError("Frontend identity mismatch; existing listener preserved")
    return True


def start(frontend=FRONTEND, *, defer_worker=False, engine="v2", rag_v2_index=RAG_V2_INDEX):
    if os.name != "nt":
        raise RuntimeError("This retained runtime is configured for Windows only")
    if engine not in {"v1", "v2"}:
        raise ValueError("Explicit RAG engine v1 or v2 required")
    index = Path(rag_v2_index)
    index = checked_path(index if index.is_absolute() else ROOT / index, ROOT)
    if engine == "v2" and not index.is_dir():
        raise RuntimeError("RAG v2 index missing; no fallback to v1 attempted")
    frontend = select_frontend(frontend)
    # Resolve every fixed target and require existing retained state first.
    for path in (CLUSTER / "PG_VERSION", STATE / "owner-identity.json",
                 frontend_path(frontend) / ".next/BUILD_ID", PGROOT / "bin/pg_ctl.exe"):
        if not checked_path(path, ROOT).is_file():
            raise RuntimeError("Required retained runtime file missing; no bootstrap attempted")
    connection()
    model_identity()
    scope = checked_path(STATE / ("resume-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")), ROOT)
    scope.mkdir(exist_ok=False)
    report = {"started": {}, "reused": {}, "database_reset": False, "security_policy_changed": False,
        "worker_deferred": defer_worker, "engine": engine, "rag_v2_index": str(index)}
    try:
        if not listening(DB_PORT):
            with checked_path(scope / "postgres-control.log", ROOT).open("xb") as log:
                result = subprocess.run([str(PGROOT / "bin/pg_ctl.exe"), "-D", str(CLUSTER),
                    "-l", str(checked_path(scope / "postgres.log", ROOT)), "-o",
                    "-h 127.0.0.1 -p 55437 -c shared_buffers=128MB -c max_connections=20 -c log_min_error_statement=panic",
                    "-w", "-t", "30", "start"], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                    creationflags=HIDDEN, check=False)
            if result.returncode:
                raise RuntimeError("PostgreSQL startup failed; inspect retained log; no OS policy change attempted")
            report["started"]["postgres"] = True
        report["database"] = asyncio.run(database_identity())
        report["queue"] = asyncio.run(queue_state())
        rows = process_inventory(frontend)
        commands = {
            "frontend": ["scripts/knowledge_platform_frontend.py", "serve", "--name", frontend, "--port", "3015"],
            "api": ["scripts/knowledge_platform.py", "serve", "--generation", "--port", "8015", "--frontend-port", "3015"],
            "worker": ["scripts/knowledge_platform.py", "worker", "--worker-heartbeat", str(scope / "worker-health.jsonl")],
        }
        if defer_worker:
            commands.pop("worker")  # Preserve deferred legacy queue without claiming its jobs.
        for kind, command in commands.items():
            existing = matching_processes(rows, kind, frontend)
            port = {"frontend": 3015, "api": 8015}.get(kind)
            if port is not None and listening(port) and not existing:
                raise RuntimeError(f"Port {port} belongs to an unrecognized process; listener preserved")
            process = None
            if existing:
                report["reused"][kind] = existing
            else:
                with checked_path(scope / (kind + ".log"), ROOT).open("xb") as log:
                    environment = os.environ.copy()
                    if kind == "api":
                        environment.update(CAMPUS247_RAG_ENGINE=engine, CAMPUS247_RAG_V2_INDEX=str(index))
                        if engine == "v2":
                            vendor = str(checked_path(ROOT / "data/rag_v2_vendor", ROOT))
                            prior = environment.get("PYTHONPATH")
                            environment["PYTHONPATH"] = os.pathsep.join([vendor, prior] if prior else [vendor])
                    process = subprocess.Popen([sys.executable, "-B", "-u", *command], cwd=ROOT,
                        stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, creationflags=HIDDEN,
                        env=environment)
                report["started"][kind] = process.pid
            if kind == "frontend":
                wait_for(process, frontend_ready)
            elif kind == "api":
                report["release"] = wait_for(process, lambda: api_state(engine=engine), seconds=180)
            else:
                report["worker"] = wait_for(process, lambda: worker_state(process_inventory(frontend)))
        report["ready"] = True
        return report
    finally:
        retain(scope / "receipt.json", report)
        print(json.dumps({"receipt": str(scope / "receipt.json"), "ready": report.get("ready", False)}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("start", "status"))
    parser.add_argument("--frontend-name", default=FRONTEND, help="Exact existing immutable build; no build or migration is performed")
    parser.add_argument("--defer-worker", action="store_true", help="Start/check serving only; preserve the queued legacy documents for later review")
    parser.add_argument("--engine", choices=("v1", "v2"), default="v2", help="Required API engine; never silently reuse a different engine")
    parser.add_argument("--rag-v2-index", default=RAG_V2_INDEX, help="Existing RAG v2 index inside this workspace")
    args = parser.parse_args()
    try:
        if args.command == "start":
            start(args.frontend_name, defer_worker=args.defer_worker, engine=args.engine, rag_v2_index=args.rag_v2_index)
        else:
            args.frontend_name = select_frontend(args.frontend_name)
            model_identity()
            workers = matching_processes(process_inventory(args.frontend_name), "worker", args.frontend_name)
            if not workers and not args.defer_worker:
                raise RuntimeError("No retained knowledge worker is running")
            print(json.dumps({"database": asyncio.run(database_identity()), "release": api_state(engine=args.engine),
                "frontend": frontend_ready(), "worker_pids": workers, "worker_deferred": args.defer_worker,
                "queue": asyncio.run(queue_state()),
                "worker": worker_state(process_inventory(args.frontend_name)) if workers else None}))
    except (OSError, RuntimeError, ValueError, KeyError, subprocess.SubprocessError,
            httpx.HTTPError, asyncpg.PostgresError, asyncpg.InterfaceError) as error:
        reason = str(error) if isinstance(error, RuntimeError) else type(error).__name__
        print(f"Runtime check failed: {reason}. Retained data preserved; protections unchanged.", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
