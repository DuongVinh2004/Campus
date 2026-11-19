"""Deployment kit: rendered units follow the profile, backup round-trips, ledger compaction never loses a byte."""
import io
import json
import os
import sqlite3
import subprocess
import sys
import tarfile
import time
from dataclasses import replace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "infra/cloud"))

import backup as backup_tool  # noqa: E402
import compact_ledgers as compactor  # noqa: E402
import render_units  # noqa: E402
from runtime_profile import load_profile  # noqa: E402


def render(profile="cloud"):
    return render_units.units(load_profile(profile), "/opt/campus247", "campus247", "/opt/campus247/.venv/bin/python",
                              "/usr/local/bin/node")


def test_units_carry_the_profile_values():
    cloud, units = load_profile("cloud"), render()
    api = units["campus247-api.service"]
    assert f"--workers {cloud.api_workers}" in api and f"CAMPUS247_CHAT_MAX_IN_FLIGHT={cloud.max_in_flight_per_worker}" in api
    assert "CAMPUS247_RATE_LIMIT_STORE=postgres" in api and "CAMPUS247_GATEWAY_URL=http://127.0.0.1:8025" in api
    gateway = units["campus247-gateway.service"]
    assert f"--concurrency {cloud.provider_concurrency}" in gateway and f"--daily-usd-cap {cloud.daily_usd_cap}" in gateway
    assert float(cloud.daily_usd_cap) > 0 and f"--daily-call-cap {cloud.daily_call_cap}" in gateway


def test_units_keep_secrets_out_and_services_hardened():
    for name, text in render().items():
        assert "API_KEY" not in text.upper() and "PASSWORD" not in text.upper(), name
        assert "EnvironmentFile=/etc/campus247/campus247.env" in text and "NoNewPrivileges=true" in text
        assert "ProtectSystem=strict" in text and "0.0.0.0" not in text


def test_one_worker_profile_does_not_pass_workers_flag():
    units = render_units.units(replace(load_profile("local"), api_workers=1), "/r", "u", "/p", "/n")
    assert "--workers" not in units["campus247-api.service"]


def test_caddy_exposes_only_https_and_install_opens_only_22_and_443():
    caddy = (ROOT / "infra/cloud/Caddyfile.example").read_text(encoding="utf-8")
    # The API is the single browser origin (it serves /v1 and /health and proxies the pages); 3015 would 404 on both.
    assert "reverse_proxy 127.0.0.1:8015" in caddy and "reverse_proxy 127.0.0.1:3015" not in caddy
    assert "auto_https disable_redirects" in caddy
    install = (ROOT / "infra/cloud/install.sh").read_text(encoding="utf-8")
    assert "ufw allow 22/tcp" in install and "ufw allow 443/tcp" in install and "ufw allow 80" not in install
    assert "set -euo pipefail" in install


def make_runtime(root: Path):
    state, ledger = root / backup_tool.STATE_REL, root / backup_tool.LEDGER_REL
    state.mkdir(parents=True)
    ledger.mkdir(parents=True)
    (state / "owner-identity.json").write_text('{"x":1}', encoding="utf-8")
    (state / "confirmation-signing.key").write_text("k" * 64, encoding="ascii")
    (state / "notes.png").write_bytes(b"png")
    (state / "student-credentials.json").write_text('{"password":"plain"}')
    (state / "bootstrap-password.txt").write_text("plain")
    (state / "resume-20261115").mkdir()
    (state / "resume-20261115" / "api.log").write_text("log")
    (state / "artifacts").mkdir()
    (state / "artifacts" / "a.bin").write_bytes(b"artifact")
    db = sqlite3.connect(state / "conversations.sqlite3")
    db.execute("CREATE TABLE t(a)")
    db.execute("INSERT INTO t VALUES (42)")
    db.commit()
    db.close()
    (state / "local-connection.json").write_text(json.dumps(
        {"host": "127.0.0.1", "port": 1, "database": "d", "user": "u", "password": "p"}), encoding="utf-8")
    for i in range(10):
        (ledger / f"provider-{i:05d}-result.json").write_text(f"r{i}")
    (ledger / "authorized-cap.json").write_text("{}")


