"""infra/cloud/backup.py records the outcome of each backup so the operations page and the alerts can read it."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("campus_backup", ROOT / "infra/cloud/backup.py")
backup = importlib.util.module_from_spec(spec)
sys.modules["campus_backup"] = backup
spec.loader.exec_module(backup)


def fake_backup_folder(out: Path) -> Path:
    folder = out / "campus247-backup-20261117T030000Z"
    folder.mkdir(parents=True)
    (folder / "MANIFEST.json").write_text(json.dumps({"schema": "campus247-backup-v1", "parts": {}}), encoding="utf-8")
    (folder / "postgres.dump").write_bytes(b"x" * 1234)
    return folder


def test_a_successful_backup_is_recorded_with_size_checksum_and_no_secret(tmp_path):
    folder = fake_backup_folder(tmp_path)
    record = backup.write_status(tmp_path, ok=True, started=0.0, folder=folder)
    stored = json.loads((tmp_path / "LAST_BACKUP.json").read_text(encoding="utf-8"))
    assert stored == record
    assert stored["ok"] is True and stored["verified"] is True and stored["folder"] == folder.name
    assert stored["bytes"] >= 1234 and len(stored["manifest_sha256"]) == 64
    assert stored["finished_at"].endswith("Z") and "error" not in stored
    assert not list(tmp_path.glob("*.tmp"))


def test_a_failed_backup_is_recorded_by_error_type_only(tmp_path):
    backup.write_status(tmp_path, ok=False, started=0.0, error="CalledProcessError")
    stored = json.loads((tmp_path / "LAST_BACKUP.json").read_text(encoding="utf-8"))
    assert stored["ok"] is False and stored["error"] == "CalledProcessError" and "folder" not in stored


def test_the_next_attempt_replaces_the_record(tmp_path):
    backup.write_status(tmp_path, ok=False, started=0.0, error="OSError")
    backup.write_status(tmp_path, ok=True, started=0.0, folder=fake_backup_folder(tmp_path))
    assert json.loads((tmp_path / "LAST_BACKUP.json").read_text(encoding="utf-8"))["ok"] is True


def run_main(monkeypatch, argv, **replace):
    monkeypatch.setattr(sys, "argv", ["backup.py", *argv])
    for name, value in replace.items():
        monkeypatch.setattr(backup, name, value)
    backup.main()


def test_main_writes_ok_after_backup_and_verify(monkeypatch, tmp_path, capsys):
    out = tmp_path / "out"
    run_main(monkeypatch, ["backup", "--out", str(out), "--root", str(tmp_path)],
             backup=lambda root, out_, pg, keep, creds: fake_backup_folder(out_),
             verify=lambda folder: {"parts": {"postgres.dump": "abc"}})
    assert json.loads((out / "LAST_BACKUP.json").read_text(encoding="utf-8"))["ok"] is True
    assert "postgres.dump" in capsys.readouterr().out


@pytest.mark.parametrize("failure", [OSError("disk"), SystemExit("checksum mismatch: postgres.dump")])
def test_main_records_a_failure_and_still_raises(monkeypatch, tmp_path, failure):
    out = tmp_path / "out"

    def broken(*args, **kwargs):
        raise failure

    with pytest.raises(type(failure)):
        run_main(monkeypatch, ["backup", "--out", str(out), "--root", str(tmp_path)], backup=broken)
    stored = json.loads((out / "LAST_BACKUP.json").read_text(encoding="utf-8"))
    assert stored["ok"] is False and stored["error"] == type(failure).__name__


def test_status_command_prints_the_record_or_says_nothing_ran(monkeypatch, tmp_path, capsys):
    with pytest.raises(SystemExit, match="no backup has run"):
        run_main(monkeypatch, ["status", "--out", str(tmp_path)])
    backup.write_status(tmp_path, ok=True, started=0.0)
    run_main(monkeypatch, ["status", "--out", str(tmp_path)])
    assert json.loads(capsys.readouterr().out)["ok"] is True


def test_operations_snapshots_are_not_saved_in_the_state_archive(tmp_path):
    state = tmp_path / backup.STATE_REL
    (state / "ops-metrics").mkdir(parents=True)
    (state / "ops-metrics" / "worker-1.json").write_text("{}", encoding="utf-8")
    (state / "ops-alerts").mkdir()
    (state / "ops-alerts" / "state.json").write_text("{}", encoding="utf-8")
    (state / "owner-identity.json").write_text("{}", encoding="utf-8")
    assert [str(rel).replace("\\", "/") for _, rel in backup.state_files(tmp_path)] == ["owner-identity.json"]
