"""The supervised ClamAV daemon: configuration, pinned binaries, launcher wiring and no orphan on a hard kill."""
import json
import os
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import clamd_service  # noqa: E402

pytestmark = pytest.mark.skipif(os.name != "nt", reason="The supervised daemon is the Windows runtime; Linux uses packaged units")


def test_the_daemon_listens_on_loopback_only_and_alerts_on_exceeded_limits(tmp_path, monkeypatch):
    monkeypatch.setattr(clamd_service, "SEED_DATABASE", tmp_path / "seed")
    (tmp_path / "seed").mkdir()
    (tmp_path / "seed" / "daily.cvd").write_bytes(b"x")
    service = tmp_path / "service"
    clamd_service.prepare(service)
    conf = (service / "clamd.conf").read_text()
    assert "TCPAddr 127.0.0.1" in conf and "TCPSocket 33100" in conf
    for required in ("AlertExceedsMax yes", "StreamMaxLength 105M", "ConcurrentDatabaseReload no", "Foreground yes", "MaxRecursion 16"):
        assert required in conf
    fresh = (service / "freshclam.conf").read_text()
    assert "CVDCertsDirectory" in fresh and "DatabaseMirror database.clamav.net" in fresh
    assert (service / "database" / "daily.cvd").read_bytes() == b"x"  # copied, the retained seed is untouched
    again = clamd_service.prepare(service)  # idempotent, never copies over an existing database
    (service / "database" / "daily.cvd").write_bytes(b"newer")
    clamd_service.prepare(service)
    assert (service / "database" / "daily.cvd").read_bytes() == b"newer" and again["database"].endswith("database")


def test_both_executables_are_pinned_and_a_changed_binary_is_refused(tmp_path, monkeypatch):
    assert clamd_service.PORTABLE.is_dir(), "the retained ClamAV bundle must be present"
    clamd_service.verify_binaries()  # the real files match their pins
    fake = tmp_path / "bundle"
    fake.mkdir()
    for name in clamd_service.PINS:
        (fake / name).write_bytes(b"tampered")
    monkeypatch.setattr(clamd_service, "PORTABLE", fake)
    with pytest.raises(RuntimeError, match="pinned checksum"):
        clamd_service.verify_binaries()


def test_the_seed_database_is_never_modified_by_prepare(tmp_path):
    before = {p.name: p.stat().st_mtime_ns for p in clamd_service.SEED_DATABASE.iterdir()}
    clamd_service.prepare(tmp_path / "service")
    assert {p.name: p.stat().st_mtime_ns for p in clamd_service.SEED_DATABASE.iterdir()} == before


def test_the_launcher_starts_the_scanner_unless_the_operator_switches_it_off(monkeypatch):
    import knowledge_platform_runtime as launcher

    monkeypatch.delenv("CAMPUS_SCANNER_ENABLED", raising=False)
    assert launcher.scanner_wanted() is True
    for value in ("false", "FALSE"):
        monkeypatch.setenv("CAMPUS_SCANNER_ENABLED", value)
        assert launcher.scanner_wanted() is False
    for value in ("true", "1", ""):
        monkeypatch.setenv("CAMPUS_SCANNER_ENABLED", value)
        assert launcher.scanner_wanted() is True


def test_the_launcher_recognises_its_scanner_process_and_nothing_else(monkeypatch):
    import knowledge_platform_runtime as launcher

    rows = [{"ProcessId": 11, "CommandLine": '"C:/x/python.exe" -B -u scripts/clamd_service.py serve'},
            {"ProcessId": 12, "CommandLine": '"C:/x/python.exe" -B -u scripts/clamd_service.py status'},
            {"ProcessId": 13, "CommandLine": '"C:/x/python.exe" -B -u scripts/gateway_sidecar.py serve'}]
    assert launcher.matching_processes(rows, "scanner") == [11]
    assert 11 not in launcher.matching_processes(rows, "gateway")


def test_the_default_learning_configuration_runs_the_scanner_daemon():
    config = json.loads((ROOT / "infra/local/learning-materials-20261104-01/config-clamd-20261117.json").read_text())
    assert config["scanner_mode"] == "clamd" and config["scanner_port"] == clamd_service.PORT
    assert config["scanner_host"] == "127.0.0.1" and "scanner_executable" not in config


def test_killing_the_supervisor_takes_the_daemon_down_with_it(tmp_path):
    """A hard kill must not leave an orphan holding the scanner port (the problem the API workers had)."""
    script = tmp_path / "parent.py"
    script.write_text(textwrap.dedent(f"""
        import subprocess, sys, time
        sys.path.insert(0, {str(ROOT / "scripts")!r})
        import clamd_service
        job = clamd_service.Job()
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
        job.add(child)
        print(child.pid, flush=True)
        time.sleep(120)
    """), encoding="utf-8")
    parent = subprocess.Popen([sys.executable, str(script)], stdout=subprocess.PIPE, text=True)
    try:
        child_pid = int(parent.stdout.readline())
        assert _alive(child_pid)
        parent.kill()
        parent.wait()
        deadline = time.time() + 10
        while time.time() < deadline and _alive(child_pid):
            time.sleep(0.2)
        assert not _alive(child_pid)
    finally:
        parent.kill()


def _alive(pid: int) -> bool:
    out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True).stdout
    return str(pid) in out