def fake_pg(calls):
    def run(tool, args, conn):
        calls.append((tool, args))
        if "-f" in args:
            Path(args[args.index("-f") + 1]).write_bytes(b"DUMP")
    return run


def test_backup_parts_are_verified_and_selective(tmp_path, monkeypatch):
    root = tmp_path / "rt"
    make_runtime(root)
    monkeypatch.setattr(backup_tool, "run_pg", fake_pg([]))
    monkeypatch.setattr(backup_tool, "LEDGER_KEEP", 4)
    folder = backup_tool.backup(root, tmp_path / "out", None, keep=14)
    manifest = backup_tool.verify(folder)
    with tarfile.open(folder / "state.tar.gz") as tar:
        names = set(tar.getnames())
    assert {"owner-identity.json", "artifacts/a.bin", "confirmation-signing.key"} <= names
    assert "notes.png" not in names and not any("resume-" in n or n.endswith(".sqlite3") for n in names)
    assert "student-credentials.json" not in names and "bootstrap-password.txt" not in names   # plaintext passwords stay out
    again = backup_tool.backup(root, tmp_path / "out2", None, keep=14, with_credentials=True)
    with tarfile.open(again / "state.tar.gz") as tar:
        assert "student-credentials.json" in set(tar.getnames())
    with tarfile.open(folder / "ledger.tar.gz") as tar:
        ledger = set(tar.getnames())
    assert "authorized-cap.json" in ledger and sum(n.startswith("provider-") for n in ledger) == 4
    assert "provider-00009-result.json" in ledger and "provider-00000-result.json" not in ledger
    (folder / "sqlite" / "conversations.sqlite3").write_bytes(b"tampered")
    with pytest.raises(SystemExit, match="checksum"):
        backup_tool.verify(folder)
    assert manifest["schema"] == "campus247-backup-v1"


def test_restore_reproduces_state_and_refuses_to_overwrite(tmp_path, monkeypatch):
    source, target = tmp_path / "src", tmp_path / "dst"
    make_runtime(source)
    (target / backup_tool.STATE_REL).mkdir(parents=True)
    for name in ("local-connection.json", "owner-identity.json"):
        (target / backup_tool.STATE_REL / name).write_text((source / backup_tool.STATE_REL / name).read_text())
    calls = []
    monkeypatch.setattr(backup_tool, "run_pg", fake_pg(calls))
    folder = backup_tool.backup(source, tmp_path / "out", None, keep=14)
    # an identity file already exists in the target, so a plain restore of the state files must refuse
    with pytest.raises(SystemExit, match="refusing"):
        backup_tool.restore(folder, target, None, force=False)
    result = backup_tool.restore(folder, target, None, force=True)
    assert result["state_files"] >= 3
    restored = target / backup_tool.STATE_REL
    assert (restored / "confirmation-signing.key").read_text() == "k" * 64
    db = sqlite3.connect(restored / "conversations.sqlite3")
    assert db.execute("SELECT a FROM t").fetchone() == (42,)
    db.close()
    assert any("pg_restore" in str(call[0]) for call in calls)


def test_archive_extraction_rejects_paths_outside_the_target(tmp_path):
    evil = tmp_path / "evil.tar.gz"
    with tarfile.open(evil, "w:gz") as tar:
        info = tarfile.TarInfo("../escape.txt")
        info.size = 1
        tar.addfile(info, io.BytesIO(b"x"))
    with pytest.raises(SystemExit, match="unsafe"):
        backup_tool.safe_extract(evil, tmp_path / "dest", force=False)
    assert not (tmp_path / "escape.txt").exists()


