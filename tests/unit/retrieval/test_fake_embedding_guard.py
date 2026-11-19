from __future__ import annotations

import ast
import importlib
import importlib.util
import os
from pathlib import Path
import subprocess
import sys

import asyncpg
import httpx
import pytest

from campus247.infrastructure.retrieval import vector


ROOT = Path(__file__).resolve().parents[3]
FAKE_MODULE = "campus247_worker.ingestion.embed_fake"
NON_TEST_PROFILES = ("dev", "development", "staging", "production", "", "unknown")


@pytest.mark.parametrize("environment", (*NON_TEST_PROFILES, None, "test"))
def test_fresh_import_requires_explicit_test_profile(environment):
    # A fresh interpreter proves the import guard without pytest/module-cache help.
    env = os.environ.copy()
    env.pop("ENVIRONMENT", None)
    if environment is not None:
        env["ENVIRONMENT"] = environment
    code = """
import importlib, os, sys, types
sys.path[:0] = sys.argv[1:]
sys.modules['pytest'] = types.ModuleType('pytest')
try:
    module = importlib.import_module('campus247_worker.ingestion.embed_fake')
except RuntimeError as error:
    assert os.getenv('ENVIRONMENT') != 'test'
    assert str(error) == 'fake embedding requires the explicit test profile'
else:
    assert os.getenv('ENVIRONMENT') == 'test'
    assert module.DeterministicEmbeddingAdapter(dimension=3).profile.model_id.startswith('test-only/')
"""
    result = subprocess.run(
        [sys.executable, "-B", "-c", code,
         str(ROOT / "services/api/src"), str(ROOT / "services/worker/src")],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("environment", NON_TEST_PROFILES)
def test_cached_fake_rejects_construction_and_use_after_profile_change(monkeypatch, environment):
    monkeypatch.syspath_prepend(str(ROOT / "services/worker/src"))
    monkeypatch.setenv("ENVIRONMENT", "test")
    module = importlib.import_module(FAKE_MODULE)
    adapter = module.DeterministicEmbeddingAdapter(dimension=3)
    monkeypatch.setenv("ENVIRONMENT", environment)

    def forbidden(*args, **kwargs):
        pytest.fail("rejected profile reached fake vector generation")

    monkeypatch.setattr(module.hashlib, "sha256", forbidden)
    with pytest.raises(RuntimeError, match="explicit test profile"):
        module.DeterministicEmbeddingAdapter(dimension=3)
    for operation in (lambda: adapter.embed_text("text"),
                      lambda: adapter.embed_query("text"),
                      lambda: adapter.embed_batch(["text"]),
                      lambda: adapter.embed_documents(["text"])):
        with pytest.raises(RuntimeError, match="explicit test profile"):
            operation()


def test_production_import_graph_has_no_fake_dependency():
    fake_path = ROOT / "services/worker/src/campus247_worker/ingestion/embed_fake.py"
    for directory in (ROOT / "services", ROOT / "scripts"):
        for path in directory.rglob("*.py"):
            if path == fake_path:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    names = [node.module or "", *(alias.name for alias in node.names)]
                elif isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                    names = [node.value]  # Also catch literal dynamic imports.
                else:
                    continue
                assert not any("embed_fake" in name or "DeterministicEmbeddingAdapter" in name
                               for name in names), str(path)


class ForbiddenDatabase:
    def __getattr__(self, name):
        pytest.fail("rejected embedding configuration reached a database")


@pytest.fixture
def forbid_external_access(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("rejected embedding configuration reached DB/provider/config access")

    monkeypatch.setattr(asyncpg, "connect", forbidden)
    monkeypatch.setattr(asyncpg, "create_pool", forbidden)
    monkeypatch.setattr(httpx, "Client", forbidden)
    monkeypatch.setattr(httpx, "AsyncClient", forbidden)
    monkeypatch.setattr(vector, "load_database_url", forbidden)
    return forbidden


@pytest.mark.asyncio
@pytest.mark.parametrize("environment", (*NON_TEST_PROFILES, "test"))
@pytest.mark.parametrize("connection", ("default", "url", "pool", "direct"))
async def test_vector_rejects_before_db_or_provider_access(
    monkeypatch, forbid_external_access, environment, connection,
):
    monkeypatch.setenv("ENVIRONMENT", environment)
    kwargs = {}
    if connection == "url":
        kwargs["database_url"] = "postgresql://unused.invalid/synthetic"
    if connection == "pool":
        kwargs["db_pool"] = ForbiddenDatabase()
    adapter = vector.VectorSearchAdapter(**kwargs)
    conn = ForbiddenDatabase() if connection == "direct" else None
    with pytest.raises(RuntimeError, match="approved embedding adapter and verified active manifest"):
        await adapter.search("synthetic query", conn=conn)


@pytest.mark.parametrize("environment", (*NON_TEST_PROFILES, None))
def test_in_memory_vectors_cannot_bypass_runtime_profile(monkeypatch, environment):
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    if environment is not None:
        monkeypatch.setenv("ENVIRONMENT", environment)
    adapter = vector.VectorSearchAdapter()
    entry = vector.VectorIndexEntry("c", "v", "s", "synthetic", [1.0, 0.0, 0.0])
    with pytest.raises(RuntimeError, match="explicit test profile"):
        adapter.add_entry(entry)
    with pytest.raises(RuntimeError, match="explicit test profile"):
        adapter.search(query_vector=[1.0, 0.0, 0.0])


@pytest.mark.parametrize("connection", ("url", "pool", "direct"))
def test_explicit_test_fixture_cannot_use_database(connection):
    kwargs = {"environment": "test"}
    if connection == "url":
        kwargs["database_url"] = "postgresql://unused.invalid/synthetic"
    if connection == "pool":
        kwargs["db_pool"] = ForbiddenDatabase()
    adapter = vector.VectorSearchAdapter(**kwargs)
    conn = ForbiddenDatabase() if connection == "direct" else None
    with pytest.raises(RuntimeError, match="cannot access a database"):
        adapter.search(query_vector=[1.0, 0.0, 0.0], conn=conn)


@pytest.mark.asyncio
@pytest.mark.parametrize("environment", (*NON_TEST_PROFILES, "test"))
async def test_ingestion_rejects_before_db_or_provider_access(
    monkeypatch, forbid_external_access, environment,
):
    monkeypatch.setenv("ENVIRONMENT", environment)
    spec = importlib.util.spec_from_file_location("guarded_ingestion", ROOT / "scripts/run_ingestion.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "load_database_url", forbid_external_access)
    with pytest.raises(RuntimeError, match="approved embedding adapter and verified active manifest"):
        await module.run_ingestion()
