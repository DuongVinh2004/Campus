"""The restore drill: order of steps, what it records, and that it removes only what it created, even when a step fails."""
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("campus_rehearse", ROOT / "infra/cloud/rehearse_restore.py")
rehearse_module = importlib.util.module_from_spec(spec)
sys.modules["campus_rehearse"] = rehearse_module
spec.loader.exec_module(rehearse_module)
rehearse, Steps = rehearse_module.rehearse, rehearse_module.Steps

NOW = lambda: datetime(2026, 11, 17, 3, 0, 0, tzinfo=timezone.utc)  # noqa: E731
TABLES = {"documents": 114, "conversations": 20}


class Recorder:
    def __init__(self, **overrides):
        self.calls, self.overrides = [], overrides

    def make(self) -> "Steps":
        def wrap(name, default):
            def call(*args):
                self.calls.append(name)
                if name in self.overrides:
                    outcome = self.overrides[name]
                    if isinstance(outcome, BaseException):
                        raise outcome
                    return outcome
                return default(*args) if callable(default) else default
            return call

        return Steps(
            verify=wrap("verify", {"schema": "campus247-backup-v1"}),
            create_database=wrap("create_database", None),
            restore=wrap("restore", lambda folder, root, database: (root / "restored.txt").write_text("x") or {}),
            live_tables=wrap("live_tables", dict(TABLES)),
            restored_tables=wrap("restored_tables", dict(TABLES) | {"documents": 110}),  # fewer rows: taken before newer writes
            sqlite_check=wrap("sqlite_check", {"conversations.sqlite3": "ok"}),
            drop_database=wrap("drop_database", None),
        )


@pytest.fixture
def folders(tmp_path):
    backups = tmp_path / "backups"
    for stamp in ("20261115T030000Z", "20261116T030000Z"):
        folder = backups / f"campus247-backup-{stamp}"
        folder.mkdir(parents=True)
        (folder / "MANIFEST.json").write_text("{}", encoding="utf-8")
    (backups / "campus247-backup-20261117T030000Z").mkdir()  # incomplete: no manifest, must be ignored
    return backups, tmp_path / "work"


def status(backups):
    return json.loads((backups / "REHEARSAL.json").read_text(encoding="utf-8"))


def test_a_good_drill_passes_records_each_step_and_cleans_up(folders):
    backups, work = folders
    recorder = Recorder()
    record = rehearse(backups=backups, work_dir=work, steps=recorder.make(), now=NOW)
    assert record["ok"] is True and record["backup"] == "campus247-backup-20261116T030000Z"
    assert record["database"] == "campus247_rehearsal_20261117030000"
    assert recorder.calls == ["verify", "create_database", "restore", "live_tables", "restored_tables", "sqlite_check", "drop_database"]
    assert [s["name"] for s in record["steps"]] == ["pick", "verify", "create_database", "restore", "live_tables", "restored_tables",
                                                    "compare_tables", "sqlite_integrity"]
    assert all(s["ok"] for s in record["steps"])
    assert record["cleanup"] == ["database_dropped", "root_removed"]
    assert list(work.iterdir()) == []
    assert status(backups)["ok"] is True and record["row_counts"]["restored"]["documents"] == 110


def test_a_failing_restore_still_drops_the_database_and_removes_the_root(folders):
    backups, work = folders
    recorder = Recorder(restore=OSError("disk full"))
    record = rehearse(backups=backups, work_dir=work, steps=recorder.make(), now=NOW)
    assert record["ok"] is False and record["error"] == "OSError"
    assert [s["ok"] for s in record["steps"]][-1] is False
    assert recorder.calls[-1] == "drop_database" and "live_tables" not in recorder.calls
    assert record["cleanup"] == ["database_dropped", "root_removed"] and list(work.iterdir()) == []
    assert status(backups)["ok"] is False


def test_different_table_sets_fail_and_say_which(folders):
    backups, work = folders
    record = rehearse(backups=backups, work_dir=work, steps=Recorder(restored_tables={"documents": 1}).make(), now=NOW)
    assert record["ok"] is False
    failure = [s for s in record["steps"] if s["name"] == "compare_tables"][0]
    assert failure["missing"] == ["conversations"] and failure["extra"] == []


def test_a_damaged_sqlite_store_fails(folders):
    backups, work = folders
    record = rehearse(backups=backups, work_dir=work, steps=Recorder(sqlite_check={"actor-state.sqlite3": "database disk image is malformed"}).make(), now=NOW)
    assert record["ok"] is False and [s for s in record["steps"] if s["name"] == "sqlite_result"][0]["stores"] == ["actor-state.sqlite3"]


def test_no_backup_means_no_database_is_ever_created(folders):
    backups, work = folders
    empty = backups.parent / "empty"
    empty.mkdir()
    recorder = Recorder()
    record = rehearse(backups=empty, work_dir=work, steps=recorder.make(), now=NOW)
    assert record["ok"] is False and recorder.calls == []
    assert record["cleanup"] == ["root_removed"] and list(work.iterdir()) == []


def test_a_checksum_failure_stops_before_anything_is_restored(folders):
    backups, work = folders
    recorder = Recorder(verify=SystemExit("checksum mismatch: postgres.dump"))
    record = rehearse(backups=backups, work_dir=work, steps=recorder.make(), now=NOW)
    assert record["ok"] is False and record["error"] == "SystemExit" and recorder.calls == ["verify"]


def test_failing_to_drop_the_database_fails_the_drill_and_is_visible(folders):
    backups, work = folders
    record = rehearse(backups=backups, work_dir=work, steps=Recorder(drop_database=RuntimeError("busy")).make(), now=NOW)
    assert record["ok"] is False and record["cleanup"] == ["database_drop_failed:RuntimeError", "root_removed"]


def test_only_the_drills_own_directory_is_removed(folders):
    backups, work = folders
    work.mkdir()
    (work / "keep-me").mkdir()
    (work / "keep-me" / "important.txt").write_text("data", encoding="utf-8")
    rehearse(backups=backups, work_dir=work, steps=Recorder().make(), now=NOW)
    assert (work / "keep-me" / "important.txt").read_text(encoding="utf-8") == "data"


def test_the_real_drop_step_refuses_names_that_are_not_rehearsal_databases(tmp_path):
    (tmp_path / "x").mkdir()
    sys.path.insert(0, str(ROOT / "infra/cloud"))
    import backup as backup_tool  # noqa: F401

    original = backup_tool.connection
    backup_tool.connection = lambda root: {"host": "h", "port": 1, "user": "u", "password": "p", "database": "campus"}
    try:
        steps = rehearse_module.real_steps(tmp_path, None, None)
        with pytest.raises(rehearse_module.RehearsalError):
            steps.drop_database("campus247")
    finally:
        backup_tool.connection = original


def test_a_relative_work_directory_works_like_an_absolute_one(tmp_path, monkeypatch):
    """mkdtemp returns an absolute path, so the safety comparison must not fail for a relative --work-dir (it did on Windows)."""
    backups = tmp_path / "backups"
    backups.mkdir()
    folder = backups / "campus247-backup-20261119T000000Z"
    folder.mkdir()
    (folder / "MANIFEST.json").write_text("{}", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    record = rehearse(backups=backups, work_dir=Path("work"), steps=Recorder().make(), now=NOW)
    assert record["ok"] is True and "AssertionError" not in json.dumps(record)
