"""Restore watermark mechanism in new retained SQLite stores only."""
import json
import os
import sqlite3
from uuid import uuid4

import pytest


def test_sqlite_read_snapshot_detects_concurrent_commits_after_backup(retained_directory):
    from knowledge_automation_restore_bundle import new_database, sqlite_fingerprint
    path = retained_directory / "source.sqlite3"
    writer = new_database(path)
    writer.execute("PRAGMA journal_mode=WAL")
    writer.execute("CREATE TABLE receipt(id TEXT PRIMARY KEY,payload BLOB)")
    writer.execute("INSERT INTO receipt VALUES(?,?)",("original",b"Preserve original receipt")); writer.commit()
    source = sqlite3.connect(path.as_uri()+"?mode=ro",uri=True)
    source.execute("PRAGMA query_only=ON")
    before = source.execute("PRAGMA data_version").fetchone()[0]
    source.execute("BEGIN")
    original = sqlite_fingerprint(source)
    backup = new_database(retained_directory / "backup.sqlite3")
    try:
        source.backup(backup)
        assert sqlite_fingerprint(backup) == original
        writer.execute("INSERT INTO receipt VALUES(?,?)",("concurrent",b"Append only concurrent event")); writer.commit()
        assert sqlite_fingerprint(source) == original  # Reader retains its pinned cut.
        source.rollback()
        assert source.execute("PRAGMA data_version").fetchone()[0] != before
        assert sqlite_fingerprint(source) != original
        assert sqlite_fingerprint(backup) == original  # Evidence stays intact.
    finally:
        backup.close(); source.close(); writer.close()


@pytest.mark.skipif(not os.environ.get("KNOWLEDGE_AUTOMATION_BUNDLE"),reason="Exact retained complete restore bundle required")
def test_complete_bundle_has_no_current_storage_fallback(retained_directory):
    from knowledge_platform import ROOT, STATE, checked_path, rehearsal_bundle_paths, retain
    manifest = checked_path(ROOT / os.environ["KNOWLEDGE_AUTOMATION_BUNDLE"],ROOT)
    paths = rehearsal_bundle_paths(manifest)
    assert paths and all(path.is_relative_to(manifest.parent) for path in paths.values())
    assert paths["actor-state.sqlite3"] != STATE / "actor-state.sqlite3"
    value = json.loads(manifest.read_text(encoding="utf-8"))
    value["restored_sqlite"]["actor-state.sqlite3"] = str(STATE / "actor-state.sqlite3")
    rejected = checked_path(manifest.parent / ("negative-bundle-binding-"+uuid4().hex+".json"),ROOT)
    retain(rejected,value)
    with pytest.raises(ValueError,match="outside the exact bundle"):
        rehearsal_bundle_paths(rejected)
