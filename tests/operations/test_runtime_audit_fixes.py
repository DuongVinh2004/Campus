"""Operational runtime regressions with fake processes, identities and HTTP."""
import asyncio
import json
import sys
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import knowledge_platform as platform_script
import knowledge_platform_runtime as runtime
from campus247.application.conversation.messages import (
    ContentFormat, ConversationRecord, ConversationStatus, MessageRecord, SenderType,
)
from campus247.bootstrap.settings import Settings
from campus247.domain.shared.values import generate_uuid7
from campus247.infrastructure.identity.local_student import LocalStudentIdentityAdapter
from campus247.infrastructure.repositories.sqlite_conversations import SQLiteConversationRepository
from campus247.ports.identity import AccountState, IdentityContext, IdentityRole
from campus247.presentation.identity import IdentityMiddleware


def actor():
    now = datetime.now(UTC)
    return IdentityContext(generate_uuid7(), "local-test", "local-test", (IdentityRole.STUDENT,),
        "Sinh viên local", now, now+timedelta(hours=1), tenant_id=platform_script.TENANT,
        session_id="test-session", is_synthetic=False, student_code="LOCAL-STUDENT-TEST")


@pytest.fixture
def operational(monkeypatch, tmp_path):
    import campus247.bootstrap.app as bootstrap
    import campus247.infrastructure.identity.local_owner as owner
    import campus247.infrastructure.identity.local_student as student
    import campus247.application.document_request.local_preparation as preparation
    first, second = actor(), actor()
    actors = {"first": first, "second": second,
        "owner": replace(first, roles=(IdentityRole.KNOWLEDGE_ADMIN,))}
    class Adapter:
        def __init__(self, *args):
            pass
        def directory(self):
            return {}
        def authenticate(self, username, password):
            if username not in actors or password != "test-password":
                raise ValueError("Invalid credentials")
            return username
        def resolve_token(self, token):
            return actors[token]
    def create_app(**kwargs):
        app = FastAPI()
        app.state.actor_state_store = SimpleNamespace(get=lambda *a: None)
        app.add_middleware(IdentityMiddleware, adapter=Adapter(),
            session_service=SimpleNamespace(is_revoked=lambda token: token == "revoked"))
        return app
    async def components(**kwargs):
        async def noop():
            pass
        return (SimpleNamespace(close=noop), Settings(_env_file=None),
            SimpleNamespace(schedules=SimpleNamespace(serve=noop)), SimpleNamespace())
    monkeypatch.delenv("CAMPUS247_RAG_ENGINE", raising=False)
    monkeypatch.setenv("CAMPUS247_IDEMPOTENCY_DB", str(tmp_path / "action-idempotency.sqlite3"))
    monkeypatch.setattr(platform_script, "components", components)
    monkeypatch.setattr(platform_script, "rehearsal_bundle_paths", lambda _: {
        name: tmp_path / name for name in ("actor-state.sqlite3", "action-idempotency.sqlite3", "conversations.sqlite3")})
    monkeypatch.setattr(bootstrap, "create_app", create_app)
    monkeypatch.setattr(owner, "LocalOwnerIdentityAdapter", Adapter)
    monkeypatch.setattr(student, "LocalCampusIdentityAdapter", Adapter)
    monkeypatch.setattr(preparation, "LocalPreparationService", lambda *a: None)
    app = asyncio.run(platform_script.make_app(frontend_port=3015))
    return app, actors, SQLiteConversationRepository(tmp_path / "conversations.sqlite3")


def test_login_uses_only_httponly_cookie(operational):
    app, actors, _ = operational
    with TestClient(app) as client:
        response = client.post("/v1/knowledge/platform/session",
            json={"username": "first", "password": "test-password"})
        assert response.status_code == 200
        assert response.json() == {"user_id": actors["first"].subject_id, "roles": ["STUDENT"],
            "is_synthetic_identity": False, "identity_provider": "local", "university_identity_verified": False}
        cookie = response.headers["set-cookie"].lower()
        assert all(value in cookie for value in ("auth_token=", "httponly", "samesite=strict", "max-age=3600"))
        assert response.headers["cache-control"] == "no-store"


