"""Retained runtime startup must not adopt unrelated processes or hide failure."""
import importlib.util
import asyncio
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("knowledge_platform_runtime", ROOT / "scripts/knowledge_platform_runtime.py")
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)


@pytest.mark.parametrize("command", [
    '"C:/Some Other App/python.exe" scripts/unrelated.py serve --port 8015 --generation --frontend-port 3015',
    'python.exe scripts/knowledge_platform.py serve --port 8015 --frontend-port 3015',
    'python.exe scripts/knowledge_platform.py serve --port 18015 --generation --frontend-port 3015',
    'python.exe C:/other-workspace/scripts/knowledge_platform.py serve --port 8015 --generation --frontend-port 3015',
])
def test_api_reuse_rejects_unrelated_or_incomplete_command(command):
    assert runtime.matching_processes([{"ProcessId": 42, "CommandLine": command}], "api") == []


def test_existing_platform_commands_and_quoted_paths_are_recognized():
    api = '"C:/Python With Spaces/python.exe" -B scripts/knowledge_platform.py serve --generation --port 8015 --frontend-port 3015'
    worker = 'python.exe "' + str(ROOT / "scripts/knowledge_platform.py") + '" worker'
    assert runtime.matching_processes([{"ProcessId": 10, "CommandLine": api}], "api") == [10]
    assert runtime.matching_processes([{"ProcessId": 11, "CommandLine": worker}], "worker") == [11]


def test_readiness_checks_owned_process_before_accepting_probe():
    class Exited:
        def poll(self):
            return 1
    with pytest.raises(RuntimeError, match="Owned process exited"):
        runtime.wait_for(Exited(), lambda: True)


def test_missing_model_identity_is_rejected_without_starting_process(monkeypatch):
    import httpx
    class Response:
        def raise_for_status(self):
            pass
        def json(self):
            return {"model_id": "unrelated-model", "model_sha": "unknown"}
    monkeypatch.setattr(httpx, "get", lambda *args, **kwargs: Response())
    with pytest.raises(RuntimeError, match="Model identity mismatch"):
        runtime.model_identity()


def test_selected_frontend_reuse_requires_exact_path_and_port():
    name = "frontend-knowledge-automation-20261027-13"
    command = 'node.exe next start "' + str(runtime.STATE / name) + '" -H 127.0.0.1 -p 3015'
    rows = [{"ProcessId": 12, "CommandLine": command}]
    assert runtime.matching_processes(rows, "frontend", name) == [12]
    assert runtime.matching_processes(rows, "frontend") == []
    rows[0]["CommandLine"] = command.replace("3015", "3018")
    assert runtime.matching_processes(rows, "frontend", name) == []


@pytest.mark.parametrize("name", ["../frontend-knowledge-v14", "frontend-knowledge-*", "frontend-knowledge-a'; exit", ""])
def test_frontend_selection_rejects_ambiguous_or_shell_input(name):
    with pytest.raises(ValueError):
        runtime.frontend_path(name)


def test_main_runtime_never_adopts_rehearsal_api_or_worker():
    command = 'python.exe scripts/knowledge_platform.py serve --port 8015 --generation --frontend-port 3015 --rehearsal bundle.json'
    assert runtime.matching_processes([{"ProcessId": 14, "CommandLine": command}], "api") == []
    command = 'python.exe scripts/knowledge_platform.py worker --rehearsal bundle.json'
    assert runtime.matching_processes([{"ProcessId": 15, "CommandLine": command}], "worker") == []


@pytest.mark.parametrize("database,schema,accepted", [
    (runtime.DB_NAME, "0018", True), (runtime.DB_NAME, "0022", True),
    (runtime.DB_NAME, "0020", False), ("another_database", "0022", False),
])
def test_database_identity_retains_exact_database_and_reviewed_schema_guard(monkeypatch, database, schema, accepted):
    class Transaction:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
    class Connection:
        def transaction(self, **kwargs):
            assert kwargs == {"readonly": True}
            return Transaction()
        async def fetchval(self, query):
            return database if "current_database" in query else schema
        async def close(self):
            pass
    async def connect(**kwargs):
        return Connection()
    monkeypatch.setattr(runtime, "connection", lambda: {})
    monkeypatch.setattr(runtime.asyncpg, "connect", connect)
    if accepted:
        assert asyncio.run(runtime.database_identity()) == {"database": database, "schema": schema}
    else:
        with pytest.raises(RuntimeError, match="identity mismatch"):
            asyncio.run(runtime.database_identity())


