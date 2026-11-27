"""F0.5: a tool whose feature is off disappears from the registry and cannot be executed; RAG options follow the flags."""
from __future__ import annotations

import asyncio

import pytest

from campus247.agent.tools.registry import ToolDefinition, ToolRegistry, ToolValidationError
from campus247.application.features.service import FeatureService
from campus247.features import runtime
from campus247.rag_v2 import answer_cache
from campus247.rag_v2.verification import verbatim


@pytest.fixture(autouse=True)
def _clean():
    yield
    runtime.uninstall()


def registry():
    return ToolRegistry({"procedure_check": ToolDefinition("procedure_check", "procedure_check", "d", False, False),
                         "plain": ToolDefinition("plain", "plain", "d", False, False)})


def test_without_a_service_everything_is_allowed():
    r = registry()
    assert r.has_tool("procedure_check") and r.available_tool_ids() == ["procedure_check", "plain"]


def test_off_tool_is_hidden_and_refused_even_with_an_old_preview():
    runtime.install(FeatureService())  # agent.procedures is off by default
    r = registry()
    assert r.available_tool_ids() == ["plain"] and not r.has_tool("procedure_check")
    with pytest.raises(ToolValidationError):
        r.validate_candidate("procedure_check", {})

    async def run():
        return await r.execute_with_policy("procedure_check", lambda: asyncio.sleep(0))

    with pytest.raises(ToolValidationError):
        asyncio.run(run())


def test_rag_options_keep_env_behaviour_and_obey_overrides(monkeypatch):
    monkeypatch.setenv("CAMPUS247_RAG_ANSWER_CACHE", "on")
    monkeypatch.setenv("CAMPUS247_RAG_SKIP_VERBATIM_SEMANTIC", "shadow")
    assert answer_cache.enabled() and verbatim.mode() == "shadow"  # nothing installed
    env = {"CAMPUS247_RAG_ANSWER_CACHE": "on", "CAMPUS247_RAG_SKIP_VERBATIM_SEMANTIC": "shadow"}
    runtime.install(FeatureService(env=env))
    assert answer_cache.enabled() and verbatim.mode() == "shadow"  # same answers through the service
    runtime.install(FeatureService(env={**env, "CAMPUS247_FEATURES_OFF": "chat.answer_cache,chat.verbatim_skip"}))
    assert not answer_cache.enabled() and verbatim.mode() == "off"
    monkeypatch.delenv("CAMPUS247_RAG_ANSWER_CACHE")
    runtime.install(FeatureService())
    assert not answer_cache.enabled()