def test_login_keeps_origin_and_password_guards(operational):
    with TestClient(operational[0]) as client:
        path = "/v1/knowledge/platform/session"
        body = {"username": "first", "password": "test-password"}
        assert client.post(path, json=body, headers={"Origin": "https://other.test"}).status_code == 403
        assert client.post(path, json={**body, "password": "wrong"}).status_code == 401


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"])
def test_operational_schema_routes_are_not_public(operational, path):
    with TestClient(operational[0]) as client:
        assert client.get(path).status_code == 404


@pytest.mark.parametrize("path", ["fonts/inter-vietnamese.woff2", "fonts/inter-latin.woff2",
    "fonts/inter-latin-ext.woff2", "images/home-banner-1-2.918477da.webp", "_next/static/test.js"])
def test_proxy_allows_build_assets(operational, monkeypatch, path):
    calls = []
    class Client:
        def __init__(self, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def get(self, url, **kwargs):
            calls.append(url)
            return httpx.Response(200, content=b"asset", headers={"content-type": "font/woff2"})
    monkeypatch.setattr(httpx, "AsyncClient", Client)
    with TestClient(operational[0]) as client:
        response = client.get("/"+path)
        assert response.status_code == 200
        assert response.content == b"asset"
        assert client.post("/"+path).status_code == 405
    assert calls == ["http://127.0.0.1:3015/"+path]


@pytest.mark.parametrize("path", ["fonts/%2e%2e/secret", "fonts/a..woff2", "fonts/a%5Cb.woff2", "admin", "staff", "memory"])
def test_proxy_rejects_traversal_and_additional_pages(operational, monkeypatch, path):
    monkeypatch.setattr(httpx, "AsyncClient", lambda **k: pytest.fail("Blocked path was forwarded"))
    with TestClient(operational[0]) as client:
        assert client.get("/"+path).status_code == 404


def test_proxy_keeps_response_size_limit(operational, monkeypatch):
    class Client:
        def __init__(self, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def get(self, *args, **kwargs):
            return httpx.Response(200, content=b"x"*(10*1024**2+1))
    monkeypatch.setattr(httpx, "AsyncClient", Client)
    with TestClient(operational[0]) as client:
        assert client.get("/fonts/large.woff2").status_code == 502


def test_student_login_limit_is_per_username(monkeypatch):
    adapter = LocalStudentIdentityAdapter(None, "test")
    directory = {"username": "student-local", "salt": "00", "password_hash": b"hash".hex(),
        "signing_key": "00", "subject_id": generate_uuid7()}
    monkeypatch.setattr(adapter, "directory", lambda: directory)
    monkeypatch.setattr("campus247.infrastructure.identity.local_student.hashlib.scrypt", lambda *a, **k: b"hash")
    for _ in range(5):
        with pytest.raises(ValueError, match="Invalid credentials"):
            adapter.authenticate("another-student", "wrong")
    with pytest.raises(ValueError, match="rate limited"):
        adapter.authenticate("another-student", "wrong")
    assert isinstance(adapter.authenticate("student-local", "test-password"), str)
    with pytest.raises(ValueError, match="rate limited"):
        adapter.authenticate("another-student", "wrong")


def test_student_login_window_expires(monkeypatch):
    adapter = LocalStudentIdentityAdapter(None, "test")
    clock = [0]
    monkeypatch.setattr("campus247.infrastructure.identity.local_student.time.monotonic", lambda: clock[0])
    monkeypatch.setattr(adapter, "directory", lambda: {"username": "student-local", "salt": "00", "password_hash": "00"})
    monkeypatch.setattr("campus247.infrastructure.identity.local_student.hashlib.scrypt", lambda *a, **k: b"wrong")
    for _ in range(5):
        with pytest.raises(ValueError, match="Invalid credentials"):
            adapter.authenticate("student-local", "wrong")
    clock[0] = 60
    with pytest.raises(ValueError, match="Invalid credentials"):
        adapter.authenticate("student-local", "wrong")


def test_conversation_catalog_is_owned_filtered_and_read_only(operational):
    app, actors, repository = operational
    now = datetime.now(UTC)
    rows = []
    async def seed():
        for username, mode, title, expired in [
            ("first", "persistent", "Học phí kỳ một", False),
            ("first", "persistent", "Học phí kỳ hai", False),
            ("first", "temporary", "Học phí bí mật", False),
            ("second", "persistent", "Riêng sinh viên khác", False),
            ("first", "persistent", "Đã hết hạn", True),
        ]:
            record = ConversationRecord(generate_uuid7(), actors[username].subject_id,
                ConversationStatus.ACTIVE, "WEB", now, now,
                now+timedelta(days=-1 if expired else 30), mode=mode)
            await repository.save_conversation(record)
            if not expired:
                await repository.save_message(MessageRecord(generate_uuid7(), record.id, 1, SenderType.USER,
                    title, ContentFormat.PLAIN_TEXT, now, sender_user_id=actors[username].subject_id))
            rows.append(record)
    asyncio.run(seed())
    with TestClient(app) as client:
        path = "/v1/assistant/conversations"
        assert client.get(path).status_code == 401
        client.cookies.set("auth_token", "first")
        response = client.get(path, params={"title": "HỌC PHÍ", "limit": 1})
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        value = response.json()
        assert value["items"][0]["id"] == rows[0].id
        assert value["items"][0]["can_continue"] is True
        assert value["items"][0]["retention_state"] == "available"
        assert value["items"][0]["mode"] == "persistent"
        assert {"title", "created_at", "updated_at", "conversation_id", "archived", "pinned"} <= value["items"][0].keys()
        assert value["page"]["has_more"] is True
        cursor = value["page"]["next_cursor"]
        next_page = client.get(path, params={"title": "HỌC PHÍ", "limit": 1, "cursor": cursor}).json()
        assert [r["id"] for r in next_page["items"]] == [rows[1].id]
        assert next_page["page"]["has_more"] is False
        assert client.get(path, params={"cursor": cursor, "title": "different"}).status_code == 422
        all_rows = client.get(path).json()["items"]
        assert [r["id"] for r in all_rows] == [rows[i].id for i in (0, 1, 4)]
        assert all_rows[-1]["retention_state"] == "expired"
        assert all_rows[-1]["can_continue"] is False
        for limit in (0, 101):
            assert client.get(path, params={"limit": limit}).status_code == 422
        client.cookies.set("auth_token", "second")
        assert [r["id"] for r in client.get(path).json()["items"]] == [rows[3].id]
        assert client.get(path, params={"cursor": cursor, "title": "HỌC PHÍ"}).status_code == 422
        client.cookies.set("auth_token", "owner")
        assert client.get(path).status_code == 403
        assert client.post(path+":preview", json={}).status_code in {404, 405}
        assert client.post(path+":confirm", json={}).status_code in {404, 405}


@pytest.mark.parametrize("change", [
    {"tenant_id": "another-tenant"}, {"session_id": ""}, {"is_synthetic": True},
    {"account_state": AccountState.SUSPENDED}, {"roles": (IdentityRole.STUDENT, IdentityRole.SYSTEM_ADMIN)},
    {"auth_time": datetime.now(UTC)-timedelta(hours=2), "expires_at": datetime.now(UTC)-timedelta(hours=1)},
])
def test_catalog_rejects_ineligible_identity(operational, change):
    app, actors, _ = operational
    actors["first"] = replace(actors["first"], **change)
    with TestClient(app) as client:
        client.cookies.set("auth_token", "first")
        assert client.get("/v1/assistant/conversations").status_code == 403


@pytest.mark.parametrize("token", ["unknown", "revoked"])
def test_catalog_rejects_invalid_or_revoked_session(operational, token):
    with TestClient(operational[0]) as client:
        client.cookies.set("auth_token", token)
        assert client.get("/v1/assistant/conversations").status_code == 401


def test_catalog_preserves_metadata_and_matches_shared_page_contract(operational):
    from campus247.application.conversation.catalog import ConversationCatalogService
    app, actors, repository = operational
    now = datetime.now(UTC)
    records = [ConversationRecord(generate_uuid7(), actors["first"].subject_id,
        ConversationStatus.ACTIVE, "WEB", now, now, now+timedelta(days=30), mode="persistent") for _ in range(2)]
    async def seed():
        for record in records:
            await repository.save_conversation(record)
    asyncio.run(seed())
    metadata = {record.id: SimpleNamespace(version=3, payload={"conversation_id": record.id,
        "title": "Tên đã lưu", "pinned": True, "archived": i == 1}) for i, record in enumerate(records)}
    app.state.actor_state_store.get = lambda scope, namespace, key: metadata.get(key)
    reference = ConversationCatalogService(app.state.actor_state_store, tenant=platform_script.TENANT,
        authorize=lambda actor: None, tokens=None, conversations=repository)
    expected = asyncio.run(reference.page(replace(actors["first"], is_synthetic=True)))
    with TestClient(app) as client:
        client.cookies.set("auth_token", "first")
        value = client.get("/v1/assistant/conversations").json()
        assert value == expected
        assert len(value["items"]) == 1
        assert value["items"][0]["pinned"] is True
        assert value["items"][0]["version"] == 3


@pytest.mark.parametrize("engine", ["v1", "v2"])
@pytest.mark.parametrize("pythonpath", [None, "", "retained-modules"])
def test_start_passes_explicit_engine_and_index_to_api(monkeypatch, engine, pythonpath):
    from io import BytesIO
    import os
    calls, receipts = [], []
    if pythonpath is None:
        monkeypatch.delenv("PYTHONPATH", raising=False)
    else:
        monkeypatch.setenv("PYTHONPATH", pythonpath)
    monkeypatch.setattr(Path, "is_file", lambda p: True)
    monkeypatch.setattr(Path, "is_dir", lambda p: True)
    monkeypatch.setattr(Path, "mkdir", lambda *a, **k: None)
    monkeypatch.setattr(Path, "open", lambda *a, **k: BytesIO())
    monkeypatch.setattr(runtime, "connection", lambda: {})
    monkeypatch.setattr(runtime, "model_identity", lambda: None)
    monkeypatch.setattr(runtime, "listening", lambda port: port == runtime.DB_PORT)
    async def empty():
        return {}
    monkeypatch.setattr(runtime, "database_identity", empty)
    monkeypatch.setattr(runtime, "queue_state", empty)
    monkeypatch.setattr(runtime, "process_inventory", lambda *a: [])
    monkeypatch.setattr(runtime, "retain", lambda p, r: receipts.append(r))
    monkeypatch.setattr(runtime.subprocess, "Popen", lambda command, **kwargs:
        calls.append((command, kwargs)) or SimpleNamespace(pid=42))
    waits = []
    monkeypatch.setattr(runtime, "wait_for", lambda process, check, **kwargs: waits.append(kwargs) or {})
    report = runtime.start("frontend-knowledge-test", defer_worker=True, engine=engine,
        rag_v2_index="data/rag_v2_index/embedded2")
    api = next(kwargs for command, kwargs in calls if "--generation" in command)
    assert api["env"]["CAMPUS247_RAG_ENGINE"] == engine
    assert Path(api["env"]["CAMPUS247_RAG_V2_INDEX"]) == ROOT / "data/rag_v2_index/embedded2"
    assert report["engine"] == engine
    assert Path(report["rag_v2_index"]) == ROOT / "data/rag_v2_index/embedded2"
    assert receipts == [report]
    assert waits[-1]["seconds"] == 180
    vendor = str(ROOT / "data/rag_v2_vendor")
    expected = os.pathsep.join([vendor, pythonpath] if pythonpath else [vendor])
    assert api["env"].get("PYTHONPATH") == (expected if engine == "v2" else pythonpath)
    for command, kwargs in calls:
        if "--generation" not in command:
            assert kwargs["env"].get("PYTHONPATH") == pythonpath
    assert os.environ.get("PYTHONPATH") == pythonpath


@pytest.fixture
def frontend_snapshots(monkeypatch, tmp_path):
    import os
    monkeypatch.setattr(runtime, "ROOT", tmp_path)
    monkeypatch.setattr(runtime, "STATE", tmp_path)
    def snapshot(name, modified, built_at=None, exit_code=0):
        build = tmp_path / name / ".next/BUILD_ID"
        build.parent.mkdir(parents=True)
        build.write_text(name, encoding="utf-8")
        os.utime(build, (modified, modified))
        if built_at is not None:
            (tmp_path / (name + "-build.json")).write_text(
                json.dumps({"exit_code": exit_code, "built_at": built_at}), encoding="utf-8")
        return name
    return snapshot


def test_frontend_defaults_to_latest_recorded_build_not_name_or_mtime(frontend_snapshots):
    frontend_snapshots("frontend-knowledge-z-old", 300, "2026-10-30T20:00:00+00:00")
    newest = frontend_snapshots("frontend-knowledge-a-new", 100, "2026-11-01T20:00:00Z")
    frontend_snapshots("frontend-knowledge-failed", 400, "2026-11-02T20:00:00Z", exit_code=1)
    assert runtime.select_frontend() == newest


def test_frontend_without_build_time_uses_build_id_mtime(frontend_snapshots):
    frontend_snapshots("frontend-knowledge-z-old", 100)
    newest = frontend_snapshots("frontend-knowledge-a-new", 300)
    (runtime.STATE / (newest + "-build.json")).write_text(
        json.dumps({"exit_code": 0, "stdout": "built", "stderr": ""}), encoding="utf-8")
    (runtime.STATE / "frontend-knowledge-unbuilt").mkdir()
    assert runtime.select_frontend() == newest


def test_explicit_frontend_name_wins_over_latest(frontend_snapshots, monkeypatch):
    older = frontend_snapshots("frontend-knowledge-older", 100)
    frontend_snapshots("frontend-knowledge-newest", 300)
    calls = []
    monkeypatch.setattr(sys, "argv", ["knowledge_platform_runtime.py", "start", "--frontend-name", older])
    monkeypatch.setattr(runtime, "start", lambda name, **kwargs: calls.append(runtime.select_frontend(name)))
    runtime.main()
    assert calls == [older]


def test_frontend_selection_without_a_build_fails_without_building(monkeypatch, tmp_path):
    monkeypatch.setattr(runtime, "STATE", tmp_path)
    monkeypatch.setattr(runtime.subprocess, "run", lambda *a, **k: pytest.fail("No automatic build"))
    with pytest.raises(RuntimeError, match="frontend"):
        runtime.select_frontend()


@pytest.mark.parametrize("command", ["start", "status"])
def test_campus_passes_complete_v2_runtime_options_without_external_environment(monkeypatch, command):
    import runpy
    calls = []
    monkeypatch.delenv("CAMPUS247_RAG_ENGINE", raising=False)
    monkeypatch.delenv("CAMPUS247_RAG_V2_INDEX", raising=False)
    monkeypatch.delenv("PYTHONPATH", raising=False)
    monkeypatch.setattr(sys, "argv", ["campus.py", command])
    monkeypatch.setattr(runtime.subprocess, "run", lambda args, **kwargs:
        calls.append((args, kwargs)) or SimpleNamespace(returncode=0, stdout="", stderr=""))
    with pytest.raises(SystemExit) as result:
        runpy.run_path(str(ROOT / "scripts/campus.py"), run_name="__main__")
    assert result.value.code == 0
    args, kwargs = calls[0]
    assert args[4:] == ["scripts/knowledge_platform_runtime.py", command, "--defer-worker",
        "--engine", "v2", "--rag-v2-index", "data/rag_v2_index/embedded2"]
    assert kwargs["cwd"] == ROOT
    assert len(calls) == 1


def test_start_cli_defaults_to_v2(monkeypatch):
    calls = []
    monkeypatch.setattr(sys, "argv", ["knowledge_platform_runtime.py", "start"])
    monkeypatch.setattr(runtime, "start", lambda *a, **k: calls.append(k))
    runtime.main()
    assert calls[0]["engine"] == "v2"
    assert calls[0]["rag_v2_index"] == "data/rag_v2_index/embedded2"


def test_start_cli_accepts_explicit_engine_and_index(monkeypatch):
    calls = []
    monkeypatch.setattr(sys, "argv", ["knowledge_platform_runtime.py", "start", "--engine", "v1",
        "--rag-v2-index", "data/other-index"])
    monkeypatch.setattr(runtime, "start", lambda *a, **k: calls.append(k))
    runtime.main()
    assert calls[0]["engine"] == "v1"
    assert calls[0]["rag_v2_index"] == "data/other-index"


def test_missing_index_stops_before_any_start_or_state_access(monkeypatch):
    monkeypatch.setattr(Path, "is_dir", lambda p: False)
    monkeypatch.setattr(runtime, "connection", lambda: pytest.fail("No state access without index"))
    monkeypatch.setattr(runtime.subprocess, "Popen", lambda *a, **k: pytest.fail("No process without index"))
    with pytest.raises(RuntimeError, match="index missing"):
        runtime.start()


@pytest.mark.parametrize("requested,enabled", [("v2", False), ("v1", True), ("v2", None)])
def test_api_reuse_rejects_wrong_or_unknown_engine_before_login(monkeypatch, requested, enabled):
    class Client:
        def __init__(self, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def get(self, path):
            assert path == "/health/ready"
            return httpx.Response(200, json={"status": "ready", "rag_v2": {"enabled": enabled}},
                request=httpx.Request("GET", "http://test/health/ready"))
    monkeypatch.setattr(runtime.httpx, "Client", Client)
    with pytest.raises(RuntimeError, match="RAG engine mismatch"):
        runtime.api_state(engine=requested)


def test_readiness_polls_past_slow_index_load_and_stays_bounded(monkeypatch):
    clock, probes = [0], []
    monkeypatch.setattr(runtime.time, "perf_counter", lambda: clock[0])
    monkeypatch.setattr(runtime.time, "sleep", lambda seconds: clock.__setitem__(0, clock[0]+seconds))
    def check():
        probes.append(clock[0])
        if clock[0] < 45:
            raise httpx.ConnectError("still loading")
        return True
    assert runtime.wait_for(None, check, seconds=180) is True
    assert clock[0] == 45
    with pytest.raises(RuntimeError, match="Readiness"):
        runtime.wait_for(None, lambda: (_ for _ in ()).throw(httpx.ConnectError("offline")), seconds=3)
    assert clock[0] <= 48


def test_readiness_reports_engine_mismatch_without_retry(monkeypatch):
    monkeypatch.setattr(runtime.time, "sleep", lambda _: pytest.fail("Engine mismatch must not be retried"))
    with pytest.raises(runtime.EngineMismatch, match="RAG engine mismatch"):
        runtime.wait_for(None, lambda: (_ for _ in ()).throw(runtime.EngineMismatch("RAG engine mismatch")))
