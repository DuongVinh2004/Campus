"""Launcher/runtime selection must fail before any existing data or model is opened."""
import asyncio
import importlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

def runtime_module():
    return importlib.import_module("knowledge_parser_runtime")

def result(**changes):
    data = {"python": [3, 12, 14], "packages": {"pypdf": "6.19.0", "pdfminer.six": "20251230"}}
    data.update(changes)
    return SimpleNamespace(returncode=0, stdout=json.dumps(data), stderr="")

def test_project_commands_use_the_retained_runtime_instead_of_the_blocked_venv():
    scripts = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))["scripts"]
    expected = r"infra\local\rag-fixture\.venv\Scripts\python.exe -B scripts/campus.py "
    assert scripts["dev"] == scripts["start"] == expected + "start"
    assert scripts["build"] == expected + "build"

def test_parser_uses_the_current_interpreters_base_installation_without_path_fallback(monkeypatch):
    module = runtime_module()
    calls = []
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-not-to-be-inherited")
    def run(args, **kwargs):
        calls.append((args, kwargs))
        return result()
    monkeypatch.setattr(module.subprocess, "run", run)
    selected = module.resolve_parser_python(ROOT)
    assert selected == (Path(sys.base_prefix) / "python.exe").resolve(strict=True)
    assert len(calls) == 1 and calls[0][0][0] == str(selected)
    assert calls[0][0][1:3] == ["-B", "-c"]
    assert calls[0][1]["cwd"] == ROOT
    assert "OPENAI_API_KEY" not in calls[0][1]["env"]
    assert "services/worker/src" in calls[0][1]["env"]["PYTHONPATH"].replace("\\", "/")

@pytest.mark.parametrize("probe", [
    SimpleNamespace(returncode=1, stdout="", stderr="An Application Control policy has blocked this file."),
    SimpleNamespace(returncode=0, stdout="not-json", stderr=""),
    SimpleNamespace(returncode=0, stdout="x" * 20001, stderr=""),
    result(python=[3, 14, 7]),
    result(packages={"pypdf": "6.19.0", "pdfminer.six": None}),
])
def test_unavailable_or_incomplete_parser_fails_without_fallback(monkeypatch, probe):
    module = runtime_module()
    calls = []
    monkeypatch.setattr(module.subprocess, "run", lambda *args, **kwargs: calls.append(args) or probe)
    with pytest.raises(RuntimeError, match="parser runtime"):
        module.resolve_parser_python(ROOT)
    assert len(calls) == 1

def test_missing_base_interpreter_is_not_replaced_by_a_different_python(monkeypatch, tmp_path):
    module = runtime_module()
    monkeypatch.setattr(module.sys, "base_prefix", str(tmp_path))
    monkeypatch.setattr(module.subprocess, "run", lambda *args, **kwargs: pytest.fail("No process may start"))
    with pytest.raises(RuntimeError, match="parser runtime"):
        module.resolve_parser_python(ROOT)

def test_parser_preflight_happens_before_database_and_model_composition(monkeypatch):
    platform = importlib.import_module("knowledge_platform")
    def unavailable(*args):
        raise RuntimeError("parser runtime unavailable")
    async def forbidden(*args, **kwargs):
        pytest.fail("No database/model composition may start before parser preflight")
    monkeypatch.setattr(platform, "resolve_parser_python", unavailable)
    monkeypatch.setattr(platform, "components", forbidden)
    with pytest.raises(RuntimeError, match="parser runtime"):
        asyncio.run(platform.work(once=True))
