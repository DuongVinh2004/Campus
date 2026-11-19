"""offsite.py with a fake restic: what it runs, what it refuses, what it records, and that no secret is ever passed on a command line."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("campus_offsite", ROOT / "infra/cloud/offsite.py")
offsite = importlib.util.module_from_spec(spec)
sys.modules["campus_offsite"] = offsite
spec.loader.exec_module(offsite)

SUMMARY = json.dumps({"message_type": "summary", "snapshot_id": "a1b2c3d4", "data_added": 4096})


class FakeRestic:
    def __init__(self, returncode=0, stdout=""):
        self.calls, self.returncode, self.stdout = [], returncode, stdout

    def __call__(self, args, env, timeout):
        self.calls.append((args, env, timeout))
        return subprocess.CompletedProcess(args, self.returncode, self.stdout, "")


@pytest.fixture
def setup(tmp_path):
    backups = tmp_path / "backups"
    folder = backups / "campus247-backup-20261117T030000Z"
    folder.mkdir(parents=True)
    (folder / "MANIFEST.json").write_text("{}", encoding="utf-8")
    (backups / "LAST_BACKUP.json").write_text(json.dumps({"ok": True, "folder": folder.name}), encoding="utf-8")
    password = tmp_path / "restic-password"
    password.write_text("correct horse battery staple", encoding="utf-8")
    password.chmod(0o600)
    environ = {"CAMPUS247_RESTIC_REPOSITORY": "sftp:backup@example.net:/srv/campus247", "RESTIC_PASSWORD_FILE": str(password),
               "RESTIC_PASSWORD": "must-be-dropped", "AWS_ACCESS_KEY_ID": "AKIA-PASSES-THROUGH"}
    return backups, environ


def status(backups, name="OFFSITE.json"):
    return json.loads((backups / name).read_text(encoding="utf-8"))


def test_push_backs_up_the_newest_good_folder_and_records_the_snapshot(setup):
    backups, environ = setup
    fake = FakeRestic(stdout="not json\n" + SUMMARY + "\n")
    record = offsite.execute("push", backups, environ, fake)
    (args, env, timeout), = fake.calls
    assert args == ["restic", "backup", str(backups / "campus247-backup-20261117T030000Z"), "--tag", "daily", "--host", "campus247", "--json"]
    assert env["RESTIC_REPOSITORY"] == environ["CAMPUS247_RESTIC_REPOSITORY"] and env["RESTIC_PASSWORD_FILE"] == environ["RESTIC_PASSWORD_FILE"]
    assert "RESTIC_PASSWORD" not in env and env["AWS_ACCESS_KEY_ID"] == "AKIA-PASSES-THROUGH" and timeout == 6 * 3600
    assert record["ok"] is True and record["snapshot"] == "a1b2c3d4" and record["bytes_added"] == 4096
    assert status(backups) == record


def test_no_secret_is_on_the_command_line_or_in_the_status_file(setup):
    backups, environ = setup
    fake = FakeRestic(stdout=SUMMARY)
    offsite.execute("push", backups, environ, fake)
    everything = json.dumps(fake.calls[0][0]) + (backups / "OFFSITE.json").read_text(encoding="utf-8")
    assert "correct horse" not in everything and "AKIA" not in everything and "sftp:backup@example.net" not in everything


def test_a_failed_last_backup_is_never_copied_off_the_server(setup):
    backups, environ = setup
    (backups / "LAST_BACKUP.json").write_text(json.dumps({"ok": False, "error": "OSError"}), encoding="utf-8")
    fake = FakeRestic()
    record = offsite.execute("push", backups, environ, fake)
    assert fake.calls == [] and record["ok"] is False and record["error"] == "OffsiteError"
    assert status(backups)["ok"] is False


def test_a_missing_status_or_incomplete_folder_is_refused(setup, tmp_path):
    backups, environ = setup
    (backups / "LAST_BACKUP.json").write_text(json.dumps({"ok": True, "folder": "campus247-backup-gone"}), encoding="utf-8")
    assert offsite.execute("push", backups, environ, FakeRestic())["ok"] is False
    (backups / "LAST_BACKUP.json").unlink()
    assert "nothing has been backed up" in offsite.execute("push", backups, environ, FakeRestic())["detail"]


@pytest.mark.parametrize("missing", ["CAMPUS247_RESTIC_REPOSITORY", "RESTIC_PASSWORD_FILE"])
def test_missing_configuration_runs_nothing(setup, missing):
    backups, environ = setup
    environ.pop(missing)
    fake = FakeRestic()
    assert offsite.execute("push", backups, environ, fake)["ok"] is False and fake.calls == []


def test_a_nonexistent_password_file_is_refused(setup, tmp_path):
    backups, environ = setup
    environ["RESTIC_PASSWORD_FILE"] = str(tmp_path / "nope")
    assert offsite.execute("check", backups, environ, FakeRestic())["ok"] is False


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits")
def test_a_password_file_others_can_read_is_refused(setup):
    backups, environ = setup
    Path(environ["RESTIC_PASSWORD_FILE"]).chmod(0o644)
    assert "owner only" in offsite.execute("check", backups, environ, FakeRestic())["detail"]


def test_a_restic_failure_is_recorded_and_not_raised(setup):
    backups, environ = setup
    record = offsite.execute("push", backups, environ, FakeRestic(returncode=1))
    assert record["ok"] is False and "exited with 1" in record["detail"] and status(backups)["ok"] is False


def test_a_timeout_is_recorded_by_type(setup):
    backups, environ = setup

    def slow(args, env, timeout):
        raise subprocess.TimeoutExpired(args, timeout)

    assert offsite.execute("push", backups, environ, slow)["error"] == "TimeoutExpired"


def test_forget_uses_the_agreed_retention_and_check_reads_a_sample(setup):
    backups, environ = setup
    fake = FakeRestic()
    offsite.execute("forget", backups, environ, fake)
    assert fake.calls[0][0] == ["restic", "forget", "--keep-daily", "14", "--keep-weekly", "8", "--keep-monthly", "6", "--prune"]
    offsite.execute("check", backups, environ, fake)
    assert fake.calls[1][0] == ["restic", "check", "--read-data-subset", "5%"]
    assert status(backups, "OFFSITE_CHECK.json")["ok"] is True and not (backups / "OFFSITE.json").exists()


def test_init_writes_no_status_and_a_custom_binary_is_used(setup):
    backups, environ = setup
    environ["CAMPUS247_RESTIC_BIN"] = "/opt/restic/restic"
    fake = FakeRestic()
    assert offsite.execute("init", backups, environ, fake)["ok"] is True
    assert fake.calls[0][0] == ["/opt/restic/restic", "init"] and list(backups.glob("OFFSITE*.json")) == []