def test_compaction_archives_old_files_byte_for_byte_and_keeps_the_newest(tmp_path):
    now = time.time()
    for i in range(12):
        path = tmp_path / f"provider-{i:05d}-result.json"
        path.write_text(f"record {i}")
        age = (30 - i) * 86400 if i < 8 else 0
        os.utime(path, (now - age, now - age))
    (tmp_path / "authorized-cap.json").write_text("keep")
    days = compactor.plan(tmp_path, "provider-*.json", keep_newest=4, older_than_days=2)
    assert sum(len(v) for v in days.values()) == 8
    originals = {p.name: p.read_bytes() for paths in days.values() for p in paths}
    for day, paths in days.items():
        compactor.archive_day(tmp_path, day, paths, "provider")
        for path in paths:
            path.unlink()
    restored = {}
    for archive in (tmp_path / "archive").glob("*.tar.gz"):
        with tarfile.open(archive) as tar:
            restored.update({m.name: tar.extractfile(m).read() for m in tar.getmembers()})
    assert restored == originals
    assert (tmp_path / "authorized-cap.json").exists() and len(list(tmp_path.glob("provider-*.json"))) == 4


def test_compaction_dry_run_changes_nothing(tmp_path):
    for i in range(3):
        path = tmp_path / f"provider-{i:05d}-r.json"
        path.write_text("x")
        os.utime(path, (1, 1))
    out = subprocess.run([sys.executable, "-B", str(ROOT / "infra/cloud/compact_ledgers.py"), "--dir", str(tmp_path),
                          "--pattern", "provider-*.json", "--keep-newest", "1"], capture_output=True, text=True, check=True).stdout
    assert json.loads(out)["dry_run"] is True and len(list(tmp_path.glob("provider-*.json"))) == 3


def test_environment_specific_connection_file_is_not_backed_up(tmp_path, monkeypatch):
    root = tmp_path / "rt"
    make_runtime(root)
    monkeypatch.setattr(backup_tool, "run_pg", fake_pg([]))
    folder = backup_tool.backup(root, tmp_path / "out", None, keep=14)
    with tarfile.open(folder / "state.tar.gz") as tar:
        assert "local-connection.json" not in set(tar.getnames())


def test_database_replacement_needs_force(tmp_path, monkeypatch):
    calls = []

    def fake_admin(admin, pg_bin, port, sql, database="postgres"):
        calls.append(sql)
        return "1" if "pg_database" in sql else ("5" if "pg_tables" in sql else "")

    monkeypatch.setattr(backup_tool, "admin_sql", fake_admin)
    conn = {"host": "h", "port": 55437, "database": "d", "user": "u", "password": "p"}
    with pytest.raises(SystemExit, match="already has 5 tables"):
        backup_tool.restore_database_as_admin(tmp_path, conn, None, ["runuser", "-u", "postgres", "--"], force=False)
    assert not any("DROP" in sql for sql in calls)


def test_backup_keeps_the_reservation_records_of_unsettled_attempts(tmp_path, monkeypatch):
    root = tmp_path / "rt"
    make_runtime(root)
    ledger = root / backup_tool.LEDGER_REL
    for path in ledger.glob("provider-*"):
        path.unlink()
    snapshot = {"calls": 50, "unsettled_attempts_retained": [3, 4]}
    for i in range(3, 12):
        (ledger / f"provider-{i:05d}-reservation.json").write_text(json.dumps({"stage": "reservation", "snapshot": {**snapshot, "calls": i}}))
        (ledger / f"provider-{i:05d}-result.json").write_text(json.dumps({"stage": "result", "snapshot": {**snapshot, "calls": i + 40}}))
    monkeypatch.setattr(backup_tool, "LEDGER_KEEP", 4)
    names = {relative.name for _, relative in backup_tool.ledger_files(root)}
    assert {"provider-00003-reservation.json", "provider-00004-reservation.json"} <= names   # old but still pending
    assert "provider-00011-result.json" in names and "provider-00005-reservation.json" not in names


