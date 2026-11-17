"""Several API processes share the SQLite stores: no lost record and no 'database is locked' under concurrent writes.

Step 1.4 of the rollout plan. Each store is hammered by 3 real processes at once (the cloud profile runs 2 API workers
and local runs up to 3, all on the same files). The counts are exact: every write a process reports as done must be in
the database afterwards, and a race on one key must have exactly one winner.
"""
import json
import sqlite3
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
WORKER = Path(__file__).with_name("sqlite_concurrency_worker.py")
PROCESSES, WRITES = 3, 40


def run_workers(store: str, database: Path, modes=None):
    """Start all workers together; return their parsed reports."""
    modes = modes or [store] * PROCESSES
    procs = [subprocess.Popen([sys.executable, "-B", str(WORKER), mode, str(database), str(i), str(WRITES)],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=ROOT)
             for i, mode in enumerate(modes)]
    reports = []
    for proc in procs:
        out, err = proc.communicate(timeout=240)
        assert proc.returncode == 0, err[-800:]
        reports.append(json.loads(out.strip().splitlines()[-1]))
    return reports


def count(database: Path, sql: str):
    with sqlite3.connect(database) as conn:
        return conn.execute(sql).fetchone()[0]


@pytest.fixture
def database():
    # The stores only open files inside the workspace, so the test directory must be below it.
    base = ROOT / ".pytest-tmp-sqlite-multiprocess"
    folder = base / uuid.uuid4().hex[:12]
    folder.mkdir(parents=True)
    yield folder
    shutil.rmtree(folder, ignore_errors=True)
    try:
        base.rmdir()
    except OSError:
        pass  # another test still has its folder


def init(code: str, path: Path):
    subprocess.run([sys.executable, "-B", "-c", code], check=True, cwd=ROOT, capture_output=True,
                   env={**os.environ, "PYTHONPATH": os.pathsep.join([str(ROOT / "services/api/src"), str(ROOT / "packages/synthetic/src")])})


def test_conversations_lose_nothing_with_concurrent_writers_and_readers(database):
    path = database / "conversations.sqlite3"
    init(f"from pathlib import Path; from campus247.infrastructure.repositories.sqlite_conversations import "
         f"SQLiteConversationRepository as R; R(Path(r'{path}'))", path)
    reports = run_workers("conversations", path, ["conversations", "conversations", "conversations", "conversation_readers"])
    assert all(not report["errors"] for report in reports), reports
    written = sum(report["ok"] for report in reports[:3])
    assert written == 3 * WRITES
    assert count(path, "SELECT COUNT(*) FROM conversation") == written
    assert count(path, "SELECT COUNT(*) FROM message") == written
    assert count(path, "SELECT COUNT(DISTINCT conversation_id || sequence) FROM message") == written  # no duplicate sequence


def test_actor_state_loses_nothing_and_a_contended_key_has_one_winner_per_version(database):
    path = database / "actor-state.sqlite3"
    init(f"from pathlib import Path; from campus247.infrastructure.repositories.sqlite_actor_state import "
         f"SQLiteActorStateStore as S; S(Path(r'{path}'))", path)
    reports = run_workers("actor_state", path)
    assert sum(report["ok"] for report in reports) == PROCESSES * WRITES
    assert all(set(report["errors"]) <= {"StorageConflict"} for report in reports), reports
    # Each version of the shared key was won by exactly one process.
    wins = sum(report["race_wins"] for report in reports)
    versions = count(path, "SELECT COUNT(*) FROM unified_state_revision WHERE key='shared'")
    assert wins == versions and 1 <= versions <= WRITES
    assert count(path, "SELECT COUNT(*) FROM unified_actor_state WHERE key LIKE 'own-%'") == PROCESSES * WRITES


def test_idempotency_has_one_creator_per_shared_key_and_loses_no_own_key(database):
    path = database / "idempotency.sqlite3"
    reports = run_workers("idempotency", path)
    assert all(not report["errors"] for report in reports), reports
    assert sum(report["ok"] for report in reports) == PROCESSES * WRITES
    assert sum(report["created_shared"] for report in reports) == WRITES  # exactly one creator per shared key
    assert count(path, "SELECT COUNT(*) FROM idempotency_record") == PROCESSES * WRITES + WRITES
