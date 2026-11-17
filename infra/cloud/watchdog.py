"""Watchdog that runs OUTSIDE the application, once a minute from a systemd timer, so it still speaks when the API is dead.

  python infra/cloud/watchdog.py check            # probe the services and send alerts
  python infra/cloud/watchdog.py unit-failed UNIT # called by systemd (OnFailure=) when a unit enters the failed state

It probes the API (/health/ready), the gateway (/health), the two model servers (/info) and the free disk space, and judges the
results with the same alert engine as the application (a probe must fail for two minutes before anything is sent, and recovery
needs two good minutes). Channels and their secrets come from the same environment variables as the application
(see services/api/src/campus247/observability/alert_notifiers.py). It imports only that package's stdlib-and-httpx modules, never
the application itself.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services/api/src"))

import httpx  # noqa: E402

from campus247.observability.alert_notifiers import build_notifier  # noqa: E402
from campus247.observability.alert_rules import Reading, Rule, Severity  # noqa: E402
from campus247.observability.alerts import AlertManager, AlertMessage  # noqa: E402

PROBES = {
    "api_ready": ("API không sẵn sàng", "http://127.0.0.1:8015/health/ready"),
    "gateway": ("Cổng gọi model không trả lời", "http://127.0.0.1:8025/health"),
    "embedding": ("Model embedding không trả lời", "http://127.0.0.1:18081/info"),
    "reranker": ("Model rerank không trả lời", "http://127.0.0.1:18082/info"),
}
DEFAULT_STATE = Path(os.environ.get("CAMPUS247_WATCHDOG_STATE", "/var/lib/campus247/watchdog"))
DISK_CRITICAL_PCT = 5.0


def probe(url: str, client: httpx.Client) -> bool:
    try:
        return client.get(url, timeout=3.0).status_code < 300
    except (httpx.HTTPError, OSError):
        return False


def probe_all(client: httpx.Client, disk_path: Path, usage=shutil.disk_usage) -> dict:
    results = {name: probe(url, client) for name, (_, url) in PROBES.items()}
    space = usage(disk_path)
    results["disk"] = 100.0 * space.free / space.total >= DISK_CRITICAL_PCT
    return results


def rules() -> list[Rule]:
    built = [Rule(f"watchdog_{name}", title, (lambda status, name=name: Reading(not status["probes"][name], "3 phút liên tiếp không đạt", Severity.CRITICAL)), for_s=120)
             for name, (title, _) in PROBES.items()]
    built.append(Rule("watchdog_disk", "Sắp hết dung lượng đĩa", lambda status: Reading(not status["probes"]["disk"], f"còn dưới {DISK_CRITICAL_PCT:g}%", Severity.CRITICAL)))
    return built


def check(state_dir: Path, disk_path: Path, environ=os.environ, client: httpx.Client | None = None, now: datetime | None = None,
          usage=shutil.disk_usage) -> list[str]:
    with (client or httpx.Client(trust_env=False)) as http:
        status = {"probes": probe_all(http, disk_path, usage)}
    manager = AlertManager(state_dir, build_notifier(environ), rules=rules())
    return manager.evaluate(status, now=now or datetime.now(timezone.utc))


def unit_failed(unit: str, environ=os.environ, now: datetime | None = None) -> None:
    """One message right away. The unit name is checked so nothing odd from the command line reaches a channel."""
    if not unit.startswith("campus247-") or not unit.replace("-", "").replace(".", "").replace("@", "").isalnum():
        raise SystemExit("not a campus247 unit name")
    build_notifier(environ).send(AlertMessage(f"unit_failed:{unit}", "firing", Severity.CRITICAL, "Một dịch vụ đã dừng hẳn", unit, now or datetime.now(timezone.utc)))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("check", "unit-failed"))
    parser.add_argument("unit", nargs="?")
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--disk-path", type=Path, default=ROOT)
    args = parser.parse_args()
    if args.command == "unit-failed":
        if not args.unit:
            parser.error("unit-failed needs a unit name")
        unit_failed(args.unit)
        return 0
    print(json.dumps({"sent": check(args.state, args.disk_path)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