def test_api_unit_wires_the_packaged_scanner_through_a_group_and_the_shared_environment_names():
    api = render()["campus247-api.service"]
    assert "clamav-daemon.service" in api.split("[Service]")[0]  # ordered after it and wants it, but does not require it
    assert "Requires=campus247-gateway.service" in api and "Requires=clamav-daemon" not in api
    assert "SupplementaryGroups=clamav" in api and "CAMPUS247_PROFILE=cloud" in api
    assert "CAMPUS_LEARNING_ENABLED=false" in api
    # The names in the unit are exactly the ones the application reads, and the cloud profile refuses to run without them.
    sys.path.insert(0, str(ROOT / "services/api/src"))
    from campus247.bootstrap.scanner import scanner_from_environment
    environ = dict(line.removeprefix("Environment=").split("=", 1) for line in api.splitlines() if line.startswith("Environment="))
    scanner = scanner_from_environment(environ)
    assert scanner.socket_path == "/run/clamav/clamd.ctl" and scanner.max_database_age.total_seconds() == 72 * 3600
    environ.pop("CAMPUS247_SCANNER_SOCKET")
    with pytest.raises(ValueError, match="cloud profile requires"):
        scanner_from_environment(environ)


def test_clamd_kit_is_socket_only_bounded_and_matches_the_client_limits():
    conf = (ROOT / "infra/cloud/clamav/clamd.conf").read_text(encoding="utf-8")
    assert "LocalSocket /run/clamav/clamd.ctl" in conf and "LocalSocketMode 660" in conf and "LocalSocketGroup clamav" in conf
    assert "TCPSocket" not in conf and "TCPAddr" not in conf
    for line in ("AlertExceedsMax yes", "ConcurrentDatabaseReload no", "MaxRecursion 16", "StreamMaxLength 105M", "MaxFileSize 100M"):
        assert line in conf
    sys.path.insert(0, str(ROOT / "services/api/src"))
    from campus247.infrastructure.scanning.clamd import ClamdScanner
    assert ClamdScanner(socket_path="/x").max_bytes <= 100 * 1024**2  # the client never sends more than clamd will take
    override = (ROOT / "infra/cloud/clamav/clamav-daemon.override.conf").read_text(encoding="utf-8")
    assert "MemoryMax=1500M" in override and "Restart=always" in override
    # The local and cloud profiles budget the daemon's measured ~960 MB.
    assert load_profile("cloud").scanner_mb >= 960 and load_profile("local").scanner_mb >= 960


def test_install_gets_signatures_before_starting_clamd_and_never_opens_a_scanner_port():
    install = (ROOT / "infra/cloud/install.sh").read_text(encoding="utf-8")
    assert "clamav-daemon clamav-freshclam" in install
    assert install.index("freshclam --quiet") < install.index("systemctl enable --now clamav-freshclam clamav-daemon")
    assert "/etc/clamav/clamd.conf.distribution" in install  # the distribution file is kept before it is replaced
    assert "ufw allow 3310" not in install and "ufw allow 33100" not in install
    ready = (ROOT / "infra/cloud/wait_scanner.sh").read_text(encoding="utf-8")
    assert "AF_UNIX" in ready and "PONG" in ready


def test_every_shell_script_and_linux_config_in_the_kit_uses_unix_line_endings():
    """A CRLF in a script fails on the VM with `bash\r: No such file or directory`; git normalizes on commit, a copied tree does not."""
    for path in sorted((ROOT / "infra/cloud").rglob("*")):
        if path.is_file() and path.suffix in {".sh", ".conf", ".service", ".timer"}:
            assert b"\r" not in path.read_bytes(), f"{path.relative_to(ROOT)} has CRLF line endings"


def test_the_vm_acceptance_script_exists_and_measures_what_the_design_left_open():
    script = (ROOT / "infra/cloud/verify_scanner.sh").read_text(encoding="utf-8")
    for needle in ("MemAvailable", "scanner_soak.py", "--reload-every", "upload-scanner", "EICAR", "no TCP listener", "MIN_AVAILABLE_MB"):
        assert needle in script, needle
    assert (ROOT / "scripts/scanner_soak.py").is_file()
    readme = (ROOT / "infra/cloud/README.md").read_text(encoding="utf-8")
    assert "verify_scanner.sh" in readme
