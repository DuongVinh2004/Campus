"""Inspect the local Advanced RAG stack and print commands; never start or stop it.

The public and advanced API runtimes share a paid ledger. A port check cannot
prove exclusive ledger ownership, so this helper deliberately remains read-only.
"""
from __future__ import annotations

import argparse
import json
import socket
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "infra/local/rag-advanced-20261013"
FINGERPRINT = "903531eb92b01e4ebb71ef6413b40fcba7b626e3480ddc6e3e580cfe634249fb"
NATIVE_CAPS = {"http": 6000, "inference": 2000, "tokens": 750000}


def checked(path: Path) -> Path:
    """Resolve every candidate and reject reparse paths, including ancestors."""
    path = path.absolute()
    resolved = path.resolve()
    if resolved == ROOT or not resolved.is_relative_to(ROOT):
        raise ValueError("path outside workspace")
    for parent in (path, *path.parents):
        if parent.exists() and (
            parent.is_symlink()
            or parent.is_junction()
            or getattr(parent.stat(), "st_file_attributes", 0) & 0x400
        ):
            raise ValueError("reparse path denied")
        if parent == ROOT:
            break
    return resolved


def read_json(path: Path) -> dict:
    value = json.loads(checked(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError("invalid retained record")
    return value


def listening(port: int) -> bool:
    with socket.socket() as client:
        client.settimeout(0.5)
        return client.connect_ex(("127.0.0.1", port)) == 0


def native_predecessor() -> tuple[Path, dict]:
    """Continue the most advanced retained counter, never a fresh allowance."""
    candidates = []
    for folder in checked(ROOT / "infra/local").glob("rag-advanced-models-20261013-*"):
        folder = checked(folder)
        if not folder.is_dir():
            continue
        records = sorted(folder.glob("native-*-reservation.json"))
        if not records:
            continue
        value = read_json(records[-1])
        if value.get("caps") != NATIVE_CAPS:
            raise ValueError("native cap mismatch")
        counts = value.get("counts")
        if not isinstance(counts, dict) or set(counts) != set(NATIVE_CAPS):
            raise ValueError("native counter mismatch")
        if any(type(counts[key]) is not int or counts[key] < 0 for key in NATIVE_CAPS):
            raise ValueError("invalid native counter")
        candidates.append((counts["inference"], counts["tokens"], folder, counts))
    if not candidates:
        raise ValueError("retained native ledger missing; do not start with zero counters")
    _, _, folder, counts = max(candidates, key=lambda row: (row[0], row[1], row[2].name))
    return folder, counts


def paid_snapshot() -> dict:
    """Read budget metadata only; do not instantiate a gateway or read secrets."""
    records = []
    for path in checked(ROOT / "infra/local/public-rag-20261013").glob("provider-*.json"):
        value = read_json(path)
        snapshot = value.get("snapshot")
        if isinstance(snapshot, dict):
            records.append((snapshot["calls"], value.get("stage") == "result", snapshot))
    if not records:
        raise ValueError("retained provider ledger missing")
    snapshot = max(records, key=lambda row: (row[0], row[1]))[2]
    if snapshot.get("hard_cap_usd") != "3" or snapshot.get("call_cap") != 8500:
        raise ValueError("paid cap mismatch")
    fields = ("hard_cap_usd", "conservative_charged_usd", "remaining_usd", "calls", "call_cap")
    return {key: snapshot[key] for key in fields}


def powershell_command(arguments: list[str]) -> str:
    return "& " + " ".join("'" + value.replace("'", "''") + "'" for value in arguments)


def inspect() -> dict:
    python_models = checked(ROOT / ".venv/Scripts/python.exe")
    python_api = checked(ROOT / "infra/local/rag-fixture/.venv/Scripts/python.exe")
    frontend = checked(STATE / "frontend3")
    index = checked(STATE / f"index-{FINGERPRINT}.json")
    manifest = read_json(index)
    if manifest.get("fingerprint") != FINGERPRINT or manifest.get("source_text_unchanged") is not True:
        raise ValueError("index binding mismatch")
    predecessor, counts = native_predecessor()
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")
    fresh_state = checked(ROOT / "infra/local" / f"rag-advanced-models-20261013-{stamp}")
    if fresh_state.exists():
        raise ValueError("planned model namespace already exists")
    commands = {
        "models": [str(python_models), "-B", str(checked(ROOT / "scripts/serve_rag_models.py")),
                   "--state", str(fresh_state), "--predecessor", str(predecessor)],
        "frontend": [str(python_api), "-B", str(checked(ROOT / "scripts/advanced_rag_frontend.py")),
                     "serve", "--name", "frontend3"],
        "api": [str(python_api), "-B", str(checked(ROOT / "scripts/run_advanced_rag.py")),
                "--port", "8001"],
    }
    ports = {str(port): listening(port) for port in (18081, 18082, 3001, 8001, 8000)}
    ready_files = {
        "python_models": python_models.is_file(),
        "python_api": python_api.is_file(),
        "frontend3_build": checked(frontend / ".next/BUILD_ID").is_file(),
        "index": index.is_file(),
    }
    return {
        "mode": "inspect_only_no_services_started",
        "workspace": str(ROOT),
        "url": "http://localhost:8001/chat",
        "files_ready": ready_files,
        "listening_loopback_ports": ports,
        "port_observation_scope": "current process network namespace; use the same context as the running services",
        "fresh_model_state": str(fresh_state),
        "native_predecessor": str(predecessor),
        "retained_native_counts": counts,
        "native_caps": NATIVE_CAPS,
        "paid_budget": paid_snapshot(),
        "index_fingerprint": FINGERPRINT,
        "powershell_commands": {key: powershell_command(value) for key, value in commands.items()},
        "startup_conditions": [
            "Preserve every existing listener; inspect ownership before any restart.",
            "Run each printed command in its own controlled runtime session.",
            "Confirm exclusive paid-ledger ownership; an unused port does not establish it.",
            "Keep the retained predecessor and all budget caps; never reset a ledger.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-free-ports", action="store_true",
                        help="return status 2 if a runtime/legacy API port is occupied")
    args = parser.parse_args()
    result = inspect()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not all(result["files_ready"].values()):
        return 1
    if args.require_free_ports and any(result["listening_loopback_ports"].values()):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
