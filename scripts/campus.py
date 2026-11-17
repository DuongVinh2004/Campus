"""Build/start Campus at one browser address: http://127.0.0.1:8015.

The private API is loopback-only. No existing process is killed, ports never
auto-increment, and every build/log/launch receipt is retained separately.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
from urllib.request import urlopen, ProxyHandler, build_opener

from campus_backend import ROOT, STATE, checked

WEB = ROOT / "apps/web"
OUTPUT = ROOT / ".tooling/campus-single-entry-20261015-01"
NODE = shutil.which("node")
NEXT = WEB / "node_modules/next/dist/bin/next"
HIDDEN = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def stamp():
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")


def source_hash():
    result = hashlib.sha256()
    paths = [WEB / name for name in ("package.json", "next.config.ts", "postcss.config.mjs")]
    for folder in ("src", "public"):
        paths.extend(p for p in (WEB / folder).rglob("*") if p.is_file())
    for path in sorted(paths):
        result.update(str(path.relative_to(WEB)).encode())
        result.update(checked(path).read_bytes())
    return result.hexdigest()


def environment(destination):
    return {**os.environ, "CAMPUS_NEXT_DIST_DIR": destination,
        "CAMPUS_BACKEND_URL": "http://127.0.0.1:8006", "NEXT_PUBLIC_UNIFIED_AI": "true",
        "NEXT_PUBLIC_CERTIFICATE_DEMO": "true", "NEXT_PUBLIC_SERVICE_DEMO": "true",
        "NEXT_PUBLIC_MULTI_AGENT": "true", "NEXT_TELEMETRY_DISABLED": "1",
        "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8"}


def record(name, value):
    with checked(OUTPUT / name).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2)


def build():
    checked(OUTPUT).mkdir(parents=True, exist_ok=True)
    if not NODE or not NEXT.is_file():
        raise RuntimeError("Existing Node/Next installation required")
    tag = stamp()
    destination = ".next-stitch-campus-" + tag
    checked(WEB / destination)
    if (WEB / destination).exists():
        raise FileExistsError(destination)
    before = source_hash()
    command = [NODE, str(NEXT), "build", "--webpack"]
    with checked(OUTPUT / ("build-" + tag + ".log")).open("xb") as log:
        result = subprocess.run(command, cwd=WEB, env=environment(destination),
                                stdout=log, stderr=subprocess.STDOUT, creationflags=HIDDEN)
    record("build-" + tag + ".json", {"destination": destination,
        "exit_code": result.returncode, "source_hash": before, "source_stable": before == source_hash()})
    if result.returncode or before != source_hash():
        raise RuntimeError("Build failed or sources changed; inspect retained build log")
    print("Build ready: " + destination, flush=True)
    return destination


def current_build():
    records = sorted(OUTPUT.glob("build-*.json"), reverse=True)
    for path in records:
        value = json.loads(checked(path).read_text(encoding="utf-8"))
        if (value["exit_code"] == 0 and value["source_stable"]
                and value["source_hash"] == source_hash()
                and checked(WEB / value["destination"] / "BUILD_ID").is_file()):
            return value["destination"]
    return build()


def port_owned(port):
    # Use a bind check, not failed HTTP as proof that a port is available.
    with socket.socket() as probe:
        if os.name == "nt":
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            return True
    return False


def wait_ready(process, url, seconds=35):
    deadline = time.monotonic() + seconds
    opener = build_opener(ProxyHandler({}))
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Owned process exited; inspect retained launch log")
        try:
            with opener.open(url, timeout=2) as response:
                if response.status == 200:
                    return
        except OSError:
            pass
        time.sleep(.3)
    raise RuntimeError("Startup timeout; inspect retained launch logs")


def start():
    checked(OUTPUT).mkdir(parents=True, exist_ok=True)
    if any(port_owned(port) for port in (3115, 8006)):
        raise RuntimeError("Campus port already occupied; no automatic kill or alternate port")
    destination = current_build()
    tag = stamp()
    commands = {
        "backend": [sys.executable, "-B", "-u", str(ROOT / "scripts/campus_backend.py")],
        "frontend": [NODE, str(NEXT), "start", "-H", "127.0.0.1", "-p", "3115"],
    }
    processes = {}
    try:
        for name, command in commands.items():
            with checked(OUTPUT / (tag + "-" + name + ".log")).open("xb") as log:
                processes[name] = subprocess.Popen(command, cwd=WEB if name == "frontend" else ROOT,
                    env=environment(destination), stdin=subprocess.DEVNULL, stdout=log,
                    stderr=subprocess.STDOUT, creationflags=HIDDEN)
            wait_ready(processes[name], "http://127.0.0.1:8006/health/live" if name == "backend"
                       else "http://127.0.0.1:3115/health/live")
        record(tag + "-launch.json", {"url": "http://127.0.0.1:3115", "private_api": "127.0.0.1:8006",
            "pids": {k: p.pid for k, p in processes.items()}, "commands": commands,
            "destination": destination, "source_hash": source_hash(),
            "runtime_directory": str(checked(STATE)),
            "generation": os.environ.get("CAMPUS_MODEL_MODE", "guarded"),
            "test_paid_call_ceiling": os.environ.get("CAMPUS_E2E_PAID_CALL_CEILING")})
        print("Campus ready: http://127.0.0.1:3115 (UI and API)", flush=True)
        while all(p.poll() is None for p in processes.values()):
            time.sleep(1)
        raise RuntimeError("A Campus component exited; the other owned component is being stopped")
    except KeyboardInterrupt:
        pass
    finally:
        # Only children created by this invocation; never unrelated listeners.
        for process in processes.values():
            if process.poll() is None:
                process.terminate()
        for process in processes.values():
            process.wait(timeout=15)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "start", "status"), nargs="?", default="start")
    args = parser.parse_args()
    # The historical implementation above is retained for recovery/reference.
    # Normal project commands now all use the same main runtime and data.
    python = checked(ROOT / "infra/local/rag-fixture/.venv/Scripts/python.exe")
    if args.command == "build":
        command = [str(python), "-B", "-X", "utf8", "scripts/knowledge_platform_frontend.py", "build",
            "--name", "frontend-knowledge-main-" + stamp().lower()]
    else:
        command = [str(python), "-B", "-X", "utf8", "scripts/knowledge_platform_runtime.py", args.command,
            "--defer-worker", "--engine", "v2", "--rag-v2-index", "data/rag_v2_index/embedded2"]
    result = subprocess.run(command, cwd=ROOT, creationflags=HIDDEN, check=False,
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(result.stdout, end="", flush=True)
    print(result.stderr, end="", file=sys.stderr, flush=True)
    raise SystemExit(result.returncode)