def test_explicit_0022_migration_does_not_backfill_content(monkeypatch):
    import knowledge_platform
    from alembic import command
    calls = []
    monkeypatch.setattr(knowledge_platform, "connection", lambda: {
        "host": "127.0.0.1", "port": 55437, "database": runtime.DB_NAME,
        "user": "synthetic", "password": "synthetic"})
    monkeypatch.setattr(command, "upgrade", lambda config, revision: calls.append(revision))
    monkeypatch.setattr(knowledge_platform, "backfill_known_inputs", lambda: pytest.fail("No content backfill for rollout"))
    knowledge_platform.migrate("0022")
    assert calls == ["0022"]
    with pytest.raises(ValueError):
        knowledge_platform.migrate("head")


@pytest.mark.parametrize("change", [
    {"state": "STOPPED"}, {"database_verified": False}, {"tenant": "other-tenant"},
    {"database": "other-database"}, {"pid": 43}, {"age": 31}, {"age": -5},
    {},
])
def test_worker_process_cannot_substitute_for_a_current_scoped_database_pulse(monkeypatch, change):
    import io
    import json
    from datetime import UTC, datetime, timedelta
    from types import SimpleNamespace
    path = runtime.STATE / "resume-20261027T235959123456" / "worker-health.jsonl"
    pulse = {"at": (datetime.now(UTC)-timedelta(seconds=change.get("age", 1))).isoformat(),
        "pid": 42, "database": runtime.DB_NAME, "tenant": runtime.TENANT,
        "state": "IDLE", "database_verified": True, **{k:v for k,v in change.items() if k != "age"}}
    data = (json.dumps(pulse)+"\n").encode()
    monkeypatch.setattr(Path, "open", lambda *a, **k: io.BytesIO(data))
    monkeypatch.setattr(Path, "stat", lambda *a, **k: SimpleNamespace(st_size=len(data)))
    monkeypatch.setattr(runtime, "checked_path", lambda p, root: p)
    rows = [{"ProcessId":42, "CommandLine":f'python.exe scripts/knowledge_platform.py worker --worker-heartbeat "{path}"'}]
    if change:
        with pytest.raises(RuntimeError, match="stale, stopped, unverified or outside scope"):
            runtime.worker_state(rows)
    else:
        # Venv wrapper and reporting interpreter are one loop, not two workers.
        assert runtime.worker_state(rows+[{**rows[0], "ProcessId":44}])["pid"] == 42


def test_worker_with_no_pulse_or_multiple_workers_is_not_ready():
    rows = [{"ProcessId":42, "CommandLine":"python.exe scripts/knowledge_platform.py worker"}]
    with pytest.raises(RuntimeError, match="no verifiable loop pulse"):
        runtime.worker_state(rows)
    with pytest.raises(RuntimeError, match="Exactly one"):
        runtime.worker_state(rows+[{**rows[0], "ProcessId":43}])


def test_alert_settings_come_from_env_and_nothing_else_does(tmp_path):
    env = tmp_path / ".env"
    env.write_text(
        "OPENAI_KEY=do-not-pass\n"
        "CAMPUS247_ALERT_TELEGRAM_TOKEN_FILE=C:/Some Folder/token.key\n"
        "# CAMPUS247_ALERT_SMTP_HOST=commented.example\n"
        'CAMPUS247_ALERT_TELEGRAM_CHAT_ID="12345"\n',
        encoding="utf-8")
    assert runtime.alert_environment(env) == {
        "CAMPUS247_ALERT_TELEGRAM_TOKEN_FILE": "C:/Some Folder/token.key",
        "CAMPUS247_ALERT_TELEGRAM_CHAT_ID": "12345",
    }


def test_a_missing_env_file_means_only_the_log_channel(tmp_path):
    assert runtime.alert_environment(tmp_path / "absent.env") == {}
