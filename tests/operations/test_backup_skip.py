"""A file the operating system will not let us read must not abort the whole backup, and must never go unmentioned."""
import importlib.util
import json
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("backup_tool", ROOT / "infra/cloud/backup.py")
backup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup)


def files(base: Path, names):
    for name in names:
        yield base / name, Path(name)


def test_an_unreadable_file_is_left_out_named_and_the_rest_is_packed(tmp_path):
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "c.txt").write_text("c")
    skipped: list[str] = []
    count = backup.add_tar(tmp_path / "x.tar.gz", tmp_path, files(tmp_path, ["a.txt", "missing.txt", "c.txt"]), skipped)
    assert count == 2 and skipped == ["missing.txt (FileNotFoundError)"]
    with tarfile.open(tmp_path / "x.tar.gz") as tar:
        assert sorted(tar.getnames()) == ["a.txt", "c.txt"]


def test_without_a_skipped_list_the_error_still_stops_the_backup(tmp_path):
    with pytest.raises(OSError):
        backup.add_tar(tmp_path / "x.tar.gz", tmp_path, files(tmp_path, ["missing.txt"]))


def test_the_status_record_counts_skipped_files(tmp_path):
    folder = tmp_path / "campus247-backup-20261119T000000Z"
    folder.mkdir()
    (folder / "MANIFEST.json").write_text(json.dumps({"schema": "campus247-backup-v1", "skipped_unreadable": ["x (OSError)", "y (OSError)"]}), encoding="utf-8")
    record = backup.write_status(tmp_path, ok=True, started=0.0, folder=folder)
    assert record["skipped_files"] == 2
