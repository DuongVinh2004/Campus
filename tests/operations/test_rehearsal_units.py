"""Static checks of the restore drill's systemd files and wrapper (systemd-analyze is not available on Windows)."""
import configparser
from pathlib import Path

CLOUD = Path(__file__).resolve().parents[2] / "infra/cloud"


def unit(name: str) -> configparser.ConfigParser:
    parser = configparser.ConfigParser(strict=False, interpolation=None)
    parser.optionxform = str
    parser.read(CLOUD / name, encoding="utf-8")
    return parser


def test_the_service_runs_the_wrapper_at_low_priority_as_a_one_shot():
    service = unit("campus247-rehearsal.service")["Service"]
    assert service["Type"] == "oneshot" and service["ExecStart"] == "/usr/local/sbin/campus247-rehearse"
    assert service["Nice"] == "15" and service["IOSchedulingClass"] == "idle"
    assert "postgresql@17-campus247.service" in unit("campus247-rehearsal.service")["Unit"]["After"]


def test_the_timer_runs_monthly_after_the_backup_and_catches_up():
    timer = unit("campus247-rehearsal.timer")
    assert timer["Timer"]["OnCalendar"] == "*-*-01 04:30:00" and timer["Timer"]["Persistent"] == "true"
    assert timer["Install"]["WantedBy"] == "timers.target"


def test_the_wrapper_drills_only_and_never_uses_force():
    text = (CLOUD / "rehearse.sh").read_text(encoding="utf-8")
    assert text.startswith("#!/usr/bin/env bash") and "set -euo pipefail" in text
    assert "rehearse_restore.py" in text and "--force" not in text and "restore.sh" not in text
    assert "--backups /var/backups/campus247" in text
